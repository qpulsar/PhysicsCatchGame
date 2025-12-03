"""Screens tab to manage game screens (opening, level-specific, victory, defeat).

Bu sekme oyuna ait ekranların düzenlenmesini sağlar:
- Başlangıç ekranı
- Her seviye için ayrı tasarım ekranı
- Zafer ekranı
- Yenilgi ekranı

Düzenle butonları ilgili ekranı `ScreenDesignerWindow` ile açar.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional

from ..screen_designer import ScreenDesignerWindow


class ScreensTab:
    """"Ekranlar" sekmesi: oyunun ekranlarını düzenlemek için arayüz.

    Attributes:
        frame: Sekmenin kök çerçevesi.
    """

    def __init__(self, parent, game_service, level_service, screen_service, sprite_service, effect_service=None):
        """Sekmeyi başlatır ve layout'u kurar.

        Args:
            parent: Notebook ebeveyni
            game_service: Oyun servisi
            level_service: Seviye servisi
            screen_service: Ekran servisi
            sprite_service: Sprite servisi
            effect_service: Efekt servisi
        """
        self.parent = parent
        self.game_service = game_service
        self.level_service = level_service
        self.screen_service = screen_service
        self.sprite_service = sprite_service
        self.effect_service = effect_service

        self.frame = ttk.Frame(parent, padding=10)
        self.frame.columnconfigure(0, weight=1)

        # Başlık
        ttk.Label(self.frame, text="Ekranlar", style="Subheader.TLabel").grid(row=0, column=0, sticky="w")

        # Üst: Genel ekranlar
        general = ttk.LabelFrame(self.frame, text="Genel Ekranlar", padding=8)
        general.grid(row=1, column=0, sticky="ew", pady=(6, 8))
        ttk.Button(general, text="Başlangıç Ekranını Düzenle", command=self._edit_opening).pack(side=tk.LEFT, padx=4)
        ttk.Button(general, text="Zafer Ekranını Düzenle", command=self._edit_victory).pack(side=tk.LEFT, padx=4)
        ttk.Button(general, text="Yenilgi Ekranını Düzenle", command=self._edit_defeat).pack(side=tk.LEFT, padx=4)

        # Alt: Seviye ekranları
        self.levels_group = ttk.LabelFrame(self.frame, text="Seviye Ekranları", padding=8)
        self.levels_group.grid(row=2, column=0, sticky="nsew")
        self.frame.rowconfigure(2, weight=1)

        self._levels_container = ttk.Frame(self.levels_group)
        self._levels_container.pack(fill="both", expand=True)
        self._levels_container.columnconfigure(1, weight=1)

        self.refresh()

    # Public API
    def refresh(self) -> None:
        """Seviye listesini yeniler ve düzenleme satırlarını oluşturur."""
        for w in self._levels_container.winfo_children():
            w.destroy()
        try:
            root = self.frame.winfo_toplevel()
            game_id: Optional[int] = getattr(root, "current_game_id", None)
            if not game_id:
                ttk.Label(self._levels_container, text="Lütfen bir oyun seçin.").grid(row=0, column=0, sticky="w")
                return
            levels = self.level_service.get_levels(game_id)
            if not levels:
                ttk.Label(self._levels_container, text="Seviye bulunamadı.").grid(row=0, column=0, sticky="w")
                return
            for idx, lvl in enumerate(levels):
                row = idx
                ttk.Label(self._levels_container, text=f"Seviye #{lvl.order if hasattr(lvl, 'order') else lvl.id}").grid(row=row, column=0, sticky="w", padx=(0,8), pady=3)
                name = getattr(lvl, 'name', None) or f"Level {getattr(lvl, 'order', lvl.id)}"
                ttk.Label(self._levels_container, text=name).grid(row=row, column=1, sticky="w")
                # Ana seviye ekranı düzenleme butonu
                ttk.Button(self._levels_container, text="Düzenle", command=lambda lid=lvl.id: self._edit_level(lid)).grid(row=row, column=2, sticky="e")
                # Seviye öncesi bilgi ekranı düzenleme butonu
                ttk.Button(self._levels_container, text="Bilgi Ekranı", command=lambda lid=lvl.id: self._edit_level_info(lid)).grid(row=row, column=3, sticky="e", padx=(6,0))
        except Exception as e:
            messagebox.showerror("Ekranlar", f"Seviyeler yüklenemedi: {e}")

    # General screens
    def _edit_opening(self) -> None:
        """Başlangıç ekranı tasarımcısını açar."""
        self._open_designer(screen_name="opening", screen_type="menu")

    def _edit_victory(self) -> None:
        """Zafer ekranı tasarımcısını açar."""
        self._open_designer(screen_name="victory", screen_type="ending")

    def _edit_defeat(self) -> None:
        """Yenilgi ekranı tasarımcısını açar."""
        self._open_designer(screen_name="defeat", screen_type="ending")

    # Level screens
    def _edit_level(self, level_id: int) -> None:
        """Belirtilen seviye için tasarımcısını açar.

        Level ekranı screen_name: "level_<id>", screen_type: "level"
        """
        self._open_designer(screen_name=f"level_{level_id}", screen_type="level")

    def _edit_level_info(self, level_id: int) -> None:
        """Belirtilen seviye için BİLGİ ekranı tasarımcısını açar.

        Bilgi ekranı screen_name: "level_<id>_info", screen_type: "info"
        Bu ekran, seviyeye başlamadan önce gösterilecek açıklama/ipuçları için tasarlanır.
        """
        self._open_designer(screen_name=f"level_{level_id}_info", screen_type="info")

    # Helpers
    def _open_designer(self, screen_name: str, screen_type: str) -> None:
        """Genel amaçlı tasarımcı penceresini açar."""
        try:
            root = self.frame.winfo_toplevel()
            game_id: Optional[int] = getattr(root, "current_game_id", None)
            
            # Servisi öncelikle doğrudan al, yoksa root'tan dene (fallback)
            eff_svc = self.effect_service
            if not eff_svc:
                eff_svc = getattr(root, "effect_service", None)
                
            if not game_id:
                messagebox.showwarning("Ekranlar", "Lütfen önce bir oyun seçin.")
                return
            ScreenDesignerWindow(
                root,
                game_id,
                self.screen_service,
                self.sprite_service,
                self.game_service,
                self.level_service,
                effect_service=eff_svc,
                screen_name=screen_name,
                screen_type=screen_type,
            )
        except Exception as e:
            messagebox.showerror("Ekranlar", f"Pencere açılamadı: {e}")
