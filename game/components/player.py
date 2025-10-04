import pygame
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, PLAYER_SPEED
from arduino import arduino_connected, ser

class Player(pygame.sprite.Sprite):
    """Represents the player's basket, controlled by keyboard or Arduino."""
    def __init__(self, image: pygame.Surface, length: int):
        super().__init__()
        self.original_image = image
        self.length = length
        
        # Scale the image to the desired length while maintaining aspect ratio
        img_w, img_h = self.original_image.get_size()
        aspect_ratio = img_h / img_w if img_w > 0 else 1
        new_w = length
        new_h = int(new_w * aspect_ratio)
        self.image = pygame.transform.scale(self.original_image, (new_w, new_h))
        
        self.rect = self.image.get_rect()
        # Position at the bottom center of the screen
        self.rect.midbottom = (SCREEN_WIDTH // 2, SCREEN_HEIGHT - 10)
        self.speed = PLAYER_SPEED

    def update(self):
        """Update the player's position based on keyboard or Arduino input."""
        # Keyboard control (if Arduino is not connected)
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            self.rect.x -= self.speed
        if keys[pygame.K_RIGHT]:
            self.rect.x += self.speed

        # Arduino control
        if arduino_connected:
            self._handle_arduino_input()

        # Keep the player on the screen
        if self.rect.left < 0:
            self.rect.left = 0
        if self.rect.right > SCREEN_WIDTH:
            self.rect.right = SCREEN_WIDTH

    def _handle_arduino_input(self):
        try:
            line = ser.readline().decode('utf-8').strip()
            if line:
                # Map the 0-1023 value from Arduino to the screen width
                pot_value = int(line)
                self.rect.x = int((pot_value / 1023) * (SCREEN_WIDTH - self.rect.width))
        except (UnicodeDecodeError, ValueError):
            # Ignore faulty data
            pass
