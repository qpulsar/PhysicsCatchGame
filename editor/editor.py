import tkinter as tk
from tkinter import ttk
import os
import sys

from editor.utils import get_project_root
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

    project_root = get_project_root()
    if project_root not in sys.path:
        sys.path.insert(0, project_root)
        
    db_path = os.path.join(project_root, 'game_data.db')
    db_manager = DatabaseManager(db_path)

    app = MainWindow(root, db_manager)
    root.mainloop()
