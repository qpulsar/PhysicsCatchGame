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

    def update(self):
        """Update carousel animation."""
        self.current_x += (self.target_x - self.current_x) * self.anim_speed

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
            
            if scale < 0.51 and i != self.selected_index:
                self.card_rects.append((pygame.Rect(0,0,0,0), i)) # Add placeholder for correct indexing
                continue

            scaled_card = pygame.transform.smoothscale(card, (int(self.card_w * scale), int(self.card_h * scale)))
            rect = scaled_card.get_rect(center=(center_x, int(SCREEN_HEIGHT * 0.42)))
            
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
                self.selected_index = round(-offset / self.card_spacing)
                self.selected_index = max(0, min(len(self.games) - 1, self.selected_index))
                self.target_x = (SCREEN_WIDTH / 2) - (self.selected_index * self.card_spacing)

                # Check for click on the selected card
                if abs(event.pos[0] - self.drag_start_x) < 5: # It's a click, not a drag
                    for rect, index in self.card_rects:
                        if rect.collidepoint(event.pos) and index == self.selected_index:
                            return self.games[self.selected_index].id

        if event.type == pygame.MOUSEMOTION and self.dragging:
            drag_delta = event.pos[0] - self.drag_start_x
            self.current_x = self.drag_start_offset + drag_delta
            self.target_x = self.current_x # Follow the drag

        return None

def _draw_quadratic_curve(surface: pygame.Surface, p0, p1, p2, color, width=2, steps=40):
    """Approximate a quadratic Bezier with line segments and draw it.

    Uses aalines when available for smoothing; falls back to regular lines.
    """
    pts = []
    for i in range(steps + 1):
        t = i / steps
        x = (1-t)*(1-t)*p0[0] + 2*(1-t)*t*p1[0] + t*t*p2[0]
        y = (1-t)*(1-t)*p0[1] + 2*(1-t)*t*p1[1] + t*t*p2[1]
        pts.append((int(x), int(y)))
    try:
        pygame.draw.aalines(surface, color, False, pts)
    except Exception:
        pass
    # Draw a slightly thicker line to make it visible on any background
    pygame.draw.lines(surface, color, False, pts, width)

def _curve_intersects_any(p0, p1, p2, rects: list[pygame.Rect], steps=24) -> bool:
    """Roughly test if quadratic curve passes through any rect by sampling points."""
    for i in range(steps + 1):
        t = i / steps
        x = (1-t)*(1-t)*p0[0] + 2*(1-t)*t*p1[0] + t*t*p2[0]
        y = (1-t)*(1-t)*p0[1] + 2*(1-t)*t*p1[1] + t*t*p2[1]
        pt = (int(x), int(y))
        for r in rects:
            if r.collidepoint(pt):
                return True
    return False

def draw_game_selection_screen(screen, carousel, mesh_bg, mouse_pos):
    """Draws the game selection carousel and handles the 'no games' state."""
    screen.fill(CAROUSEL_BG_COLOR)
    mesh_bg.update()
    mesh_bg.draw(screen)
    
    if carousel:
        draw_text(screen, "Bir Oyun Seç", 56, SCREEN_WIDTH / 2, SCREEN_HEIGHT * 0.14, TEXT_COLOR)
        carousel.update()
        carousel.draw(screen)
        # Seçili oyunun seviyelerini yatay mindmap gibi listele ve kart ile spline bağla
        try:
            selected_game = carousel.games[carousel.selected_index] if carousel.games else None
            if selected_game:
                levels = Database().get_levels(getattr(selected_game, 'id', 0))
                sel_rect = getattr(carousel, 'selected_rect', None)
                # Anchor: kartın sağ-orta kenarı; yoksa ekran ortası
                if sel_rect:
                    anchor_x = sel_rect.right
                    # Çoklu anchor: seçili kartın üst ve alt kenarlarına eşit aralıklı dağıt
                    x_start = anchor_x + 36
                else:
                    anchor_x = SCREEN_WIDTH // 2
                    anchor_y = int(SCREEN_HEIGHT * 0.46)
                    x_start = anchor_x + 36
                # Yatay dağılım: soldan sağa eşit aralıklı
                L = min(12, len(levels))
                if L > 0:
                    available_w = max(200, SCREEN_WIDTH - x_start - 48)
                    step_x = max(140, available_w // (L + 1))
                    base_y = anchor_y if not sel_rect else (sel_rect.top + sel_rect.height // 2)  # simetri
                    # Alternatif dikey offset dizisi: +/- artan genlik
                    offsets = []
                    amp_seq = [32, 56, 80, 104, 128, 152]
                    i = 0
                    while len(offsets) < L:
                        amp = amp_seq[min(i//2, len(amp_seq)-1)]
                        offsets.append((-amp) if i % 2 == 0 else (+amp))
                        i += 1
                    # Anchor noktaları: üst ve alt kenar boyunca eşit aralıklı X'ler
                    if sel_rect:
                        m = 12
                        avail_w = max(20, sel_rect.width - 2*m)
                        step_ax = avail_w / max(2, (L + 1))
                        top_points = [(int(sel_rect.left + m + (k+1)*step_ax), sel_rect.top) for k in range(L)]
                        bot_points = [(int(sel_rect.left + m + (k+1)*step_ax), sel_rect.bottom) for k in range(L)]
                        # L eleman için sırayla üst-alt seç
                        anchors = [top_points[i] if i % 2 == 0 else bot_points[i] for i in range(L)]
                    else:
                        anchors = [(anchor_x, base_y) for _ in range(L)]
                    # Çarpışmadan kaçınmak için yan thumbnail dikdörtgenlerini topla
                    avoid_rects: list[pygame.Rect] = []
                    try:
                        for r, idx in getattr(carousel, 'card_rects', []):
                            if not isinstance(r, pygame.Rect):
                                continue
                            if sel_rect and r.colliderect(sel_rect):
                                continue
                            # Biraz şişir (tam temas olmasın)
                            avoid_rects.append(r.inflate(8, 8))
                    except Exception:
                        avoid_rects = []
                    # Düğümleri çiz
                    for idx in range(L):
                        lv = levels[idx]
                        x = x_start + (idx + 1) * step_x
                        y = base_y + offsets[idx]
                        # Level numarasını gösterme; yalnızca isim
                        label = f"{lv.get('level_name')}"
                        # Bağlantı eğrisi: anchor -> kontrol -> (x-14,y)
                        end_pt = (x - 18, y)
                        a_x, a_y = anchors[idx]
                        ctrl = [int((a_x + end_pt[0]) / 2), int((a_y + y) / 2) + (12 if offsets[idx] >= 0 else -12)]
                        # Yan thumbnail'lere değmeyi önlemek için kontrol noktasını ayarla
                        tries = 0
                        while _curve_intersects_any((a_x, a_y), tuple(ctrl), end_pt, avoid_rects) and tries < 8:
                            ctrl[1] += 32 if offsets[idx] >= 0 else -32
                            tries += 1
                        # Anchor noktasına küçük düğüm çiz
                        pygame.draw.circle(screen, TEXT_COLOR, (a_x, a_y), 3)
                        _draw_quadratic_curve(screen, (a_x, a_y), tuple(ctrl), end_pt, TEXT_COLOR, width=3, steps=40)
                        pygame.draw.circle(screen, TEXT_COLOR, end_pt, 3)
                        # Metni hafif sola hizalı çiz; daha geniş wrap
                        draw_text(screen, label, 24, x + 6, y, TEXT_COLOR, wrap_width=220)
        except Exception:
            pass
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
