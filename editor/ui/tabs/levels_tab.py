"""Levels tab for the game editor."""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Dict, Any, Optional, List, Callable

from ...core.models import Level
from ...core.services import LevelService, ExpressionService


class LevelsTab:
    """Tab for managing game levels."""
    
    def __init__(self, parent, level_service: LevelService, expression_service: ExpressionService):
        """Initialize the levels tab.
        
        Args:
            parent: Parent widget.
            level_service: Service for level operations.
            expression_service: Service for expression operations.
        """
        self.parent = parent
        self.level_service = level_service
        self.expression_service = expression_service
        
        # Create the main frame for this tab
        self.frame = ttk.Frame(parent)
        
        # Level list frame
        self._setup_level_list()
        
        # Buttons frame
        self._setup_buttons()
        
        # Load initial data
        self.refresh()
    
    def _setup_level_list(self) -> None:
        """Set up the level list view."""
        list_frame = ttk.LabelFrame(self.frame, text="Seviye Listesi", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview for levels
        columns = ("level", "name", "description", "wrong%", "speed", "max_items")
        self.level_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        # Configure columns
        self.level_tree.heading("level", text="Seviye No")
        self.level_tree.heading("name", text="Seviye Adı")
        self.level_tree.heading("description", text="Açıklama")
        self.level_tree.heading("wrong%", text="Yanlış Cevap %")
        self.level_tree.heading("speed", text="Hız")
        self.level_tree.heading("max_items", text="Maks. Öğe")
        
        self.level_tree.column("level", width=80, anchor="center")
        self.level_tree.column("name", width=150, anchor="center")
        self.level_tree.column("description", width=200, anchor="center")
        self.level_tree.column("wrong%", width=80, anchor="center")
        self.level_tree.column("speed", width=80, anchor="center")
        self.level_tree.column("max_items", width=80, anchor="center")
        
        self.level_tree.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.level_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.level_tree.configure(yscrollcommand=scrollbar.set)
        
        # Double-click to edit
        self.level_tree.bind("<Double-1>", lambda e: self.edit_level())
    
    def _setup_buttons(self) -> None:
        """Set up the action buttons."""
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(btn_frame, text="Yeni Seviye", command=self.add_level).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Düzenle", command=self.edit_level).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Sil", command=self.delete_level).pack(side=tk.LEFT, padx=5)
    
    def refresh(self) -> None:
        """Refresh the level list."""
        # Clear existing items
        for item in self.level_tree.get_children():
            self.level_tree.delete(item)
        
        # Get the current game ID from the parent window
        parent = self.frame.winfo_toplevel()
        if hasattr(parent, 'current_game_id'):
            game_id = parent.current_game_id
            
            # Load levels from the database for the current game
            levels = self.level_service.get_levels(game_id)
            
            # Add levels to the treeview
            for level in levels:
                self.level_tree.insert("", tk.END, values=(
                    level.level_number,
                    level.level_name,
                    level.level_description[:50] + "..." if level.level_description else "",
                    level.wrong_answer_percentage,
                    level.item_speed,
                    level.max_items_on_screen
                ), tags=(str(level.id),))
    
    def get_selected_level_id(self) -> Optional[int]:
        """Get the ID of the currently selected level."""
        selected = self.level_tree.selection()
        if not selected:
            messagebox.showwarning("Uyarı", "Lütfen bir seviye seçin.")
            return None
        return int(self.level_tree.item(selected[0], "tags")[0])
    
    def add_level(self) -> None:
        """Add a new level."""
        # Get the current game ID from the parent window
        parent = self.frame.winfo_toplevel()
        if not hasattr(parent, 'current_game_id'):
            messagebox.showerror("Hata", "Oyun bağlamı bulunamadı.")
            return
            
        dialog = LevelDialog(
            self.frame, 
            title="Yeni Seviye Ekle",
            on_submit=self._handle_add_level
        )
        self.frame.wait_window(dialog.top)
    
    def edit_level(self) -> None:
        """Edit the selected level."""
        level_id = self.get_selected_level_id()
        if not level_id:
            return
        
        level = self.level_service.get_level(level_id)
        if not level:
            messagebox.showerror("Hata", "Seviye bulunamadı.")
            return
        
        dialog = LevelDialog(
            self.frame,
            title="Seviyeyi Düzenle",
            level=level,
            on_submit=self._handle_edit_level
        )
        self.frame.wait_window(dialog.top)
    
    def delete_level(self) -> None:
        """Delete the selected level."""
        level_id = self.get_selected_level_id()
        if not level_id:
            return
        
        if not messagebox.askyesno("Onay", "Bu seviyeyi silmek istediğinize emin misiniz?"):
            return
        
        success = self.level_service.delete_level(level_id)
        if success:
            messagebox.showinfo("Başarılı", "Seviye başarıyla silindi.")
            self.refresh()
        else:
            messagebox.showerror("Hata", "Seviye silinirken bir hata oluştu.")
    
    def _handle_add_level(self, level_data: Dict[str, Any]) -> None:
        """Handle adding a new level."""
        try:
            # Get the current game ID from the parent window
            parent = self.frame.winfo_toplevel()
            if not hasattr(parent, 'current_game_id'):
                messagebox.showerror("Hata", "Oyun bağlamı bulunamadı.")
                return
                
            # Add the current game ID to the level data
            level_data['game_id'] = parent.current_game_id
            
            self.level_service.create_level(level_data)
            messagebox.showinfo("Başarılı", "Seviye başarıyla eklendi.")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Hata", f"Seviye eklenirken bir hata oluştu: {str(e)}")
    
    def _handle_edit_level(self, level_data: Dict[str, Any]) -> None:
        """Handle editing an existing level."""
        level_id = self.get_selected_level_id()
        if not level_id:
            return
        
        try:
            updated = self.level_service.update_level(level_id, level_data)
            if updated:
                messagebox.showinfo("Başarılı", "Seviye başarıyla güncellendi.")
                self.refresh()
            else:
                messagebox.showerror("Hata", "Seviye güncellenirken bir hata oluştu.")
        except Exception as e:
            messagebox.showerror("Hata", f"Seviye güncellenirken bir hata oluştu: {str(e)}")


class LevelDialog:
    """Dialog for adding/editing levels."""
    
    def __init__(
        self, 
        parent, 
        title: str, 
        level: Optional[Dict[str, Any]] = None,
        on_submit: Optional[Callable[[Dict[str, Any]], None]] = None
    ):
        """Initialize the dialog.
        
        Args:
            parent: Parent widget.
            title: Dialog title.
            level: Optional level data for editing.
            on_submit: Callback when the form is submitted.
        """
        self.parent = parent
        self.level = level or {}
        self.on_submit = on_submit
        
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.transient(parent)
        self.top.grab_set()
        
        # Center the dialog
        self.top.geometry("500x400")
        self.top.update_idletasks()
        width = self.top.winfo_width()
        height = self.top.winfo_height()
        x = (self.top.winfo_screenwidth() // 2) - (width // 2)
        y = (self.top.winfo_screenheight() // 2) - (height // 2)
        self.top.geometry(f"{width}x{height}+{x}+{y}")
        
        # Create form
        self._create_form()
    
    def _create_form(self) -> None:
        """Create the form fields."""
        # Main frame
        main_frame = ttk.Frame(self.top, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        # Form fields
        ttk.Label(main_frame, text="Seviye Numarası:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.level_number = ttk.Spinbox(main_frame, from_=1, to=100, width=10)
        self.level_number.grid(row=0, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(main_frame, text="Seviye Adı:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.level_name = ttk.Entry(main_frame, width=40)
        self.level_name.grid(row=1, column=1, columnspan=2, sticky="we", padx=5, pady=5)
        
        ttk.Label(main_frame, text="Açıklama:").grid(row=2, column=0, sticky="ne", padx=5, pady=5)
        self.level_description = tk.Text(main_frame, height=5, width=40)
        self.level_description.grid(row=2, column=1, columnspan=2, sticky="we", padx=5, pady=5)
        
        ttk.Label(main_frame, text="Yanlış Cevap Yüzdesi (%):").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        self.wrong_percentage = ttk.Spinbox(main_frame, from_=0, to=100, width=10)
        self.wrong_percentage.grid(row=3, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(main_frame, text="Öğe Hızı:").grid(row=4, column=0, sticky="e", padx=5, pady=5)
        self.item_speed = ttk.Spinbox(main_frame, from_=0.1, to=10.0, increment=0.1, width=10)
        self.item_speed.grid(row=4, column=1, sticky="w", padx=5, pady=5)
        
        ttk.Label(main_frame, text="Maksimum Ekrandaki Öğe Sayısı:").grid(row=5, column=0, sticky="e", padx=5, pady=5)
        self.max_items = ttk.Spinbox(main_frame, from_=1, to=20, width=10)
        self.max_items.grid(row=5, column=1, sticky="w", padx=5, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=6, column=0, columnspan=3, pady=10)
        
        ttk.Button(btn_frame, text="İptal", command=self.top.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Kaydet", command=self._on_submit).pack(side=tk.RIGHT, padx=5)
        
        # Load data if editing
        if self.level:
            self._load_data()
    
    def _load_data(self) -> None:
        """Load level data into the form."""
        self.level_number.delete(0, tk.END)
        self.level_number.insert(0, str(self.level.get('level_number', 1)))
        
        self.level_name.delete(0, tk.END)
        self.level_name.insert(0, self.level.get('level_name', ''))
        
        self.level_description.delete('1.0', tk.END)
        self.level_description.insert('1.0', self.level.get('level_description', ''))
        
        self.wrong_percentage.delete(0, tk.END)
        self.wrong_percentage.insert(0, str(self.level.get('wrong_answer_percentage', 20)))
        
        self.item_speed.delete(0, tk.END)
        self.item_speed.insert(0, str(self.level.get('item_speed', 2.0)))
        
        self.max_items.delete(0, tk.END)
        self.max_items.insert(0, str(self.level.get('max_items_on_screen', 5)))
    
    def _on_submit(self) -> None:
        """Handle form submission."""
        try:
            level_data = {
                'level_number': int(self.level_number.get()),
                'level_name': self.level_name.get().strip(),
                'level_description': self.level_description.get('1.0', tk.END).strip(),
                'wrong_answer_percentage': int(self.wrong_percentage.get()),
                'item_speed': float(self.item_speed.get()),
                'max_items_on_screen': int(self.max_items.get())
            }
            
            if not level_data['level_name']:
                messagebox.showerror("Hata", "Lütfen bir seviye adı girin.")
                return
            
            if self.on_submit:
                self.on_submit(level_data)
            
            self.top.destroy()
            
        except ValueError as e:
            messagebox.showerror("Hata", f"Geçersiz değer: {str(e)}")
