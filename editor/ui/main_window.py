"""Main window for the game editor."""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Optional, Dict, Any, List, Callable

from ..core.services import GameService, LevelService, ExpressionService
from ..database.database import DatabaseManager
from .tabs.levels_tab import LevelsTab
from .tabs.expressions_tab import ExpressionsTab
from .tabs.settings_tab import SettingsTab
from .game_dialog import GameDialog


class GameSelector(ttk.Frame):
    """Game selection dropdown with add button."""
    
    def __init__(self, parent, game_service: GameService, on_game_selected: Callable[[int], None], on_game_added: Callable[[str, str], None]):
        """Initialize the game selector.
        
        Args:
            parent: Parent widget.
            game_service: Game service for database operations.
            on_game_selected: Callback when a game is selected.
            on_game_added: Callback when a new game is added (name, description).
        """
        super().__init__(parent)
        self.game_service = game_service
        self.on_game_selected = on_game_selected
        self.on_game_added = on_game_added
        self.games = {}
        
        # Create widgets
        ttk.Label(self, text="Oyun:").pack(side=tk.LEFT, padx=5)
        
        self.game_var = tk.StringVar()
        self.game_dropdown = ttk.Combobox(
            self,
            textvariable=self.game_var,
            state="readonly",
            width=40
        )
        self.game_dropdown.pack(side=tk.LEFT, padx=5)
        self.game_dropdown.bind("<<ComboboxSelected>>", self._on_game_selected)
        
        ttk.Button(
            self,
            text="Yeni Oyun Ekle",
            command=self._add_new_game
        ).pack(side=tk.LEFT, padx=5)
        
        # Load games
        self.refresh_games()
    
    def refresh_games(self) -> None:
        """Refresh the list of games from the database."""
        with self.game_service.db._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT id, name FROM games ORDER BY name')
            self.games = {}
            game_names = []
            
            for game_id, name in cursor.fetchall():
                self.games[name] = game_id
                game_names.append(name)
            
            current = self.game_var.get()
            self.game_dropdown['values'] = game_names
            
            # Try to restore the previous selection
            if current in self.games:
                self.game_dropdown.set(current)
            elif game_names:
                self.game_dropdown.current(0)
                self._on_game_selected()
    
    def _on_game_selected(self, event=None) -> None:
        """Handle game selection."""
        selected_game = self.game_var.get()
        if selected_game and selected_game in self.games:
            self.on_game_selected(self.games[selected_game])
    
    def _add_new_game(self) -> None:
        """Show dialog to add a new game with description."""
        dialog = GameDialog(self, title="Yeni Oyun Ekle")
        result = dialog.show()
        if not result:
            return
        name, description = result
        self.on_game_added(game_name=name, game_description=description)


class MainWindow:
    """Main application window for the game editor."""
    
    def _on_game_added(self, game_name: str, game_description: str = "") -> None:
        """
        Yeni bir oyun eklendiğinde arayüzü ve ilgili değişkenleri günceller.
        Args:
            game_name (str): Eklenen oyunun adı.
            game_description (str): Eklenen oyunun açıklaması (opsiyonel).
        """
        try:
            # Validate game name
            if not game_name or not game_name.strip():
                messagebox.showwarning("Uyarı", "Lütfen geçerli bir oyun adı girin.")
                return
                
            # Check if game name already exists
            existing_games = self.game_service.get_games()
            if any(g.name.lower() == game_name.lower() for g in existing_games):
                messagebox.showwarning("Uyarı", f"'{game_name}' adında bir oyun zaten mevcut.")
                return
            
            # Create the new game with name and description
            game = self.game_service.create_game(game_name, game_description)

            # Refresh the game selector
            self.game_selector.refresh_games()
            
            # Select the new game
            self.game_selector.game_var.set(game_name)
            self.current_game_id = game.id
            
            # Update window title
            self.root.title(f"FizikselB Oyun Editörü - {game_name}")
            
            # Refresh tabs with the new game data
            self.refresh_tabs(game.id)
            
            messagebox.showinfo("Başarılı", f"'{game_name}' oyunu başarıyla eklendi.")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Oyun eklenirken bir hata oluştu: {str(e)}")

    def __init__(self, root: tk.Tk, db_manager: Optional[DatabaseManager] = None):
        """Initialize the main window.
        
        Args:
            root: The root Tkinter window.
            db_manager: Database manager instance. If None, a new one will be created.
        """
        self.root = root
        self.root.title("Oyun Seviye Editörü")
        self.root.geometry("1000x800")
        
        # Initialize services
        self.db_manager = db_manager or DatabaseManager()
        self.game_service = GameService(self.db_manager)
        self.level_service = LevelService(self.db_manager)
        self.expression_service = ExpressionService(self.db_manager)
        
        # Current game (default to ID 1 for now)
        self.current_game_id = 1
        
        # Create main container
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Add game selector at the top
        self._setup_game_selector()
        
        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        
        # Create tabs
        self.tabs: Dict[str, ttk.Frame] = {}
        self._setup_tabs()
    
    def _setup_game_selector(self) -> None:
        """Set up the game selection dropdown."""
        # Create a frame for the game selector with a border and padding
        selector_frame = ttk.LabelFrame(self.main_frame, text="Oyun Seçimi", padding="5")
        selector_frame.pack(fill=tk.X, padx=5, pady=5, anchor="n")
        
        # Create the game selector inside the frame
        self.game_selector = GameSelector(
            selector_frame,
            self.game_service,
            self._on_game_selected,
            self._on_game_added
        )
        
        # Pack the game selector to fill the frame
        self.game_selector.pack(fill=tk.X, expand=True, pady=5)
        
        # Make sure the frame is visible
        selector_frame.pack_propagate(True)
    
    def _on_game_selected(self, game_id: int) -> None:
        """
        Oyun seçildiğinde ilgili ID'yi hem MainWindow hem de kök widget'a (root) aktarır, başlığı ve servisleri günceller.
        Args:
            game_id: Seçilen oyunun ID'si.
        """
        try:
            # Mevcut oyun ID'sini güncelle
            self.current_game_id = game_id
            # Kök widget'a da oyun ID'sini aktar
            setattr(self.root, "current_game_id", game_id)
            
            # Update window title with the selected game name
            game = self.game_service.get_game(game_id)
            if game:
                self.root.title(f"FizikselB Oyun Editörü - {game.name}")
            
            # Update services with the new game ID
            # Note: We don't need to recreate services, just update their current_game_id
            if hasattr(self, 'level_service'):
                self.level_service.current_game_id = game_id
            if hasattr(self, 'expression_service'):
                self.expression_service.current_game_id = game_id
            
            # Only refresh tabs if they've been initialized
            if hasattr(self, 'tabs') and self.tabs:
                self.refresh_tabs(game_id)
                
        except Exception as e:
            messagebox.showerror("Hata", f"Oyun yüklenirken bir hata oluştu: {str(e)}")
            # Fall back to default title if there's an error
            self.root.title("FizikselB Oyun Editörü")
    
    def _on_game_added(self, game_name: str, game_description: str = "") -> None:
        """Handle adding a new game.
        
        Args:
            game_name: Name of the new game
            game_description: Optional description for the new game
        """
        try:
            # Validate game name
            if not game_name or not game_name.strip():
                messagebox.showwarning("Uyarı", "Lütfen geçerli bir oyun adı girin.")
                return
                
            # Check if game name already exists
            existing_games = self.game_service.get_games()
            if any(g.name.lower() == game_name.lower() for g in existing_games):
                messagebox.showwarning("Uyarı", f"'{game_name}' adında bir oyun zaten mevcut.")
                return
            
            # Add the new game to the database with default settings
            game = self.game_service.create_game(game_name)
            
            # Set default settings for the new game
            default_settings = {
                'total_levels': '10',
                'default_wrong_percentage': '20',
                'default_item_speed': '2.0',
                'default_max_items': '5'
            }
            
            for key, value in default_settings.items():
                self.game_service.update_setting(game.id, key, value)
            
            # Oyun seçim kutusunu güncelle
            self.game_selector.refresh_games()
            
            # Select the new game
            self.game_selector.game_var.set(game_name)
            self.current_game_id = game.id
            
            # Update window title
            self.root.title(f"FizikselB Oyun Editörü - {game_name}")
            
            # Refresh tabs with the new game data
            self.refresh_tabs(game.id)
            
            messagebox.showinfo("Başarılı", f"'{game_name}' oyunu başarıyla eklendi.")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Oyun eklenirken bir hata oluştu: {str(e)}")
    
    def _setup_tabs(self) -> None:
        """Set up the application tabs."""
        # Clear existing tabs
        for tab_id in self.notebook.tabs():
            self.notebook.forget(tab_id)
        
        # Clear existing tab references
        self.tabs = {}
        
        # Create new tabs with the current game context
        self.tabs['levels'] = LevelsTab(
            self.notebook, 
            self.level_service,
            self.expression_service
        )
        self.notebook.add(self.tabs['levels'].frame, text="Seviyeler")
        
        self.tabs['expressions'] = ExpressionsTab(
            self.notebook,
            self.level_service,
            self.expression_service
        )
        self.notebook.add(self.tabs['expressions'].frame, text="İfadeler")
        
        self.tabs['settings'] = SettingsTab(
            self.notebook,
            self.game_service
        )
        self.notebook.add(self.tabs['settings'].frame, text="Ayarlar")
        
    def refresh_tabs(self, game_id: int) -> None:
        """Refresh all tabs with the current game's data.
        
        Args:
            game_id: ID of the selected game.
        """
        # Update the current game ID
        self.current_game_id = game_id
        
        # Refresh each tab that has a refresh method
        for tab in self.tabs.values():
            if hasattr(tab, 'refresh'):
                tab.refresh()
    
    def _on_tab_changed(self, event: tk.Event) -> None:
        """Handle tab change events."""
        current_tab = self.notebook.select()
        if not current_tab:  # No tab selected
            return
            
        tab_name = self.notebook.tab(current_tab, 'text')
        
        # Refresh the tab content if it has a refresh method
        if tab_name and hasattr(self.tabs.get(tab_name.lower(), {}), 'refresh'):
            self.tabs[tab_name.lower()].refresh()
    
    def run(self) -> None:
        """Run the main application loop."""
        self.root.mainloop()
