import pygame
import random
import os
import sys
import traceback
from settings import ITEM_SIZE, ITEM_WIDTH, ITEM_HEIGHT, SCREEN_WIDTH, BLACK, RED, GREEN, BLUE, YELLOW, PURPLE, WHITE

# Try to import sprite_utils with error handling
try:
    from ..core.sprite_utils import load_buttons_from_sheet
    SPRITE_UTILS_AVAILABLE = True
except ImportError as e:
    print(f"Warning: Could not import sprite_utils: {e}")
    SPRITE_UTILS_AVAILABLE = False
    traceback.print_exc()

def get_font(size=20):
    """Helper function to get a font with fallback"""
    try:
        font_path = pygame.font.match_font('timesnewroman') or pygame.font.match_font('times new roman')
        return pygame.font.Font(font_path, size) if font_path else pygame.font.Font(None, size)
    except:
        return pygame.font.Font(None, size)

class Item(pygame.sprite.Sprite):
    _button_sprites = None
    
    def __init__(self, text, item_type, base_surface: pygame.Surface | None = None):
        super().__init__()
        self.text = str(text)
        self.item_type = str(item_type)
        self._create_image(base_surface)
        
        # Set initial position (random x, just above the screen)
        self.rect = self.image.get_rect()
        self.rect.x = random.randrange(SCREEN_WIDTH - self.rect.width)
        self.rect.y = random.randrange(-100, -40)
        
        # Movement properties
        self.speed_y = 3
    
    def _create_image(self, base_surface: pygame.Surface | None = None):
        """Create the item's image with sprite or fallback to simple shape"""
        # 1) Dışarıdan verilen base_surface öncelikli
        if base_surface is not None:
            try:
                print("[SpriteDBG] item: using provided base_surface")
                self.image = pygame.transform.smoothscale(base_surface, (ITEM_WIDTH, ITEM_HEIGHT)).convert_alpha()
                self._add_text_to_image()
                return
            except Exception:
                pass
        # 2) Ortak sprite sheet (opsiyonel)
        if SPRITE_UTILS_AVAILABLE and self._try_load_sprite():
            return
            
        # Fallback to simple colored shape
        self._create_fallback_image()
    
    def _try_load_sprite(self):
        """Try to load and use a sprite for the item"""
        try:
            # Load sprites if not already loaded
            if Item._button_sprites is None:
                Item._button_sprites = load_buttons_from_sheet()
                if not Item._button_sprites:
                    print("Warning: No sprites loaded from sprite sheet")
                    return False
            
            # Liste boş ise seçim yapma
            if not Item._button_sprites:
                return False

            # Choose a random button sprite
            base_button = random.choice(Item._button_sprites)
            print("[SpriteDBG] item: using sheet button sprite")
            
            # Scale the sprite to match item dimensions while maintaining aspect ratio
            self.image = pygame.transform.smoothscale(base_button, (ITEM_WIDTH, ITEM_HEIGHT)).convert_alpha()
            
            # Add text to the button
            self._add_text_to_image()
            return True
            
        except Exception as e:
            print(f"Error loading sprite: {e}")
            traceback.print_exc()
            return False
    
    def _add_text_to_image(self):
        """Metni item görseline ekler; genişlik taşarsa fontu dinamik küçültür."""
        try:
            # Arkaplan parlaklığına göre metin rengi
            avg_color = pygame.transform.average_color(self.image)
            brightness = (avg_color[0]*0.299 + avg_color[1]*0.587 + avg_color[2]*0.114)
            text_color = BLACK if brightness > 186 else WHITE

            # Metni görsel içine sığdırmak için font boyutunu ayarla
            max_w = int(self.image.get_width() * 0.9)  # %90 genişlik içinde kalsın
            max_h = int(self.image.get_height() * 0.8) # yükseklikte de pay bırak
            size = 22
            text_surface = None
            while size >= 10:
                font = get_font(size)
                surf = font.render(self.text, True, text_color)
                if surf.get_width() <= max_w and surf.get_height() <= max_h:
                    text_surface = surf
                    break
                size -= 2
            if text_surface is None:
                # Son çare: en küçük boy
                font = get_font(10)
                text_surface = font.render(self.text, True, text_color)

            # Ortala ve çiz
            text_rect = text_surface.get_rect(center=(self.image.get_width() // 2, self.image.get_height() // 2))
            self.image.blit(text_surface, text_rect)

        except Exception as e:
            print(f"Error adding text to item: {e}")
    
    def _create_fallback_image(self):
        """Create a simple fallback image when sprites are not available"""
        try:
            self.image = pygame.Surface([ITEM_WIDTH, ITEM_HEIGHT], pygame.SRCALPHA)
            color = random.choice([RED, GREEN, BLUE, YELLOW, PURPLE])
            
            # Draw a simple shape
            shape_type = random.choice(['rect', 'circle'])
            if shape_type == 'rect':
                pygame.draw.rect(self.image, color, [0, 0, ITEM_WIDTH, ITEM_HEIGHT])
            else:  # circle
                pygame.draw.circle(
                    self.image, 
                    color, 
                    (ITEM_WIDTH // 2, ITEM_HEIGHT // 2), 
                    min(ITEM_WIDTH, ITEM_HEIGHT) // 2
                )
            
            # Add text
            font = get_font(16)
            text_surface = font.render(self.text, True, WHITE)
            text_rect = text_surface.get_rect(center=(ITEM_WIDTH // 2, ITEM_HEIGHT // 2))
            self.image.blit(text_surface, text_rect)
            
        except Exception as e:
            print(f"Error creating fallback image: {e}")
            # Create a simple red square as last resort
            self.image = pygame.Surface([ITEM_WIDTH, ITEM_HEIGHT])
            self.image.fill(RED)
    
    def update(self):
        """Update the item's position"""
        if not hasattr(self, 'rect'):
            print("Item has no rect!")
            return
            
        self.rect.y += self.speed_y
        
        # Debug output for item position
        if hasattr(self, 'debug_counter'):
            self.debug_counter += 1
            if self.debug_counter >= 60:  # Print every second (assuming 60 FPS)
                print(f"Item '{self.text}' at position: {self.rect.topleft}")
                self.debug_counter = 0
        else:
            self.debug_counter = 0
