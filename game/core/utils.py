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

def draw_spline(surface, start, end, progress, color, width=3):
    """Draws a quadratic bezier curve from start to end based on progress."""
    if progress <= 0:
        return start
        
    # Control point: creates a nice 'organic' curve
    # Using a mix of start and end to make it more natural
    control = (start[0], end[1]) 
    
    points = []
    steps = 24
    max_t = max(0.0, min(1.0, progress))
    
    for i in range(steps + 1):
        t = (i / steps) * max_t
        # Bezier formula: (1-t)^2 * P0 + 2(1-t)t * P1 + t^2 * P2
        inv_t = 1.0 - t
        x = inv_t**2 * start[0] + 2*inv_t*t * control[0] + t**2 * end[0]
        y = inv_t**2 * start[1] + 2*inv_t*t * control[1] + t**2 * end[1]
        points.append((x, y))
    
    if len(points) > 1:
        # Create a temporary surface for alpha if needed, but pygame.draw.lines is fine for now
        # If color has alpha, we might need a different approach
        if len(color) > 3:
            # Draw with alpha
            alpha_surf = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
            pygame.draw.lines(alpha_surf, color, False, points, width)
            surface.blit(alpha_surf, (0, 0))
        else:
            pygame.draw.lines(surface, color, False, points, width)
    
    return points[-1] if points else start
