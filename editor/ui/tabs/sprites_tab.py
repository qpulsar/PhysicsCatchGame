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
import json
import unicodedata
import numpy as np
from PIL import Image, ImageDraw, ImageChops, ImageFilter

from ...core.models import Sprite, SpriteDefinition, Expression
from ...core.services import SpriteService, ExpressionService, LevelService, GameService
from ...utils import get_project_root, pil_to_tkphoto

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
        self.tk_image = pil_to_tkphoto(self.image)

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
        # Debug & refresh controls
        ttk.Button(button_frame, text="Yenile", command=self.refresh).pack(side=tk.RIGHT)
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
        # Ana görsel için dinamik büyüyen canvas
        self._main_preview_max = (800, 500)
        self.image_canvas = tk.Canvas(viewer_frame, background="white")
        self.image_canvas.pack(fill="both", expand=True)
        self.image_canvas.bind("<Double-1>", self._open_cropper)
        self.image_canvas.bind("<Configure>", lambda e: self._on_canvas_resize())

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
        project_root = get_project_root()
        abs_path = os.path.join(project_root, rel_path)
        if os.path.exists(abs_path):
            image = Image.open(abs_path)
            # Kanvasın o anki boyutunu al ve ona göre ölçekle
            self.image_canvas.update_idletasks()
            cw = self.image_canvas.winfo_width()
            ch = self.image_canvas.winfo_height()
            if cw < 50: cw, ch = self._main_preview_max
            self._display_image_on_canvas(self.image_canvas, image, cw, ch)

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
        project_root = get_project_root()
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
        - Görseldeki bağlantılı bileşenleri (objeleri) alfa kanalı üzerinden otomatik tespit eder.
        - Kullanıcıdan kök ad (örn. "buton") ve buton sayısı (varsayılan 10) ister.
        - Akıllı tespit (Flood-fill) ile her bir bağımsız sprite'ı bulur.
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
            project_root = get_project_root()
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

            # Akıllı bağlantılı bileşen tespiti (Flood-fill + BBox)
            raw_props = self._detect_smart(img)
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

            # Tespit edilen bölgeleri tek tek kullanıcıya onaya sun
            saved = 0
            for rp in raw_props:
                # Akıllı tespit sonucunu kullan (herhangi bir referansa zorlama yapma)
                current_box = self._clamp_bbox(dict(rp), iw, ih)

                action, edited = self._review_region_dialog(abs_path, current_box)
                if action == "accept":
                    final_box = current_box
                    name = f"{base}_{rp['index']}"
                    try:
                        self.sprite_service.upsert_sprite_region(rel, name, final_box)
                        saved += 1
                    except Exception as e:
                        messagebox.showerror("Hata", f"Kaydedilemedi: {e}")
                elif action == "edit" and edited:
                    name = f"{base}_{rp['index']}"
                    try:
                        self.sprite_service.upsert_sprite_region(rel, name, edited)
                        saved += 1
                    except Exception as e:
                        messagebox.showerror("Hata", f"Kaydedilemedi: {e}")
                elif action == "skip":
                    continue
                elif action == "cancel":
                    break

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


    def _detect_smart(self, img: Image.Image) -> List[dict]:
        """Alpha kanalı üzerinden bağlantılı bileşenleri tespit eder ve birbirine çok yakın kutuları birleştirir.
        
        Gelişmiş Özellikler:
        - Morfolojik Kapanma: Küçük boşlukları ve kopuk parçaları (parıltı vb.) birleştirir.
        - Kutu Birleştirme: İç içe geçen veya birbirine değen bboxes'ları tek bir sprite olarak gruplar.
        """
        iw, ih = img.size
        # 1. Alfa maskesini al
        if img.mode == 'RGBA':
            alpha = img.split()[3]
        else:
            alpha = img.convert('L')
        
        # Eşikleme (Threshold)
        mask = alpha.point(lambda p: 255 if p > 35 else 0)
        
        # --- MORFOLOJİK İŞLEM: CLOSING ---
        # Yakın parçaları birleştirmek için maskeyi biraz genişletip geri daraltıyoruz
        # Bu, 'glow' veya 'parçacıklar' gibi kopuk duran kısımları ana gövdeye bağlar.
        dilated = mask.filter(ImageFilter.MaxFilter(7)) # 7x7 genişletme
        closed = dilated.filter(ImageFilter.MinFilter(5)) # 5x5 daraltma (net sonuç: +2px genişleme)
        
        bboxes = []
        work_mask = closed.copy()
        
        # 2. Bağlantılı Bileşen Tespiti (Flood-fill)
        while True:
            curr_bbox = work_mask.getbbox()
            if not curr_bbox: break
            
            start_pixel = None
            found = False
            for y in range(curr_bbox[1], curr_bbox[3]):
                for x in range(curr_bbox[0], curr_bbox[2]):
                    if work_mask.getpixel((x, y)) > 0:
                        start_pixel = (x, y)
                        found = True
                        break
                if found: break
            if not start_pixel: break
            
            # Bileşeni çıkar
            comp_mask = work_mask.copy()
            ImageDraw.floodfill(work_mask, start_pixel, 0)
            single_comp = ImageChops.subtract(comp_mask, work_mask)
            
            # Orijinal alfa kanalı üzerinde bu bileşenin gerçek sınırlarını bulalım
            # Çünkü morfolojik işlem maskeyi biraz büyütmüş olabilir.
            b = single_comp.getbbox()
            if b:
                # Orijinal maskeden bu bölgeyi kırpıp gerçek bbox alalım
                actual_crop = mask.crop(b)
                actual_bbox = actual_crop.getbbox()
                if actual_bbox:
                    # Koordinatları orijinal resme göre offsetle
                    final_b = (
                        b[0] + actual_bbox[0],
                        b[1] + actual_bbox[1],
                        b[0] + actual_bbox[2],
                        b[1] + actual_bbox[3]
                    )
                    w = final_b[2] - final_b[0]
                    h = final_b[3] - final_b[1]
                    if w > 4 and h > 4:
                        bboxes.append([final_b[0], final_b[1], final_b[2], final_b[3]])
        
        # 3. KUTU BİRLEŞTİRME (Merging Overlapping/Intersecting Bboxes)
        # Bazen morfolojik işlem yetmezse, iç içe geçen kutuları manuel birleştiriyoruz.
        def get_iou_or_overlap(b1, b2):
            # Eğer biri diğerinin içindeyse veya çok yakınsa True
            # [x1, y1, x2, y2]
            # Biraz tolerans payı ekleyelim (5px)
            t = 5
            intersect_x1 = max(b1[0], b2[0]) - t
            intersect_y1 = max(b1[1], b2[1]) - t
            intersect_x2 = min(b1[2], b2[2]) + t
            intersect_y2 = min(b1[3], b2[3]) + t
            
            if intersect_x2 > intersect_x1 and intersect_y2 > intersect_y1:
                return True
            return False

        changed = True
        while changed:
            changed = False
            new_bboxes = []
            used = [False] * len(bboxes)
            for i in range(len(bboxes)):
                if used[i]: continue
                current = bboxes[i]
                used[i] = True
                for j in range(i + 1, len(bboxes)):
                    if not used[j] and get_iou_or_overlap(current, bboxes[j]):
                        # Birleştir
                        current = [
                            min(current[0], bboxes[j][0]),
                            min(current[1], bboxes[j][1]),
                            max(current[2], bboxes[j][2]),
                            max(current[3], bboxes[j][3])
                        ]
                        used[j] = True
                        changed = True
                new_bboxes.append(current)
            bboxes = new_bboxes

        # Sözlük yapısına dönüştür
        final_props = []
        for b in bboxes:
            final_props.append({
                'x': b[0], 'y': b[1], 'width': b[2]-b[0], 'height': b[3]-b[1]
            })

        # 4. Akıllı Sıralama (Satır bazlı)
        final_props.sort(key=lambda b: b['y'])
        
        final_sorted = []
        if final_props:
            rows = []
            curr_row = [final_props[0]]
            for i in range(1, len(final_props)):
                prev = curr_row[-1]
                curr = final_props[i]
                if curr['y'] < prev['y'] + prev['height'] * 0.7:
                    curr_row.append(curr)
                else:
                    rows.append(curr_row)
                    curr_row = [curr]
            rows.append(curr_row)
            
            for r in rows:
                r.sort(key=lambda b: b['x'])
                final_sorted.extend(r)
        
        for i, b in enumerate(final_sorted, start=1):
            b['index'] = i
            b['row_y1'] = b['y']
            b['row_y2'] = b['y'] + b['height']
            b['col_x1'] = b['x']
            b['col_x2'] = b['x'] + b['width']
            
        return final_sorted

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
        photo = pil_to_tkphoto(pil_rz)
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
                photo = pil_to_tkphoto(prev)
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
        project_root = get_project_root()
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
        project_root = get_project_root()
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

    def _on_canvas_resize(self):
        """Pencere/Kanvas boyutu değiştiğinde önizlemeyi gecikmeli (debounce) günceller."""
        if hasattr(self, "_resize_timer"):
            self.frame.after_cancel(self._resize_timer)
        self._resize_timer = self.frame.after(200, self._perform_delayed_resize)

    def _perform_delayed_resize(self):
        """Asıl boyutlandırma işlemini yapar."""
        selection = self.sheets_tree.selection()
        if not selection:
            return
        iid = selection[0]
        rel = self._index_to_path.get(iid)
        if rel:
            self._load_image(rel)

    def _display_image_on_canvas(self, canvas: tk.Canvas, pil_image: Image.Image, max_w: int, max_h: int) -> None:
        """PIL görüntüyü orana sadık kalarak belirtilen alana sığdırıp (stretch yapmadan) canvas'a çizer."""
        try:
            canvas.delete("all")
            # 1. Gradient arkaplanı çiz
            self._draw_gradient_background(canvas, max_w, max_h)
            
            # 2. Resmi ölçekle (sadece gerekliyse küçült, asla büyütme/stretch yapma)
            iw, ih = pil_image.size
            scale = min(max_w / max(1, iw), max_h / max(1, ih))
            if scale > 1.0: scale = 1.0 # Stretch yapma, orijinal boyutu koru
            
            new_w = max(1, int(iw * scale))
            new_h = max(1, int(ih * scale))
            resized = pil_image.resize((new_w, new_h), Image.LANCZOS)
            photo = pil_to_tkphoto(resized)
            
            # Ortala
            canvas.create_image(max_w//2, max_h//2, anchor="center", image=photo)
            
            # Referansı sakla; aksi halde GC edilir
            if canvas is self.image_canvas:
                self.tk_image = photo
            elif canvas is self.region_canvas:
                self.tk_region_image = photo
        except Exception:
            pass

    def _draw_gradient_background(self, canvas: tk.Canvas, w: int, h: int) -> None:
        """Belirtilen kanvasa şık bir koyu gradient çizer."""
        if w < 10 or h < 10: return
        
        top_color = (45, 49, 58)    # Koyu gri
        bottom_color = (20, 22, 26) # Siyahımsı
        
        grad_img = Image.new('RGB', (1, h))
        for y in range(h):
            r = int(top_color[0] + (bottom_color[0] - top_color[0]) * (y / h))
            g = int(top_color[1] + (bottom_color[1] - top_color[1]) * (y / h))
            b = int(top_color[2] + (bottom_color[2] - top_color[2]) * (y / h))
            grad_img.putpixel((0, y), (r, g, b))
            
        full_bg = grad_img.resize((w, h), Image.LANCZOS)
        photo = pil_to_tkphoto(full_bg)
        canvas.create_image(0, 0, anchor="nw", image=photo)
        
        # Referansı sakla (GC önlemi)
        if canvas is self.image_canvas:
            self.tk_grad_main = photo
        else:
            self.tk_grad_region = photo

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
        project_root = get_project_root()
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
        project_root = get_project_root()
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
        project_root = get_project_root()
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

