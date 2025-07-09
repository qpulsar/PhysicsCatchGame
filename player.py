# player.py
import pygame
from settings import PLAYER_WIDTH, PLAYER_HEIGHT, ORANGE, SCREEN_WIDTH, SCREEN_HEIGHT

class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = pygame.Surface([PLAYER_WIDTH, PLAYER_HEIGHT])
        self.image.fill(ORANGE)
        self.rect = self.image.get_rect()
        self.rect.x = (SCREEN_WIDTH - PLAYER_WIDTH) // 2
        self.rect.y = SCREEN_HEIGHT - PLAYER_HEIGHT - 10

    def update(self, move_left=False, move_right=False):
        if move_left:
            self.rect.x -= 10
        if move_right:
            self.rect.x += 10
        self.rect.x = max(0, min(self.rect.x, SCREEN_WIDTH - PLAYER_WIDTH))
