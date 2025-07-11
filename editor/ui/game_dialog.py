import tkinter as tk
from tkinter import ttk

class GameDialog:
    def __init__(self, parent, title="Yeni Oyun Ekle"):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.transient(parent)
        self.top.grab_set()
        self.result = None

        ttk.Label(self.top, text="Oyun Adı:").pack(padx=10, pady=(10, 2), anchor=tk.W)
        self.name_var = tk.StringVar()
        self.name_entry = ttk.Entry(self.top, textvariable=self.name_var, width=40)
        self.name_entry.pack(padx=10, pady=(0, 10), fill=tk.X)
        self.name_entry.focus()

        ttk.Label(self.top, text="Oyun Açıklaması:").pack(padx=10, pady=(0, 2), anchor=tk.W)
        self.desc_text = tk.Text(self.top, height=4, width=40)
        self.desc_text.pack(padx=10, pady=(0, 10), fill=tk.X)

        button_frame = ttk.Frame(self.top)
        button_frame.pack(pady=(0, 10))

        ttk.Button(button_frame, text="Ekle", command=self._on_ok).pack(side=tk.LEFT, padx=5)
        ttk.Button(button_frame, text="İptal", command=self._on_cancel).pack(side=tk.LEFT, padx=5)

        self.top.bind("<Return>", lambda e: self._on_ok())
        self.top.bind("<Escape>", lambda e: self._on_cancel())

    def _on_ok(self):
        name = self.name_var.get().strip()
        desc = self.desc_text.get("1.0", tk.END).strip()
        if name:
            self.result = (name, desc)
            self.top.destroy()
        else:
            self.name_entry.focus_set()

    def _on_cancel(self):
        self.result = None
        self.top.destroy()

    def show(self):
        self.top.wait_window()
        return self.result
