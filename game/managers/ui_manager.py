"""UI Manager Module

This module provides the UIManager class which handles all user interface
elements and rendering for the game.
"""

import os
from typing import List, Optional, Tuple, Union

import pygame
from pygame import Surface, Rect
from pygame.font import Font

import settings
from settings import MEDIUM_GRAY


class UIManager:
    """Manages all UI elements and rendering for the game.
    
    This class handles:
    - Text rendering with different sizes and alignments
    - HUD display (score, lives, level info)
    - Game screens (splash, game over, level up)
    - UI elements like buttons and help menus
    
    Attributes:
        font: Default font for UI elements
        small_font: Smaller font for secondary text
        medium_font: Medium font for buttons and important info
        large_font: Large font for titles
        help_button_img: Image for the help button
    """
    
    def __init__(self):
        """Initialize the UIManager with default fonts and load UI assets."""
        self.font: Font = Font(None, 36)
        self.small_font: Font = Font(None, 22)
        self.medium_font: Font = Font(None, 28)
        self.large_font: Font = Font(None, 64)
        
        # UI elements
        self.help_button_img: Optional[Surface] = None
        self.help_menu_bg: Optional[Surface] = None
        # Help menu anchor position: 'top-right' | 'top-left'
        self.help_area: str = 'top-right'
        self._load_ui_elements()
    
    def _load_ui_elements(self) -> None:
        """Load UI elements like buttons and other assets.
        
        Handles loading of all UI assets and sets appropriate scaling.
        
        Note:
            - Currently only loads the help button image
            - Silently continues if assets can't be loaded
        """
        try:
            help_img_path = os.path.join('img', 'button_help.png')
            if os.path.exists(help_img_path):
                self.help_button_img = pygame.image.load(help_img_path).convert_alpha()
                self.help_button_img = pygame.transform.scale(
                    self.help_button_img, 
                    (40, 40)
                )
        except (pygame.error, FileNotFoundError) as e:
            print(f"Error loading UI elements: {e}")
            self.help_button_img = None

        try:
            bg_path = os.path.join('img', 'backgrounds', '6.jpg')
            if os.path.exists(bg_path):
                self.help_menu_bg = pygame.image.load(bg_path).convert()
        except (pygame.error, FileNotFoundError) as e:
            print(f"Error loading help menu background: {e}")
            self.help_menu_bg = None

    def set_help_button(self, image_path: str | None) -> None:
        """Set custom help button sprite from path.

        If path is invalid, silently ignore and keep previous image.
        """
        if not image_path:
            return
        try:
            if os.path.exists(image_path):
                img = pygame.image.load(image_path).convert_alpha()
                self.help_button_img = pygame.transform.scale(img, (40, 40))
        except Exception:
            pass
    
    def draw_text(
        self,
        surface: Surface,
        text: str,
        size: str,
        x: int,
        y: int,
        color: Tuple[int, int, int],
        align: str = "center"
    ) -> Rect:
        """Draw text on the surface with the specified alignment.
        
        Args:
            surface: The pygame surface to draw on.
            text: The text to render.
            size: Font size ('small', 'medium', 'large', or default).
            x: X-coordinate for text position.
            y: Y-coordinate for text position.
            color: Text color as an RGB tuple.
            align: Text alignment ('left', 'center', or 'right').
            
        Returns:
            The pygame.Rect of the rendered text.
        """
        # Select appropriate font
        font = self._get_font(size)
        
        # Render text
        text_surface = font.render(str(text), True, color)
        text_rect = text_surface.get_rect()
        
        # Position text based on alignment
        if align == "center":
            text_rect.midtop = (x, y)
        elif align == "left":
            text_rect.topleft = (x, y)
        elif align == "right":
            text_rect.topright = (x, y)
        else:
            text_rect.topleft = (x, y)  # Default to top-left if invalid alignment
            
        surface.blit(text_surface, text_rect)
        return text_rect
        
    def _get_font(self, size: str) -> Font:
        """Get the appropriate font based on size.
        
        Args:
            size: Font size identifier ('small', 'medium', 'large').
            
        Returns:
            The requested pygame.font.Font object.
        """
        return {
            'small': self.small_font,
            'medium': self.medium_font,
            'large': self.large_font
        }.get(size.lower(), self.font)
    
    def draw_hud(
        self,
        surface: Surface,
        score: int,
        lives: int,
        level: int,
        target_category: str,
        help_mode: bool = False,
        remaining_items: Optional[List[str]] = None
    ) -> None:
        """Draw the heads-up display with game information.
        
        Args:
            surface: The pygame surface to draw on.
            score: Current player score.
            lives: Remaining player lives.
            level: Current level number.
            target_category: The target category for the current level.
            help_mode: Whether to show the help menu.
            remaining_items: List of items remaining to be caught.
        """
        # Draw score (centered at top)
        self.draw_text(surface, f"Puan: {score}", 'medium', 
                      settings.SCREEN_WIDTH // 2, 10, settings.BLACK)
        
        # Draw lives (top-left)
        self.draw_text(surface, f"Can: {lives}", 'medium', 
                      60, 10, settings.BLACK, "left")
        
        # Draw level info (top-right)
        level_text = f"Seviye {level}: {target_category}"
        self.draw_text(surface, level_text, 'small', 
                      settings.SCREEN_WIDTH - 10, 10, settings.BLACK, "right")
        
        # Draw help button (top-left)
        self._draw_help_button(surface)
        
        # Draw help menu if enabled
        if help_mode and remaining_items:
            self._draw_help_menu(surface, remaining_items)
    
    def _draw_help_button(self, surface: Surface) -> Optional[Rect]:
        """Draw the help button in the top-left corner.
        
        Args:
            surface: The pygame surface to draw on.
            
        Returns:
            The Rect of the help button if drawn, None otherwise.
        """
        if not self.help_button_img:
            return None
            
        help_button_rect = self.help_button_img.get_rect(topleft=(10, 10))
        surface.blit(self.help_button_img, help_button_rect)
        return help_button_rect
    
    def _draw_help_menu(
        self, 
        surface: Surface, 
        remaining_items: List[str],
        max_width: int = 220,
        item_height: int = 25,
        padding: int = 10
    ) -> Rect:
        """Draw the help menu showing remaining items.
        
        Args:
            surface: The pygame surface to draw on.
            remaining_items: List of items to display.
            max_width: Maximum width of the help menu.
            item_height: Height of each item in the menu.
            padding: Padding around the menu.
            
        Returns:
            The Rect of the help menu.
        """
        if not remaining_items:
            return pygame.Rect(0, 0, 0, 0)
        
        # Calculate menu dimensions
        menu_width = min(max_width, settings.SCREEN_WIDTH - 40)  # Ensure it fits on screen
        menu_height = 60 + (len(remaining_items) * item_height)
        
        # Position the menu based on configured anchor
        if (self.help_area or '').lower() == 'top-left':
            menu_x = padding
            menu_y = 60  # Below the HUD
        else:
            # default top-right
            menu_x = settings.SCREEN_WIDTH - menu_width - padding
            menu_y = 60
        
        # Create menu rectangle
        menu_rect = pygame.Rect(menu_x, menu_y, menu_width, menu_height)
        
        # Create a surface for the menu with per-pixel alpha
        menu_surface = pygame.Surface(menu_rect.size, pygame.SRCALPHA)

        # Draw background with transparency
        if self.help_menu_bg:
            # Scale the background to fit the menu
            scaled_bg = pygame.transform.scale(self.help_menu_bg, menu_rect.size)
            menu_surface.blit(scaled_bg, (0, 0))
        else:
            # Fallback to a solid color if image fails to load
            menu_surface.fill((230, 230, 255, 0)) # Transparent fallback

        # Set overall transparency to 50%
        menu_surface.set_alpha(128) # 128 is 50% of 255
        
        # Draw a border on the menu surface
        pygame.draw.rect(menu_surface, (200, 200, 255, 180), menu_surface.get_rect(), 2, border_radius=10)

        # Draw title on the menu surface (coordinates are relative to the surface)
        self.draw_text(
            menu_surface, 
            "Kalanlar:", 
            'medium', 
            menu_width // 2, 
            10,
            settings.BLUE,
            "center"
        )
        
        # Draw items on the menu surface (coordinates are relative to the surface)
        for idx, item in enumerate(remaining_items):
            self.draw_text(
                menu_surface, 
                item, 
                'small',
                15, 
                40 + (idx * item_height), 
                settings.BLACK,
                "left"
            )
        
        # Blit the final menu surface to the main screen
        surface.blit(menu_surface, menu_rect.topleft)
            
        return menu_rect
    
    def draw_splash_screen(
        self, 
        surface: Surface, 
        button_rect: Rect, 
        is_button_hovered: bool
    ) -> None:
        """Draw the splash screen with start button.
        
        Args:
            surface: The pygame surface to draw on.
            button_rect: The rectangle defining the start button's position and size.
            is_button_hovered: Whether the mouse is hovering over the button.
        """
        try:
            # Try to load and draw background image
            bg_path = os.path.join('img', 'backgrounds', '1.jpg')
            if os.path.exists(bg_path):
                splash_bg = pygame.image.load(bg_path).convert()
                splash_bg = pygame.transform.scale(splash_bg, (settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT))
                surface.blit(splash_bg, (0, 0))
            else:
                # Fallback to solid color if image not found
                surface.fill(settings.LIGHT_BLUE)
        except (pygame.error, FileNotFoundError):
            surface.fill(settings.LIGHT_BLUE)
        
        # Draw title with shadow effect
        shadow_offset = 3
        self.draw_text(
            surface, 
            "Fiziksel Büyüklükleri Yakala!", 
            'large',
            settings.SCREEN_WIDTH // 2 + shadow_offset,
            settings.SCREEN_HEIGHT // 4 + shadow_offset,
            settings.DARK_GRAY,
            "center"
        )
        self.draw_text(
            surface, 
            "Fiziksel Büyüklükleri Yakala!", 
            'large',
            settings.SCREEN_WIDTH // 2,
            settings.SCREEN_HEIGHT // 4,
            settings.BLUE,
            "center"
        )
        
        # Draw subtitle
        self.draw_text(
            surface, 
            "Doğru büyüklükleri topla, yanlışlardan kaç!", 
            'medium',
            settings.SCREEN_WIDTH // 2,
            settings.SCREEN_HEIGHT // 4 + 70,
            (40, 40, 40),  # Dark gray
            "center"
        )
        
        # Draw instruction
        self.draw_text(
            surface, 
            "Başlamak için aşağıdaki butona tıkla.", 
            'medium',
            settings.SCREEN_WIDTH // 2,
            settings.SCREEN_HEIGHT // 2 - 30,
            settings.MEDIUM_GRAY,
            "center"
        )
        
        # Draw button with hover effect
        button_color = (0, 191, 255) if is_button_hovered else (30, 144, 255)
        border_color = (0, 120, 200) if is_button_hovered else (0, 0, 0)
        
        # Button shadow
        shadow_rect = button_rect.move(5, 5)
        pygame.draw.rect(surface, (0, 0, 0, 100), shadow_rect, border_radius=15)
        
        # Button background
        pygame.draw.rect(surface, button_color, button_rect, border_radius=15)
        pygame.draw.rect(surface, border_color, button_rect, 2, border_radius=15)
        
        # Button text with shadow
        text_shadow = (button_rect.centerx + 2, button_rect.centery - 8)
        self.draw_text(
            surface, 
            "Başlat", 
            'medium',
            text_shadow[0], 
            text_shadow[1], 
            (0, 0, 0, 100),  # Semi-transparent black
            "center"
        )
        self.draw_text(
            surface, 
            "Başlat", 
            'medium',
            button_rect.centerx, 
            button_rect.centery - 10,
            settings.WHITE,
            "center"
        )
    
    def draw_game_over(self, surface: Surface, score: int) -> None:
        """Draw the game over screen with final score.
        
        Args:
            surface: The pygame surface to draw on.
            score: The final score to display.
        """
        # Semi-transparent overlay
        overlay = Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 200))  # More opaque for better text readability
        surface.blit(overlay, (0, 0))
        
        # Game over text with shadow
        self._draw_text_with_shadow(
            surface,
            "OYUN BİTTİ!",
            'large',
            settings.SCREEN_WIDTH // 2,
            settings.SCREEN_HEIGHT // 4,
            settings.RED,
            shadow_color=(150, 0, 0)
        )
        
        # Score display
        self._draw_text_with_shadow(
            surface,
            f"Skorunuz: {score}",
            'medium',
            settings.SCREEN_WIDTH // 2,
            settings.SCREEN_HEIGHT // 2,
            settings.WHITE,
            shadow_color=(100, 100, 100)
        )
        
        # Instruction
        self._draw_text_with_shadow(
            surface,
            "Yeniden başlamak için bir tuşa basın.",
            'medium',
            settings.SCREEN_WIDTH // 2,
            settings.SCREEN_HEIGHT * 3 // 4,
            settings.LIGHT_GRAY,
            shadow_color=(50, 50, 50)
        )
        
    def _draw_text_with_shadow(
        self,
        surface: Surface,
        text: str,
        size: str,
        x: int,
        y: int,
        color: Tuple[int, int, int],
        shadow_color: Tuple[int, int, int] = (0, 0, 0),
        shadow_offset: int = 2,
        align: str = "center"
    ) -> None:
        """Helper method to draw text with a shadow effect.
        
        Args:
            surface: The pygame surface to draw on.
            text: The text to render.
            size: Font size ('small', 'medium', 'large', or default).
            x: X-coordinate for text position.
            y: Y-coordinate for text position.
            color: Text color as an RGB tuple.
            shadow_color: Shadow color as an RGB tuple.
            shadow_offset: Offset in pixels for the shadow.
            align: Text alignment ('left', 'center', or 'right').
        """
        # Draw shadow
        self.draw_text(surface, text, size, x + shadow_offset, y + shadow_offset, 
                      shadow_color, align)
        # Draw main text
        self.draw_text(surface, text, size, x, y, color, align)
    
    def draw_level_up(
        self, 
        surface: Surface, 
        level: int, 
        target_category: str
    ) -> None:
        """Draw the level completion screen.
        
        Args:
            surface: The pygame surface to draw on.
            level: The level that was just completed.
            target_category: The target category for the next level.
        """
        # Semi-transparent overlay with blur effect (simulated with alpha)
        overlay = Surface((settings.SCREEN_WIDTH, settings.SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))  # More opaque for better readability
        surface.blit(overlay, (0, 0))
        
        # Level up text with shadow
        self._draw_text_with_shadow(
            surface,
            "TEBRİKLER!",
            'large',
            settings.SCREEN_WIDTH // 2,
            settings.SCREEN_HEIGHT // 4,
            settings.GREEN,
            shadow_color=(0, 100, 0)
        )
        
        # Level info
        self._draw_text_with_shadow(
            surface,
            f"Seviye {level} Tamamlandı!",
            'medium',
            settings.SCREEN_WIDTH // 2,
            settings.SCREEN_HEIGHT // 2 - 20,
            settings.WHITE,
            shadow_color=(50, 50, 50)
        )
        
        # Next level info
        self._draw_text_with_shadow(
            surface,
            f"Sonraki Seviye: {target_category}",
            'medium',
            settings.SCREEN_WIDTH // 2,
            settings.SCREEN_HEIGHT // 2 + 20,
            settings.LIGHT_GREEN,
            shadow_color=(0, 80, 0)
        )
        
        # Instruction
        self._draw_text_with_shadow(
            surface,
            "Devam etmek için bir tuşa basın...",
            'small',
            settings.SCREEN_WIDTH // 2,
            settings.SCREEN_HEIGHT * 3 // 4,
            settings.LIGHT_GRAY,
            shadow_color=(50, 50, 50)
        )
