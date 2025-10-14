"""Main window for the game editor."""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any
import os
import json
import sys
import subprocess
from PIL import Image, ImageTk

from ..core.models import Game
from ..core.services import GameService, LevelService, ExpressionService, SpriteService, ScreenService
from ..database.database import DatabaseManager
from .tabs.levels_tab import LevelsTab
from .tabs.settings_tab import SettingsTab
from .tabs.sprites_tab import SpritesTab
from .tabs.media_tab import MediaTab
from .tabs.screens_tab import ScreensTab
from .game_dialog import GameDialog
from .screen_designer import ScreenDesignerWindow
from .media_manager import MediaManagerWindow
from .effects_manager import EffectsManagerWindow
from .sprites_manager import SpritesManagerWindow


class GamesListFrame(ttk.Frame):
    """Frame for listing games and providing management buttons."""
    def __init__(self, parent, game_service: GameService, on_game_select, on_add, on_edit, on_delete):
        super().__init__(parent)
        self.game_service = game_service
        self.on_game_select = on_game_select
        self.on_add = on_add
        self.on_edit = on_edit
        self.on_delete = on_delete

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
        
    def refresh_games(self, select_id: Optional[int] = None):
        """Refreshes the list of games in the treeview."""
        for item in self.games_tree.get_children():
            self.games_tree.delete(item)
        
        self.games = self.game_service.get_games()
        for game in self.games:
            self.games_tree.insert("", tk.END, iid=str(game.id), values=(game.name,))
        
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
    def __init__(self, parent, game_service: GameService, level_service: LevelService, expression_service: ExpressionService, sprite_service: SpriteService, screen_service: ScreenService):
        super().__init__(parent)
        self.game_service = game_service
        self.level_service = level_service
        self.expression_service = expression_service
        self.sprite_service = sprite_service
        self.screen_service = screen_service
        self.current_game: Optional[Game] = None
        # Proje kökü (assets için mutlak yol çözmekte kullanılır)
        self._project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        
        # --- Layout ---
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # --- Widgets ---
        self.title_label = ttk.Label(self, text="Lütfen bir oyun seçin.", style="Header.TLabel")
        self.title_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)
        # "Ekranlar" sekmesine hızlı erişim sağlayan buton
     #   self.design_button = ttk.Button(self, text="Ekranlar", command=self._select_screens_tab, state="disabled")
     #   self.design_button.grid(row=0, column=1, sticky="e", padx=10, pady=5)
        
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
            self.title_label.config(text=self.current_game.name)
            self.desc_label.config(text=self.current_game.description or "Açıklama yok.")
            #self.design_button.config(state="normal")
            
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
            #self.design_button.config(state="disabled")

            # Disable tabs if no game is selected
            for i in range(self.notebook.index("end")):
                self.notebook.tab(i, state="disabled")
                
    def _create_summary_frame(self) -> ttk.Frame:
        """Creates the summary tab content."""
        frame = ttk.Frame(self.notebook, padding=10)
        frame.columnconfigure(0, weight=1)
        
        ttk.Label(frame, text="Açıklama", style="Subheader.TLabel").grid(row=0, column=0, sticky="w")
        self.desc_label = ttk.Label(frame, text="", wraplength=400, justify="left")
        self.desc_label.grid(row=1, column=0, sticky="ew", pady=(0, 10))

        ttk.Label(frame, text="Varsayılan Ayarlar", style="Subheader.TLabel").grid(row=2, column=0, sticky="w")
        self.settings_text = tk.Text(frame, height=5, width=40, wrap="word", state="disabled", relief="flat")
        self.settings_text.grid(row=3, column=0, sticky="ew", pady=(0, 10))
        
        ttk.Label(frame, text="Medya Galerisi", style="Subheader.TLabel").grid(row=4, column=0, sticky="w")
        self.gallery_frame = ttk.Frame(frame)
        self.gallery_frame.grid(row=5, column=0, sticky="nsew")
        frame.rowconfigure(5, weight=1)
        self.gallery_canvas = tk.Canvas(self.gallery_frame, height=260)
        self.gallery_scrollbar = ttk.Scrollbar(self.gallery_frame, orient="vertical", command=self.gallery_canvas.yview)
        self.gallery_inner = ttk.Frame(self.gallery_canvas)
        self.gallery_inner.bind(
            "<Configure>",
            lambda e: self.gallery_canvas.configure(scrollregion=self.gallery_canvas.bbox("all"))
        )
        self.gallery_canvas.create_window((0,0), window=self.gallery_inner, anchor="nw")
        self.gallery_canvas.configure(yscrollcommand=self.gallery_scrollbar.set)
        self.gallery_canvas.grid(row=0, column=0, sticky="nsew")
        self.gallery_scrollbar.grid(row=0, column=1, sticky="ns")
        self.gallery_frame.columnconfigure(0, weight=1)
        self._gallery_images = []
        
        return frame

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

            # Sprite ve Medya yönetimi ayrı pencerelere taşındı (navbar düğmeleriyle açılır)

            # Settings tab
            try:
                self.tabs['settings'] = SettingsTab(self.notebook, self.game_service)
                self.notebook.add(self.tabs['settings'].frame, text="Ayarlar")
            except Exception as e:
                messagebox.showerror("Sekme Hatası", f"Ayarlar sekmesi yüklenemedi: {e}")

            # Screens tab
            try:
                self.tabs['screens'] = ScreensTab(self.notebook, self.game_service, self.level_service, self.screen_service, self.sprite_service)
                self.notebook.add(self.tabs['screens'].frame, text="Ekranlar")
            except Exception as e:
                messagebox.showerror("Sekme Hatası", f"Ekranlar sekmesi yüklenemedi: {e}")
            
            self.refresh_tabs()

    def refresh_tabs(self):
        """Calls the refresh method on all available tabs."""
        if self.current_game:
            for tab in self.tabs.values():
                if hasattr(tab, 'refresh'):
                    tab.refresh()

    def _refresh_media_gallery(self):
        """Özet sekmesindeki medya galerisini yalnızca bu oyunda kullanılan
        medya ile doldurur.

        - Oyun ayarlarında geçen yollar (başlangıç/bitış arkaplanları, seviye
          arkaplanları, müzik vb.) gösterilir.
        - Sprite görselleri, yalnızca bu oyundaki seviyelerdeki ifadeler için
          tanımlanmış sprite tanımlarının bağlı olduğu sprite sheet'lerden
          gösterilir.
        - Global metadata.json açıklamalı medyalar artık eklenmez (yalnızca
          bu oyuna ait kullanım hedeflenir).
        """
        for child in self.gallery_inner.winfo_children():
            child.destroy()
        self._gallery_images.clear()
        if not self.current_game:
            return
        game_id = self.current_game.id
        settings = self.game_service.get_settings(game_id)
        items = []
        seen_paths = set()
        label_map = {
            'start_background_path': 'Başlangıç Arkaplanı',
            'thumbnail_path': 'Küçük Resim',
            'music_path': 'Müzik (BGM)',
            'end_win_background_path': 'Kazanma Arkaplanı',
            'end_lose_background_path': 'Kaybetme Arkaplanı'
        }
        for key, label in label_map.items():
            path = settings.get(key)
            if path:
                if path not in seen_paths:
                    items.append({'type': 'setting', 'key': key, 'label': label, 'path': path})
                    seen_paths.add(path)
        for k, v in settings.settings.items():
            if k.startswith('level_') and k.endswith('_background_path') and v:
                if v not in seen_paths:
                    items.append({'type': 'setting', 'key': k, 'label': k.replace('_', ' ').title(), 'path': v})
                    seen_paths.add(v)
        # Açılış ekranı (opening) tasarımından referans verilen medya
        try:
            sc = self.screen_service.get_screen(game_id, "opening")
            if sc and getattr(sc, 'data_json', None):
                import json as _json
                data = _json.loads(sc.data_json)
                # background image
                bg_rel = ((data.get('background') or {}).get('image')) or ''
                if bg_rel:
                    if bg_rel not in seen_paths:
                        items.append({'type': 'screen', 'key': 'opening_bg', 'label': 'Açılış: Arkaplan', 'path': bg_rel})
                        seen_paths.add(bg_rel)
                # music
                mus_rel = data.get('music') or ''
                if mus_rel and mus_rel not in seen_paths:
                    items.append({'type': 'screen', 'key': 'opening_music', 'label': 'Açılış: Müzik', 'path': mus_rel})
                    seen_paths.add(mus_rel)
                # widget sprite image'ları
                for w in (data.get('widgets') or []):
                    sp = (w.get('sprite') or {}) if isinstance(w, dict) else {}
                    img_rel = sp.get('image')
                    if img_rel and img_rel not in seen_paths:
                        items.append({'type': 'screen', 'key': 'opening_widget_sprite', 'label': 'Açılış: Sprite Görseli', 'path': img_rel})
                        seen_paths.add(img_rel)
        except Exception:
            pass
        # Diğer tüm ekranlardan referans verilen medyaları ekle (victory, defeat, level_*, vb.)
        try:
            screens = self.screen_service.list_screens(game_id)
            for sc in screens:
                try:
                    if not getattr(sc, 'data_json', None):
                        continue
                    data = json.loads(sc.data_json)
                    name = getattr(sc, 'name', '') or (data.get('id') or '')
                    prefix = {
                        'opening': 'Açılış',
                        'victory': 'Zafer',
                        'defeat': 'Yenilgi'
                    }.get(name, f"Ekran: {name}")
                    # background
                    bg_rel = ((data.get('background') or {}).get('image')) or ''
                    if bg_rel and bg_rel not in seen_paths:
                        items.append({'type': 'screen', 'key': f'{name}_bg', 'label': f'{prefix}: Arkaplan', 'path': bg_rel})
                        seen_paths.add(bg_rel)
                    # music
                    mus_rel = data.get('music') or ''
                    if mus_rel and mus_rel not in seen_paths:
                        items.append({'type': 'screen', 'key': f'{name}_music', 'label': f'{prefix}: Müzik', 'path': mus_rel})
                        seen_paths.add(mus_rel)
                    # widget sprite image'ları
                    for w in (data.get('widgets') or []):
                        if not isinstance(w, dict):
                            continue
                        sp = (w.get('sprite') or {})
                        img_rel = sp.get('image')
                        if img_rel and img_rel not in seen_paths:
                            items.append({'type': 'screen', 'key': f'{name}_widget_sprite', 'label': f'{prefix}: Sprite Görseli', 'path': img_rel})
                            seen_paths.add(img_rel)
                except Exception:
                    continue
        except Exception:
            pass
        # Yalnızca bu oyunda kullanılan sprite sheet'leri topla
        try:
            # Oyunun seviyelerini ve ifadelerini gezerek kullanılan sprite tanımlarını bul
            levels = self.level_service.get_levels(game_id)
            used_sprite_ids = set()
            for lvl in levels:
                try:
                    exprs = self.expression_service.get_expressions(lvl.id)
                except Exception:
                    exprs = []
                for expr in exprs:
                    try:
                        sdef = self.sprite_service.get_sprite_definition_for_expr(expr.id)
                    except Exception:
                        sdef = None
                    if sdef and getattr(sdef, 'sprite_id', None):
                        used_sprite_ids.add(sdef.sprite_id)
            for sid in used_sprite_ids:
                try:
                    s = self.sprite_service.get_sprite_sheet(sid)
                except Exception:
                    s = None
                if s and s.path not in seen_paths:
                    items.append({'type': 'sprite', 'sprite_id': s.id, 'label': f"Sprite: {s.name}", 'path': s.path})
                    seen_paths.add(s.path)
        except Exception:
            # Sprite taraması başarısız olsa bile, galeri en azından ayarlardaki medyaları gösterebilsin
            pass
        cols = 3
        row = 0
        col = 0
        thumb_size = (160, 100)
        for it in items:
            frame = ttk.Frame(self.gallery_inner, padding=6)
            frame.grid(row=row, column=col, sticky="nw")
            path = it.get('path')
            abs_path = self._abs_path(path) if path else None
            thumb_label = ttk.Label(frame)
            thumb_label.pack()
            img_ref = None
            if abs_path and os.path.isfile(abs_path) and self._is_image(abs_path):
                try:
                    img = Image.open(abs_path)
                    img.thumbnail(thumb_size, Image.LANCZOS)
                    img_ref = ImageTk.PhotoImage(img)
                    thumb_label.configure(image=img_ref)
                    self._gallery_images.append(img_ref)
                except Exception:
                    thumb_label.configure(text="[Resim yüklenemedi]")
            else:
                name = os.path.basename(path) if path else "(yok)"
                thumb_label.configure(text=f"📄 {name}")
            ttk.Label(frame, text=it.get('label', '')).pack()
            ttk.Button(frame, text="Sil", command=lambda item=it: self._delete_media_item(item)).pack(pady=(4,0))
            col += 1
            if col >= cols:
                col = 0
                row += 1

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
        try:
            if item.get('type') == 'sprite':
                sprite_id = item.get('sprite_id')
                self.sprite_service.delete_sprite_sheet(sprite_id)
                abs_p = self._abs_path(item.get('path'))
                if abs_p and os.path.isfile(abs_p):
                    try:
                        os.remove(abs_p)
                    except Exception:
                        pass
            elif item.get('type') == 'setting':
                key = item.get('key')
                self.game_service.update_setting(self.current_game.id, key, '')
                abs_p = self._abs_path(item.get('path'))
                if abs_p and os.path.isfile(abs_p):
                    try:
                        os.remove(abs_p)
                    except Exception:
                        pass
            else:
                return
            messagebox.showinfo("Başarılı", "Medya silindi.")
        except Exception as e:
            messagebox.showerror("Hata", f"Medya silinirken hata: {e}")
        finally:
            self._refresh_media_gallery()


class MainWindow:
    """Main application window for the game editor."""

    def __init__(self, root: tk.Tk, db_manager: Optional[DatabaseManager] = None):
        """Initialize the main window."""
        self.root = root
        self.root.title("FizikselB Oyun Editörü")
        self.root.geometry("1200x800")
        
        # --- Styles ---
        style = ttk.Style(self.root)
        style.configure("Header.TLabel", font=('Segoe UI', 14, 'bold'))
        style.configure("Subheader.TLabel", font=('Segoe UI', 10, 'bold'))

        # --- Services ---
        self.db_manager = db_manager or DatabaseManager()
        self.game_service = GameService(self.db_manager)
        self.level_service = LevelService(self.db_manager)
        self.expression_service = ExpressionService(self.db_manager)
        self.sprite_service = SpriteService(self.db_manager)
        self.screen_service = ScreenService(self.db_manager)
        
        self.current_game_id: Optional[int] = None
        
        # --- Top Navbar ---
        navbar = ttk.Frame(root)
        navbar.pack(side=tk.TOP, fill=tk.X)
        # Place global managers on the navbar as buttons
        ttk.Button(navbar, text="Sprite'ları Düzenle", command=self._open_sprites_manager).pack(side=tk.LEFT, padx=(10, 4), pady=6)
        ttk.Button(navbar, text="Effectleri Düzenle", command=self._open_effects_manager).pack(side=tk.LEFT, padx=4, pady=6)
        ttk.Button(navbar, text="Medya'yı Düzenle", command=self._open_media_manager).pack(side=tk.LEFT, padx=4, pady=6)
        ttk.Button(navbar, text="Oyun Oyna", command=self._play_selected_game).pack(side=tk.RIGHT, padx=10, pady=6)

        # --- Layout ---
        paned_window = ttk.PanedWindow(root, orient=tk.HORIZONTAL)
        paned_window.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Left: Games List
        self.games_list_frame = GamesListFrame(
            paned_window, 
            self.game_service,
            on_game_select=self._on_game_selected,
            on_add=self._add_game,
            on_edit=self._edit_game,
            on_delete=self._delete_game
        )
        paned_window.add(self.games_list_frame, weight=1)

        # Right: Dashboard
        self.dashboard_frame = DashboardFrame(
            paned_window,
            self.game_service,
            self.level_service,
            self.expression_service,
            self.sprite_service,
            self.screen_service
        )
        paned_window.add(self.dashboard_frame, weight=4)
        
        # --- Initial Load ---
        self.games_list_frame.refresh_games()
        self.dashboard_frame.update_view()

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
        try:
            EffectsManagerWindow(self.root)
        except Exception as e:
            messagebox.showerror("Effect", f"Pencere açılamadı: {e}")

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
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
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
        """Handle request to add a new game."""
        dialog = GameDialog(self.root, title="Yeni Oyun Ekle")
        result = dialog.show()
        if not result:
            return
            
        name, description = result
        try:
            if not name:
                messagebox.showwarning("Geçersiz Ad", "Oyun adı boş olamaz.")
                return
            
            existing_games = self.game_service.get_games()
            if any(g.name.lower() == name.lower() for g in existing_games):
                messagebox.showwarning("Uyarı", f"'{name}' adında bir oyun zaten mevcut.")
                return

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
