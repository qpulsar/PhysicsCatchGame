"""Medya yöneticisi penceresi (oyundan bağımsız).

Bu pencere, mevcut `MediaTab` arayüzünü daha geniş ve bağımsız bir Toplevel içinde
sunar. Böylece medya havuzu tek bir yerden yönetilir ve herhangi bir oyundan
bağımsız olarak kullanılabilir.

Kullanım:
    MediaManagerWindow(parent, game_service)

Notlar:
- Var olan `MediaTab` sınıfı yeniden kullanılır; sadece daha geniş bir
  pencerede yerleştirilir.
- Oyuna özel açıklama alanı için aktif oyun ID'si, ana pencereden otomatik
  olarak okunmaya devam eder; oyun seçili değilse 0 kabul edilir.
"""
from __future__ import annotations

import tkinter as tk
from tkinter import ttk

from .tabs.media_tab import MediaTab


class MediaManagerWindow(tk.Toplevel):
    """Medya yönetimi için bağımsız Toplevel pencere.

    Attributes:
        tab: Genişletilmiş `MediaTab` örneği
    """

    def __init__(self, parent: tk.Tk, game_service):
        """Pencereyi oluşturur ve MediaTab'i gömer.

        Args:
            parent: Üst Tk penceresi
            game_service: Oyun servis örneği (MediaTab'in ihtiyaçları için)
        """
        super().__init__(parent)
        self.title("Medya Yöneticisi")
        self.geometry("1000x700")
        self.transient(parent)
        # Modal yapmıyoruz; kullanıcı aynı anda başka işleri de yapabilsin

        # Üst başlık/toolbar
        header = ttk.Frame(self, padding=(10, 8))
        header.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(header, text="Genel Medya Havuzu", style="Header.TLabel").pack(side=tk.LEFT)

        # İçerik alanı
        content = ttk.Frame(self)
        content.pack(side=tk.TOP, fill=tk.BOTH, expand=True)

        # MediaTab'i oluştur ve yerleştir
        self.tab = MediaTab(content, game_service)
        self.tab.frame.pack(fill=tk.BOTH, expand=True)

        # İlk yükleme
        try:
            self.tab.refresh()
        except Exception:
            pass
