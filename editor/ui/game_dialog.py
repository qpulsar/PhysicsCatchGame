import tkinter as tk
from tkinter import ttk
from typing import Optional, List, Dict, Any

class GameDialog:
    def __init__(self, parent, title: str = "Yeni Oyun", game_name: Optional[str] = None, game_description: Optional[str] = None, templates: Optional[List[Dict[str, str]]] = None):
        self.top = tk.Toplevel(parent)
        self.top.title(title)
        self.top.transient(parent)
        self.top.grab_set()
        self.top.resizable(False, False)
        self.result = None
        self.templates = templates or []

        main_frame = ttk.Frame(self.top, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        # Oyun Adı
        ttk.Label(main_frame, text="Oyun Adı:", font=("Segoe UI", 9, "bold")).pack(padx=10, pady=(5, 2), anchor=tk.W)
        self.name_var = tk.StringVar(value=game_name or "")
        self.name_entry = ttk.Entry(main_frame, textvariable=self.name_var, width=50)
        self.name_entry.pack(padx=10, pady=(0, 10), fill=tk.X)
        self.name_entry.focus()

        # Şablon Seçimi (Sadece yeni oyun eklenirken gösterilir)
        self.template_var = tk.StringVar(value="blank")
        if self.templates and not game_name:
            ttk.Label(main_frame, text="Oyun Şablonu:", font=("Segoe UI", 9, "bold")).pack(padx=10, pady=(5, 2), anchor=tk.W)
            
            # Combobox için isim listesi oluştur
            template_names = [t["name"] for t in self.templates]
            self.template_combo = ttk.Combobox(main_frame, values=template_names, state="readonly")
            
            # Varsayılan olarak "Boş Oyun" veya ilk şablonu seç
            if template_names:
                self.template_combo.current(0)
            
            self.template_combo.pack(padx=10, pady=(0, 10), fill=tk.X)
            
            # Açıklama alanı (Seçilen şablonun açıklamasını gösterir)
            self.template_desc_label = ttk.Label(main_frame, text="", wraplength=350, foreground="#888")
            self.template_desc_label.pack(padx=10, pady=(0, 10), anchor=tk.W)
            
            def _on_template_select(event):
                idx = self.template_combo.current()
                if idx >= 0:
                    t = self.templates[idx]
                    self.template_var.set(t["id"])
                    self.template_desc_label.config(text=t.get("description", ""))

            self.template_combo.bind("<<ComboboxSelected>>", _on_template_select)
            # İlk durumu ayarla
            _on_template_select(None)

        # Oyun Açıklaması
        ttk.Label(main_frame, text="Oyun Açıklaması:", font=("Segoe UI", 9, "bold")).pack(padx=10, pady=(5, 2), anchor=tk.W)
        self.desc_text = tk.Text(main_frame, height=4, width=50, font=("Segoe UI", 9))
        self.desc_text.pack(padx=10, pady=(0, 10), fill=tk.BOTH, expand=True)
        if game_description:
            self.desc_text.insert("1.0", game_description)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(pady=(10, 0), fill=tk.X)
        
        spacer = ttk.Frame(button_frame)
        spacer.pack(side=tk.LEFT, expand=True)

        action_text = "Güncelle" if game_name else "Ekle"
        self.ok_button = ttk.Button(button_frame, text=action_text, command=self._on_ok, style="Accent.TButton")
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
        template_id = self.template_var.get()
        if name:
            self.result = (name, desc, template_id)
            self.top.destroy()
        else:
            self.name_entry.focus_set()

    def _on_cancel(self, event=None):
        self.result = None
        self.top.destroy()

    def show(self):
        self.top.wait_window()
        return self.result

class TemplateSelectorDialog:
    """Dialog to select a template for editing."""
    def __init__(self, parent, templates: List[Dict[str, Any]]):
        self.top = tk.Toplevel(parent)
        self.top.title("Şablon Seç")
        self.top.transient(parent)
        self.top.grab_set()
        self.top.resizable(False, False)
        self.result = None
        self.templates = templates

        main_frame = ttk.Frame(self.top, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)

        ttk.Label(main_frame, text="Düzenlemek istediğiniz şablonu seçin:", font=("Segoe UI", 9, "bold")).pack(padx=10, pady=(5, 10), anchor=tk.W)

        template_names = [t["name"] for t in self.templates]
        self.template_combo = ttk.Combobox(main_frame, values=template_names, state="readonly", width=40)
        if template_names:
            self.template_combo.current(0)
        self.template_combo.pack(padx=10, pady=(0, 10), fill=tk.X)

        self.desc_label = ttk.Label(main_frame, text="", wraplength=350, foreground="#888")
        self.desc_label.pack(padx=10, pady=(0, 10), anchor=tk.W)

        def _on_select(event):
            idx = self.template_combo.current()
            if idx >= 0:
                self.desc_label.config(text=self.templates[idx].get("description", ""))
        
        self.template_combo.bind("<<ComboboxSelected>>", _on_select)
        _on_select(None)

        btn_frame = ttk.Frame(main_frame)
        btn_frame.pack(pady=(10, 0), fill=tk.X)
        
        ttk.Button(btn_frame, text="Düzenle", command=self._on_ok, style="Accent.TButton").pack(side=tk.RIGHT, padx=5)
        ttk.Button(btn_frame, text="İptal", command=self.top.destroy).pack(side=tk.RIGHT)

    def _on_ok(self):
        idx = self.template_combo.current()
        if idx >= 0:
            self.result = self.templates[idx]
            self.top.destroy()

    def show(self):
        self.top.wait_window()
        return self.result
