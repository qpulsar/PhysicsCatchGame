import pygame
import json
from settings import *
from ..core.utils import draw_text, get_resource_path, draw_spline
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
    def __init__(self, db_path=None):
        if db_path is None:
            # Bundled veya normal çalışmada veritabanını bul
            db_path = get_resource_path('game_data.db')
        
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
        self.card_spacing = self.card_w + 120  # Increased gap significantly to prevent branch overlap
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
        
        # Animation state for sub-levels
        self.anim_progress = 1.0
        self.prev_selected_index = -1

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
            thumbnail_path = assets_thumb if assets_thumb and os.path.exists(assets_thumb) else get_resource_path(f"assets/images/{game.id}.png")
            # Fallback to checking assets/games/ID/thumbnail.png or similar if needed, but per-game asset is usually handled by settings.
            # If standard location is desired:
            if not os.path.exists(thumbnail_path):
                 thumbnail_path = get_resource_path(f"img/thumbnails/{game.id}.png")
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
        return self.get_card_rect(self.selected_index)

    def get_card_rect(self, index: int) -> pygame.Rect:
        """Calculates the rect for a given card index based on current_x."""
        center_x = self.current_x + index * self.card_spacing
        
        dist = abs(center_x - SCREEN_WIDTH / 2)
        scale = max(0.5, 1.0 - (dist / (SCREEN_WIDTH * 0.75)) * 0.5)
        
        w = int(self.card_w * scale)
        h = int(self.card_h * scale)
        
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
            
        # Alt bölüm (tree) animasyonu
        if self.anim_progress < 1.0:
            self.anim_progress = min(1.0, self.anim_progress + 0.04)

    def draw(self, surface: pygame.Surface):
        """Draw the carousel on the given surface."""
        self.card_rects.clear()
        
        # Draw cards from back to front
        sorted_indices = sorted(range(len(self.cards)), key=lambda i: abs(i - self.selected_index), reverse=True)

        for i in sorted_indices:
            card = self.cards[i]
            center_x = self.current_x + i * self.card_spacing
            
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
                old_index = self.selected_index
                if event.key == pygame.K_RIGHT and self.selected_index < len(self.games) - 1:
                    self.selected_index += 1
                    moved = True
                elif event.key == pygame.K_LEFT and self.selected_index > 0:
                    self.selected_index -= 1
                    moved = True
                
                if moved:
                    self.prev_selected_index = old_index
                    self.anim_progress = 0.0
                    self.target_x = (SCREEN_WIDTH / 2) - (self.selected_index * self.card_spacing)
                    self.last_key_press_time = current_time

            if event.key == pygame.K_RETURN or event.key == pygame.K_SPACE:
                return self.games[self.selected_index].id

        # Mouse wheel input with cooldown
        if event.type == pygame.MOUSEWHEEL:
            if current_time - self.last_key_press_time > self.key_cooldown:
                moved = False
                old_index = self.selected_index
                if event.y < 0 and self.selected_index < len(self.games) - 1: # Scroll down/right
                    self.selected_index += 1
                    moved = True
                elif event.y > 0 and self.selected_index > 0: # Scroll up/left
                    self.selected_index -= 1
                    moved = True
                
                if moved:
                    self.prev_selected_index = old_index
                    self.anim_progress = 0.0
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
                new_idx = round(-offset / self.card_spacing)
                new_idx = max(0, min(len(self.games) - 1, int(new_idx)))
                
                if new_idx != self.selected_index:
                    self.prev_selected_index = self.selected_index
                    self.selected_index = new_idx
                    self.anim_progress = 0.0
                
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

def _draw_level_tree(screen, center_rect: pygame.Rect, levels: list, progress: float):
    """Draws levels branching out vertically using aesthetic spline curves."""
    if not levels or progress <= 0:
        return

    center_x, center_y = center_rect.center
    
    # Dalların uzunluğu (Optimal seviyeye çekildi)
    radius = 180
    
    # Font
    font = pygame.font.Font(None, 24)

    # Create a dedicated surface for the tree to handle alpha smoothly
    tree_surf = pygame.Surface(screen.get_size(), pygame.SRCALPHA)

    # Gruplama: Çiftler yukarı, Tekler aşağı
    upper_levels = levels[0::2]
    lower_levels = levels[1::2]
    
    def draw_branch(surf, level, angle_deg, p):
        rad = math.radians(angle_deg)
        start_pos = (center_x, center_y)
        
        end_x = center_x + radius * math.cos(rad)
        end_y = center_y + radius * math.sin(rad)
        end_pos = (end_x, end_y)
        
        # Spline Rengi
        alpha = int(255 * p)
        line_color = (200, 200, 255, alpha)
        glow_color = (150, 150, 255, int(alpha * 0.4))
        
        # Glow (daha geniş, daha şeffaf spline)
        draw_spline(surf, start_pos, end_pos, p, glow_color, 7)
        # Ana Spline
        tip_pos = draw_spline(surf, start_pos, end_pos, p, line_color, 3)
        
        # Uç nokta
        if p > 0.7:
            node_p = (p - 0.7) / 0.3
            node_alpha = int(255 * node_p)
            
            # Pulse efekti (zaman bazlı)
            pulse = (math.sin(pygame.time.get_ticks() * 0.005) + 1) * 0.5
            pulse_radius = 8 + pulse * 5  # Düğümler biraz daha büyük ve belirgin
            
            # Dış ışıma
            pygame.draw.circle(surf, (100, 100, 255, int(60 * node_p)), (int(tip_pos[0]), int(tip_pos[1])), int(pulse_radius + 5))
            # Ana düğüm
            pygame.draw.circle(surf, (*CARD_SELECTED_COLOR, node_alpha), (int(tip_pos[0]), int(tip_pos[1])), 8)
            pygame.draw.circle(surf, (255, 255, 255, node_alpha), (int(tip_pos[0]), int(tip_pos[1])), 4)
            
            # Metin
            level_name = level.get('level_name', str(level.get('level_number')))
            text_surf = font.render(level_name, True, TEXT_COLOR)
            text_surf.set_alpha(node_alpha)
            
            t_offset = 34  # Yazı mesafesini biraz daha açtık
            tx = tip_pos[0] + t_offset * math.cos(rad)
            ty = tip_pos[1] + t_offset * math.sin(rad)
            text_rect = text_surf.get_rect(center=(tx, ty))
            
            bg_rect = text_rect.inflate(18, 10)
            # Metin arkaplanı (yuvarlatılmış)
            bg_surf = pygame.Surface((bg_rect.width, bg_rect.height), pygame.SRCALPHA)
            pygame.draw.rect(bg_surf, (20, 20, 45, int(220 * node_p)), bg_surf.get_rect(), border_radius=8)
            pygame.draw.rect(bg_surf, (100, 100, 255, int(100 * node_p)), bg_surf.get_rect(), border_radius=8, width=1) # Hafif bir sınır ekledik
            surf.blit(bg_surf, bg_rect.topleft)
            surf.blit(text_surf, text_rect)

    # Yukarıdakiler (Dengeli açı yayılımı)
    if upper_levels:
        count = len(upper_levels)
        angles = [-90] if count == 1 else [(-135 + i * (90 / (count - 1))) for i in range(count)]
        for i, lvl in enumerate(upper_levels):
            draw_branch(tree_surf, lvl, angles[i], progress)

    # Aşağıdakiler (Dengeli açı yayılımı)
    if lower_levels:
        count = len(lower_levels)
        angles = [90] if count == 1 else [(45 + i * (90 / (count - 1))) for i in range(count)]
        for i, lvl in enumerate(lower_levels):
            draw_branch(tree_surf, lvl, angles[i], progress)

    # Ağacı ana ekrana bas
    screen.blit(tree_surf, (0, 0))

def draw_game_selection_screen(screen, carousel, mesh_bg, mouse_pos):
    """Draws the game selection carousel and handles the 'no games' state."""
    # Darker, deep space background
    screen.fill((15, 15, 25)) 
    mesh_bg.update()
    mesh_bg.draw(screen)
    
    if carousel:
        # Title with a subtle glow (multiple draws)
        title = "Bir Macera Seç"
        draw_text(screen, title, 56, SCREEN_WIDTH / 2 + 2, SCREEN_HEIGHT * 0.14 + 2, (0, 0, 0, 100))
        draw_text(screen, title, 56, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.14, (100, 200, 255))
        
        carousel.update()

        # Önce ağaçları arkaya çiz
        try:
            # 1. Eski (kaybolan) oyunun ağacı
            if carousel.anim_progress < 1.0 and carousel.prev_selected_index != -1:
                prev_game = carousel.games[carousel.prev_selected_index]
                prev_rect = carousel.get_card_rect(carousel.prev_selected_index)
                prev_levels = Database().get_levels(getattr(prev_game, 'id', 0))
                _draw_level_tree(screen, prev_rect, prev_levels, 1.0 - carousel.anim_progress)

            # 2. Yeni (aktif) oyunun ağacı
            selected_game = carousel.games[carousel.selected_index] if carousel.games else None
            if selected_game:
                sel_rect = carousel.get_current_selected_rect()
                levels = Database().get_levels(getattr(selected_game, 'id', 0))
                _draw_level_tree(screen, sel_rect, levels, carousel.anim_progress)
        except Exception as e:
            pass
        
        # Şimdi kartları öne çiz
        carousel.draw(screen)
    else:
        draw_text(screen, "Oyun Bulunamadı", 64, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 3, (255, 100, 100))
        draw_text(screen, "Lütfen editör programını kullanarak bir oyun oluşturun.", 28, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2, TEXT_COLOR)
        
    # Design button with modern look
    editor_button_rect = pygame.Rect(SCREEN_WIDTH - 240, SCREEN_HEIGHT - 80, 220, 60)
    is_hovered = editor_button_rect.collidepoint(mouse_pos)
    
    btn_color = (180, 100, 255) if is_hovered else (150, 50, 200)
    pygame.draw.rect(screen, (0, 0, 0, 100), editor_button_rect.move(4, 4), border_radius=15)
    pygame.draw.rect(screen, btn_color, editor_button_rect, border_radius=15)
    pygame.draw.rect(screen, (255, 255, 255, 50), editor_button_rect, width=2, border_radius=15)
    
    draw_text(screen, "Oyun Tasarla", 32, editor_button_rect.centerx, editor_button_rect.centery - 2, WHITE)
    return editor_button_rect

def draw_game_info_screen(screen, game, mesh_bg, mouse_pos, bg_surface: pygame.Surface | None = None):
    """Draws the selected game's information screen with a premium modern look."""
    # Background
    if bg_surface:
        scaled = pygame.transform.scale(bg_surface, (SCREEN_WIDTH, SCREEN_HEIGHT))
        screen.blit(scaled, (0, 0))
        overlay = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT), pygame.SRCALPHA)
        overlay.fill((10, 10, 25, 160)) # Deeper, tinted overlay
        screen.blit(overlay, (0, 0))
    else:
        screen.fill((10, 10, 20))
        mesh_bg.update()
        mesh_bg.draw(screen)

    # Main Panel (Glassmorphism)
    panel_w, panel_h = int(SCREEN_WIDTH * 0.8), int(SCREEN_HEIGHT * 0.7)
    panel_rect = pygame.Rect((SCREEN_WIDTH - panel_w)//2, (SCREEN_HEIGHT - panel_h)//2, panel_w, panel_h)
    
    panel_surf = pygame.Surface((panel_w, panel_h), pygame.SRCALPHA)
    pygame.draw.rect(panel_surf, (255, 255, 255, 20), panel_surf.get_rect(), border_radius=30)
    pygame.draw.rect(panel_surf, (255, 255, 255, 40), panel_surf.get_rect(), width=2, border_radius=30)
    screen.blit(panel_surf, panel_rect.topleft)

    title = getattr(game, 'name', 'Fizik Macerası').upper()
    description = getattr(game, 'description', '') or "Doğru fiziksel büyüklükleri topla, yanlışlardan kaçın ve rekorunu kır!"

    # Title with dual glow
    from .core.utils import draw_text as _draw_text
    _draw_text(screen, title, 80, SCREEN_WIDTH // 2, panel_rect.top + 70, (100, 200, 255))
    _draw_text(screen, title, 80, SCREEN_WIDTH // 2 - 2, panel_rect.top + 68, WHITE)

    # Decorative separator
    sep_w = 400
    pygame.draw.line(screen, (100, 200, 255, 100), (SCREEN_WIDTH//2 - sep_w//2, panel_rect.top + 130), (SCREEN_WIDTH//2 + sep_w//2, panel_rect.top + 130), 2)

    # Description text
    _draw_text(screen, description, 30, SCREEN_WIDTH // 2, panel_rect.top + 200, (220, 220, 250), wrap_width=panel_w - 100)

    # Control hint
    hint_rect = pygame.Rect(SCREEN_WIDTH // 2 - 200, panel_rect.bottom - 180, 400, 60)
    pygame.draw.rect(screen, (0, 0, 0, 100), hint_rect, border_radius=15)
    _draw_text(screen, "Kontrol: Yön Tuşları / Mouse", 22, SCREEN_WIDTH // 2, hint_rect.centery, (150, 180, 255))

    # Start Button
    btn_w, btn_h = 320, 80
    start_button_rect = pygame.Rect((SCREEN_WIDTH - btn_w)//2, panel_rect.bottom - 80, btn_w, btn_h)
    is_hovered = start_button_rect.collidepoint(mouse_pos)
    
    # Button glow
    glow_color = (0, 255, 150, 60) if is_hovered else (0, 200, 100, 30)
    for i in range(8):
        pygame.draw.rect(screen, glow_color, start_button_rect.inflate(i*3, i*3), border_radius=20, width=1)

    btn_color = (0, 255, 150) if is_hovered else (0, 200, 100)
    pygame.draw.rect(screen, btn_color, start_button_rect, border_radius=20)
    pygame.draw.rect(screen, WHITE, start_button_rect, width=3, border_radius=20)
    
    _draw_text(screen, "OYUNU BAŞLAT", 44, start_button_rect.centerx, start_button_rect.centery - 2, (10, 40, 30))

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
