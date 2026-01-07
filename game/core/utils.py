# utils.py
import pygame
import os
import sys
from settings import BLACK
from settings import ALL_QUANTITIES, LEVEL_TARGETS
import random

def get_resource_path(relative_path):
    """Get absolute path to resource, works for dev and for PyInstaller"""
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        # Dev mode: use project root (two levels up from this file: game/core/utils.py -> game/core -> game -> root)
        # However, checking the folder structure:
        # game/core/utils.py
        # App is at root/main.py
        # We want base_path to be root.
        # os.path.dirname(__file__) is .../game/core
        # .. is .../game
        # .. is .../ (root)
        base_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

    return os.path.join(base_path, relative_path)


def draw_text(surf, text, size, x, y, color, wrap_width=None):
    # Sistem fontlarını dene (Verdana, Arial daha okunaklıdır)
    try:
        font = pygame.font.SysFont(['Verdana', 'Arial', 'sans-serif'], size)
    except:
        font = pygame.font.Font(None, size)
    
    if wrap_width:
        words = str(text).split(' ')
        lines = []
        current_line = ""
        for word in words:
            if not word: continue
            test_line = (current_line + " " + word).strip()
            if font.size(test_line)[0] < wrap_width:
                current_line = test_line
            else:
                if current_line:
                    lines.append(current_line)
                current_line = word
        if current_line:
            lines.append(current_line)

        # Render and blit each line
        line_height = font.get_linesize()
        total_height = len(lines) * line_height
        start_y = y - total_height / 2
        
        for i, line in enumerate(lines):
            text_surface = font.render(line, True, color)
            text_rect = text_surface.get_rect(center=(x, start_y + i * line_height + line_height / 2))
            surf.blit(text_surface, text_rect)
    else:
        text_surface = font.render(str(text), True, color)
        text_rect = text_surface.get_rect(center=(x, y))
        surf.blit(text_surface, text_rect)

def get_new_item(level):
    level_name = LEVEL_TARGETS[level]
    item_list = ALL_QUANTITIES[level_name]
    text = random.choice(item_list)
    item_type = level_name
    return text, item_type
