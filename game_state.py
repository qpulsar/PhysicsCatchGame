import os
import pygame
from settings import *

class GameState:
    def __init__(self):
        # Game state
        self.score = 0
        self.lives = 3
        self.level = 1
        self.game_over = False
        self.help_mode = False
        
        # Player state
        self.player = None
        self.player_speed = PLAYER_SPEED
        
        # Level state
        self.target_category = None
        self.correct_items = []
        self.dropped_correct = []
        self.caught_correct = []
        self.level_queue = []
        
        # Game objects
        self.all_sprites = pygame.sprite.Group()
        self.items = pygame.sprite.Group()
        
        # Effects
        self.confetti_effect_timer = 0
        self.confetti_particles = []
        self.sad_effect_timer = 0
        self.sad_effect = None
        
        # Spawn management
        self.spawn_events = []
        self.spawn_index = 0
        self.next_spawn_tick = 0
        self.item_spawned_count = 0
        self.total_items_to_spawn = 0
        self.spawn_ready = False
        
        # UI elements
        self.help_button_rect = pygame.Rect(10, 10, 60, 40)
        self.help_button_img = None
        
        # Initialize UI elements
        self._init_ui()
    
    def _init_ui(self):
        """Initialize UI elements that require pygame to be initialized"""
        help_img_path = os.path.join('img', 'button_help.png')
        if os.path.exists(help_img_path):
            self.help_button_img = pygame.image.load(help_img_path)
            self.help_button_img = pygame.transform.scale(self.help_button_img, (40, 40))
    
    def reset(self):
        """Reset the game state to initial values"""
        self.__init__()
    
    def setup_level(self, level):
        """Set up a new level with the given level number"""
        self.level = level
        self.target_category = LEVEL_TARGETS[level]
        self.correct_items = ALL_QUANTITIES[self.target_category][:]
        self.dropped_correct = []
        self.caught_correct = []
        self.level_queue = self.correct_items.copy()
        
        # Clear existing items
        for item in self.items:
            item.kill()
        
        # Reset spawn state
        self.spawn_events = []
        self.spawn_index = 0
        self.next_spawn_tick = 0
        self.item_spawned_count = 0
        self.total_items_to_spawn = 0
        self.spawn_ready = False
    
    def create_player(self):
        """Create and return a new player instance"""
        self.player = Player()
        self.all_sprites.add(self.player)
        return self.player
    
    def add_score(self, points):
        """Add points to the score"""
        self.score += points
    
    def lose_life(self, reason="unknown"):
        """Decrease lives and check for game over
        
        Args:
            reason (str): The reason for losing a life (for debugging)
        """
        print(f"Losing a life. Reason: {reason}. Current lives: {self.lives} -> {self.lives - 1}")
        self.lives -= 1
        if self.lives <= 0:
            print("Game over! No lives remaining.")
            self.game_over = True
        return self.game_over
    
    def is_level_complete(self):
        """Check if the current level is complete"""
        return set(self.caught_correct) >= set(self.correct_items)
    
    def get_remaining_items(self):
        """Get items that haven't been caught yet"""
        return [item for item in self.correct_items if item not in self.caught_correct]
    
    def cleanup_effects(self):
        """Clean up expired effects"""
        # Clean up expired confetti particles
        self.confetti_particles = [p for p in self.confetti_particles 
                                 if p.timer > 0]
        
        # Clean up sad effect if expired
        if hasattr(self, 'sad_effect') and self.sad_effect and self.sad_effect.life <= 0:
            self.sad_effect = None
                                  
    def update(self, level_manager):
        """Update game state
        
        Args:
            level_manager: The level manager instance to use for level-related operations
            
        Returns:
            str or None: The new game state if it changed, None otherwise
        """
        # Update all sprites (including player and items)
        self.all_sprites.update()
        
        # Update player separately if needed for input handling
        if self.player:
            self.player.update()
            
        # Debug: Print number of items and their positions
        if hasattr(self, 'debug_counter'):
            self.debug_counter += 1
            if self.debug_counter >= 60:  # Print every second (assuming 60 FPS)
                print(f"\n--- GameState Update ---")
                print(f"Total sprites: {len(self.all_sprites)}")
                print(f"Items in group: {len(self.items)}")
                for i, item in enumerate(self.items):
                    if hasattr(item, 'rect'):
                        print(f"  Item {i+1}: '{getattr(item, 'text', '?')}' at {item.rect.topleft}")
                    else:
                        print(f"  Item {i+1}: Missing rect!")
                self.debug_counter = 0
        else:
            self.debug_counter = 0
            
        # Check for level completion
        if level_manager.is_level_complete():
            if level_manager.level >= len(level_manager.LEVEL_TARGETS):
                self.game_over = True
                return 'game_over'
            else:
                level_manager.level += 1
                level_manager.setup_level(level_manager.level)
                return 'level_up'
                
        # Update effects
        self.cleanup_effects()
        
        # Update confetti particles
        for particle in self.confetti_particles:
            particle.update()
            
        # Update sad effect if active
        if hasattr(self, 'sad_effect') and self.sad_effect:
            self.sad_effect.update()
            
        return None  # No state change
