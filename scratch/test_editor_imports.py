import sys
import os
sys.path.insert(0, os.path.abspath("."))
try:
    import tkinter as tk
    from editor.database.database import DatabaseManager
    from editor.ui.main_window import MainWindow
    import sv_ttk
    print("Editor imports successful!")
except Exception as e:
    print(f"Editor imports failed: {e}")
    sys.exit(1)
