"""Screens tab to manage game screens (opening, level-specific, victory, defeat).

Bu sekme oyuna ait ekranların düzenlenmesini sağlar:
- Başlangıç ekranı
- Her seviye için ayrı tasarım ekranı
- Zafer ekranı
- Yenilgi ekranı

Düzenle butonları ilgili ekranı `ScreenDesignerWindow` ile açar.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, List, Dict, Any
import os
import json
from PIL import Image, ImageTk

from ..screen_designer import ScreenDesignerWindow


class ScreensTab:
    """"Ekranlar" sekmesi: oyunun ekranlarını düzenlemek için arayüz.

    Attributes:
        frame: Sekmenin kök çerçevesi.
    """

    def __init__(self, parent, game_service, level_service, screen_service, sprite_service, effect_service=None):
        """Sekmeyi başlatır ve layout'u kurar.

        Args:
            parent: Notebook ebeveyni
            game_service: Oyun servisi
            level_service: Seviye servisi
            screen_service: Ekran servisi
            sprite_service: Sprite servisi
            effect_service: Efekt servisi
        """
        self.parent = parent
        self.game_service = game_service
        self.level_service = level_service
        self.screen_service = screen_service
        self.sprite_service = sprite_service
        self.effect_service = effect_service
        
        # Project root for assets
        self._project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../../"))
        self._photo_refs: List[ImageTk.PhotoImage] = []

        self.frame = ttk.Frame(parent, padding=10)
        self.frame.columnconfigure(0, weight=1)

        # Başlık
        ttk.Label(self.frame, text="Ekranlar", style="Subheader.TLabel").grid(row=0, column=0, sticky="w")

        # Üst: Genel ekranlar
        self.general_group = ttk.LabelFrame(self.frame, text="Genel Ekranlar", padding=8)
        self.general_group.grid(row=1, column=0, sticky="ew", pady=(6, 8))
        
        self._general_container = ttk.Frame(self.general_group)
        self._general_container.pack(fill="both", expand=True)

        # Alt: Seviye ekranları
        self.levels_group = ttk.LabelFrame(self.frame, text="Seviye Ekranları", padding=8)
        self.levels_group.grid(row=2, column=0, sticky="nsew")
        self.frame.rowconfigure(2, weight=1)

        # Kaydırılabilir alan kurulumu
        self._levels_canvas = tk.Canvas(self.levels_group, highlightthickness=0, background="#2b2b2b")
        self._levels_scrollbar = ttk.Scrollbar(self.levels_group, orient="vertical", command=self._levels_canvas.yview)
        self._levels_container = ttk.Frame(self._levels_canvas)
        
        self._levels_container.bind(
            "<Configure>",
            lambda e: self._levels_canvas.configure(scrollregion=self._levels_canvas.bbox("all"))
        )
        self._levels_window = self._levels_canvas.create_window((0, 0), window=self._levels_container, anchor="nw")
        self._levels_canvas.configure(yscrollcommand=self._levels_scrollbar.set)
        
        # Genişlik takibi (Canvas genişlediğinde içeriği de genişlet)
        def _on_levels_canvas_resize(event):
            self._levels_canvas.itemconfig(self._levels_window, width=event.width)
        self._levels_canvas.bind("<Configure>", _on_levels_canvas_resize)

        self._levels_scrollbar.pack(side="right", fill="y")
        self._levels_canvas.pack(side="left", fill="both", expand=True)
        
        self._levels_container.columnconfigure(1, weight=1)

        self.refresh()

    def _get_abs_path(self, rel_path: Optional[str]) -> Optional[str]:
        if not rel_path: return None
        if os.path.isabs(rel_path): return rel_path
        return os.path.join(self._project_root, rel_path)

    # Public API
    def refresh(self) -> None:
        """Ekran listelerini yeniler (küçük bir gecikmeyle dosya sistemine zaman tanır)."""
        self.frame.after(300, self._actual_refresh)

    def _actual_refresh(self) -> None:
        """Asıl yenileme mantığı."""
        # Seviye listesini yeniler
        self._refresh_general_screens()
        self._refresh_level_screens()

    def _refresh_general_screens(self) -> None:
        """Genel ekranları (opening, victory, defeat) thumbnailleri ile listeler."""
        for w in self._general_container.winfo_children():
            w.destroy()
        self._photo_refs.clear()

        root = self.frame.winfo_toplevel()
        game_id = getattr(root, "current_game_id", None)
        if not game_id:
            return

        screens_to_show = [
            ("opening", "Başlangıç Ekranı", "menu"),
            ("victory", "Zafer Ekranı", "ending"),
            ("defeat", "Yenilgi Ekranı", "ending")
        ]

        thumb_size = (160, 90)

        for i, (name, label, stype) in enumerate(screens_to_show):
            frame = ttk.Frame(self._general_container, padding=5)
            frame.grid(row=0, column=i, sticky="n", padx=10)
            
            # Thumbnail alanı
            thumb_lbl = ttk.Label(frame, background="#2b2b2b", relief="solid", borderwidth=1)
            thumb_lbl.pack(pady=(0, 5))
            
            # 1. Önce kaydedilmiş thumbnail'ı kontrol et (assets/previews/)
            preview_name = f"screen_{game_id}_{name}.png"
            preview_path = os.path.join(self._project_root, "assets", "previews", preview_name)
            
            img_to_load = None
            if os.path.isfile(preview_path):
                img_to_load = preview_path
            else:
                # 2. Kayıtlı thumbnail yoksa arkaplan görselini dene
                sc = self.screen_service.get_screen(game_id, name)
                if sc and sc.data_json:
                    try:
                        data = json.loads(sc.data_json)
                        img_to_load = self._get_abs_path((data.get('background') or {}).get('image'))
                    except: pass

            # Thumbnail yükle veya placeholder oluştur
            photo = None
            if img_to_load and os.path.isfile(img_to_load):
                try:
                    img = Image.open(img_to_load).convert('RGB')
                    img.thumbnail(thumb_size, Image.LANCZOS)
                    # Siyah arkaplan üzerine ortala
                    canvas_img = Image.new('RGB', thumb_size, (40, 44, 52))
                    offset = ((thumb_size[0] - img.size[0]) // 2, (thumb_size[1] - img.size[1]) // 2)
                    canvas_img.paste(img, offset)
                    photo = ImageTk.PhotoImage(canvas_img)
                except: pass

            if not photo:
                # 3. Hiç görsel yoksa standart placeholder oluştur
                placeholder = Image.new('RGB', thumb_size, (60, 63, 65))
                # Ortaya bir ikon veya metin ekleyebiliriz (opsiyonel)
                photo = ImageTk.PhotoImage(placeholder)
                thumb_lbl.configure(text="Tasarım Yok", compound="center", foreground="#888888")
            
            if photo:
                self._photo_refs.append(photo)
                thumb_lbl.configure(image=photo)

            ttk.Label(frame, text=label, font=("Segoe UI", 9, "bold")).pack()
            
            # Düzenle butonu
            btn = ttk.Button(frame, text="Düzenle", 
                             command=lambda n=name, t=stype: self._open_designer(n, t))
            btn.pack(pady=5)

    def _create_screen_preview_block(self, parent, game_id, name, title, stype, thumb_size):
        """Thumbnail + Başlık + Düzenle butonu içeren küçük bir blok oluşturur."""
        frame = ttk.Frame(parent, padding=5)
        
        # Thumbnail alanı
        thumb_lbl = ttk.Label(frame, background="#2b2b2b", relief="solid", borderwidth=1)
        thumb_lbl.pack(pady=(0, 2))
        
        preview_name = f"screen_{game_id}_{name}.png"
        preview_path = os.path.join(self._project_root, "assets", "previews", preview_name)
        
        img_to_load = None
        if os.path.isfile(preview_path):
            img_to_load = preview_path
        else:
            # Arkaplan dene
            sc = self.screen_service.get_screen(game_id, name)
            if sc and sc.data_json:
                try:
                    data = json.loads(sc.data_json)
                    img_to_load = self._get_abs_path((data.get('background') or {}).get('image'))
                except: pass

        photo = None
        if img_to_load and os.path.isfile(img_to_load):
            try:
                img = Image.open(img_to_load).convert('RGB')
                img.thumbnail(thumb_size, Image.LANCZOS)
                canvas_img = Image.new('RGB', thumb_size, (40, 44, 52))
                offset = ((thumb_size[0] - img.size[0]) // 2, (thumb_size[1] - img.size[1]) // 2)
                canvas_img.paste(img, offset)
                photo = ImageTk.PhotoImage(canvas_img)
                self._photo_refs.append(photo)
            except: pass
            
        if photo:
            thumb_lbl.configure(image=photo)
        else:
            thumb_lbl.configure(text="Tasarım Yok", compound="center", foreground="#888888", width=16)

        ttk.Label(frame, text=title, font=("Segoe UI", 8)).pack()
        
        btn = ttk.Button(frame, text="Düzenle", 
                         command=lambda: self._open_designer(name, stype))
        btn.pack(pady=2)
        
        return frame

    def _refresh_level_screens(self) -> None:
        """Seviye listesini yeniler ve her seviye için Oyun + Bilgi ekranı kartı oluşturur."""
        for w in self._levels_container.winfo_children():
            w.destroy()
        
        try:
            root = self.frame.winfo_toplevel()
            game_id = getattr(root, "current_game_id", None)
            if not game_id:
                ttk.Label(self._levels_container, text="Lütfen bir oyun seçin.").grid(row=0, column=0, sticky="w", padx=10, pady=10)
                return

            levels = self.level_service.get_levels(game_id)
            if not levels:
                ttk.Label(self._levels_container, text="Henüz seviye oluşturulmamış.").grid(row=0, column=0, sticky="w", padx=10, pady=10)
                return

            # Seviye görselleri için biraz daha küçük thumbnail
            thumb_size = (140, 80)

            current_row = 0
            for idx, lvl in enumerate(levels):
                if current_row > 0:
                    ttk.Separator(self._levels_container, orient="horizontal").grid(row=current_row, column=0, sticky="ew", pady=10)
                    current_row += 1

                row_frame = ttk.Frame(self._levels_container, padding=(0, 5))
                row_frame.grid(row=current_row, column=0, sticky="ew", padx=5)
                row_frame.columnconfigure(2, weight=1) # Özet bilgi alanı genişlesin
                current_row += 1

                # --- 1. Oyun Ekranı Bloğu ---
                game_preview = self._create_screen_preview_block(
                    row_frame, game_id, f"level_{lvl.id}", "Oyun Ekranı", "level", thumb_size
                )
                game_preview.grid(row=0, column=0, padx=(0, 5), sticky="n")

                # --- 2. Bilgi Ekranı Bloğu ---
                info_preview = self._create_screen_preview_block(
                    row_frame, game_id, f"level_{lvl.id}_info", "Bilgi Ekranı", "info", thumb_size
                )
                info_preview.grid(row=0, column=1, padx=(0, 15), sticky="n")

                # --- 3. Özet Bilgi (Sağ) ---
                sum_frame = ttk.Frame(row_frame)
                sum_frame.grid(row=0, column=2, sticky="nw", pady=5)
                
                title = f"Seviye #{lvl.level_number}: {lvl.level_name}"
                ttk.Label(sum_frame, text=title, font=("Segoe UI", 11, "bold"), foreground="#cc7832").pack(anchor="w")
                
                stats = f"Hız: {lvl.item_speed} | Max Öğe: {lvl.max_items_on_screen} | Hata Payı: %{lvl.wrong_answer_percentage}"
                ttk.Label(sum_frame, text=stats, font=("Segoe UI", 9), foreground="#a9b7c6").pack(anchor="w", pady=2)
                
                if lvl.level_description:
                    desc = lvl.level_description[:120] + "..." if len(lvl.level_description) > 120 else lvl.level_description
                    ttk.Label(sum_frame, text=desc, font=("Segoe UI", 9, "italic"), foreground="#888888", wraplength=350).pack(anchor="w")

        except Exception as e:
            messagebox.showerror("Ekranlar", f"Seviyeler yüklenemedi: {e}")
            import traceback
            traceback.print_exc()

        except Exception as e:
            messagebox.showerror("Ekranlar", f"Seviyeler yüklenemedi: {e}")
            import traceback
            traceback.print_exc()

    # General screens
    def _edit_opening(self) -> None:
        """Başlangıç ekranı tasarımcısını açar."""
        self._open_designer(screen_name="opening", screen_type="menu")

    def _edit_victory(self) -> None:
        """Zafer ekranı tasarımcısını açar."""
        self._open_designer(screen_name="victory", screen_type="ending")

    def _edit_defeat(self) -> None:
        """Yenilgi ekranı tasarımcısını açar."""
        self._open_designer(screen_name="defeat", screen_type="ending")

    # Level screens
    def _edit_level(self, level_id: int) -> None:
        """Belirtilen seviye için tasarımcısını açar.

        Level ekranı screen_name: "level_<id>", screen_type: "level"
        """
        self._open_designer(screen_name=f"level_{level_id}", screen_type="level")

    def _edit_level_info(self, level_id: int) -> None:
        """Belirtilen seviye için BİLGİ ekranı tasarımcısını açar.

        Bilgi ekranı screen_name: "level_<id>_info", screen_type: "info"
        Bu ekran, seviyeye başlamadan önce gösterilecek açıklama/ipuçları için tasarlanır.
        """
        self._open_designer(screen_name=f"level_{level_id}_info", screen_type="info")

    # Helpers
    def _open_designer(self, screen_name: str, screen_type: str) -> None:
        """Genel amaçlı tasarımcı penceresini açar."""
        try:
            root = self.frame.winfo_toplevel()
            game_id: Optional[int] = getattr(root, "current_game_id", None)
            
            # Servisi öncelikle doğrudan al, yoksa root'tan dene (fallback)
            eff_svc = self.effect_service
            if not eff_svc:
                eff_svc = getattr(root, "effect_service", None)
                
            if not game_id:
                messagebox.showwarning("Ekranlar", "Lütfen önce bir oyun seçin.")
                return
            ScreenDesignerWindow(
                root,
                game_id,
                self.screen_service,
                self.sprite_service,
                self.game_service,
                self.level_service,
                effect_service=eff_svc,
                screen_name=screen_name,
                screen_type=screen_type,
                on_save_callback=self.refresh
            )
        except Exception as e:
            messagebox.showerror("Ekranlar", f"Pencere açılamadı: {e}")
