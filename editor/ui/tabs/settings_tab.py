"""Settings tab for the game editor."""
import tkinter as tk
from tkinter import ttk, messagebox
from typing import Dict, Any, Optional, Callable

from ...core.services import GameService


class SettingsTab:
    """Tab for managing game settings."""
    
    def __init__(self, parent, game_service: GameService):
        """Initialize the settings tab.
        
        Args:
            parent: Parent widget.
            game_service: Service for game operations.
        """
        self.parent = parent
        self.game_service = game_service
        self.current_game_id = None
        
        # Create the main frame for this tab
        self.frame = ttk.Frame(parent)
        
        # Settings form
        self._setup_settings_form()
        
        # Track if we've loaded settings at least once
        self._initialized = False
    
    def _setup_settings_form(self) -> None:
        """Set up the settings form."""
        # Main container
        container = ttk.Frame(self.frame, padding="10")
        container.pack(fill=tk.BOTH, expand=True)
        
        # Form fields
        ttk.Label(container, text="Toplam Seviye Sayısı:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.total_levels = ttk.Spinbox(container, from_=1, to=100, width=10)
        self.total_levels.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(container, text="Varsayılan Yanlış Cevap Yüzdesi (%):").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.default_wrong_percentage = ttk.Spinbox(container, from_=0, to=100, width=10)
        self.default_wrong_percentage.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(container, text="Varsayılan Öğe Hızı:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.default_item_speed = ttk.Spinbox(container, from_=0.1, to=10.0, increment=0.1, width=10)
        self.default_item_speed.grid(row=2, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(container, text="Varsayılan Maksimum Öğe Sayısı:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.default_max_items = ttk.Spinbox(container, from_=1, to=20, width=10)
        self.default_max_items.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        
        # Save button
        btn_frame = ttk.Frame(container)
        btn_frame.grid(row=4, column=0, columnspan=2, pady=20)
        
        ttk.Button(
            btn_frame, 
            text="Ayarları Kaydet", 
            command=self.save_settings
        ).pack(side=tk.TOP, pady=10)
    
    def refresh(self) -> None:
        """Refresh the settings form with current values."""
        # Get the current game ID from the parent window
        parent = self.frame.winfo_toplevel()
        if not hasattr(parent, 'current_game_id') or parent.current_game_id is None:
            # Clear the form if no game is selected
            if self._initialized:
                self._clear_form()
            return
            
        game_id = parent.current_game_id
        
        # Only update if the game has changed
        if self.current_game_id == game_id and self._initialized:
            return
            
        self.current_game_id = game_id
        
        try:
            # Get settings for the current game
            settings = self.game_service.get_settings()
            
            # Update form fields
            self.total_levels.delete(0, tk.END)
            self.total_levels.insert(0, settings.get('total_levels', '10'))
            
            self.default_wrong_percentage.delete(0, tk.END)
            self.default_wrong_percentage.insert(0, settings.get('default_wrong_percentage', '20'))
            
            self.default_item_speed.delete(0, tk.END)
            self.default_item_speed.insert(0, settings.get('default_item_speed', '2.0'))
            
            self.default_max_items.delete(0, tk.END)
            self.default_max_items.insert(0, settings.get('default_max_items', '5'))
            
            self._initialized = True
            
        except Exception as e:
            messagebox.showerror("Hata", f"Ayarlar yüklenirken bir hata oluştu: {str(e)}")
    
    def _clear_form(self) -> None:
        """Clear all form fields."""
        for widget in [self.total_levels, self.default_wrong_percentage, 
                      self.default_item_speed, self.default_max_items]:
            widget.delete(0, tk.END)
            widget.insert(0, "")
        
        self.current_game_id = None
        self._initialized = False
    
    def save_settings(self) -> None:
        """Save the current settings."""
        # Get the current game ID from the parent window
        parent = self.frame.winfo_toplevel()
        if not hasattr(parent, 'current_game_id') or parent.current_game_id is None:
            messagebox.showerror("Hata", "Lütfen önce bir oyun seçin.")
            return
            
        game_id = parent.current_game_id
        
        try:
            settings = {
                'total_levels': self.total_levels.get(),
                'default_wrong_percentage': self.default_wrong_percentage.get(),
                'default_item_speed': self.default_item_speed.get(),
                'default_max_items': self.default_max_items.get()
            }
            
            # Validate inputs
            for key, value in settings.items():
                if not value:
                    messagebox.showerror("Hata", f"Lütfen tüm alanları doldurun: {key}")
                    return
            
            # Convert and validate numeric values
            try:
                total_levels = int(settings['total_levels'])
                wrong_percent = int(settings['default_wrong_percentage'])
                item_speed = float(settings['default_item_speed'])
                max_items = int(settings['default_max_items'])
                
                if total_levels < 1 or total_levels > 100:
                    raise ValueError("Toplam seviye sayısı 1-100 arasında olmalıdır.")
                if wrong_percent < 0 or wrong_percent > 100:
                    raise ValueError("Yanlış cevap yüzdesi 0-100 arasında olmalıdır.")
                if item_speed <= 0 or item_speed > 10:
                    raise ValueError("Öğe hızı 0.1-10.0 arasında olmalıdır.")
                if max_items < 1 or max_items > 20:
                    raise ValueError("Maksimum öğe sayısı 1-20 arasında olmalıdır.")
                    
            except ValueError as e:
                messagebox.showerror("Geçersiz Değer", str(e))
                return
            
            # Save settings
            for key, value in settings.items():
                self.game_service.update_setting(game_id, key, value)
            
            messagebox.showinfo("Başarılı", "Ayarlar başarıyla kaydedildi.")
            
        except Exception as e:
            messagebox.showerror("Hata", f"Ayarlar kaydedilirken bir hata oluştu: {str(e)}")
