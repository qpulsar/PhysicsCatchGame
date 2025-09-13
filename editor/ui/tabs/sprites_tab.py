"""Tab for managing sprite sheets and their definitions."""
import os
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from typing import Optional, Dict, List
from PIL import Image, ImageTk

from ...core.models import Sprite, SpriteDefinition, Expression
from ...core.services import SpriteService, ExpressionService

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
    def __init__(self, parent, sprite_service: SpriteService, expression_service: ExpressionService):
        self.parent = parent
        self.sprite_service = sprite_service
        self.expression_service = expression_service # To get unassigned expressions
        self.current_game_id = None
        self.selected_sprite_sheet: Optional[Sprite] = None
        self.tk_image = None
        self.sprite_definitions: List[SpriteDefinition] = []

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
        ttk.Button(button_frame, text="Ekle", command=self._add_sheet).pack(side=tk.LEFT, padx=2)
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
        self.assign_button = ttk.Button(assign_frame, text="Ata", command=self._assign_expression, state="disabled")
        self.assign_button.pack(side=tk.LEFT)

        return pane

    def refresh(self):
        root = self.frame.winfo_toplevel()
        if not hasattr(root, 'current_game_id') or not root.current_game_id:
            return
        self.current_game_id = root.current_game_id

        # Refresh sprite sheets list
        for item in self.sheets_tree.get_children(): self.sheets_tree.delete(item)
        
        sheets = self.sprite_service.get_sprite_sheets(self.current_game_id)
        for sheet in sheets:
            self.sheets_tree.insert("", "end", iid=str(sheet.id), values=(sheet.name,))
        
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
        
        # In a real app, copy the file to a project-local directory.
        # For simplicity, we'll just store the absolute path.
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
            # Here, we have coordinates but no expression to link it to yet.
            # A better UX might be to first create a "definition" then link it.
            # For now, we will link it via the combobox below.
            messagebox.showinfo("Koordinatlar", f"Seçilen alan: {result}", parent=self.frame)
            # This is where we would create a new, unlinked definition
            # and refresh the definitions list. This part is complex and
            # left as a potential improvement.
    
    def _refresh_definitions(self):
        # This part is a placeholder for full implementation
        pass

    def _assign_expression(self):
        # This part is a placeholder for full implementation
        pass
