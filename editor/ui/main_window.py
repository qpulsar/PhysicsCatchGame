"""Main window for the game editor."""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any
import os
import json
import sys
import subprocess
from PIL import Image
from ..utils import pil_to_tkphoto

from ..core.models import Game
from ..core.services import GameService, LevelService, ExpressionService, SpriteService, ScreenService, EffectService, TemplateService
from ..database.database import DatabaseManager
from .tabs.levels_tab import LevelsTab
from .tabs.settings_tab import SettingsTab
from .tabs.sprites_tab import SpritesTab
from .tabs.media_tab import MediaTab
from .tabs.screens_tab import ScreensTab
from .tabs.arduino_tab import ArduinoTab
from .game_dialog import GameDialog, TemplateSelectorDialog
from .publisher_dialog import SubmissionDialog
from .screen_designer import ScreenDesignerWindow
from .media_manager import MediaManagerWindow
from .effects_manager import EffectsManagerWindow
from .sprites_manager import SpritesManagerWindow
from ..utils import get_project_root, pil_to_tkphoto


class GamesListFrame(ttk.Frame):
    """Frame for listing games and providing management buttons."""
    def __init__(self, parent, game_service: GameService, on_game_select, on_add, on_edit, on_delete, **kwargs):
        super().__init__(parent)
        self.game_service = game_service
        self.on_game_select = on_game_select
        self.on_add = on_add
        self.on_edit = on_edit
        self.on_delete = on_delete
        self.on_template_toggle = kwargs.get('on_template_toggle')

        # --- Layout ---
        self.rowconfigure(1, weight=1)
        self.columnconfigure(0, weight=1)
        
        # --- Widgets ---
        ttk.Label(self, text="Oyunlar", style="Header.TLabel").grid(row=0, column=0, columnspan=2, pady=5, sticky="w")
        
        # Treeview for games list
        columns = ("name",)
        self.games_tree = ttk.Treeview(self, columns=columns, show="headings", selectmode="browse")
        self.games_tree.heading("name", text="Oyun Adı")
        self.games_tree.column("name", width=200)
        self.games_tree.grid(row=1, column=0, columnspan=2, sticky="nsew", pady=(0, 5))
        self.games_tree.bind("<<TreeviewSelect>>", self._on_select)
        
        # Buttons
        button_frame = ttk.Frame(self)
        button_frame.grid(row=2, column=0, columnspan=2, sticky="ew")
        
        ttk.Button(button_frame, text="Ekle", command=self.on_add).pack(side=tk.LEFT, padx=2)
        self.edit_button = ttk.Button(button_frame, text="Düzenle", command=self._on_edit, state="disabled")
        self.edit_button.pack(side=tk.LEFT, padx=2)
        self.delete_button = ttk.Button(button_frame, text="Sil", command=self._on_delete, state="disabled")
        self.delete_button.pack(side=tk.LEFT, padx=2)
        
        # Template visibility toggle
        self.show_templates_var = tk.BooleanVar(value=False)
        self.template_check = ttk.Checkbutton(self, text="Şablonları Göster", variable=self.show_templates_var, command=self._on_template_toggle)
        self.template_check.grid(row=3, column=0, columnspan=2, sticky="w", padx=5, pady=5)

    def _on_template_toggle(self):
        if self.on_template_toggle:
            self.on_template_toggle()
        self.refresh_games()
        
    def refresh_games(self, select_id: Optional[int] = None):
        """Refreshes the list of games in the treeview."""
        for item in self.games_tree.get_children():
            self.games_tree.delete(item)
        
        show_templates = getattr(self, 'show_templates_var', None)
        show_templates = show_templates.get() if show_templates else False
        
        self.games = self.game_service.get_games()
        for game in self.games:
            # Filter out templates if checkbox is not selected
            if game.is_template and not show_templates:
                continue
                
            display_name = f"[ŞABLON] {game.name}" if game.is_template else game.name
            self.games_tree.insert("", tk.END, iid=str(game.id), values=(display_name,))
        
        if select_id and self.games_tree.exists(str(select_id)):
            self.games_tree.selection_set(str(select_id))
            self.games_tree.focus(str(select_id))
        else:
            # Auto-select the first game if available
            children = self.games_tree.get_children()
            if children:
                first_iid = children[0]
                self.games_tree.selection_set(first_iid)
                self.games_tree.focus(first_iid)
                # Trigger selection handler to update dashboard tabs
                self._on_select()

    def get_selected_game_id(self) -> Optional[int]:
        """Returns the ID of the selected game, or None."""
        selection = self.games_tree.selection()
        return int(selection[0]) if selection else None

    def _on_select(self, event=None):
        """Handles selection in the treeview."""
        game_id = self.get_selected_game_id()
        if game_id:
            self.edit_button.config(state="normal")
            self.delete_button.config(state="normal")
            self.on_game_select(game_id)
        else:
            self.edit_button.config(state="disabled")
            self.delete_button.config(state="disabled")
            self.on_game_select(None)
    
    def _on_edit(self):
        game_id = self.get_selected_game_id()
        if game_id:
            self.on_edit(game_id)

    def _on_delete(self):
        game_id = self.get_selected_game_id()
        if game_id:
            self.on_delete(game_id)


class DashboardFrame(ttk.Frame):
    """The main dashboard frame, showing game details and management tabs."""
    def __init__(self, parent, game_service: GameService, level_service: LevelService, expression_service: ExpressionService, sprite_service: SpriteService, screen_service: ScreenService, effect_service: EffectService = None):
        super().__init__(parent)
        self.game_service = game_service
        self.level_service = level_service
        self.expression_service = expression_service
        self.sprite_service = sprite_service
        self.screen_service = screen_service
        self.effect_service = effect_service
        self.current_game: Optional[Game] = None
        # Proje kökü (assets için mutlak yol çözmekte kullanılır)
        self._project_root = get_project_root()
        
        # --- Layout ---
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # --- Widgets ---
        self.title_label = ttk.Label(self, text="Lütfen bir oyun seçin.", style="Header.TLabel")
        self.title_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
        self.template_save_btn = ttk.Button(self, text="Şablon Dosyasını Güncelle 💾", command=self._export_template, style="Accent.TButton")
        self.template_save_btn.grid(row=0, column=1, sticky="e", padx=5, pady=5)
        
        self.submit_game_btn = ttk.Button(self, text="Oyunu İncelemeye Gönder 🚀", command=self._submit_game, style="Accent.TButton")
        self.submit_game_btn.grid(row=0, column=2, sticky="e", padx=10, pady=5)
        
        # Notebook for game management
        self.notebook = ttk.Notebook(self)
        self.notebook.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
        
        self.summary_frame = self._create_summary_frame()
        self.notebook.add(self.summary_frame, text="Özet")
        
        # Tabs will be added when a game is selected
        self.tabs: Dict[str, ttk.Frame] = {}

    def set_game(self, game: Optional[Game]):
        """Sets the current game and updates the view."""
        self.current_game = game
        self.update_view()
        self._update_tabs()

    def update_view(self):
        """Updates the dashboard with the current game's data."""
        if self.current_game:
            display_name = f"Şablon: {self.current_game.name}" if self.current_game.is_template else self.current_game.name
            self.title_label.config(text=display_name)
            self.desc_label.config(text=self.current_game.description or "Açıklama yok.")
            
            if self.current_game.is_template:
                self.template_save_btn.grid(row=0, column=1, sticky="e", padx=5, pady=5)
                self.submit_game_btn.grid_forget()
            else:
                self.template_save_btn.grid_forget()
                self.submit_game_btn.grid(row=0, column=1, sticky="e", padx=10, pady=5)
            
            self.submit_game_btn.config(state="normal")
            
            settings = self.game_service.get_settings(self.current_game.id)
            settings_text = "\n".join([f"{k}: {v}" for k, v in settings.settings.items()])
            self.settings_text.config(state="normal")
            self.settings_text.delete("1.0", tk.END)
            self.settings_text.insert("1.0", settings_text or "Ayarlar bulunamadı.")
            self.settings_text.config(state="disabled")
            
            self.notebook.tab(0, state="normal")
            for i in range(1, self.notebook.index("end")):
                self.notebook.tab(i, state="normal")

            self._refresh_media_gallery()
        else:
            self.title_label.config(text="Lütfen bir oyun seçin veya yeni bir tane ekleyin.")
            self.desc_label.config(text="")
            self.settings_text.config(state="normal")
            self.settings_text.delete("1.0", tk.END)
            self.settings_text.config(state="disabled")
            self.submit_game_btn.config(state="disabled")
            #self.design_button.config(state="disabled")

            # Disable tabs if no game is selected
            for i in range(self.notebook.index("end")):
                self.notebook.tab(i, state="disabled")
                
    def _create_summary_frame(self) -> ttk.Frame:
        """Creates the summary tab content."""
        frame = ttk.Frame(self.notebook, padding=10)
        frame.columnconfigure(0, weight=1)
        
        ttk.Label(frame, text="Açıklama", style="Subheader.TLabel").grid(row=0, column=0, sticky="w")
        self.desc_label = ttk.Label(frame, text="", justify="left")
        self.desc_label.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        # Bind to resize to update wraplength dynamically
        frame.bind("<Configure>", lambda e: self.desc_label.configure(wraplength=e.width-20))

        ttk.Label(frame, text="Varsayılan Ayarlar", style="Subheader.TLabel").grid(row=2, column=0, sticky="w")
        self.settings_text = tk.Text(frame, height=8, width=40, wrap="word", state="disabled", relief="flat",
                                     background="#45494a", foreground="#a9b7c6", insertbackground="white",
                                     highlightthickness=1, highlightbackground="#555555", highlightcolor="#555555")
        self.settings_text.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        
        ttk.Label(frame, text="Medya Galerisi", style="Subheader.TLabel").grid(row=4, column=0, sticky="w")
        self.gallery_frame = ttk.Frame(frame)
        self.gallery_frame.grid(row=5, column=0, sticky="nsew")
        frame.rowconfigure(5, weight=1)
        
        self.gallery_canvas = tk.Canvas(self.gallery_frame, background="#2b2b2b", highlightthickness=0)
        self.gallery_scrollbar = ttk.Scrollbar(self.gallery_frame, orient="vertical", command=self.gallery_canvas.yview)
        self.gallery_inner = ttk.Frame(self.gallery_canvas, style="TFrame")
        self.gallery_inner.bind(
            "<Configure>",
            lambda e: self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
        )
        self.gallery_window_id = self.gallery_canvas.create_window((0,0), window=self.gallery_inner, anchor="nw")
        self.gallery_canvas.configure(yscrollcommand=self.gallery_scrollbar.set)
        
        # Bind canvas resize to inner frame width
        self.gallery_canvas.bind("<Configure>", self._on_gallery_canvas_configure)
        
        self.gallery_canvas.grid(row=0, column=0, sticky="nsew")
        self.gallery_scrollbar.grid(row=0, column=1, sticky="ns")
        self.gallery_frame.columnconfigure(0, weight=1)
        self.gallery_frame.rowconfigure(0, weight=1)
        self._gallery_images = []
        
        return frame

    def _on_gallery_canvas_configure(self, event):
        """Update the width of the inner frame to match the canvas width."""
        self.gallery_canvas.itemconfig(self.gallery_window_id, width=event.width)

    def _select_screens_tab(self):
        """"Ekranlar" sekmesine geçiş yapar (varsa)."""
        try:
            end = self.notebook.index("end")
            for i in range(end):
                if self.notebook.tab(i, option='text') == "Ekranlar":
                    self.notebook.select(i)
                    return
        except Exception:
            pass

    def _submit_game(self):
        """Opens the submission dialog for the current game."""
        if not self.current_game:
            return
        SubmissionDialog(self, self.current_game.id, self.game_service.db)
        
    def _update_tabs(self):
        """Creates or refreshes the management tabs."""
        for tab in self.tabs.values():
            tab.frame.destroy()
        self.tabs.clear()
        
        # Remove old tabs (except summary)
        while self.notebook.index("end") > 1:
            self.notebook.forget(1)
            
        if self.current_game:
            # Levels tab
            try:
                self.tabs['levels'] = LevelsTab(self.notebook, self.game_service, self.level_service, self.expression_service, self.sprite_service)
                self.notebook.add(self.tabs['levels'].frame, text="Seviyeler")
            except Exception as e:
                messagebox.showerror("Sekme Hatası", f"Seviyeler sekmesi yüklenemedi: {e}")

            # Settings tab
            try:
                self.tabs['settings'] = SettingsTab(self.notebook, self.game_service)
                self.notebook.add(self.tabs['settings'].frame, text="Ayarlar")
            except Exception as e:
                messagebox.showerror("Sekme Hatası", f"Ayarlar sekmesi yüklenemedi: {e}")

            # Screens tab
            try:
                self.tabs['screens'] = ScreensTab(self.notebook, self.game_service, self.level_service, self.screen_service, self.sprite_service, self.effect_service)
                self.notebook.add(self.tabs['screens'].frame, text="Ekranlar")
            except Exception as e:
                messagebox.showerror("Sekme Hatası", f"Ekranlar sekmesi yüklenemedi: {e}")

            # Arduino tab
            try:
                self.tabs['arduino'] = ArduinoTab(self.notebook, self.game_service)
                self.notebook.add(self.tabs['arduino'].frame, text="Arduino")
            except Exception as e:
                messagebox.showerror("Sekme Hatası", f"Arduino sekmesi yüklenemedi: {e}")
            
            self.refresh_tabs()

    def _export_template(self):
        """Exports the current template game back to its JSON file."""
        if not self.current_game or not self.current_game.is_template:
            return
            
        # Extract template ID from game name or description? 
        # Better: We need to know which file it came from.
        # Let's assume template_id is stored in a setting or just use the name slugified.
        settings = self.game_service.get_settings(self.current_game.id)
        template_id = settings.get("template_id")
        
        if not template_id:
            messagebox.showerror("Hata", "Şablon ID'si bulunamadı. Bu oyun şablon olarak dışa aktarılamaz.")
            return
            
        if messagebox.askyesno("Onay", f"'{template_id}.json' dosyasını mevcut verilerle güncellemek istiyor musunuz?"):
            from ..core.services import TemplateService
            ts = TemplateService()
            success = ts.export_game_to_template(self.current_game.id, template_id, self.game_service.db)
            if success:
                messagebox.showinfo("Başarılı", f"'{template_id}.json' başarıyla güncellendi.")
            else:
                messagebox.showerror("Hata", "Şablon güncellenirken bir hata oluştu.")

    def refresh_tabs(self):
        """Calls the refresh method on all available tabs."""
        if self.current_game:
            for tab in self.tabs.values():
                if hasattr(tab, 'refresh'):
                    tab.refresh()

    def _refresh_media_gallery(self):
        """Özet sekmesindeki medya galerisini kategorize ederek yeniler.
        
        Kategoriler:
        - Giriş (Intro): Opening screen ve start background
        - Zafer (Win): Victory screen ve win background
        - Yenilgi (Lose): Defeat screen ve lose background
        - Bilgi (Info): Diğer tanımlı ekranlar
        - Seviyeler (Levels): Seviye arkaplanları
        """
        # Temizle
        for child in self.gallery_inner.winfo_children():
            child.destroy()
        self._gallery_images.clear()
        
        if not self.current_game:
            return

        game_id = self.current_game.id
        settings = self.game_service.get_settings(game_id)
        
        # -- Kategorileri Hazırla --
        categories = {
            'intro': {'title': 'Giriş Ekranları (Intro)', 'items': []},
            'win': {'title': 'Zafer Ekranları (Win)', 'items': []},
            'lose': {'title': 'Yenilgi Ekranları (Lose)', 'items': []},
            'info': {'title': 'Bilgi Ekranları', 'items': []},
            'levels': {'title': 'Seviye Ekranları', 'items': []},
            'other': {'title': 'Diğer / Genel', 'items': []}
        }
        
        seen_paths = set()

        def add_item(cat_key, item_type, key, label, path, context=None):
            """Helper to add unique items to categories."""
            if not path or path in seen_paths:
                return
            categories[cat_key]['items'].append({
                'type': item_type,
                'key': key,
                'label': label,
                'path': path,
                'context': context
            })
            seen_paths.add(path)

        # 1. Settings'den gelen temel yollar
        # Intro
        add_item('intro', 'setting', 'start_background_path', 'Başlangıç Arkaplanı (Eski)', settings.get('start_background_path'))
        add_item('intro', 'setting', 'thumbnail_path', 'Küçük Resim', settings.get('thumbnail_path'))
        
        # Win/Lose
        add_item('win', 'setting', 'end_win_background_path', 'Kazanma Arkaplanı (Eski)', settings.get('end_win_background_path'))
        add_item('lose', 'setting', 'end_lose_background_path', 'Kaybetme Arkaplanı (Eski)', settings.get('end_lose_background_path'))
        
        # Genel Müzik -> Other
        add_item('other', 'setting', 'music_path', 'Genel Müzik (BGM)', settings.get('music_path'))

        # 2. Screen Service'den gelen ekranlar
        try:
            screens = self.screen_service.list_screens(game_id)
            import json as _json
            
            for sc in screens:
                if not getattr(sc, 'data_json', None):
                    continue
                
                try:
                    data = _json.loads(sc.data_json)
                except Exception:
                    continue

                s_name = getattr(sc, 'name', '') or str(data.get('id', ''))
                
                # Kategori Belirle
                target_cat = 'info' # Varsayılan
                if s_name == 'opening':
                    target_cat = 'intro'
                elif s_name == 'victory':
                    target_cat = 'win'
                elif s_name == 'defeat':
                    target_cat = 'lose'
                
                prefix = s_name.title()
                
                # Background
                bg_rel = ((data.get('background') or {}).get('image')) or ''
                if bg_rel:
                    add_item(target_cat, 'screen', f'{s_name}_bg', f'{prefix}: Arkaplan', bg_rel)
                
                # Music
                mus_rel = data.get('music') or ''
                if mus_rel:
                    add_item(target_cat, 'screen', f'{s_name}_music', f'{prefix}: Müzik', mus_rel)
                
                # Widget Sprites
                widgets = data.get('widgets') or []
                for idx, w in enumerate(widgets):
                    if not isinstance(w, dict): continue
                    sp = w.get('sprite') or {}
                    img_rel = sp.get('image')
                    if img_rel:
                        add_item(target_cat, 'screen', f'{s_name}_w{idx}', f'{prefix}: Widget', img_rel)

        except Exception as e:
            print(f"Error loading screens for gallery: {e}")

        # 3. Level Arkaplanları
        try:
            levels = self.level_service.get_levels(game_id)
            # Level numarasına göre sırala
            levels.sort(key=lambda x: x.level_number)
            
            for lvl in levels:
                # Level arkaplanları genellikle GameSettings içinde tutuluyor
                s_key = f"level_{lvl.id}_background_path"
                s_path = settings.get(s_key)
                
                if s_path:
                    label_text = f"Level {lvl.level_number}"
                    if lvl.level_name:
                        label_text += f": {lvl.level_name}"
                    else:
                        label_text += ": Arkaplan"
                        
                    add_item('levels', 'setting', s_key, label_text, s_path)

        except Exception as e:
            print(f"Error loading levels for gallery: {e}")

        # 4. Sprite Sheets (Kullanılanlar) -> 'other' veya ilgili kategoriye?
        # Genellikle sprite'lar geneldir ama burada 'other' altına koyalım.
        try:
            levels = self.level_service.get_levels(game_id)
            used_sprite_ids = set()
            for lvl in levels:
                try:
                    exprs = self.expression_service.get_expressions(lvl.id)
                except:
                    exprs = []
                for expr in exprs:
                    try:
                        sdef = self.sprite_service.get_sprite_definition_for_expr(expr.id)
                        if sdef and getattr(sdef, 'sprite_id', None):
                            used_sprite_ids.add(sdef.sprite_id)
                    except: pass
            
            for sid in used_sprite_ids:
                try:
                    s = self.sprite_service.get_sprite_sheet(sid)
                    if s:
                        add_item('other', 'sprite', f'sprite_{s.id}', f"Sprite: {s.name}", s.path)
                except: pass
        except Exception:
            pass

        # -- ARAYÜZ OLUŞTURMA --
        
        # Kategorileri belirli bir sırada dönelim
        display_order = ['intro', 'win', 'lose', 'info', 'levels', 'other']
        
        current_row = 0
        thumb_size = (120, 80) # Biraz daha kompakt

        for cat_key in display_order:
            cat_data = categories[cat_key]
            items = cat_data['items']
            
            if not items:
                continue

            # Kategori Başlığı (LabelFrame)
            group_frame = ttk.LabelFrame(self.gallery_inner, text=cat_data['title'], padding=10)
            group_frame.grid(row=current_row, column=0, sticky="ew", padx=5, pady=10)
            self.gallery_inner.columnconfigure(0, weight=1)
            
            # Grid yapısı için iç frame
            # items_frame = ttk.Frame(group_frame)
            # items_frame.pack(fill=tk.BOTH, expand=True)
            
            col = 0
            row = 0
            max_cols = 4 # Yan yana kaç tane
            
            for item in items:
                # Her bir item için bir frame
                item_frame = ttk.Frame(group_frame, borderwidth=1, relief="solid")
                item_frame.grid(row=row, column=col, padx=5, pady=5, sticky="n")
                
                path = item.get('path')
                abs_path = self._abs_path(path)
                
                # Görsel veya Dosya İkonu
                preview_lbl = ttk.Label(item_frame)
                preview_lbl.pack(pady=2, padx=2)
                
                img_ref = None
                if abs_path and os.path.isfile(abs_path) and self._is_image(abs_path):
                    try:
                        img = Image.open(abs_path)
                        img.thumbnail(thumb_size, Image.LANCZOS)
                        img_ref = pil_to_tkphoto(img)
                        preview_lbl.configure(image=img_ref)
                        self._gallery_images.append(img_ref) # Referansı sakla
                    except Exception:
                        preview_lbl.configure(text="[Hata]")
                else:
                    # Resim değilse veya bulunamadıysa
                    fname = os.path.basename(path) if path else "???"
                    if path and not (abs_path and os.path.isfile(abs_path)):
                         preview_lbl.configure(text=f"❌ {fname}\n(Dosya Yok)", foreground="red")
                    else:
                        preview_lbl.configure(text=f"🎵/📄 {fname}")

                # Etiket (Alt metin)
                lbl_text = item.get('label', '')
                if len(lbl_text) > 20:
                    lbl_text = lbl_text[:17] + "..."
                ttk.Label(item_frame, text=lbl_text, font=("Segoe UI", 8)).pack(pady=(0, 2))

                # Silme butonu (Opsiyonel - çok kalabalık olmasın diye belki küçük bir 'x' butonu?)
                # Mevcut yapıda 'Sil' butonu vardı, koruyalım ama küçük olsun.
                del_btn = ttk.Button(item_frame, text="Sil", width=4, command=lambda it=item: self._delete_media_item(it))
                del_btn.pack(pady=(0, 2))

                col += 1
                if col >= max_cols:
                    col = 0
                    row += 1
            
            current_row += 1

    def _is_image(self, path: str) -> bool:
        ext = os.path.splitext(path.lower())[1]
        return ext in ('.png', '.jpg', '.jpeg', '.bmp', '.gif')

    def _abs_path(self, maybe_rel: Optional[str]) -> Optional[str]:
        """Convert a stored path (possibly relative like 'assets/...') to an absolute path.

        Args:
            maybe_rel: Stored path string.
        Returns:
            Absolute path string or None.
        """
        if not maybe_rel:
            return None
        if os.path.isabs(maybe_rel):
            return maybe_rel
        return os.path.join(self._project_root, maybe_rel)

    def _delete_media_item(self, item: Dict[str, Any]):
        """Deletes a media item, warning the user if it's used in the game."""
        if not self.current_game:
            return

        game_id = self.current_game.id
        path = item.get('path')
        type_ = item.get('type')
        key = item.get('key')
        
        usage_locations = []
        
        # --- 1. Kullanım Kontrolü ---
        
        # A. Ayarlardaki Kullanım
        settings = self.game_service.get_settings(game_id)
        for s_key, s_val in settings.settings.items():
            if s_val == path:
                usage_locations.append(f"Ayarlar: {s_key}")
        
        # B. Ekranlardaki Kullanım (Arkaplan, Müzik, Widget)
        try:
            screens = self.screen_service.list_screens(game_id)
            for sc in screens:
                if not sc.data_json: continue
                data = json.loads(sc.data_json)
                
                # Arkaplan
                if (data.get('background') or {}).get('image') == path:
                    usage_locations.append(f"Ekran Arkaplanı: {sc.name}")
                
                # Müzik
                if data.get('music') == path:
                    usage_locations.append(f"Ekran Müziği: {sc.name}")
                
                # Widgetlar
                widgets = data.get('widgets') or []
                for idx, w in enumerate(widgets):
                    if not isinstance(w, dict): continue
                    if (w.get('sprite') or {}).get('image') == path:
                        usage_locations.append(f"Ekran Widget: {sc.name} (Nesne #{idx+1})")
        except Exception as e:
            print(f"Usage check error (screens): {e}")

        # C. Sprite Olarak Seviyelerdeki Kullanım
        sprite_id = None
        if type_ == 'sprite' or (path and 'assets/sprites' in path):
            # Sprite ID'sini bul
            if key and key.startswith('sprite_'):
                try: sprite_id = int(key.split('_')[1])
                except: pass
            
            if not sprite_id and path:
                all_sprites = self.sprite_service.get_sprite_sheets()
                for s in all_sprites:
                    if s.path == path:
                        sprite_id = s.id
                        break
            
            if sprite_id:
                try:
                    defs = self.sprite_service.get_all_definitions_for_sheet(sprite_id)
                    for d in defs:
                        expr = self.expression_service._get_expression(d.expression_id)
                        if expr:
                            lvl = self.level_service.get_level(expr.level_id)
                            usage_locations.append(f"Seviye {lvl.level_number if lvl else '?'}: {expr.expression}")
                except Exception as e:
                    print(f"Usage check error (sprites): {e}")

        # --- 2. Kullanıcı Onayı ---
        
        if usage_locations:
            msg = "Bu medya dosyası oyun içinde şu yerlerde kullanılmaktadır:\n\n"
            msg += "\n".join(usage_locations[:12])
            if len(usage_locations) > 12:
                msg += f"\n... ve {len(usage_locations)-12} yer daha."
            msg += "\n\nBu medyayı silmek ve kullanıldığı yerlerden (ayarlar, ekranlar vb.) KALDIRMAK istiyor musunuz?"
            if not messagebox.askyesno("Kullanım Uyarısı", msg):
                return
        else:
            if not messagebox.askyesno("Onay", "Bu medyayı silmek istediğinizden emin misiniz?"):
                return

        # --- 3. Temizlik ve Silme İşlemi ---
        
        try:
            # A. Ayarlardan Kaldır
            for s_key, s_val in settings.settings.items():
                if s_val == path:
                    self.game_service.update_setting(game_id, s_key, '')
            
            # B. Ekranlardan Kaldır
            screens = self.screen_service.list_screens(game_id)
            for sc in screens:
                if not sc.data_json: continue
                data = json.loads(sc.data_json)
                changed = False
                
                if (data.get('background') or {}).get('image') == path:
                    data['background']['image'] = ''
                    changed = True
                
                if data.get('music') == path:
                    data['music'] = ''
                    changed = True
                
                old_widgets = data.get('widgets') or []
                new_widgets = []
                for w in old_widgets:
                    if not isinstance(w, dict): continue
                    if (w.get('sprite') or {}).get('image') == path:
                        changed = True
                        continue # Widget'ı kaldır
                    new_widgets.append(w)
                
                if changed:
                    data['widgets'] = new_widgets
                    self.screen_service.upsert_screen(game_id, sc.name, sc.type, json.dumps(data))
            
            # C. Sprite Veritabanından Kaldır
            if sprite_id:
                # Önce tanımları (definitions) temizle
                defs = self.sprite_service.get_all_definitions_for_sheet(sprite_id)
                for d in defs:
                    self.sprite_service.remove_sprite_definition(d.expression_id)
                # Sheet kaydını sil
                self.sprite_service.delete_sprite_sheet(sprite_id)
            
            # D. Fiziksel Dosyayı Sil
            abs_p = self._abs_path(path)
            if abs_p and os.path.isfile(abs_p):
                try:
                    os.remove(abs_p)
                except Exception as e:
                    print(f"File deletion error: {e}")
            
            messagebox.showinfo("Başarılı", "Medya ve ilişkili tüm referanslar silindi.")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Silme işlemi sırasında hata oluştu: {e}")
        finally:
            self._refresh_media_gallery()


class MainWindow:
    """Main application window for the game editor."""

    def __init__(self, root: tk.Tk, db_manager: Optional[DatabaseManager] = None):
        """Initialize the main window."""
        self.root = root
        self.root.title("FizikselB Oyun Editörü")
        self.root.geometry("1200x800")
        
        # --- Theme ---
        self._apply_theme()

        # --- Services ---
        self.db_manager = db_manager or DatabaseManager()
        self.game_service = GameService(self.db_manager)
        self.level_service = LevelService(self.db_manager)
        self.expression_service = ExpressionService(self.db_manager)
        self.sprite_service = SpriteService(self.db_manager)
        self.screen_service = ScreenService(self.db_manager)
        self.effect_service = EffectService(self.db_manager)
        self.template_service = TemplateService()
        # Effect servisinin root üzerinden de erişilebilir olmasını sağla (ScreensTab/ScreenDesigner için)
        try:
            setattr(self.root, "effect_service", self.effect_service)
        except Exception:
            pass
        
        self.current_game_id: Optional[int] = None
        
        # --- Top Navbar ---
        # Navbar için özel stil (Theme içinde tanımlandı: Navbar.TFrame)
        navbar = ttk.Frame(root, style="Navbar.TFrame", padding=5)
        navbar.pack(side=tk.TOP, fill=tk.X)
        
        # Place global managers on the navbar as buttons
        ttk.Button(navbar, text="Sprite'ları Düzenle", command=self._open_sprites_manager, style="Navbar.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(navbar, text="Effectleri Düzenle", command=self._open_effects_manager, style="Navbar.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(navbar, text="Medya'yı Düzenle", command=self._open_media_manager, style="Navbar.TButton").pack(side=tk.LEFT, padx=5)
        ttk.Button(navbar, text="Fontları Düzenle", command=self._open_font_manager, style="Navbar.TButton").pack(side=tk.LEFT, padx=5)
        
        # Play button - Accent style
        ttk.Button(navbar, text="Oyun Oyna ▶", command=self._play_selected_game, style="Accent.TButton").pack(side=tk.RIGHT, padx=10)

        # --- Layout ---
        paned_window = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=0, pady=0)

        # Left: Games List
        self.games_list_frame = GamesListFrame(
            paned_window, 
            self.game_service,
            on_game_select=self._on_game_selected,
            on_add=self._add_game,
            on_edit=self._edit_game,
            on_delete=self._delete_game,
            on_template_toggle=self._on_template_toggle_callback
        )
        paned_window.add(self.games_list_frame, weight=1)
        
        # Secret shortcut for template editing - Using bind_all for global access
        self.root.bind_all("<Command-Option-t>", self._on_template_shortcut)
        self.root.bind_all("<Command-Option-T>", self._on_template_shortcut)
        self.root.bind_all("<Command-Alt-t>", self._on_template_shortcut)
        self.root.bind_all("<Command-Alt-T>", self._on_template_shortcut)
        self.root.bind_all("<Control-Alt-t>", self._on_template_shortcut)
        self.root.bind_all("<Control-Alt-T>", self._on_template_shortcut)

        # Right: Dashboard
        self.dashboard_frame = DashboardFrame(
            paned_window,
            self.game_service,
            self.level_service,
            self.expression_service,
            self.sprite_service,
            self.screen_service,
            self.effect_service
        )
        paned_window.add(self.dashboard_frame, weight=4)
        
        # --- Initial Load ---
        self.games_list_frame.refresh_games()
        self.dashboard_frame.update_view()

    def _apply_theme(self):
        """Uygulama genelinde modern koyu tema uygular."""
        style = ttk.Style(self.root)
        
        # Mevcut temayı 'clam' olarak ayarla (özelleştirme için en iyisi)
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass
            
        # Renk Paleti (Dark Modern - IntelliJ / VSCode benzeri)
        colors = {
            "bg": "#2b2b2b",             # Ana arka plan
            "fg": "#a9b7c6",             # Ana metin
            "panel_bg": "#313335",       # Panel/Sidebar arka planı
            "input_bg": "#45494a",       # Giriş kutuları
            "border": "#555555",         # Kenarlıklar
            "accent": "#365880",         # Vurgu (Buton vb.)
            "accent_hover": "#4b6eaf",   # Vurgu hover
            "select_bg": "#2f65ca",      # Seçim arka planı
            "success": "#4CAF50",        # Başarı rengi
            "warning": "#FFC107"         # Uyarı rengi
        }

        self.root.configure(background=colors["bg"])
        
        # --- Genel Widget Ayarları ---
        style.configure(".", 
                        background=colors["bg"], 
                        foreground=colors["fg"], 
                        borderwidth=0, 
                        font=('Segoe UI', 9))
                        
        style.configure("TFrame", background=colors["bg"])
        style.configure("TLabelframe", 
                        background=colors["bg"], 
                        foreground=colors["fg"], 
                        bordercolor=colors["border"])
                        
        style.configure("TLabelframe.Label", 
                        background=colors["bg"], 
                        foreground="#cc7832", # Turuncu tonu
                        font=('Segoe UI', 9, 'bold'))

        style.configure("TLabel", background=colors["bg"], foreground=colors["fg"])
        
        # --- Headers ---
        style.configure("Header.TLabel", font=('Segoe UI', 14, 'bold'), foreground="#cc7832")
        style.configure("Subheader.TLabel", font=('Segoe UI', 10, 'bold'), foreground="#a9b7c6")

        # --- Buttons ---
        style.configure("TButton", 
                        background=colors["panel_bg"], 
                        foreground="white", 
                        borderwidth=1, 
                        bordercolor=colors["border"], 
                        focuscolor=colors["border"],
                        padding=(8, 4))
                        
        style.map("TButton",
                  background=[("active", colors["border"]), ("pressed", colors["input_bg"])],
                  foreground=[("active", "white")])

        # Accent Button (Örn: Oyun Oyna, Kaydet)
        style.configure("Accent.TButton", 
                        background=colors["accent"], 
                        foreground="white", 
                        font=('Segoe UI', 9, 'bold'))
        style.map("Accent.TButton", 
                  background=[("active", colors["accent_hover"])])
        
        # Navbar Buttons
        style.configure("Navbar.TButton", 
                        background=colors["panel_bg"], 
                        font=('Segoe UI', 9))

        # --- Navbar Frame ---
        style.configure("Navbar.TFrame", background=colors["panel_bg"])

        # --- Treeview (Listeler) ---
        style.configure("Treeview",
                        background=colors["input_bg"],
                        foreground="white",
                        fieldbackground=colors["input_bg"],
                        borderwidth=0,
                        font=('Segoe UI', 9),
                        rowheight=24)
        
        style.map("Treeview", background=[("selected", colors["select_bg"])])
        
        style.configure("Treeview.Heading",
                        background=colors["panel_bg"],
                        foreground="white",
                        relief="flat",
                        font=('Segoe UI', 9, 'bold'),
                        padding=(5, 5))
                        
        # --- Notebook (Sekmeler) ---
        style.configure("TNotebook", background=colors["bg"], borderwidth=0)
        style.configure("TNotebook.Tab",
                        background=colors["panel_bg"],
                        foreground=colors["fg"],
                        padding=(12, 6),
                        borderwidth=0)
                        
        style.map("TNotebook.Tab",
                  background=[("selected", colors["bg"]), ("active", colors["input_bg"])],
                  foreground=[("selected", "white")],
                  expand=[("selected", [1, 1, 1, 0])]) # Seçili sekme biraz büyüsün

        # --- Entry & Combobox ---
        style.configure("TEntry", 
                        fieldbackground=colors["input_bg"], 
                        foreground="white", 
                        insertcolor="white", 
                        bordercolor=colors["border"],
                        padding=4)
                        
        style.configure("TCombobox", 
                        fieldbackground=colors["input_bg"], 
                        foreground="white", 
                        arrowcolor="white", 
                        bordercolor=colors["border"])
        
        style.map("TCombobox", 
                  fieldbackground=[("readonly", colors["input_bg"])],
                  selectbackground=[("readonly", colors["select_bg"])])

        # --- Scrollbar ---
        style.configure("Vertical.TScrollbar", 
                        background=colors["panel_bg"], 
                        troughcolor=colors["bg"], 
                        bordercolor=colors["bg"], 
                        arrowcolor="white")

    def _open_media_manager(self) -> None:
        """Open the standalone Media Manager window (global pool)."""
        try:
            MediaManagerWindow(self.root, self.game_service)
        except Exception as e:
            messagebox.showerror("Medya", f"Pencere açılamadı: {e}")

    def _open_sprites_manager(self) -> None:
        """Open the standalone Sprites Manager window (global pool)."""
        try:
            SpritesManagerWindow(self.root, self.sprite_service, self.expression_service, self.level_service, self.game_service)
        except Exception as e:
            messagebox.showerror("Sprite", f"Pencere açılamadı: {e}")

    def _open_effects_manager(self) -> None:
        """Open the standalone Effects Manager window (global pool).

        Note: Saving to DB is pending schema approval; the window allows selection and preview.
        """
        # Oyun seçme zorunluluğu kaldırıldı, efektler global yönetilir.
        try:
            EffectsManagerWindow(self.root, self.effect_service, game_id=0)
        except Exception as e:
            messagebox.showerror("Effect", f"Pencere açılamadı: {e}")

    def _open_font_manager(self) -> None:
        """Open the standalone Font Manager window."""
        try:
            from .font_manager import FontManagerWindow
            assets_fonts = os.path.join(get_project_root(), "assets/fonts")
            FontManagerWindow(self.root, assets_fonts, None)
        except Exception as e:
            messagebox.showerror("Font", f"Pencere açılamadı: {e}")

    def _play_selected_game(self) -> None:
        """Seçili oyunu pygame penceresinde başlatır.

        Not:
        - Oyun, `main.py` komutu ile yeni bir süreçte çalıştırılır.
        - Argüman olarak `--game-id` ve `--from-editor` gönderilir.
        - Editörde tasarlanan açılış ekranı (opening) oyun başlarken gösterilir.
        """
        if not self.current_game_id:
            messagebox.showwarning("Oyun Seçilmedi", "Lütfen listeden bir oyun seçin.")
            return
        try:
            # main.py yolunu güvenle oluştur
            project_root = get_project_root()
            main_path = os.path.join(project_root, "main.py")
            if not os.path.isfile(main_path):
                raise FileNotFoundError(f"main.py bulunamadı: {main_path}")
            # Mevcut Python yorumlayıcısıyla oyunu başlat
            subprocess.Popen([sys.executable, main_path, "--game-id", str(self.current_game_id), "--from-editor"], cwd=project_root)
        except Exception as e:
            messagebox.showerror("Oyun", f"Oyun başlatılamadı: {e}")

    def _on_game_selected(self, game_id: Optional[int]):
        """Handle game selection from the list."""
        self.current_game_id = game_id
        setattr(self.root, "current_game_id", game_id) # For tabs to access
        
        game = self.game_service.get_game(game_id) if game_id else None
        self.dashboard_frame.set_game(game)

    def _add_game(self):
        """Handle request to add a new game with template support."""
        templates = self.template_service.list_templates()
        dialog = GameDialog(self.root, title="Yeni Oyun Ekle", templates=templates)
        result = dialog.show()
        if not result:
            return
            
        name, description, template_id = result
        try:
            if not name:
                messagebox.showwarning("Geçersiz Ad", "Oyun adı boş olamaz.")
                return
            
            existing_games = self.game_service.get_games()
            if any(g.name.lower() == name.lower() for g in existing_games):
                messagebox.showwarning("Uyarı", f"'{name}' adında bir oyun zaten mevcut.")
                return

            if template_id == "blank":
                # Create blank game
                game = self.game_service.create_game(name, description)
                self._set_default_settings(game.id)
            else:
                # Create from template
                template_data = self.template_service.get_template(template_id)
                if template_data:
                    game = self.game_service.create_game_from_template(name, description, template_data)
                else:
                    game = self.game_service.create_game(name, description)
                    self._set_default_settings(game.id)

            messagebox.showinfo("Başarılı", f"'{name}' oyunu oluşturuldu.")
            self.games_list_frame.refresh_games(select_id=game.id)
                
        except Exception as e:
            messagebox.showerror("Hata", f"Oyun oluşturulurken hata oluştu: {e}")

    def _edit_game(self, game_id: int):
        """Handle request to edit a game."""
        game = self.game_service.get_game(game_id)
        if not game:
            messagebox.showerror("Hata", "Düzenlenecek oyun bulunamadı.")
            return

        dialog = GameDialog(self.root, title="Oyunu Düzenle", game_name=game.name, game_description=game.description)
        result = dialog.show()

        if not result:
            return
            
        name, description = result
        try:
            if not name:
                messagebox.showwarning("Geçersiz Ad", "Oyun adı boş olamaz.")
                return
                
            # Check for name conflict (excluding the current game)
            existing_games = self.game_service.get_games()
            if any(g.name.lower() == name.lower() and g.id != game_id for g in existing_games):
                messagebox.showwarning("Uyarı", f"'{name}' adında başka bir oyun zaten mevcut.")
                return
            
            self.game_service.update_game(game_id, name, description)
            messagebox.showinfo("Başarılı", f"'{name}' oyunu güncellendi.")
            self.games_list_frame.refresh_games(select_id=game_id)
            self._on_game_selected(game_id) # Refresh dashboard view
            
        except Exception as e:
            messagebox.showerror("Hata", f"Oyun güncellenirken hata oluştu: {e}")

    def _delete_game(self, game_id: int):
        """Handle request to delete a game."""
        game = self.game_service.get_game(game_id)
        if not game:
            messagebox.showerror("Hata", "Silinecek oyun bulunamadı.")
            return

        if not messagebox.askyesno("Onay", f"'{game.name}' oyununu ve tüm ilişkili verileri (seviyeler, ifadeler vb.) silmek istediğinizden emin misiniz? Bu işlem geri alınamaz."):
            return

        try:
            self.game_service.delete_game(game_id)
            messagebox.showinfo("Başarılı", f"'{game.name}' oyunu silindi.")
            self.games_list_frame.refresh_games()
            self._on_game_selected(None) # Clear selection
        except Exception as e:
            messagebox.showerror("Hata", f"Oyun silinirken hata oluştu: {e}")

    def _set_default_settings(self, game_id: int):
        """Sets default settings for a newly created game."""
        default_settings = {
            'total_levels': '10',
            'default_wrong_percentage': '20',
            'default_item_speed': '2.0',
            'default_max_items': '5'
        }
        for key, value in default_settings.items():
            self.game_service.update_setting(game_id, key, value)

    def _on_template_shortcut(self, event=None):
        """Toggle template visibility and sync if needed."""
        current = self.games_list_frame.show_templates_var.get()
        new_state = not current
        self.games_list_frame.show_templates_var.set(new_state)
        
        if new_state:
            self._sync_templates_to_db()
            
        self.games_list_frame.refresh_games()

    def _sync_templates_to_db(self):
        """Ensure all JSON templates have a corresponding entry in the DB for editing."""
        templates = self.template_service.list_templates()
        existing_games = self.game_service.get_games()
        
        for t in templates:
            if t["id"] == "blank":
                continue
                
            # Check if this template is already in the DB
            if not any(g.is_template and g.name == t["name"] for g in existing_games):
                try:
                    # Create a "Mock" game for this template in the DB
                    game = self.game_service.create_game_from_template(
                        name=t["name"],
                        description=t["description"],
                        template_data=t,
                        is_template=True
                    )
                    # Store template_id in settings for export
                    self.game_service.update_setting(game.id, "template_id", t["id"])
                except Exception as e:
                    print(f"Error syncing template {t['name']}: {e}")

    def _on_template_toggle_callback(self):
        """Callback from GamesListFrame when template checkbox is toggled."""
        if self.games_list_frame.show_templates_var.get():
            self._sync_templates_to_db()
