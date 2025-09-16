"""Screen Designer Window (Toplevel) for creating DB-backed screens like the Opening screen.

This designer uses a single Canvas (default 800x600) and provides a minimal, fast
UI to place widgets via drag & drop. It saves/loads a screen JSON into the DB
using ScreenService. Heavy asset browsing is deferred to existing MediaTab and
SpritesTab; here we focus on positions and basic properties.

Usage:
    win = ScreenDesignerWindow(parent, game_id, screen_service, sprite_service, game_service)

Notes:
- Minimum viable features implemented:
  * Background image select and preview
  * Music file select (stored as path)
  * Add Label and Button widgets; move by drag
  * Edit properties (text, color, font size, action)
  * Save to DB via ScreenService (name='opening', type='menu')
  * Load existing design if present

Future extensions:
- Sprite sheet region picker integration
- Overlay text advanced styling
- Alignment grid and snapping
"""
from __future__ import annotations

import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog
from typing import Dict, Any, Optional, List

from PIL import Image, ImageTk


class ScreenDesignerWindow(tk.Toplevel):
    """Toplevel pencere: Tek kanvaslı, sürükle-bırak ekran tasarımcısı.

    Attributes:
        game_id: Aktif oyunun kimliği
        screen_service: DB CRUD için servis
        canvas: Tasarım alanı (800x600)
        items: Kanvas üzerindeki öğelerin dahili listesi
    """

    CANVAS_W = 800
    CANVAS_H = 600

    def __init__(self, parent: tk.Tk, game_id: int, screen_service, sprite_service, game_service,
                 screen_name: str = "opening", screen_type: str = "menu"):
        """Designer'ı başlatır.

        Args:
            parent: Üst Tk penceresi
            game_id: Tasarlanan oyunun ID'si
            screen_service: DB'ye kaydetmek ve okumak için ScreenService
            sprite_service: Sprite erişimi (gelecek genişletmeler için)
            game_service: Oyun ayarlarına erişim (gerekirse)
        """
        super().__init__(parent)
        # Başlık: ekran adına göre
        self.title(f"Ekran Tasarımcısı - {screen_name}")
        self.geometry("1100x760")
        self.transient(parent)
        self.grab_set()

        self.game_id = game_id
        self.screen_service = screen_service
        self.sprite_service = sprite_service
        self.game_service = game_service
        self.screen_name = screen_name
        self.screen_type = screen_type

        self._bg_img_ref: Optional[ImageTk.PhotoImage] = None
        self._canvas_bg_path: Optional[str] = None
        # Zoom (rendering scale). Logical tasarım 800x600, çizim zoom ile ölçeklenir.
        self.zoom: float = 1.0
        self.zoom_var = tk.StringVar(value="100%")

        self.items: List[Dict[str, Any]] = []  # [{'id':canvas_id, 'type':'label'|'button'|'image', 'props':{...}}]
        self.selected_item: Optional[Dict[str, Any]] = None
        self._drag_start = (0, 0)
        self._name_counters = {"label": 0, "button": 0}

        self._build_ui()
        self._scan_assets()
        # Sprite/audio dropdown'larını ilk yüklemede de doldur
        try:
            self._load_sprite_regions()
        except Exception:
            pass
        self._load_existing()

    # UI setup
    def _build_ui(self) -> None:
        """Ana arayüzü oluşturur: sol palet, orta kanvas, sağ özellik paneli."""
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # Center canvas (ilk önce oluştur ki komut tıklamaları sırasında hazır olsun)
        center = ttk.Frame(self, padding=8)
        center.grid(row=0, column=1, sticky="nsew")
        center.rowconfigure(0, weight=1)
        center.columnconfigure(0, weight=1)
        self.canvas = tk.Canvas(center, width=self.CANVAS_W, height=self.CANVAS_H, background="#1e1e1e")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)

        # Left palette
        left = ttk.Frame(self, padding=8)
        left.grid(row=0, column=0, sticky="ns")

        ttk.Label(left, text="Palet", style="Subheader.TLabel").pack(anchor="w")
        ttk.Button(left, text="Label Ekle", command=self._add_label).pack(fill="x", pady=4)
        ttk.Button(left, text="Buton Ekle", command=self._add_button).pack(fill="x", pady=4)
        ttk.Button(left, text="Sprite Ekle", command=self._add_image_sprite).pack(fill="x", pady=4)
        ttk.Separator(left).pack(fill="x", pady=6)
        ttk.Label(left, text="Nesneler", style="Subheader.TLabel").pack(anchor="w")
        tree_frame = ttk.Frame(left)
        tree_frame.pack(fill="both", expand=True)
        self.obj_tree = ttk.Treeview(tree_frame, columns=("name",), show="headings", height=8, selectmode="browse")
        self.obj_tree.heading("name", text="Ad")
        self.obj_tree.column("name", stretch=True)
        self.obj_tree.pack(fill="both", expand=True)
        self.obj_tree.bind("<<TreeviewSelect>>", lambda e: self._on_tree_select())
        zrow = ttk.Frame(left)
        zrow.pack(fill="x", pady=4)
        ttk.Button(zrow, text="Öne Getir", command=self._bring_forward).pack(side=tk.LEFT, expand=True, fill="x", padx=(0,2))
        ttk.Button(zrow, text="Arkaya Gönder", command=self._send_backward).pack(side=tk.LEFT, expand=True, fill="x", padx=(2,0))
        row_actions = ttk.Frame(left)
        row_actions.pack(fill="x", pady=(2,6))
        ttk.Button(row_actions, text="Yeniden Adlandır", command=self._rename_selected).pack(side=tk.LEFT, expand=True, fill="x", padx=(0,2))
        ttk.Button(row_actions, text="Sil", command=self._delete_selected).pack(side=tk.LEFT, expand=True, fill="x", padx=(2,0))
        ttk.Label(left, text="Arkaplan (assets)").pack(anchor="w")
        self.bg_path_var = tk.StringVar()
        self.bg_combo = ttk.Combobox(left, textvariable=self.bg_path_var, state="readonly")
        self.bg_combo.pack(fill="x", pady=2)
        self.bg_combo.bind("<<ComboboxSelected>>", lambda e: self._on_bg_select())

        ttk.Label(left, text="Müzik (assets)").pack(anchor="w", pady=(8,0))
        self.music_path_var = tk.StringVar()
        self.music_combo = ttk.Combobox(left, textvariable=self.music_path_var, state="readonly")
        self.music_combo.pack(fill="x", pady=2)
        self.music_combo.bind("<<ComboboxSelected>>", lambda e: None)

        ttk.Label(left, text="Yakınlaştırma").pack(anchor="w", pady=(8,0))
        zoom_box = ttk.Combobox(left, textvariable=self.zoom_var, state="readonly",
                                 values=["50%", "75%", "100%", "125%", "150%"])
        zoom_box.pack(fill="x")
        zoom_box.bind("<<ComboboxSelected>>", lambda e: self._on_zoom_change())

        ttk.Separator(left).pack(fill="x", pady=6)
        # Save button (style toggles when dirty)
        self.save_btn = ttk.Button(left, text="Kaydet", command=self._save, style="TButton")
        self.save_btn.pack(fill="x", pady=2)
        ttk.Button(left, text="Kapat", command=self.destroy).pack(fill="x", pady=2)

        # Right property panel
        right = ttk.Frame(self, padding=8)
        right.grid(row=0, column=2, sticky="ns")
        ttk.Label(right, text="Özellikler", style="Subheader.TLabel").pack(anchor="w")

        # Common position
        pos_frame = ttk.LabelFrame(right, text="Konum")
        pos_frame.pack(fill="x", pady=6)
        self.pos_x_var = tk.StringVar()
        self.pos_y_var = tk.StringVar()
        row1 = ttk.Frame(pos_frame); row1.pack(fill="x", pady=2)
        ttk.Label(row1, text="X:").pack(side=tk.LEFT); ttk.Entry(row1, textvariable=self.pos_x_var, width=6).pack(side=tk.LEFT)
        ttk.Label(row1, text="Y:").pack(side=tk.LEFT, padx=(8,0)); ttk.Entry(row1, textvariable=self.pos_y_var, width=6).pack(side=tk.LEFT)
        ttk.Button(pos_frame, text="Uygula", command=self._apply_position).pack(anchor="e", pady=(4,0))

        # Label props
        self.label_frame = ttk.LabelFrame(right, text="Label")
        self.label_text = tk.Text(self.label_frame, height=3, width=28, wrap="word")
        self.label_color_var = tk.StringVar(value="#FFFFFF")
        self.label_size_var = tk.StringVar(value="20")
        ttk.Label(self.label_frame, text="Metin:").pack(anchor="w")
        self.label_text.pack(fill="x")
        row = ttk.Frame(self.label_frame); row.pack(fill="x", pady=2)
        ttk.Label(row, text="Renk:").pack(side=tk.LEFT)
        ttk.Entry(row, textvariable=self.label_color_var, width=10).pack(side=tk.LEFT)
        ttk.Button(row, text="Seç", command=self._pick_label_color).pack(side=tk.LEFT, padx=4)
        row2 = ttk.Frame(self.label_frame); row2.pack(fill="x", pady=2)
        ttk.Label(row2, text="Punto:").pack(side=tk.LEFT)
        ttk.Entry(row2, textvariable=self.label_size_var, width=6).pack(side=tk.LEFT)
        # Apply instantly: bind changes
        self.label_text.bind("<KeyRelease>", lambda e: (self._apply_label_props(), self._set_dirty(True)))
        self.label_color_var.trace_add('write', lambda *args: (self._apply_label_props(), self._set_dirty(True)))
        self.label_size_var.trace_add('write', lambda *args: (self._apply_label_props(), self._set_dirty(True)))

        # Button props
        self.button_frame = ttk.LabelFrame(right, text="Buton")
        self.button_text_var = tk.StringVar(value="Buton")
        self.button_action_var = tk.StringVar(value="start_game")
        ttk.Label(self.button_frame, text="Yazı:").pack(anchor="w")
        ttk.Entry(self.button_frame, textvariable=self.button_text_var).pack(fill="x")
        ttk.Label(self.button_frame, text="Aksiyon:").pack(anchor="w", pady=(6,0))
        ttk.Combobox(self.button_frame, textvariable=self.button_action_var, state="readonly", values=["start_game", "back"]).pack(fill="x")
        # Button bg color (used if no sprite image selected)
        self.button_color_var = tk.StringVar(value="#4CAF50")
        color_row = ttk.Frame(self.button_frame); color_row.pack(fill="x", pady=(6,0))
        ttk.Label(color_row, text="Arka plan rengi:").pack(side=tk.LEFT)
        ttk.Entry(color_row, textvariable=self.button_color_var, width=10).pack(side=tk.LEFT)
        ttk.Button(color_row, text="Seç", command=self._pick_button_color).pack(side=tk.LEFT, padx=4)
        # Sprite region selection (from assets/metadata.json)
        sprite_row = ttk.Frame(self.button_frame); sprite_row.pack(fill="x", pady=(6,0))
        ttk.Label(sprite_row, text="Sprite Bölgesi:").pack(side=tk.LEFT)
        self.button_sprite_var = tk.StringVar()
        self.button_sprite_combo = ttk.Combobox(sprite_row, textvariable=self.button_sprite_var, state="readonly")
        self.button_sprite_combo.pack(side=tk.LEFT, expand=True, fill="x", padx=(4,0))
        # Apply sprite immediately on selection
        self.button_sprite_combo.bind('<<ComboboxSelected>>', lambda e: (self._apply_button_sprite(), self._set_dirty(True)))
        # Apply instantly: bind changes
        # text
        self.button_text_var.trace_add('write', lambda *args: (self._apply_button_props(), self._set_dirty(True)))
        # action
        self.button_action_var.trace_add('write', lambda *args: (self._apply_button_props(), self._set_dirty(True)))
        # color entry
        self.button_color_var.trace_add('write', lambda *args: (self._apply_button_props(), self._set_dirty(True)))

        # Image sprite props (image-only)
        self.sprite_frame = ttk.LabelFrame(right, text="Sprite (Görsel)")
        spr_row = ttk.Frame(self.sprite_frame); spr_row.pack(fill="x", pady=(2,0))
        ttk.Label(spr_row, text="Sprite Bölgesi:").pack(side=tk.LEFT)
        self.image_sprite_var = tk.StringVar()
        self.image_sprite_combo = ttk.Combobox(spr_row, textvariable=self.image_sprite_var, state="readonly")
        self.image_sprite_combo.pack(side=tk.LEFT, expand=True, fill="x", padx=(4,0))
        self.image_sprite_combo.bind('<<ComboboxSelected>>', lambda e: (self._apply_image_sprite(), self._set_dirty(True)))

        # Level ekranına özel ayarlar
        self.level_frame = ttk.LabelFrame(right, text="Seviye Ayarları")
        # Sepet sprite bölgesi ve uzunluğu
        lf_row1 = ttk.Frame(self.level_frame); lf_row1.pack(fill="x", pady=(2,0))
        ttk.Label(lf_row1, text="Sepet Sprite:").pack(side=tk.LEFT)
        self.level_basket_sprite_var = tk.StringVar()
        self.level_basket_sprite_combo = ttk.Combobox(lf_row1, textvariable=self.level_basket_sprite_var, state="readonly")
        self.level_basket_sprite_combo.pack(side=tk.LEFT, expand=True, fill="x", padx=(4,0))
        lf_row1b = ttk.Frame(self.level_frame); lf_row1b.pack(fill="x", pady=(2,0))
        ttk.Label(lf_row1b, text="Sepet Uzunluğu:").pack(side=tk.LEFT)
        self.level_basket_len_var = tk.StringVar(value="128")
        ttk.Entry(lf_row1b, textvariable=self.level_basket_len_var, width=8).pack(side=tk.LEFT, padx=(4,0))
        # Ses efektleri
        lf_row2 = ttk.Frame(self.level_frame); lf_row2.pack(fill="x", pady=(6,0))
        ttk.Label(lf_row2, text="Doğru SFX:").pack(side=tk.LEFT)
        self.level_sfx_ok_var = tk.StringVar()
        self.level_sfx_ok_combo = ttk.Combobox(lf_row2, textvariable=self.level_sfx_ok_var, state="readonly")
        self.level_sfx_ok_combo.pack(side=tk.LEFT, expand=True, fill="x", padx=(4,0))
        lf_row3 = ttk.Frame(self.level_frame); lf_row3.pack(fill="x", pady=(2,0))
        ttk.Label(lf_row3, text="Yanlış SFX:").pack(side=tk.LEFT)
        self.level_sfx_bad_var = tk.StringVar()
        self.level_sfx_bad_combo = ttk.Combobox(lf_row3, textvariable=self.level_sfx_bad_var, state="readonly")
        self.level_sfx_bad_combo.pack(side=tk.LEFT, expand=True, fill="x", padx=(4,0))
        # HUD sprite
        lf_row4 = ttk.Frame(self.level_frame); lf_row4.pack(fill="x", pady=(6,0))
        ttk.Label(lf_row4, text="HUD Sprite:").pack(side=tk.LEFT)
        self.level_hud_sprite_var = tk.StringVar()
        self.level_hud_sprite_combo = ttk.Combobox(lf_row4, textvariable=self.level_hud_sprite_var, state="readonly")
        self.level_hud_sprite_combo.pack(side=tk.LEFT, expand=True, fill="x", padx=(4,0))
        # Yardım alanı
        lf_row5 = ttk.Frame(self.level_frame); lf_row5.pack(fill="x", pady=(6,0))
        ttk.Label(lf_row5, text="Yardım Alanı:").pack(side=tk.LEFT)
        self.level_help_area_var = tk.StringVar(value="none")
        self.level_help_area_combo = ttk.Combobox(lf_row5, textvariable=self.level_help_area_var, state="readonly",
                                                  values=["none","top-left","top-right","bottom-left","bottom-right"])
        self.level_help_area_combo.pack(side=tk.LEFT, expand=True, fill="x", padx=(4,0))

        # Initially hide detail frames
        self.label_frame.pack_forget()
        self.button_frame.pack_forget()
        self.sprite_frame.pack_forget()
        self.level_frame.pack_forget()
        # Level türündeyse paneli göster
        if (self.screen_type or "").lower() == "level":
            self.level_frame.pack(fill="x", pady=6)

    # Palette actions
    def _on_bg_select(self) -> None:
        """Arkaplan combobox'tan seçildiğinde önizleme uygular."""
        rel = self.bg_path_var.get().strip()
        abs_path = self._abs_assets_path(rel)
        if abs_path:
            self._apply_canvas_bg(abs_path)
            self._set_dirty(True)

    def _ensure_canvas(self) -> bool:
        """Canvas'ın var olduğunu garantiler."""
        return hasattr(self, "canvas") and self.canvas is not None

    def _apply_canvas_bg(self, path: str) -> None:
        """Kanvas arkaplanını uygular (görseli 800x600'e sığdırır)."""
        try:
            img = Image.open(path)
            w = max(1, int(self.CANVAS_W * self.zoom))
            h = max(1, int(self.CANVAS_H * self.zoom))
            img = img.resize((w, h), Image.LANCZOS)
            self._bg_img_ref = ImageTk.PhotoImage(img)
            self.canvas.delete("__bg__")
            self.canvas.create_image(0, 0, anchor="nw", image=self._bg_img_ref, tags=("__bg__",))
            self._canvas_bg_path = path
            # Always keep background at bottom
            try:
                self.canvas.tag_lower("__bg__")
            except Exception:
                pass
        except Exception as e:
            messagebox.showwarning("Arkaplan", f"Görsel yüklenemedi: {e}")

    # --- Zoom helpers ---
    def _to_canvas(self, v: float) -> float:
        return v * self.zoom

    def _to_logical(self, v: float) -> float:
        return v / self.zoom if self.zoom else v

    def _on_zoom_change(self) -> None:
        val = self.zoom_var.get().strip().replace('%', '')
        try:
            pct = int(val)
            if pct < 25 or pct > 300:
                raise ValueError
        except ValueError:
            self.zoom = 1.0
            self.zoom_var.set("100%")
        else:
            self.zoom = pct / 100.0
        # Canvas boyutunu güncelle
        self.canvas.config(width=int(self.CANVAS_W * self.zoom), height=int(self.CANVAS_H * self.zoom))
        # Arkaplanı yeniden uygula
        if self._canvas_bg_path:
            self._apply_canvas_bg(self._canvas_bg_path)
        # Öğeleri yeniden konumlandır/ölçekle
        self._reflow_items()

    # Asset scanning
    def _scan_assets(self) -> None:
        """assets/ ve assets/games/<game_id>/ altındaki görüntü/ses dosyalarını (RECURSIVE) listele.

        Ek olarak proje kökündeki `img/` klasörünü de fallback olarak tarar.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        assets_root = os.path.join(project_root, "assets")
        per_game_root = os.path.join(assets_root, "games", str(self.game_id))
        img_root_fallback = os.path.join(project_root, "img")

        img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}
        aud_exts = {".mp3", ".wav", ".ogg", ".mid", ".midi"}
        images: List[str] = []
        audios: List[str] = []

        def add_files_recursive(base_dir: str, exts: set[str]) -> List[str]:
            files: List[str] = []
            if os.path.isdir(base_dir):
                for root, _, fnames in os.walk(base_dir):
                    for fn in fnames:
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in exts:
                            abs_p = os.path.join(root, fn)
                            rel = os.path.relpath(abs_p, project_root).replace('\\','/')
                            files.append(rel)
            return sorted(files, key=lambda p: p.lower())

        # Görseller
        images.extend(add_files_recursive(assets_root, img_exts))
        images.extend(add_files_recursive(per_game_root, img_exts))
        images.extend(add_files_recursive(img_root_fallback, img_exts))

        # Sesler
        audios.extend(add_files_recursive(assets_root, aud_exts))
        audios.extend(add_files_recursive(per_game_root, aud_exts))

        # De-duplicate preserving order
        def dedup(lst: List[str]) -> List[str]:
            seen = set(); out = []
            for x in lst:
                if x not in seen:
                    seen.add(x); out.append(x)
            return out

        images = dedup(images)
        audios = dedup(audios)

        self._images = images
        self._audios = audios
        self.bg_combo['values'] = images
        self.music_combo['values'] = audios

        # Varsayılan seçimleri doldur
        if images and not self.bg_path_var.get():
            self.bg_path_var.set(images[0])
            abs_bg0 = self._abs_assets_path(images[0])
            if abs_bg0 and os.path.isfile(abs_bg0):
                self._apply_canvas_bg(abs_bg0)
        if audios and not self.music_path_var.get():
            self.music_path_var.set(audios[0])

    def _abs_assets_path(self, rel: str) -> Optional[str]:
        if not rel:
            return None
        if os.path.isabs(rel):
            return rel
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        return os.path.join(project_root, rel)

    def _add_label(self) -> None:
        """Kanvas üzerine bir Label ekler."""
        if not self._ensure_canvas():
            return
        x, y = 100, 100
        text = "Yeni Label"
        cx, cy = int(self._to_canvas(x)), int(self._to_canvas(y))
        cid = self.canvas.create_text(cx, cy, text=text, fill="#FFFFFF", anchor="nw", font=("Segoe UI", 20))
        name = self._gen_name("label")
        item = {"id": cid, "type": "label", "props": {"name": name, "text": text, "color": "#FFFFFF", "font_size": 20, "x": x, "y": y}}
        self.items.append(item)
        self._select_item(item)
        # Insert into tree and select
        try:
            self.obj_tree.insert("", tk.END, iid=str(cid), values=(f"{name} (label)",))
            self.obj_tree.selection_set(str(cid))
        except Exception:
            pass
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

    def _apply_image_sprite(self) -> None:
        """Seçili image-only sprite öğesine combobox'tan seçilen sprite bölgesini uygular ve çizer.

        - Combobox değeri "name — image_rel" formatındadır.
        - Bölgeyi bulup kırpılmış resmi oluşturur, kanvasa image olarak yerleştirir.
        - Öğenin genişlik/yüksekliğini bölge ölçülerine göre günceller.
        - item.props.sprite alanına meta veriyi yazar.
        """
        if not self.selected_item or self.selected_item["type"] != "image":
            return
        key = self.image_sprite_var.get().strip()
        if not key or " — " not in key:
            return
        name, image_rel = key.split(" — ", 1)
        entry = self._find_sprite_region(image_rel, name)
        if not entry:
            messagebox.showwarning("Sprite", "Seçilen sprite bölgesi bulunamadı.")
            return
        # yükle ve uygula
        pil_crop = self._load_crop_image(entry)
        if pil_crop is None:
            messagebox.showwarning("Sprite", "Görsel yüklenemedi.")
            return
        it = self.selected_item
        x = int(it["props"].get("x", 0)); y = int(it["props"].get("y", 0))
        w = int(entry.get("width", pil_crop.width)); h = int(entry.get("height", pil_crop.height))
        cx, cy = int(self._to_canvas(x)), int(self._to_canvas(y))
        cw, ch = int(self._to_canvas(w)), int(self._to_canvas(h))
        img_zoomed = pil_crop.resize((max(1,cw), max(1,ch)), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img_zoomed)
        # mevcut primitive'i (rect/image) kaldır ve yeni image ekle
        try:
            self.canvas.delete(it["id"])
        except Exception:
            pass
        img_id = self.canvas.create_image(cx, cy, anchor="nw", image=photo)
        # prop güncellemeleri ve referansları koru
        it["props"]["pil_crop"] = pil_crop
        it["props"]["img_ref"] = photo
        it["props"]["w"], it["props"]["h"] = w, h
        it["props"]["sprite"] = {"image": image_rel, "name": name, "x": int(entry.get("x",0)), "y": int(entry.get("y",0)), "width": w, "height": h}
        it["id"] = img_id
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass
        self._set_dirty(True)

    def _add_image_sprite(self) -> None:
        """Kanvas üzerine yalnızca görselden oluşan bir sprite ekler (buton değil)."""
        if not self._ensure_canvas():
            return
        x, y = 400, 200
        # Başlangıçta bir placeholder dikdörtgen kullan; sprite seçilince görsel ile değiştirilir
        w, h = 128, 128
        cx, cy, cw, ch = int(self._to_canvas(x)), int(self._to_canvas(y)), int(self._to_canvas(w)), int(self._to_canvas(h))
        rect = self.canvas.create_rectangle(cx, cy, cx+cw, cy+ch, outline="#888", dash=(3,2), fill="")
        name = self._gen_name("sprite")
        item = {"id": rect, "type": "image", "props": {"name": name, "x": x, "y": y, "w": w, "h": h}}
        self.items.append(item)
        self._select_item(item)
        try:
            self.obj_tree.insert("", tk.END, iid=str(rect), values=(f"{name} (sprite)",))
            self.obj_tree.selection_set(str(rect))
        except Exception:
            pass
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

    def _add_button(self) -> None:
        """Kanvas üzerine bir Buton (placeholder dikdörtgen + metin) ekler."""
        if not self._ensure_canvas():
            return
        x, y, w, h = 300, 300, 180, 48
        cx, cy, cw, ch = int(self._to_canvas(x)), int(self._to_canvas(y)), int(self._to_canvas(w)), int(self._to_canvas(h))
        rect = self.canvas.create_rectangle(cx, cy, cx+cw, cy+ch, fill="#4CAF50", outline="", tags=("button",))
        label = self.canvas.create_text(cx+cw/2, cy+ch/2, text="Başla", fill="#FFFFFF", font=("Segoe UI", 18), anchor="center", tags=("button",))
        name = self._gen_name("button")
        item = {"id": rect, "type": "button", "props": {"name": name, "text": "Başla", "action": "start_game", "w": w, "h": h, "x": x, "y": y, "label_id": label}}
        self.items.append(item)
        self._select_item(item)
        # Insert into tree and select
        try:
            self.obj_tree.insert("", tk.END, iid=str(rect), values=(f"{name} (button)",))
            self.obj_tree.selection_set(str(rect))
        except Exception:
            pass
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

    # Selection & dragging
    def _find_item_by_canvas_id(self, cid: int) -> Optional[Dict[str, Any]]:
        for it in self.items:
            if it["id"] == cid or it["props"].get("label_id") == cid:
                return it
        return None

    def _on_canvas_click(self, event) -> None:
        """Kanvas tıklamasında seçim ve sürükleme başlangıcı."""
        cid = self.canvas.find_closest(event.x, event.y)[0]
        it = self._find_item_by_canvas_id(cid)
        if it:
            self._select_item(it)
            self._drag_start = (event.x, event.y)
            # Sync selection to tree
            if self.obj_tree.exists(str(it["id"])):
                self.obj_tree.selection_set(str(it["id"]))
        else:
            self._select_item(None)

    def _on_drag(self, event) -> None:
        if not self.selected_item:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self._drag_start = (event.x, event.y)
        it = self.selected_item
        if it["type"] == "label":
            self.canvas.move(it["id"], dx, dy)
            cx, cy = self.canvas.coords(it["id"])  # canvas coords
            it["props"]["x"], it["props"]["y"] = float(self._to_logical(cx)), float(self._to_logical(cy))
        elif it["type"] == "button":
            # move rect and label together
            self.canvas.move(it["id"], dx, dy)
            self.canvas.move(it["props"]["label_id"], dx, dy)
            x1, y1, x2, y2 = self.canvas.coords(it["id"])  # canvas coords
            it["props"]["x"], it["props"]["y"] = float(self._to_logical(x1)), float(self._to_logical(y1))
        else:
            # image-only sprite
            self.canvas.move(it["id"], dx, dy)
            x1, y1, x2, y2 = self.canvas.coords(it["id"])  # for rectangle or image
            it["props"]["x"], it["props"]["y"] = float(self._to_logical(x1)), float(self._to_logical(y1))
        self._refresh_position_fields()

    def _on_drag_end(self, event) -> None:
        # Her sürükleme bitiminde kaydetme butonunu koyu yap
        self._set_dirty(True)

    def _select_item(self, item: Optional[Dict[str, Any]]) -> None:
        self.selected_item = item
        # toggle prop panels
        self.label_frame.pack_forget(); self.button_frame.pack_forget(); self.sprite_frame.pack_forget()
        if not item:
            return
        # set position fields
        self._refresh_position_fields()
        if item["type"] == "label":
            self.label_frame.pack(fill="x", pady=6)
            # load props
            self.label_text.delete("1.0", "end")
            self.label_text.insert("1.0", item["props"].get("text", ""))
            self.label_color_var.set(item["props"].get("color", "#FFFFFF"))
            self.label_size_var.set(str(item["props"].get("font_size", 20)))
        elif item["type"] == "button":
            self.button_frame.pack(fill="x", pady=6)
            self.button_text_var.set(item["props"].get("text", ""))
            self.button_action_var.set(item["props"].get("action", "start_game"))
            self.button_color_var.set(item["props"].get("bg_color", "#4CAF50"))
            # load sprite regions and set selection if present (DB-backed)
            self._load_sprite_regions()
            sp = item["props"].get("sprite") or {}
            if sp.get("name") and sp.get("image"):
                key = f"{sp.get('name')} — {sp.get('image')}"
                if key in (self.button_sprite_combo['values'] or ()):  
                    self.button_sprite_var.set(key)
        else:
            # image-only sprite props
            self.sprite_frame.pack(fill="x", pady=6)
            self._load_sprite_regions()
            sp = item["props"].get("sprite") or {}
            if sp.get("name") and sp.get("image"):
                key = f"{sp.get('name')} — {sp.get('image')}"
                if key in (self.image_sprite_combo['values'] or ()):  
                    self.image_sprite_var.set(key)
        # ensure bg stays behind
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

    def _refresh_position_fields(self) -> None:
        if not self.selected_item:
            self.pos_x_var.set(""); self.pos_y_var.set("")
            return
        it = self.selected_item
        if it["type"] == "label":
            x, y = it["props"].get("x", 0), it["props"].get("y", 0)
        else:
            x, y = it["props"].get("x", 0), it["props"].get("y", 0)
        self.pos_x_var.set(str(int(x)))
        self.pos_y_var.set(str(int(y)))

    def _apply_position(self) -> None:
        """Seçili öğeyi girilen pozisyona taşır."""
        if not self.selected_item:
            return
        try:
            x = int(self.pos_x_var.get()); y = int(self.pos_y_var.get())
        except ValueError:
            messagebox.showwarning("Konum", "Geçerli bir sayı girin.")
            return
        it = self.selected_item
        if it["type"] == "label":
            it["props"]["x"], it["props"]["y"] = x, y
            cx, cy = int(self._to_canvas(x)), int(self._to_canvas(y))
            self.canvas.coords(it["id"], cx, cy)
        elif it["type"] == "button":
            it["props"]["x"], it["props"]["y"] = x, y
            w = int(it["props"].get("w", 180))
            h = int(it["props"].get("h", 48))
            cx, cy, cw, ch = int(self._to_canvas(x)), int(self._to_canvas(y)), int(self._to_canvas(w)), int(self._to_canvas(h))
            if self.canvas.type(it["id"]) == 'image':
                self.canvas.coords(it["id"], cx, cy)
            else:
                self.canvas.coords(it["id"], cx, cy, cx+cw, cy+ch)
            # center text
            self.canvas.coords(it["props"]["label_id"], cx+cw/2, cy+ch/2)
        else:
            # image-only
            it["props"]["x"], it["props"]["y"] = x, y
            w = int(it["props"].get("w", 128))
            h = int(it["props"].get("h", 128))
            cx, cy = int(self._to_canvas(x)), int(self._to_canvas(y))
            if self.canvas.type(it["id"]) == 'image':
                self.canvas.coords(it["id"], cx, cy)
            else:
                self.canvas.coords(it["id"], cx, cy, cx+int(self._to_canvas(w)), cy+int(self._to_canvas(h)))
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass
        self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        """Kaydedilmemiş değişiklik var/yok işaretini ve buton stilini yönetir."""
        setattr(self, "_dirty", bool(dirty))
        try:
            self.save_btn.configure(style=("Accent.TButton" if dirty else "TButton"))
        except Exception:
            # Fallback: add asterisk to text
            base = "Kaydet*" if dirty else "Kaydet"
            self.save_btn.configure(text=base)

    def _pick_label_color(self) -> None:
        color = colorchooser.askcolor(title="Renk Seç", initialcolor=self.label_color_var.get())[1]
        if color:
            self.label_color_var.set(color)

    def _pick_button_color(self) -> None:
        color = colorchooser.askcolor(title="Buton Rengi", initialcolor=self.button_color_var.get())[1]
        if color:
            self.button_color_var.set(color)

    def _apply_label_props(self) -> None:
        """Label özelliklerini uygular (metin, renk, punto)."""
        if not self.selected_item or self.selected_item["type"] != "label":
            return
        text = self.label_text.get("1.0", "end-1c")
        color = self.label_color_var.get().strip() or "#FFFFFF"
        try:
            size = int(self.label_size_var.get())
        except ValueError:
            size = 20
        it = self.selected_item
        self.canvas.itemconfigure(it["id"], text=text, fill=color, font=("Segoe UI", size))
        it["props"].update({"text": text, "color": color, "font_size": size})

    def _apply_button_props(self) -> None:
        """Buton özelliklerini uygular (metin, aksiyon)."""
        if not self.selected_item or self.selected_item["type"] != "button":
            return
        txt = self.button_text_var.get().strip() or "Buton"
        act = self.button_action_var.get() or "start_game"
        it = self.selected_item
        # Update text label
        self.canvas.itemconfigure(it["props"]["label_id"], text=txt)
        # If no sprite selected, apply rect fill color
        bgc = self.button_color_var.get().strip() or "#4CAF50"
        # If currently using rect, recolor; if using image keep image
        if self.canvas.type(it["id"]) == 'rectangle':
            self.canvas.itemconfigure(it["id"], fill=bgc)
        it["props"].update({"text": txt, "action": act, "bg_color": bgc})

    def _apply_button_sprite(self) -> None:
        """Apply selected sprite region to the selected button and render it."""
        if not self.selected_item or self.selected_item["type"] != "button":
            return
        key = self.button_sprite_var.get().strip()
        if not key:
            return
        # Parse "name — image_rel"
        if " — " not in key:
            return
        name, image_rel = key.split(" — ", 1)
        entry = self._find_sprite_region(image_rel, name)
        if not entry:
            messagebox.showwarning("Sprite", "Seçilen sprite bölgesi bulunamadı.")
            return
        # Load and crop
        pil_crop = self._load_crop_image(entry)
        if pil_crop is None:
            messagebox.showwarning("Sprite", "Görsel yüklenemedi, dikdörtgen arkaplan kullanılacak.")
            return
        it = self.selected_item
        x = int(it["props"].get("x", 0)); y = int(it["props"].get("y", 0))
        w = int(entry.get("width", pil_crop.width)); h = int(entry.get("height", pil_crop.height))
        cx, cy = int(self._to_canvas(x)), int(self._to_canvas(y))
        cw, ch = int(self._to_canvas(w)), int(self._to_canvas(h))
        # Create zoomed PhotoImage from crop
        img_zoomed = pil_crop.resize((max(1,cw), max(1,ch)), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img_zoomed)
        # Replace background primitive with image
        try:
            self.canvas.delete(it["id"])  # remove rect/image
        except Exception:
            pass
        img_id = self.canvas.create_image(cx, cy, anchor="nw", image=photo)
        # Keep references for GC
        it["props"]["pil_crop"] = pil_crop
        it["props"]["img_ref"] = photo
        it["props"]["w"], it["props"]["h"] = w, h
        it["id"] = img_id
        # Recenter text and ensure it's above image
        self.canvas.coords(it["props"]["label_id"], cx+cw/2, cy+ch/2)
        try:
            self.canvas.tag_raise(it["props"]["label_id"])
        except Exception:
            pass
        # Save sprite meta
        it["props"]["sprite"] = {"image": image_rel, "name": name, "x": int(entry.get("x",0)), "y": int(entry.get("y",0)), "width": w, "height": h}
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

    def _load_sprite_regions(self) -> None:
        """Load sprite regions from the GLOBAL pool (game_id=0) into combobox.

        Sprite bölgeleri artık oyundan bağımsızdır; bu yüzden 0 id'li global
        havuzdan yüklenir ve her oyunda kullanılabilir.
        """
        vals = []
        try:
            rows = self.sprite_service.list_sprite_regions()
            for e in rows:
                img = e.get("image_path"); name = e.get("name")
                if img and name:
                    vals.append(f"{name} — {img}")
        except Exception:
            pass
        self.button_sprite_combo['values'] = sorted(vals, key=lambda s: s.lower())
        self.image_sprite_combo['values'] = sorted(vals, key=lambda s: s.lower())
        # Level panelindeki sprite seçimleri de aynı değerleri kullanır
        try:
            self.level_basket_sprite_combo['values'] = sorted(vals, key=lambda s: s.lower())
            self.level_hud_sprite_combo['values'] = sorted(vals, key=lambda s: s.lower())
            self.level_sfx_ok_combo['values'] = self._audios
            self.level_sfx_bad_combo['values'] = self._audios
        except Exception:
            pass

    def _find_sprite_region(self, image_rel: str, name: str) -> Optional[Dict[str,Any]]:
        """Find a sprite region by image path and name from the GLOBAL pool (game_id=0)."""
        try:
            rows = self.sprite_service.list_sprite_regions()
            for e in rows:
                if e.get("image_path") == image_rel and e.get("name") == name:
                    # Map keys to expected names
                    return {
                        "image": e.get("image_path"),
                        "x": int(e.get("x", 0)),
                        "y": int(e.get("y", 0)),
                        "width": int(e.get("width", 0)),
                        "height": int(e.get("height", 0))
                    }
        except Exception:
            return None
        return None

    def _current_game_id(self) -> int:
        """Return current game id from self or root, fallback to 1."""
        try:
            if getattr(self, 'game_id', None):
                return int(self.game_id)
        except Exception:
            pass
        try:
            root = self.winfo_toplevel()
            gid = getattr(root, 'current_game_id', None)
            if gid:
                return int(gid)
        except Exception:
            pass
        return 1

    # metadata helpers removed; DB is the source of truth for sprite regions

    def _load_crop_image(self, entry: Dict[str,Any]) -> Optional[Image.Image]:
        """Load and crop the image per entry; return PIL Image or None."""
        rel = entry.get("image")
        if not rel:
            return None
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        abs_path = os.path.join(project_root, rel)
        if not os.path.isfile(abs_path):
            return None
        try:
            base = Image.open(abs_path)
            x = int(entry.get("x",0)); y = int(entry.get("y",0)); w = int(entry.get("width",0)); h = int(entry.get("height",0))
            w = max(1,w); h = max(1,h)
            return base.crop((x, y, x+w, y+h))
        except Exception:
            return None

    # Save & Load
    def _collect_json(self) -> Dict[str, Any]:
        """Kanvas üzerindeki öğelerden JSON oluşturur."""
        widgets: List[Dict[str, Any]] = []
        for it in self.items:
            if it["type"] == "label":
                x = float(it["props"].get("x", 0))
                y = float(it["props"].get("y", 0))
                widgets.append({
                    "id": f"label_{it['id']}",
                    "type": "label",
                    "text": it["props"].get("text", ""),
                    "font": {"name": "Segoe UI", "size": it["props"].get("font_size", 20)},
                    "color": it["props"].get("color", "#FFFFFF"),
                    "x": int(round(x)), "y": int(round(y)),
                    "anchor": "nw",
                    "name": it["props"].get("name")
                })
            else:
                x = float(it["props"].get("x", 0))
                y = float(it["props"].get("y", 0))
                if it["type"] == "button":
                    w = float(it["props"].get("w", 180))
                    h = float(it["props"].get("h", 48))
                    btn = {
                        "id": f"button_{it['id']}",
                        "type": "button",
                        "x": int(round(x)), "y": int(round(y)),
                        "anchor": "nw",
                        "sprite": (it["props"].get("sprite") or {"source": "placeholder", "frame": {"width": int(round(w)), "height": int(round(h))}}),
                        "text_overlay": {
                            "text": it["props"].get("text", "Buton"),
                            "font": {"name": "Segoe UI", "size": 18},
                            "color": "#FFFFFF"
                        },
                        "action": it["props"].get("action", "start_game"),
                        "bg_color": it["props"].get("bg_color", "#4CAF50"),
                        "name": it["props"].get("name")
                    }
                    widgets.append(btn)
                else:
                    w = float(it["props"].get("w", 128))
                    h = float(it["props"].get("h", 128))
                    imgw = {
                        "id": f"image_{it['id']}",
                        "type": "image",
                        "x": int(round(x)), "y": int(round(y)),
                        "anchor": "nw",
                        "sprite": it["props"].get("sprite"),
                        "frame": {"width": int(round(w)), "height": int(round(h))},
                        "name": it["props"].get("name")
                    }
                    widgets.append(imgw)
        # Ekran kimliği ve türü parametrelerden gelir
        data = {
            "id": self.screen_name,
            "type": self.screen_type,
            "resolution": {"width": self.CANVAS_W, "height": self.CANVAS_H},
            "background": {"image": self.bg_path_var.get().strip(), "fit": "cover"},
            "music": self.music_path_var.get().strip(),
            "widgets": widgets
        }
        # Level türü için ilave ayarlar
        if (self.screen_type or "").lower() == "level":
            try:
                data["level_settings"] = {
                    "basket_sprite": self.level_basket_sprite_var.get().strip(),
                    "basket_length": int(self.level_basket_len_var.get() or "0"),
                    "sfx_correct": self.level_sfx_ok_var.get().strip(),
                    "sfx_wrong": self.level_sfx_bad_var.get().strip(),
                    "hud_sprite": self.level_hud_sprite_var.get().strip(),
                    "help_area": self.level_help_area_var.get().strip() or "none",
                }
            except Exception:
                # Bozuk değerler varsa sessizce atla
                pass
        return data

    def _save(self) -> None:
        """JSON'u DB'ye kaydeder (screens.name='opening')."""
        try:
            data = self._collect_json()
            payload = json.dumps(data, ensure_ascii=False, indent=2)
            self.screen_service.upsert_screen(self.game_id, self.screen_name, self.screen_type, payload)
            messagebox.showinfo("Kayıt", "Açılış ekranı kaydedildi.")
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydedilemedi: {e}")

    def _load_existing(self) -> None:
        """Varsa DB'den 'opening' ekranını okur ve kanvasa uygular."""
        try:
            sc = self.screen_service.get_screen(self.game_id, self.screen_name)
            if not sc:
                return
            data = json.loads(sc.data_json)
            # background
            bg = (data.get("background") or {}).get("image")
            if bg:
                self.bg_path_var.set(bg)
                abs_bg = self._abs_assets_path(bg)
                if abs_bg and os.path.isfile(abs_bg):
                    self._apply_canvas_bg(abs_bg)
            # music
            mus = data.get("music") or ""
            self.music_path_var.set(mus)
            # ensure combos show items if pre-saved values exist
            if bg and bg not in (self.bg_combo['values'] or ()): 
                self.bg_combo['values'] = list(self.bg_combo['values']) + [bg]
            if mus and mus not in (self.music_combo['values'] or ()): 
                self.music_combo['values'] = list(self.music_combo['values']) + [mus]
            # Level ayarları
            try:
                if (self.screen_type or "").lower() == "level":
                    lv = data.get("level_settings") or {}
                    if lv:
                        if lv.get("basket_sprite") and lv.get("basket_sprite") in (self.level_basket_sprite_combo['values'] or ()): 
                            self.level_basket_sprite_var.set(lv.get("basket_sprite"))
                        if "basket_length" in lv:
                            self.level_basket_len_var.set(str(lv.get("basket_length") or ""))
                        if lv.get("sfx_correct") and lv.get("sfx_correct") in (self._audios if hasattr(self, "_audios") else []):
                            self.level_sfx_ok_var.set(lv.get("sfx_correct"))
                        if lv.get("sfx_wrong") and lv.get("sfx_wrong") in (self._audios if hasattr(self, "_audios") else []):
                            self.level_sfx_bad_var.set(lv.get("sfx_wrong"))
                        if lv.get("hud_sprite") and lv.get("hud_sprite") in (self.level_hud_sprite_combo['values'] or ()): 
                            self.level_hud_sprite_var.set(lv.get("hud_sprite"))
                        if lv.get("help_area"):
                            self.level_help_area_var.set(str(lv.get("help_area")))
            except Exception:
                pass
            # widgets
            for w in data.get("widgets", []):
                if w.get("type") == "label":
                    lx, ly = float(w.get("x", 0)), float(w.get("y", 0))
                    cx, cy = int(self._to_canvas(lx)), int(self._to_canvas(ly))
                    text = w.get("text", "")
                    color = w.get("color", "#FFFFFF")
                    size = int(((w.get("font") or {}).get("size") or 20))
                    cid = self.canvas.create_text(cx, cy, text=text, fill=color, anchor=w.get("anchor", "nw"), font=("Segoe UI", size))
                    name = (w.get("name") or (text.strip() if text.strip() else None)) or self._gen_name("label")
                    self.items.append({"id": cid, "type": "label", "props": {"name": name, "text": text, "color": color, "font_size": size, "x": lx, "y": ly}})
                elif w.get("type") == "button":
                    bx, by = float(w.get("x", 0)), float(w.get("y", 0))
                    txt = ((w.get("text_overlay") or {}).get("text") or "Buton")
                    name = (w.get("name") or (txt.strip() if txt.strip() else None)) or self._gen_name("button")
                    action = w.get("action", "start_game")
                    bgc = w.get("bg_color") or "#4CAF50"
                    sprite_info = w.get("sprite") or {}
                    # determine size
                    if sprite_info and sprite_info.get("width") and sprite_info.get("height"):
                        wth = float(sprite_info.get("width")); hgt = float(sprite_info.get("height"))
                    else:
                        frame = (sprite_info.get("frame") if isinstance(sprite_info, dict) else {}) or {}
                        wth = float(frame.get("width", 180)); hgt = float(frame.get("height", 48))
                    cx, cy = int(self._to_canvas(bx)), int(self._to_canvas(by))
                    cw, ch = int(self._to_canvas(wth)), int(self._to_canvas(hgt))
                    lbl = self.canvas.create_text(cx+cw/2, cy+ch/2, text=txt, fill="#FFFFFF", anchor="center", font=("Segoe UI", 18))
                    # try render sprite image
                    img_id = None; pil_crop = None; photo = None
                    if sprite_info.get("image") and sprite_info.get("name"):
                        entry = {"image": sprite_info.get("image"), "x": int(sprite_info.get("x",0)), "y": int(sprite_info.get("y",0)), "width": int(wth), "height": int(hgt)}
                        pil_crop = self._load_crop_image(entry)
                        if pil_crop is not None:
                            img_zoomed = pil_crop.resize((max(1,cw), max(1,ch)), Image.LANCZOS)
                            photo = ImageTk.PhotoImage(img_zoomed)
                            img_id = self.canvas.create_image(cx, cy, anchor="nw", image=photo)
                            try:
                                # ensure label stays on top of image
                                self.canvas.tag_raise(lbl)
                            except Exception:
                                pass
                    if img_id is None:
                        # fallback to colored rect
                        rect = self.canvas.create_rectangle(cx, cy, cx+cw, cy+ch, fill=bgc, outline="")
                        props = {"name": name, "text": txt, "action": action, "w": wth, "h": hgt, "x": bx, "y": by, "label_id": lbl, "bg_color": bgc}
                        self.items.append({"id": rect, "type": "button", "props": props})
                    else:
                        props = {"name": name, "text": txt, "action": action, "w": wth, "h": hgt, "x": bx, "y": by, "label_id": lbl, "bg_color": bgc, "sprite": sprite_info, "pil_crop": pil_crop, "img_ref": photo}
                        self.items.append({"id": img_id, "type": "button", "props": props})
                elif w.get("type") == "image":
                    ix, iy = float(w.get("x", 0)), float(w.get("y", 0))
                    frame = (w.get("frame") or {}) if isinstance(w.get("frame"), dict) else {}
                    iw = float(frame.get("width", 128)); ih = float(frame.get("height", 128))
                    cx, cy = int(self._to_canvas(ix)), int(self._to_canvas(iy))
                    cw, ch = int(self._to_canvas(iw)), int(self._to_canvas(ih))
                    sp = w.get("sprite") or {}
                    # Varsayılan olarak placeholder dikdörtgen çiz; sprite varsa görsel bas
                    img_id = None; pil_crop = None; photo = None
                    if sp.get("image") and sp.get("name"):
                        entry = {"image": sp.get("image"), "x": int(sp.get("x",0)), "y": int(sp.get("y",0)), "width": int(iw), "height": int(ih)}
                        pil_crop = self._load_crop_image(entry)
                        if pil_crop is not None:
                            img_zoomed = pil_crop.resize((max(1,cw), max(1,ch)), Image.LANCZOS)
                            photo = ImageTk.PhotoImage(img_zoomed)
                            img_id = self.canvas.create_image(cx, cy, anchor="nw", image=photo)
                    if img_id is None:
                        # Placeholder
                        rect = self.canvas.create_rectangle(cx, cy, cx+cw, cy+ch, outline="#888", dash=(3,2), fill="")
                        self.items.append({"id": rect, "type": "image", "props": {"name": w.get("name"), "x": ix, "y": iy, "w": iw, "h": ih}})
                    else:
                        self.items.append({"id": img_id, "type": "image", "props": {"name": w.get("name"), "x": ix, "y": iy, "w": iw, "h": ih, "sprite": sp, "pil_crop": pil_crop, "img_ref": photo}})
            # Fill object tree after load
            self._populate_tree()
            # keep bg at bottom
            try:
                self.canvas.tag_lower("__bg__")
            except Exception:
                pass
        except Exception as e:
            messagebox.showwarning("Yükleme", f"Ekran yüklenemedi: {e}")

    def _reflow_items(self) -> None:
        """Zoom değiştiğinde tüm öğeleri yeniden boyutlandır/konumlandır."""
        for it in self.items:
            if it["type"] == "label":
                x, y = it["props"].get("x", 0), it["props"].get("y", 0)
                cx, cy = int(self._to_canvas(x)), int(self._to_canvas(y))
                self.canvas.coords(it["id"], cx, cy)
            else:
                x, y = it["props"].get("x", 0), it["props"].get("y", 0)
                w = it["props"].get("w", 180)
                h = it["props"].get("h", 48)
                cx, cy, cw, ch = int(self._to_canvas(x)), int(self._to_canvas(y)), int(self._to_canvas(w)), int(self._to_canvas(h))
                if self.canvas.type(it["id"]) == 'image' and it["props"].get("pil_crop"):
                    # Resize image by zoom and update
                    pil_crop = it["props"].get("pil_crop")
                    img_zoomed = pil_crop.resize((max(1,cw), max(1,ch)), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img_zoomed)
                    it["props"]["img_ref"] = photo
                    self.canvas.itemconfigure(it["id"], image=photo)
                    self.canvas.coords(it["id"], cx, cy)
                else:
                    self.canvas.coords(it["id"], cx, cy, cx+cw, cy+ch)
                # Sadece butonlarda label merkezini güncelle
                if it["type"] == "button" and "label_id" in it["props"]:
                    self.canvas.coords(it["props"]["label_id"], cx+cw/2, cy+ch/2)
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

    def _on_drag(self, event) -> None:
        if not self.selected_item:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self._drag_start = (event.x, event.y)
        it = self.selected_item
        if it["type"] == "label":
            self.canvas.move(it["id"], dx, dy)
            cx, cy = self.canvas.coords(it["id"])  # canvas coords
            it["props"]["x"], it["props"]["y"] = float(self._to_logical(cx)), float(self._to_logical(cy))
        elif it["type"] == "button":
            # buton: rect/image ve label birlikte hareket eder
            self.canvas.move(it["id"], dx, dy)
            if "label_id" in it["props"]:
                self.canvas.move(it["props"]["label_id"], dx, dy)
            if self.canvas.type(it["id"]) == 'image':
                x1, y1 = self.canvas.coords(it["id"])  # (x,y)
                it["props"]["x"], it["props"]["y"] = float(self._to_logical(x1)), float(self._to_logical(y1))
            else:
                x1, y1, x2, y2 = self.canvas.coords(it["id"])  # (x1,y1,x2,y2)
                it["props"]["x"], it["props"]["y"] = float(self._to_logical(x1)), float(self._to_logical(y1))
        else:
            # image-only sprite: sadece görüntü hareket eder
            self.canvas.move(it["id"], dx, dy)
            x1, y1 = self.canvas.coords(it["id"])  # (x,y)
            it["props"]["x"], it["props"]["y"] = float(self._to_logical(x1)), float(self._to_logical(y1))
        self._refresh_position_fields()

    # ------- Tree/Z helpers -------
    def _populate_tree(self) -> None:
        """Populate the object tree with current items."""
        for iid in self.obj_tree.get_children():
            self.obj_tree.delete(iid)
        for it in self.items:
            name = it["props"].get("name") or (it["props"].get("text") or it["type"]).strip() or it["type"].title()
            label = f"{name} ({it['type']})"
            self.obj_tree.insert("", tk.END, iid=str(it["id"]), values=(label,))

    def _on_tree_select(self) -> None:
        """Select corresponding canvas item when a tree row is selected."""
        sel = self.obj_tree.selection()
        if not sel:
            return
        canvas_id = int(sel[0])
        it = self._find_item_by_canvas_id(canvas_id)
        if it:
            self._select_item(it)

    def _bring_forward(self) -> None:
        """Bring selected item to front (preserving background at bottom)."""
        if not self.selected_item:
            return
        it = self.selected_item
        try:
            self.canvas.tag_raise(it["id"])
            if it["type"] == "button":
                # ensure text above image/rect
                self.canvas.tag_raise(it["props"]["label_id"])
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass
        self._set_dirty(True)

    def _send_backward(self) -> None:
        """Send selected item one step backward (but keep above background)."""
        if not self.selected_item:
            return
        it = self.selected_item
        try:
            self.canvas.tag_lower(it["id"])
            if it["type"] == "button":
                self.canvas.tag_lower(it["props"]["label_id"])
            # ensure background is bottom-most
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass
        self._set_dirty(True)

    def _gen_name(self, kind: str) -> str:
        """Generate a default display name for an item."""
        self._name_counters[kind] = self._name_counters.get(kind, 0) + 1
        base = "Label" if kind == "label" else "Button"
        return f"{base} {self._name_counters[kind]}"

    def _rename_selected(self) -> None:
        """Seçili nesnenin görünen adını günceller ve TreeView'i senkronlar."""
        if not self.selected_item:
            return
        it = self.selected_item
        current = it["props"].get("name") or (it["props"].get("text") or it["type"]).strip()
        new_name = simpledialog.askstring("Yeniden Adlandır", "Yeni ad:", initialvalue=current, parent=self)
        if not new_name:
            return
        it["props"]["name"] = new_name.strip()
        label = f"{new_name.strip()} ({it['type']})"
        try:
            self.obj_tree.item(str(it["id"]), values=(label,))
        except Exception:
            pass

    def _delete_selected(self) -> None:
        """Seçili nesneyi kanvastan, iç listeden ve ağaçtan kaldırır."""
        if not self.selected_item:
            return
        it = self.selected_item
        # remove from canvas
        try:
            self.canvas.delete(it["id"])
            if it["type"] == "button" and it["props"].get("label_id"):
                self.canvas.delete(it["props"]["label_id"])
        except Exception:
            pass
        # remove from items list
        self.items = [x for x in self.items if x is not it]
        # remove from tree
        try:
            self.obj_tree.delete(str(it["id"]))
        except Exception:
            pass
        # clear selection and panels
        self.selected_item = None
        self.label_frame.pack_forget(); self.button_frame.pack_forget()
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

