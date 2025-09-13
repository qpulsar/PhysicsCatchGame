import pygame
import sys
import subprocess
from settings import *
from .core.game_state import GameState
from .managers.effect_manager import EffectManager
from .managers.level_manager import LevelManager
from .managers.ui_manager import UIManager
from .components.player import Player
from .components.item import Item
from .screens.game_screens import (
    draw_game_selection_screen, 
    draw_playing_screen,
    MeshBackground,
    Database,
    Carousel
)

class Game:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.font = pygame.font.Font(None, 48)
        self.game_state = GameState()
        self.effect_manager = EffectManager()
        self.level_manager = LevelManager()
        self.ui_manager = UIManager()
        self.db = Database()

        # Game Selection Screen
        self.mesh_bg = MeshBackground(SCREEN_WIDTH, SCREEN_HEIGHT, particle_color=MD_LIGHT_GRAY, line_color=MD_TEAL)
        self.games = self.db.get_games()
        self.carousel = Carousel(self.games, self.font) if self.games else None
        
        self.current_state = 'game_selection' if self.carousel else 'no_games'
        self.selected_game_id = None
        self.editor_button_rect = None

        # Backgrounds (should be managed by a theme or level manager)
        self.level_bgs = [pygame.transform.scale(pygame.image.load(os.path.join('img', 'backgrounds', f'{i}.jpg')), (SCREEN_WIDTH, SCREEN_HEIGHT)) for i in range(2,6)]
        self.finish_bg = pygame.transform.scale(pygame.image.load(os.path.join('img', 'backgrounds', '6.jpg')), (SCREEN_WIDTH, SCREEN_HEIGHT))

    def run(self):
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()
        sys.exit()

    def handle_events(self):
        mouse_pos = pygame.mouse.get_pos()

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return False
            
            if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
                if self.current_state == 'game_selection' and self.editor_button_rect and self.editor_button_rect.collidepoint(event.pos):
                    try:
                        subprocess.Popen([sys.executable, "editor/editor.py"])
                        return False
                    except Exception as e:
                        print(f"Editör başlatılamadı: {e}")
                else:
                    self.handle_mouse_click(event.pos)

            if self.current_state == 'game_selection' and self.carousel:
                selected_id = self.carousel.handle_event(event)
                if selected_id:
                    self.start_game(selected_id)
            
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE:
                    return False
                elif self.current_state in ['game_over', 'level_up']:
                    if self.current_state == 'game_over':
                        self.current_state = 'game_selection'
                        if self.carousel:
                            self.carousel.selected_index = 0
                            self.carousel.target_x = SCREEN_WIDTH / 2
                    else: # level_up
                        self.current_state = 'playing'
        return True

    def handle_mouse_click(self, pos):
        if self.current_state == 'splash':
            button_rect = pygame.Rect((SCREEN_WIDTH - 220)//2, SCREEN_HEIGHT//2 + 40, 220, 70)
            if button_rect.collidepoint(pos):
                self.start_game(self.selected_game_id) # Needs a selected game
        elif self.current_state == 'playing':
            if self.game_state.help_button_rect.collidepoint(pos):
                self.game_state.help_mode = not self.game_state.help_mode
        elif self.current_state in ['game_over', 'level_up']:
            if self.current_state == 'game_over':
                self.current_state = 'game_selection'
            else:
                self.current_state = 'playing'
    
    def start_game(self, game_id):
        self.selected_game_id = game_id
        self.game_state.reset()
        self.level_manager.setup_level(1, game_id)
        self.game_state.player = Player()
        self.game_state.all_sprites.add(self.game_state.player)
        self.current_state = 'playing'

    def update(self):
        if self.current_state != 'playing':
            return
            
        new_state = self.game_state.update(self.level_manager)
        if new_state:
            self.current_state = new_state
            return

        self.handle_item_spawning()
        
        collision_state = self.check_collisions()
        if collision_state:
            self.current_state = collision_state
            
        self.remove_off_screen_items()

    def draw(self):
        mouse_pos = pygame.mouse.get_pos()
        if self.current_state == 'game_selection' or self.current_state == 'no_games':
            self.editor_button_rect = draw_game_selection_screen(self.screen, self.carousel, self.mesh_bg, mouse_pos)
        elif self.current_state == 'playing':
            draw_playing_screen(self.screen, self.game_state, self.level_manager, self.ui_manager, self.effect_manager, self.level_bgs)
        elif self.current_state == 'level_up':
            self.ui_manager.draw_level_up(self.screen, self.level_manager.level, self.level_manager.target_category)
        elif self.current_state == 'game_over':
            self.ui_manager.draw_game_over(self.screen, self.game_state.score)
        # splash screen is missing, we can add it or remove it from states
        
        pygame.display.flip()
    
    # Methods from main.py that are now part of the Game class
    def handle_item_spawning(self):
        if self.level_manager.spawn_index >= len(self.level_manager.spawn_events) and not self.level_manager.is_level_complete():
            self.level_manager.prepare_spawn_events(min_items=2, max_items=5)
        
        current_time = pygame.time.get_ticks()
        should_spawn, item_text, item_category = self.level_manager.should_spawn_item(current_time)
        
        if should_spawn:
            self.spawn_item(item_text, item_category)

    def spawn_item(self, text, category):
        item = Item(text, category)
        self.game_state.all_sprites.add(item)
        self.game_state.items.add(item)
        
        if category == self.level_manager.target_category:
            self.level_manager.dropped_correct.append(text)

    def check_collisions(self):
        if not self.game_state.player:
            return None
        hits = pygame.sprite.spritecollide(self.game_state.player, self.game_state.items, True)
        for hit in hits:
            if hit.item_type == self.level_manager.target_category:
                points = 5 if self.game_state.help_mode else 10
                self.game_state.score += points
                self.level_manager.caught_correct.append(hit.text)
                self.effect_manager.trigger_confetti(self.game_state.player.rect.centerx, self.game_state.player.rect.centery)
            else:
                if self.game_state.lose_life(reason="caught_wrong_item"):
                    return 'game_over'
                self.effect_manager.trigger_sad_effect(self.game_state.player.rect.centerx, self.game_state.player.rect.centery)
        return None

    def remove_off_screen_items(self):
        for item in list(self.game_state.items):
            if item.rect.top > SCREEN_HEIGHT + 10:
                if item.item_type == self.level_manager.target_category:
                    self.level_manager.level_queue.append(item.text)
                item.kill()
