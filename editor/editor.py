import sqlite3
import tkinter as tk
from tkinter import ttk, messagebox
import os
import sys

# Add the parent directory to the path so we can import from the editor package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from editor.database.database import DatabaseManager
from editor.ui.main_window import MainWindow


def main():
    """Main entry point for the application."""
    # Initialize the database
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'game_data.db')
    db_manager = DatabaseManager(db_path)

    # Create the main application window
    root = tk.Tk()
    app = MainWindow(root, db_manager)

    # Start the application
    root.mainloop()


class LevelEditor:
    def __init__(self, root, DB_PATH):
        self.root = root
        self.root.title("Oyun Seviye Editörü")
        self.root.geometry("900x700")
        self.DB_PATH = DB_PATH
        # Initialize database
        # init_database()

        # Create main container
        self.main_frame = ttk.Frame(root, padding="10")
        self.main_frame.pack(fill=tk.BOTH, expand=True)

        # Create notebook for tabs
        self.notebook = ttk.Notebook(self.main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)

        # Create tabs
        self.setup_levels_tab()
        self.setup_expressions_tab()
        self.setup_settings_tab()

        # Load initial data
        self.load_levels()

    def setup_levels_tab(self):
        """Setup the levels management tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Seviyeler")

        # Level list frame
        list_frame = ttk.LabelFrame(tab, text="Seviye Listesi", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Treeview for levels
        columns = ("level", "name", "description", "wrong%", "speed", "max_items")
        self.level_tree = ttk.Treeview(list_frame, columns=columns, show="headings")

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

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.level_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.level_tree.configure(yscrollcommand=scrollbar.set)

        # Buttons frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="Yeni Seviye", command=self.add_level).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Düzenle", command=self.edit_level).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Sil", command=self.delete_level).pack(side=tk.LEFT, padx=5)

    def setup_expressions_tab(self):
        """Setup the expressions management tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="İfadeler")

        # Level selection
        level_frame = ttk.Frame(tab)
        level_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(level_frame, text="Seviye Seçin:").pack(side=tk.LEFT, padx=5)
        self.level_var = tk.StringVar()
        self.level_combo = ttk.Combobox(level_frame, textvariable=self.level_var, state="readonly")
        self.level_combo.pack(side=tk.LEFT, padx=5, fill=tk.X, expand=True)
        self.level_combo.bind("<<ComboboxSelected>>", self.load_expressions)

        # Expressions list
        list_frame = ttk.LabelFrame(tab, text="İfadeler", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        columns = ("expression", "is_correct")
        self.expr_tree = ttk.Treeview(list_frame, columns=columns, show="headings")

        self.expr_tree.heading("expression", text="İfade")
        self.expr_tree.heading("is_correct", text="Doğru mu?")

        self.expr_tree.column("expression", width=400)
        self.expr_tree.column("is_correct", width=100, anchor=tk.CENTER)

        self.expr_tree.pack(fill=tk.BOTH, expand=True, pady=5)

        # Scrollbar
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.expr_tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.expr_tree.configure(yscrollcommand=scrollbar.set)

        # Buttons frame
        btn_frame = ttk.Frame(tab)
        btn_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Button(btn_frame, text="İfade Ekle", command=self.add_expression).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Düzenle", command=self.edit_expression).pack(side=tk.LEFT, padx=5)
        ttk.Button(btn_frame, text="Sil", command=self.delete_expression).pack(side=tk.LEFT, padx=5)

    def setup_settings_tab(self):
        """Setup the settings tab."""
        tab = ttk.Frame(self.notebook)
        self.notebook.add(tab, text="Ayarlar")

        # Settings form
        form_frame = ttk.LabelFrame(tab, text="Varsayılan Ayarlar", padding=10)
        form_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        # Total levels
        ttk.Label(form_frame, text="Toplam Seviye Sayısı:").grid(row=0, column=0, sticky=tk.W, pady=5)
        self.total_levels_var = tk.StringVar()
        ttk.Spinbox(form_frame, from_=1, to=100, textvariable=self.total_levels_var, width=10).grid(row=0, column=1,
                                                                                                    sticky=tk.W, padx=5,
                                                                                                    pady=5)

        # Default wrong percentage
        ttk.Label(form_frame, text="Varsayılan Yanlış Yüzdesi:").grid(row=1, column=0, sticky=tk.W, pady=5)
        self.default_wrong_var = tk.StringVar()
        ttk.Spinbox(form_frame, from_=0, to=100, textvariable=self.default_wrong_var, width=10).grid(row=1, column=1,
                                                                                                     sticky=tk.W,
                                                                                                     padx=5, pady=5)

        # Default item speed
        ttk.Label(form_frame, text="Varsayılan Öğe Hızı:").grid(row=2, column=0, sticky=tk.W, pady=5)
        self.default_speed_var = tk.StringVar()
        ttk.Spinbox(form_frame, from_=0.1, to=10.0, increment=0.1, format="%.1f",
                    textvariable=self.default_speed_var, width=10).grid(row=2, column=1, sticky=tk.W, padx=5, pady=5)

        # Default max items
        ttk.Label(form_frame, text="Varsayılan Maksimum Öğe:").grid(row=3, column=0, sticky=tk.W, pady=5)
        self.default_max_items_var = tk.StringVar()
        ttk.Spinbox(form_frame, from_=1, to=20, textvariable=self.default_max_items_var, width=10).grid(row=3, column=1,
                                                                                                        sticky=tk.W,
                                                                                                        padx=5, pady=5)

        # Save button
        ttk.Button(form_frame, text="Ayarları Kaydet", command=self.save_settings).grid(row=4, column=0, columnspan=2,
                                                                                        pady=20)

        # Load current settings
        self.load_settings()

    def load_levels(self):
        """Load levels from database into the treeview."""
        # Clear existing items
        for item in self.level_tree.get_children():
            self.level_tree.delete(item)

        # Load from database
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        cursor.execute('''
                       SELECT level_number,
                              level_name,
                              level_description,
                              wrong_answer_percentage,
                              item_speed,
                              max_items_on_screen
                       FROM levels
                       ORDER BY level_number
                       ''')

        for row in cursor.fetchall():
            self.level_tree.insert("", tk.END, values=row)

        # Update level combobox in expressions tab
        self.update_level_combobox()

        conn.close()

    def update_level_combobox(self):
        """Update the level combobox with current levels."""
        levels = [self.level_tree.item(item)['values'][0] for item in self.level_tree.get_children()]
        self.level_combo['values'] = levels
        if levels:
            self.level_combo.current(0)
            self.load_expressions()

    def load_expressions(self, event=None):
        """Load expressions for the selected level."""
        # Clear existing items
        for item in self.expr_tree.get_children():
            self.expr_tree.delete(item)

        level = self.level_var.get()
        if not level:
            return

        # Load from database
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("""
                       SELECT expression,
                              CASE WHEN is_correct = 1 THEN 'Evet' ELSE 'Hayır' END as is_correct_display
                       FROM expressions e
                                JOIN levels l ON e.level_id = l.id
                       WHERE l.level_number = ?
                       ORDER BY e.id
                       """, (level,))

        for row in cursor.fetchall():
            self.expr_tree.insert("", tk.END, values=row)

        conn.close()

    def add_level(self):
        """Add a new level with default settings."""
        # Get default values from settings
        conn = sqlite3.connect(self.DB_PATH)
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM game_settings WHERE key = 'default_wrong_percentage'")
        default_wrong = int(cursor.fetchone()[0])
        cursor.execute("SELECT value FROM game_settings WHERE key = 'default_item_speed'")
        default_speed = float(cursor.fetchone()[0])
        cursor.execute("SELECT value FROM game_settings WHERE key = 'default_max_items'")
        default_max_items = int(cursor.fetchone()[0])
        conn.close()

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("Yeni Seviye Ekle")
        dialog.transient(self.root)
        dialog.grab_set()

        row = 0
        tk.Label(dialog, text="Seviye Numarası:").grid(row=row, column=0, padx=5, pady=5, sticky='e')
        level_entry = ttk.Entry(dialog)
        level_entry.grid(row=row, column=1, padx=5, pady=5, sticky='we')

        row += 1
        tk.Label(dialog, text="Seviye Adı:").grid(row=row, column=0, padx=5, pady=5, sticky='e')
        name_entry = ttk.Entry(dialog)
        name_entry.grid(row=row, column=1, padx=5, pady=5, sticky='we')

        row += 1
        tk.Label(dialog, text="Açıklama:").grid(row=row, column=0, padx=5, pady=5, sticky='ne')
        desc_entry = tk.Text(dialog, height=4, width=30)
        desc_entry.grid(row=row, column=1, padx=5, pady=5, sticky='we')

        row += 1
        tk.Label(dialog, text="Yanlış Cevap Yüzdesi (0-100):").grid(row=row, column=0, padx=5, pady=5, sticky='e')
        wrong_entry = ttk.Entry(dialog)
        wrong_entry.insert(0, str(default_wrong))
        wrong_entry.grid(row=row, column=1, padx=5, pady=5, sticky='we')

        row += 1
        tk.Label(dialog, text="Öğe Hızı:").grid(row=row, column=0, padx=5, pady=5, sticky='e')
        speed_entry = ttk.Entry(dialog)
        speed_entry.insert(0, str(default_speed))
        speed_entry.grid(row=row, column=1, padx=5, pady=5, sticky='we')

        row += 1
        tk.Label(dialog, text="Maksimum Öğe Sayısı:").grid(row=row, column=0, padx=5, pady=5, sticky='e')
        max_items_entry = ttk.Entry(dialog)
        max_items_entry.insert(0, str(default_max_items))
        max_items_entry.grid(row=row, column=1, padx=5, pady=5, sticky='we')

        def save():
            try:
                level_number = int(level_entry.get())
                level_name = name_entry.get().strip()
                level_description = desc_entry.get("1.0", tk.END).strip()
                wrong_percentage = float(wrong_entry.get())
                item_speed = float(speed_entry.get())
                max_items = int(max_items_entry.get())

                if not level_name:
                    messagebox.showerror("Hata", "Lütfen bir seviye adı girin!")
                    return

                if not (0 <= wrong_percentage <= 100):
                    messagebox.showerror("Hata", "Yanlış cevap yüzdesi 0-100 arasında olmalıdır!")
                    return

                conn = sqlite3.connect(self.DB_PATH)
                cursor = conn.cursor()
                cursor.execute('''
                               INSERT INTO levels (level_number, level_name, level_description, wrong_answer_percentage,
                                                   item_speed, max_items_on_screen)
                               VALUES (?, ?, ?, ?, ?, ?)
                               ''',
                               (level_number, level_name, level_description, wrong_percentage, item_speed, max_items))
                conn.commit()
                conn.close()

                self.load_levels()
                dialog.destroy()
                messagebox.showinfo("Başarılı", "Seviye başarıyla eklendi.")
            except sqlite3.IntegrityError:
                messagebox.showerror("Hata", "Bu seviye numarası zaten mevcut!")
            except ValueError as ve:
                messagebox.showerror("Hata", f"Geçersiz değer: {str(ve)}")
            except Exception as e:
                messagebox.showerror("Hata", f"Bir hata oluştu: {str(e)}")

        ttk.Button(dialog, text="Kaydet", command=save).grid(row=row + 1, column=0, columnspan=2, pady=10)

        dialog.columnconfigure(1, weight=1)

    def edit_level(self):
        """Edit the selected level."""
        selected = self.level_tree.selection()
        if not selected:
            messagebox.showwarning("Uyarı", "Lütfen düzenlemek için bir seviye seçin.")
            return

        level_data = self.level_tree.item(selected[0])['values']
        level_number = level_data[0]
        level_name = level_data[1]
        level_description = level_data[2]

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"Seviye {level_number} Düzenle")
        dialog.transient(self.root)
        dialog.grab_set()

        row = 0
        tk.Label(dialog, text="Seviye Adı:").grid(row=row, column=0, padx=5, pady=5, sticky='e')
        name_entry = ttk.Entry(dialog)
        name_entry.insert(0, level_name)
        name_entry.grid(row=row, column=1, padx=5, pady=5, sticky='we')

        row += 1
        tk.Label(dialog, text="Açıklama:").grid(row=row, column=0, padx=5, pady=5, sticky='ne')
        desc_entry = tk.Text(dialog, height=4, width=30)
        desc_entry.insert("1.0", level_description)
        desc_entry.grid(row=row, column=1, padx=5, pady=5, sticky='we')

        row += 1
        tk.Label(dialog, text="Yanlış Cevap Yüzdesi (0-100):").grid(row=row, column=0, padx=5, pady=5, sticky='e')
        wrong_entry = ttk.Entry(dialog)
        wrong_entry.insert(0, str(level_data[3]))
        wrong_entry.grid(row=row, column=1, padx=5, pady=5, sticky='we')

        row += 1
        tk.Label(dialog, text="Öğe Hızı:").grid(row=row, column=0, padx=5, pady=5, sticky='e')
        speed_entry = ttk.Entry(dialog)
        speed_entry.insert(0, str(level_data[4]))
        speed_entry.grid(row=row, column=1, padx=5, pady=5, sticky='we')

        row += 1
        tk.Label(dialog, text="Maksimum Öğe Sayısı:").grid(row=row, column=0, padx=5, pady=5, sticky='e')
        max_items_entry = ttk.Entry(dialog)
        max_items_entry.insert(0, str(level_data[5]))
        max_items_entry.grid(row=row, column=1, padx=5, pady=5, sticky='we')

        def save():
            try:
                level_name = name_entry.get().strip()
                level_description = desc_entry.get("1.0", tk.END).strip()
                wrong_percentage = float(wrong_entry.get())
                item_speed = float(speed_entry.get())
                max_items = int(max_items_entry.get())

                if not level_name:
                    messagebox.showerror("Hata", "Lütfen bir seviye adı girin!")
                    return

                if not (0 <= wrong_percentage <= 100):
                    messagebox.showerror("Hata", "Yanlış cevap yüzdesi 0-100 arasında olmalıdır!")
                    return

                conn = sqlite3.connect(self.DB_PATH)
                cursor = conn.cursor()
                cursor.execute('''
                               UPDATE levels
                               SET level_name              = ?,
                                   level_description       = ?,
                                   wrong_answer_percentage = ?,
                                   item_speed              = ?,
                                   max_items_on_screen     = ?
                               WHERE level_number = ?
                               ''',
                               (level_name, level_description, wrong_percentage, item_speed, max_items, level_number))
                conn.commit()
                conn.close()

                self.load_levels()
                dialog.destroy()
                messagebox.showinfo("Başarılı", "Seviye başarıyla güncellendi.")
            except ValueError as ve:
                messagebox.showerror("Hata", f"Geçersiz değer: {str(ve)}")
            except Exception as e:
                messagebox.showerror("Hata", f"Bir hata oluştu: {str(e)}")

        ttk.Button(dialog, text="Kaydet", command=save).grid(row=row + 1, column=0, columnspan=2, pady=10)

        dialog.columnconfigure(1, weight=1)

    def delete_level(self):
        """Delete the selected level."""
        selected = self.level_tree.selection()
        if not selected:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir seviye seçin.")
            return

        level_num = self.level_tree.item(selected[0])['values'][0]

        if messagebox.askyesno("Onay", f"{level_num}. seviyeyi ve tüm ifadelerini silmek istediğinize emin misiniz?"):
            try:
                conn = sqlite3.connect(self.DB_PATH)
                cursor = conn.cursor()

                # Get level ID first
                cursor.execute("SELECT id FROM levels WHERE level_number = ?", (level_num,))
                level_id = cursor.fetchone()[0]

                # Delete expressions first (due to foreign key constraint)
                cursor.execute("DELETE FROM expressions WHERE level_id = ?", (level_id,))
                # Then delete the level
                cursor.execute("DELETE FROM levels WHERE id = ?", (level_id,))

                conn.commit()
                conn.close()

                self.load_levels()
                messagebox.showinfo("Başarılı", "Seviye ve bağlı ifadeler başarıyla silindi.")
            except Exception as e:
                messagebox.showerror("Hata", f"Seviye silinirken bir hata oluştu: {str(e)}")

    def add_expression(self):
        """Add a new expression to the selected level."""
        level = self.level_var.get()
        if not level:
            messagebox.showwarning("Uyarı", "Lütfen önce bir seviye seçin.")
            return

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title(f"İfade Ekle - Seviye {level}")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="İfade:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        expr_var = tk.StringVar()
        ttk.Entry(dialog, textvariable=expr_var, width=40).grid(row=0, column=1, padx=5, pady=5)

        is_correct_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(dialog, text="Doğru Cevap", variable=is_correct_var).grid(row=1, column=0, columnspan=2, pady=5)

        def save():
            expression = expr_var.get().strip()
            if not expression:
                messagebox.showwarning("Uyarı", "Lütfen bir ifade girin.")
                return

            try:
                conn = sqlite3.connect(self.DB_PATH)
                cursor = conn.cursor()

                # Get level ID
                cursor.execute("SELECT id FROM levels WHERE level_number = ?", (level,))
                level_id = cursor.fetchone()[0]

                # Insert expression
                cursor.execute(
                    "INSERT INTO expressions (level_id, expression, is_correct) VALUES (?, ?, ?)",
                    (level_id, expression, 1 if is_correct_var.get() else 0)
                )

                conn.commit()
                conn.close()

                self.load_expressions()
                dialog.destroy()
                messagebox.showinfo("Başarılı", "İfade başarıyla eklendi.")
            except Exception as e:
                messagebox.showerror("Hata", f"İfade eklenirken bir hata oluştu: {str(e)}")

        ttk.Button(dialog, text="Ekle", command=save).grid(row=2, column=0, columnspan=2, pady=10)
        dialog.bind("<Return>", lambda e: save())

    def edit_expression(self):
        """Edit the selected expression."""
        selected = self.expr_tree.selection()
        if not selected:
            messagebox.showwarning("Uyarı", "Lütfen düzenlemek için bir ifade seçin.")
            return

        level = self.level_var.get()
        expr_data = self.expr_tree.item(selected[0])['values']
        old_expression = expr_data[0]
        is_correct = expr_data[1] == 'Evet'

        # Create dialog
        dialog = tk.Toplevel(self.root)
        dialog.title("İfade Düzenle")
        dialog.transient(self.root)
        dialog.grab_set()

        ttk.Label(dialog, text="İfade:").grid(row=0, column=0, padx=5, pady=5, sticky=tk.W)
        expr_var = tk.StringVar(value=old_expression)
        ttk.Entry(dialog, textvariable=expr_var, width=40).grid(row=0, column=1, padx=5, pady=5)

        is_correct_var = tk.BooleanVar(value=is_correct)
        ttk.Checkbutton(dialog, text="Doğru Cevap", variable=is_correct_var).grid(row=1, column=0, columnspan=2, pady=5)

        def save():
            new_expression = expr_var.get().strip()
            if not new_expression:
                messagebox.showwarning("Uyarı", "Lütfen bir ifade girin.")
                return

            try:
                conn = sqlite3.connect(self.DB_PATH)
                cursor = conn.cursor()

                # Update expression
                cursor.execute(
                    "UPDATE expressions SET expression = ?, is_correct = ? "
                    "WHERE id = (SELECT e.id FROM expressions e "
                    "JOIN levels l ON e.level_id = l.id "
                    "WHERE l.level_number = ? AND e.expression = ? LIMIT 1)",
                    (new_expression, 1 if is_correct_var.get() else 0, level, old_expression)
                )

                conn.commit()
                conn.close()

                self.load_expressions()
                dialog.destroy()
                messagebox.showinfo("Başarılı", "İfade başarıyla güncellendi.")
            except Exception as e:
                messagebox.showerror("Hata", f"İfade güncellenirken bir hata oluştu: {str(e)}")

        ttk.Button(dialog, text="Kaydet", command=save).grid(row=2, column=0, columnspan=2, pady=10)
        dialog.bind("<Return>", lambda e: save())

    def delete_expression(self):
        """Delete the selected expression."""
        selected = self.expr_tree.selection()
        if not selected:
            messagebox.showwarning("Uyarı", "Lütfen silmek için bir ifade seçin.")
            return

        level = self.level_var.get()
        expression = self.expr_tree.item(selected[0])['values'][0]

        if messagebox.askyesno("Onay", f"'{expression}' ifadesini silmek istediğinize emin misiniz?"):
            try:
                conn = sqlite3.connect(self.DB_PATH)
                cursor = conn.cursor()

                cursor.execute(
                    "DELETE FROM expressions WHERE id = ("
                    "SELECT e.id FROM expressions e "
                    "JOIN levels l ON e.level_id = l.id "
                    "WHERE l.level_number = ? AND e.expression = ? LIMIT 1"
                    ")",
                    (level, expression)
                )

                conn.commit()
                conn.close()

                self.load_expressions()
                messagebox.showinfo("Başarılı", "İfade başarıyla silindi.")
            except Exception as e:
                messagebox.showerror("Hata", f"İfade silinirken bir hata oluştu: {str(e)}")

    def load_settings(self):
        """Load settings from the database."""
        try:
            conn = sqlite3.connect(self.DB_PATH)
            cursor = conn.cursor()

            cursor.execute("SELECT key, value FROM game_settings")
            settings = {row[0]: row[1] for row in cursor.fetchall()}

            self.total_levels_var.set(settings.get('total_levels', '10'))
            self.default_wrong_var.set(settings.get('default_wrong_percentage', '20'))
            self.default_speed_var.set(settings.get('default_item_speed', '2.0'))
            self.default_max_items_var.set(settings.get('default_max_items', '5'))

            conn.close()
        except Exception as e:
            messagebox.showerror("Hata", f"Ayarlar yüklenirken bir hata oluştu: {str(e)}")

    def save_settings(self):
        """Save settings to the database."""
        try:
            total_levels = int(self.total_levels_var.get())
            wrong_pct = int(self.default_wrong_var.get())
            speed = float(self.default_speed_var.get())
            max_items = int(self.default_max_items_var.get())

            if total_levels <= 0:
                raise ValueError("Toplam seviye sayısı pozitif bir değer olmalıdır.")
            if not (0 <= wrong_pct <= 100):
                raise ValueError("Varsayılan yanlış yüzdesi 0-100 arasında olmalıdır.")
            if speed <= 0:
                raise ValueError("Varsayılan hız pozitif bir değer olmalıdır.")
            if max_items <= 0:
                raise ValueError("Varsayılan maksimum öğe sayısı pozitif bir değer olmalıdır.")

            conn = sqlite3.connect(self.DB_PATH)
            cursor = conn.cursor()

            cursor.execute(
                "INSERT OR REPLACE INTO game_settings (key, value) VALUES (?, ?)",
                ('total_levels', str(total_levels))
            )
            cursor.execute(
                "INSERT OR REPLACE INTO game_settings (key, value) VALUES (?, ?)",
                ('default_wrong_percentage', str(wrong_pct))
            )
            cursor.execute(
                "INSERT OR REPLACE INTO game_settings (key, value) VALUES (?, ?)",
                ('default_item_speed', str(speed))
            )
            cursor.execute(
                "INSERT OR REPLACE INTO game_settings (key, value) VALUES (?, ?)",
                ('default_max_items', str(max_items))
            )

            conn.commit()
            conn.close()

            messagebox.showinfo("Başarılı", "Ayarlar başarıyla kaydedildi.")
        except ValueError as e:
            messagebox.showerror("Hata", str(e))
        except Exception as e:
            messagebox.showerror("Hata", f"Ayarlar kaydedilirken bir hata oluştu: {str(e)}")


if __name__ == "__main__":
    root = tk.Tk()
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'game_data.db')
    db_manager = DatabaseManager(db_path)

#    app = LevelEditor(root, DB_PATH=db_path)
    app = MainWindow(root, db_manager)
    root.mainloop()
