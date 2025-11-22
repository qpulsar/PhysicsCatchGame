"""Screen Designer Window (Toplevel) for creating DB-backed screens like the Opening screen.

This designer uses a single Canvas (default 1024x768) and provides a minimal, fast
UI to place widgets via drag & drop. It saves/loads a screen JSON into the DB
using ScreenService. Heavy asset browsing is deferred to existing MediaTab and
SpritesTab; here we focus on positions and basic properties.

Usage:
    win = ScreenDesignerWindow(parent, game_id, screen_service, sprite_service, game_service)

Notes:
- Minimum viable features implemented:
  * Background image select and preview
  * Music file select (stored as path)
  * Add Label and Button widgets; move by drag
  * Edit properties (text, color, font size, action)
  * Save to DB via ScreenService (name='opening', type='menu')
  * Load existing design if present

Future extensions:
- Sprite sheet region picker integration
- Overlay text advanced styling
- Alignment grid and snapping
"""
from __future__ import annotations

import os
import json
from collections import Counter
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, colorchooser, simpledialog
from typing import Dict, Any, Optional, List

from PIL import Image, ImageTk


class ScreenDesignerWindow(tk.Toplevel):
    """Toplevel pencere: Tek kanvaslı, sürükle-bırak ekran tasarımcısı.

    Attributes:
        game_id: Aktif oyunun kimliği
        screen_service: DB CRUD için servis
        canvas: Tasarım alanı (1024x768)
        items: Kanvas üzerindeki öğelerin dahili listesi
    """

    CANVAS_W = 1024
    CANVAS_H = 768

    def __init__(self, parent: tk.Tk, game_id: int, screen_service, sprite_service, game_service, level_service=None,
                 effect_service=None, screen_name: str = "opening", screen_type: str = "menu"):
        """Designer'ı başlatır.

        Args:
            parent: Üst Tk penceresi
            game_id: Tasarlanan oyunun ID'si
            screen_service: DB'ye kaydetmek ve okumak için ScreenService
            sprite_service: Sprite erişimi (gelecek genişletmeler için)
            game_service: Oyun ayarlarına erişim (gerekirse)
        """
        super().__init__(parent)
        # Başlık: ekran adına göre
        self.title(f"Ekran Tasarımcısı - {screen_name}")
        self.geometry("1100x760")
        self.transient(parent)
        self.grab_set()
        # Açılışta tam ekran denemesi (platforma göre güvenli)
        try:
            # Windows/Linux: zoomed
            self.state('zoomed')
        except Exception:
            pass
        try:
            # macOS/evrensel fallback
            self.after(50, lambda: self.attributes('-fullscreen', True))
        except Exception:
            pass

        self.game_id = game_id
        self.screen_service = screen_service
        self.sprite_service = sprite_service
        self.game_service = game_service
        self.level_service = level_service
        self.effect_service = effect_service
        self.screen_name = screen_name
        self.screen_type = screen_type

        self._bg_img_ref: Optional[ImageTk.PhotoImage] = None
        self._canvas_bg_path: Optional[str] = None
        self._bg_display_to_path: Dict[str, str] = {}
        self._bg_path_to_display: Dict[str, str] = {}
        # Zoom (rendering scale). Logical tasarım 800x600, çizim zoom ile ölçeklenir.
        self.zoom: float = 1.0
        self.zoom_var = tk.StringVar(value="100%")

        self.items: List[Dict[str, Any]] = []  # [{'id':canvas_id, 'type':'label'|'button'|'image', 'props':{...}}]
        self.selected_item: Optional[Dict[str, Any]] = None
        self._drag_start = (0, 0)
        self._name_counters = {"label": 0, "button": 0, "sprite": 0}

        # Sepet önizlemesi için referanslar
        self._basket_preview_img_ref: Optional[ImageTk.PhotoImage] = None
        self._basket_preview_id: Optional[int] = None

        # Düşen item arkaplan önizlemesi için referanslar
        self._item_preview_img_ref: Optional[ImageTk.PhotoImage] = None
        self._item_preview_id: Optional[int] = None
        self._item_preview_text_id: Optional[int] = None
        # Çoklu önizleme için dinamik düğümler ve referans listesi
        self._item_preview_nodes: list[tuple[int, int]] = []  # (img_id, text_id)
        self._item_preview_img_refs: list[ImageTk.PhotoImage] = []

        # Efekt (yakalama) önizlemesi için durum
        self._effect_preview_id: Optional[int] = None
        self._effect_timer: Optional[str] = None  # after id
        self._effect_frames_ok: list[ImageTk.PhotoImage] = []
        self._effect_frames_bad: list[ImageTk.PhotoImage] = []
        self._effect_current_list: list[ImageTk.PhotoImage] = []
        self._effect_current_index: int = 0
        self._effect_cycle_kind: str = "ok"  # ok -> bad -> ok ...
        # EffectService tabanlı efekt tanımları için haritalar
        self._effect_name_to_params: Dict[str, Dict[str, Any]] = {}
        self._effect_image_to_name: Dict[str, str] = {}

        # UI Değişkenleri (Erken Tanım)
        self.zoom_var = tk.StringVar(value="100%")
        
        # Konum
        self.pos_x_var = tk.StringVar()
        self.pos_y_var = tk.StringVar()
        
        # Label
        self.label_color_var = tk.StringVar(value="#FFFFFF")
        self.label_size_var = tk.StringVar(value="20")
        
        # Buton
        self.button_text_var = tk.StringVar(value="Buton")
        self.button_action_var = tk.StringVar(value="start_game")
        self.button_color_var = tk.StringVar(value="#4CAF50")
        self.button_sprite_var = tk.StringVar()
        
        # Sprite
        self.image_sprite_var = tk.StringVar()
        
        # Level - Basket & Effect
        self.level_basket_sprite_var = tk.StringVar()
        self.level_basket_len_var = tk.StringVar(value="128")
        self.level_effect_ok_var = tk.StringVar()
        self.level_effect_bad_var = tk.StringVar()
        self.level_effect_fps_var = tk.StringVar(value="30")
        self.level_effect_scale_var = tk.StringVar(value="60")
        
        # Level - SFX & Music
        self.level_sfx_ok_var = tk.StringVar()
        self.level_sfx_bad_var = tk.StringVar()
        self.music_path_var = tk.StringVar()
        
        # Level - HUD
        self.level_hud_sprite_var = tk.StringVar()
        self.level_help_area_var = tk.StringVar(value="none")

        # Level ekranı ise, level_id'yi UI kurulmadan ÖNCE çöz (UI bu alana bakıyor olabilir)
        self.level_id = self._parse_level_id() if (self.screen_type or "").lower() == "level" else None

        self._apply_theme()
        self._build_ui()
        self._scan_assets()
        # Sprite/audio dropdown'larını ilk yüklemede de doldur
        try:
            self._load_sprite_regions()
        except Exception:
            pass
        # Oyun için tanımlanmış efekt kayıtlarını yükle
        try:
            self._load_effects_for_game()
        except Exception:
            pass
        self._load_existing()

    def _apply_theme(self) -> None:
        """Modern koyu tema ayarlarını ve stillerini yapılandırır."""
        style = ttk.Style(self)
        # 'clam' teması renk özelleştirmeleri için iyi bir temeldir
        try:
            style.theme_use('clam')
        except tk.TclError:
            pass

        # Renk Paleti (Dark Modern)
        bg_color = "#2b2b2b"       # Ana arka plan
        panel_color = "#313335"    # Paneller
        fg_color = "#a9b7c6"       # Genel yazı rengi
        accent_color = "#4b6eaf"   # Vurgu (Seçim vb.)
        entry_bg = "#45494a"       # Input alanları
        border_color = "#555555"

        self.configure(background=bg_color)

        # Genel element yapılandırması
        style.configure(".", background=bg_color, foreground=fg_color, borderwidth=0)
        style.configure("TFrame", background=bg_color)
        style.configure("TLabelframe", background=bg_color, foreground=fg_color, bordercolor=border_color)
        style.configure("TLabelframe.Label", background=bg_color, foreground="#cc7832", font=("Segoe UI", 9, "bold"))
        style.configure("TLabel", background=bg_color, foreground=fg_color)
        
        # Butonlar
        style.configure("TButton", background=panel_color, foreground="white", borderwidth=1, bordercolor=border_color, padding=4)
        style.map("TButton",
                  background=[("active", accent_color), ("pressed", border_color)],
                  foreground=[("active", "white")])

        # Accent Button (Örn: Kaydet)
        style.configure("Accent.TButton", background="#365880", foreground="white", font=("Segoe UI", 9, "bold"))
        style.map("Accent.TButton", background=[("active", "#4b6eaf")])

        # Treeview (Liste)
        style.configure("Treeview", 
                        background=entry_bg, 
                        foreground="white", 
                        fieldbackground=entry_bg, 
                        borderwidth=0,
                        font=("Segoe UI", 9))
        style.map("Treeview", background=[("selected", accent_color)])
        style.configure("Treeview.Heading", background=panel_color, foreground="white", relief="flat")
        
        # Giriş Elemanları
        style.configure("TEntry", fieldbackground=entry_bg, foreground="white", insertcolor="white", bordercolor=border_color)
        style.configure("TCombobox", fieldbackground=entry_bg, foreground="white", arrowcolor="white", bordercolor=border_color)
        style.map("TCombobox", fieldbackground=[("readonly", entry_bg)], selectbackground=[("readonly", entry_bg)])

        # Tablar (Notebook)
        style.configure("TNotebook", background=bg_color, borderwidth=0)
        style.configure("TNotebook.Tab", background=panel_color, foreground=fg_color, padding=(10, 4))
        style.map("TNotebook.Tab", background=[("selected", entry_bg)], foreground=[("selected", "white")])

        # Özel stiller
        style.configure("Toolbar.TFrame", background=panel_color)
        style.configure("Subheader.TLabel", font=("Segoe UI", 11, "bold"), foreground="#cc7832")

    # UI setup
    def _build_ui(self) -> None:
        """Ana arayüzü oluşturur: Üst bar, ve 3 panelli (Sol, Orta, Sağ) yapı."""
        # Ana grid yapılandırması (tek hücre, tamamını kapla)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=0) # Toolbar
        self.rowconfigure(1, weight=1) # Main content

        # --- 1. Üst Araç Çubuğu (Toolbar) ---
        toolbar = ttk.Frame(self, style="Toolbar.TFrame", padding=5)
        toolbar.grid(row=0, column=0, sticky="ew")
        
        ttk.Label(toolbar, text="Tasarımcı:", style="Subheader.TLabel", background="#313335").pack(side=tk.LEFT, padx=(5, 10))
        
        # Zoom kontrolleri
        ttk.Label(toolbar, text="Zoom:", background="#313335").pack(side=tk.LEFT, padx=(10, 2))
        zoom_box = ttk.Combobox(toolbar, textvariable=self.zoom_var, state="readonly", width=6,
                                 values=["50%", "75%", "100%", "125%", "150%"])
        zoom_box.pack(side=tk.LEFT)
        zoom_box.bind("<<ComboboxSelected>>", lambda e: self._on_zoom_change())

        # Sağ taraf toolbar butonları
        ttk.Button(toolbar, text="Kapat", command=self.destroy).pack(side=tk.RIGHT, padx=5)
        self.save_btn = ttk.Button(toolbar, text="KAYDET", command=self._save, style="Accent.TButton")
        self.save_btn.pack(side=tk.RIGHT, padx=5)

        # --- 2. Ana İçerik (PanedWindow) ---
        # Horizontal PanedWindow: Sol (Araçlar), Orta (Tuval), Sağ (Özellikler)
        main_pane = ttk.PanedWindow(self, orient=tk.HORIZONTAL)
        main_pane.grid(row=1, column=0, sticky="nsew")

        # -- SOL PANEL (Tools & Assets) --
        left_panel = ttk.Frame(main_pane, padding=5)
        main_pane.add(left_panel, weight=1)

        # Sol panel içeriği: Notebook ile sekmeli yapı (Daha temiz görünüm için)
        left_tabs = ttk.Notebook(left_panel)
        left_tabs.pack(fill="both", expand=True)

        # Sekme 1: Ekle & Düzenle
        tab_tools = ttk.Frame(left_tabs, padding=5)
        left_tabs.add(tab_tools, text="Araçlar")

        # Widget Ekleme
        grp_add = ttk.LabelFrame(tab_tools, text="Öğe Ekle")
        grp_add.pack(fill="x", pady=(0, 10))
        
        btn_grid = ttk.Frame(grp_add)
        btn_grid.pack(fill="x", pady=5)
        ttk.Button(btn_grid, text="Etiket (Label)", command=self._add_label).grid(row=0, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(btn_grid, text="Buton", command=self._add_button).grid(row=0, column=1, sticky="ew", padx=2, pady=2)
        ttk.Button(btn_grid, text="Devam Btn", command=self._add_continue_button).grid(row=1, column=0, sticky="ew", padx=2, pady=2)
        ttk.Button(btn_grid, text="Sprite", command=self._add_image_sprite).grid(row=1, column=1, sticky="ew", padx=2, pady=2)
        btn_grid.columnconfigure(0, weight=1); btn_grid.columnconfigure(1, weight=1)

        # Nesne Listesi (Treeview)
        grp_items = ttk.LabelFrame(tab_tools, text="Katmanlar / Nesneler")
        grp_items.pack(fill="both", expand=True, pady=(0, 10))
        
        tree_scroll = ttk.Scrollbar(grp_items)
        tree_scroll.pack(side=tk.RIGHT, fill="y")
        self.obj_tree = ttk.Treeview(grp_items, columns=("name",), show="headings", height=10, 
                                     selectmode="browse", yscrollcommand=tree_scroll.set)
        tree_scroll.config(command=self.obj_tree.yview)
        self.obj_tree.heading("name", text="Öğe Adı", anchor="w")
        self.obj_tree.column("name", stretch=True)
        self.obj_tree.pack(fill="both", expand=True)
        self.obj_tree.bind("<<TreeviewSelect>>", lambda e: self._on_tree_select())

        # Katman butonları
        zrow = ttk.Frame(grp_items)
        zrow.pack(fill="x", pady=4)
        ttk.Button(zrow, text="▲ Yukarı", command=self._bring_forward, width=8).pack(side=tk.LEFT, padx=2, expand=True, fill="x")
        ttk.Button(zrow, text="▼ Aşağı", command=self._send_backward, width=8).pack(side=tk.LEFT, padx=2, expand=True, fill="x")
        
        # Yönetim butonları
        act_row = ttk.Frame(grp_items)
        act_row.pack(fill="x", pady=2)
        ttk.Button(act_row, text="Ad Değiştir", command=self._rename_selected).pack(side=tk.LEFT, padx=2, expand=True, fill="x")
        ttk.Button(act_row, text="Sil", command=self._delete_selected).pack(side=tk.LEFT, padx=2, expand=True, fill="x")

        # Sekme 2: Varlıklar (Arkaplan, Müzik)
        tab_assets = ttk.Frame(left_tabs, padding=5)
        left_tabs.add(tab_assets, text="Arkaplan")
        
        grp_bg = ttk.LabelFrame(tab_assets, text="Genel Ayarlar")
        grp_bg.pack(fill="x", pady=5)
        
        ttk.Label(grp_bg, text="Arkaplan Görseli:").pack(anchor="w", pady=(2, 0))
        self.bg_path_var = tk.StringVar()
        self.bg_display_var = tk.StringVar()
        self.bg_combo = ttk.Combobox(grp_bg, textvariable=self.bg_display_var, state="readonly")
        self.bg_combo.pack(fill="x", pady=(0, 5))
        self.bg_combo.bind("<<ComboboxSelected>>", lambda e: self._on_bg_select())

        # -- ORTA PANEL (Canvas) --
        center_panel = ttk.Frame(main_pane, style="TFrame") # Koyu arkaplan
        main_pane.add(center_panel, weight=4)
        
        # Canvas'ı ortalamak için container
        center_panel.rowconfigure(0, weight=1)
        center_panel.columnconfigure(0, weight=1)
        
        # Canvas etrafında scrollbar eklenebilir ama şimdilik fixed boyutlu canvas
        self.canvas = tk.Canvas(center_panel, width=self.CANVAS_W, height=self.CANVAS_H, 
                                background="#1e1e1e", highlightthickness=0)
        self.canvas.grid(row=0, column=0) # Sticky yok, ortada dursun
        
        # Canvas eventleri
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<B1-Motion>", self._on_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_drag_end)

        # Önizleme (Preview) Elemanları (Sepet, Efekt vb.)
        self._create_canvas_previews()

        # -- SAĞ PANEL (Properties) --
        right_panel = ttk.Frame(main_pane, padding=5, width=300)
        main_pane.add(right_panel, weight=1)
        
        ttk.Label(right_panel, text="Özellikler Paneli", style="Subheader.TLabel").pack(anchor="w", pady=(0, 10))

        # Scroll edilebilir özellikler alanı (ekran küçükse taşmaması için)
        prop_canvas = tk.Canvas(right_panel, background="#2b2b2b", highlightthickness=0)
        prop_scrollbar = ttk.Scrollbar(right_panel, orient="vertical", command=prop_canvas.yview)
        self.prop_inner = ttk.Frame(prop_canvas)
        
        self.prop_inner.bind(
            "<Configure>",
            lambda e: prop_canvas.configure(scrollregion=prop_canvas.bbox("all"))
        )
        prop_window = prop_canvas.create_window((0, 0), window=self.prop_inner, anchor="nw")
        
        # Canvas boyutuna uydur (Genişlik ve Yükseklik)
        def _on_prop_resize(event):
            canvas_width = event.width
            canvas_height = event.height
            # İçeriğin ihtiyaç duyduğu minimum yükseklik
            req_height = self.prop_inner.winfo_reqheight()
            # Canvas yüksekliği veya içerik yüksekliğinden büyük olanı al
            new_height = max(canvas_height, req_height)
            prop_canvas.itemconfig(prop_window, width=canvas_width, height=new_height)
        
        prop_canvas.bind("<Configure>", _on_prop_resize)
        prop_canvas.configure(yscrollcommand=prop_scrollbar.set)
        
        prop_canvas.pack(side="left", fill="both", expand=True)
        prop_scrollbar.pack(side="right", fill="y")

        # İçerik oluşturucular (Sağ panele eklenenler self.prop_inner içine gidecek)
        self._build_property_panels(self.prop_inner)

    def _create_canvas_previews(self):
        """Canvas üzerindeki özel önizleme öğelerini oluşturur."""
        # Sepet
        self._basket_preview_id = self.canvas.create_image(
            self.CANVAS_W / 2, self.CANVAS_H - 40, anchor="s", state="hidden", tags=("__basket_preview__",)
        )
        # Efekt
        self._effect_preview_id = self.canvas.create_image(
            self.CANVAS_W / 2, self.CANVAS_H - 90, anchor="s", state="hidden", tags=("__effect_preview__",)
        )
        # Düşen item
        self._item_preview_id = self.canvas.create_image(
            self.CANVAS_W / 2, 90, anchor="n", state="hidden", tags=("__item_bg_preview__",)
        )
        # Düşen item text
        self._item_preview_text_id = self.canvas.create_text(
            self.CANVAS_W / 2, 90, text="", fill="#FFFFFF", font=("Segoe UI", 24), anchor="n",
            state="hidden", tags=("__item_bg_preview_text__",)
        )

    def _build_property_panels(self, parent):
        """Sağ paneldeki özellik gruplarını oluşturur."""
        
        # 1. Konum
        pos_frame = ttk.LabelFrame(parent, text="Konum & Boyut")
        pos_frame.pack(fill="x", pady=5)
        
        p_grid = ttk.Frame(pos_frame)
        p_grid.pack(fill="x", pady=5)
        ttk.Label(p_grid, text="X:").grid(row=0, column=0, padx=5)
        ttk.Entry(p_grid, textvariable=self.pos_x_var, width=6).grid(row=0, column=1)
        ttk.Label(p_grid, text="Y:").grid(row=0, column=2, padx=5)
        ttk.Entry(p_grid, textvariable=self.pos_y_var, width=6).grid(row=0, column=3)
        
        ttk.Button(pos_frame, text="Konumu Uygula", command=self._apply_position).pack(fill="x", pady=(5,0))

        # 2. Label Props
        self.label_frame = ttk.LabelFrame(parent, text="Etiket Ayarları")
        self.label_text = tk.Text(self.label_frame, height=3, width=20, wrap="word", 
                                  background="#45494a", foreground="white", insertbackground="white", borderwidth=0)
        
        ttk.Label(self.label_frame, text="Metin:").pack(anchor="w")
        self.label_text.pack(fill="x", pady=(0, 5))
        
        l_row = ttk.Frame(self.label_frame)
        l_row.pack(fill="x")
        ttk.Label(l_row, text="Renk:").pack(side=tk.LEFT)
        ttk.Entry(l_row, textvariable=self.label_color_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(l_row, text="Seç", command=self._pick_label_color, width=4).pack(side=tk.LEFT)
        
        l_row2 = ttk.Frame(self.label_frame)
        l_row2.pack(fill="x", pady=5)
        ttk.Label(l_row2, text="Boyut:").pack(side=tk.LEFT)
        ttk.Entry(l_row2, textvariable=self.label_size_var, width=5).pack(side=tk.LEFT, padx=5)

        # Bindings
        self.label_text.bind("<KeyRelease>", lambda e: (self._apply_label_props(), self._set_dirty(True)))
        self.label_color_var.trace_add('write', lambda *args: (self._apply_label_props(), self._set_dirty(True)))
        self.label_size_var.trace_add('write', lambda *args: (self._apply_label_props(), self._set_dirty(True)))

        # 3. Button Props
        self.button_frame = ttk.LabelFrame(parent, text="Buton Ayarları")
        
        ttk.Label(self.button_frame, text="Yazı:").pack(anchor="w")
        ttk.Entry(self.button_frame, textvariable=self.button_text_var).pack(fill="x", pady=(0,5))
        
        ttk.Label(self.button_frame, text="Aksiyon:").pack(anchor="w")
        ttk.Combobox(self.button_frame, textvariable=self.button_action_var, state="readonly",
                     values=["start_game", "continue_level", "next_level", "back"]).pack(fill="x", pady=(0,5))
        
        b_row = ttk.Frame(self.button_frame)
        b_row.pack(fill="x")
        ttk.Label(b_row, text="Renk:").pack(side=tk.LEFT)
        ttk.Entry(b_row, textvariable=self.button_color_var, width=8).pack(side=tk.LEFT, padx=5)
        ttk.Button(b_row, text="Seç", command=self._pick_button_color, width=4).pack(side=tk.LEFT)

        ttk.Label(self.button_frame, text="Sprite Bölgesi:").pack(anchor="w", pady=(5,0))
        self.button_sprite_combo = ttk.Combobox(self.button_frame, textvariable=self.button_sprite_var, state="readonly")
        self.button_sprite_combo.pack(fill="x")
        self.button_sprite_combo.bind('<<ComboboxSelected>>', lambda e: (self._apply_button_sprite(), self._set_dirty(True)))
        
        # Bindings
        self.button_text_var.trace_add('write', lambda *args: (self._apply_button_props(), self._set_dirty(True)))
        self.button_action_var.trace_add('write', lambda *args: (self._apply_button_props(), self._set_dirty(True)))
        self.button_color_var.trace_add('write', lambda *args: (self._apply_button_props(), self._set_dirty(True)))

        # 4. Sprite Props
        self.sprite_frame = ttk.LabelFrame(parent, text="Görsel (Sprite) Ayarları")
        ttk.Label(self.sprite_frame, text="Görsel Seçimi:").pack(anchor="w")
        self.image_sprite_combo = ttk.Combobox(self.sprite_frame, textvariable=self.image_sprite_var, state="readonly")
        self.image_sprite_combo.pack(fill="x")
        self.image_sprite_combo.bind('<<ComboboxSelected>>', lambda e: (self._apply_image_sprite(), self._set_dirty(True)))

        # 5. Level Settings
        self.level_frame = ttk.LabelFrame(parent, text="Seviye (Level) Ayarları")
        
        # Level ayarları için Notebook (Küçük alanda sekmeler daha iyi)
        lnb = ttk.Notebook(self.level_frame)
        lnb.pack(fill="both", expand=True, pady=5)
        
        lt_basket = ttk.Frame(lnb, padding=5); lnb.add(lt_basket, text="Oyun")
        lt_sfx = ttk.Frame(lnb, padding=5); lnb.add(lt_sfx, text="Ses")
        lt_hud = ttk.Frame(lnb, padding=5); lnb.add(lt_hud, text="HUD")
        lt_bg = ttk.Frame(lnb, padding=5); lnb.add(lt_bg, text="Nesne")

        # -- Helper --
        def _frm(p, txt):
            f = ttk.Frame(p); f.pack(fill="x", pady=2)
            ttk.Label(f, text=txt, anchor="w").pack(fill="x")
            return f
        
        # Display vars for simplified view
        self.level_basket_display_var = tk.StringVar()
        self.level_hud_display_var = tk.StringVar()
        self.level_effect_ok_display_var = tk.StringVar()
        self.level_effect_bad_display_var = tk.StringVar()
        self.level_sfx_ok_display_var = tk.StringVar()
        self.level_sfx_bad_display_var = tk.StringVar()
        self.music_display_var = tk.StringVar()

        # Mapping helper
        def _on_img_select(disp_var, path_var, cb=None):
            disp = disp_var.get()
            path = self._img_display_map.get(disp, "")
            path_var.set(path)
            if cb: cb()

        def _on_effect_select(disp_var, path_var, cb=None):
            """Effect combobox seçiminde, mümkünse DB kayıtlı efekt parametrelerini kullan.

            - Kullanıcıya isim gösterilir (Effect.name).
            - İçeride ilgili efektin image_path değeri level_effect_*_var içinde saklanır.
            - Eğer isim bir efekt kaydıyla eşleşmezse, eski dosya bazlı davranışa geri döner.
            """
            name = (disp_var.get() or "").strip()
            params_map = getattr(self, "_effect_name_to_params", {}) or {}
            params = params_map.get(name)
            if not params:
                # Geriye dönük uyumluluk: doğrudan görsel listesinden seçilmiş olabilir
                _on_img_select(disp_var, path_var, cb)
                return
            path = (params.get("image_path") or "").strip()
            path_var.set(path)
            if cb:
                cb()

        def _on_sprite_region_select(disp_var, path_var, cb=None):
            """Sprite bölgesi seçimlerinde (Name — Path) değeri olduğu gibi sakla."""
            val = disp_var.get()
            path_var.set(val)
            if cb: cb()

        def _on_aud_select(disp_var, path_var):
            disp = disp_var.get()
            path = self._audio_display_map.get(disp, "")
            path_var.set(path)

        # Basket
        self.level_basket_sprite_combo = ttk.Combobox(_frm(lt_basket, "Sepet Sprite:"), 
                                                      textvariable=self.level_basket_display_var, state="readonly")
        self.level_basket_sprite_combo.pack(fill="x")
        self.level_basket_sprite_combo.bind("<<ComboboxSelected>>", 
            lambda e: _on_sprite_region_select(self.level_basket_display_var, self.level_basket_sprite_var, self._update_basket_preview))
        
        self.level_basket_len_var.trace_add('write', lambda *args: self._update_basket_preview())
        ttk.Entry(_frm(lt_basket, "Sepet Genişlik:"), textvariable=self.level_basket_len_var).pack(fill="x")

        # Efektler
        self.level_effect_ok_combo = ttk.Combobox(_frm(lt_basket, "Doğru Efekt:"), 
                                                  textvariable=self.level_effect_ok_display_var, state="readonly")
        self.level_effect_ok_combo.pack(fill="x")
        self.level_effect_ok_combo.bind("<<ComboboxSelected>>", 
            lambda e: _on_effect_select(self.level_effect_ok_display_var, self.level_effect_ok_var, self._restart_effect_preview))
        
        self.level_effect_bad_combo = ttk.Combobox(_frm(lt_basket, "Yanlış Efekt:"), 
                                                   textvariable=self.level_effect_bad_display_var, state="readonly")
        self.level_effect_bad_combo.pack(fill="x")
        self.level_effect_bad_combo.bind("<<ComboboxSelected>>", 
            lambda e: _on_effect_select(self.level_effect_bad_display_var, self.level_effect_bad_var, self._restart_effect_preview))

        f_fps = ttk.Frame(lt_basket); f_fps.pack(fill="x", pady=4)
        ttk.Label(f_fps, text="FPS:").pack(side=tk.LEFT)
        ttk.Entry(f_fps, textvariable=self.level_effect_fps_var, width=5).pack(side=tk.LEFT, padx=5)
        ttk.Label(f_fps, text="Ölçek %:").pack(side=tk.LEFT)
        ttk.Entry(f_fps, textvariable=self.level_effect_scale_var, width=5).pack(side=tk.LEFT, padx=5)
        
        # Ses
        self.level_sfx_ok_combo = ttk.Combobox(_frm(lt_sfx, "Doğru Sesi:"), 
                                               textvariable=self.level_sfx_ok_display_var, state="readonly")
        self.level_sfx_ok_combo.pack(fill="x")
        self.level_sfx_ok_combo.bind("<<ComboboxSelected>>", 
             lambda e: _on_aud_select(self.level_sfx_ok_display_var, self.level_sfx_ok_var))
        
        self.level_sfx_bad_combo = ttk.Combobox(_frm(lt_sfx, "Yanlış Sesi:"), 
                                                textvariable=self.level_sfx_bad_display_var, state="readonly")
        self.level_sfx_bad_combo.pack(fill="x")
        self.level_sfx_bad_combo.bind("<<ComboboxSelected>>", 
             lambda e: _on_aud_select(self.level_sfx_bad_display_var, self.level_sfx_bad_var))
        
        self.music_combo = ttk.Combobox(_frm(lt_sfx, "Müzik:"), 
                                        textvariable=self.music_display_var, state="readonly")
        self.music_combo.pack(fill="x")
        self.music_combo.bind("<<ComboboxSelected>>", 
             lambda e: _on_aud_select(self.music_display_var, self.music_path_var))

        # HUD
        self.level_hud_sprite_combo = ttk.Combobox(_frm(lt_hud, "HUD Sprite:"), 
                                                   textvariable=self.level_hud_display_var, state="readonly")
        self.level_hud_sprite_combo.pack(fill="x")
        self.level_hud_sprite_combo.bind("<<ComboboxSelected>>", 
             lambda e: _on_sprite_region_select(self.level_hud_display_var, self.level_hud_sprite_var))
        
        self.level_help_area_combo = ttk.Combobox(_frm(lt_hud, "Yardım Konumu:"), textvariable=self.level_help_area_var, state="readonly",
                                                  values=["none","top-left","top-right","bottom-left","bottom-right"])
        self.level_help_area_combo.pack(fill="x")

        # BG
        ttk.Button(lt_bg, text="Nesne Resimleri Seç", command=self._open_bg_region_picker).pack(fill="x", pady=5)
        self.level_bg_preview_frame = ttk.LabelFrame(lt_bg, text="Seçili Bölgeler")
        self.level_bg_preview_frame.pack(fill="x", expand=True)
        self._refresh_bg_region_preview()

        # Initial Visibility
        self.label_frame.pack_forget()
        self.button_frame.pack_forget()
        self.sprite_frame.pack_forget()
        self.level_frame.pack_forget()
        
        if (self.screen_type or "").lower() == "level":
            self.level_frame.pack(fill="both", expand=True, pady=5)


    # Palette actions
    def _on_bg_select(self) -> None:
        """Arkaplan combobox'tan seçildiğinde önizleme uygular."""
        display = self.bg_display_var.get().strip()
        rel = self._bg_display_to_path.get(display, "").strip()
        if not rel:
            return
        self.bg_path_var.set(rel)
        abs_path = self._abs_assets_path(rel)
        if abs_path:
            self._apply_canvas_bg(abs_path)
            self._set_dirty(True)

    def _set_bg_selection(self, rel: str) -> None:
        """Arka plan seçiminde içsel yolu saklayıp kullanıcıya görünen etiketi senkronize eder."""
        rel = (rel or "").strip()
        if not rel:
            self.bg_path_var.set("")
            self.bg_display_var.set("")
            return
        display = self._bg_path_to_display.get(rel)
        if not display:
            display = self._register_bg_option(rel)
        self.bg_path_var.set(rel)
        self.bg_display_var.set(display)

    def _register_bg_option(self, rel: str) -> str:
        """Combobox'ta olmayan bir arka plan yolunu kullanıcı dostu etiketiyle ekler."""
        rel = (rel or "").strip()
        if not rel:
            return ""
        base_label = os.path.basename(rel) or rel
        parent = os.path.basename(os.path.dirname(rel)) or os.path.dirname(rel)
        if parent:
            base_label = f"{base_label} ({parent})"
        label = self._make_unique_bg_label(base_label)
        self._bg_display_to_path[label] = rel
        self._bg_path_to_display[rel] = label
        current_vals = list(self.bg_combo['values'] or ())
        current_vals.append(label)
        self.bg_combo['values'] = current_vals
        return label

    def _make_unique_bg_label(self, label: str) -> str:
        """Arka plan etiketini combobox değerleri içinde benzersiz hale getirir."""
        candidate = label or "Arka plan"
        suffix = 2
        while candidate in self._bg_display_to_path:
            candidate = f"{label} [{suffix}]"
            suffix += 1
        return candidate

    def _parse_level_id(self) -> Optional[int]:
        """Level ekranları için screen_name'den level_id çıkarır.

        Beklenen biçim: "level_<id>". Uymuyorsa None döner.
        """
        try:
            name = (self.screen_name or "").strip().lower()
            if not name.startswith("level_"):
                return None
            token = name.split("_", 1)[1]
            cand = int(token)

            # 1) Önce bu değeri gerçek DB level ID'si olarak doğrula
            try:
                if self.level_service is not None:
                    row = self.level_service.get_level(cand)  # type: ignore[attr-defined]
                    if row is not None:
                        return cand
            except Exception:
                pass

            # 2) Değilse, bu değeri seviye NUMARASI olarak yorumlayıp ID'ye eşle
            try:
                if self.level_service is not None and getattr(self, 'game_id', None):
                    levels = self.level_service.get_levels(self.game_id)  # type: ignore[attr-defined]
                    for lv in levels:
                        try:
                            if int(getattr(lv, 'level_number', -1)) == cand:
                                return int(getattr(lv, 'id'))
                        except Exception:
                            continue
            except Exception:
                pass

            # 3) Son çare: ham değeri döndür (ileri aşamada doğrulama/hataya düşer)
            return cand
        except Exception:
            return None

    def _open_bg_region_picker(self) -> None:
        """Önceden tanımlanmış sprite region'lar arasından görsel önizlemeli çoklu seçim penceresi açar.

        - Yalnızca level ekranında (ve level_id mevcutsa) çalışır.
        - Seçimler veritabanında `level_background_regions` eşlemesine kaydedilir.
        """
        if not self.level_service or not self.sprite_service:
            messagebox.showwarning("Sprite", "Sprite/Seviye servisi hazır değil.")
            return
        if not self.level_id:
            messagebox.showwarning("Seviye", "Bu işlem sadece seviye ekranında yapılabilir.")
            return

        # Mevcut seçimleri al
        selected_ids_set = set()
        try:
            raw_ids = self.level_service.get_level_background_region_ids(self.level_id)  # type: ignore[attr-defined]
            if raw_ids:
                # Gelen ID'leri güvenli şekilde integer setine çevir (str/int uyumsuzluğunu önle)
                selected_ids_set = {int(x) for x in raw_ids if str(x).isdigit() or isinstance(x, int)}
        except Exception as e:
            print(f"Seçili bölgeler alınırken hata: {e}")
            selected_ids_set = set()

        # Region listesini al
        regions = []
        try:
            regions = self.sprite_service.list_sprite_regions()
        except Exception as e:
            messagebox.showerror("Sprite Bölgeleri", f"Bölgeler alınamadı: {e}")
            return

        # Dialog
        dlg = tk.Toplevel(self)
        dlg.title("Arka Plan Bölge Seçimi")
        dlg.transient(self)
        dlg.grab_set()
        dlg.geometry("950x700")
        dlg.configure(bg="#2b2b2b")  # Koyu arka plan

        # Ana kapsayıcı
        container = ttk.Frame(dlg)
        container.pack(fill="both", expand=True, padx=10, pady=10)

        # Scrollable canvas
        canvas = tk.Canvas(container, borderwidth=0, background="#2b2b2b", highlightthickness=0)
        vsb = ttk.Scrollbar(container, orient="vertical", command=canvas.yview)
        frame = tk.Frame(canvas, bg="#2b2b2b") # İç frame de koyu olsun
        
        frame.bind(
            "<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all"))
        )
        # Canvas window'u sol üst köşeye sabitle
        canvas.create_window((0, 0), window=frame, anchor="nw")
        canvas.configure(yscrollcommand=vsb.set)
        
        canvas.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")

        # Resim referanslarını canlı tutmak için liste
        thumbs: List[ImageTk.PhotoImage] = []
        # ÖNEMLİ: Referansları dlg nesnesine bağla ki Garbage Collector temizlemesin
        dlg.image_refs = thumbs 

        var_by_id: Dict[int, tk.BooleanVar] = {}

        # Sabit boyutlu kart görünümü ayarları
        CARD_W, CARD_H = 200, 220
        IMG_AREA_W, IMG_AREA_H = 180, 120
        COLS = 4
        
        # Grid halinde kartlar
        for idx, reg in enumerate(regions):
            try:
                rid = int(reg.get("id"))
                img_rel = str(reg.get("image_path") or "")
                name = str(reg.get("name") or "")
                
                # Sprite koordinatları
                x = int(reg.get("x", 0))
                y = int(reg.get("y", 0))
                w = int(reg.get("width", 0))
                h = int(reg.get("height", 0))
                
                abs_path = self._abs_assets_path(img_rel)
                
                # Kart Çerçevesi (Sabit Boyut)
                cell = tk.Frame(frame, bg="#3c3f41", width=CARD_W, height=CARD_H, relief="flat", bd=1)
                cell.pack_propagate(False) # İçerik kartı büyütmesin/küçültmesin
                
                r = idx // COLS; c = idx % COLS
                cell.grid(row=r, column=c, padx=8, pady=8)

                # 1. Resim Alanı (Canvas) - Koyu arkaplan ile
                img_canvas = tk.Canvas(cell, width=IMG_AREA_W, height=IMG_AREA_H, bg="#212121", highlightthickness=0)
                img_canvas.pack(pady=(10, 5))

                thumb = None
                error_text = None
                
                if abs_path and os.path.isfile(abs_path):
                    if w > 0 and h > 0:
                        try:
                            pil = Image.open(abs_path)
                            iw, ih = pil.size
                            
                            # Sprite sheet içindeki bölgeyi güvenli şekilde belirle
                            x1 = max(0, min(iw, x))
                            y1 = max(0, min(ih, y))
                            x2 = max(0, min(iw, x + w))
                            y2 = max(0, min(ih, y + h))
                            
                            if x2 > x1 and y2 > y1:
                                pil_crop = pil.crop((x1, y1, x2, y2))
                                
                                # Oranı koruyarak sığdır
                                src_w, src_h = pil_crop.size
                                ratio = min(IMG_AREA_W / src_w, IMG_AREA_H / src_h)
                                new_w = max(1, int(src_w * ratio))
                                new_h = max(1, int(src_h * ratio))
                                
                                pil_thumb = pil_crop.resize((new_w, new_h), Image.LANCZOS)
                                thumb = ImageTk.PhotoImage(pil_thumb)
                                thumbs.append(thumb) # Listeye ekle
                                
                                # Canvas ortasına çiz
                                cx = IMG_AREA_W / 2
                                cy = IMG_AREA_H / 2
                                img_canvas.create_image(cx, cy, anchor="center", image=thumb)
                            else:
                                error_text = "Boş Bölge"
                        except Exception as e:
                            print(f"Resim yükleme hatası ({name}): {e}")
                            error_text = "Yükleme Hatası"
                    else:
                        error_text = "Geçersiz Boyut"
                else:
                     error_text = "Dosya Yok"

                if error_text:
                    img_canvas.create_text(IMG_AREA_W/2, IMG_AREA_H/2, text=error_text, fill="#666", font=("Segoe UI", 9))

                # 2. Bilgi ve Seçim
                # İsim (Kısaltılmış)
                disp_name = (name[:20] + '..') if len(name) > 20 else name
                tk.Label(cell, text=disp_name, bg="#3c3f41", fg="white", font=("Segoe UI", 9, "bold")).pack()
                
                # Yol (Kısaltılmış)
                short_path = os.path.basename(img_rel)
                tk.Label(cell, text=short_path, bg="#3c3f41", fg="#aaaaaa", font=("Segoe UI", 8)).pack()

                # Checkbox
                var = tk.BooleanVar(value=(rid in selected_ids_set))
                var_by_id[rid] = var
                chk = ttk.Checkbutton(cell, text="Seç", variable=var)
                chk.pack(pady=(5,0))
                
                # Tüm hücreye tıklayınca seçimi tersine çevir (isteğe bağlı UX iyileştirmesi)
                # Ancak checkbox'ın kendi event'iyle çakışabilir, şimdilik sadece checkbox.

            except Exception:
                continue

        # Actions
        action = ttk.Frame(dlg)
        action.pack(fill="x", side="bottom", pady=10, padx=10)
        
        def on_ok():
            try:
                chosen = [rid for rid, v in var_by_id.items() if v.get()]
                self.level_service.set_level_background_region_ids(self.level_id, chosen)  # type: ignore[attr-defined]
                messagebox.showinfo("Kaydedildi", "Arka plan bölgeleri kaydedildi.", parent=dlg)
                # Sağ panelde küçük önizlemeyi yenile
                self._refresh_bg_region_preview()
                # Kanvasta düşen item arkaplan önizlemesini güncelle
                self._update_item_bg_preview()
                dlg.destroy()
            except Exception as e:
                messagebox.showerror("Hata", f"Kaydedilemedi: {e}", parent=dlg)
        
        ttk.Button(action, text="Kaydet", command=on_ok, style="Accent.TButton").pack(side=tk.RIGHT, padx=6)
        ttk.Button(action, text="İptal", command=dlg.destroy).pack(side=tk.RIGHT)

    def _refresh_bg_region_preview(self) -> None:
        """Seçili arka plan bölge ID'lerine göre küçük önizlemeleri listeler."""
        # Panel yoksa veya level değilse atla
        if not hasattr(self, 'level_bg_preview_frame'):
            return
        for w in self.level_bg_preview_frame.winfo_children():
            w.destroy()
        level_id = getattr(self, 'level_id', None)
        if not self.level_service or not self.sprite_service or not level_id:
            ttk.Label(self.level_bg_preview_frame, text="Seçim yok.").pack(anchor="w")
            return
        try:
            selected = set(self.level_service.get_level_background_region_ids(level_id))
            if not selected:
                ttk.Label(self.level_bg_preview_frame, text="Seçim yok.").pack(anchor="w")
                return
            regions = self.sprite_service.list_sprite_regions()
            show = [r for r in regions if int(r.get('id', 0)) in selected]
        except Exception:
            ttk.Label(self.level_bg_preview_frame, text="Seçimler yüklenemedi.").pack(anchor="w")
            return

        wrap = ttk.Frame(self.level_bg_preview_frame); wrap.pack(fill="x")
        # referansları sakla
        self._bg_prev_refs: List[ImageTk.PhotoImage] = []

        def abs_project(rel: str) -> Optional[str]:
            if not rel:
                return None
            p = rel.replace('\\','/').strip()
            if os.path.isabs(p):
                return p
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
            return os.path.join(project_root, p)

        row = ttk.Frame(wrap); row.pack(fill="x")
        for reg in show:
            try:
                rid = int(reg.get('id', 0))
                img_rel = str(reg.get("image_path") or "")
                name = str(reg.get("name") or "")
                x = int(reg.get("x", 0)); y = int(reg.get("y", 0))
                w = int(reg.get("width", 0)); h = int(reg.get("height", 0))
                abs_path = abs_project(img_rel)
                thumb = None
                if abs_path and os.path.isfile(abs_path) and w > 0 and h > 0:
                    pil = Image.open(abs_path)
                    iw, ih = pil.size
                    x1 = max(0, min(iw, x)); y1 = max(0, min(ih, y))
                    x2 = max(0, min(iw, x + w)); y2 = max(0, min(ih, y + h))
                    if x2 > x1 and y2 > y1:
                        pil_crop = pil.crop((x1, y1, x2, y2))
                        # küçük önizleme 64x48
                        tw, th = 64, 48
                        scale = min(tw / max(1, pil_crop.width), th / max(1, pil_crop.height))
                        rz = (max(1, int(pil_crop.width * scale)), max(1, int(pil_crop.height * scale)))
                        pil_thumb = pil_crop.resize(rz, Image.LANCZOS)
                        thumb = ImageTk.PhotoImage(pil_thumb)
                        self._bg_prev_refs.append(thumb)
                cell = ttk.Frame(row, padding=(4,2)); cell.pack(side=tk.LEFT)
                if thumb:
                    tk.Label(cell, image=thumb).pack()
                # Silme butonu: bu bölgeyi seçili listeden kaldırır
                btn_row = ttk.Frame(cell); btn_row.pack(fill="x")
                ttk.Label(btn_row, text=name).pack(side=tk.LEFT)
                def _do_remove(rid_val: int = rid):
                    try:
                        level_id = getattr(self, 'level_id', None)
                        if not (self.level_service and level_id):
                            return
                        current = list(self.level_service.get_level_background_region_ids(level_id))  # type: ignore[attr-defined]
                        if rid_val in current:
                            new_list = [x for x in current if x != rid_val]
                            self.level_service.set_level_background_region_ids(level_id, new_list)  # type: ignore[attr-defined]
                            # UI yenile
                            self._refresh_bg_region_preview()
                            self._update_item_bg_preview()
                    except Exception as e:
                        try:
                            messagebox.showerror("Hata", f"Bölge silinemedi: {e}")
                        except Exception:
                            pass
                ttk.Button(btn_row, text="Sil", width=4, command=_do_remove).pack(side=tk.RIGHT, padx=(6,0))
            except Exception:
                continue

        # Kanvasta büyük önizlemeyi güncelle
        try:
            self._update_item_bg_preview()
        except Exception:
            pass

    # Yardımcı: Önizleme üzerinden silme butonlarının kullanacağı fonksiyon (gerekirse doğrudan da çağrılabilir)
    def _remove_level_bg_region(self, region_id: int) -> None:
        try:
            level_id = getattr(self, 'level_id', None)
            if not (self.level_service and level_id):
                return
            current = list(self.level_service.get_level_background_region_ids(level_id))  # type: ignore[attr-defined]
            if region_id in current:
                new_list = [x for x in current if x != region_id]
                self.level_service.set_level_background_region_ids(level_id, new_list)  # type: ignore[attr-defined]
                self._refresh_bg_region_preview()
                self._update_item_bg_preview()
        except Exception:
            pass

    def _update_item_bg_preview(self) -> None:
        """Seçili arka plan sprite bölgesinden birini kanvasta örnek metinle ölçekleyerek gösterir.

        - Text sığacak şekilde arkaplan ölçeklenir (oran korunur).
        - Örnek metin, seçili fontla (Segoe UI, 24) görüntülenir.
        """
        if not self._ensure_canvas() or not hasattr(self, '_item_preview_id'):
            return
        # Sadece level ekranında çalış
        if (self.screen_type or "").lower() != "level" or not self.level_service or not self.level_id:
            try:
                self.canvas.itemconfigure(self._item_preview_id, state="hidden")
                self.canvas.itemconfigure(self._item_preview_text_id, state="hidden")
            except Exception:
                pass
            return

        # Önce önceki dinamik önizlemeleri temizle
        try:
            for img_id, txt_id in self._item_preview_nodes:
                try:
                    self.canvas.delete(img_id)
                except Exception:
                    pass
                try:
                    self.canvas.delete(txt_id)
                except Exception:
                    pass
        finally:
            self._item_preview_nodes = []
            self._item_preview_img_refs = []

        # Eski tekil yer tutucuları gizle
        try:
            self.canvas.itemconfigure(self._item_preview_id, state="hidden")
            self.canvas.itemconfigure(self._item_preview_text_id, state="hidden")
        except Exception:
            pass

        # Seçili tüm region'ları örnekle
        try:
            selected_ids = self.level_service.get_level_background_region_ids(self.level_id)  # type: ignore[attr-defined]
        except Exception:
            selected_ids = []
        if not selected_ids:
            return

        # Region detaylarını al
        try:
            regions = self.sprite_service.list_sprite_regions()
            region_list = [r for r in regions if int(r.get('id', -1)) in set(int(x) for x in selected_ids)]
        except Exception:
            region_list = []
        if not region_list:
            return

        # Örnek metin ve yazı tipi
        import tkinter.font as tkfont
        sample_text = "12 N"
        font = tkfont.Font(family="Segoe UI", size=24)
        text_w = max(1, font.measure(sample_text))
        text_h = max(1, font.metrics("linespace"))
        pad_x, pad_y = 16, 10

        # Her region için scaled görsel boyutunu hesapla ve toplam genişliği bul
        previews: list[tuple[int,int,ImageTk.PhotoImage]] = []  # (w,h,photo)
        spacing = 16
        for reg in region_list:
            entry = {
                'image': reg.get('image_path'),
                'name': reg.get('name'),
                'x': reg.get('x'), 'y': reg.get('y'),
                'width': reg.get('width'), 'height': reg.get('height')
            }
            pil_crop = self._load_crop_image(entry)
            if pil_crop is None:
                continue
            bg_w, bg_h = max(1, pil_crop.width), max(1, pil_crop.height)
            target_w = text_w + pad_x * 2
            target_h = text_h + pad_y * 2
            scale = max(target_w / bg_w, target_h / bg_h)
            new_w = max(1, int(bg_w * scale * self.zoom))
            new_h = max(1, int(bg_h * scale * self.zoom))
            pil_scaled = pil_crop.resize((new_w, new_h), Image.LANCZOS)
            photo = ImageTk.PhotoImage(pil_scaled)
            previews.append((new_w, new_h, photo))
        if not previews:
            return

        total_w = sum(w for w,_,_ in previews) + spacing * (len(previews) - 1)
        cx_center = int(self._to_canvas(self.CANVAS_W / 2))
        top_y = int(self._to_canvas(90))
        start_x = cx_center - total_w // 2

        # Çiz ve referansları sakla
        cur_x = start_x
        for new_w, new_h, photo in previews:
            img_id = self.canvas.create_image(cur_x, top_y, anchor="nw", image=photo, tags=("__item_bg_preview__",))
            txt_id = self.canvas.create_text(cur_x + new_w/2, top_y + new_h/2, text=sample_text, fill="#FFFFFF", font=("Segoe UI", 24), anchor="center", tags=("__item_bg_preview_text__",))
            self._item_preview_nodes.append((img_id, txt_id))
            self._item_preview_img_refs.append(photo)
            cur_x += new_w + spacing

        # Efekt önizlemesini de (varsa) güncel konuma göre yeniden başlat
        try:
            self._restart_effect_preview()
        except Exception:
            pass

    def _ensure_canvas(self) -> bool:
        """Canvas'ın var olduğunu garantiler."""
        return hasattr(self, "canvas") and self.canvas is not None

    def _apply_canvas_bg(self, path: str) -> None:
        """Kanvas arkaplanını uygular (görseli 800x600'e sığdırır)."""
        try:
            img = Image.open(path)
            w = max(1, int(self.CANVAS_W * self.zoom))
            h = max(1, int(self.CANVAS_H * self.zoom))
            img = img.resize((w, h), Image.LANCZOS)
            self._bg_img_ref = ImageTk.PhotoImage(img)
            self.canvas.delete("__bg__")
            self.canvas.create_image(0, 0, anchor="nw", image=self._bg_img_ref, tags=("__bg__",))
            self._canvas_bg_path = path
            # Always keep background at bottom
            try:
                self.canvas.tag_lower("__bg__")
            except Exception:
                pass
        except Exception as e:
            messagebox.showwarning("Arkaplan", f"Görsel yüklenemedi: {e}")

    # --- Zoom helpers ---
    def _to_canvas(self, v: float) -> float:
        return v * self.zoom

    def _to_logical(self, v: float) -> float:
        return v / self.zoom if self.zoom else v

    def _on_zoom_change(self) -> None:
        val = self.zoom_var.get().strip().replace('%', '')
        try:
            pct = int(val)
            if pct < 25 or pct > 300:
                raise ValueError
        except ValueError:
            self.zoom = 1.0
            self.zoom_var.set("100%")
        else:
            self.zoom = pct / 100.0
        # Canvas boyutunu güncelle
        self.canvas.config(width=int(self.CANVAS_W * self.zoom), height=int(self.CANVAS_H * self.zoom))
        # Arkaplanı yeniden uygula
        if self._canvas_bg_path:
            self._apply_canvas_bg(self._canvas_bg_path)
        # Öğeleri yeniden konumlandır/ölçekle
        self._reflow_items()
        # Zoom değişiminde de item bg önizlemesini tazele
        self._update_item_bg_preview()
        # Efekt önizlemeyi de yeniden konumlandır
        self._restart_effect_preview()

    # Asset scanning
    def _scan_assets(self) -> None:
        """assets/ ve assets/games/<game_id>/ altındaki görüntü/ses dosyalarını (RECURSIVE) listele.

        Ek olarak proje kökündeki `img/` klasörünü de fallback olarak tarar.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        assets_root = os.path.join(project_root, "assets")
        per_game_root = os.path.join(assets_root, "games", str(self.game_id))
        img_root_fallback = os.path.join(project_root, "img")

        img_exts = {".png", ".jpg", ".jpeg", ".bmp", ".gif"}
        aud_exts = {".mp3", ".wav", ".ogg", ".mid", ".midi"}
        images: List[str] = []
        audios: List[str] = []

        def add_files_recursive(base_dir: str, exts: set[str]) -> List[str]:
            files: List[str] = []
            if os.path.isdir(base_dir):
                for root, _, fnames in os.walk(base_dir):
                    for fn in fnames:
                        ext = os.path.splitext(fn)[1].lower()
                        if ext in exts:
                            abs_p = os.path.join(root, fn)
                            rel = os.path.relpath(abs_p, project_root).replace('\\','/')
                            files.append(rel)
            return sorted(files, key=lambda p: p.lower())

        # Görseller
        images.extend(add_files_recursive(assets_root, img_exts))
        images.extend(add_files_recursive(per_game_root, img_exts))
        images.extend(add_files_recursive(img_root_fallback, img_exts))

        # Sesler
        audios.extend(add_files_recursive(assets_root, aud_exts))
        audios.extend(add_files_recursive(per_game_root, aud_exts))

        # De-duplicate preserving order
        def dedup(lst: List[str]) -> List[str]:
            seen = set(); out = []
            for x in lst:
                if x not in seen:
                    seen.add(x); out.append(x)
            return out

        images = dedup(images)
        audios = dedup(audios)

        backgrounds_root = os.path.join(assets_root, "images", "backgrounds")
        backgrounds_rel = os.path.relpath(backgrounds_root, project_root).replace('\\', '/')
        if not backgrounds_rel.endswith('/'):
            backgrounds_rel += '/'
        background_images = [img for img in images if img.startswith(backgrounds_rel)]

        self._images = images
        self._audios = audios
        self._background_images = background_images

        # Mappingleri temizle
        self._bg_display_to_path.clear()
        self._bg_path_to_display.clear()
        self._img_display_map = {}
        self._img_path_map = {}
        self._audio_display_map = {}
        self._audio_path_map = {}

        # Helper to fill map
        def fill_map(file_list, d_map, p_map):
            counts = Counter(os.path.basename(p) or p for p in file_list)
            display_list = []
            for rel in file_list:
                base = os.path.basename(rel) or rel
                label = base
                if counts[base] > 1:
                    parent = os.path.basename(os.path.dirname(rel)) or os.path.dirname(rel)
                    if parent:
                        label = f"{base} ({parent})"
                # Unique garantisi
                orig_label = label
                idx = 2
                while label in d_map:
                    label = f"{orig_label} [{idx}]"
                    idx += 1
                
                d_map[label] = rel
                p_map[rel] = label
                display_list.append(label)
            return display_list

        # Görseller (Image Assets)
        img_display_values = fill_map(images, self._img_display_map, self._img_path_map)
        # Sesler (Audio Assets)
        aud_display_values = fill_map(audios, self._audio_display_map, self._audio_path_map)

        # Arka Plan (Sadece background klasöründekiler için ayrı map'i de doldur, uyumluluk için)
        background_display_values = []
        bg_counts = Counter(os.path.basename(p) or p for p in background_images)
        for rel in background_images:
            base = os.path.basename(rel) or rel
            label = base
            if bg_counts[base] > 1:
                parent = os.path.basename(os.path.dirname(rel)) or os.path.dirname(rel)
                if parent:
                    label = f"{base} ({parent})"
            unique_label = self._make_unique_bg_label(label)
            self._bg_display_to_path[unique_label] = rel
            self._bg_path_to_display[rel] = unique_label
            background_display_values.append(unique_label)

        self.bg_combo['values'] = background_display_values
        self.music_combo['values'] = aud_display_values
        
        # Level comboboxları
        try:
            self.level_basket_sprite_combo['values'] = img_display_values
        except Exception: pass
        try:
            self.level_hud_sprite_combo['values'] = img_display_values
        except Exception: pass
        try:
             # SFX Combos
            if hasattr(self, 'level_sfx_ok_combo'):
                self.level_sfx_ok_combo['values'] = aud_display_values
            if hasattr(self, 'level_sfx_bad_combo'):
                self.level_sfx_bad_combo['values'] = aud_display_values
        except Exception: pass

        # Varsayılan seçimleri doldur
        if background_images and not self.bg_path_var.get():
            self._set_bg_selection(background_images[0])
            abs_bg0 = self._abs_assets_path(background_images[0])
            if abs_bg0 and os.path.isfile(abs_bg0):
                self._apply_canvas_bg(abs_bg0)
        
        # Mevcut path değerlerine göre display değerlerini güncelle
        self._refresh_display_vars()

    def _refresh_display_vars(self):
        """Path değişkenlerindeki yollara göre Display değişkenlerini günceller."""
        try:
            # Helper
            def _upd(d_var, p_var, p_map):
                path = p_var.get()
                if path and path in p_map:
                    d_var.set(p_map[path])
                elif path: # Map'te yoksa path göster
                    d_var.set(path)

            # Image bazlılar
            _upd(self.level_basket_display_var, self.level_basket_sprite_var, self._img_path_map)
            _upd(self.level_hud_display_var, self.level_hud_sprite_var, self._img_path_map)
            # Efekt display değerleri için öncelikle image_path -> efekt ismi eşlemesini kullan
            try:
                img_to_name = getattr(self, "_effect_image_to_name", {}) or {}
                ok_path = (self.level_effect_ok_var.get() or "").strip()
                bad_path = (self.level_effect_bad_var.get() or "").strip()
                if ok_path and ok_path in img_to_name:
                    self.level_effect_ok_display_var.set(img_to_name[ok_path])
                else:
                    _upd(self.level_effect_ok_display_var, self.level_effect_ok_var, self._img_path_map)
                if bad_path and bad_path in img_to_name:
                    self.level_effect_bad_display_var.set(img_to_name[bad_path])
                else:
                    _upd(self.level_effect_bad_display_var, self.level_effect_bad_var, self._img_path_map)
            except Exception:
                _upd(self.level_effect_ok_display_var, self.level_effect_ok_var, self._img_path_map)
                _upd(self.level_effect_bad_display_var, self.level_effect_bad_var, self._img_path_map)
            
            # Audio bazlılar
            _upd(self.level_sfx_ok_display_var, self.level_sfx_ok_var, self._audio_path_map)
            _upd(self.level_sfx_bad_display_var, self.level_sfx_bad_var, self._audio_path_map)
            _upd(self.music_display_var, self.music_path_var, self._audio_path_map)
            
        except Exception:
            pass

    def _abs_assets_path(self, rel: str) -> Optional[str]:
        if not rel:
            return None
        if os.path.isabs(rel):
            return rel
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        return os.path.join(project_root, rel)

    def _add_label(self) -> None:
        """Kanvas üzerine bir Label ekler."""
        if not self._ensure_canvas():
            return
        x, y = 100, 100
        text = "Yeni Label"
        cx, cy = int(self._to_canvas(x)), int(self._to_canvas(y))
        cid = self.canvas.create_text(cx, cy, text=text, fill="#FFFFFF", anchor="nw", font=("Segoe UI", 20))
        name = self._gen_name("label")
        item = {"id": cid, "type": "label", "props": {"name": name, "text": text, "color": "#FFFFFF", "font_size": 20, "x": x, "y": y}}
        self.items.append(item)
        self._select_item(item)
        # Insert into tree and select
        try:
            self.obj_tree.insert("", tk.END, iid=str(cid), values=(f"{name} (label)",))
            self.obj_tree.selection_set(str(cid))
        except Exception:
            pass
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

    def _apply_image_sprite(self) -> None:
        """Seçili image-only sprite öğesine combobox'tan seçilen sprite bölgesini uygular ve çizer.

        - Combobox değeri "name — image_rel" formatındadır.
        - Bölgeyi bulup kırpılmış resmi oluşturur, kanvasa image olarak yerleştirir.
        - Öğenin genişlik/yüksekliğini bölge ölçülerine göre günceller.
        - item.props.sprite alanına meta veriyi yazar.
        """
        if not self.selected_item or self.selected_item["type"] != "image":
            return
        key = self.image_sprite_var.get().strip()
        if not key or " — " not in key:
            return
        name, image_rel = key.split(" — ", 1)
        entry = self._find_sprite_region(image_rel, name)
        if not entry:
            messagebox.showwarning("Sprite", "Seçilen sprite bölgesi bulunamadı.")
            return
        # yükle ve uygula
        pil_crop = self._load_crop_image(entry)
        if pil_crop is None:
            messagebox.showwarning("Sprite", "Görsel yüklenemedi.")
            return
        it = self.selected_item
        x = int(it["props"].get("x", 0)); y = int(it["props"].get("y", 0))
        w = int(entry.get("width", pil_crop.width)); h = int(entry.get("height", pil_crop.height))
        cx, cy = int(self._to_canvas(x)), int(self._to_canvas(y))
        cw, ch = int(self._to_canvas(w)), int(self._to_canvas(h))
        img_zoomed = pil_crop.resize((max(1,cw), max(1,ch)), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img_zoomed)
        # mevcut primitive'i (rect/image) kaldır ve yeni image ekle
        try:
            self.canvas.delete(it["id"])
        except Exception:
            pass
        img_id = self.canvas.create_image(cx, cy, anchor="nw", image=photo)
        # prop güncellemeleri ve referansları koru
        it["props"]["pil_crop"] = pil_crop
        it["props"]["img_ref"] = photo
        it["props"]["w"], it["props"]["h"] = w, h
        it["props"]["sprite"] = {"image": image_rel, "name": name, "x": int(entry.get("x",0)), "y": int(entry.get("y",0)), "width": w, "height": h}
        it["id"] = img_id
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass
        self._set_dirty(True)

    def _add_image_sprite(self) -> None:
        """Kanvas üzerine yalnızca görselden oluşan bir sprite ekler (buton değil)."""
        if not self._ensure_canvas():
            return
        x, y = 400, 200
        # Başlangıçta bir placeholder dikdörtgen kullan; sprite seçilince görsel ile değiştirilir
        w, h = 128, 128
        cx, cy, cw, ch = int(self._to_canvas(x)), int(self._to_canvas(y)), int(self._to_canvas(w)), int(self._to_canvas(h))
        rect = self.canvas.create_rectangle(cx, cy, cx+cw, cy+ch, outline="#888", dash=(3,2), fill="")
        name = self._gen_name("sprite")
        item = {"id": rect, "type": "image", "props": {"name": name, "x": x, "y": y, "w": w, "h": h}}
        self.items.append(item)
        self._select_item(item)
        try:
            self.obj_tree.insert("", tk.END, iid=str(rect), values=(f"{name} (sprite)",))
            self.obj_tree.selection_set(str(rect))
        except Exception:
            pass
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

    def _add_button(self) -> None:
        """Kanvas üzerine bir Buton (placeholder dikdörtgen + metin) ekler."""
        if not self._ensure_canvas():
            return
        x, y, w, h = 300, 300, 180, 48
        cx, cy, cw, ch = int(self._to_canvas(x)), int(self._to_canvas(y)), int(self._to_canvas(w)), int(self._to_canvas(h))
        rect = self.canvas.create_rectangle(cx, cy, cx+cw, cy+ch, fill="#4CAF50", outline="", tags=("button",))
        label = self.canvas.create_text(cx+cw/2, cy+ch/2, text="Başla", fill="#FFFFFF", font=("Segoe UI", 18), anchor="center", tags=("button",))
        name = self._gen_name("button")
        item = {"id": rect, "type": "button", "props": {"name": name, "text": "Başla", "action": "start_game", "w": w, "h": h, "x": x, "y": y, "label_id": label}}
        self.items.append(item)
        self._select_item(item)
        # Insert into tree and select
        try:
            self.obj_tree.insert("", tk.END, iid=str(rect), values=(f"{name} (button)",))
            self.obj_tree.selection_set(str(rect))
        except Exception:
            pass
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

    def _add_continue_button(self) -> None:
        """Kanvas üzerine 'Devam' yazılı ve 'continue_level' aksiyonlu bir buton ekler."""
        if not self._ensure_canvas():
            return
        x, y, w, h = 320, 360, 180, 48
        cx, cy, cw, ch = int(self._to_canvas(x)), int(self._to_canvas(y)), int(self._to_canvas(w)), int(self._to_canvas(h))
        rect = self.canvas.create_rectangle(cx, cy, cx+cw, cy+ch, fill="#4CAF50", outline="", tags=("button",))
        label = self.canvas.create_text(cx+cw/2, cy+ch/2, text="Devam", fill="#FFFFFF", font=("Segoe UI", 18), anchor="center", tags=("button",))
        name = self._gen_name("button")
        item = {"id": rect, "type": "button", "props": {"name": name, "text": "Devam", "action": "continue_level", "w": w, "h": h, "x": x, "y": y, "label_id": label}}
        self.items.append(item)
        self._select_item(item)
        try:
            self.obj_tree.insert("", tk.END, iid=str(rect), values=(f"{name} (button)",))
            self.obj_tree.selection_set(str(rect))
        except Exception:
            pass
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

    # Selection & dragging
    def _find_item_by_canvas_id(self, cid: int) -> Optional[Dict[str, Any]]:
        for it in self.items:
            if it["id"] == cid or it["props"].get("label_id") == cid:
                return it
        return None

    def _on_canvas_click(self, event) -> None:
        """Kanvas tıklamasında seçim ve sürükleme başlangıcı."""
        cid = self.canvas.find_closest(event.x, event.y)[0]
        it = self._find_item_by_canvas_id(cid)
        if it:
            self._select_item(it)
            self._drag_start = (event.x, event.y)
            # Sync selection to tree
            if self.obj_tree.exists(str(it["id"])):
                self.obj_tree.selection_set(str(it["id"]))
        else:
            self._select_item(None)

    def _on_drag(self, event) -> None:
        if not self.selected_item:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self._drag_start = (event.x, event.y)
        it = self.selected_item
        if it["type"] == "label":
            self.canvas.move(it["id"], dx, dy)
            cx, cy = self.canvas.coords(it["id"])  # canvas coords
            it["props"]["x"], it["props"]["y"] = float(self._to_logical(cx)), float(self._to_logical(cy))
        elif it["type"] == "button":
            # move rect and label together
            self.canvas.move(it["id"], dx, dy)
            self.canvas.move(it["props"]["label_id"], dx, dy)
            x1, y1, x2, y2 = self.canvas.coords(it["id"])  # canvas coords
            it["props"]["x"], it["props"]["y"] = float(self._to_logical(x1)), float(self._to_logical(y1))
        else:
            # image-only sprite
            self.canvas.move(it["id"], dx, dy)
            x1, y1, x2, y2 = self.canvas.coords(it["id"])  # for rectangle or image
            it["props"]["x"], it["props"]["y"] = float(self._to_logical(x1)), float(self._to_logical(y1))
        self._refresh_position_fields()

    def _on_drag_end(self, event) -> None:
        # Her sürükleme bitiminde kaydetme butonunu koyu yap
        self._set_dirty(True)

    def _select_item(self, item: Optional[Dict[str, Any]]) -> None:
        self.selected_item = item
        # toggle prop panels
        self.label_frame.pack_forget(); self.button_frame.pack_forget(); self.sprite_frame.pack_forget()
        if not item:
            return
        # set position fields
        self._refresh_position_fields()
        if item["type"] == "label":
            self.label_frame.pack(fill="x", pady=6)
            # load props
            self.label_text.delete("1.0", "end")
            self.label_text.insert("1.0", item["props"].get("text", ""))
            self.label_color_var.set(item["props"].get("color", "#FFFFFF"))
            self.label_size_var.set(str(item["props"].get("font_size", 20)))
        elif item["type"] == "button":
            self.button_frame.pack(fill="x", pady=6)
            self.button_text_var.set(item["props"].get("text", ""))
            self.button_action_var.set(item["props"].get("action", "start_game"))
            self.button_color_var.set(item["props"].get("bg_color", "#4CAF50"))
            # load sprite regions and set selection if present (DB-backed)
            self._load_sprite_regions()
            sp = item["props"].get("sprite") or {}
            if sp.get("name") and sp.get("image"):
                key = f"{sp.get('name')} — {sp.get('image')}"
                if key in (self.button_sprite_combo['values'] or ()):  
                    self.button_sprite_var.set(key)
        else:
            # image-only sprite props
            self.sprite_frame.pack(fill="x", pady=6)
            self._load_sprite_regions()
            sp = item["props"].get("sprite") or {}
            if sp.get("name") and sp.get("image"):
                key = f"{sp.get('name')} — {sp.get('image')}"
                if key in (self.image_sprite_combo['values'] or ()):  
                    self.image_sprite_var.set(key)
        # ensure bg stays behind
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

    def _refresh_position_fields(self) -> None:
        if not self.selected_item:
            self.pos_x_var.set(""); self.pos_y_var.set("")
            return
        it = self.selected_item
        if it["type"] == "label":
            x, y = it["props"].get("x", 0), it["props"].get("y", 0)
        else:
            x, y = it["props"].get("x", 0), it["props"].get("y", 0)
        self.pos_x_var.set(str(int(x)))
        self.pos_y_var.set(str(int(y)))

    def _apply_position(self) -> None:
        """Seçili öğeyi girilen pozisyona taşır."""
        if not self.selected_item:
            return
        try:
            x = int(self.pos_x_var.get()); y = int(self.pos_y_var.get())
        except ValueError:
            messagebox.showwarning("Konum", "Geçerli bir sayı girin.")
            return
        it = self.selected_item
        if it["type"] == "label":
            it["props"]["x"], it["props"]["y"] = x, y
            cx, cy = int(self._to_canvas(x)), int(self._to_canvas(y))
            self.canvas.coords(it["id"], cx, cy)
        elif it["type"] == "button":
            it["props"]["x"], it["props"]["y"] = x, y
            w = int(it["props"].get("w", 180))
            h = int(it["props"].get("h", 48))
            cx, cy, cw, ch = int(self._to_canvas(x)), int(self._to_canvas(y)), int(self._to_canvas(w)), int(self._to_canvas(h))
            if self.canvas.type(it["id"]) == 'image':
                self.canvas.coords(it["id"], cx, cy)
            else:
                self.canvas.coords(it["id"], cx, cy, cx+cw, cy+ch)
            # center text
            self.canvas.coords(it["props"]["label_id"], cx+cw/2, cy+ch/2)
        else:
            # image-only
            it["props"]["x"], it["props"]["y"] = x, y
            w = int(it["props"].get("w", 128))
            h = int(it["props"].get("h", 128))
            cx, cy = int(self._to_canvas(x)), int(self._to_canvas(y))
            if self.canvas.type(it["id"]) == 'image':
                self.canvas.coords(it["id"], cx, cy)
            else:
                self.canvas.coords(it["id"], cx, cy, cx+int(self._to_canvas(w)), cy+int(self._to_canvas(h)))
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass
        self._set_dirty(True)

    def _set_dirty(self, dirty: bool) -> None:
        """Kaydedilmemiş değişiklik var/yok işaretini ve buton stilini yönetir."""
        setattr(self, "_dirty", bool(dirty))
        try:
            self.save_btn.configure(style=("Accent.TButton" if dirty else "TButton"))
        except Exception:
            # Fallback: add asterisk to text
            base = "Kaydet*" if dirty else "Kaydet"
            self.save_btn.configure(text=base)

    def _pick_label_color(self) -> None:
        color = colorchooser.askcolor(title="Renk Seç", initialcolor=self.label_color_var.get())[1]
        if color:
            self.label_color_var.set(color)

    def _pick_button_color(self) -> None:
        color = colorchooser.askcolor(title="Buton Rengi", initialcolor=self.button_color_var.get())[1]
        if color:
            self.button_color_var.set(color)

    def _apply_label_props(self) -> None:
        """Label özelliklerini uygular (metin, renk, punto)."""
        if not self.selected_item or self.selected_item["type"] != "label":
            return
        text = self.label_text.get("1.0", "end-1c")
        color = self.label_color_var.get().strip() or "#FFFFFF"
        try:
            size = int(self.label_size_var.get())
        except ValueError:
            size = 20
        it = self.selected_item
        self.canvas.itemconfigure(it["id"], text=text, fill=color, font=("Segoe UI", size))
        it["props"].update({"text": text, "color": color, "font_size": size})

    def _apply_button_props(self) -> None:
        """Buton özelliklerini uygular (metin, aksiyon)."""
        if not self.selected_item or self.selected_item["type"] != "button":
            return
        txt = self.button_text_var.get().strip() or "Buton"
        act = self.button_action_var.get() or "start_game"
        it = self.selected_item
        # Update text label
        self.canvas.itemconfigure(it["props"]["label_id"], text=txt)
        # If no sprite selected, apply rect fill color
        bgc = self.button_color_var.get().strip() or "#4CAF50"
        # If currently using rect, recolor; if using image keep image
        if self.canvas.type(it["id"]) == 'rectangle':
            self.canvas.itemconfigure(it["id"], fill=bgc)
        it["props"].update({"text": txt, "action": act, "bg_color": bgc})

    def _apply_button_sprite(self) -> None:
        """Apply selected sprite region to the selected button and render it."""
        if not self.selected_item or self.selected_item["type"] != "button":
            return
        key = self.button_sprite_var.get().strip()
        if not key:
            return
        # Parse "name — image_rel"
        if " — " not in key:
            return
        name, image_rel = key.split(" — ", 1)
        entry = self._find_sprite_region(image_rel, name)
        if not entry:
            messagebox.showwarning("Sprite", "Seçilen sprite bölgesi bulunamadı.")
            return
        # Load and crop
        pil_crop = self._load_crop_image(entry)
        if pil_crop is None:
            messagebox.showwarning("Sprite", "Görsel yüklenemedi, dikdörtgen arkaplan kullanılacak.")
            return
        it = self.selected_item
        x = int(it["props"].get("x", 0)); y = int(it["props"].get("y", 0))
        w = int(entry.get("width", pil_crop.width)); h = int(entry.get("height", pil_crop.height))
        cx, cy = int(self._to_canvas(x)), int(self._to_canvas(y))
        cw, ch = int(self._to_canvas(w)), int(self._to_canvas(h))
        # Create zoomed PhotoImage from crop
        img_zoomed = pil_crop.resize((max(1,cw), max(1,ch)), Image.LANCZOS)
        photo = ImageTk.PhotoImage(img_zoomed)
        # Replace background primitive with image
        try:
            self.canvas.delete(it["id"])  # remove rect/image
        except Exception:
            pass
        img_id = self.canvas.create_image(cx, cy, anchor="nw", image=photo)
        # Keep references for GC
        it["props"]["pil_crop"] = pil_crop
        it["props"]["img_ref"] = photo
        it["props"]["w"], it["props"]["h"] = w, h
        it["id"] = img_id
        # Recenter text and ensure it's above image
        self.canvas.coords(it["props"]["label_id"], cx+cw/2, cy+ch/2)
        try:
            self.canvas.tag_raise(it["props"]["label_id"])
        except Exception:
            pass
        # Save sprite meta
        it["props"]["sprite"] = {"image": image_rel, "name": name, "x": int(entry.get("x",0)), "y": int(entry.get("y",0)), "width": w, "height": h}
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

    def _load_sprite_regions(self) -> None:
        """Load sprite regions from the GLOBAL pool (game_id=0) into combobox.

        Sprite bölgeleri artık oyundan bağımsızdır; bu yüzden 0 id'li global
        havuzdan yüklenir ve her oyunda kullanılabilir.
        """
        vals = []
        try:
            rows = self.sprite_service.list_sprite_regions()
            for e in rows:
                img = e.get("image_path"); name = e.get("name")
                if img and name:
                    vals.append(f"{name} — {img}")
        except Exception:
            pass
        self.button_sprite_combo['values'] = sorted(vals, key=lambda s: s.lower())
        self.image_sprite_combo['values'] = sorted(vals, key=lambda s: s.lower())
        # Level panelindeki sprite seçimleri sadece tanımlı sprite bölgelerini göstersin
        try:
            # Sadece sprite bölgelerini kullan (dosyaları karıştırma)
            sprite_vals = sorted(vals, key=lambda s: s.lower())
            self.level_basket_sprite_combo['values'] = sprite_vals
            self.level_hud_sprite_combo['values'] = sprite_vals
            
            # SFX comboboxları
            # self.level_sfx_ok_combo['values'] = self._audios
            # self.level_sfx_bad_combo['values'] = self._audios
        except Exception:
            pass

    def _find_sprite_region(self, image_rel: str, name: str) -> Optional[Dict[str,Any]]:
        """Find a sprite region by image path and name from the GLOBAL pool (game_id=0)."""
        try:
            rows = self.sprite_service.list_sprite_regions()
            for e in rows:
                if e.get("image_path") == image_rel and e.get("name") == name:
                    # Map keys to expected names
                    return {
                        "image": e.get("image_path"),
                        "x": int(e.get("x", 0)),
                        "y": int(e.get("y", 0)),
                        "width": int(e.get("width", 0)),
                        "height": int(e.get("height", 0))
                    }
        except Exception:
            return None
        return None

    def _current_game_id(self) -> int:
        """Return current game id from self or root, fallback to 1."""
        try:
            if getattr(self, 'game_id', None):
                return int(self.game_id)
        except Exception:
            pass
        try:
            root = self.winfo_toplevel()
            gid = getattr(root, 'current_game_id', None)
            if gid:
                return int(gid)
        except Exception:
            pass
        return 1

    # metadata helpers removed; DB is the source of truth for sprite regions

    def _load_crop_image(self, entry: Dict[str,Any]) -> Optional[Image.Image]:
        """Load and crop the image per entry; return PIL Image or None."""
        rel = entry.get("image")
        if not rel:
            return None
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../"))
        abs_path = os.path.join(project_root, rel)
        if not os.path.isfile(abs_path):
            return None
        try:
            base = Image.open(abs_path)
            x = int(entry.get("x",0)); y = int(entry.get("y",0)); w = int(entry.get("width",0)); h = int(entry.get("height",0))
            w = max(1,w); h = max(1,h)
            return base.crop((x, y, x+w, y+h))
        except Exception:
            return None

    # Save & Load
    def _collect_json(self) -> Dict[str, Any]:
        """Kanvas üzerindeki öğelerden JSON oluşturur."""
        widgets: List[Dict[str, Any]] = []
        for it in self.items:
            if it["type"] == "label":
                x = float(it["props"].get("x", 0))
                y = float(it["props"].get("y", 0))
                widgets.append({
                    "id": f"label_{it['id']}",
                    "type": "label",
                    "text": it["props"].get("text", ""),
                    "font": {"name": "Segoe UI", "size": it["props"].get("font_size", 20)},
                    "color": it["props"].get("color", "#FFFFFF"),
                    "x": int(round(x)), "y": int(round(y)),
                    "anchor": "nw",
                    "name": it["props"].get("name")
                })
            else:
                x = float(it["props"].get("x", 0))
                y = float(it["props"].get("y", 0))
                if it["type"] == "button":
                    w = float(it["props"].get("w", 180))
                    h = float(it["props"].get("h", 48))
                    btn = {
                        "id": f"button_{it['id']}",
                        "type": "button",
                        "x": int(round(x)), "y": int(round(y)),
                        "anchor": "nw",
                        "sprite": (it["props"].get("sprite") or {"source": "placeholder", "frame": {"width": int(round(w)), "height": int(round(h))}}),
                        "text_overlay": {
                            "text": it["props"].get("text", "Buton"),
                            "font": {"name": "Segoe UI", "size": 18},
                            "color": "#FFFFFF"
                        },
                        "action": it["props"].get("action", "start_game"),
                        "bg_color": it["props"].get("bg_color", "#4CAF50"),
                        "name": it["props"].get("name")
                    }
                    widgets.append(btn)
                else:
                    w = float(it["props"].get("w", 128))
                    h = float(it["props"].get("h", 128))
                    imgw = {
                        "id": f"image_{it['id']}",
                        "type": "image",
                        "x": int(round(x)), "y": int(round(y)),
                        "anchor": "nw",
                        "sprite": it["props"].get("sprite"),
                        "frame": {"width": int(round(w)), "height": int(round(h))},
                        "name": it["props"].get("name")
                    }
                    widgets.append(imgw)
        # Ekran kimliği ve türü parametrelerden gelir
        data = {
            "id": self.screen_name,
            "type": self.screen_type,
            "resolution": {"width": self.CANVAS_W, "height": self.CANVAS_H},
            "background": {"image": self.bg_path_var.get().strip(), "fit": "cover"},
            "music": self.music_path_var.get().strip(),
            "widgets": widgets
        }
        # Level türü için ilave ayarlar
        if (self.screen_type or "").lower() == "level":
            try:
                data["level_settings"] = {
                    "basket_sprite": self.level_basket_sprite_var.get().strip(),
                    "basket_length": int(self.level_basket_len_var.get() or "0"),
                    "sfx_correct": self.level_sfx_ok_var.get().strip(),
                    "sfx_wrong": self.level_sfx_bad_var.get().strip(),
                    "hud_sprite": self.level_hud_sprite_var.get().strip(),
                    "help_area": self.level_help_area_var.get().strip() or "none",
                    "effect_correct_sheet": self.level_effect_ok_var.get().strip(),
                    "effect_wrong_sheet": self.level_effect_bad_var.get().strip(),
                    "effect_fps": int(self.level_effect_fps_var.get() or "30"),
                    "effect_scale_percent": int(self.level_effect_scale_var.get() or "60"),
                }
            except Exception:
                # Bozuk değerler varsa sessizce atla
                pass
        return data

    def _save(self) -> None:
        """JSON'u DB'ye kaydeder (screens.name='opening')."""
        try:
            data = self._collect_json()
            payload = json.dumps(data, ensure_ascii=False, indent=2)
            self.screen_service.upsert_screen(self.game_id, self.screen_name, self.screen_type, payload)
            messagebox.showinfo("Kayıt", "Açılış ekranı kaydedildi.")
        except Exception as e:
            messagebox.showerror("Hata", f"Kaydedilemedi: {e}")

    def _load_existing(self) -> None:
        """Varsa DB'den 'opening' ekranını okur ve kanvasa uygular."""
        try:
            sc = self.screen_service.get_screen(self.game_id, self.screen_name)
            if not sc:
                return
            data = json.loads(sc.data_json)
            # background
            bg = (data.get("background") or {}).get("image")
            if bg:
                self._set_bg_selection(bg)
                abs_bg = self._abs_assets_path(bg)
                if abs_bg and os.path.isfile(abs_bg):
                    self._apply_canvas_bg(abs_bg)
            # music
            mus = data.get("music") or ""
            self.music_path_var.set(mus)
            # ensure combos show items if pre-saved values exist
            if mus and mus not in (self.music_combo['values'] or ()): 
                self.music_combo['values'] = list(self.music_combo['values']) + [mus]
            # Level ayarları
            try:
                if (self.screen_type or "").lower() == "level":
                    lv = data.get("level_settings") or {}
                    if lv:
                        # Basket
                        if lv.get("basket_sprite"):
                            self.level_basket_sprite_var.set(lv.get("basket_sprite"))
                        if "basket_length" in lv:
                            self.level_basket_len_var.set(str(lv.get("basket_length") or ""))
                        
                        # SFX
                        if lv.get("sfx_correct"):
                            self.level_sfx_ok_var.set(lv.get("sfx_correct"))
                        if lv.get("sfx_wrong"):
                            self.level_sfx_bad_var.set(lv.get("sfx_wrong"))
                        
                        # HUD
                        if lv.get("hud_sprite"):
                            self.level_hud_sprite_var.set(lv.get("hud_sprite"))
                        if lv.get("help_area"):
                            self.level_help_area_var.set(str(lv.get("help_area")))
                        
                        # Effects
                        if lv.get("effect_correct_sheet"):
                            self.level_effect_ok_var.set(lv.get("effect_correct_sheet"))
                        if lv.get("effect_wrong_sheet"):
                            self.level_effect_bad_var.set(lv.get("effect_wrong_sheet"))
                        
                        # FPS ve Ölçek
                        if "effect_fps" in lv:
                            try:
                                self.level_effect_fps_var.set(str(int(lv.get("effect_fps") or 30)))
                            except Exception:
                                pass
                        if "effect_scale_percent" in lv:
                            try:
                                self.level_effect_scale_var.set(str(int(lv.get("effect_scale_percent") or 60)))
                            except Exception:
                                pass

                    # Path değişkenlerini Display değişkenlerine (dosya adına) çevir
                    self._refresh_display_vars()

                    # EffectService ile kayıtlı efektleri yükle
                    self._load_effects_for_game()

                    # Mevcut veriyi yükledikten sonra önizlemeleri göster
                    self.after(100, self._update_basket_preview)  # UI'nin çizilmesini bekle
                    self.after(120, self._update_item_bg_preview)
            except Exception:
                pass
            # widgets
            for w in data.get("widgets", []):
                if w.get("type") == "label":
                    lx, ly = float(w.get("x", 0)), float(w.get("y", 0))
                    cx, cy = int(self._to_canvas(lx)), int(self._to_canvas(ly))
                    text = w.get("text", "")
                    color = w.get("color", "#FFFFFF")
                    size = int(((w.get("font") or {}).get("size") or 20))
                    cid = self.canvas.create_text(cx, cy, text=text, fill=color, anchor=w.get("anchor", "nw"), font=("Segoe UI", size))
                    name = (w.get("name") or (text.strip() if text.strip() else None)) or self._gen_name("label")
                    self.items.append({"id": cid, "type": "label", "props": {"name": name, "text": text, "color": color, "font_size": size, "x": lx, "y": ly}})
                elif w.get("type") == "button":
                    bx, by = float(w.get("x", 0)), float(w.get("y", 0))
                    txt = ((w.get("text_overlay") or {}).get("text") or "Buton")
                    name = (w.get("name") or (txt.strip() if txt.strip() else None)) or self._gen_name("button")
                    action = w.get("action", "start_game")
                    bgc = w.get("bg_color") or "#4CAF50"
                    sprite_info = w.get("sprite") or {}
                    # determine size
                    if sprite_info and sprite_info.get("width") and sprite_info.get("height"):
                        wth = float(sprite_info.get("width")); hgt = float(sprite_info.get("height"))
                    else:
                        frame = (sprite_info.get("frame") if isinstance(sprite_info, dict) else {}) or {}
                        wth = float(frame.get("width", 180)); hgt = float(frame.get("height", 48))
                    cx, cy = int(self._to_canvas(bx)), int(self._to_canvas(by))
                    cw, ch = int(self._to_canvas(wth)), int(self._to_canvas(hgt))
                    lbl = self.canvas.create_text(cx+cw/2, cy+ch/2, text=txt, fill="#FFFFFF", anchor="center", font=("Segoe UI", 18))
                    # try render sprite image
                    img_id = None; pil_crop = None; photo = None
                    if sprite_info.get("image") and sprite_info.get("name"):
                        entry = {"image": sprite_info.get("image"), "x": int(sprite_info.get("x",0)), "y": int(sprite_info.get("y",0)), "width": int(wth), "height": int(hgt)}
                        pil_crop = self._load_crop_image(entry)
                        if pil_crop is not None:
                            img_zoomed = pil_crop.resize((max(1,cw), max(1,ch)), Image.LANCZOS)
                            photo = ImageTk.PhotoImage(img_zoomed)
                            img_id = self.canvas.create_image(cx, cy, anchor="nw", image=photo)
                            try:
                                # ensure label stays on top of image
                                self.canvas.tag_raise(lbl)
                            except Exception:
                                pass
                    if img_id is None:
                        # fallback to colored rect
                        rect = self.canvas.create_rectangle(cx, cy, cx+cw, cy+ch, fill=bgc, outline="")
                        props = {"name": name, "text": txt, "action": action, "w": wth, "h": hgt, "x": bx, "y": by, "label_id": lbl, "bg_color": bgc}
                        self.items.append({"id": rect, "type": "button", "props": props})
                    else:
                        props = {"name": name, "text": txt, "action": action, "w": wth, "h": hgt, "x": bx, "y": by, "label_id": lbl, "bg_color": bgc, "sprite": sprite_info, "pil_crop": pil_crop, "img_ref": photo}
                        self.items.append({"id": img_id, "type": "button", "props": props})
                elif w.get("type") == "image":
                    ix, iy = float(w.get("x", 0)), float(w.get("y", 0))
                    frame = (w.get("frame") or {}) if isinstance(w.get("frame"), dict) else {}
                    iw = float(frame.get("width", 128)); ih = float(frame.get("height", 128))
                    cx, cy = int(self._to_canvas(ix)), int(self._to_canvas(iy))
                    cw, ch = int(self._to_canvas(iw)), int(self._to_canvas(ih))
                    sp = w.get("sprite") or {}
                    # Varsayılan olarak placeholder dikdörtgen çiz; sprite varsa görsel bas
                    img_id = None; pil_crop = None; photo = None
                    if sp.get("image") and sp.get("name"):
                        entry = {"image": sp.get("image"), "x": int(sp.get("x",0)), "y": int(sp.get("y",0)), "width": int(iw), "height": int(ih)}
                        pil_crop = self._load_crop_image(entry)
                        if pil_crop is not None:
                            img_zoomed = pil_crop.resize((max(1,cw), max(1,ch)), Image.LANCZOS)
                            photo = ImageTk.PhotoImage(img_zoomed)
                            img_id = self.canvas.create_image(cx, cy, anchor="nw", image=photo)
                    if img_id is None:
                        # Placeholder
                        rect = self.canvas.create_rectangle(cx, cy, cx+cw, cy+ch, outline="#888", dash=(3,2), fill="")
                        self.items.append({"id": rect, "type": "image", "props": {"name": w.get("name"), "x": ix, "y": iy, "w": iw, "h": ih}})
                    else:
                        self.items.append({"id": img_id, "type": "image", "props": {"name": w.get("name"), "x": ix, "y": iy, "w": iw, "h": ih, "sprite": sp, "pil_crop": pil_crop, "img_ref": photo}})
            # Fill object tree after load
            self._populate_tree()
            # keep bg at bottom
            try:
                self.canvas.tag_lower("__bg__")
            except Exception:
                pass
        except Exception as e:
            messagebox.showwarning("Yükleme", f"Ekran yüklenemedi: {e}")

    def _reflow_items(self) -> None:
        """Zoom değiştiğinde tüm öğeleri yeniden boyutlandır/konumlandır."""
        for it in self.items:
            if it["type"] == "label":
                x, y = it["props"].get("x", 0), it["props"].get("y", 0)
                cx, cy = int(self._to_canvas(x)), int(self._to_canvas(y))
                self.canvas.coords(it["id"], cx, cy)
            else:
                x, y = it["props"].get("x", 0), it["props"].get("y", 0)
                w = it["props"].get("w", 180)
                h = it["props"].get("h", 48)
                cx, cy, cw, ch = int(self._to_canvas(x)), int(self._to_canvas(y)), int(self._to_canvas(w)), int(self._to_canvas(h))
                if self.canvas.type(it["id"]) == 'image' and it["props"].get("pil_crop"):
                    # Resize image by zoom and update
                    pil_crop = it["props"].get("pil_crop")
                    img_zoomed = pil_crop.resize((max(1,cw), max(1,ch)), Image.LANCZOS)
                    photo = ImageTk.PhotoImage(img_zoomed)
                    it["props"]["img_ref"] = photo
                    self.canvas.itemconfigure(it["id"], image=photo)
                    self.canvas.coords(it["id"], cx, cy)
                else:
                    self.canvas.coords(it["id"], cx, cy, cx+cw, cy+ch)
                # Sadece butonlarda label merkezini güncelle
                if it["type"] == "button" and "label_id" in it["props"]:
                    self.canvas.coords(it["props"]["label_id"], cx+cw/2, cy+ch/2)
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

    def _on_drag(self, event) -> None:
        if not self.selected_item:
            return
        dx = event.x - self._drag_start[0]
        dy = event.y - self._drag_start[1]
        self._drag_start = (event.x, event.y)
        it = self.selected_item
        if it["type"] == "label":
            self.canvas.move(it["id"], dx, dy)
            cx, cy = self.canvas.coords(it["id"])  # canvas coords
            it["props"]["x"], it["props"]["y"] = float(self._to_logical(cx)), float(self._to_logical(cy))
        elif it["type"] == "button":
            # buton: rect/image ve label birlikte hareket eder
            self.canvas.move(it["id"], dx, dy)
            if "label_id" in it["props"]:
                self.canvas.move(it["props"]["label_id"], dx, dy)
            if self.canvas.type(it["id"]) == 'image':
                x1, y1 = self.canvas.coords(it["id"])  # (x,y)
                it["props"]["x"], it["props"]["y"] = float(self._to_logical(x1)), float(self._to_logical(y1))
            else:
                x1, y1, x2, y2 = self.canvas.coords(it["id"])  # (x1,y1,x2,y2)
                it["props"]["x"], it["props"]["y"] = float(self._to_logical(x1)), float(self._to_logical(y1))
        else:
            # image-only sprite: sadece görüntü hareket eder
            self.canvas.move(it["id"], dx, dy)
            x1, y1 = self.canvas.coords(it["id"])  # (x,y)
            it["props"]["x"], it["props"]["y"] = float(self._to_logical(x1)), float(self._to_logical(y1))
        self._refresh_position_fields()

    def _update_basket_preview(self) -> None:
        """Seçili sepet sprite'ını ve uzunluğunu kullanarak kanvasta bir önizleme çizer."""
        if not self._ensure_canvas() or not hasattr(self, '_basket_preview_id'):
            return

        key = self.level_basket_sprite_var.get().strip()
        if not key:
            self.canvas.itemconfigure(self._basket_preview_id, state="hidden")
            return

        try:
            basket_len = int(self.level_basket_len_var.get())
            if basket_len <= 0:
                self.canvas.itemconfigure(self._basket_preview_id, state="hidden")
                return
        except (ValueError, TypeError):
            self.canvas.itemconfigure(self._basket_preview_id, state="hidden")
            return

        pil_crop = None

        # Eğer " — " içeriyorsa sprite region'dır
        if " — " in key:
            name, image_rel = key.split(" — ", 1)
            entry = self._find_sprite_region(image_rel, name)
            if entry:
                pil_crop = self._load_crop_image(entry)
        else:
            # Değilse doğrudan dosya yoludur
            abs_path = self._abs_assets_path(key)
            if abs_path and os.path.isfile(abs_path):
                try:
                    pil_crop = Image.open(abs_path)
                except Exception:
                    pass

        if not pil_crop:
            self.canvas.itemconfigure(self._basket_preview_id, state="hidden")
            return

        try:
            # Görüntüyü en/boy oranını koruyarak yeniden boyutlandır
            w, h = pil_crop.size
            aspect_ratio = h / w if w > 0 else 1
            new_w = int(self._to_canvas(basket_len))
            new_h = int(new_w * aspect_ratio)

            if new_w < 1 or new_h < 1:
                self.canvas.itemconfigure(self._basket_preview_id, state="hidden")
                return

            img_resized = pil_crop.resize((new_w, new_h), Image.LANCZOS)
            self._basket_preview_img_ref = ImageTk.PhotoImage(img_resized)

            # Kanvas öğesini güncelle
            self.canvas.itemconfigure(self._basket_preview_id, image=self._basket_preview_img_ref, state="normal")
            self.canvas.tag_raise(self._basket_preview_id) # Diğer her şeyin üzerinde olsun

        except Exception as e:
            print(f"Error updating basket preview: {e}")
            self.canvas.itemconfigure(self._basket_preview_id, state="hidden")

        # Sepet güncellendikten sonra efekt önizlemeyi yeniden başlat (konum ve ölçek)
        try:
            self._restart_effect_preview()
        except Exception:
            pass

    def _restart_effect_preview(self) -> None:
        """Seçili efektleri sepet üzerinde animasyon olarak oynatır.

        Öncelik sırası:
        - Eğer EffectService ile yüklenmiş bir efekt parametresi (image_path + frames) varsa, kareler buradan üretilir.
        - Aksi halde, eski davranış korunarak efekt sheet'i 6x5 sabit grid ile bölünür.
        """
        # Yalnızca level ekranında çalış
        if (self.screen_type or "").lower() != "level":
            return
        if not self._ensure_canvas() or self._basket_preview_id is None or self._effect_preview_id is None:
            return

        # Önce eski zamanlayıcıyı durdur
        self._stop_effect_preview()

        # Seçilen efekt İSİMLERİNİ ve image path'lerini oku
        ok_name = (self.level_effect_ok_display_var.get() or "").strip()
        bad_name = (self.level_effect_bad_display_var.get() or "").strip()
        ok_rel = (self.level_effect_ok_var.get() or "").strip()
        bad_rel = (self.level_effect_bad_var.get() or "").strip()

        params_map = getattr(self, "_effect_name_to_params", {}) or {}

        def _build_frames_from_params(name: str, fallback_rel: str) -> list[ImageTk.PhotoImage]:
            params = params_map.get(name)
            if not params:
                # Herhangi bir parametre eşleşmesi yoksa sheet fallback'ine dön
                return self._slice_effect_sheet(fallback_rel) if fallback_rel else []
            img_rel = (params.get("image_path") or "").strip() or fallback_rel
            if not img_rel:
                return []
            abs_path = self._abs_assets_path(img_rel)
            if not abs_path or not os.path.isfile(abs_path):
                return []
            try:
                sheet = Image.open(abs_path)
            except Exception:
                return []
            frames_conf = params.get("frames") or []
            if not isinstance(frames_conf, list) or not frames_conf:
                # Kare listesi yoksa tekrar sheet fallback'i dene
                return self._slice_effect_sheet(img_rel)

            # Hedef genişlik: sepet uzunluğunun %scale'i (mevcut davranışla uyumlu)
            try:
                basket_len = max(1, int(self.level_basket_len_var.get() or "128"))
            except Exception:
                basket_len = 128
            try:
                scale_pct = int(self.level_effect_scale_var.get() or "60")
            except Exception:
                scale_pct = 60
            scale_pct = max(10, min(200, scale_pct))
            target_w = max(16, int(self._to_canvas(int(basket_len * scale_pct / 100.0))))

            frames: list[ImageTk.PhotoImage] = []
            for fr in frames_conf:
                try:
                    x = int(fr.get("x", 0))
                    y = int(fr.get("y", 0))
                    w = int(fr.get("w", 0))
                    h = int(fr.get("h", 0))
                    if w <= 0 or h <= 0:
                        continue
                    crop = sheet.crop((x, y, x + w, y + h))
                    # Ölçekle (oranı koru)
                    scale = target_w / max(1, crop.width)
                    rw = max(1, int(crop.width * scale))
                    rh = max(1, int(crop.height * scale))
                    crop = crop.resize((rw, rh), Image.LANCZOS)
                    frames.append(ImageTk.PhotoImage(crop))
                except Exception:
                    continue
            if frames:
                return frames
            # Kare üretilmediyse son çare olarak sheet fallback'i kullan
            return self._slice_effect_sheet(img_rel)

        # Frame listelerini hazırla (önce parametre tabanlı, sonra fallback)
        self._effect_frames_ok = _build_frames_from_params(ok_name, ok_rel) if (ok_name or ok_rel) else []
        self._effect_frames_bad = _build_frames_from_params(bad_name, bad_rel) if (bad_name or bad_rel) else []

        # Hiçbiri yoksa gizle ve çık
        if not self._effect_frames_ok and not self._effect_frames_bad:
            try:
                self.canvas.itemconfigure(self._effect_preview_id, state="hidden")
            except Exception:
                pass
            return

        # İlk oynatılacak listeyi seç
        if self._effect_frames_ok:
            self._effect_current_list = self._effect_frames_ok
            self._effect_cycle_kind = "ok"
        else:
            self._effect_current_list = self._effect_frames_bad
            self._effect_cycle_kind = "bad"
        self._effect_current_index = 0

        # Konumu sepetin üstüne al ve başlat
        self._position_effect_over_basket()
        self._schedule_next_effect_frame()

    def _stop_effect_preview(self) -> None:
        """Efekt önizleme zamanlayıcısını durdurur ve mevcut kareyi saklı tutar."""
        try:
            if self._effect_timer is not None:
                self.after_cancel(self._effect_timer)
        except Exception:
            pass
        finally:
            self._effect_timer = None

    def _position_effect_over_basket(self) -> None:
        """Efekt önizleme öğesini sepet önizlemesinin hemen üstüne hizalar.

        Sepet görünmüyorsa ekranın alt-ortasına yakın bir konum kullanır.
        """
        try:
            # Sepet bbox'ını al ve üst noktasını kullan
            bbox = self.canvas.bbox(self._basket_preview_id)
            if bbox:
                x1, y1, x2, y2 = bbox
                cx = (x1 + x2) // 2
                top_y = y1
                # Efekti sepetin biraz üstüne koy
                ex, ey = int(cx), int(top_y - 10)
            else:
                ex, ey = int(self.CANVAS_W/2 * self.zoom), int(self.CANVAS_H - 90)
        except Exception:
            ex, ey = int(self.CANVAS_W/2 * self.zoom), int(self.CANVAS_H - 90)

        try:
            self.canvas.coords(self._effect_preview_id, ex, ey)
        except Exception:
            pass

    def _slice_effect_sheet(self, rel_path: str) -> list[ImageTk.PhotoImage]:
        """Verilen görsel yolundaki 6x5 efekt sheet'ini karelere böler ve `PhotoImage` listesi döndürür.

        - Kare sayısı 30 (6 sütun x 5 satır) varsayılır.
        - Kareler, sepetin genişliğine yakın oranda ölçeklenir (uzunluğun %scale'i).
        """
        frames: list[ImageTk.PhotoImage] = []
        try:
            abs_path = self._abs_assets_path(rel_path)
            if not abs_path or not os.path.isfile(abs_path):
                return frames
            sheet = Image.open(abs_path)
            sw, sh = sheet.size
            cols, rows = 6, 5
            if sw < cols or sh < rows:
                return frames

            cw = sw // cols
            ch = sh // rows

            # Hedef boyut: sepet uzunluğunun %scale'i; yükseklik oranı korunur
            try:
                basket_len = max(1, int(self.level_basket_len_var.get() or "128"))
            except Exception:
                basket_len = 128
            try:
                scale_pct = int(self.level_effect_scale_var.get() or "60")
            except Exception:
                scale_pct = 60
            scale_pct = max(10, min(200, scale_pct))
            target_w = max(16, int(self._to_canvas(int(basket_len * scale_pct / 100.0))))

            for r in range(rows):
                for c in range(cols):
                    x1, y1 = c * cw, r * ch
                    x2, y2 = x1 + cw, y1 + ch
                    frame = sheet.crop((x1, y1, x2, y2))
                    # Ölçekle (oranı koru)
                    scale = target_w / max(1, frame.width)
                    rw = max(1, int(frame.width * scale))
                    rh = max(1, int(frame.height * scale))
                    frame = frame.resize((rw, rh), Image.LANCZOS)
                    frames.append(ImageTk.PhotoImage(frame))
        except Exception:
            return frames
        return frames

    def _schedule_next_effect_frame(self) -> None:
        """Aktif efekt listesindeki bir sonraki kareyi kanvas üzerinde gösterir ve zamanlar.

        Kareler biterse diğer efekt listesine (ok/bad) geçer; o da yoksa başa sarar.
        """
        if not self._effect_current_list:
            return
        try:
            img = self._effect_current_list[self._effect_current_index]
            self.canvas.itemconfigure(self._effect_preview_id, image=img, state="normal")
            self.canvas.tag_raise(self._effect_preview_id)
        except Exception:
            pass

        # Sonraki indeks
        self._effect_current_index += 1
        if self._effect_current_index >= len(self._effect_current_list):
            # Diğer türe geçiş dene
            if self._effect_cycle_kind == "ok" and self._effect_frames_bad:
                self._effect_current_list = self._effect_frames_bad
                self._effect_cycle_kind = "bad"
            elif self._effect_cycle_kind == "bad" and self._effect_frames_ok:
                self._effect_current_list = self._effect_frames_ok
                self._effect_cycle_kind = "ok"
            # İndeksi sıfırla
            self._effect_current_index = 0

        # FPS'e göre zamanla
        try:
            fps = int(self.level_effect_fps_var.get() or "30")
        except Exception:
            fps = 30
        fps = max(5, min(60, fps))
        delay = max(10, int(1000 / fps))
        try:
            self._effect_timer = self.after(delay, self._schedule_next_effect_frame)
        except Exception:
            self._effect_timer = None


    # ------- Tree/Z helpers -------
    def _populate_tree(self) -> None:
        """Populate the object tree with current items."""
        for iid in self.obj_tree.get_children():
            self.obj_tree.delete(iid)
        for it in self.items:
            name = it["props"].get("name") or (it["props"].get("text") or it["type"]).strip() or it["type"].title()
            label = f"{name} ({it['type']})"
            self.obj_tree.insert("", tk.END, iid=str(it["id"]), values=(label,))

    def _on_tree_select(self) -> None:
        """Select corresponding canvas item when a tree row is selected."""
        sel = self.obj_tree.selection()
        if not sel:
            return
        canvas_id = int(sel[0])
        it = self._find_item_by_canvas_id(canvas_id)
        if it:
            self._select_item(it)

    def _bring_forward(self) -> None:
        """Bring selected item to front (preserving background at bottom)."""
        if not self.selected_item:
            return
        it = self.selected_item
        try:
            self.canvas.tag_raise(it["id"])
            if it["type"] == "button":
                # ensure text above image/rect
                self.canvas.tag_raise(it["props"]["label_id"])
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass
        self._set_dirty(True)

    def _send_backward(self) -> None:
        """Send selected item one step backward (but keep above background)."""
        if not self.selected_item:
            return
        it = self.selected_item
        try:
            self.canvas.tag_lower(it["id"])
            if it["type"] == "button":
                self.canvas.tag_lower(it["props"]["label_id"])
            # ensure background is bottom-most
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass
        self._set_dirty(True)

    def _gen_name(self, kind: str) -> str:
        """Generate a default display name for an item."""
        self._name_counters[kind] = self._name_counters.get(kind, 0) + 1
        base = "Label" if kind == "label" else "Button"
        return f"{base} {self._name_counters[kind]}"

    def _rename_selected(self) -> None:
        """Seçili nesnenin görünen adını günceller ve TreeView'i senkronlar."""
        if not self.selected_item:
            return
        it = self.selected_item
        current = it["props"].get("name") or (it["props"].get("text") or it["type"]).strip()
        new_name = simpledialog.askstring("Yeniden Adlandır", "Yeni ad:", initialvalue=current, parent=self)
        if not new_name:
            return
        it["props"]["name"] = new_name.strip()
        label = f"{new_name.strip()} ({it['type']})"
        try:
            self.obj_tree.item(str(it["id"]), values=(label,))
        except Exception:
            pass

    def _delete_selected(self) -> None:
        """Seçili nesneyi kanvastan, iç listeden ve ağaçtan kaldırır."""
        if not self.selected_item:
            return
        it = self.selected_item
        # remove from canvas
        try:
            self.canvas.delete(it["id"])
            if it["type"] == "button" and it["props"].get("label_id"):
                self.canvas.delete(it["props"]["label_id"])
        except Exception:
            pass
        # remove from items list
        self.items = [x for x in self.items if x is not it]
        # remove from tree
        try:
            self.obj_tree.delete(str(it["id"]))
        except Exception:
            pass
        # clear selection and panels
        self.selected_item = None
        self.label_frame.pack_forget(); self.button_frame.pack_forget()
        try:
            self.canvas.tag_lower("__bg__")
        except Exception:
            pass

