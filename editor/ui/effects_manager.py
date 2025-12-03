"""Effect yöneticisi penceresi (oyundan bağımsız).

Bu pencere, bir sprite sheet üzerinde ardışık oynatılacak efekt karelerini
(bölgeler) seçmenize ve sıralamanıza izin verir. Sprite yöneticisine benzer
bir arayüz sağlar; fark olarak kareler bir sırada oynatılır ve oynatma
önizlemesi bulunur.

Not: DB şeması onayı alınmadan veri tabanına yazma yapılmaz. Kaydet butonu
şema onayı sonrası ilgili servise bağlanacak şekilde tasarlanmıştır.
"""
from __future__ import annotations

import os
import json
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List, Optional, Tuple

from PIL import Image, ImageTk


class EffectsManagerWindow(tk.Toplevel):
    """Efekt yönetimi için bağımsız Toplevel pencere.

    Attributes:
        frames: Seçilen karelerin listesi [{'x','y','w','h'}].
    """

    def __init__(self, parent: tk.Tk, effect_service=None, game_id: int = 0):
        """Pencereyi oluşturur ve UI bileşenlerini yerleştirir.

        Args:
            parent: Üst Tk penceresi
            effect_service: Efekt servis örneği
            game_id: Opsiyonel oyun ID (Varsayılan 0 = Global)
        """
        super().__init__(parent)
        self.effect_service = effect_service
        self.game_id = 0 # Force Global ID for effects
        self.title("Effect Yöneticisi (Global)")
        self.geometry("1200x800")
        self.transient(parent)

        # Proje kökü (assets için)
        self._project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        self._assets_root = os.path.join(self._project_root, "assets")

        # Durum
        self.frames: List[dict] = []
        self._current_image_path: Optional[str] = None
        self._pil_image: Optional[Image.Image] = None
        self._tk_image: Optional[ImageTk.PhotoImage] = None
        self._scale: float = 1.0
        self._sel_start: Optional[Tuple[int, int]] = None
        self._sel_rect_id: Optional[int] = None
        self._current_effect_id: Optional[int] = None  # Düzenlenen efektin ID'si

        # Grid / Kılavuz Modu Değişkenleri
        self._grid_mode = False
        self._grid_xs: List[int] = []  # Dikey çizgi X koordinatları (Image space)
        self._grid_ys: List[int] = []  # Yatay çizgi Y koordinatları (Image space)
        self._drag_line: Optional[Tuple[str, int]] = None  # ('x', index) veya ('y', index)
        self._hover_line: Optional[Tuple[str, int]] = None

        self._build_ui()
        self._refresh_effects_list()

    def _build_ui(self) -> None:
        """UI iskeletini kurar: Sol (Liste), Orta (Kareler), Sağ (Canvas)."""
        main_frame = ttk.Frame(self)
        main_frame.pack(fill=tk.BOTH, expand=True)

        # --- Üst Araç Çubuğu ---
        toolbar = ttk.Frame(main_frame, padding=4)
        toolbar.pack(fill=tk.X, side=tk.TOP)
        
        ttk.Label(toolbar, text="Efekt Adı:").pack(side=tk.LEFT)
        self.effect_name_var = tk.StringVar(value="New Effect")
        ttk.Entry(toolbar, textvariable=self.effect_name_var, width=24).pack(side=tk.LEFT, padx=4)
        
        ttk.Button(toolbar, text="Yeni Efekt", command=self._new_effect).pack(side=tk.LEFT, padx=10)
        ttk.Button(toolbar, text="Kaydet / Güncelle", command=self._save_effect).pack(side=tk.LEFT, padx=4)
        
        ttk.Separator(toolbar, orient=tk.VERTICAL).pack(side=tk.LEFT, fill=tk.Y, padx=10)
        ttk.Button(toolbar, text="Medya Seç...", command=self._select_media_image).pack(side=tk.LEFT, padx=4)

        # --- Ana Split (PanedWindow) ---
        self.paned = ttk.PanedWindow(main_frame, orient=tk.HORIZONTAL)
        self.paned.pack(fill=tk.BOTH, expand=True, padx=4, pady=4)

        # 1. Sol Panel: Kayıtlı Efektler Listesi
        left_panel = ttk.LabelFrame(self.paned, text="Kayıtlı Efektler", padding=4)
        self.paned.add(left_panel, weight=1)

        self.effects_tree = ttk.Treeview(left_panel, columns=("name", "type"), show="headings")
        self.effects_tree.heading("name", text="Ad")
        self.effects_tree.heading("type", text="Tip")
        self.effects_tree.column("name", width=120)
        self.effects_tree.column("type", width=80)
        self.effects_tree.pack(fill=tk.BOTH, expand=True)
        self.effects_tree.bind("<<TreeviewSelect>>", self._on_effect_select)
        
        btn_frame_left = ttk.Frame(left_panel)
        btn_frame_left.pack(fill=tk.X, pady=4)
        ttk.Button(btn_frame_left, text="Seçili Efekti Sil", command=self._delete_effect_db).pack(fill=tk.X)

        # 2. Orta Panel: Kare Listesi ve Önizleme Ayarları
        mid_panel = ttk.LabelFrame(self.paned, text="Kareler (Frames)", padding=4)
        self.paned.add(mid_panel, weight=1)
        
        self.listbox = tk.Listbox(mid_panel, height=20, selectmode=tk.EXTENDED)
        self.listbox.pack(fill=tk.BOTH, expand=True)
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._select_from_list())
        # Ctrl+A veya Command+A ile tümünü seç
        self.listbox.bind("<Control-a>", self._select_all_frames)
        self.listbox.bind("<Command-a>", self._select_all_frames) # Mac için

        mid_btns = ttk.Frame(mid_panel)
        mid_btns.pack(fill=tk.X, pady=4)
        ttk.Button(mid_btns, text="▲", width=3, command=lambda: self._move_item(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(mid_btns, text="▼", width=3, command=lambda: self._move_item(1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(mid_btns, text="Sil", command=self._delete_frame_item).pack(side=tk.RIGHT, padx=2)

        # --- Araçlar Paneli (Auto Slice & Sort) ---
        tools_frame = ttk.LabelFrame(mid_panel, text="Akıllı Araçlar", padding=4)
        tools_frame.pack(fill=tk.X, pady=4)
        
        # Grid Mode Toggle
        self.grid_btn = ttk.Button(tools_frame, text="📏 Kılavuz Modu: KAPALI", command=self._toggle_grid_mode)
        self.grid_btn.pack(fill=tk.X, pady=2)
        
        ttk.Button(tools_frame, text="↔ Aralıkları Eşitle", command=self._distribute_grid).pack(fill=tk.X, pady=2)
        ttk.Button(tools_frame, text="✅ Kılavuzdan Kare Üret", command=self._apply_grid_to_frames).pack(fill=tk.X, pady=2)
        
        # Legacy Auto Slice (Alternatif olarak kalsın mı? Yer kazanmak için kaldırabiliriz veya alta atabiliriz)
        # ttk.Button(tools_frame, text="⚡ Manuel Kesim...", command=self._open_auto_slice_dialog).pack(fill=tk.X, pady=2)
        
        # Sıralama Menüsü
        self.sort_var = tk.StringVar()
        sort_btn = ttk.Menubutton(tools_frame, text="Sırala", direction="below")
        sort_menu = tk.Menu(sort_btn, tearoff=False)
        sort_menu.add_command(label="Satır Öncelikli (Z)", command=lambda: self._sort_frames("row"))
        sort_menu.add_command(label="Sütun Öncelikli (N)", command=lambda: self._sort_frames("col"))
        sort_btn["menu"] = sort_menu
        sort_btn.pack(fill=tk.X, pady=2)

        play_frame = ttk.LabelFrame(mid_panel, text="Oynatma", padding=4)
        play_frame.pack(fill=tk.X, pady=4)
        
        ttk.Label(play_frame, text="Kare (ms):").pack(side=tk.LEFT)
        self.frame_ms_var = tk.StringVar(value="120")
        ttk.Entry(play_frame, textvariable=self.frame_ms_var, width=5).pack(side=tk.LEFT, padx=2)
        
        ttk.Button(play_frame, text="▶", width=4, command=self._preview_play).pack(side=tk.LEFT, padx=4)
        ttk.Button(play_frame, text="■", width=4, command=self._preview_stop).pack(side=tk.LEFT)

        # 3. Sağ Panel: Canvas (Sprite Sheet)
        right_panel = ttk.LabelFrame(self.paned, text="Sprite Sheet Düzenleyici", padding=4)
        self.paned.add(right_panel, weight=3)
        
        self.canvas = tk.Canvas(right_panel, bg="black")
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        self.canvas.bind("<Button-1>", self._on_canvas_down)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_up)
        # Yeni grid etkileşimleri
        self.canvas.bind("<Double-Button-1>", self._on_canvas_double_click)
        self.canvas.bind("<Button-2>", self._on_canvas_right_click) # Mac trackpad
        self.canvas.bind("<Button-3>", self._on_canvas_right_click) # Windows/Mouse sağ tık

        # Alt Durum Çubuğu
        status = ttk.Frame(self)
        status.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_var = tk.StringVar(value="Hazır")
        ttk.Label(status, textvariable=self.status_var).pack(side=tk.LEFT, padx=6)

    # --- DB İşlemleri ---

    def _refresh_effects_list(self):
        """Veritabanındaki efektleri listeye doldurur."""
        if not self.effect_service:
            return
        
        # Temizle
        for item in self.effects_tree.get_children():
            self.effects_tree.delete(item)
            
        effects = self.effect_service.get_effects(self.game_id)
        for eff in effects:
            eff_id = eff.id
            name = eff.name
            typ = eff.type
            self.effects_tree.insert("", tk.END, iid=str(eff_id), values=(name, typ))

    def _on_effect_select(self, event):
        """Listeden bir efekt seçildiğinde yükler."""
        sel = self.effects_tree.selection()
        if not sel:
            return
        
        eff_id = int(sel[0])
        self._load_effect(eff_id)

    def _load_effect(self, eff_id: int):
        """Efekt detaylarını veritabanından yükler ve arayüzü doldurur."""
        item = self.effects_tree.item(str(eff_id))
        name = item['values'][0]
        
        row = self.effect_service.get_effect(0, name)
        if not row:
            messagebox.showerror("Hata", "Efekt bulunamadı.")
            return
            
        try:
            data = json.loads(row.params_json)
            
            self._current_effect_id = eff_id
            self.effect_name_var.set(row.name)
            self.frame_ms_var.set(str(data.get('frame_ms', 120)))
            
            rel_path = data.get('image_path')
            if rel_path:
                rel_path = rel_path.replace('\\', '/')
                abs_path = os.path.join(self._project_root, rel_path)
                if os.path.exists(abs_path):
                    self._load_image(abs_path)
                else:
                    messagebox.showwarning("Uyarı", f"Görsel dosyası bulunamadı:\n{rel_path}")
            
            self.frames = data.get('frames', [])
            self._refresh_list()  # Eski metod adı _refresh_list, aşağıda duruyor.
            self._draw_overlays()
            
            self.status_var.set(f"Efekt yüklendi: {name}")
            
        except json.JSONDecodeError:
            messagebox.showerror("Hata", "Efekt verisi bozuk (JSON hatası).")
        except Exception as e:
            messagebox.showerror("Hata", f"Yükleme hatası: {e}")

    def _new_effect(self):
        """Arayüzü sıfırlar ve yeni efekt moduna geçer."""
        self._current_effect_id = None
        self.effect_name_var.set("New Effect")
        self.frames = []
        # Listede seçimi kaldır
        if self.effects_tree.selection():
            self.effects_tree.selection_remove(self.effects_tree.selection())
            
        self._refresh_list()
        self._draw_overlays()
        self.status_var.set("Yeni efekt oluşturuluyor.")

    def _delete_effect_db(self):
        """Seçili efekti veritabanından siler."""
        sel = self.effects_tree.selection()
        if not sel:
            return
        
        if not messagebox.askyesno("Onay", "Seçili efekti silmek istediğinize emin misiniz?"):
            return
            
        item_id = sel[0]
        name = self.effects_tree.item(item_id)['values'][0]
        
        try:
            if self.effect_service.delete_effect(0, name):
                self._refresh_effects_list()
                self._new_effect() 
                messagebox.showinfo("Silindi", f"{name} silindi.")
            else:
                messagebox.showerror("Hata", "Silme işlemi başarısız.")
        except Exception as e:
            messagebox.showerror("Hata", f"Silme hatası: {e}")

    def _select_media_image(self) -> None:
        """Mevcut proje medyaları arasından seçim yapar."""
        # Medya seçim penceresi - Basit bir Toplevel liste
        try:
            top = tk.Toplevel(self)
            top.title("Görsel Seç")
            top.geometry("400x500")
            top.transient(self)
            
            tree = ttk.Treeview(top, columns=("path",), show="headings")
            tree.heading("path", text="Dosya Yolu")
            tree.pack(fill=tk.BOTH, expand=True)
            
            # Assets klasörünü tara
            base_dir = os.path.join(self._assets_root, "images")
            if os.path.isdir(base_dir):
                for root, dirs, files in os.walk(base_dir):
                    for f in files:
                        if f.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                            full_path = os.path.join(root, f)
                            rel_path = os.path.relpath(full_path, self._project_root)
                            tree.insert("", tk.END, values=(rel_path,))
            
            def _on_select(event):
                sel = tree.selection()
                if not sel: return
                val = tree.item(sel[0], "values")[0]
                abs_path = os.path.join(self._project_root, val)
                self._load_image(abs_path)
                top.destroy()
                
            tree.bind("<Double-1>", _on_select)
            
        except Exception as e:
            messagebox.showerror("Hata", f"Medya listesi açılamadı: {e}")

    def _open_image(self) -> None:
        # Legacy method, kept for reference or fallback
        self._select_media_image()

    def _load_image(self, path: str) -> None:
        """Belirtilen yolu yükler."""
        if not path or not os.path.exists(path):
            return
        try:
            img = Image.open(path).convert("RGBA")
            self._pil_image = img
            self._current_image_path = os.path.relpath(path, self._project_root).replace('\\', '/')
            self._fit_image_to_canvas()
            self.frames.clear()
            self._refresh_list()
            self.status_var.set(os.path.basename(path))
        except Exception as e:
            messagebox.showerror("Görsel", str(e))

    def _fit_image_to_canvas(self) -> None:
        """Görseli pencere boyutuna orantılı sığdırır ve canvas'a çizer."""
        if not self._pil_image:
            return
        iw, ih = self._pil_image.size
        cw = max(200, int(self.winfo_width() * 0.6))
        ch = max(200, int(self.winfo_height() * 0.7))
        self._scale = min(cw / iw, ch / ih)
        if self._scale <= 0:
            self._scale = 1.0
        rw, rh = int(iw * self._scale), int(ih * self._scale)
        rz = self._pil_image.resize((rw, rh), Image.LANCZOS)
        self._tk_image = ImageTk.PhotoImage(rz)
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_image, tags=("img",))
        self.canvas.config(width=rw, height=rh, scrollregion=(0, 0, rw, rh))
        self._draw_overlays()

    def _scale_to_image(self, x: int, y: int) -> Tuple[int, int]:
        """Canvas piksel koordinatını kaynak görsel pikseline dönüştürür."""
        sx = int(x / max(1e-6, self._scale))
        sy = int(y / max(1e-6, self._scale))
        return sx, sy

    def _on_canvas_down(self, e) -> None:
        """Canvas üzerine fare basıldığında."""
        if self._grid_mode:
            # Çizgi taşıma kontrolü
            # Canvas koordinatlarını al
            cx, cy = e.x, e.y
            # En yakın çizgiye bak (5 piksel tolerans)
            best_dist = 6
            found = None
            
            # Dikey çizgiler (X)
            for i, gx in enumerate(self._grid_xs):
                screen_x = int(gx * self._scale)
                if abs(screen_x - cx) < best_dist:
                    best_dist = abs(screen_x - cx)
                    found = ('x', i)
            
            # Yatay çizgiler (Y)
            for i, gy in enumerate(self._grid_ys):
                screen_y = int(gy * self._scale)
                if abs(screen_y - cy) < best_dist:
                    best_dist = abs(screen_y - cy)
                    found = ('y', i)
            
            if found:
                self._drag_line = found
            return
            
        self._sel_start = (e.x, e.y)
        if self._sel_rect_id:
            try:
                self.canvas.delete(self._sel_rect_id)
            except Exception:
                pass
            self._sel_rect_id = None

    def _on_canvas_drag(self, e) -> None:
        """Sürükleme işlemi."""
        if self._grid_mode:
            if self._drag_line:
                axis, idx = self._drag_line
                # Yeni image koordinatı
                if axis == 'x':
                    new_x, _ = self._scale_to_image(e.x, 0)
                    # Sınır kontrolü (önceki/sonraki çizgi arasında kalmalı mı? 
                    # Kullanım kolaylığı için serbest bırakıp apply'da sıralayabiliriz)
                    self._grid_xs[idx] = max(0, new_x)
                else:
                    _, new_y = self._scale_to_image(0, e.y)
                    self._grid_ys[idx] = max(0, new_y)
                self._draw_overlays()
            return
            
        if not self._sel_start:
            return
        x0, y0 = self._sel_start
        x1, y1 = e.x, e.y
        if self._sel_rect_id:
            self.canvas.coords(self._sel_rect_id, x0, y0, x1, y1)
        else:
            self._sel_rect_id = self.canvas.create_rectangle(x0, y0, x1, y1, outline="#00E5FF", dash=(4, 3))

    def _on_canvas_up(self, e) -> None:
        """Fare bırakıldığında."""
        if self._grid_mode:
            self._drag_line = None
            return
            
        if not self._sel_start:
            return
        x0, y0 = self._sel_start
        x1, y1 = e.x, e.y
        self._sel_start = None
        if abs(x1 - x0) < 4 or abs(y1 - y0) < 4:
            return
        ix0, iy0 = self._scale_to_image(min(x0, x1), min(y0, y1))
        ix1, iy1 = self._scale_to_image(max(x0, x1), max(y0, y1))
        w, h = max(1, ix1 - ix0), max(1, iy1 - iy0)
        self.frames.append({"x": ix0, "y": iy0, "w": w, "h": h})
        self._refresh_list()
        self._draw_overlays()
        
        # Seçim karesini sil
        if self._sel_rect_id:
            self.canvas.delete(self._sel_rect_id)
            self._sel_rect_id = None

    def _draw_overlays(self) -> None:
        """Canvas çizimlerini günceller (Kareler + Grid)."""
        if not self._tk_image:
            return
        self.canvas.delete("ov")
        
        # 1. Mevcut Kareler
        for i, fr in enumerate(self.frames, start=1):
            sx = int(fr['x'] * self._scale)
            sy = int(fr['y'] * self._scale)
            ex = int((fr['x'] + fr['w']) * self._scale)
            ey = int((fr['y'] + fr['h']) * self._scale)
            self.canvas.create_rectangle(sx, sy, ex, ey, outline="#FF5252", width=2, dash=(6,4), tags=("ov",))
            self.canvas.create_text(sx + 4, sy + 4, text=str(i), fill="#FFF176", anchor="nw", tags=("ov",))
            
        # 2. Grid Modu Çizgileri
        if self._grid_mode:
            w = self.canvas.winfo_width()
            h = self.canvas.winfo_height()
            
            # Dikey çizgiler (Cyan)
            for x in self._grid_xs:
                sx = int(x * self._scale)
                self.canvas.create_line(sx, 0, sx, h, fill="#00E5FF", width=2, tags=("ov",))
                
            # Yatay çizgiler (Magenta)
            for y in self._grid_ys:
                sy = int(y * self._scale)
                self.canvas.create_line(0, sy, w, sy, fill="#FF4081", width=2, tags=("ov",))
                
            # Kesişim noktalarını (potansiyel kareler) hafifçe göster
            # Çok kalabalık olmasın diye sadece çizgileri çizmek yeterli olabilir.

    def _refresh_list(self) -> None:
        """Listbox içeriğini `frames` durumundan yeniden üretir."""
        self.listbox.delete(0, tk.END)
        for i, fr in enumerate(self.frames, start=1):
            self.listbox.insert(tk.END, f"{i}) x={fr['x']} y={fr['y']} w={fr['w']} h={fr['h']}")

    def _move_item(self, delta: int) -> None:
        """Seçili kareyi listede yukarı/aşağı taşır ve overlay'i yeniler."""
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        new = idx + delta
        if new < 0 or new >= len(self.frames):
            return
        self.frames[idx], self.frames[new] = self.frames[new], self.frames[idx]
        self._refresh_list()
        self.listbox.selection_set(new)
        self._draw_overlays()

    def _delete_frame_item(self) -> None:
        """Seçili kareleri (frame) listeden siler (Çoklu seçim destekli)."""
        sel = self.listbox.curselection()
        if not sel:
            return
        
        # Sondan başa doğru sil ki indeksler kaymasın
        for idx in sorted(sel, reverse=True):
            if 0 <= idx < len(self.frames):
                self.frames.pop(idx)
                
        self._refresh_list()
        self._draw_overlays()

    def _delete_item(self) -> None:
        """(Legacy) Seçili kareyi kaldırır."""
        self._delete_frame_item()

    def _select_all_frames(self, event=None) -> str:
        """Listbox'taki tüm kareleri seçer."""
        self.listbox.select_set(0, tk.END)
        return "break"  # Event'in varsayılan davranışını engelle

    def _select_from_list(self) -> None:
        """Listeden seçim yapıldığında, ilgili kareyi vurgular (geleceğe hazır)."""
        # Şimdilik ek bir vurgulama yapmıyoruz; overlay tüm kareleri gösteriyor.
        pass

    def _preview_play(self) -> None:
        """Kareleri canvas üzerinde sırayla göstererek hızlı bir önizleme oynatır."""
        if not self.frames or not self._pil_image:
            return
        try:
            dur = max(1, int(self.frame_ms_var.get()))
        except Exception:
            dur = 120
        # Önceden yaratılan image objelerini saklayalım
        seq_imgs: List[ImageTk.PhotoImage] = []
        crops = []
        for fr in self.frames:
            box = (fr['x'], fr['y'], fr['x'] + fr['w'], fr['y'] + fr['h'])
            try:
                crop = self._pil_image.crop(box)
                rw = int(crop.size[0] * self._scale)
                rh = int(crop.size[1] * self._scale)
                crop_rz = crop.resize((rw, rh), Image.LANCZOS)
                seq_imgs.append(ImageTk.PhotoImage(crop_rz))
                crops.append((seq_imgs[-1], rw, rh))
            except Exception:
                continue

        def step(i: int) -> None:
            self.canvas.delete("pv")
            if i >= len(crops):
                return
            img_ref, rw, rh = crops[i]
            # Sol üstte göster
            self.canvas.create_image(0, 0, anchor="nw", image=img_ref, tags=("pv",))
            # Tekrar schedule
            self.after(dur, lambda: step(i + 1))

        # Referansı sakla ki GC olmasın
        self._preview_refs = seq_imgs
        step(0)

    def _preview_stop(self) -> None:
        """Önizlemeyi temizler."""
        self.canvas.delete("pv")
        self._preview_refs = []

    def _save_effect(self) -> None:
        """Efekti veritabanına kaydeder veya günceller."""
        if not self.effect_service:
            messagebox.showerror("Hata", "Servis bağlantısı yok.")
            return
            
        name = self.effect_name_var.get().strip()
        if not name:
            messagebox.showwarning("Uyarı", "Lütfen efekt adı girin.")
            return
            
        if not self._current_image_path:
            messagebox.showwarning("Uyarı", "Lütfen bir görsel seçin.")
            return
            
        if not self.frames:
            messagebox.showwarning("Uyarı", "En az bir kare seçmelisiniz.")
            return

        try:
            frame_ms = int(self.frame_ms_var.get())
        except ValueError:
            frame_ms = 120

        # Veri paketi
        params = {
            "image_path": self._current_image_path,
            "frame_ms": frame_ms,
            "frames": self.frames,
            "type": "frame_sequence"
        }
        json_str = json.dumps(params)

        try:
            if self._current_effect_id:
                # Güncelleme (Global ID=0)
                success = self.effect_service.update_effect(
                    self._current_effect_id,
                    0, # game_id=0 (Global)
                    name,
                    "frame_sequence",
                    json_str
                )
                if success:
                    messagebox.showinfo("Başarılı", f"Efekt güncellendi: {name}")
                else:
                    messagebox.showerror("Hata", "Güncelleme başarısız oldu.")
            else:
                # Yeni Kayıt (Global ID=0)
                new_effect = self.effect_service.add_effect(
                    0, # game_id=0 (Global)
                    name,
                    "frame_sequence",
                    json_str
                )
                self._current_effect_id = new_effect.id
                messagebox.showinfo("Başarılı", f"Yeni efekt kaydedildi: {name}")

            self._refresh_effects_list()
            
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydetme hatası: {e}")

    # --- Otomatik Algılama ve Araçlar ---

    def _open_auto_slice_dialog(self):
        """Otomatik kesim parametreleri için dialog açar."""
        if not self._pil_image:
            messagebox.showwarning("Uyarı", "Önce bir görsel seçin.")
            return

        # Dialog oluştur
        top = tk.Toplevel(self)
        top.title("Otomatik Kes")
        top.geometry("300x280")
        top.transient(self)
        
        ttk.Label(top, text="1. Canvas üzerinde kesilecek alanı seçin\n(Tüm resim için seçim yapmayın)", justify=tk.CENTER).pack(pady=5)
        
        f = ttk.Frame(top, padding=10)
        f.pack(fill=tk.BOTH, expand=True)
        
        ttk.Label(f, text="Kare Genişliği (px):").grid(row=0, column=0, sticky="e", pady=2)
        w_var = tk.StringVar(value="64")
        ttk.Entry(f, textvariable=w_var, width=8).grid(row=0, column=1, pady=2)
        
        ttk.Label(f, text="Kare Yüksekliği (px):").grid(row=1, column=0, sticky="e", pady=2)
        h_var = tk.StringVar(value="64")
        ttk.Entry(f, textvariable=h_var, width=8).grid(row=1, column=1, pady=2)
        
        ttk.Label(f, text="Yatay Boşluk (Gap X):").grid(row=2, column=0, sticky="e", pady=2)
        gx_var = tk.StringVar(value="0")
        ttk.Entry(f, textvariable=gx_var, width=8).grid(row=2, column=1, pady=2)
        
        ttk.Label(f, text="Dikey Boşluk (Gap Y):").grid(row=3, column=0, sticky="e", pady=2)
        gy_var = tk.StringVar(value="0")
        ttk.Entry(f, textvariable=gy_var, width=8).grid(row=3, column=1, pady=2)
        
        chk_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(f, text="Boş kareleri atla", variable=chk_var).grid(row=4, column=0, columnspan=2, pady=10)
        
        def run():
            try:
                cw = int(w_var.get())
                ch = int(h_var.get())
                gx = int(gx_var.get())
                gy = int(gy_var.get())
                skip = chk_var.get()
                if cw < 1 or ch < 1:
                    raise ValueError("Boyutlar 0'dan büyük olmalı")
                self._run_auto_slice(cw, ch, gx, gy, skip)
                top.destroy()
            except ValueError:
                messagebox.showerror("Hata", "Geçerli sayısal değerler girin.")

        ttk.Button(top, text="Kesmeye Başla", command=run).pack(pady=10)

    def _run_auto_slice(self, cell_w: int, cell_h: int, gap_x: int, gap_y: int, skip_empty: bool):
        """Verilen parametrelere göre ızgara oluşturur ve kareleri ekler."""
        if not self._pil_image:
            return

        # Alan belirle: Seçim varsa o alan, yoksa tüm resim
        # Seçim koordinatları canvas üzerindedir, resme çevirmeliyiz.
        # Ancak _sel_start tek nokta, bir rect_id varsa coords alabiliriz.
        
        area_rect = None
        if self._sel_rect_id:
            try:
                x1, y1, x2, y2 = self.canvas.coords(self._sel_rect_id)
                # Canvas -> Image koordinat
                ix1, iy1 = self._scale_to_image(min(x1, x2), min(y1, y2))
                ix2, iy2 = self._scale_to_image(max(x1, x2), max(y1, y2))
                area_rect = (ix1, iy1, ix2, iy2)
            except Exception:
                pass
        
        if not area_rect:
            iw, ih = self._pil_image.size
            area_rect = (0, 0, iw, ih)
            
        sx, sy, ex, ey = area_rect
        
        new_frames = []
        
        curr_y = sy
        while curr_y + cell_h <= ey:
            curr_x = sx
            while curr_x + cell_w <= ex:
                # Kare adayımız
                box = (curr_x, curr_y, curr_x + cell_w, curr_y + cell_h)
                
                valid = True
                if skip_empty:
                    # Alpha kontrolü
                    crop = self._pil_image.crop(box)
                    bbox = crop.getbbox() # Tamamen şeffafsa None döner
                    if not bbox:
                        valid = False
                
                if valid:
                    new_frames.append({"x": curr_x, "y": curr_y, "w": cell_w, "h": cell_h})
                
                curr_x += cell_w + gap_x
            curr_y += cell_h + gap_y
            
        if new_frames:
            # Mevcut karelerin üzerine mi ekleyelim yoksa silip mi?
            # Genelde "seçili alana ekle" mantığı daha güvenli.
            self.frames.extend(new_frames)
            self._refresh_list()
            self._draw_overlays()
            messagebox.showinfo("Tamamlandı", f"{len(new_frames)} kare eklendi.")
        else:
            messagebox.showwarning("Sonuç", "Belirtilen kriterlere uygun kare bulunamadı.")

    def _sort_frames(self, mode: str):
        """Mevcut kareleri sıralar."""
        if not self.frames:
            return
            
        # Sıralama toleransı (biraz kayık olsa da aynı satır sayılsın)
        tolerance = 10 
        
        def row_major(f):
            # Y'ye göre grupla, sonra X
            y_group = f['y'] // tolerance
            return (y_group, f['x'])
            
        def col_major(f):
            # X'e göre grupla, sonra Y
            x_group = f['x'] // tolerance
            return (x_group, f['y'])
            
        if mode == "row":
            self.frames.sort(key=row_major)
        elif mode == "col":
            self.frames.sort(key=col_major)
            
        self._refresh_list()
        self._draw_overlays()

    # --- Kılavuz (Grid) Modu ---

    def _toggle_grid_mode(self):
        self._grid_mode = not self._grid_mode
        if self._grid_mode:
            self.grid_btn.configure(text="📏 Kılavuz Modu: AÇIK")
            # Eğer hiç çizgi yoksa otomatik algıla
            if not self._grid_xs and not self._grid_ys:
                self._detect_grid()
        else:
            self.grid_btn.configure(text="📏 Kılavuz Modu: KAPALI")
        self._draw_overlays()

    def _distribute_grid(self):
        """Mevcut kılavuz çizgilerini eşit aralıklarla hizalar."""
        if not self._grid_mode:
            messagebox.showwarning("Uyarı", "Kılavuz modu açık olmalıdır.")
            return
            
        changed = False
        
        # X Eşitleme
        if len(self._grid_xs) > 2:
            self._grid_xs.sort()
            start = self._grid_xs[0]
            end = self._grid_xs[-1]
            count = len(self._grid_xs)
            step = (end - start) / (count - 1)
            
            new_xs = []
            for i in range(count):
                # Son eleman kesinlikle end olmalı
                if i == count - 1:
                    val = end
                else:
                    val = int(start + i * step)
                new_xs.append(val)
            
            self._grid_xs = new_xs
            changed = True
            
        # Y Eşitleme
        if len(self._grid_ys) > 2:
            self._grid_ys.sort()
            start = self._grid_ys[0]
            end = self._grid_ys[-1]
            count = len(self._grid_ys)
            step = (end - start) / (count - 1)
            
            new_ys = []
            for i in range(count):
                if i == count - 1:
                    val = end
                else:
                    val = int(start + i * step)
                new_ys.append(val)
                
            self._grid_ys = new_ys
            changed = True
            
        if changed:
            self._draw_overlays()
        else:
            messagebox.showinfo("Bilgi", "Hizalamak için her eksende en az 3 çizgi gerekli.")

    def _detect_grid(self):
        """Resmi analiz ederek kılavuz çizgilerini tahmin eder."""
        if not self._pil_image:
            return

        w, h = self._pil_image.size
        # Alpha kanalını al
        try:
            if 'A' in self._pil_image.getbands():
                alpha = self._pil_image.split()[-1]
            else:
                self._grid_xs = [0, w]
                self._grid_ys = [0, h]
                return
        except Exception:
            return
        
        # Bounding box ile içeriğin sınırlarını bul
        bbox = alpha.getbbox()
        if not bbox:
            self._grid_xs = [0, w]
            self._grid_ys = [0, h]
            return
            
        bx, by, bx2, by2 = bbox
        
        # Izgara listeleri (Image space)
        xs_set = {0, w, bx, bx2}
        ys_set = {0, h, by, by2}
        
        # Basit bölme önerisi (Kullanıcı düzenlesin diye)
        if (bx2 - bx) > 100:
            xs_set.add(bx + (bx2 - bx) // 2)
        if (by2 - by) > 100:
            ys_set.add(by + (by2 - by) // 2)
            
        self._grid_xs = sorted(list(xs_set))
        self._grid_ys = sorted(list(ys_set))

    def _detect_grid(self):
        """Resmi analiz ederek kılavuz çizgilerini tahmin eder (Segment Gap Midpoint Yöntemi)."""
        if not self._pil_image:
            return

        w, h = self._pil_image.size
        try:
            if 'A' in self._pil_image.getbands():
                alpha = self._pil_image.split()[-1]
            else:
                self._grid_xs = [0, w]
                self._grid_ys = [0, h]
                return
        except Exception:
            return

        # 1. Projeksiyon Verilerini Al
        # X Projeksiyonu (Sütunlar)
        x_proj_img = alpha.resize((w, 1), resample=Image.BOX)
        x_data = list(x_proj_img.getdata())
        
        # Y Projeksiyonu (Satırlar)
        y_proj_img = alpha.resize((1, h), resample=Image.BOX)
        y_data = list(y_proj_img.getdata())

        threshold = 10
        
        def find_segments(data, length):
            """Verilen dizideki dolu aralıkları (start, end) listesi olarak döner."""
            segs = []
            start = None
            for i in range(length):
                val = data[i]
                if val > threshold:
                    if start is None:
                        start = i
                else:
                    if start is not None:
                        segs.append((start, i))
                        start = None
            if start is not None:
                segs.append((start, length))
            return segs

        def merge_close_segments(segs, gap_limit):
            """Birbirine yakın segmentleri birleştirir."""
            if not segs: return []
            merged = []
            curr_start, curr_end = segs[0]
            
            for i in range(1, len(segs)):
                next_start, next_end = segs[i]
                if (next_start - curr_end) <= gap_limit:
                    # Birleştir
                    curr_end = next_end
                else:
                    merged.append((curr_start, curr_end))
                    curr_start, curr_end = next_start, next_end
            merged.append((curr_start, curr_end))
            return merged

        def get_lines_from_segments(segs, length):
            """Segmentler arasındaki boşlukların ortasına çizgi koyar."""
            lines = set()
            lines.add(0)
            lines.add(length)
            
            if not segs:
                return sorted(list(lines))
            
            # İki segmentin arasındaki boşluğun ortasına çizgi çek
            for i in range(len(segs) - 1):
                # segs[i][1] = bitiş, segs[i+1][0] = sonraki başlangıç
                mid = (segs[i][1] + segs[i+1][0]) // 2
                lines.add(mid)
                
            return sorted(list(lines))

        # X Ekseninde Segmentler
        x_segs = find_segments(x_data, w)
        # Sprite içindeki ufak boşlukları yoksaymak için gap_limit
        x_segs = merge_close_segments(x_segs, gap_limit=5) 
        self._grid_xs = get_lines_from_segments(x_segs, w)
        
        # Y Ekseninde Segmentler
        y_segs = find_segments(y_data, h)
        y_segs = merge_close_segments(y_segs, gap_limit=5)
        self._grid_ys = get_lines_from_segments(y_segs, h)

    def _on_canvas_double_click(self, e) -> None:
        """Çift tıklama ile kılavuz çizgisi ekle."""
        if not self._grid_mode:
            return
        
        ix, iy = self._scale_to_image(e.x, e.y)
        w, h = self._pil_image.size
        
        # Hangi eksene daha yakın? Veya her iki eksene de mi ekleyelim?
        # Genelde kullanıcı dikey veya yatay bir çizgi eklemek ister.
        # Fare hareketinden bunu anlamak zor. 
        # Basitçe: Hem X hem Y'ye ekleyelim, kullanıcı istemediğini silsin?
        # Veya daha akıllıca: Resmin kenarlarına yakınlığa göre değil,
        # mevcut çizgilere olan mesafeye göre değil...
        # En iyisi: Her ikisini de ekleyelim, çünkü bir kare tanımlıyor olabilir.
        
        # Ancak grid sistemi "tüm satır/sütun" mantığında çalıştığı için,
        # bir yere tıklayınca oradan geçen hem yatay hem dikey çizgi eklemek mantıklı.
        
        if 0 <= ix <= w:
            if ix not in self._grid_xs:
                self._grid_xs.append(ix)
                self._grid_xs.sort()
                
        if 0 <= iy <= h:
            if iy not in self._grid_ys:
                self._grid_ys.append(iy)
                self._grid_ys.sort()
                
        self._draw_overlays()

    def _on_canvas_right_click(self, e) -> None:
        """Sağ tıklama ile en yakın kılavuz çizgisini sil."""
        if not self._grid_mode:
            return
            
        cx, cy = e.x, e.y
        # En yakın çizgiyi bul
        best_dist = 10 # Piksel toleransı
        found = None
        
        # X çizgileri
        for i, gx in enumerate(self._grid_xs):
            screen_x = int(gx * self._scale)
            dist = abs(screen_x - cx)
            if dist < best_dist:
                best_dist = dist
                found = ('x', gx) # index yerine değeri sakla, silerken güvenli olsun
                
        # Y çizgileri
        for i, gy in enumerate(self._grid_ys):
            screen_y = int(gy * self._scale)
            dist = abs(screen_y - cy)
            if dist < best_dist:
                best_dist = dist
                found = ('y', gy)
                
        if found:
            axis, val = found
            if axis == 'x':
                if val in self._grid_xs:
                    self._grid_xs.remove(val)
            else:
                if val in self._grid_ys:
                    self._grid_ys.remove(val)
            self._draw_overlays()

    def _apply_grid_to_frames(self):
        """Kılavuz çizgileri arasındaki alanları karelere dönüştürür."""
        if not self._grid_xs or not self._grid_ys:
            messagebox.showwarning("Uyarı", "Önce kılavuz çizgileri oluşturun.")
            return
            
        self._grid_xs.sort()
        self._grid_ys.sort()
        
        new_frames = []
        
        # Her bir ızgara hücresini kontrol et
        for i in range(len(self._grid_ys) - 1):
            y1 = self._grid_ys[i]
            y2 = self._grid_ys[i+1]
            h = y2 - y1
            if h < 2: continue
            
            for j in range(len(self._grid_xs) - 1):
                x1 = self._grid_xs[j]
                x2 = self._grid_xs[j+1]
                w = x2 - x1
                if w < 2: continue
                
                # Boş mu kontrolü
                box = (x1, y1, x2, y2)
                try:
                    crop = self._pil_image.crop(box)
                    if crop.getbbox(): # Doluysa ekle
                        new_frames.append({"x": x1, "y": y1, "w": w, "h": h})
                except Exception:
                    pass
                    
        if new_frames:
            if messagebox.askyesno("Onay", f"{len(new_frames)} adet kare bulundu. Mevcut listeye eklensin mi?"):
                self.frames.extend(new_frames)
                self._refresh_list()
                self._draw_overlays()
                # Grid modundan çık
                self._toggle_grid_mode()
        else:
            messagebox.showinfo("Sonuç", "Seçilen alanlarda içerik bulunamadı.")

