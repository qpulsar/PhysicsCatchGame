import pygame
import json
from settings import *
from ..core.utils import draw_text
import random
import math
import sqlite3
import os

class MeshBackground:
    """Creates an animated mesh background with moving particles and lines."""
    def __init__(self, width, height, num_particles=50, particle_color=(200, 200, 255), line_color=(200, 200, 255), max_dist=150):
        self.width = width
        self.height = height
        self.particles = [self._create_particle() for _ in range(num_particles)]
        self.particle_color = particle_color
        self.line_color = line_color
        self.max_dist = max_dist
        self.max_dist_sq = max_dist ** 2

    def _create_particle(self):
        """Creates a single particle with random properties."""
        return {
            'x': random.uniform(0, self.width),
            'y': random.uniform(0, self.height),
            'vx': random.uniform(-0.5, 0.5),
            'vy': random.uniform(-0.5, 0.5),
            'radius': random.uniform(1.5, 3.5)
        }

    def update(self):
        """Updates the position of all particles."""
        for p in self.particles:
            p['x'] += p['vx']
            p['y'] += p['vy']

            if p['x'] <= 0 or p['x'] >= self.width:
                p['vx'] *= -1
                p['x'] = max(0, min(p['x'], self.width))
            if p['y'] <= 0 or p['y'] >= self.height:
                p['vy'] *= -1
                p['y'] = max(0, min(p['y'], self.height))

    def draw(self, surface):
        """Draws particles and connecting lines on the given surface."""
        for i, p1 in enumerate(self.particles):
            pygame.draw.circle(surface, self.particle_color, (int(p1['x']), int(p1['y'])), int(p1['radius']))

            for p2 in self.particles[i+1:]:
                dist_sq = (p1['x'] - p2['x'])**2 + (p1['y'] - p2['y'])**2
                if dist_sq < self.max_dist_sq:
                    distance = math.sqrt(dist_sq)
                    
                    # Calculate brightness based on distance (0 to 1)
                    brightness = max(0.0, 1.0 - distance / self.max_dist)
                    
                    # Create a color that fades with distance
                    final_line_color = (
                        int(self.line_color[0] * brightness),
                        int(self.line_color[1] * brightness),
                        int(self.line_color[2] * brightness)
                    )
                    
                    # Only draw if the line is bright enough to be seen
                    if brightness > 0.05:
                        pygame.draw.line(surface, final_line_color, (p1['x'], p1['y']), (p2['x'], p2['y']), 1)

class Database:
    """A simple class to fetch game data for the main game."""
    def __init__(self, db_path='game_data.db'):
        self.db_path = db_path

    def get_games(self) -> list: # Hinting for Game object would require importing it
        """Get all games as Game objects."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM games ORDER BY name')
                # Dynamically create a simple object to avoid dependency on editor models
                Game = type("Game", (), {})
                games = []
                for row in cursor.fetchall():
                    game_obj = Game()
                    for key, value in dict(row).items():
                        setattr(game_obj, key, value)
                    games.append(game_obj)
                return games
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []

    def get_level_effect_settings(self, level_id: int) -> dict:
        """Read effect settings columns from levels table if present.

        Returns keys only if available in schema and non-null: 
        - effect_correct_sheet, effect_wrong_sheet, effect_fps, effect_scale_percent
        - effect_correct_sheet_id, effect_wrong_sheet_id
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                # Check columns existence via PRAGMA to avoid SQL errors on older DBs
                cursor.execute('PRAGMA table_info(levels)')
                cols = {row[1] for row in cursor.fetchall()}
                wanted = [
                    'effect_correct_sheet',
                    'effect_wrong_sheet',
                    'effect_fps',
                    'effect_scale_percent',
                    'effect_correct_sheet_id',
                    'effect_wrong_sheet_id',
                    'effect_correct_id',
                    'effect_wrong_id'
                ]
                if not any(k in cols for k in wanted):
                    return {}
                select_cols = ', '.join([k for k in wanted if k in cols])
                cursor.execute(f'SELECT {select_cols} FROM levels WHERE id = ?', (level_id,))
                row = cursor.fetchone()
                if not row:
                    return {}
                out = {}
                for k in wanted:
                    if k in row.keys() and row[k] is not None and row[k] != '':
                        out[k] = row[k]
                return out
        except sqlite3.Error as e:
            print(f"Database error get_level_effect_settings: {e}")
            return {}

    def get_effect_sheet_by_id(self, effect_id: int) -> dict | None:
        """Fetch a single effect_sheets row as dict."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM effect_sheets WHERE id = ?', (effect_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Database error get_effect_sheet_by_id: {e}")
            return None

    def get_effect_by_id(self, effect_id: int) -> dict | None:
        """Fetch a single effect row from 'effects' table as dict."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT * FROM effects WHERE id = ?', (effect_id,))
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Database error get_effect_by_id: {e}")
            return None

    def get_game_settings(self, game_id: int) -> dict:
        """Get settings key/value for a specific game."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT key, value FROM game_settings WHERE game_id = ?', (game_id,))
                return {row['key']: row['value'] for row in cursor.fetchall()}
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return {}

    def get_sprite_path(self, sprite_id: int) -> str | None:
        """Get sprite sheet file path by sprite ID."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT path FROM sprites WHERE id = ?', (sprite_id,))
                row = cursor.fetchone()
                return row['path'] if row else None
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None

    def get_levels(self, game_id: int) -> list[dict]:
        """Get levels for a given game as list of dicts sorted by level_number."""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT id, level_number, level_name FROM levels WHERE game_id = ? ORDER BY level_number', (game_id,))
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []

    def get_screen(self, game_id: int, name: str) -> dict | None:
        """Fetch a designed screen JSON for given game and name.

        Doc:
            - Reads from `screens` table created by the editor.
            - Returns parsed `data_json` as dict, or None if not found/invalid.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute('SELECT data_json FROM screens WHERE game_id = ? AND name = ?', (game_id, name))
                row = cursor.fetchone()
                if not row:
                    return None
                try:
                    return json.loads(row['data_json']) if row['data_json'] else None
                except Exception:
                    return None
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return None

    def get_level_background_regions(self, level_id: int) -> list[dict]:
        """Return sprite regions (with sheet path) mapped to a level for falling items backgrounds.

        Joins level_background_regions -> sprite_regions -> sprites to obtain
        sheet path and region geometry.
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT sr.x, sr.y, sr.width, sr.height, sr.image_path AS sheet_path
                    FROM level_background_regions lbr
                    JOIN sprite_regions sr ON sr.id = lbr.region_id
                    WHERE lbr.level_id = ?
                    ORDER BY lbr.id
                    ''',
                    (level_id,)
                )
                return [dict(row) for row in cursor.fetchall()]
        except sqlite3.Error as e:
            print(f"Database error: {e}")
            return []

    def get_sprite_region(self, region_key: str) -> dict | None:
        """'name — image_path' anahtarına göre sprite bölgesini döndürür.
        sprite_regions şeması: (image_path, name, x, y, width, height)
        """
        if not region_key or ' — ' not in region_key:
            return None
        
        name, image_path = region_key.split(' — ', 1)
        image_path = image_path.strip()
        name = name.strip()

        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.row_factory = sqlite3.Row
                cursor = conn.cursor()
                cursor.execute(
                    '''
                    SELECT x, y, width, height, image_path AS sheet_path
                    FROM sprite_regions
                    WHERE name = ? AND image_path = ?
                    ''',
                    (name, image_path)
                )
                row = cursor.fetchone()
                return dict(row) if row else None
        except sqlite3.Error as e:
            print(f"Database error in get_sprite_region: {e}")
            return None

class Carousel:
    """Manages the game selection carousel."""
    def __init__(self, games: list, font: pygame.font.Font):
        self.games = games
        self.font = font
        self.selected_index = 0
        # Thumbnail boyutlarını sabitle: 150x150
        self.card_w = 150
        self.card_h = 150
        self.card_spacing = self.card_w + CARD_GAP
        self.cards = self._create_cards()
        self.target_x = SCREEN_WIDTH / 2
        self.current_x = self.target_x
        self.anim_speed = 0.1
        
        # Cooldown for key presses
        self.key_cooldown = 200  # milliseconds
        self.last_key_press_time = 0

        # Mouse dragging state
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_offset = 0
        self.card_rects = []
        # Last selected rect (for external layout binding)
        self.selected_rect: pygame.Rect | None = None

    def _create_cards(self) -> list[pygame.Surface]:
        """Create surfaces (cards) for each game with vibrant backgrounds."""
        cards = []
        for idx, game in enumerate(self.games):
            # Prefer per-game assets thumbnail if present in settings
            assets_thumb = None
            try:
                settings = Database().get_game_settings(getattr(game, 'id', 0))
                assets_thumb = settings.get('thumbnail_path')
            except Exception:
                assets_thumb = None
            thumbnail_path = assets_thumb if assets_thumb and os.path.exists(assets_thumb) else f"img/thumbnails/{game.id}.png"
            card_surface = pygame.Surface((self.card_w, self.card_h), pygame.SRCALPHA)

            # Canlı arka planı her zaman çiz
            base_color = CARD_PALETTE[idx % len(CARD_PALETTE)] if 'CARD_PALETTE' in globals() else CARD_COLOR
            pygame.draw.rect(card_surface, base_color, card_surface.get_rect(), border_radius=12)

            # Görsel varsa içeri yerleştir, yoksa adını yaz
            try:
                if os.path.exists(thumbnail_path):
                    img = pygame.image.load(thumbnail_path).convert_alpha()
                    img = pygame.transform.scale(img, (self.card_w - 20, self.card_h - 20))
                    img_rect = img.get_rect()
                    img_rect.topleft = (10, 10)
                    card_surface.blit(img, img_rect)
                else:
                    raise FileNotFoundError
            except (pygame.error, FileNotFoundError):
                draw_text(card_surface, game.name, 22, self.card_w / 2, self.card_h / 2, WHITE, wrap_width=self.card_w - 24)

            cards.append(card_surface)
        return cards

    def get_current_selected_rect(self) -> pygame.Rect:
        """Calculates the rect of the selected card based on current_x without drawing."""
        # Seçili kartın merkezi self.current_x'tir
        center_x = self.current_x
        
        # Ölçek hesabı (draw metoduyla aynı mantık)
        dist = abs(center_x - SCREEN_WIDTH / 2)
        scale = max(0.5, 1.0 - (dist / (SCREEN_WIDTH * 0.75)) * 0.5)
        
        w = int(self.card_w * scale)
        h = int(self.card_h * scale)
        
        # Kartın dikey konumu (daha aşağı alındı)
        cy = int(SCREEN_HEIGHT * 0.6)
        rect = pygame.Rect(0, 0, w, h)
        rect.center = (center_x, cy)
        return rect

    def update(self):
        """Update carousel animation."""
        # Basit lerp yerine, hedefe çok yakınsa direkt eşitleme
        diff = self.target_x - self.current_x
        if abs(diff) < 1.0:
            self.current_x = self.target_x
        else:
            self.current_x += diff * self.anim_speed

    def draw(self, surface: pygame.Surface):
        """Draw the carousel on the given surface."""
        self.card_rects.clear()
        
        # Draw cards from back to front
        sorted_indices = sorted(range(len(self.cards)), key=lambda i: abs(i - self.selected_index), reverse=True)

        for i in sorted_indices:
            card = self.cards[i]
            offset = (i - self.selected_index) * self.card_spacing + (self.current_x - SCREEN_WIDTH / 2)
            center_x = SCREEN_WIDTH / 2 + offset
            
            dist_from_center = abs(center_x - SCREEN_WIDTH / 2)
            scale = max(0.5, 1.0 - (dist_from_center / (SCREEN_WIDTH * 0.75)) * 0.5)
            
            # Uzaktaki kartları çizme
            if scale < 0.51 and i != self.selected_index:
                self.card_rects.append((pygame.Rect(0,0,0,0), i)) 
                continue

            scaled_card = pygame.transform.smoothscale(card, (int(self.card_w * scale), int(self.card_h * scale)))
            # Kartın dikey konumu (daha aşağı alındı)
            cy = int(SCREEN_HEIGHT * 0.6)
            rect = scaled_card.get_rect(center=(center_x, cy))
            
            # Store rect with its index
            self.card_rects.append((rect, i))

            if i == self.selected_index:
                # Seçili karta parlak dış hat ve hafif gölge
                outline_rect = rect.inflate(24, 24)
                pygame.draw.rect(surface, CARD_SELECTED_COLOR, outline_rect, width=4, border_radius=18)
                shadow = pygame.Surface((outline_rect.width, outline_rect.height), pygame.SRCALPHA)
                pygame.draw.rect(shadow, (0,0,0,80), shadow.get_rect(), border_radius=18)
                surface.blit(shadow, outline_rect.topleft)
                # Expose selected rect
                self.selected_rect = rect.copy()

            surface.blit(scaled_card, rect)
        
        # Ensure card_rects is sorted by index for correct click detection
        self.card_rects.sort(key=lambda item: item[1])


    def handle_event(self, event):
        """Handle user input for the carousel."""
        current_time = pygame.time.get_ticks()

        # Keyboard input with cooldown
        if event.type == pygame.KEYDOWN:
            if current_time - self.last_key_press_time > self.key_cooldown:
                moved = False
                if event.key == pygame.K_RIGHT and self.selected_index < len(self.games) - 1:
                    self.selected_index += 1
                    moved = True
                elif event.key == pygame.K_LEFT and self.selected_index > 0:
                    self.selected_index -= 1
                    moved = True
                
                if moved:
                    self.target_x = (SCREEN_WIDTH / 2) - (self.selected_index * self.card_spacing)
                    self.last_key_press_time = current_time

            if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                return self.games[self.selected_index].id

        # Mouse wheel input with cooldown
        if event.type == pygame.MOUSEWHEEL:
            if current_time - self.last_key_press_time > self.key_cooldown:
                moved = False
                if event.y < 0 and self.selected_index < len(self.games) - 1: # Scroll down/right
                    self.selected_index += 1
                    moved = True
                elif event.y > 0 and self.selected_index > 0: # Scroll up/left
                    self.selected_index -= 1
                    moved = True
                
                if moved:
                    self.target_x = (SCREEN_WIDTH / 2) - (self.selected_index * self.card_spacing)
                    self.last_key_press_time = current_time

        # Mouse drag input
        if event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            self.dragging = True
            self.drag_start_x = event.pos[0]
            self.drag_start_offset = self.current_x

        if event.type == pygame.MOUSEBUTTONUP and event.button == 1:
            if self.dragging:
                self.dragging = False
                # Snap to the nearest card
                offset = self.current_x - (SCREEN_WIDTH / 2)
                # Daha kararlı bir yuvarlama için
                idx = round(-offset / self.card_spacing)
                self.selected_index = max(0, min(len(self.games) - 1, int(idx)))
                
                # Hedef konumu kesin olarak ayarla
                self.target_x = (SCREEN_WIDTH / 2) - (self.selected_index * self.card_spacing)

                # Check for click on the selected card
                if abs(event.pos[0] - self.drag_start_x) < 5: # It's a click, not a drag
                    for rect, index in self.card_rects:
                        if rect.collidepoint(event.pos) and index == self.selected_index:
                            return self.games[self.selected_index].id

        if event.type == pygame.MOUSEMOTION and self.dragging:
            drag_delta = event.pos[0] - self.drag_start_x
            self.current_x = self.drag_start_offset + drag_delta
            # Sürüklerken hedef de güncellensin ama sınırları aşmasın diye basit kontrol eklenebilir
            # Şimdilik serbest bırakıyoruz, bırakınca snap olacak.
            self.target_x = self.current_x

        return None

def _draw_level_tree(screen, center_rect: pygame.Rect, levels: list):
    """Draws levels branching out vertically (up/down) from the center card."""
    if not levels:
        return

    center_x, center_y = center_rect.center
    
    # Dalların uzunluğu (kısaltıldı)
    radius = 110
    
    # Font (küçültüldü)
    font = pygame.font.Font(None, 22)

    # Gruplama: Çiftler yukarı, Tekler aşağı
    upper_levels = levels[0::2]
    lower_levels = levels[1::2]
    
    def draw_branch(level, angle_deg):
        # Açı: 0 sağ, -90 yukarı, 90 aşağı
        rad = math.radians(angle_deg)
        
        # Merkezden başla
        start_pos = (center_x, center_y)
        
        end_x = center_x + radius * math.cos(rad)
        end_y = center_y + radius * math.sin(rad)
        end_pos = (end_x, end_y)
        
        line_color = (200, 200, 255, 180)
        pygame.draw.line(screen, line_color, start_pos, end_pos, 3)
        
        # Uç nokta
        pygame.draw.circle(screen, CARD_SELECTED_COLOR, (int(end_x), int(end_y)), 6)
        pygame.draw.circle(screen, WHITE, (int(end_x), int(end_y)), 3)
        
        # Metin
        level_name = level.get('level_name', str(level.get('level_number')))
        text_surf = font.render(level_name, True, TEXT_COLOR)
        
        # Metni dalın ucuna, biraz öteye koy
        t_offset = 18
        tx = end_x + t_offset * math.cos(rad)
        ty = end_y + t_offset * math.sin(rad)
        text_rect = text_surf.get_rect(center=(tx, ty))
        
        # Arkaplan kutusu (yarı saydam)
        bg_rect = text_rect.inflate(8, 4)
        s = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
        s.fill((20, 20, 40, 200)) # Koyu yarı saydam
        screen.blit(s, bg_rect.topleft)
        screen.blit(text_surf, text_rect)

    # Yukarıdakileri dağıt (-130 ile -50 arası)
    if upper_levels:
        count = len(upper_levels)
        if count == 1:
            angles = [-90]
        else:
            min_a, max_a = -130, -50
            step = (max_a - min_a) / (count - 1)
            angles = [min_a + i * step for i in range(count)]
            
        for i, lvl in enumerate(upper_levels):
            draw_branch(lvl, angles[i])

    # Aşağıdakileri dağıt (50 ile 130 arası)
    if lower_levels:
        count = len(lower_levels)
        if count == 1:
            angles = [90]
        else:
            min_a, max_a = 50, 130
            step = (max_a - min_a) / (count - 1)
            angles = [min_a + i * step for i in range(count)]
            
        for i, lvl in enumerate(lower_levels):
            draw_branch(lvl, angles[i])


def draw_game_selection_screen(screen, carousel, mesh_bg, mouse_pos):
    """Draws the game selection carousel and handles the 'no games' state."""
    screen.fill(CAROUSEL_BG_COLOR)
    mesh_bg.update()
    mesh_bg.draw(screen)
    
    if carousel:
        draw_text(screen, "Bir Oyun Seç", 56, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.14, TEXT_COLOR)
        
        carousel.update()

        # Önce seçili kartın pozisyonunu tahmin et ve ağacı arkaya çiz
        try:
            selected_game = carousel.games[carousel.selected_index] if carousel.games else None
            if selected_game:
                # Çizim yapmadan rect'i hesapla
                sel_rect = carousel.get_current_selected_rect()
                levels = Database().get_levels(getattr(selected_game, 'id', 0))
                _draw_level_tree(screen, sel_rect, levels)
        except Exception as e:
            print(f"Tree draw error: {e}")
            pass
        
        # Şimdi kartları öne çiz
        carousel.draw(screen)
    else:
        draw_text(screen, "Oyun Bulunamadı", 64, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 3, TEXT_COLOR)
        draw_text(screen, "Lütfen editör programını kullanarak bir oyun oluşturun.", 28, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, TEXT_COLOR)
        
    # Draw the "Oyun Tasarla" button with a hover effect
    editor_button_rect = pygame.Rect(SCREEN_WIDTH - 220, SCREEN_HEIGHT - 70, 200, 50)
    is_hovered = editor_button_rect.collidepoint(mouse_pos)
    
    button_color = PURPLE_LIGHT if is_hovered else PURPLE
    
    pygame.draw.rect(screen, button_color, editor_button_rect, border_radius=10)
    draw_text(screen, "Oyun Tasarla", 32, editor_button_rect.centerx, editor_button_rect.centery, TEXT_COLOR)
    return editor_button_rect

def draw_game_info_screen(screen, game, mesh_bg, mouse_pos, bg_surface: pygame.Surface | None = None):
    """Draws the selected game's information screen with a Start button."""
    if bg_surface:
        scaled = pygame.transform.scale(bg_surface, (SCREEN_WIDTH, SCREEN_HEIGHT))
        screen.blit(scaled, (0, 0))
    else:
        screen.fill(CAROUSEL_BG_COLOR)
        mesh_bg.update()
        mesh_bg.draw(screen)

    title = getattr(game, 'name', 'Seçilen Oyun')
    description = getattr(game, 'description', '') or "Bu oyunun kuralları: Doğru nesneleri yakalayarak puan kazan. Yanlışları kaçır. Seviye hedefini tamamla."

    # Başlık
    draw_text(screen, title, 64, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.18, TEXT_COLOR)

    # Açıklama/kural metni (sarılmış)
    content_width = int(SCREEN_WIDTH * 0.7)
    draw_text(screen, description, 28, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.38, TEXT_COLOR, wrap_width=content_width)

    # Başla butonu
    btn_width, btn_height = 260, 64
    start_button_rect = pygame.Rect((SCREEN_WIDTH - btn_width) // 2, int(SCREEN_HEIGHT * 0.72), btn_width, btn_height)
    is_hovered = start_button_rect.collidepoint(mouse_pos)
    button_color = LIGHT_GREEN if is_hovered else GREEN
    pygame.draw.rect(screen, button_color, start_button_rect, border_radius=12)
    draw_text(screen, "Başla", 36, start_button_rect.centerx, start_button_rect.centery, WHITE)

    return start_button_rect

def draw_playing_screen(screen, game_state, level_manager, ui_manager, effect_manager, level_bgs, bg_surface: pygame.Surface | None = None):
    """Draw the main game screen"""
    # Draw background
    # Prefer provided background surface, else fallback to defaults list
    if bg_surface:
        screen.blit(pygame.transform.scale(bg_surface, (SCREEN_WIDTH, SCREEN_HEIGHT)), (0, 0))
    else:
        bg_index = min(level_manager.level - 1, len(level_bgs) - 1)
        screen.blit(level_bgs[bg_index], (0, 0))
    
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
