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
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from typing import List, Optional, Tuple

from PIL import Image, ImageTk


class EffectsManagerWindow(tk.Toplevel):
    """Efekt yönetimi için bağımsız Toplevel pencere.

    Attributes:
        frames: Seçilen karelerin listesi [{'x','y','w','h'}].
    """

    def __init__(self, parent: tk.Tk, effect_service=None, game_id: int = None):
        """Pencereyi oluşturur ve UI bileşenlerini yerleştirir.

        Args:
            parent: Üst Tk penceresi
            effect_service: Efekt servis örneği
            game_id: Aktif oyun ID'si
        """
        super().__init__(parent)
        self.effect_service = effect_service
        self.game_id = game_id
        self.title("Effect Yöneticisi")
        self.geometry("1100x760")
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

        self._build_ui()

    def _build_ui(self) -> None:
        """UI iskeletini kurar: sol listeler, sağda canvas ve önizleme kontrolleri."""
        root = ttk.Frame(self, padding=6)
        root.pack(fill=tk.BOTH, expand=True)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)

        # Üst araç çubuğu
        bar = ttk.Frame(root)
        bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        ttk.Button(bar, text="Medya'dan Görsel Seç...", command=self._select_media_image).pack(side=tk.LEFT, padx=4)
        ttk.Label(bar, text="Efekt Adı:").pack(side=tk.LEFT)
        self.effect_name_var = tk.StringVar(value="effect")
        ttk.Entry(bar, textvariable=self.effect_name_var, width=24).pack(side=tk.LEFT, padx=4)
        ttk.Button(bar, text="Kaydet", command=self._save_effect).pack(side=tk.RIGHT, padx=4)

        # Sol panel: kare listesi ve sıralama
        left = ttk.LabelFrame(root, text="Kareler (sıra)", padding=6)
        left.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        left.rowconfigure(1, weight=1)
        left.columnconfigure(0, weight=1)

        self.listbox = tk.Listbox(left, height=20)
        self.listbox.grid(row=1, column=0, sticky="nsew")
        self.listbox.bind("<<ListboxSelect>>", lambda e: self._select_from_list())

        btns = ttk.Frame(left)
        btns.grid(row=2, column=0, sticky="ew", pady=(6, 0))
        ttk.Button(btns, text="Yukarı", command=lambda: self._move_item(-1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Aşağı", command=lambda: self._move_item(1)).pack(side=tk.LEFT, padx=2)
        ttk.Button(btns, text="Sil", command=self._delete_item).pack(side=tk.LEFT, padx=2)

        # Oynatma ayarları
        play = ttk.LabelFrame(left, text="Önizleme", padding=6)
        play.grid(row=3, column=0, sticky="ew", pady=(8,0))
        ttk.Label(play, text="Kare Süresi (ms)").pack(side=tk.LEFT)
        self.frame_ms_var = tk.StringVar(value="120")
        ttk.Entry(play, textvariable=self.frame_ms_var, width=6).pack(side=tk.LEFT, padx=4)
        ttk.Button(play, text="▶ Oynat", command=self._preview_play).pack(side=tk.LEFT, padx=4)
        ttk.Button(play, text="■ Durdur", command=self._preview_stop).pack(side=tk.LEFT)

        # Sağ panel: canvas
        right = ttk.LabelFrame(root, text="Sprite Sheet", padding=6)
        right.grid(row=1, column=1, sticky="nsew")
        right.rowconfigure(0, weight=1)
        right.columnconfigure(0, weight=1)

        self.canvas = tk.Canvas(right, bg="black")
        self.canvas.grid(row=0, column=0, sticky="nsew")
        self.canvas.bind("<Button-1>", self._on_canvas_down)
        self.canvas.bind("<B1-Motion>", self._on_canvas_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_canvas_up)

        # Alt durum çubuğu
        status = ttk.Frame(self)
        status.pack(side=tk.BOTTOM, fill=tk.X)
        self.status_var = tk.StringVar(value="Hazır")
        ttk.Label(status, textvariable=self.status_var).pack(side=tk.LEFT, padx=6)

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
        """Canvas üzerine fare basıldığında seçim başlangıcını işaretler."""
        self._sel_start = (e.x, e.y)
        if self._sel_rect_id:
            try:
                self.canvas.delete(self._sel_rect_id)
            except Exception:
                pass
            self._sel_rect_id = None

    def _on_canvas_drag(self, e) -> None:
        """Sürüklerken geçici seçim dikdörtgenini çizer."""
        if not self._sel_start:
            return
        x0, y0 = self._sel_start
        x1, y1 = e.x, e.y
        if self._sel_rect_id:
            self.canvas.coords(self._sel_rect_id, x0, y0, x1, y1)
        else:
            self._sel_rect_id = self.canvas.create_rectangle(x0, y0, x1, y1, outline="#00E5FF", dash=(4, 3))

    def _on_canvas_up(self, e) -> None:
        """Fare bırakıldığında geçerli seçimden kare oluşturur ve listeye ekler."""
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

    def _draw_overlays(self) -> None:
        """Canvas üzerinde mevcut kareleri kesik çizgi ve numara ile çizer."""
        if not self._tk_image:
            return
        self.canvas.delete("ov")
        for i, fr in enumerate(self.frames, start=1):
            sx = int(fr['x'] * self._scale)
            sy = int(fr['y'] * self._scale)
            ex = int((fr['x'] + fr['w']) * self._scale)
            ey = int((fr['y'] + fr['h']) * self._scale)
            self.canvas.create_rectangle(sx, sy, ex, ey, outline="#FF5252", width=2, dash=(6,4), tags=("ov",))
            self.canvas.create_text(sx + 4, sy + 4, text=str(i), fill="#FFF176", anchor="nw", tags=("ov",))

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

    def _delete_item(self) -> None:
        """Seçili kareyi kaldırır ve overlay'i günceller."""
        sel = self.listbox.curselection()
        if not sel:
            return
        idx = sel[0]
        self.frames.pop(idx)
        self._refresh_list()
        self._draw_overlays()

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
        """Kullanıcının kare sırası ile bir efekt tanımını diske/DBye kaydetmek için tetiklenir."""
        if not self._current_image_path:
            messagebox.showwarning("Effect", "Önce bir sprite sheet seçin.")
            return
        if not self.frames:
            messagebox.showwarning("Effect", "Önce en az bir kare seçin.")
            return
        if not self.game_id or not self.effect_service:
            messagebox.showerror("Hata", "Oyun veya servis bilgisi eksik.")
            return
            
        name = (self.effect_name_var.get() or "effect").strip()
        if not name:
            name = "effect"
            
        # JSON formatında parametreleri hazırla
        import json
        try:
            params = {
                "image_path": self._current_image_path,
                "frame_ms": max(1, int(self.frame_ms_var.get() or 120)),
                "frames": self.frames,
                "type": "frame_sequence"
            }
            
            # DB'ye kaydet
            self.effect_service.add_effect(self.game_id, name, "frame_sequence", json.dumps(params))
            messagebox.showinfo("Başarılı", f"Efekt kaydedildi: {name}")
            self.destroy()
            
        except Exception as e:
            messagebox.showerror("Hata", f"Efekt kaydedilemedi: {e}")
