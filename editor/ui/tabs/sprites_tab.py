"""Tab for managing sprite sheets and their definitions."""
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
    """The main UI for sprite management."""
    def __init__(self, parent, sprite_service: SpriteService, expression_service: ExpressionService, level_service: LevelService, game_service: GameService):
        self.parent = parent
        self.sprite_service = sprite_service
        self.expression_service = expression_service # To get expressions
        self.level_service = level_service
        self.game_service = game_service
        self.current_game_id = None
        self.selected_sprite_sheet: Optional[Sprite] = None
        self.tk_image = None
        self.sprite_definitions: List[SpriteDefinition] = []
        self.expressions_index: Dict[int, str] = {}
        self.expr_label_to_id: Dict[str, int] = {}
        self.last_crop_coords: Optional[Dict[str, int]] = None
        self.levels_cache: List = []
        self.sheets_cache: List[Sprite] = []

        self.frame = ttk.Frame(parent)
        self.frame.rowconfigure(0, weight=1)
        self.frame.columnconfigure(0, weight=1)

        self.paned_window = ttk.PanedWindow(self.frame, orient=tk.HORIZONTAL)
        self.paned_window.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)

        # Left Pane: Sprite Sheet List
        left_pane = self._create_left_pane()
        self.paned_window.add(left_pane, weight=1)

        # Right Pane: Sprite Sheet Viewer and Definitions
        right_pane = self._create_right_pane()
        self.paned_window.add(right_pane, weight=3)

    def _create_left_pane(self) -> ttk.Frame:
        pane = ttk.Frame(self.paned_window)
        pane.rowconfigure(0, weight=1)
        pane.columnconfigure(0, weight=1)

        # Sprite Sheet List
        list_frame = ttk.LabelFrame(pane, text="Sprite Sheets", padding=5)
        list_frame.grid(row=0, column=0, sticky="nsew", pady=5)
        list_frame.rowconfigure(0, weight=1)
        list_frame.columnconfigure(0, weight=1)

        self.sheets_tree = ttk.Treeview(list_frame, columns=("name",), show="headings", selectmode="browse")
        self.sheets_tree.heading("name", text="Ad")
        self.sheets_tree.grid(row=0, column=0, sticky="nsew")
        self.sheets_tree.bind("<<TreeviewSelect>>", self._on_sheet_select)

        # Buttons
        button_frame = ttk.Frame(pane)
        button_frame.grid(row=1, column=0, sticky="ew", pady=(5,0))
        ttk.Button(button_frame, text="Assets'e Ekle", command=self._add_sheet).pack(side=tk.LEFT, padx=2)
        self.delete_sheet_button = ttk.Button(button_frame, text="Sil", command=self._delete_sheet, state="disabled")
        self.delete_sheet_button.pack(side=tk.LEFT, padx=2)
        
        return pane

    def _create_right_pane(self) -> ttk.Frame:
        pane = ttk.Frame(self.paned_window)
        pane.rowconfigure(0, weight=1)
        pane.columnconfigure(0, weight=1)

        # Viewer Frame
        viewer_frame = ttk.LabelFrame(pane, text="Önizleme", padding=5)
        viewer_frame.grid(row=0, column=0, sticky="nsew", pady=5)
        self.image_canvas = tk.Canvas(viewer_frame, background="white")
        self.image_canvas.pack(fill="both", expand=True)
        self.image_canvas.bind("<Double-1>", self._open_cropper)

        # Selected area label
        sel_frame = ttk.Frame(viewer_frame)
        sel_frame.pack(fill="x", pady=(5,0))
        ttk.Label(sel_frame, text="Seçilen Alan:").pack(side=tk.LEFT)
        self.selected_area_var = tk.StringVar(value="(yok)")
        ttk.Label(sel_frame, textvariable=self.selected_area_var).pack(side=tk.LEFT, padx=5)

        # Definitions Frame
        defs_frame = ttk.LabelFrame(pane, text="Sprite Tanımları", padding=5)
        defs_frame.grid(row=1, column=0, sticky="ew", pady=5)
        defs_frame.columnconfigure(0, weight=1)

        # Treeview for definitions
        self.defs_tree = ttk.Treeview(defs_frame, columns=("expr", "coords"), show="headings")
        self.defs_tree.heading("expr", text="İlişkili İfade")
        self.defs_tree.heading("coords", text="Koordinatlar (x, y, w, h)")
        self.defs_tree.grid(row=0, column=0, sticky="ew")

        # Assign Expression UI
        assign_frame = ttk.Frame(defs_frame)
        assign_frame.grid(row=1, column=0, sticky="ew", pady=5)
        ttk.Label(assign_frame, text="İfade Ata:").pack(side=tk.LEFT)
        self.expr_var = tk.StringVar()
        self.expr_combo = ttk.Combobox(assign_frame, textvariable=self.expr_var, state="readonly")
        self.expr_combo.pack(side=tk.LEFT, padx=5, expand=True, fill="x")
        ttk.Button(assign_frame, text="Bölge Seç", command=self._open_cropper).pack(side=tk.LEFT, padx=5)
        self.assign_button = ttk.Button(assign_frame, text="Ata", command=self._assign_expression, state="disabled")
        self.assign_button.pack(side=tk.LEFT)

        # Level Assets Frame
        level_assets = ttk.LabelFrame(pane, text="Seviye Varlıkları (Arkaplan ve Paddle)", padding=5)
        level_assets.grid(row=2, column=0, sticky="ew", pady=5)
        level_assets.columnconfigure(1, weight=1)

        ttk.Label(level_assets, text="Seviye:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.level_sel_var = tk.StringVar()
        self.level_sel = ttk.Combobox(level_assets, textvariable=self.level_sel_var, state="readonly")
        self.level_sel.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        self.level_sel.bind("<<ComboboxSelected>>", lambda e: self._load_level_assets())

        # Level background selector
        ttk.Label(level_assets, text="Seviye Arkaplanı:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.level_bg_var = tk.StringVar()
        lvl_bg_frame = ttk.Frame(level_assets)
        lvl_bg_frame.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        ttk.Entry(lvl_bg_frame, textvariable=self.level_bg_var, width=32).pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(lvl_bg_frame, text="Seç...", command=self._browse_level_bg).pack(side=tk.LEFT)
        # Level background scaling options
        self.level_scale_enable_var = tk.BooleanVar(value=False)
        self.level_scale_keep_ratio_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(level_assets, text="Yeniden boyutlandır", variable=self.level_scale_enable_var).grid(row=1, column=2, sticky="w")
        lvl_scale_row = ttk.Frame(level_assets)
        lvl_scale_row.grid(row=1, column=3, sticky="w")
        ttk.Label(lvl_scale_row, text="W:").pack(side=tk.LEFT)
        self.level_scale_w_var = tk.StringVar()
        ttk.Entry(lvl_scale_row, textvariable=self.level_scale_w_var, width=6).pack(side=tk.LEFT)
        ttk.Label(lvl_scale_row, text="H:").pack(side=tk.LEFT)
        self.level_scale_h_var = tk.StringVar()
        ttk.Entry(lvl_scale_row, textvariable=self.level_scale_h_var, width=6).pack(side=tk.LEFT)
        ttk.Checkbutton(lvl_scale_row, text="Oran", variable=self.level_scale_keep_ratio_var).pack(side=tk.LEFT)

        # Paddle selection: sheet + region
        ttk.Label(level_assets, text="Paddle Sprite Sheet:").grid(row=2, column=0, sticky="e", padx=5, pady=5)
        self.paddle_sheet_var = tk.StringVar()
        self.paddle_sheet_combo = ttk.Combobox(level_assets, textvariable=self.paddle_sheet_var, state="readonly")
        self.paddle_sheet_combo.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(level_assets, text="Paddle Bölge:").grid(row=3, column=0, sticky="e", padx=5, pady=5)
        paddle_area_frame = ttk.Frame(level_assets)
        paddle_area_frame.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        self.paddle_area_var = tk.StringVar(value="(yok)")
        ttk.Label(paddle_area_frame, textvariable=self.paddle_area_var).pack(side=tk.LEFT)
        ttk.Button(paddle_area_frame, text="Bölge Seç", command=self._select_paddle_region).pack(side=tk.LEFT, padx=5)

        ttk.Button(level_assets, text="Seviye Varlıklarını Kaydet", command=self._save_level_assets).grid(row=4, column=0, columnspan=2, pady=(8,0))

        # End Screens Frame
        end_frame = ttk.LabelFrame(pane, text="Bitiş Ekranları (Kazanma / Kaybetme)", padding=5)
        end_frame.grid(row=3, column=0, sticky="ew", pady=5)
        end_frame.columnconfigure(1, weight=1)

        ttk.Label(end_frame, text="Kazanma Arkaplanı:").grid(row=0, column=0, sticky="e", padx=5, pady=5)
        self.win_bg_var = tk.StringVar()
        win_bg_frame = ttk.Frame(end_frame)
        win_bg_frame.grid(row=0, column=1, sticky="ew", padx=5, pady=5)
        ttk.Entry(win_bg_frame, textvariable=self.win_bg_var, width=32).pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(win_bg_frame, text="Seç...", command=self._browse_win_bg).pack(side=tk.LEFT)
        # Win scaling
        self.win_scale_enable_var = tk.BooleanVar(value=False)
        self.win_scale_keep_ratio_var = tk.BooleanVar(value=True)
        win_scale_row = ttk.Frame(end_frame)
        win_scale_row.grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(win_scale_row, text="Boyutlandır", variable=self.win_scale_enable_var).pack(side=tk.LEFT)
        ttk.Label(win_scale_row, text="W:").pack(side=tk.LEFT)
        self.win_scale_w_var = tk.StringVar()
        ttk.Entry(win_scale_row, textvariable=self.win_scale_w_var, width=6).pack(side=tk.LEFT)
        ttk.Label(win_scale_row, text="H:").pack(side=tk.LEFT)
        self.win_scale_h_var = tk.StringVar()
        ttk.Entry(win_scale_row, textvariable=self.win_scale_h_var, width=6).pack(side=tk.LEFT)
        ttk.Checkbutton(win_scale_row, text="Oran", variable=self.win_scale_keep_ratio_var).pack(side=tk.LEFT)

        ttk.Label(end_frame, text="Kaybetme Arkaplanı:").grid(row=1, column=0, sticky="e", padx=5, pady=5)
        self.lose_bg_var = tk.StringVar()
        lose_bg_frame = ttk.Frame(end_frame)
        lose_bg_frame.grid(row=1, column=1, sticky="ew", padx=5, pady=5)
        ttk.Entry(lose_bg_frame, textvariable=self.lose_bg_var, width=32).pack(side=tk.LEFT, padx=(0,5))
        ttk.Button(lose_bg_frame, text="Seç...", command=self._browse_lose_bg).pack(side=tk.LEFT)
        # Lose scaling
        self.lose_scale_enable_var = tk.BooleanVar(value=False)
        self.lose_scale_keep_ratio_var = tk.BooleanVar(value=True)
        lose_scale_row = ttk.Frame(end_frame)
        lose_scale_row.grid(row=1, column=2, sticky="w")
        ttk.Checkbutton(lose_scale_row, text="Boyutlandır", variable=self.lose_scale_enable_var).pack(side=tk.LEFT)
        ttk.Label(lose_scale_row, text="W:").pack(side=tk.LEFT)
        self.lose_scale_w_var = tk.StringVar()
        ttk.Entry(lose_scale_row, textvariable=self.lose_scale_w_var, width=6).pack(side=tk.LEFT)
        ttk.Label(lose_scale_row, text="H:").pack(side=tk.LEFT)
        self.lose_scale_h_var = tk.StringVar()
        ttk.Entry(lose_scale_row, textvariable=self.lose_scale_h_var, width=6).pack(side=tk.LEFT)
        ttk.Checkbutton(lose_scale_row, text="Oran", variable=self.lose_scale_keep_ratio_var).pack(side=tk.LEFT)

        ttk.Button(end_frame, text="Bitiş Ekranlarını Kaydet", command=self._save_end_screens).grid(row=2, column=0, columnspan=2, pady=(8,0))

        return pane

    def refresh(self):
        root = self.frame.winfo_toplevel()
        if not hasattr(root, 'current_game_id') or not root.current_game_id:
            return
        self.current_game_id = root.current_game_id

        # Refresh sprite sheets list
        for item in self.sheets_tree.get_children(): self.sheets_tree.delete(item)
        
        sheets = self.sprite_service.get_sprite_sheets(self.current_game_id)
        self.sheets_cache = sheets
        for sheet in sheets:
            self.sheets_tree.insert("", "end", iid=str(sheet.id), values=(sheet.name,))
        
        # Refresh expressions list
        self._refresh_expressions()

        # Refresh levels list
        self._refresh_levels()
        self._load_end_screens()
        
        self._on_sheet_select()

    def _on_sheet_select(self, event=None):
        selection = self.sheets_tree.selection()
        if not selection:
            self.selected_sprite_sheet = None
            self.delete_sheet_button.config(state="disabled")
            self.image_canvas.delete("all")
            return
        
        sheet_id = int(selection[0])
        self.selected_sprite_sheet = self.sprite_service.get_sprite_sheet(sheet_id)
        self.delete_sheet_button.config(state="normal")
        self._load_image()
        self._refresh_definitions()

    def _load_image(self):
        self.image_canvas.delete("all")
        self.selected_area_var.set("(yok)")
        self.last_crop_coords = None
        if self.selected_sprite_sheet and os.path.exists(self.selected_sprite_sheet.path):
            image = Image.open(self.selected_sprite_sheet.path)
            self.tk_image = ImageTk.PhotoImage(image)
            self.image_canvas.create_image(0, 0, anchor="nw", image=self.tk_image)

    def _add_sheet(self):
        if not self.current_game_id: return
        
        filepath = filedialog.askopenfilename(
            title="Sprite Sheet Seç",
            filetypes=[("Image Files", "*.png *.jpg *.jpeg *.bmp"), ("All Files", "*.*")]
        )
        if not filepath: return
        
        filename = os.path.basename(filepath)
        
        self.sprite_service.add_sprite_sheet(self.current_game_id, filename, filepath)
        self.refresh()

    def _delete_sheet(self):
        if not self.selected_sprite_sheet: return
        if not messagebox.askyesno("Onay", f"'{self.selected_sprite_sheet.name}' dosyasını ve tüm tanımlarını silmek istediğinize emin misiniz?"):
            return
        
        self.sprite_service.delete_sprite_sheet(self.selected_sprite_sheet.id)
        self.refresh()

    def _open_cropper(self, event=None):
        if not self.selected_sprite_sheet: return
        
        cropper = Cropper(self.frame, self.selected_sprite_sheet.path)
        result = cropper.show()
        
        if result:
            self.last_crop_coords = result
            self.selected_area_var.set(f"(x={result['x']}, y={result['y']}, w={result['width']}, h={result['height']})")
            # Draw overlay rectangle on canvas
            self.image_canvas.delete("selection_rect")
            self.image_canvas.create_rectangle(
                result['x'], result['y'], result['x']+result['width'], result['y']+result['height'],
                outline='red', width=2, tags=("selection_rect",)
            )
            # Enable assign button if expression is selected
            self._update_assign_button_state()
    
    def _refresh_definitions(self):
        for item in self.defs_tree.get_children():
            self.defs_tree.delete(item)
        if not self.selected_sprite_sheet:
            return
        defs = self.sprite_service.get_all_definitions_for_sheet(self.selected_sprite_sheet.id)
        for d in defs:
            expr_label = self.expressions_index.get(d.expression_id, f"(expr #{d.expression_id})")
            coords_text = f"{d.x}, {d.y}, {d.width}, {d.height}"
            self.defs_tree.insert("", "end", values=(expr_label, coords_text))

    def _assign_expression(self):
        if not self.selected_sprite_sheet:
            messagebox.showwarning("Uyarı", "Lütfen önce bir sprite sheet seçin.")
            return
        if not self.last_crop_coords:
            messagebox.showwarning("Uyarı", "Lütfen önce bir bölge seçin (Bölge Seç).")
            return
        label = self.expr_var.get()
        if not label or label not in self.expr_label_to_id:
            messagebox.showwarning("Uyarı", "Lütfen bir ifade seçin.")
            return
        expr_id = self.expr_label_to_id[label]
        coords = self.last_crop_coords
        try:
            self.sprite_service.add_or_update_sprite_definition(
                self.selected_sprite_sheet.id, expr_id, coords
            )
            self._refresh_definitions()
            messagebox.showinfo("Başarılı", "Bölge ifade ile ilişkilendirildi.")
        except Exception as e:
            messagebox.showerror("Hata", f"Tanım kaydedilirken hata: {e}")

    def _refresh_expressions(self):
        self.expressions_index.clear()
        self.expr_label_to_id.clear()
        labels: List[str] = []
        try:
            levels = self.level_service.get_levels(self.current_game_id)
            for lvl in levels:
                exprs = self.expression_service.get_expressions(lvl.id)
                for ex in exprs:
                    label = f"Seviye {lvl.level_number}: {ex.expression}"
                    self.expressions_index[ex.id] = label
                    self.expr_label_to_id[label] = ex.id
                    labels.append(label)
        except Exception:
            pass
        self.expr_combo['values'] = labels
        self.expr_combo.set(labels[0] if labels else "")
        self._update_assign_button_state()

    def _update_assign_button_state(self):
        has_coords = self.last_crop_coords is not None
        has_expr = bool(self.expr_var.get())
        state = "normal" if has_coords and has_expr else "disabled"
        self.assign_button.config(state=state)

    # ------- Level assets UI logic -------
    def _refresh_levels(self):
        try:
            self.levels_cache = self.level_service.get_levels(self.current_game_id)
            labels = [f"{lvl.level_number} - {lvl.level_name}" for lvl in self.levels_cache]
            self.level_sel['values'] = labels
            if labels:
                self.level_sel.set(labels[0])
                self._load_level_assets()
        except Exception:
            self.levels_cache = []
            self.level_sel['values'] = []

        # Populate paddle sheet list
        sheet_labels = [f"{s.id} - {s.name}" for s in self.sheets_cache]
        self.paddle_sheet_combo['values'] = sheet_labels
        if sheet_labels:
            self.paddle_sheet_combo.set(sheet_labels[0])

    def _get_selected_level(self):
        if not self.levels_cache:
            return None
        idx = self.level_sel.current()
        if idx < 0 or idx >= len(self.levels_cache):
            return None
        return self.levels_cache[idx]

    def _load_level_assets(self):
        lvl = self._get_selected_level()
        if not lvl:
            return
        settings = self.game_service.get_settings(lvl.game_id)
        self.level_bg_var.set(settings.get(f"level_{lvl.level_number}_background_path", ""))
        paddle_json = settings.get(f"level_{lvl.level_number}_paddle_sprite", "")
        if paddle_json:
            try:
                info = json.loads(paddle_json)
                self.paddle_area_var.set(f"sheet {info.get('sprite_id')} @ x={info.get('x')}, y={info.get('y')}, w={info.get('width')}, h={info.get('height')}")
                # set sheet combo to matching sheet
                for i, s in enumerate(self.sheets_cache):
                    if s.id == info.get('sprite_id'):
                        self.paddle_sheet_combo.set(f"{s.id} - {s.name}")
                        break
            except Exception:
                self.paddle_area_var.set("(yok)")
        else:
            self.paddle_area_var.set("(yok)")

    def _browse_level_bg(self):
        path = filedialog.askopenfilename(
            title="Seviye Arkaplanı Seç",
            filetypes=[("Görüntü Dosyaları", "*.png;*.jpg;*.jpeg;*.bmp"), ("Tümü", "*.*")]
        )
        if path:
            self.level_bg_var.set(path)

    def _select_paddle_region(self):
        sheet_label = self.paddle_sheet_var.get()
        if not sheet_label:
            messagebox.showwarning("Uyarı", "Önce bir sprite sheet seçin.")
            return
        try:
            sheet_id = int(sheet_label.split(' - ')[0])
        except Exception:
            messagebox.showwarning("Uyarı", "Geçerli bir sprite sheet seçin.")
            return
        sheet = next((s for s in self.sheets_cache if s.id == sheet_id), None)
        if not sheet or not os.path.exists(sheet.path):
            messagebox.showerror("Hata", "Sprite sheet bulunamadı.")
            return
        cropper = Cropper(self.frame, sheet.path)
        result = cropper.show()
        if result:
            self.paddle_area_var.set(f"sheet {sheet.id} @ x={result['x']}, y={result['y']}, w={result['width']}, h={result['height']}")
            # temporarily store in instance for saving
            self._paddle_temp = {**result, 'sprite_id': sheet.id}

    def _save_level_assets(self):
        lvl = self._get_selected_level()
        if not lvl:
            messagebox.showwarning("Uyarı", "Önce bir seviye seçin.")
            return
        # background copy
        src_bg = self.level_bg_var.get().strip()
        if src_bg:
            try:
                if not os.path.isfile(src_bg):
                    raise FileNotFoundError("Seçilen arkaplan dosyası bulunamadı.")
                dst_dir = os.path.join('assets', 'games', str(lvl.game_id), 'levels', str(lvl.level_number), 'backgrounds')
                os.makedirs(dst_dir, exist_ok=True)
                safe_name = self._sanitize_filename(os.path.basename(src_bg))
                dst_path = self._avoid_collision(dst_dir, safe_name)
                if os.path.abspath(src_bg) != os.path.abspath(dst_path):
                    import shutil
                    shutil.copy2(src_bg, dst_path)
                rel = dst_path.replace('\\', '/')
                self.game_service.update_setting(lvl.game_id, f"level_{lvl.level_number}_background_path", rel)
            except Exception as e:
                messagebox.showwarning("Uyarı", f"Seviye arkaplanı kaydedilemedi: {e}")
        # paddle sprite save
        info = getattr(self, '_paddle_temp', None)
        if info:
            try:
                payload = json.dumps(info)
                self.game_service.update_setting(lvl.game_id, f"level_{lvl.level_number}_paddle_sprite", payload)
            except Exception as e:
                messagebox.showwarning("Uyarı", f"Paddle bilgisi kaydedilemedi: {e}")
        messagebox.showinfo("Başarılı", "Seviye varlıkları kaydedildi.")

    # ------- End screens UI logic -------
    def _load_end_screens(self):
        if not self.current_game_id:
            return
        settings = self.game_service.get_settings(self.current_game_id)
        self.win_bg_var.set(settings.get('end_win_background_path', ''))
        self.lose_bg_var.set(settings.get('end_lose_background_path', ''))

    def _browse_win_bg(self):
        path = filedialog.askopenfilename(
            title="Kazanma Arkaplanı Seç",
            filetypes=[("Görüntü Dosyaları", "*.png;*.jpg;*.jpeg;*.bmp"), ("Tümü", "*.*")]
        )
        if path:
            self.win_bg_var.set(path)

    def _browse_lose_bg(self):
        path = filedialog.askopenfilename(
            title="Kaybetme Arkaplanı Seç",
            filetypes=[("Görüntü Dosyaları", "*.png;*.jpg;*.jpeg;*.bmp"), ("Tümü", "*.*")]
        )
        if path:
            self.lose_bg_var.set(path)

    def _save_end_screens(self):
        if not self.current_game_id:
            return
        tasks = [
            ('end_win_background_path', self.win_bg_var, 'end_screens', self.win_scale_enable_var, self.win_scale_w_var, self.win_scale_h_var, self.win_scale_keep_ratio_var),
            ('end_lose_background_path', self.lose_bg_var, 'end_screens', self.lose_scale_enable_var, self.lose_scale_w_var, self.lose_scale_h_var, self.lose_scale_keep_ratio_var)
        ]
        for key, var, subdir, ena, wv, hv, keep in tasks:
            src = var.get().strip()
            if not src:
                continue
            try:
                dst_dir = os.path.join('assets', 'games', str(self.current_game_id), subdir)
                os.makedirs(dst_dir, exist_ok=True)
                dst_path = self._resize_and_copy_image(src, dst_dir, ena.get(), wv.get().strip(), hv.get().strip(), keep.get())
                rel = dst_path.replace('\\', '/')
                self.game_service.update_setting(self.current_game_id, key, rel)
            except Exception as e:
                messagebox.showwarning("Uyarı", f"{key} kaydedilemedi: {e}")
        messagebox.showinfo("Başarılı", "Bitiş ekranları kaydedildi.")

    # ------- Helpers -------
    def _sanitize_filename(self, name: str) -> str:
        name = name.strip().lower()
        name = unicodedata.normalize('NFKD', name)
        name = name.encode('ascii', 'ignore').decode('ascii')
        base, ext = os.path.splitext(name)
        safe_base = ''.join(c if c.isalnum() or c in ('-', '_') else '_' for c in base)
        safe_ext = ''.join(c if c.isalnum() else '' for c in ext)
        ext = ('.' + safe_ext) if safe_ext else ''
        if not safe_base:
            safe_base = 'file'
        return safe_base + ext

    def _avoid_collision(self, directory: str, filename: str) -> str:
        base, ext = os.path.splitext(filename)
        candidate = os.path.join(directory, filename)
        counter = 1
        while os.path.exists(candidate):
            candidate = os.path.join(directory, f"{base}_{counter}{ext}")
            counter += 1
        return candidate

    def _resize_and_copy_image(self, src_path: str, dst_dir: str, enable_scale: bool, w_str: str, h_str: str, keep_ratio: bool) -> str:
        if not os.path.isfile(src_path):
            raise FileNotFoundError("Kaynak dosya bulunamadı")
        basename = os.path.basename(src_path)
        safe_name = self._sanitize_filename(basename)
        dst_path = self._avoid_collision(dst_dir, safe_name)
        if not enable_scale:
            if os.path.abspath(src_path) != os.path.abspath(dst_path):
                import shutil
                shutil.copy2(src_path, dst_path)
            return dst_path
        img = Image.open(src_path)
        orig_w, orig_h = img.size
        new_w = int(w_str) if w_str.isdigit() and int(w_str) > 0 else None
        new_h = int(h_str) if h_str.isdigit() and int(h_str) > 0 else None
        if keep_ratio:
            if new_w and not new_h:
                new_h = int(round(orig_h * (new_w / orig_w)))
            elif new_h and not new_w:
                new_w = int(round(orig_w * (new_h / orig_h)))
            elif new_w and new_h:
                new_h = int(round(orig_h * (new_w / orig_w)))
            else:
                if os.path.abspath(src_path) != os.path.abspath(dst_path):
                    import shutil
                    shutil.copy2(src_path, dst_path)
                return dst_path
        else:
            if not new_w and not new_h:
                if os.path.abspath(src_path) != os.path.abspath(dst_path):
                    import shutil
                    shutil.copy2(src_path, dst_path)
                return dst_path
            if not new_w:
                new_w = orig_w
            if not new_h:
                new_h = orig_h
        resized = img.resize((new_w, new_h), Image.LANCZOS)
        resized.save(dst_path)
        return dst_path
