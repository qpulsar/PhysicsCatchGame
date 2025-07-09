"""Effect Manager Module

This module provides classes for managing visual effects in the game,
including confetti and sad effects.
"""

import random
from typing import List, Optional, Tuple

import pygame

from settings import *

class ConfettiParticle:
    """A single particle in a confetti effect.
    
    Attributes:
        x (float): The x-coordinate of the particle.
        y (float): The y-coordinate of the particle.
        radius (int): The size of the particle.
        color (tuple): The color of the particle (RGB).
        speed_x (float): Horizontal speed of the particle.
        speed_y (float): Vertical speed of the particle.
        life (float): The remaining life of the particle.
    """
    
    def __init__(self, x: float, y: float):
        """Initialize a new confetti particle.
        
        Args:
            x: The x-coordinate of the effect origin.
            y: The y-coordinate of the effect origin.
        """
        self.x = x + random.uniform(-50, 50)
        self.y = y + random.uniform(-50, 50)
        self.radius = random.randint(3, 7)
        self.color = random.choice([RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE])
        self.speed_x = random.uniform(-3, 3)
        self.speed_y = random.uniform(1, 6)
        self.life = random.randint(15, 30)
    
    def update(self) -> None:
        """Update the particle's position and life."""
        self.x += self.speed_x
        self.y += self.speed_y
        self.life -= 0.1
    
    def draw(self, surface: pygame.Surface) -> None:
        """Draw the particle on the given surface.
        
        Args:
            surface: The pygame surface to draw on.
        """
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), int(self.radius))

class SadEffect:
    """A visual effect that shows a shaking red circle.
    
    Attributes:
        x (float): The x-coordinate of the effect center.
        y (float): The y-coordinate of the effect center.
        radius (int): The radius of the effect.
        life (int): The remaining life of the effect.
        shake (int): The current shake intensity.
    """
    
    def __init__(self, x: float, y: float):
        """Initialize a new sad effect.
        
        Args:
            x: The x-coordinate of the effect center.
            y: The y-coordinate of the effect center.
        """
        self.x = x
        self.y = y
        self.radius = 60
        self.life = 30
        self.shake = 0
    
    def update(self) -> None:
        """Update the effect's state."""
        self.shake = (self.shake + 1) % 4
        self.life -= 1
    
    def draw(self, surface: pygame.Surface) -> None:
        """Draw the effect on the given surface.
        
        Args:
            surface: The pygame surface to draw on.
        """
        if self.life > 0:
            offset_x = random.randint(-self.shake, self.shake)
            offset_y = random.randint(-self.shake, self.shake)
            pygame.draw.circle(
                surface, 
                (255, 0, 0, 100),  # Semi-transparent red
                (int(self.x) + offset_x, int(self.y) + offset_y), 
                self.radius, 
                3  # Line width
            )

class EffectManager:
    """Manages all visual effects in the game.
    
    This class handles the creation, updating, and rendering of all
    visual effects, including confetti and sad effects.
    """
    
    def __init__(self):
        """Initialize the EffectManager with empty effect lists."""
        self.confetti_particles: List[ConfettiParticle] = []
        self.sad_effect: Optional[SadEffect] = None
        self.confetti_timer: int = 0
        self.sad_timer: int = 0
    
    def trigger_confetti(self, x: float, y: float, count: int = 40) -> None:
        """Trigger a confetti effect at the specified position.
        
        Args:
            x: The x-coordinate where the effect should appear.
            y: The y-coordinate where the effect should appear.
            count: The number of confetti particles to create.
        """
        self.confetti_particles = [ConfettiParticle(x, y) for _ in range(count)]
        self.confetti_timer = 25
    
    def trigger_sad_effect(self, x: float, y: float) -> None:
        """Trigger a sad effect at the specified position.
        
        Args:
            x: The x-coordinate where the effect should appear.
            y: The y-coordinate where the effect should appear.
        """
        self.sad_effect = SadEffect(x, y)
        self.sad_timer = 30
    
    def update(self) -> None:
        """Update all active effects."""
        self._update_confetti()
        self._update_sad_effect()
    
    def _update_confetti(self) -> None:
        """Update the confetti effect."""
        if self.confetti_timer > 0:
            self.confetti_timer -= 1
            # Update existing particles
            for particle in self.confetti_particles[:]:
                particle.update()
                if particle.life <= 0:
                    self.confetti_particles.remove(particle)
    
    def _update_sad_effect(self) -> None:
        """Update the sad effect."""
        if self.sad_effect:
            self.sad_effect.update()
            self.sad_timer -= 1
            if self.sad_timer <= 0 or self.sad_effect.life <= 0:
                self.sad_effect = None
    
    def draw(self, surface: pygame.Surface) -> None:
        """Draw all active effects on the given surface.
        
        Args:
            surface: The pygame surface to draw on.
        """
        self._draw_confetti(surface)
        self._draw_sad_effect(surface)
    
    def _draw_confetti(self, surface: pygame.Surface) -> None:
        """Draw all confetti particles."""
        for particle in self.confetti_particles:
            particle.draw(surface)
    
    def _draw_sad_effect(self, surface: pygame.Surface) -> None:
        """Draw the sad effect if active."""
        if self.sad_effect and self.sad_effect.life > 0:
            self.sad_effect.draw(surface)
    
    def clear_effects(self) -> None:
        """Clear all active effects."""
        self.confetti_particles.clear()
        self.sad_effect = None
        self.confetti_timer = 0
        self.sad_timer = 0
