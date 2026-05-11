"""UI Manager Module

This module provides the UIManager class which handles all user interface
elements and rendering for the game.
"""

import os
import math
import time
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
        self._font_cache: dict[str, pygame.font.Font] = {}
        self._fonts_root = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'assets', 'fonts')
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
        align: str = "center",
        font_name: Optional[str] = None
    ) -> Rect:
        """Draw text on the surface with the specified alignment and optional custom font.
        
        Args:
            surface: The pygame surface to draw on.
            text: The text to render.
            size: Font size ('small', 'medium', 'large') or numeric size.
            x: X-coordinate for text position.
            y: Y-coordinate for text position.
            color: Text color as an RGB tuple.
            align: Text alignment ('left', 'center', or 'right').
            font_name: Optional filename of the TTF font in assets/fonts.
            
        Returns:
            The pygame.Rect of the rendered text.
        """
        # Select appropriate font
        if font_name and font_name != "Arial":
            # Determine numeric size
            num_size = 24
            if isinstance(size, int):
                num_size = size
            elif size == 'small': num_size = 22
            elif size == 'medium': num_size = 28
            elif size == 'large': num_size = 64
            elif isinstance(size, str) and size.isdigit():
                num_size = int(size)
                
            font = self._get_custom_font(font_name, num_size)
        else:
            font = self._get_font(str(size))
        
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

    def _get_custom_font(self, font_name: str, size: int) -> Font:
        """Loads and caches a custom TTF font from assets/fonts."""
        cache_key = f"{font_name}_{size}"
        if cache_key in self._font_cache:
            return self._font_cache[cache_key]
        
        font_path = os.path.join(self._fonts_root, font_name)
        if not os.path.exists(font_path):
            # Fallback to default
            return pygame.font.Font(None, size)
            
        try:
            font = pygame.font.Font(font_path, size)
            self._font_cache[cache_key] = font
            return font
        except Exception as e:
            print(f"Error loading custom font {font_name}: {e}")
            return pygame.font.Font(None, size)
    
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
        """Draw the heads-up display with game information."""
        # 1. Background Panel (Modern, glassmorphism style)
        hud_bg = pygame.Surface((settings.SCREEN_WIDTH, 60), pygame.SRCALPHA)
        pygame.draw.rect(hud_bg, (20, 20, 30, 160), (0, 0, settings.SCREEN_WIDTH, 60))
        pygame.draw.line(hud_bg, (100, 100, 255, 100), (0, 59), (settings.SCREEN_WIDTH, 59), 2)
        surface.blit(hud_bg, (0, 0))

        # 2. Draw Score (Center)
        score_text = f"SKOR: {score}"
        self._draw_text_with_shadow(surface, score_text, 'medium', 
                      settings.SCREEN_WIDTH // 2, 15, (255, 215, 0))
        
        # 3. Draw Lives (Left side, with simple heart icon if possible)
        lives_color = (255, 80, 80) if lives <= 1 else (255, 255, 255)
        self._draw_text_with_shadow(surface, f"CAN: {lives}", 'medium', 
                      120, 15, lives_color, align="left")
        
        # 4. Draw Level & Category (Right side)
        level_text = f"SEVİYE {level}"
        cat_text = f"HEDEF: {target_category}"
        self._draw_text_with_shadow(surface, level_text, 'small', 
                      settings.SCREEN_WIDTH - 20, 10, (200, 200, 255), align="right")
        self._draw_text_with_shadow(surface, cat_text, 'small', 
                      settings.SCREEN_WIDTH - 20, 32, (255, 255, 255), align="right")
        
        # 5. Draw help button (top-left)
        self._draw_help_button(surface)
        
        # 6. Draw help menu if enabled
        if help_mode and remaining_items:
            self._draw_help_menu(surface, remaining_items)
    
    def _draw_help_button(self, surface: Surface) -> Optional[Rect]:
        """Draw the help button in the top-left corner."""
        if not self.help_button_img:
            # Fallback to a simple [?] button
            btn_rect = pygame.Rect(10, 10, 40, 40)
            pygame.draw.rect(surface, (60, 60, 100), btn_rect, border_radius=8)
            pygame.draw.rect(surface, (150, 150, 255), btn_rect, width=2, border_radius=8)
            self.draw_text(surface, "?", "medium", 30, 15, (255, 255, 255), "center")
            return btn_rect
            
        help_button_rect = self.help_button_img.get_rect(topleft=(10, 10))
        # Add glow if hovered (simulated)
        surface.blit(self.help_button_img, help_button_rect)
        return help_button_rect
    
    def _draw_help_menu(
        self, 
        surface: Surface, 
        remaining_items: List[str],
        max_width: int = 240,
        item_height: int = 28,
        padding: int = 15
    ) -> Rect:
        """Draw the help menu showing remaining items."""
        if not remaining_items:
            return pygame.Rect(0, 0, 0, 0)
        
        menu_width = max_width
        menu_height = 50 + (len(remaining_items) * item_height)
        
        # Position: Left side, below HUD
        menu_x = padding
        menu_y = 70
        
        menu_rect = pygame.Rect(menu_x, menu_y, menu_width, menu_height)
        
        # Glassmorphism effect for menu
        menu_surface = pygame.Surface(menu_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(menu_surface, (20, 20, 40, 200), menu_surface.get_rect(), border_radius=12)
        pygame.draw.rect(menu_surface, (100, 100, 255, 150), menu_surface.get_rect(), 2, border_radius=12)

        # Title
        self.draw_text(
            menu_surface, 
            "TOPLANACAKLAR", 
            'small', 
            menu_width // 2, 
            12,
            (255, 215, 0),
            "center"
        )
        pygame.draw.line(menu_surface, (100, 100, 255, 100), (20, 38), (menu_width - 20, 38), 1)
        
        # Items
        for idx, item in enumerate(remaining_items):
            # Bullets
            pygame.draw.circle(menu_surface, (0, 255, 100), (25, 58 + idx * item_height), 4)
            self.draw_text(
                menu_surface, 
                item, 
                'small',
                40, 
                48 + (idx * item_height), 
                (255, 255, 255),
                "left"
            )
        
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
        """Draw the game over screen."""
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((40, 10, 10, 200))
        surface.blit(overlay, (0, 0))
        
        panel_w, panel_h = 500, 300
        panel_rect = pygame.Rect((settings.SCREEN_WIDTH - panel_w)//2, (settings.SCREEN_HEIGHT - panel_h)//2, panel_w, panel_h)
        
        pygame.draw.rect(surface, (40, 20, 20), panel_rect, border_radius=20)
        pygame.draw.rect(surface, (255, 80, 80), panel_rect, width=3, border_radius=20)
        
        self._draw_text_with_shadow(surface, "OYUN BİTTİ", 'large', settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2 - 60, (255, 80, 80))
        self._draw_text_with_shadow(surface, f"Toplam Skor: {score}", 'medium', settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2, (255, 255, 255))
        self._draw_text_with_shadow(surface, "Yeniden başlamak için R, çıkmak için ESC", 'small', settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2 + 80, (200, 200, 200))
        
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
    
    def draw_level_up(self, surface: Surface, level: int, target_category: str) -> None:
        """Draw the level up screen with a premium glassmorphism effect."""
        # Darkening overlay
        overlay = pygame.Surface(surface.get_size(), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 180))
        surface.blit(overlay, (0, 0))
        
        # Panel
        panel_w, panel_h = 560, 360
        panel_rect = pygame.Rect((settings.SCREEN_WIDTH - panel_w)//2, (settings.SCREEN_HEIGHT - panel_h)//2, panel_w, panel_h)
        
        # Animated Glow (using time for pulse)
        pulse = (math.sin(time.time() * 5) + 1) / 2
        glow_size = int(10 + pulse * 10)
        for i in range(glow_size):
            alpha = int((glow_size - i) * (2 + pulse * 2))
            pygame.draw.rect(surface, (0, 255, 150, alpha), panel_rect.inflate(i*2, i*2), border_radius=30, width=2)
            
        # Glass Panel
        glass = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
        pygame.draw.rect(glass, (255, 255, 255, 15), glass.get_rect(), border_radius=30)
        pygame.draw.rect(glass, (255, 255, 255, 40), glass.get_rect(), width=2, border_radius=30)
        surface.blit(glass, panel_rect.topleft)
        
        # Text Content
        cx, cy = settings.SCREEN_WIDTH // 2, settings.SCREEN_HEIGHT // 2
        self._draw_text_with_shadow(surface, "TEBRİKLER!", 'large', cx, cy - 100, (0, 255, 150))
        self._draw_text_with_shadow(surface, f"Seviye {level-1} Tamamlandı", 'medium', cx, cy - 20, (255, 255, 255))
        
        # New Target Info Box
        info_rect = pygame.Rect(cx - 200, cy + 30, 400, 60)
        pygame.draw.rect(surface, (0, 0, 0, 100), info_rect, border_radius=15)
        self._draw_text_with_shadow(surface, f"Yeni Hedef: {target_category}", 'small', cx, info_rect.centery, (200, 255, 200))
        
        # Continue Prompt
        prompt_alpha = int(150 + pulse * 105)
        self._draw_text_with_shadow(surface, "Devam etmek için TIKLAYIN", 'small', cx, cy + 130, (255, 255, 255, prompt_alpha))
