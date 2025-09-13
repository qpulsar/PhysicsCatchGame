# settings.py
import os

# --- Sabitler ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

CARD_WIDTH = 220
CARD_HEIGHT = 56
CARD_GAP = 10
CARD_COLOR = (255, 255, 255)
CAROUSEL_BG_COLOR = (30, 30, 40)

CARD_SELECTED_COLOR = (255, 215, 0)
TEXT_COLOR = (255, 255, 255) 


# Renkler
WHITE = (255, 255, 255)
BLACK = (0, 0, 0)
RED = (255, 69, 0)
GREEN = (50, 205, 50)
BLUE = (65, 105, 225)
LIGHT_BLUE = (35, 75, 195)
YELLOW = (255, 215, 0)
ORANGE = (255, 140, 0)
PURPLE = (153, 50, 204)
PURPLE_LIGHT = (204, 102, 255)
LIGHT_GRAY = (127, 127, 127)
MEDIUM_GRAY = (60, 60, 60)
DARK_GRAY = (50, 50, 50)
LIGHT_GREEN = (80,215,80)
TEAL = (0, 128, 128)

BACKGROUND_COLOR = (173, 216, 230) # Açık Mavi

# Kartlar için canlı renk paleti (sıra ile döner)
CARD_PALETTE = [
    RED,
    ORANGE,
    YELLOW,
    LIGHT_GREEN,
    BLUE,
    PURPLE,
    TEAL
]

# Oyun Ayarları
PLAYER_WIDTH = 100
PLAYER_HEIGHT = 20
PLAYER_SPEED = 10

# Buton boyutlarını orijinal oranlarda tut (220x56 piksel ~ 3.93:1 oran)
ITEM_WIDTH = 120
ITEM_HEIGHT = int(ITEM_WIDTH * (56/220))  # Orijinal oranı koru (~23)

# Oyun içinde kullanılan boyut (geriye dönük uyumluluk için)
ITEM_SIZE = ITEM_WIDTH
ITEM_SPEED = 3

# --- Fiziksel Büyüklükler ---
LEVEL_TARGETS = {
    1: "Temel Büyüklükler",
    2: "Türetilmiş Büyüklükler",
    3: "Skaler Büyüklükler",
    4: "Vektörel Büyüklükler"
}

TEMEL_LIST = ["Kütle", "Işık Şiddeti", "Sıcaklık", "Akım Şiddeti", "Madde Miktarı", "Uzunluk", "Zaman"]
TURETILMIS_LIST = ["Hız", "İvme", "Kuvvet", "Enerji", "Güç", "Basınç", "Frekans", "Alan", "Ağırlık", "Elektrik Alan", "Hacim", "Isı", "Manyetik Alan", "Tork", "Momentum", "Sürat", "Yer Değiştirme", "Özkütle", "Yüzey Alanı", "Özısı", "İş"]
SKALER_LIST = list(set(["Sürat", "Alınan Yol", "Kütle", "Hacim", "Özkütle", "Sıcaklık", "Enerji"] + TEMEL_LIST + ["Alan", "Basınç", "Güç", "Isı", "Yüzey Alanı", "Özısı", "İş"]))
VEKTOREL_LIST = list(set(["Hız", "Yer Değiştirme", "Kuvvet", "Ağırlık", "İvme", "Konum", "Tork", "Elektrik Alan", "Manyetik Alan", "Momentum"]))

ALL_QUANTITIES = {
    "Temel Büyüklükler": TEMEL_LIST,
    "Türetilmiş Büyüklükler": TURETILMIS_LIST,
    "Skaler Büyüklükler": SKALER_LIST,
    "Vektörel Büyüklükler": VEKTOREL_LIST
}
