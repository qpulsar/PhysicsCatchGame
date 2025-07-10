"""Expressions tab for the game editor."""
import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Dict, Any, Optional, List, Callable, Tuple

from ...core.models import Expression
from ...core.services import LevelService, ExpressionService


class ExpressionsTab:
    """Tab for managing expressions for each level."""
    
    def __init__(self, parent, level_service: LevelService, expression_service: ExpressionService):
        """Initialize the expressions tab.
        
        Args:
            parent: Parent widget.
            level_service: Service for level operations.
            expression_service: Service for expression operations.
        """
        self.parent = parent
        self.level_service = level_service
        self.expression_service = expression_service
        self.current_level_id = None
        
        # Create the main frame for this tab
        self.frame = ttk.Frame(parent)
        
        # Level selection
        self._setup_level_selection()
        
        # Expressions list
        self._setup_expression_list()
        
        # Buttons frame
        self._setup_buttons()
        
        # Load initial data
        self.refresh_levels()
    
    def _setup_level_selection(self) -> None:
        """Set up the level selection combo box."""
        level_frame = ttk.Frame(self.frame)
        level_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Label(level_frame, text="Seviye Seçin:").pack(side=tk.LEFT, padx=5)
        
        self.level_var = tk.StringVar()
        self.level_combo = ttk.Combobox(
            level_frame, 
            textvariable=self.level_var, 
            state="readonly"
        )
        self.level_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.level_combo.bind("<<ComboboxSelected>>", self._on_level_selected)
    
    def _setup_expression_list(self) -> None:
        """Set up the expressions list view."""
        list_frame = ttk.LabelFrame(self.frame, text="İfadeler", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Treeview for expressions
        columns = ("expression", "is_correct")
        self.expr_tree = ttk.Treeview(list_frame, columns=columns, show="headings")
        
        # Configure columns
        self.expr_tree.heading("expression", text="İfade")
        self.expr_tree.heading("is_correct", text="Doğru mu?")
        
        self.expr_tree.column("expression", width=400)
        self.expr_tree.column("is_correct", width=100, anchor=tk.CENTER)
        
        self.expr_tree.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.expr_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.expr_tree.configure(yscrollcommand=scrollbar.set)
        
        # Double-click to edit
        self.expr_tree.bind("<Double-1>", lambda e: self.edit_expression())
    
    def _setup_buttons(self) -> None:
        """Set up the action buttons."""
        btn_frame = ttk.Frame(self.frame)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(btn_frame, text="İfade Ekle", command=self.add_expression).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Düzenle", command=self.edit_expression).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Sil", command=self.delete_expression).pack(side=tk.LEFT, padx=5)
    
    def refresh_levels(self) -> None:
        """Refresh the level list in the combo box."""
        # Get the current game ID from the parent window
        parent = self.frame.winfo_toplevel()
        if not hasattr(parent, 'current_game_id'):
            return
            
        levels = self.level_service.get_levels(parent.current_game_id)
        self.levels = {f"{level.level_number}. {level.level_name}": level.id for level in levels}
        
        current_selection = self.level_var.get()
        self.level_combo['values'] = list(self.levels.keys())
        
        # Try to restore the previous selection if it still exists
        if current_selection in self.levels:
            self.level_combo.set(current_selection)
        # Select the first level by default if available
        elif levels:
            self.level_combo.current(0)
        
        # Refresh expressions if we have a selection
        if self.level_var.get():
            self._on_level_selected()
    
    def refresh_expressions(self) -> None:
        """Refresh the expressions list for the current level."""
        # Clear existing items
        for item in self.expr_tree.get_children():
            self.expr_tree.delete(item)
        
        if not self.current_level_id:
            return
        
        try:
            # Load expressions from the database
            expressions = self.expression_service.get_expressions(self.current_level_id)
            
            # Add expressions to the treeview
            for expr in expressions:
                self.expr_tree.insert(
                    "", 
                    tk.END, 
                    values=(
                        expr.expression,
                        "Evet" if expr.is_correct else "Hayır"
                    ), 
                    tags=(str(expr.id),)
                )
        except Exception as e:
            messagebox.showerror("Hata", f"İfadeler yüklenirken bir hata oluştu: {str(e)}")
    
    def refresh(self) -> None:
        """Refresh both levels and expressions."""
        # Clear current selection
        self.current_level_id = None
        self.level_var.set("")
        
        # Clear the expressions tree
        for item in self.expr_tree.get_children():
            self.expr_tree.delete(item)
            
        # Refresh the levels list
        self.refresh_levels()
    
    def _on_level_selected(self, event=None) -> None:
        """Handle level selection change."""
        selected_level = self.level_var.get()
        if not selected_level:
            self.current_level_id = None
            return
        
        # Clear previous expressions
        for item in self.expr_tree.get_children():
            self.expr_tree.delete(item)
        
        # Update current level ID and refresh expressions
        self.current_level_id = self.levels.get(selected_level)
        if self.current_level_id:
            try:
                self.refresh_expressions()
            except Exception as e:
                messagebox.showerror("Hata", f"Seviye yüklenirken bir hata oluştu: {str(e)}")
                self.current_level_id = None
                self.level_var.set("")
    
    def get_selected_expression_id(self) -> Optional[int]:
        """Get the ID of the currently selected expression."""
        selected = self.expr_tree.selection()
        if not selected:
            messagebox.showwarning("Uyarı", "Lütfen bir ifade seçin.")
            return None
        return int(self.expr_tree.item(selected[0], "tags")[0])
    
    def add_expression(self) -> None:
        """Add a new expression."""
        if not self.current_level_id:
            messagebox.showwarning("Uyarı", "Lütfen önce bir seviye seçin.")
            return
        
        # Get the current level to show in the dialog title
        level_name = ""
        parent = self.frame.winfo_toplevel()
        if hasattr(parent, 'current_game_id'):
            try:
                level = self.level_service.get_level(self.current_level_id)
                if level:
                    level_name = f" - {level.level_name}"
            except:
                pass
        
        dialog = ExpressionDialog(
            self.frame, 
            title=f"Yeni İfade Ekle{level_name}",
            on_submit=self._handle_add_expression
        )
        self.frame.wait_window(dialog.top)
    
    def edit_expression(self) -> None:
        """Edit the selected expression."""
        if not self.current_level_id:
            messagebox.showwarning("Uyarı", "Lütfen önce bir seviye seçin.")
            return
        
        expr_id = self.get_selected_expression_id()
        if not expr_id:
            return
        
        expr = self.expression_service._get_expression(expr_id)
        if not expr:
            messagebox.showerror("Hata", "İfade bulunamadı.")
            return
        
        dialog = ExpressionDialog(
            self.frame,
            title="İfadeyi Düzenle",
            expression=expr.expression,
            is_correct=expr.is_correct,
            on_submit=self._handle_edit_expression
        )
        self.frame.wait_window(dialog.top)
    
    def delete_expression(self) -> None:
        """Delete the selected expression."""
        if not self.current_level_id:
            messagebox.showwarning("Uyarı", "Lütfen önce bir seviye seçin.")
            return
        
        expr_id = self.get_selected_expression_id()
        if not expr_id:
            return
        
        if not messagebox.askyesno("Onay", "Bu ifadeyi silmek istediğinize emin misiniz?"):
            return
        
        success = self.expression_service.delete_expression(expr_id)
        if success:
            messagebox.showinfo("Başarılı", "İfade başarıyla silindi.")
            self.refresh_expressions()
        else:
            messagebox.showerror("Hata", "İfade silinirken bir hata oluştu.")
    
    def _handle_add_expression(self, expr_data: Tuple[str, bool]) -> None:
        """Handle adding a new expression."""
        try:
            if not self.current_level_id:
                messagebox.showerror("Hata", "Geçersiz seviye.")
                return
                
            expression, is_correct = expr_data
            if not expression.strip():
                messagebox.showwarning("Uyarı", "Lütfen geçerli bir ifade girin.")
                return
                
            self.expression_service.add_expression(self.current_level_id, expression, is_correct)
            messagebox.showinfo("Başarılı", "İfade başarıyla eklendi.")
            self.refresh_expressions()
        except Exception as e:
            messagebox.showerror("Hata", f"İfade eklenirken bir hata oluştu: {str(e)}")
    
    def _handle_edit_expression(self, expr_data: Tuple[str, bool]) -> None:
        """Handle editing an existing expression."""
        expr_id = self.get_selected_expression_id()
        if not expr_id:
            return
        
        try:
            expression, is_correct = expr_data
            updated = self.expression_service.update_expression(expr_id, expression, is_correct)
            if updated:
                messagebox.showinfo("Başarılı", "İfade başarıyla güncellendi.")
                self.refresh_expressions()
            else:
                messagebox.showerror("Hata", "İfade güncellenirken bir hata oluştu.")
        except Exception as e:
            messagebox.showerror("Hata", f"İfade güncellenirken bir hata oluştu: {str(e)}")


class ExpressionDialog:
    """Dialog for adding/editing expressions."""
    
    def __init__(
        self, 
        parent, 
        title: str, 
        expression: str = "",
        is_correct: bool = True,
        on_submit: Optional[Callable[[Tuple[str, bool]], None]] = None
    ):
        """Initialize the dialog.
        
        Args:
            parent: Parent widget.
            title: Dialog title.
            expression: Optional expression text for editing.
            is_correct: Whether the expression is correct.
            on_submit: Callback when the form is submitted.
        """
        self.parent = parent
        self.expression = expression
        self.is_correct = is_correct
        self.on_submit = on_submit
        
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.transient(parent)
        self.top.grab_set()
        
        # Center the dialog
        self.top.geometry("500x300")
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
        ttk.Label(main_frame, text="İfade:").grid(row=0, column=0, sticky="ne", padx=5, pady=5)
        self.expression_text = tk.Text(main_frame, height=5, width=40)
        self.expression_text.grid(row=0, column=1, columnspan=2, sticky="we", padx=5, pady=5)
        
        self.is_correct_var = tk.BooleanVar(value=self.is_correct)
        ttk.Checkbutton(
            main_frame, 
            text="Doğru İfade",
            variable=self.is_correct_var
        ).grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        # Buttons
        btn_frame = ttk.Frame(main_frame)
        btn_frame.grid(row=2, column=0, columnspan=3, pady=10)
        
        ttk.Button(btn_frame, text="İptal", command=self.top.destroy).pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="Kaydet", command=self._on_submit).pack(side=tk.RIGHT, padx=5)
        
        # Load data if editing
        if self.expression:
            self.expression_text.insert('1.0', self.expression)
    
    def _on_submit(self) -> None:
        """Handle form submission."""
        expression = self.expression_text.get('1.0', tk.END).strip()
        is_correct = self.is_correct_var.get()
        
        if not expression:
            messagebox.showerror("Hata", "Lütfen bir ifade girin.")
            return
        
        if self.on_submit:
            self.on_submit((expression, is_correct))
        
        self.top.destroy()
