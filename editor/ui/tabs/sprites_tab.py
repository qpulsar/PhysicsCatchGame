"""Tab for browsing image assets and selecting visuals from assets/.

This refactor simplifies the original Sprite Sheets manager. It now:
- Scans assets/ and assets/games/<game_id>/ recursively for image files
- Lists images on the left and previews the selection on the right
- Removes overlapping responsibilities with ScreenDesigner (no expressions, levels, end screens here)
"""
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional, Dict, List
from PIL import Image, ImageTk
import json
import unicodedata

from ...core.models import Sprite, SpriteDefinition, Expression
from ...core.services import SpriteService, ExpressionService, LevelService, GameService

# A simple pop-up window to draw a rectangle on an image
class Cropper(tk.Toplevel):
    """A window for selecting a rectangular region from an image."""
    def __init__(self, parent, image_path):
        super().__init__(parent)
        self.title("Sprite Seç")
        self.transient(parent)
        self.grab_set()
        self.result = None

        self.image = Image.open(image_path)
        self.tk_image = ImageTk.PhotoImage(self.image)

        self.canvas = tk.Canvas(self, width=self.image.width, height=self.image.height, cursor="cross")
        self.canvas.create_image(0, 0, anchor="nw", image=self.tk_image)
        self.canvas.pack(fill="both", expand=True)

        self.rect = None
        self.start_x = None
        self.start_y = None

        self.canvas.bind("<ButtonPress-1>", self.on_button_press)
        self.canvas.bind("<B1-Motion>", self.on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_button_release)

    def on_button_press(self, event):
        self.start_x = self.canvas.canvasx(event.x)
        self.start_y = self.canvas.canvasy(event.y)
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(self.start_x, self.start_y, self.start_x, self.start_y, outline='red', width=2)

    def on_mouse_drag(self, event):
        cur_x, cur_y = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        self.canvas.coords(self.rect, self.start_x, self.start_y, cur_x, cur_y)

    def on_button_release(self, event):
        end_x, end_y = (self.canvas.canvasx(event.x), self.canvas.canvasy(event.y))
        
        x1 = min(self.start_x, end_x)
        y1 = min(self.start_y, end_y)
        x2 = max(self.start_x, end_x)
        y2 = max(self.start_y, end_y)

        if x2 - x1 > 0 and y2 - y1 > 0:
            self.result = {'x': int(x1), 'y': int(y1), 'width': int(x2 - x1), 'height': int(y2 - y1)}
            self.destroy()

    def show(self):
        self.wait_window()
        return self.result


class SpritesTab:
    """Simplified assets browser for selecting images from assets/."""
    def __init__(self, parent, sprite_service: SpriteService, expression_service: ExpressionService, level_service: LevelService, game_service: GameService):
        self.parent = parent
        self.sprite_service = sprite_service
        self.expression_service = expression_service # To get expressions
        self.level_service = level_service
        self.game_service = game_service
        self.selected_sprite_sheet: Optional[Sprite] = None  # legacy, unused
        self.tk_image = None
        # Simplified state
        self.asset_images: List[str] = []  # relative paths from project root
        self._index_to_path: Dict[str, str] = {}  # tree iid -> rel path

        self.frame = ttk.Frame(parent)
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)

        self.paned_window = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        self.paned_window.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        # deferred refresh state
        self._defer_attempts = 0
        self._defer_max = 25  # ~5sn (200ms aralıklarla)
        self._defer_scheduled = False

        # Left Pane: Assets Image List
        left_pane = self._create_left_pane()
        self.paned_window.add(left_pane, weight=1)

        # Right Pane: Preview
        right_pane = self._create_right_pane()
        self.paned_window.add(right_pane, weight=3)

        # Populate regions immediately (even before a game is selected)
        try:
            self._refresh_regions_list()
        except Exception:
            pass

        # Auto-refresh when the tab becomes visible
        self.frame.bind('<Map>', lambda event: self.refresh())

    def _create_left_pane(self) -> ttk.Frame:
        pane = ttk.Frame(self.paned_window)
        pane.rowconfigure(0, weight=1)
        pane.columnconfigure(0, weight=1)

        # Assets Image List (restricted to assets/images/sprites)
        list_frame = ttk.LabelFrame(pane, text="Görseller (assets/images/sprites)", padding=5)
        list_frame.grid(row=0, column=0, sticky="nsew", pady=5)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.sheets_tree = ttk.Treeview(list_frame, columns=("path",), show="headings", selectmode="browse")
        self.sheets_tree.heading("path", text="Görsel (göreli yol)")
        self.sheets_tree.grid(row=0, column=0, sticky="nsew")
        self.sheets_tree.bind("<<TreeviewSelect>>", self._on_sheet_select)

        # Info row (management hint + refresh)
        button_frame = ttk.Frame(pane)
        button_frame.grid(row=1, column=0, sticky="ew", pady=(5,0))
        ttk.Label(button_frame, text="Bu sekme sadece seçim içindir. Yönetim ScreenDesigner/Level ekranlarında yapılır.").pack(side=tk.LEFT)
        # Debug & refresh controls
        ttk.Button(button_frame, text="Yenile", command=self.refresh).pack(side=tk.RIGHT)
        ttk.Button(button_frame, text="Debug: Sprite Kontrol", command=self._debug_regions_check).pack(side=tk.RIGHT, padx=(0,6))
        ttk.Button(button_frame, text="Otomatik Tespit", command=self._auto_detect_buttons).pack(side=tk.RIGHT, padx=(0,6))
        
        # Regions management
        regions_frame = ttk.LabelFrame(pane, text="Sprite Bölgeleri", padding=5)
        regions_frame.grid(row=2, column=0, sticky="nsew", pady=5)
        regions_frame.rowconfigure(0, weight=1)
        regions_frame.columnconfigure(0, weight=1)
        self.regions_tree = ttk.Treeview(regions_frame, columns=("name","image","coords"), show="headings", selectmode="browse")
        self.regions_tree.heading("name", text="Ad")
        self.regions_tree.heading("image", text="Görsel")
        self.regions_tree.heading("coords", text="(x,y,w,h)")
        self.regions_tree.column("name", width=160)
        self.regions_tree.column("image", width=260)
        self.regions_tree.column("coords", width=140)
        self.regions_tree.grid(row=0, column=0, sticky="nsew")
        # Bölge seçimi değişince küçük önizlemeyi güncelle
        self.regions_tree.bind("<<TreeviewSelect>>", lambda e: self._update_region_preview())
        btn_row = ttk.Frame(regions_frame)
        btn_row.grid(row=1, column=0, sticky="ew", pady=(6,0))
        ttk.Button(btn_row, text="Yeniden Adlandır", command=self._rename_region).pack(side=tk.LEFT)
        ttk.Button(btn_row, text="Sil", command=self._delete_region).pack(side=tk.LEFT, padx=6)
        ttk.Button(btn_row, text="Yeniden Kırp", command=self._recrop_region).pack(side=tk.LEFT)
        return pane

    def _create_right_pane(self) -> ttk.Frame:
        pane = ttk.Frame(self.paned_window)
        pane.rowconfigure(0, weight=1)
        pane.columnconfigure(0, weight=1)

        # Viewer Frame (küçültülmüş ana önizleme)
        viewer_frame = ttk.LabelFrame(pane, text="Önizleme", padding=5)
        viewer_frame.grid(row=0, column=0, sticky="nsew", pady=5)
        # Ana görsel için daha küçük bir canvas ve sabit maksimum boyut
        self._main_preview_max = (500, 300)
        self.image_canvas = tk.Canvas(viewer_frame, width=self._main_preview_max[0], height=self._main_preview_max[1], background="white")
        self.image_canvas.pack(fill="x", expand=False)
        self.image_canvas.bind("<Double-1>", self._open_cropper)

        # Seçili görsel yol bilgisi
        sel_frame = ttk.Frame(viewer_frame)
        sel_frame.pack(fill="x", pady=(5,0))
        ttk.Label(sel_frame, text="Seçilen Görsel:").pack(side=tk.LEFT)
        self.selected_image_var = tk.StringVar(value="(yok)")
        ttk.Label(sel_frame, textvariable=self.selected_image_var).pack(side=tk.LEFT, padx=5)

        # Seçilen sprite bölgesi için önizleme alanı
        region_preview = ttk.LabelFrame(pane, text="Seçili Sprite Önizleme", padding=5)
        region_preview.grid(row=1, column=0, sticky="nsew", pady=(0,5))
        self._region_preview_max = (220, 180)
        self.region_canvas = tk.Canvas(region_preview, width=self._region_preview_max[0], height=self._region_preview_max[1], background="white")
        self.region_canvas.pack(fill="x", expand=False)

        return pane

    def refresh(self):

        # Populate assets image list
        for item in self.sheets_tree.get_children():
            self.sheets_tree.delete(item)
        self._index_to_path.clear()
        self.asset_images = self._scan_assets_images()
        for idx, rel in enumerate(self.asset_images):
            iid = str(idx)
            self._index_to_path[iid] = rel
            self.sheets_tree.insert("", "end", iid=iid, values=(rel,))
        self._on_sheet_select()
        self._refresh_regions_list()



    def _on_sheet_select(self, event=None):
        selection = self.sheets_tree.selection()
        if not selection:
            self.selected_image_var.set("(yok)")
            self.image_canvas.delete("all")
            return
        iid = selection[0]
        rel = self._index_to_path.get(iid)
        if not rel:
            self.selected_image_var.set("(yok)")
            self.image_canvas.delete("all")
            return
        self.selected_image_var.set(rel)
        self._load_image(rel)

    def _load_image(self, rel_path: str):
        self.image_canvas.delete("all")
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        abs_path = os.path.join(project_root, rel_path)
        if os.path.exists(abs_path):
            image = Image.open(abs_path)
            self._display_image_on_canvas(self.image_canvas, image, *self._main_preview_max)

    def _add_sheet(self):
        messagebox.showinfo("Bilgi", "Bu sekmede varlık yönetimi devre dışı. Yalnızca seçim yapılır.")

    def _delete_sheet(self):
        messagebox.showinfo("Bilgi", "Bu sekmede silme işlemi devre dışı.")

    def _open_cropper(self, event=None):
        selection = self.sheets_tree.selection()
        if not selection:
            return
        iid = selection[0]
        rel = self._index_to_path.get(iid)
        if not rel:
            return
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        abs_path = os.path.join(project_root, rel)
        if not os.path.exists(abs_path):
            messagebox.showwarning("Uyarı", "Dosya bulunamadı.")
            return
        cropper = Cropper(self.frame, abs_path)
        result = cropper.show()
        if result:
            # prompt for a region name
            from tkinter.simpledialog import askstring
            name = askstring("İsim", "Sprite adı:", parent=self.frame)
            if not name:
                return
            try:
                # Save to DB
                self.sprite_service.upsert_sprite_region(rel, name.strip(), result)
                messagebox.showinfo("Kayıt", "Sprite bölgesi kaydedildi.")
            except Exception as e:
                messagebox.showerror("Hata", f"Kaydedilemedi: {e}")
            finally:
                self._refresh_regions_list()

    def _auto_detect_buttons(self) -> None:
        """Seçili görselde yatay dizilmiş butonları otomatik tespit eder ve kaydetmeden önce kullanıcıya inceletir.

        Akış:
        - Seçili görseli alır (soldaki liste).
        - Kullanıcıdan kök ad (örn. "buton") ve buton sayısı (varsayılan 10) ister.
        - Görseli N eşit dilime böler, her dilimde alfa kanalından bbox çıkarır.
        - Kullanıcının ilk kabul/editle ettiği bölgeyi REFERANS kabul eder.
        - Sonraki bölgelerde, referansın yüksekliği ve dikey hizasını koruyarak,
          segment veya alfa merkezine göre kutuyu yatayda konumlandırır (rehberli tespit).
        - Her öneri için önizleme penceresi açar: Kabul, Editle (Cropper), Atla.
        - Kabul veya editle sonrası `sprite_service.upsert_sprite_region` ile kaydeder ve sıralı ad verir.
        """
        try:
            selection = self.sheets_tree.selection()
            if not selection:
                messagebox.showinfo("Otomatik Tespit", "Önce soldan bir görsel seçiniz.")
                return
            iid = selection[0]
            rel = self._index_to_path.get(iid)
            if not rel:
                messagebox.showwarning("Uyarı", "Görsel yolu alınamadı.")
                return
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
            abs_path = os.path.join(project_root, rel)
            if not os.path.isfile(abs_path):
                messagebox.showwarning("Uyarı", "Dosya bulunamadı.")
                return
            from tkinter.simpledialog import askstring
            base = askstring("Kök Ad", "İsim kökü (örn. buton):", initialvalue="buton", parent=self.frame)
            if not base:
                return
            count_str = askstring("Buton Sayısı", "Tahmini buton sayısı (opsiyonel):", initialvalue="", parent=self.frame)
            try:
                n_hint = int(count_str) if count_str else None
            except Exception:
                n_hint = None

            # Görseli aç ve RGBA'ya çevir
            img = Image.open(abs_path).convert("RGBA")
            iw, ih = img.size

            # Projeksiyon tabanlı ham tespit (satır/sütun bantları)
            raw_props = self._detect_by_projections(img)
            # İsteğe bağlı: kullanıcı bir sayı girdiyse ilk n adet ile sınırla
            if n_hint is not None and n_hint > 0:
                raw_props = raw_props[:n_hint]

            if not raw_props:
                messagebox.showinfo("Otomatik Tespit", "Uygun bölge bulunamadı.")
                return

            # Tam ekran overlay aç ve ilk ham önerileri çiz
            try:
                self._open_detection_overlay(abs_path, iw, ih)
                self._render_detection_overlay(raw_props, iw, ih)
            except Exception:
                pass

            # Rehberli tespit: kullanıcı referansı ile hizalama
            ref_box: Optional[dict] = None  # {'x','y','width','height'}
            saved = 0
            for rp in raw_props:
                # Referans uygula: varsa aynı yükseklik ve y, yatayda merkezle
                guided = dict(rp)
                if ref_box and ref_box.get("width", 0) > 0 and ref_box.get("height", 0) > 0:
                    # Yükseklik referanstan alınır; Y, bandın ortasına referans yüksekliği merkezlenerek oturtulur
                    guided_h = int(ref_box["height"])  # type: ignore[index]
                    row_y1 = int(rp.get('row_y1', 0)); row_y2 = int(rp.get('row_y2', ih))
                    band_cy = (row_y1 + row_y2) // 2
                    guided_y = int(band_cy - guided_h // 2)
                    # X merkezini ham bbox merkezinden al; yoksa sütun merkezini kullan
                    col_x1 = int(rp.get('col_x1', rp.get('seg_x1', 0)))
                    col_x2 = int(rp.get('col_x2', rp.get('seg_x2', iw)))
                    if rp.get("width", 0) > 0:
                        cx = rp["x"] + rp["width"] // 2
                    else:
                        cx = (col_x1 + col_x2) // 2
                    guided_w = int(ref_box["width"])   # type: ignore[index]
                    guided_x = int(cx - guided_w // 2)
                    guided = {
                        "x": guided_x,
                        "y": guided_y,
                        "width": guided_w,
                        "height": guided_h,
                        "index": rp["index"],
                    }
                    # Kolon bandına yatay kısıtlama (taşmayı ve üstüste binmeyi önle)
                    cx1 = int(rp.get('col_x1', guided['x']))
                    cx2 = int(rp.get('col_x2', guided['x'] + guided['width']))
                    if cx2 > cx1:
                        if guided['x'] < cx1:
                            guided['x'] = cx1
                        if guided['x'] + guided['width'] > cx2:
                            guided['width'] = max(1, cx2 - guided['x'])
                # Sınırları kısıtla
                guided = self._clamp_bbox(guided, iw, ih)

                action, edited = self._review_region_dialog(abs_path, guided)
                if action == "accept":
                    final_box = guided
                    name = f"{base}_{guided['index']}"
                    try:
                        self.sprite_service.upsert_sprite_region(rel, name, final_box)
                        saved += 1
                    except Exception as e:
                        messagebox.showerror("Hata", f"Kaydedilemedi: {e}")
                    # Referansı güncelle
                    ref_box = final_box
                    # Overlay'i güncelle: mevcut referansa göre tüm kutuları yeniden çiz
                    try:
                        all_guided = [self._clamp_bbox(self._apply_ref_on_raw(r, ref_box, iw, ih), iw, ih) for r in raw_props]
                        self._render_detection_overlay(all_guided, iw, ih)
                    except Exception:
                        pass
                elif action == "edit" and edited:
                    name = f"{base}_{guided['index']}"
                    try:
                        self.sprite_service.upsert_sprite_region(rel, name, edited)
                        saved += 1
                    except Exception as e:
                        messagebox.showerror("Hata", f"Kaydedilemedi: {e}")
                    # Referansı güncelle (kullanıcının düzenlediği kutu en iyi referanstır)
                    ref_box = edited
                    try:
                        all_guided = [self._clamp_bbox(self._apply_ref_on_raw(r, ref_box, iw, ih), iw, ih) for r in raw_props]
                        self._render_detection_overlay(all_guided, iw, ih)
                    except Exception:
                        pass
                # skip -> hiçbir şey yapma

            if saved > 0:
                self._refresh_regions_list()
                messagebox.showinfo("Otomatik Tespit", f"{saved} sprite kaydedildi.")
            # Overlay'i kapat
            try:
                self._close_detection_overlay()
            except Exception:
                pass
        except Exception as e:
            try:
                messagebox.showerror("Hata", f"Otomatik tespit başarısız: {e}")
            except Exception:
                pass

    def _apply_ref_on_raw(self, rp: dict, ref_box: Optional[dict], iw: int, ih: int) -> dict:
        """Ham kutuya referans hizalamayı uygular; referans yoksa hamı döndürür.

        Y, ilgili satır bandının ortasına referans yüksekliği merkezlenerek yerleştirilir; X, ham bbox/kolon merkezinden alınır.
        """
        guided = dict(rp)
        if ref_box and ref_box.get("width", 0) > 0 and ref_box.get("height", 0) > 0:
            guided_h = int(ref_box["height"])  # type: ignore[index]
            row_y1 = int(rp.get('row_y1', 0)); row_y2 = int(rp.get('row_y2', ih))
            band_cy = (row_y1 + row_y2) // 2
            guided_y = int(band_cy - guided_h // 2)
            col_x1 = int(rp.get('col_x1', rp.get('seg_x1', 0)))
            col_x2 = int(rp.get('col_x2', rp.get('seg_x2', iw)))
            if rp.get("width", 0) > 0:
                cx = rp["x"] + rp["width"] // 2
            else:
                cx = (col_x1 + col_x2) // 2
            guided_w = int(ref_box["width"])   # type: ignore[index]
            guided_x = int(cx - guided_w // 2)
            guided = {
                "x": guided_x,
                "y": guided_y,
                "width": guided_w,
                "height": guided_h,
                "index": rp.get("index"),
            }
            # Kolon bandına yatay kısıtlama
            cx1 = int(rp.get('col_x1', guided['x']))
            cx2 = int(rp.get('col_x2', guided['x'] + guided['width']))
            if cx2 > cx1:
                if guided['x'] < cx1:
                    guided['x'] = cx1
                if guided['x'] + guided['width'] > cx2:
                    guided['width'] = max(1, cx2 - guided['x'])
        return guided

    def _detect_by_projections(self, img: Image.Image) -> List[dict]:
        """Alfa projeksiyonları ile satır ve sütun bantlarını bularak ham kutular döndürür.

        Dönüş: [{'x','y','width','height','index','row_y1','row_y2','col_x1','col_x2'}]
        Sıralama: üstten alta, soldan sağa.
        """
        iw, ih = img.size
        alpha = img.split()[3] if img.mode == 'RGBA' else img.convert('L')
        px = alpha.load()
        # 1) Yatay bantlar (satırlar)
        bands: List[tuple[int,int]] = []
        in_band = False; band_start = 0
        for y in range(ih):
            row_has = False
            for x in range(iw):
                if px[x, y] > 0:
                    row_has = True; break
            if row_has and not in_band:
                in_band = True; band_start = y
            elif not row_has and in_band:
                if y - band_start >= 8:  # min yükseklik filtresi
                    bands.append((band_start, y))
                in_band = False
        if in_band:
            if ih - band_start >= 8:
                bands.append((band_start, ih))

        props: List[dict] = []
        # 2) Her bant içinde dikey kolon kümeleri
        for (y1, y2) in bands:
            # Dikey projeksiyon
            col_on = [False]*iw
            for x in range(iw):
                any_on = False
                for y in range(y1, y2):
                    if px[x, y] > 0:
                        any_on = True; break
                col_on[x] = any_on
            # x aralıklarını çıkar (dar boşlukları birleştir)
            gap_max = max(12, iw // 50)  # görsele göre ~%2 veya en az 12px
            in_col = False; cx1 = 0; gap_run = 0
            cols: List[tuple[int,int]] = []
            for x in range(iw):
                if col_on[x]:
                    if not in_col:
                        in_col = True; cx1 = x; gap_run = 0
                    else:
                        gap_run = 0  # içerideyken boşluk sıfırlanır
                else:
                    if in_col:
                        gap_run += 1
                        # İçerideyken küçük boşluklar devam ederse sütunu sürdür
                        if gap_run > gap_max:
                            # sütunu kapat
                            end_x = x - gap_run + 1
                            if end_x - cx1 >= 8:  # min genişlik filtresi
                                cols.append((cx1, end_x))
                            in_col = False; gap_run = 0
            # Satır sonu için kapanmamış sütun
            if in_col:
                end_x = iw
                if end_x - cx1 >= 8:
                    cols.append((cx1, end_x))

            # 3) Her sütun aralığında kesin bbox hesapla
            for (x1, x2) in cols:
                # Sınırlı bölgede bbox hesaplamak için küçük bir tarama
                minx, miny, maxx, maxy = x2, y2, x1, y1
                any_pix = False
                for yy in range(y1, y2):
                    for xx in range(x1, x2):
                        if px[xx, yy] > 0:
                            any_pix = True
                            if xx < minx: minx = xx
                            if yy < miny: miny = yy
                            if xx > maxx: maxx = xx
                            if yy > maxy: maxy = yy
                if not any_pix:
                    continue
                w = max(1, maxx - minx + 1); h = max(1, maxy - miny + 1)
                props.append({
                    'x': int(minx), 'y': int(miny), 'width': int(w), 'height': int(h),
                    'row_y1': int(y1), 'row_y2': int(y2), 'col_x1': int(x1), 'col_x2': int(x2),
                })

        # 4) Sırala ve index ver
        props.sort(key=lambda b: (b['y'], b['x']))
        for i, b in enumerate(props, start=1):
            b['index'] = i
        return props

    def _open_detection_overlay(self, abs_image_path: str, iw: int, ih: int) -> None:
        """Tam ekran bir overlay penceresi açar ve sprite sheet'i çizer."""
        win = tk.Toplevel(self.frame)
        try:
            win.attributes('-fullscreen', True)
        except Exception:
            # Fallback: maksimize
            try:
                win.state('zoomed')
            except Exception:
                pass
        win.title("Tespit Önizleme")
        win.transient(self.frame)

        # ESC ile kapat
        win.bind('<Escape>', lambda e: self._close_detection_overlay())

        # Ekran boyutu ve ölçek
        sw = win.winfo_screenwidth(); sh = win.winfo_screenheight()
        scale = min(sw / max(1, iw), sh / max(1, ih))
        cw = int(iw * scale); ch = int(ih * scale)

        canvas = tk.Canvas(win, width=cw, height=ch, background='black', highlightthickness=0)
        canvas.pack(fill='both', expand=True)

        # Görseli ölçekle ve çiz
        pil = Image.open(abs_image_path).convert('RGBA')
        pil_rz = pil.resize((cw, ch), Image.LANCZOS)
        photo = ImageTk.PhotoImage(pil_rz)
        canvas.create_image(0, 0, anchor='nw', image=photo)

        # Referansları sakla
        self._det_overlay = {
            'win': win,
            'canvas': canvas,
            'scale': scale,
            'photo': photo,
        }

    def _render_detection_overlay(self, boxes: List[dict], iw: int, ih: int) -> None:
        """Overlay'de kutuları kesik çizgi ve numara ile çizer."""
        ov = getattr(self, '_det_overlay', None)
        if not ov:
            return
        canvas = ov['canvas']; scale = ov['scale']
        # Önce önceki overlay çizimlerini temizle (arka plan resmini korumak için tümünü silip resmi tekrar çizmek yerine kutuları tag ile yönet)
        try:
            canvas.delete('ov')
        except Exception:
            pass
        for b in boxes:
            try:
                x = int(b.get('x', 0)); y = int(b.get('y', 0))
                w = int(b.get('width', 0)); h = int(b.get('height', 0))
                idx = int(b.get('index', 0))
                sx = int(x * scale); sy = int(y * scale)
                ex = int((x + w) * scale); ey = int((y + h) * scale)
                canvas.create_rectangle(sx, sy, ex, ey, outline='#FF5252', width=2, dash=(6, 4), tags=('ov',))
                canvas.create_text(sx + 4, sy + 4, text=str(idx), anchor='nw', fill='#FFF176', font=('TkDefaultFont', 14, 'bold'), tags=('ov',))
            except Exception:
                continue

    def _close_detection_overlay(self) -> None:
        ov = getattr(self, '_det_overlay', None)
        if ov and ov.get('win'):
            try:
                ov['win'].destroy()
            except Exception:
                pass
        self._det_overlay = None

    def _clamp_bbox(self, box: dict, iw: int, ih: int) -> dict:
        """Bbox'ı görüntü boyutlarına kısıtlar ve negatifleri düzeltir.

        Args:
            box: {'x','y','width','height', 'index'?}
            iw: image width
            ih: image height
        Returns:
            Yeni kısıtlanmış sözlük.
        """
        try:
            x = int(box.get('x', 0)); y = int(box.get('y', 0))
            w = int(max(1, box.get('width', 1))); h = int(max(1, box.get('height', 1)))
            if x < 0:
                w += x; x = 0
            if y < 0:
                h += y; y = 0
            if x + w > iw:
                w = max(1, iw - x)
            if y + h > ih:
                h = max(1, ih - y)
            out = {"x": x, "y": y, "width": w, "height": h}
            if 'index' in box:
                out['index'] = box['index']
            return out
        except Exception:
            return box

    def _review_region_dialog(self, abs_image_path: str, region: dict) -> tuple[str, Optional[dict]]:
        """Önerilen bir bölge için küçük inceleme penceresi açar.

        Parametreler:
        - abs_image_path: İncelenecek görselin mutlak yolu.
        - region: {'x','y','width','height'} anahtarlarını içeren sözlük.

        Dönüş:
        - ("accept"|"edit"|"skip", edited_region or None)
        """
        # Küçük önizleme üret
        try:
            pil = Image.open(abs_image_path)
            x = int(region.get('x', 0)); y = int(region.get('y', 0))
            w = int(region.get('width', 0)); h = int(region.get('height', 0))
            crop = pil.crop((x, y, x + w, y + h)) if (w > 0 and h > 0) else pil
        except Exception:
            crop = None

        dlg = tk.Toplevel(self.frame)
        dlg.title("Öneri İncele")
        dlg.transient(self.frame)
        dlg.grab_set()

        wrap = ttk.Frame(dlg, padding=8)
        wrap.pack(fill="both", expand=True)

        if crop is not None:
            # küçük önizleme 220x160
            tw, th = 220, 160
            try:
                scale = min(tw / max(1, crop.width), th / max(1, crop.height))
                rz = (max(1, int(crop.width * scale)), max(1, int(crop.height * scale)))
                prev = crop.resize(rz, Image.LANCZOS)
                photo = ImageTk.PhotoImage(prev)
                lbl = ttk.Label(wrap, image=photo)
                lbl.image = photo  # referans
                lbl.pack()
            except Exception:
                ttk.Label(wrap, text="Önizleme yüklenemedi").pack()
        else:
            ttk.Label(wrap, text="Önizleme yok").pack()

        btns = ttk.Frame(wrap)
        btns.pack(fill="x", pady=(6,0))

        result = {"action": "skip", "edited": None}

        def do_accept():
            result["action"] = "accept"
            dlg.destroy()

        def do_edit():
            # Tam görselde Cropper aç
            cropper = Cropper(self.frame, abs_image_path)
            r = cropper.show()
            if r:
                result["action"] = "edit"
                result["edited"] = {k: int(v) for k, v in r.items()}
            dlg.destroy()

        def do_skip():
            result["action"] = "skip"
            dlg.destroy()

        ttk.Button(btns, text="Kabul", command=do_accept).pack(side=tk.RIGHT)
        ttk.Button(btns, text="Editle", command=do_edit).pack(side=tk.RIGHT, padx=6)
        ttk.Button(btns, text="Atla", command=do_skip).pack(side=tk.RIGHT)

        dlg.wait_window()
        return result["action"], result["edited"]

    
    def _refresh_definitions(self):
        return

    def _assign_expression(self):
        return

    def _refresh_expressions(self):
        return

    def _update_assign_button_state(self):
        return

    # ------- Level assets UI logic -------
    def _refresh_levels(self):
        return

    def _get_selected_level(self):
        if not self.levels_cache:
            return None
        idx = self.level_sel.current()
        if idx < 0 or idx >= len(self.levels_cache):
            return None
        return self.levels_cache[idx]

    def _load_level_assets(self):
        return

    def _browse_level_bg(self):
        return

    def _select_paddle_region(self):
        return

    def _save_level_assets(self):
        return

    # ------- End screens UI logic -------
    def _load_end_screens(self):
        return

    def _browse_win_bg(self):
        return

    def _browse_lose_bg(self):
        return

    def _save_end_screens(self):
        return

    # ------- Helpers -------
    def _sanitize_filename(self, name: str) -> str:
        return name

    def _avoid_collision(self, directory: str, filename: str) -> str:
        return os.path.join(directory, filename)

    def _resize_and_copy_image(self, src_path: str, dst_dir: str, enable_scale: bool, w_str: str, h_str: str, keep_ratio: bool) -> str:
        return src_path

    # -------- Assets scanning --------
    def _scan_assets_images(self) -> List[str]:
        """Recursively scan only assets/images/sprites/ for image files.

        Returns relative paths from project root using forward slashes.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        sprites_root = os.path.join(project_root, "assets", "images", "sprites")
        img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}

        def walk_collect(base_dir: str) -> List[str]:
            items: List[str] = []
            if os.path.isdir(base_dir):
                for root, _, fnames in os.walk(base_dir):
                    for fn in fnames:
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in img_exts:
                            abs_p = os.path.join(root, fn)
                            rel = os.path.relpath(abs_p, project_root).replace('\\', '/')
                            items.append(rel)
            return items

        images: List[str] = walk_collect(sprites_root)
        # de-duplicate preserving order
        seen = set(); out = []
        for p in images:
            if p not in seen:
                seen.add(p); out.append(p)
        return sorted(out, key=lambda p: p.lower())

    # -------- Sprite regions UI (DB-backed) --------

    # -------- Regions UI helpers --------
    def _refresh_regions_list(self) -> None:
        for iid in self.regions_tree.get_children():
            self.regions_tree.delete(iid)
        self._regions_cache = []
        rows = self.sprite_service.list_sprite_regions()
        self._regions_cache = rows
        for i, e in enumerate(rows):
            name = e.get("name", "?")
            img = e.get("image_path", "")
            coords = f"{e.get('x',0)}, {e.get('y',0)}, {e.get('width',0)}, {e.get('height',0)}"
            iid = str(i)
            self.regions_tree.insert("", tk.END, iid=iid, values=(name, img, coords))
        # Liste yenilendikten sonra küçük önizlemeyi güncelle
        self._update_region_preview()

    def _update_region_preview(self) -> None:
        """Seçili sprite bölgesini küçük önizleme alanında göster."""
        self.region_canvas.delete("all")
        entry = self._get_selected_region_entry()
        if not entry:
            return
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        abs_path = os.path.join(project_root, entry.get("image_path", ""))
        if not os.path.isfile(abs_path):
            return
        try:
            img = Image.open(abs_path)
            x = int(entry.get('x', 0)); y = int(entry.get('y', 0))
            w = int(entry.get('width', 0)); h = int(entry.get('height', 0))
            if w > 0 and h > 0:
                img = img.crop((x, y, x + w, y + h))
            self._display_image_on_canvas(self.region_canvas, img, *self._region_preview_max)
        except Exception:
            pass

    def _display_image_on_canvas(self, canvas: tk.Canvas, pil_image: Image.Image, max_w: int, max_h: int) -> None:
        """PIL görüntüyü orana sadık kalarak belirtilen alana sığdırıp canvas'a çizer."""
        try:
            iw, ih = pil_image.size
            scale = min(max_w / max(1, iw), max_h / max(1, ih))
            new_w = max(1, int(iw * scale))
            new_h = max(1, int(ih * scale))
            resized = pil_image.resize((new_w, new_h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(resized)
            # Canvas boyutunu sabit tut (görsel merkezli)
            canvas.configure(width=max_w, height=max_h)
            x = (max_w - new_w) // 2
            y = (max_h - new_h) // 2
            canvas.create_image(x, y, anchor="nw", image=photo)
            # Referansı sakla; aksi halde GC edilir
            if canvas is self.image_canvas:
                self.tk_image = photo
            elif canvas is self.region_canvas:
                self.tk_region_image = photo
        except Exception:
            pass

    def _get_selected_region_entry(self) -> Optional[Dict]:
        sel = self.regions_tree.selection()
        if not sel:
            return None
        idx = int(sel[0])
        lst = getattr(self, '_regions_cache', []) or []
        if 0 <= idx < len(lst):
            return lst[idx]
        return None

    def _rename_region(self) -> None:
        entry = self._get_selected_region_entry()
        if not entry:
            return
        from tkinter.simpledialog import askstring
        new_name = askstring("Yeniden Adlandır", "Yeni ad:", initialvalue=entry.get("name",""), parent=self.frame)
        if not new_name:
            return
        self.sprite_service.rename_sprite_region(entry.get("image_path",""), entry.get("name",""), new_name.strip())
        self._refresh_regions_list()

    def _delete_region(self) -> None:
        entry = self._get_selected_region_entry()
        if not entry:
            return
        if not messagebox.askyesno("Onay", f"'{entry.get('name','?')}' silinsin mi?"):
            return
        self.sprite_service.delete_sprite_region(entry.get("image_path",""), entry.get("name",""))
        self._refresh_regions_list()

    def _recrop_region(self) -> None:
        entry = self._get_selected_region_entry()
        if not entry:
            return
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        abs_path = os.path.join(project_root, entry.get("image_path",""))
        if not os.path.isfile(abs_path):
            messagebox.showwarning("Uyarı", "Görsel bulunamadı.")
            return
        cropper = Cropper(self.frame, abs_path)
        result = cropper.show()
        if result:
            # overwrite coords
            self.sprite_service.upsert_sprite_region(entry.get("image_path",""), entry.get("name",""), result)
            self._refresh_regions_list()

    def _debug_regions_check(self) -> None:
        """DB'deki sprite_regions kayıtlarını ve dosya yollarını kontrol edip özetler.

        - Kayıt sayısı, mevcut dosya sayısı, eksik dosya sayısı
        - Olası yol uyumsuzlukları: 'assets/' prefix eksik/fazla
        - Detaylar konsola yazdırılır.
        """
        try:
            rows = self.sprite_service.list_sprite_regions()
        except Exception as e:
            messagebox.showerror("Debug", f"DB okunamadı: {e}")
            return
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        total = len(rows)
        exists_cnt = 0
        missing = []
        fix_suggestions = []
        for r in rows:
            p = r.get("image_path", "")
            abs_p = os.path.join(project_root, p)
            if os.path.isfile(abs_p):
                exists_cnt += 1
                continue
            # try alt with assets/ prefix
            if not p.startswith("assets/"):
                alt = os.path.join(project_root, "assets", p)
                if os.path.isfile(alt):
                    fix_suggestions.append((p, f"assets/{p}"))
            else:
                # maybe extra assets/ added
                no_pref = p[len("assets/"):]
                alt = os.path.join(project_root, no_pref)
                if os.path.isfile(alt):
                    fix_suggestions.append((p, no_pref))
            missing.append(p)
        # Print details to console
        print("[Sprites Debug] total rows=", total)
        print("[Sprites Debug] existing files=", exists_cnt)
        print("[Sprites Debug] missing files=", len(missing))
        for p in missing:
            print("  MISSING:", p)
        if fix_suggestions:
            print("[Sprites Debug] path fix suggestions (stored -> suggested):")
            for a, b in fix_suggestions:
                print("  ", a, "->", b)
        # Messagebox summary
        sample_missing = ", ".join(missing[:3]) if missing else "yok"
        sample_fix = ", ".join([f"{a} -> {b}" for a,b in fix_suggestions[:3]]) if fix_suggestions else "yok"
        message = (
            f"Toplam kayıt: {total}\n"
            f"Mevcut dosya: {exists_cnt}\n"
            f"Eksik dosya: {len(missing)}\n"
            f"Örnek eksik: {sample_missing}\n"
            f"Önerilen yol düzeltmeleri: {sample_fix}\n\n"
            "Detaylar konsola yazdırıldı."
        )
        messagebox.showinfo("Sprite Debug", message)

    # ----- Legacy metadata migration (one-time) -----
    def _metadata_path(self) -> str:
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        return os.path.join(project_root, "assets", "metadata.json")

    def _read_metadata_sprite_regions(self) -> List[Dict]:
        path = self._metadata_path()
        if not os.path.isfile(path):
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            lst = data.get("sprite_regions") or []
            # Normalize keys 'image' -> 'image_path'
            out: List[Dict] = []
            for e in lst:
                img = e.get("image") or e.get("image_path")
                if img and all(k in e for k in ("x","y","width","height")):
                    out.append({
                        "image_path": img,
                        "name": e.get("name", ""),
                        "x": int(e["x"]),
                        "y": int(e["y"]),
                        "width": int(e["width"]),
                        "height": int(e["height"]),
                    })
            return out
        except Exception:
            return []

