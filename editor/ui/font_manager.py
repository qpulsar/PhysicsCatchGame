import os
import tkinter as tk
from tkinter import ttk, colorchooser
from PIL import Image, ImageTk, ImageDraw
import pygame

class FontManagerWindow(tk.Toplevel):
    """Font seçimi ve önizlemesi için Toplevel pencere."""
    
    def __init__(self, parent, font_dir: str, on_select_callback=None):
        super().__init__(parent)
        self.title("Font Yöneticisi")
        self.geometry("600x700")
        self.transient(parent)
        
        if on_select_callback:
            self.grab_set()
        
        self.font_dir = font_dir
        self.on_select = on_select_callback
        self.selected_font = None
        
        # Önizleme Değişkenleri
        self.preview_size_var = tk.IntVar(value=36)
        self.preview_color_var = tk.StringVar(value="#FFFFFF")
        self.preview_theme_var = tk.StringVar(value="dark") # dark veya light
        
        # Pygame init
        if not pygame.get_init():
            pygame.init()
        if not pygame.font.get_init():
            pygame.font.init()

        self._build_ui()
        self._refresh_list()

    def _build_ui(self):
        main_frame = ttk.Frame(self, padding=15)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # 1. Liste Kısmı
        list_group = ttk.LabelFrame(main_frame, text="Mevcut Fontlar (Seçmek için Çift Tıkla)", padding=5)
        list_group.pack(fill=tk.BOTH, expand=True, pady=(0, 10))

        self.listbox = tk.Listbox(list_group, font=("Segoe UI", 11), background="#2b2b2b", 
                                  foreground="white", selectbackground="#4b6eaf", borderwidth=0, highlightthickness=0)
        self.listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        scrollbar = ttk.Scrollbar(list_group, orient="vertical", command=self.listbox.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.listbox.configure(yscrollcommand=scrollbar.set)
        
        self.listbox.bind("<<ListboxSelect>>", self._on_list_select)
        self.listbox.bind("<Double-Button-1>", lambda e: self._confirm_selection())

        # 2. Kontrol Paneli
        ctrl_frame = ttk.LabelFrame(main_frame, text="Önizleme Ayarları", padding=10)
        ctrl_frame.pack(fill=tk.X, pady=(0, 10))
        
        # Boyut
        ttk.Label(ctrl_frame, text="Boyut:").grid(row=0, column=0, padx=5, sticky="w")
        size_scale = ttk.Scale(ctrl_frame, from_=10, to=120, variable=self.preview_size_var, orient=tk.HORIZONTAL, command=lambda e: self._refresh_preview())
        size_scale.grid(row=0, column=1, sticky="ew", padx=5)
        ttk.Label(ctrl_frame, textvariable=self.preview_size_var).grid(row=0, column=2, padx=5)
        
        # Renk
        ttk.Label(ctrl_frame, text="Renk:").grid(row=1, column=0, padx=5, sticky="w", pady=5)
        self.color_btn = tk.Button(ctrl_frame, text="Renk Seç", bg=self.preview_color_var.get(), command=self._pick_color)
        self.color_btn.grid(row=1, column=1, sticky="w", padx=5, pady=5)
        
        # Tema (Koyu/Açık)
        ttk.Label(ctrl_frame, text="Tema:").grid(row=1, column=2, padx=5, sticky="e")
        theme_combo = ttk.Combobox(ctrl_frame, textvariable=self.preview_theme_var, values=["dark", "light"], state="readonly", width=8)
        theme_combo.grid(row=1, column=3, padx=5)
        theme_combo.bind("<<ComboboxSelected>>", lambda e: self._refresh_preview())

        ctrl_frame.columnconfigure(1, weight=1)

        # 3. Önizleme Alanı
        preview_group = ttk.LabelFrame(main_frame, text="Font Görünümü", padding=5)
        preview_group.pack(fill=tk.X, pady=5)
        
        # Canvas yüksekliğini artırdım ve daha belirgin yaptım
        self.preview_canvas = tk.Canvas(preview_group, height=200, bg="#1a1a1a", highlightthickness=1, highlightbackground="#444")
        self.preview_canvas.pack(fill=tk.X)
        
        # 4. Kapat Butonu
        ttk.Button(main_frame, text="Kapat", command=self.destroy).pack(side=tk.BOTTOM, pady=5, fill=tk.X)

    def _refresh_list(self):
        self.listbox.delete(0, tk.END)
        if not os.path.exists(self.font_dir):
            return
            
        fonts = [f for f in os.listdir(self.font_dir) if f.lower().endswith(".ttf")]
        for f in sorted(fonts):
            self.listbox.insert(tk.END, f)

    def _on_list_select(self, event):
        sel = self.listbox.curselection()
        if not sel:
            return
        
        self.selected_font = self.listbox.get(sel[0])
        self._refresh_preview()

    def _pick_color(self):
        color = colorchooser.askcolor(title="Metin Rengi", initialcolor=self.preview_color_var.get())[1]
        if color:
            self.preview_color_var.set(color)
            self.color_btn.config(bg=color)
            self._refresh_preview()

    def _refresh_preview(self):
        if not self.selected_font:
            return
        self._update_preview(self.selected_font)

    def _create_gradient(self, width, height, theme="dark"):
        """Gradiyent arkaplan oluşturur."""
        base = Image.new('RGB', (width, height), (30, 30, 30) if theme=="dark" else (220, 220, 220))
        top_color = (40, 44, 52) if theme=="dark" else (240, 240, 245)
        bottom_color = (20, 20, 25) if theme=="dark" else (200, 200, 210)
        
        draw = ImageDraw.Draw(base)
        for y in range(height):
            r = int(top_color[0] + (bottom_color[0] - top_color[0]) * (y / height))
            g = int(top_color[1] + (bottom_color[1] - top_color[1]) * (y / height))
            b = int(top_color[2] + (bottom_color[2] - top_color[2]) * (y / height))
            draw.line([(0, y), (width, y)], fill=(r, g, b))
        return base

    def _update_preview(self, font_file):
        """Fontu render eder ve gradiyent arkaplan üzerinde gösterir.
        
        Gerçekçi boyut için 1:1 render yapar, stretch yapmaz.
        """
        path = os.path.join(self.font_dir, font_file)
        try:
            # Canvas boyutları
            self.update_idletasks()
            cw = self.preview_canvas.winfo_width()
            ch = self.preview_canvas.winfo_height()
            if cw < 10: cw = 570
            if ch < 10: ch = 200

            # 1. Gradiyent Arkaplan
            theme = self.preview_theme_var.get()
            bg_img = self._create_gradient(cw, ch, theme)
            
            # 2. Font Render (Pygame)
            # Türkçe karakter desteği için kapsamlı test metni (Pangram + Alfabe)
            text = "Pijamalı hasta, yağız şoföre çabucak güvendi.\nABCÇDEFGĞHIİJKLMNOÖPRSŞTUÜVYZ\nabcçdefgğhıijklmnoöprsştuüvyz\n0123456789 !?*+-"
            
            size = self.preview_size_var.get()
            color_hex = self.preview_color_var.get()
            rgb = tuple(int(color_hex.lstrip('#')[i:i+2], 16) for i in (0, 2, 4))
            
            pg_font = pygame.font.Font(path, size)
            
            # Satır satır render (Çok satırlı destek için)
            lines = text.split('\n')
            y_offset = 20
            
            for line in lines:
                if not line.strip(): continue
                surf = pg_font.render(line, True, rgb)
                
                # Surface -> PIL (RGBA)
                data_rgba = pygame.image.tostring(surf, "RGBA")
                txt_img_rgba = Image.frombytes("RGBA", surf.get_size(), data_rgba)
                
                tw, th = txt_img_rgba.size
                
                # STRETCH YAPMA: Eğer çok genişse sadece kırp (clip), boyutla oynama.
                # Böylece kullanıcı gerçek boyutu görür.
                paste_x = (cw - tw) // 2
                if paste_x < 10: paste_x = 10 # Sola yasla eğer sığmıyorsa
                
                bg_img.paste(txt_img_rgba, (paste_x, y_offset), txt_img_rgba)
                y_offset += th + 5
                
                # Eğer canvas boyunu aştıysak dur
                if y_offset > ch - 20:
                    break
            
            photo = ImageTk.PhotoImage(bg_img)
            self.preview_canvas.delete("all")
            self.preview_canvas.create_image(0, 0, anchor="nw", image=photo)
            self.tk_preview = photo 
            
        except Exception as e:
            self.preview_canvas.delete("all")
            cw_err = self.preview_canvas.winfo_width() or 300
            ch_err = self.preview_canvas.winfo_height() or 100
            self.preview_canvas.create_text(cw_err//2, ch_err//2, text=f"Önizleme Hatası: {e}", fill="red")

    def _confirm_selection(self):
        if self.selected_font and self.on_select:
            self.on_select(self.selected_font)
            self.destroy()
        else:
            # Sadece kapat
            self.destroy()
