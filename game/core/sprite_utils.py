from PIL import Image
import pygame
import os

SPRITE_SHEET_PATH = os.path.join('img', 'buttons.png')

def load_buttons_from_sheet():
    """Sprite sheet'ten 10 adet buton döndürür (2 sütun x 5 satır).

    Dosya bulunamazsa boş liste döndürür; böylece çağıran kod fallback'e geçebilir.
    """
    if not os.path.exists(SPRITE_SHEET_PATH):
        return []
    try:
        sheet = Image.open(SPRITE_SHEET_PATH).convert('RGBA')
    except Exception:
        return []
    # Koordinatlar: (left, upper, right, lower)
    coords = [
        (0, 0, 220, 56),       # sol üst
        (0, 80, 220, 136),     # sol 2. satır
        (0, 160, 220, 216),    # sol 3. satır
        (0, 240, 220, 296),    # sol 4. satır
        (0, 320, 220, 376),    # sol 5. satır
        (235, 0, 451, 56),     # sağ üst
        (235, 80, 451, 136),   # sağ 2. satır
        (235, 160, 451, 216),  # sağ 3. satır
        (235, 240, 451, 296),  # sağ 4. satır
        (235, 320, 451, 376)   # sağ 5. satır
    ]
    buttons = []
    for left, upper, right, lower in coords:
        button_img = sheet.crop((left, upper, right, lower))
        mode = button_img.mode
        size = button_img.size
        data = button_img.tobytes()
        surf = pygame.image.fromstring(data, size, mode)
        buttons.append(surf)
    return buttons
