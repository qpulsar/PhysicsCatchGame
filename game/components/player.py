import pygame
from settings import SCREEN_WIDTH, PLAYER_WIDTH, PLAYER_HEIGHT, PLAYER_SPEED, ORANGE
from arduino import arduino_connected, ser

class Player(pygame.sprite.Sprite):
    def __init__(self):
        super().__init__()
        self.image = pygame.Surface([PLAYER_WIDTH, PLAYER_HEIGHT])
        self.image.fill(ORANGE)
        self.rect = self.image.get_rect()
        self.rect.x = (SCREEN_WIDTH - PLAYER_WIDTH) // 2
        self.rect.y = SCREEN_HEIGHT - PLAYER_HEIGHT - 10
        self.speed = PLAYER_SPEED

    def update(self):
        # Klavye kontrolü (Arduino olmadığında)
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            self.rect.x -= self.speed
        if keys[pygame.K_RIGHT]:
            self.rect.x += self.speed

        # Arduino kontrolü
        if arduino_connected:
            self._handle_arduino_input()

        # Sepetin ekran sınırları içinde kalmasını sağla
        self.rect.x = max(0, min(self.rect.x, SCREEN_WIDTH - PLAYER_WIDTH))
    
    def _handle_arduino_input(self):
        try:
            line = ser.readline().decode('utf-8').strip()
            if line:
                # Arduino'dan gelen 0-1023 arası değeri ekran genişliğine oranla
                pot_value = int(line)
                self.rect.x = int((pot_value / 1023) * (SCREEN_WIDTH - PLAYER_WIDTH))
        except (UnicodeDecodeError, ValueError):
            # Hatalı veri gelirse görmezden gel
            pass
