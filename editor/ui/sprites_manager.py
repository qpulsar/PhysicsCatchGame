"""Sprite yöneticisi penceresi (oyundan bağımsız).

Bu pencere, mevcut `SpritesTab` arayüzünü daha geniş ve bağımsız bir Toplevel içinde
sunar. Sprite bölgeleri için veritabanında global havuz (game_id=0) kullanılır.

Kullanım:
    SpritesManagerWindow(parent, sprite_service, expression_service, level_service, game_service)

Notlar:
- `SpritesTab` zaten assets dizinlerini tarayabiliyor. Bu pencerede `current_game_id` 0
  olarak ayarlanarak, bölgeler DB'de global olarak saklanır ve her oyunda kullanılabilir.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .tabs.sprites_tab import SpritesTab


class SpritesManagerWindow(tk.Toplevel):
    """Sprite yönetimi için bağımsız Toplevel pencere (global havuz).

    Attributes:
        tab: Genişletilmiş `SpritesTab` örneği
    """

    def __init__(self, parent: tk.Tk, sprite_service, expression_service, level_service, game_service):
        """Pencereyi oluşturur ve SpritesTab'i gömer.

        Args:
            parent: Üst Tk penceresi
            sprite_service: Sprite servis örneği
            expression_service: İfade servis örneği
            level_service: Seviye servis örneği
            game_service: Oyun servis örneği
        """
        super().__init__(parent)
        self.title("Sprite Yöneticisi")
        self.geometry("1100x750")
        self.transient(parent)
        # Global havuz için game_id=0 kullanılsın diye kök attribute'u set edelim
        setattr(self, "current_game_id", 0)

        # Üst başlık/toolbar
        header = ttk.Frame(self, padding=(10, 8))
        header.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(header, text="Genel Sprite Havuzu", style="Header.TLabel").pack(side=tk.LEFT)

        # İçerik alanı
        content = ttk.Frame(self)
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # SpritesTab'i oluştur ve yerleştir
        self.tab = SpritesTab(content, sprite_service, expression_service, level_service, game_service)
        # SpritesTab'in parent'ı üzerinden current_game_id erişir; Toplevel'de 0 olarak
        # görülecek. İlk refresh çağrısında assets taraması ve region listesi gelecektir.
        self.tab.frame.pack(fill=tk.BOTH, expand=True)

        try:
            self.tab.refresh()
        except Exception:
            pass
