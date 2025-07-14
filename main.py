import os
import sys
import pygame
from arduino import arduino_connected, ser
from item import Item
from settings import *
from game_state import GameState
from effect_manager import EffectManager
from level_manager import LevelManager
from ui_manager import UIManager
from utils import draw_text


# GAME START
# --- Oyun Yöneticilerini Başlat ---
pygame.init()
screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
pygame.display.set_caption("Fiziksel Büyüklükleri Yakala!")
clock = pygame.time.Clock()

# Oyun durumu yöneticisi
game_state = GameState()

# Efekt yöneticisi
effect_manager = EffectManager()

# Seviye yöneticisi
level_manager = LevelManager()
level_manager.setup_level(1)

# Arayüz yöneticisi
ui_manager = UIManager()

# Oyun durumu
current_state = 'splash'  # 'splash', 'playing', 'game_over', 'level_up'

# --- Sınıflar ---
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


# Oyun durumu artık GameState sınıfında yönetiliyor

# --- Oyun Durumu Fonksiyonları ---
def handle_events(current_state):
    """Handle all game events
    
    Args:
        current_state: The current game state
        
    Returns:
        tuple: (continue_running, new_state) - Whether to continue running and the updated game state
    """
    for event in pygame.event.get():
        if event.type == pygame.QUIT:
            return False, current_state
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if event.button == 1:  # Left mouse button
                current_state = handle_mouse_click(event.pos, current_state)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                return False, current_state
            elif event.key == pygame.K_h:
                game_state.help_mode = not game_state.help_mode
    return True, current_state

def handle_mouse_click(pos, current_state):
    """Handle mouse click events
    
    Args:
        pos: The (x, y) position of the mouse click
        current_state: The current game state
        
    Returns:
        str: The updated game state
    """
    if current_state == 'splash':
        # Check if start button is clicked
        button_rect = pygame.Rect((SCREEN_WIDTH - 220)//2, SCREEN_HEIGHT//2 + 40, 220, 70)
        if button_rect.collidepoint(pos):
            return start_game()  # Return the new state from start_game()
    elif current_state == 'playing':
        # Check if help button is clicked
        if game_state.help_button_rect.collidepoint(pos):
            game_state.help_mode = not game_state.help_mode
    elif current_state in ['game_over', 'level_up']:
        # Any click to continue
        if current_state == 'game_over':
            start_game()
            return 'playing'
        else:
            return 'playing'
    return current_state

def start_game():
    """Initialize or reset the game
    
    Returns:
        str: The new game state ('playing')
    """
    print("Starting new game...")
    game_state.reset()
    level_manager.setup_level(1)
    
    # Create and add player to the game state
    game_state.player = Player()
    game_state.all_sprites.add(game_state.player)
    
    return 'playing'

def update_game():
    """Update game state
    
    Returns:
        str or None: The new game state if it changed, None otherwise
    """
    if current_state != 'playing':
        print(f"Not in playing state: {current_state}")
        return None
    
    print("\n--- Updating game state ---")
    print(f"Current items: {len(game_state.items)}")
    print(f"Player position: {game_state.player.rect if game_state.player else 'No player'}")
        
    # Let GameState handle updates and state transitions
    new_state = game_state.update(level_manager)
    print(f"GameState update returned state: {new_state}")
    
    # Handle game mechanics that aren't part of the core state
    if new_state is None:  # Only process these if state didn't change
        print("Handling game mechanics...")
        handle_item_spawning()
        
        # Check for collisions and get potential state change
        collision_state = check_collisions()
        if collision_state:
            print(f"Collision triggered state change to: {collision_state}")
            new_state = collision_state
            
        remove_off_screen_items()
    
    print(f"Update complete. Next state: {new_state}")
    return new_state

def handle_item_spawning():
    """Handle the spawning of new items continuously."""
    # If the current spawn list is exhausted and the level isn't complete, prepare more items.
    if level_manager.spawn_index >= len(level_manager.spawn_events) and not level_manager.is_level_complete():
        print("\n--- Current spawn batch finished, preparing new one. ---")
        level_manager.prepare_spawn_events(min_items=2, max_items=5)
    
    # Check if we should spawn a new item based on the prepared events.
    current_time = pygame.time.get_ticks()
    should_spawn, item_text, item_category = level_manager.should_spawn_item(current_time)
    
    if should_spawn:
        print(f"Time: {current_time}, Spawning item: {item_text} ({item_category})")
        spawn_item(item_text, item_category)
        print(f"Total items after spawn: {len(game_state.items)}")

def spawn_item(text, category):
    """Spawn a new item with the given text and category"""
    try:
        print(f"Attempting to spawn item: {text} ({category})")
        item = Item(text, category)
        
        # Add to both sprite groups
        game_state.all_sprites.add(item)
        game_state.items.add(item)
        
        print(f"Item created and added to sprite groups. Total items: {len(game_state.items)}")
        
        # If it's a correct item, add it to dropped list
        if category == level_manager.target_category:
            level_manager.dropped_correct.append(text)
            print(f"Added to dropped_correct: {text}")
            
    except Exception as e:
        print(f"Error spawning item: {e}")
        import traceback
        traceback.print_exc()

def check_collisions():
    """Check for collisions between player and items"""
    if not game_state.player or not game_state.items:
        return
        
    hits = pygame.sprite.spritecollide(game_state.player, game_state.items, True)
    print(f"Checking collisions. Hits: {len(hits)}")
    
    for hit in hits:
        print(f"Collision with item: {hit.text} (type: {hit.item_type})")
        
        if hit.item_type == level_manager.target_category:
            # Correct item caught
            points = 5 if game_state.help_mode else 10
            game_state.score += points
            level_manager.caught_correct.append(hit.text)
            print(f"Correct item caught! Score: {game_state.score}")
            
            # Trigger confetti effect at player position
            effect_manager.trigger_confetti(
                game_state.player.rect.centerx, 
                game_state.player.rect.centery
            )
        else:
            # Wrong item caught
            print("Wrong item caught!")
            if game_state.lose_life(reason="caught_wrong_item"):
                return 'game_over'  # Return new state if game over
                
            # Trigger sad effect at player position
            effect_manager.trigger_sad_effect(
                game_state.player.rect.centerx,
                game_state.player.rect.centery
            )
    
    # Return None to indicate no state change (unless game over was triggered)
    return None

def remove_off_screen_items():
    """Remove items that have fallen off the screen"""
    for item in list(game_state.items):
        if item.rect.top > SCREEN_HEIGHT + 10:
            # If it's a correct item that wasn't caught, add it back to the queue
            if item.item_type == level_manager.target_category:
                level_manager.level_queue.append(item.text)
            item.kill()

def draw_game():
    """Draw the current game state"""
    if current_state == 'splash':
        draw_splash_screen()
    elif current_state == 'playing':
        draw_playing_screen()
    elif current_state == 'level_up':
        draw_level_up_screen()
    elif current_state == 'game_over':
        draw_game_over_screen()
    
    pygame.display.flip()
    clock.tick(60)

def draw_splash_screen():
    """Draw the splash screen"""
    button_rect = pygame.Rect((SCREEN_WIDTH - 220)//2, SCREEN_HEIGHT//2 + 40, 220, 70)
    mouse_pos = pygame.mouse.get_pos()
    is_hovered = button_rect.collidepoint(mouse_pos)
    
    ui_manager.draw_splash_screen(screen, button_rect, is_hovered)

def draw_playing_screen():
    """Draw the main game screen"""
    # Draw background
    bg_index = min(level_manager.level - 1, len(level_bgs) - 1)
    screen.blit(level_bgs[bg_index], (0, 0))
    
    # Debug: Print sprite counts
    print(f"\n--- Drawing Frame ---")
    print(f"Total sprites: {len(game_state.all_sprites)}")
    print(f"Items in group: {len(game_state.items)}")
    
    # Debug: Print sprite positions
    for i, sprite in enumerate(game_state.all_sprites):
        print(f"  Sprite {i}: {sprite.__class__.__name__} at {getattr(sprite, 'rect', 'no rect').topleft if hasattr(sprite, 'rect') else 'no rect'}")
    
    # Draw all sprites
    game_state.all_sprites.draw(screen)
    
    # Draw effects
    effect_manager.update()
    effect_manager.draw(screen)
    
    # Draw UI
    remaining_items = level_manager.get_remaining_items()
    ui_manager.draw_hud(
        screen, 
        game_state.score, 
        game_state.lives, 
        level_manager.level,
        level_manager.target_category,
        game_state.help_mode,
        remaining_items if game_state.help_mode else None
    )

def draw_level_up_screen():
    """Draw the level up screen"""
    ui_manager.draw_level_up(
        screen,
        level_manager.level,
        level_manager.target_category
    )

def draw_game_over_screen():
    """Draw the game over screen"""
    ui_manager.draw_game_over(screen, game_state.score)

def main():
    """Main game loop"""
    global current_state
    
    running = True
    clock = pygame.time.Clock()
    
    while running:
        # Handle events and get updated state
        running, current_state = handle_events(current_state)
        
        if not running:
            break
            
        # Update game state and handle state transitions
        if current_state == 'playing':
            new_state = update_game()
            if new_state:  # If the game state changed
                current_state = new_state
                continue  # Skip drawing this frame to prevent flicker
        
        # Draw the current screen based on game state
        if current_state == 'splash':
            # Create a button rectangle for the splash screen
            button_width, button_height = 200, 60
            button_x = (SCREEN_WIDTH - button_width) // 2
            button_y = SCREEN_HEIGHT // 2 + 20
            button_rect = pygame.Rect(button_x, button_y, button_width, button_height)
            
            # Check if mouse is hovering over the button
            mouse_x, mouse_y = pygame.mouse.get_pos()
            is_button_hovered = button_rect.collidepoint(mouse_x, mouse_y)
            
            # Draw the splash screen with the button
            ui_manager.draw_splash_screen(screen, button_rect, is_button_hovered)
        elif current_state == 'playing':
            draw_playing_screen()
        elif current_state == 'level_up':
            draw_level_up_screen()
        elif current_state == 'game_over':
            draw_game_over_screen()
        
        # Update the display and maintain frame rate
        pygame.display.flip()
        clock.tick(60)  # Cap at 60 FPS
    
    # Clean up
    pygame.quit()
    if ser and ser.is_open:
        ser.close()
    sys.exit()

def show_splash_screen():
    button_width = 220
    button_height = 70
    button_color = (30, 144, 255)
    button_hover_color = (0, 191, 255)
    button_rect = pygame.Rect((SCREEN_WIDTH - button_width)//2, SCREEN_HEIGHT//2 + 40, button_width, button_height)
    
    running = True
    while running:
        screen.blit(splash_bg, (0, 0))
        draw_text(screen, "Fiziksel Büyüklükleri Yakala!", 54, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 4, BLUE)
        draw_text(screen, "Doğru büyüklükleri topla, yanlışlardan kaç!", 32, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 4 + 70, BLACK)
        draw_text(screen, "Başlamak için aşağıdaki butona tıkla.", 28, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 30, BLACK)

        mouse_pos = pygame.mouse.get_pos()
        is_hover = button_rect.collidepoint(mouse_pos)
        color = button_hover_color if is_hover else button_color
        pygame.draw.rect(screen, color, button_rect, border_radius=15)
        draw_text(screen, "Başlat", 40, SCREEN_WIDTH/2, button_rect.centery, WHITE)

        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                sys.exit()
            if event.type == pygame.MOUSEBUTTONDOWN and is_hover:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                running = False
        clock.tick(60)

if __name__ == "__main__":
    # Load background images

    level_bgs = [pygame.image.load(os.path.join('img', 'backgrounds', f'{i}.jpg')) for i in range(2,6)]
    level_bgs = [pygame.transform.scale(bg, (SCREEN_WIDTH, SCREEN_HEIGHT)) for bg in level_bgs]
    
    finish_bg = pygame.image.load(os.path.join('img', 'backgrounds', '6.jpg'))
    finish_bg = pygame.transform.scale(finish_bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
    
    # Start the game
    main()



