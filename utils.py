# utils.py
import pygame
from settings import BLACK
from settings import ALL_QUANTITIES, LEVEL_TARGETS
import random

def draw_text(surf, text, size, x, y, color):
    font = pygame.font.Font(None, size)
    text_surface = font.render(text, True, color)
    text_rect = text_surface.get_rect(center=(x, y))
    surf.blit(text_surface, text_rect)

def get_new_item(level):
    level_name = LEVEL_TARGETS[level]
    item_list = ALL_QUANTITIES[level_name]
    text = random.choice(item_list)
    item_type = level_name
    return text, item_type
