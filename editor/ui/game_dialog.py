import tkinter as tk
from tkinter import ttk
from typing import Optional

class GameDialog:
    def __init__(self, parent, title: str = "Yeni Oyun", game_name: Optional[str] = None, game_description: Optional[str] = None):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.transient(parent)
        self.top.grab_set()
        self.top.resizable(False, False)
        self.result = None

        main_frame = ttk.Frame(self.top, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Oyun Adı:").pack(padx=10, pady=(10, 2), anchor=tk.W)
        self.name_var = tk.StringVar(value=game_name or "")
        self.name_entry = ttk.Entry(main_frame, textvariable=self.name_var, width=50)
        self.name_entry.pack(padx=10, pady=(0, 10), fill=tk.X)
        self.name_entry.focus()

        ttk.Label(main_frame, text="Oyun Açıklaması:").pack(padx=10, pady=(0, 2), anchor=tk.W)
        self.desc_text = tk.Text(main_frame, height=5, width=50)
        self.desc_text.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)
        if game_description:
            self.desc_text.insert("1.0", game_description)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(5, 0), fill=tk.X)
        
        # Add a spacer to push buttons to the right
        spacer = ttk.Frame(button_frame)
        spacer.pack(side=tk.LEFT, expand=True)

        action_text = "Güncelle" if game_name else "Ekle"
        self.ok_button = ttk.Button(button_frame, text=action_text, command=self._on_ok)
        self.ok_button.pack(side=tk.LEFT, padx=5)
        
        self.cancel_button = ttk.Button(button_frame, text="İptal", command=self._on_cancel)
        self.cancel_button.pack(side=tk.LEFT)

        self.top.bind("<Return>", lambda e: self._on_ok())
        self.top.bind("<Escape>", lambda e: self._on_cancel())
        
        # Center the window
        self.top.update_idletasks()
        parent_x = parent.winfo_rootx()
        parent_y = parent.winfo_rooty()
        parent_width = parent.winfo_width()
        parent_height = parent.winfo_height()
        dialog_width = self.top.winfo_width()
        dialog_height = self.top.winfo_height()
        
        x = parent_x + (parent_width - dialog_width) // 2
        y = parent_y + (parent_height - dialog_height) // 2
        self.top.geometry(f"+{x}+{y}")


    def _on_ok(self, event=None):
        name = self.name_var.get().strip()
        desc = self.desc_text.get("1.0", tk.END).strip()
        if name:
            self.result = (name, desc)
            self.top.destroy()
        else:
            self.name_entry.focus_set()

    def _on_cancel(self, event=None):
        self.result = None
        self.top.destroy()

    def show(self):
        self.top.wait_window()
        return self.result
