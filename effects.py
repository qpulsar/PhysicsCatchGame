# effects.py
import pygame
import random
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE

class ConfettiParticle:
    def __init__(self):
        self.x = random.randint(0, SCREEN_WIDTH)
        self.y = random.randint(0, SCREEN_HEIGHT//2)
        self.radius = random.randint(3, 7)
        self.color = random.choice([RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE])
        self.speed = random.uniform(2, 6)
        self.angle = random.uniform(-1, 1)
        self.life = random.randint(15, 30)
    def update(self):
        self.x += self.angle
        self.y += self.speed
        self.life -= 1
    def draw(self, surf):
        pygame.draw.circle(surf, self.color, (int(self.x), int(self.y)), self.radius)

class SadEffect:
    def __init__(self):
        self.x = SCREEN_WIDTH//2
        self.y = SCREEN_HEIGHT//2
        self.radius = 60
        self.life = 30
        self.shake = 0
    def update(self):
        self.life -= 1
        self.shake = random.randint(-5, 5)
    def draw(self, surf):
        pygame.draw.circle(surf, (180, 180, 180), (self.x + self.shake, self.y), self.radius)
        pygame.draw.arc(surf, (100, 100, 100), (self.x-30+self.shake, self.y+20, 60, 30), 3.14, 0, 3)
