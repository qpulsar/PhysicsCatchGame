import pygame
import sys
import subprocess
import os
from settings import *
from .core.game_state import GameState
from .managers.effect_manager import EffectManager
from .managers.level_manager import LevelManager
from .managers.ui_manager import UIManager
from .components.player import Player
from .components.item import Item
from .screens.game_screens import (
    draw_game_selection_screen, 
    draw_game_info_screen,
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
        self.per_game_bg_surface = None
        self.level_bg_surface = None
        self.paddle_surface = None

        # Game Selection Screen
        self.mesh_bg = MeshBackground(SCREEN_WIDTH, SCREEN_HEIGHT, particle_color=LIGHT_GRAY, line_color=TEAL)
        self.games = self.db.get_games()
        self.carousel = Carousel(self.games, self.font) if self.games else None
        
        self.current_state = 'game_selection' if self.carousel else 'no_games'
        self.selected_game_id = None
        self.selected_game = None
        self.editor_button_rect = None
        self.start_button_rect = None

        # Backgrounds (should be managed by a theme or level manager)
        self.level_bgs = self._load_default_backgrounds()
        # Finish background: fall back to first of level_bgs
        self.finish_bg = self.level_bgs[-1] if self.level_bgs else pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))

    def run(self):
        """Ana oyun döngüsünü çalıştırır."""
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()
        sys.exit()

    def _load_default_backgrounds(self):
        """Yoksa hata vermeyen, esnek varsayılan arkaplan yükleyici.

        Öncelik sırası:
        1) img/backgrounds/{2..5}.jpg
        2) assets/images/ içindeki mevcut jpg/png dosyaları
        3) Düz renk yüzeyler (ayarlanmış paletten)

        Returns:
            list[pygame.Surface]: Ekran boyutunda arkaplan yüzeyleri listesi
        """
        candidates = []
        # 1) legacy backgrounds
        for i in range(2, 6):
            p = os.path.join('img', 'backgrounds', f'{i}.jpg')
            if os.path.exists(p):
                candidates.append(p)
        # 2) assets/images altından al
        assets_img_dir = os.path.join('assets', 'images')
        if os.path.isdir(assets_img_dir):
            for fn in sorted(os.listdir(assets_img_dir)):
                if fn.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    candidates.append(os.path.join(assets_img_dir, fn))
        # Görselleri yükle
        surfaces = []
        for path in candidates:
            try:
                img = pygame.image.load(path)
                surfaces.append(pygame.transform.scale(img, (SCREEN_WIDTH, SCREEN_HEIGHT)))
            except Exception:
                continue
        if surfaces:
            return surfaces
        # 3) Fallback plain color surfaces
        palette = [
            (20, 20, 30),
            (30, 40, 60),
            (40, 60, 90),
            (60, 80, 110),
        ]
        return [self._make_color_surface(c) for c in palette]

    def _make_color_surface(self, color):
        """Belirtilen renkte ekran boyutunda yüzey üretir."""
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill(color)
        return surf

    def handle_events(self):
        """Girdi olaylarını işler ve durum geçişlerini yönetir."""
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
                    self.selected_game_id = selected_id
                    self.selected_game = next((g for g in self.games if getattr(g, 'id', None) == selected_id), None)
                    # Load per-game background if set
                    self.per_game_bg_surface = None
                    try:
                        settings = self.db.get_game_settings(self.selected_game_id)
                        bg_path = settings.get('start_background_path')
                        if bg_path and os.path.exists(bg_path):
                            self.per_game_bg_surface = pygame.image.load(bg_path).convert()
                    except Exception as _:
                        self.per_game_bg_surface = None
                    self.current_state = 'game_info'
            
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
                elif self.current_state == 'game_info' and (event.key == pygame.K_RETURN or event.key == pygame.K_SPACE):
                    self.start_game(self.selected_game_id)
        return True

    def handle_mouse_click(self, pos):
        if self.current_state == 'splash':
            button_rect = pygame.Rect((SCREEN_WIDTH - 220)//2, SCREEN_HEIGHT//2 + 40, 220, 70)
            if button_rect.collidepoint(pos):
                self.start_game(self.selected_game_id) # Needs a selected game
        elif self.current_state == 'game_info':
            if self.start_button_rect and self.start_button_rect.collidepoint(pos):
                self.start_game(self.selected_game_id)
        elif self.current_state == 'playing':
            if self.game_state.help_button_rect.collidepoint(pos):
                self.game_state.help_mode = not self.game_state.help_mode
        elif self.current_state in ['game_over', 'level_up']:
            if self.current_state == 'game_over':
                self.current_state = 'game_selection'
            else:
                self.current_state = 'playing'
    
    def start_game(self, game_id):
        """Seçilen oyunla oynanışı başlatır ve ayarları uygular.

        - Level ayarlarını yükler ve uygular
        - Seviye arkaplanını ve paddle görselini yükler
        - Oyun müziğini ayarlardan ya da varsayılanlardan başlatır
        """
        self.selected_game_id = game_id
        self.game_state.reset()
        self.level_manager.setup_level(1, game_id)

        # Load level-specific background if available
        self.level_bg_surface = None
        try:
            settings_map = self.db.get_game_settings(game_id)
            lvl_key = f"level_{self.level_manager.level}_background_path"
            bg_path = settings_map.get(lvl_key)
            if bg_path and os.path.exists(bg_path):
                self.level_bg_surface = pygame.image.load(bg_path).convert()
        except Exception:
            self.level_bg_surface = None

        # Load paddle from settings (sprite sheet region)
        self.paddle_surface = None
        try:
            settings_map = settings_map if 'settings_map' in locals() else self.db.get_game_settings(game_id)
            paddle_key = f"level_{self.level_manager.level}_paddle_sprite"
            data = settings_map.get(paddle_key)
            if data:
                import json
                info = json.loads(data)
                sheet_path = self.db.get_sprite_path(int(info.get('sprite_id', 0)))
                if sheet_path and os.path.exists(sheet_path):
                    sheet_img = pygame.image.load(sheet_path).convert_alpha()
                    rect = pygame.Rect(int(info['x']), int(info['y']), int(info['width']), int(info['height']))
                    self.paddle_surface = sheet_img.subsurface(rect).copy()
        except Exception:
            self.paddle_surface = None

        self.game_state.player = Player(self.paddle_surface)
        self.game_state.all_sprites.add(self.game_state.player)
        self.game_state.items.add(self.game_state.player) if False else None  # no-op to keep structure
        self.current_state = 'playing'

        # Start background music (settings or default)
        try:
            if 'settings_map' not in locals():
                settings_map = self.db.get_game_settings(game_id)
            music_path = settings_map.get('music_path') if settings_map else None
            if music_path and os.path.exists(music_path):
                chosen_music = music_path
            else:
                # pick first available under assets/audio or assets/midi
                chosen_music = None
                for base in ('assets/audio', 'assets/midi'):
                    if os.path.isdir(base):
                        for fn in os.listdir(base):
                            if fn.lower().endswith(('.mp3', '.wav', '.ogg', '.mid', '.midi')):
                                chosen_music = os.path.join(base, fn)
                                break
                    if chosen_music:
                        break
            if chosen_music:
                try:
                    if not pygame.mixer.get_init():
                        pygame.mixer.init()
                    pygame.mixer.music.load(chosen_music)
                    pygame.mixer.music.set_volume(0.5)
                    pygame.mixer.music.play(-1)
                except Exception as _:
                    pass
        except Exception:
            pass

        # Apply settings from editor: max concurrent items, item speed
        try:
            max_items_on_screen = int(settings_map.get('default_max_items', 5))
            self.level_manager.max_items_on_screen = max_items_on_screen
            item_speed = float(settings_map.get('default_item_speed', 3.0))
            self.level_manager.item_speed = item_speed
        except Exception:
            pass

    def update(self):
        """Oyun durumunu günceller; oynanış harici durumlarda erken döner."""
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
        elif self.current_state == 'game_info':
            self.start_button_rect = draw_game_info_screen(self.screen, self.selected_game, self.mesh_bg, mouse_pos, self.per_game_bg_surface)
        elif self.current_state == 'playing':
            draw_playing_screen(self.screen, self.game_state, self.level_manager, self.ui_manager, self.effect_manager, self.level_bgs, self.level_bg_surface)
        elif self.current_state == 'level_up':
            self.ui_manager.draw_level_up(self.screen, self.level_manager.level, self.level_manager.target_category)
        elif self.current_state == 'game_over':
            self.ui_manager.draw_game_over(self.screen, self.game_state.score)
        # splash screen is missing, we can add it or remove it from states
        
        pygame.display.flip()
    
    # Methods from main.py that are now part of the Game class
    def handle_item_spawning(self):
        """Nesne doğurma akışını yönetir ve eşzamanlı nesne sınırına uyar."""
        # Hazır event yoksa üret
        if self.level_manager.spawn_index >= len(self.level_manager.spawn_events) and not self.level_manager.is_level_complete():
            # min/max adetleri makul tut; LevelManager içeriden kalan doğru öğeleri ekler
            self.level_manager.prepare_spawn_events(min_items=2, max_items=5)

        # Ekranda çok fazla nesne varsa bekle
        try:
            active_items = len(self.game_state.items)
            if active_items >= max(1, int(getattr(self.level_manager, 'max_items_on_screen', 5))):
                return
        except Exception:
            pass

        current_time = pygame.time.get_ticks()
        should_spawn, item_text, item_category = self.level_manager.should_spawn_item(current_time)

        if should_spawn:
            self.spawn_item(item_text, item_category)

    def spawn_item(self, text, category):
        """Yeni bir düşen nesne oluşturur ve hızını ayarlardan uygular."""
        item = Item(text, category)
        # Editörden gelen hız ayarını uygula
        try:
            speed = float(getattr(self.level_manager, 'item_speed', 3.0))
            if speed > 0:
                item.speed_y = speed
        except Exception:
            pass
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
