import tkinter as tk
from tkinter import ttk
import os
import sys

# Add the parent directory to the path so we can import from the editor package
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from editor.database.database import DatabaseManager
from editor.ui.main_window import MainWindow

if __name__ == "__main__":
    root = tk.Tk()

    # sv-ttk temasını uygula (daha modern bir görünüm için)
    try:
        import sv_ttk
        # Temayı "light" veya "dark" olarak ayarlayabilirsiniz
        sv_ttk.set_theme("light")
    except ImportError:
        # sv-ttk yüklü değilse, standart bir temaya geri dön
        print("sv-ttk kütüphanesi bulunamadı. Standart tema kullanılacak.")
        style = ttk.Style(root)
        if "clam" in style.theme_names():
            style.theme_use("clam")

    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'game_data.db')
    db_manager = DatabaseManager(db_path)

    #    app = LevelEditor(root, DB_PATH=db_path)
    app = MainWindow(root, db_manager)
    root.mainloop()
