# utils.py
import pygame
from settings import BLACK
from settings import ALL_QUANTITIES, LEVEL_TARGETS
import random

def draw_text(surf, text, size, x, y, color, wrap_width=None):
    font = pygame.font.Font(None, size)
    
    if wrap_width:
        words = text.split(' ')
        lines = []
        current_line = ""
        for word in words:
            test_line = current_line + word + " "
            if font.size(test_line)[0] < wrap_width:
                current_line = test_line
            else:
                lines.append(current_line)
                current_line = word + " "
        lines.append(current_line)

        # Render and blit each line
        line_height = font.get_linesize()
        total_height = len(lines) * line_height
        start_y = y - total_height / 2
        
        for i, line in enumerate(lines):
            text_surface = font.render(line.strip(), True, color)
            text_rect = text_surface.get_rect(center=(x, start_y + i * line_height + line_height / 2))
            surf.blit(text_surface, text_rect)
    else:
        text_surface = font.render(text, True, color)
        text_rect = text_surface.get_rect(center=(x, y))
        surf.blit(text_surface, text_rect)

def get_new_item(level):
    level_name = LEVEL_TARGETS[level]
    item_list = ALL_QUANTITIES[level_name]
    text = random.choice(item_list)
    item_type = level_name
    return text, item_type
