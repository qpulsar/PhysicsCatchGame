"""Main window for the game editor."""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Any

from ..core.models import Game
from ..core.services import GameService, LevelService, ExpressionService, SpriteService
from ..database.database import DatabaseManager
from .tabs.levels_tab import LevelsTab
from .tabs.settings_tab import SettingsTab
from .tabs.sprites_tab import SpritesTab
from .game_dialog import GameDialog


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
        
        if select_id:
            if self.games_tree.exists(str(select_id)):
                self.games_tree.selection_set(str(select_id))
                self.games_tree.focus(str(select_id))

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
    def __init__(self, parent, game_service: GameService, level_service: LevelService, expression_service: ExpressionService, sprite_service: SpriteService):
        super().__init__(parent)
        self.game_service = game_service
        self.level_service = level_service
        self.expression_service = expression_service
        self.sprite_service = sprite_service
        self.current_game: Optional[Game] = None
        
        # --- Layout ---
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        # --- Widgets ---
        self.title_label = ttk.Label(self, text="Lütfen bir oyun seçin.", style="Header.TLabel")
        self.title_label.grid(row=0, column=0, sticky="w", padx=10, pady=5)
        
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
            
            settings = self.game_service.get_settings(self.current_game.id)
            settings_text = "\n".join([f"{k}: {v}" for k, v in settings.settings.items()])
            self.settings_text.config(state="normal")
            self.settings_text.delete("1.0", tk.END)
            self.settings_text.insert("1.0", settings_text or "Ayarlar bulunamadı.")
            self.settings_text.config(state="disabled")
            
            self.notebook.tab(0, state="normal")
            for i in range(1, self.notebook.index("end")):
                self.notebook.tab(i, state="normal")
        else:
            self.title_label.config(text="Lütfen bir oyun seçin veya yeni bir tane ekleyin.")
            self.desc_label.config(text="")
            self.settings_text.config(state="normal")
            self.settings_text.delete("1.0", tk.END)
            self.settings_text.config(state="disabled")

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
        gallery_frame = ttk.LabelFrame(frame, text=" (Yakında) ", padding=10)
        gallery_frame.grid(row=5, column=0, sticky="nsew")
        ttk.Label(gallery_frame, text="Oyun medyaları burada görünecek.").pack()
        
        return frame
        
    def _update_tabs(self):
        """Creates or refreshes the management tabs."""
        for tab in self.tabs.values():
            tab.frame.destroy()
        self.tabs.clear()
        
        # Remove old tabs (except summary)
        while self.notebook.index("end") > 1:
            self.notebook.forget(1)
        
        if self.current_game:
            self.tabs['levels'] = LevelsTab(self.notebook, self.game_service, self.level_service, self.expression_service)
            self.notebook.add(self.tabs['levels'].frame, text="Seviyeler")

            self.tabs['sprites'] = SpritesTab(self.notebook, self.sprite_service, self.expression_service)
            self.notebook.add(self.tabs['sprites'].frame, text="Sprite Yönetimi")

            self.tabs['settings'] = SettingsTab(self.notebook, self.game_service)
            self.notebook.add(self.tabs['settings'].frame, text="Ayarlar")
            
            self.refresh_tabs()

    def refresh_tabs(self):
        """Calls the refresh method on all available tabs."""
        if self.current_game:
            for tab in self.tabs.values():
                if hasattr(tab, 'refresh'):
                    tab.refresh()


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
        
        self.current_game_id: Optional[int] = None
        
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
            self.sprite_service
        )
        paned_window.add(self.dashboard_frame, weight=4)
        
        # --- Initial Load ---
        self.games_list_frame.refresh_games()
        self.dashboard_frame.update_view()

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
