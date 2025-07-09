# settings.py
import os

# --- Sabitler ---
SCREEN_WIDTH = 800
SCREEN_HEIGHT = 600

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
LIGHT_GRAY = (127, 127, 127)
MEDIUM_GRAY = (60, 60, 60)
DARK_GRAY = (50, 50, 50)
LIGHT_GREEN = (80,215,80)

BACKGROUND_COLOR = (173, 216, 230) # Açık Mavi

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

IMAGE_FILENAME_MAP = {
    "Akım Şiddeti": "ELEKTRİKAKIMI", "Işık Şiddeti": "IŞIKŞİDDETİ", "Kütle": "KÜTLE",
    "Madde Miktarı": "MADDE MİKTARI", "Sıcaklık": "SICAKLIK", "Uzunluk": "UZUNLUK", "Zaman": "ZAMAN",
    "Alan": "ALAN", "Ağırlık": "AĞIRLIK", "Basınç": "BASINC", "Elektrik Alan": "ELEKTRİKALAN",
    "Enerji": "ENERJİ", "Frekans": "FREKANS", "Güç": "GÜÇ", "Hacim": "HACİM", "Hız": "HIZ",
    "Isı": "ISI", "Kuvvet": "KUVVET", "Manyetik Alan": "MANYETİK ALAN", "Tork": "MOMENT",
    "Momentum": "MOMENTUM", "Sürat": "SÜRAT", "Yer Değiştirme": "YERDEĞİŞTİRME",
    "Özkütle": "YOĞUNLUK", "Yüzey Alanı": "YÜZEYALANI", "Özısı": "ÖZISI", "İvme": "İVME", "İş": "İŞ"
}

QUANTITY_TO_FOLDER_MAP = {}
for q in TEMEL_LIST:
    QUANTITY_TO_FOLDER_MAP[q] = "TEMEL BÜYÜKLÜKLER_BUTON"
for q in TURETILMIS_LIST:
    if q not in QUANTITY_TO_FOLDER_MAP:
        QUANTITY_TO_FOLDER_MAP[q] = "TÜRETİLMİŞ BÜYÜKÜLKER_BUTON"
