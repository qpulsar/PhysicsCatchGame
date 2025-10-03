import pygame
import sys
import subprocess
import os
import settings
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
    def __init__(self, screen, force_game_id: int | None = None, start_state: str | None = None):
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
        # Level oynanış ekranı için tasarım katmanı (widget overlay)
        self.level_overlay_data = None
        self.level_overlay_buttons = []  # list of {rect, action, text}
        # Tasarım kaynaklı sesler
        self.sfx_correct = None
        self.sfx_wrong = None
        # Designed level-info screen state
        self.level_info_data = None  # parsed JSON from editor
        self.level_info_buttons = []  # list of {rect, action, text}
        # Opening screen state (from editor)
        self.opening_data = None
        self.opening_buttons = []

        # Game Selection Screen
        self.mesh_bg = MeshBackground(SCREEN_WIDTH, SCREEN_HEIGHT, particle_color=LIGHT_GRAY, line_color=TEAL)
        self.games = self.db.get_games()
        self.carousel = Carousel(self.games, self.font) if self.games else None

        # Başlangıç durumu: dışarıdan bir oyun ID'si verilirse doğrudan bilgi ekranına geç
        self.selected_game_id = None
        self.selected_game = None
        if force_game_id:
            self.selected_game_id = force_game_id
            self.selected_game = next((g for g in self.games if getattr(g, 'id', None) == force_game_id), None)
            # Per-game background
            try:
                settings = self.db.get_game_settings(force_game_id)
                bg_path = settings.get('start_background_path')
                if bg_path and os.path.exists(bg_path):
                    self.per_game_bg_surface = pygame.image.load(bg_path).convert()
            except Exception:
                self.per_game_bg_surface = None
            # Eğer başlangıç durumu verilmemişse ve editörde 'opening' tanımlıysa önce onu göster
            if start_state:
                self.current_state = start_state
            else:
                try:
                    opening = self.db.get_screen(force_game_id, 'opening')
                except Exception:
                    opening = None
                if opening and isinstance(opening, dict):
                    self.opening_data = opening
                    self._prepare_opening_widgets()
                    self.current_state = 'opening'
                else:
                    self.current_state = 'game_info'
        else:
            self.current_state = 'game_selection' if self.carousel else 'no_games'
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

    def _prepare_overlay_widgets(self):
        """Oynanış overlay'i (tasarım) için buton bölgelerini hazırlar.

        Editor ekranında 'button' tipli widget'lardan Rect ve action çıkarır.
        """
        self.level_overlay_buttons = []
        data = self.level_overlay_data or {}
        widgets = data.get('widgets') or []
        for w in widgets:
            try:
                if w.get('type') == 'button':
                    x = int(w.get('x', 0)); y = int(w.get('y', 0))
                    fw = int(((w.get('sprite') or {}).get('frame') or {}).get('width', 200))
                    fh = int(((w.get('sprite') or {}).get('frame') or {}).get('height', 54))
                    rect = pygame.Rect(x, y, max(1, fw), max(1, fh))
                    action = str(w.get('action') or 'none')
                    text = str(((w.get('text_overlay') or {}).get('text')) or w.get('text') or '')
                    self.level_overlay_buttons.append({'rect': rect, 'action': action, 'text': text})
            except Exception:
                continue

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
                    # Seçim sonrası: eğer editörde 'opening' tanımlıysa doğrudan açılış ekranına geç
                    try:
                        opening = self.db.get_screen(self.selected_game_id, 'opening')
                    except Exception:
                        opening = None
                    if opening and isinstance(opening, dict):
                        self.opening_data = opening
                        self._prepare_opening_widgets()
                        self.current_state = 'opening'
                    else:
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
        if self.current_state == 'opening':
            # Opening ekranındaki butonlara tıkla
            for b in self.opening_buttons:
                if b['rect'].collidepoint(pos):
                    act = b.get('action')
                    if act in ('start_game', 'continue'):
                        # opening sonrası akış: level info varsa gösterilecek, yoksa oynanış
                        try:
                            info = self.db.get_screen(self.selected_game_id, 'level_1_info')
                        except Exception:
                            info = None
                        if info and isinstance(info, dict):
                            self.level_info_data = info
                            self._prepare_level_info_widgets()
                            self.current_state = 'level_info'
                        else:
                            self._start_playing(self.selected_game_id)
                    elif act == 'back':
                        self.current_state = 'game_selection'
                    break
        elif self.current_state == 'game_info':
            if self.start_button_rect and self.start_button_rect.collidepoint(pos):
                self.start_game(self.selected_game_id)
        elif self.current_state == 'level_info':
            # Tasarlanan bilgi ekranındaki butonlara tıkla
            for b in self.level_info_buttons:
                if b['rect'].collidepoint(pos):
                    act = b.get('action')
                    if act == 'continue_level':
                        self._start_playing(self.selected_game_id)
                    elif act == 'back':
                        self.current_state = 'game_selection'
                    elif act == 'start_game':
                        self._start_playing(self.selected_game_id)
                    break
        elif self.current_state == 'playing':
            if self.game_state.help_button_rect.collidepoint(pos):
                self.game_state.help_mode = not self.game_state.help_mode
            # Overlay buton aksiyonları
            try:
                for b in self.level_overlay_buttons:
                    if b['rect'].collidepoint(pos):
                        act = b.get('action')
                        if act == 'toggle_help':
                            self.game_state.help_mode = not self.game_state.help_mode
                        elif act == 'back':
                            self.current_state = 'game_selection'
                        elif act == 'continue' or act == 'resume':
                            # Şimdilik no-op; ileride pause desteği eklenebilir
                            pass
                        elif act == 'start_game':
                            # Zaten oyun içindeyiz; no-op
                            pass
                        break
            except Exception:
                pass
        elif self.current_state in ['game_over', 'level_up']:
            if self.current_state == 'game_over':
                self.current_state = 'game_selection'
            else:
                self.current_state = 'playing'

    def _draw_wrapped_topleft(self, surface, text: str, font_size: int, x: int, y: int, color, wrap_width: int | None = None):
        """Sol-üst (tkinter NW) anchora göre çok satırlı metin çizer.

        - '\n' satır sonlarını korur.
        - wrap_width verilirse kelime bazlı sarma uygular.
        """
        font = pygame.font.Font(None, max(12, int(font_size)))
        lines: list[str] = []
        raw_lines = str(text or "").split("\n")
        for raw in raw_lines:
            if wrap_width and wrap_width > 20:
                words = raw.split(' ')
                current = ""
                for w in words:
                    test = (current + w + " ").strip()
                    if font.size(test)[0] <= wrap_width:
                        current = test
                    else:
                        if current:
                            lines.append(current)
                        current = w
                lines.append(current)
            else:
                lines.append(raw)
        line_h = font.get_linesize()
        cy = y
        for ln in lines:
            if not ln:
                cy += line_h
                continue
            surf = font.render(ln, True, color)
            surface.blit(surf, (x, cy))
            cy += line_h
    
    def start_game(self, game_id):
        """Oyunu başlatır; sırayla açılış ve seviye bilgi ekranlarını uygular.

        Akış:
        - Eğer `screens` tablosunda 'opening' varsa önce 'opening' durumunda gösterilir.
        - Sonrasında `level_1_info` tasarımı varsa 'level_info' durumu gösterilir.
        - Aksi halde doğrudan oynanışa geçilir.
        """
        self.selected_game_id = game_id
        self.game_state.reset()
        # Açılış ekranını kontrol et
        try:
            opening = self.db.get_screen(game_id, 'opening')
        except Exception:
            opening = None
        if opening and isinstance(opening, dict):
            self.opening_data = opening
            self._prepare_opening_widgets()
            self.current_state = 'opening'
            return
        # Bilgi ekranını kontrol et
        try:
            info = self.db.get_screen(game_id, 'level_1_info')
        except Exception:
            info = None
        if info and isinstance(info, dict):
            self.level_info_data = info
            self._prepare_level_info_widgets()
            self.current_state = 'level_info'
            return
        # Aksi halde doğrudan oynanışa geç
        self._start_playing(game_id)

    def _start_playing(self, game_id):
        """Editördeki ayarları uygulayarak oyunu ve Level 1'i başlatır."""
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

    def _apply_overlay_background(self):
        """Overlay tasarımındaki arkaplan görselini oynanış arkaplanı olarak uygular.

        Tasarım ekranında belirtilen `background.image` yolu mevcutsa `self.level_bg_surface`
        buna göre set edilir. Böylece level ekranı tasarımdaki arkaplanla başlar.
        """
        data = self.level_overlay_data or {}
        bg_rel = ((data.get('background') or {}).get('image')) or ''
        if bg_rel and os.path.exists(bg_rel):
            try:
                img = pygame.image.load(bg_rel).convert()
                self.level_bg_surface = img
            except Exception:
                pass

    def _apply_overlay_paddle(self):
        """Overlay widget'larından paddle için sprite türetir (opsiyonel).

        Editörde bir widget 'sprite' olup rolü/ismi paddle ise, ilgili sheet bölgesi ya da
        doğrudan görselden `self.paddle_surface` üretilir.
        Desteklenen ipuçları: widget'ta `role=='paddle'` veya `name=='paddle'` ya da `action=='paddle'`.
        """
        data = self.level_overlay_data or {}
        widgets = data.get('widgets') or []
        target = None
        for w in widgets:
            try:
                if w.get('type') in ('sprite', 'image'):
                    tag = (w.get('role') or w.get('name') or w.get('action') or '').lower()
                    if tag == 'paddle' or 'paddle' in str(tag):
                        target = w
                        break
            except Exception:
                continue
        if not target:
            return
        spr = target.get('sprite') or {}
        # Öncelik: sprite sheet + frame -> doğrudan image path
        try:
            sprite_id = spr.get('sprite_id')
            frame = (target.get('frame') or spr.get('frame') or spr.get('region') or {})
            fx = int(spr.get('x', spr.get('left', 0)))
            fy = int(spr.get('y', spr.get('top', 0)))
            fw_val = spr.get('width', spr.get('w', 0))
            fh_val = spr.get('height', spr.get('h', 0))
            if frame:
                fx = int(frame.get('x', frame.get('left', fx)))
                fy = int(frame.get('y', frame.get('top', fy)))
                fw_val = frame.get('width', frame.get('w', fw_val))
                fh_val = frame.get('height', frame.get('h', fh_val))
            fw_i = int(fw_val); fh_i = int(fh_val)
            if sprite_id is not None and fw_i > 0 and fh_i > 0:
                sheet_path = self.db.get_sprite_path(int(sprite_id))
                if sheet_path and os.path.exists(sheet_path):
                    sheet_img = pygame.image.load(sheet_path).convert_alpha()
                    rect = pygame.Rect(fx, fy, fw_i, fh_i)
                    rect = rect.clip(pygame.Rect(0, 0, sheet_img.get_width(), sheet_img.get_height()))
                    sub = sheet_img.subsurface(rect).copy()
                    self.paddle_surface = sub
                    return
        except Exception:
            pass
        # Doğrudan image
        try:
            img_path = str(spr.get('image') or target.get('image') or '')
            if img_path and os.path.exists(img_path):
                img = pygame.image.load(img_path).convert_alpha()
                frame = (target.get('frame') or spr.get('frame') or spr.get('region') or {})
                if frame:
                    fx = int(frame.get('x', frame.get('left', 0)))
                    fy = int(frame.get('y', frame.get('top', 0)))
                    fw = int(frame.get('width', frame.get('w', img.get_width())))
                    fh = int(frame.get('height', frame.get('h', img.get_height())))
                    src_rect = pygame.Rect(fx, fy, fw, fh)
                    src_rect = src_rect.clip(pygame.Rect(0, 0, img.get_width(), img.get_height()))
                    self.paddle_surface = img.subsurface(src_rect).copy()
                else:
                    self.paddle_surface = img
        except Exception:
            pass

    def _apply_overlay_settings(self):
        """Overlay tasarımındaki genel ayarları uygular.

        Desteklenen anahtarlar (TR ve EN):
        - HUD Sprite: yol -> UI help düğmesi
        - Yardım Alanı / help_area: 'top-right' | 'top-left'
        - Doğru SFX / sfx_correct, Yanlış SFX / sfx_wrong: ses dosya yolları
        """
        data = self.level_overlay_data or {}
        settings_map = data.get('settings') or {}
        # HUD sprite
        hud_path = (
            settings_map.get('HUD Sprite')
            or settings_map.get('hud_sprite')
            or settings_map.get('hud')
        )
        try:
            if hud_path:
                self.ui_manager.set_help_button(hud_path)
        except Exception:
            pass
        # Help area
        help_area = (
            settings_map.get('Yardım Alanı')
            or settings_map.get('help_area')
            or settings_map.get('help')
        )
        try:
            if isinstance(help_area, str) and help_area:
                self.ui_manager.help_area = help_area
        except Exception:
            pass
        # SFX load
        corr = settings_map.get('Doğru SFX') or settings_map.get('sfx_correct')
        wrong = settings_map.get('Yanlış SFX') or settings_map.get('sfx_wrong')
        try:
            if corr and os.path.exists(corr):
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                self.sfx_correct = pygame.mixer.Sound(corr)
        except Exception:
            self.sfx_correct = None
        try:
            if wrong and os.path.exists(wrong):
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                self.sfx_wrong = pygame.mixer.Sound(wrong)
        except Exception:
            self.sfx_wrong = None
        # Paddle length (Sepet Uzunluğu)
        try:
            paddle_len = settings_map.get('Sepet Uzunluğu') or settings_map.get('paddle_length')
            if paddle_len:
                settings.PLAYER_WIDTH = int(paddle_len)
        except Exception:
            pass
        # Paddle sprite from settings
        try:
            paddle_path = settings_map.get('Sepet Sprite') or settings_map.get('paddle_sprite')
            if paddle_path and os.path.exists(paddle_path):
                img = pygame.image.load(paddle_path).convert_alpha()
                self.paddle_surface = img
        except Exception:
            pass
        # Music override from overlay
        try:
            music_path = settings_map.get('Müzik') or settings_map.get('music')
            if music_path and os.path.exists(music_path):
                if not pygame.mixer.get_init():
                    pygame.mixer.init()
                pygame.mixer.music.load(music_path)
                pygame.mixer.music.set_volume(0.5)
                pygame.mixer.music.play(-1)
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

        # Level oynanış ekranı için tasarım overlay'ini yükle (opsiyonel)
        # Olası isimler: level_1_screen, level_1_play, level_1, playing
        self.level_overlay_data = None
        try:
            candidate_names = [
                f"level_{self.level_manager.level}_screen",
                f"level_{self.level_manager.level}_play",
                f"level_{self.level_manager.level}",
                "playing",
            ]
            for name in candidate_names:
                data = self.db.get_screen(game_id, name)
                if data and isinstance(data, dict):
                    self.level_overlay_data = data
                    break
        except Exception:
            self.level_overlay_data = None
        # Overlay butonlarını hazırla
        try:
            self._prepare_overlay_widgets()
        except Exception:
            self.level_overlay_buttons = []
        # Overlay'deki arkaplanı level oynanışına uygula (varsa)
        try:
            self._apply_overlay_background()
        except Exception:
            pass
        # Overlay'den paddle sprite'ı türet (opsiyonel)
        try:
            self._apply_overlay_paddle()
        except Exception:
            pass
        # Overlay genel ayarlarını uygula (HUD sprite, help area, SFX)
        try:
            self._apply_overlay_settings()
        except Exception:
            pass

    def _prepare_level_info_widgets(self):
        """Editor JSON'undan buton bölgelerini ve aksiyonlarını çıkarır."""
        self.level_info_buttons = []
        data = self.level_info_data or {}
        widgets = data.get('widgets') or []
        for w in widgets:
            try:
                if w.get('type') == 'button':
                    x = int(w.get('x', 0)); y = int(w.get('y', 0))
                    # ölçüler sprite.frame ya da varsayılan üzerinden
                    fw = int(((w.get('sprite') or {}).get('frame') or {}).get('width', 180))
                    fh = int(((w.get('sprite') or {}).get('frame') or {}).get('height', 48))
                    rect = pygame.Rect(x, y, max(1, fw), max(1, fh))
                    action = str(w.get('action') or 'start_game')
                    text = str(((w.get('text_overlay') or {}).get('text')) or 'Buton')
                    self.level_info_buttons.append({'rect': rect, 'action': action, 'text': text})
            except Exception:
                continue

    def _prepare_opening_widgets(self):
        """Opening ekranı için buton bölgelerini ve aksiyonlarını hazırlar."""
        self.opening_buttons = []
        data = self.opening_data or {}
        widgets = data.get('widgets') or []
        for w in widgets:
            try:
                if w.get('type') == 'button':
                    x = int(w.get('x', 0)); y = int(w.get('y', 0))
                    fw = int(((w.get('sprite') or {}).get('frame') or {}).get('width', 200))
                    fh = int(((w.get('sprite') or {}).get('frame') or {}).get('height', 54))
                    rect = pygame.Rect(x, y, max(1, fw), max(1, fh))
                    action = str(w.get('action') or 'start_game')
                    text = str(((w.get('text_overlay') or {}).get('text')) or 'Başla')
                    self.opening_buttons.append({'rect': rect, 'action': action, 'text': text})
            except Exception:
                continue

    def _render_designed_screen(self, data: dict | None, bg_surface: pygame.Surface | None = None, draw_background: bool = True):
        """Editor ile tasarlanan ekranları (opening/level_info vb.) ortak biçimde çizer.

        Davranış:
        - Arkaplan önceliği (draw_background True ise): data.background.image -> bg_surface -> mesh arkaplan.
        - Widget türleri: label, sprite/image, button.
        - Label ve Button metinleri üst katmanda, hafif gölgeli çizilir.

        Args:
            data: Ekran JSON verisi (editor "screens" tablosundan).
            bg_surface: Varsa oyun/level özel arkaplan yüzeyi.
            draw_background: False ise sadece widget'ları çizer (oynanış üstü overlay).
        """
        data = data or {}
        # Arkaplan
        if draw_background:
            try:
                bg_rel = ((data.get('background') or {}).get('image')) or ''
                if bg_rel and os.path.exists(bg_rel):
                    bg_img = pygame.image.load(bg_rel)
                    self.screen.blit(pygame.transform.scale(bg_img, (SCREEN_WIDTH, SCREEN_HEIGHT)), (0, 0))
                elif bg_surface:
                    self.screen.blit(pygame.transform.scale(bg_surface, (SCREEN_WIDTH, SCREEN_HEIGHT)), (0, 0))
                else:
                    self.screen.fill((24, 28, 40))
                    self.mesh_bg.update(); self.mesh_bg.draw(self.screen)
            except Exception:
                self.screen.fill((24, 28, 40))
                self.mesh_bg.update(); self.mesh_bg.draw(self.screen)

        # Widget'lar
        widgets = data.get('widgets') or []
        deferred_texts: list[tuple[str, int, pygame.Color, int, int]] = []
        for w in widgets:
            try:
                wtype = w.get('type')
                if wtype == 'label':
                    txt = str(w.get('text') or '')
                    color = WHITE
                    try:
                        color = pygame.Color(w.get('color') or '#FFFFFF')
                    except Exception:
                        color = WHITE
                    x = int(w.get('x', 0)); y = int(w.get('y', 0))
                    fsz = int(((w.get('font') or {}).get('size')) or 22)
                    wrap_w = max(50, SCREEN_WIDTH - x - 40)
                    self._draw_wrapped_topleft(self.screen, txt, int(fsz*1.2), x, y, color, wrap_w)
                elif wtype in ('sprite', 'image'):
                    x = int(w.get('x', 0)); y = int(w.get('y', 0))
                    spr = w.get('sprite') or {}
                    drew = False
                    # sprite sheet + frame
                    try:
                        sprite_id = spr.get('sprite_id')
                        frame = (w.get('frame') or spr.get('frame') or spr.get('region') or {})
                        fx = int(spr.get('x', spr.get('left', 0)))
                        fy = int(spr.get('y', spr.get('top', 0)))
                        fw_val = spr.get('width', spr.get('w', 1))
                        fh_val = spr.get('height', spr.get('h', 1))
                        if frame:
                            fx = int(frame.get('x', frame.get('left', fx)))
                            fy = int(frame.get('y', frame.get('top', fy)))
                            fw_val = frame.get('width', frame.get('w', fw_val))
                            fh_val = frame.get('height', frame.get('h', fh_val))
                        fw_i = int(fw_val); fh_i = int(fh_val)
                        if sprite_id is not None and fw_i > 0 and fh_i > 0:
                            sheet_path = self.db.get_sprite_path(int(sprite_id))
                            if sheet_path and os.path.exists(sheet_path):
                                sheet_img = pygame.image.load(sheet_path).convert_alpha()
                                rect = pygame.Rect(fx, fy, fw_i, fh_i)
                                rect = rect.clip(pygame.Rect(0, 0, sheet_img.get_width(), sheet_img.get_height()))
                                sub = sheet_img.subsurface(rect).copy()
                                self.screen.blit(sub, (x, y))
                                drew = True
                    except Exception:
                        drew = False
                    if not drew:
                        try:
                            img_path = str(spr.get('image') or w.get('image') or '')
                            if img_path and os.path.exists(img_path):
                                img = pygame.image.load(img_path).convert_alpha()
                                frame = (w.get('frame') or spr.get('frame') or spr.get('region') or {})
                                fx = int(spr.get('x', spr.get('left', 0)))
                                fy = int(spr.get('y', spr.get('top', 0)))
                                fw_val = spr.get('width', spr.get('w', img.get_width()))
                                fh_val = spr.get('height', spr.get('h', img.get_height()))
                                if frame:
                                    fx = int(frame.get('x', frame.get('left', fx)))
                                    fy = int(frame.get('y', frame.get('top', fy)))
                                    fw_val = frame.get('width', frame.get('w', fw_val))
                                    fh_val = frame.get('height', frame.get('h', fh_val))
                                if fw_val and fh_val:
                                    src_rect = pygame.Rect(int(fx), int(fy), int(fw_val), int(fh_val))
                                    src_rect = src_rect.clip(pygame.Rect(0, 0, img.get_width(), img.get_height()))
                                    sub = img.subsurface(src_rect).copy()
                                    self.screen.blit(sub, (x, y))
                                else:
                                    self.screen.blit(img, (x, y))
                                drew = True
                        except Exception:
                            pass
                    if not drew:
                        fw = int(((spr.get('frame') or w.get('frame') or spr).get('width', 120)))
                        fh = int(((spr.get('frame') or w.get('frame') or spr).get('height', 80)))
                        pygame.draw.rect(self.screen, (120,120,160), pygame.Rect(x, y, max(1, fw), max(1, fh)), border_radius=8)
                        pygame.draw.rect(self.screen, (80,80,120), pygame.Rect(x, y, max(1, fw), max(1, fh)), width=2, border_radius=8)
                elif wtype == 'button':
                    x = int(w.get('x', 0)); y = int(w.get('y', 0))
                    spr = w.get('sprite') or {}
                    frame = (w.get('frame') or spr.get('frame') or spr.get('region') or {})
                    fx = int(spr.get('x', spr.get('left', 0)))
                    fy = int(spr.get('y', spr.get('top', 0)))
                    fw = int(spr.get('width', spr.get('w', 200)))
                    fh = int(spr.get('height', spr.get('h', 54)))
                    if frame:
                        fx = int(frame.get('x', frame.get('left', fx)))
                        fy = int(frame.get('y', frame.get('top', fy)))
                        fw = int(frame.get('width', frame.get('w', fw)))
                        fh = int(frame.get('height', frame.get('h', fh)))
                    rect = pygame.Rect(x, y, max(1, fw), max(1, fh))
                    drawn = False
                    try:
                        sprite_id = spr.get('sprite_id')
                        if sprite_id is not None and fw > 0 and fh > 0:
                            sheet_path = self.db.get_sprite_path(int(sprite_id))
                            if sheet_path and os.path.exists(sheet_path):
                                sheet_img = pygame.image.load(sheet_path).convert_alpha()
                                src_rect = pygame.Rect(fx, fy, fw, fh)
                                src_rect = src_rect.clip(pygame.Rect(0, 0, sheet_img.get_width(), sheet_img.get_height()))
                                btn_img = sheet_img.subsurface(src_rect).copy()
                                self.screen.blit(btn_img, (x, y))
                                drawn = True
                    except Exception:
                        drawn = False
                    if not drawn:
                        try:
                            img_path = str(spr.get('image') or '')
                            if img_path and os.path.exists(img_path):
                                img = pygame.image.load(img_path).convert_alpha()
                                if fw and fh:
                                    src_rect = pygame.Rect(fx, fy, fw, fh)
                                    src_rect = src_rect.clip(pygame.Rect(0, 0, img.get_width(), img.get_height()))
                                    btn_img = img.subsurface(src_rect).copy()
                                    self.screen.blit(btn_img, (x, y))
                                    rect = pygame.Rect(x, y, fw, fh)
                                else:
                                    self.screen.blit(img, (x, y))
                                    fw, fh = img.get_width(), img.get_height()
                                    rect = pygame.Rect(x, y, fw, fh)
                                drawn = True
                        except Exception:
                            pass
                    if not drawn:
                        pygame.draw.rect(self.screen, (70, 130, 180), rect, border_radius=12)
                        pygame.draw.rect(self.screen, (40, 80, 120), rect, width=2, border_radius=12)
                    # Metin overlay (erteleyerek üst katmanda)
                    txt_cfg = (w.get('text_overlay') or {})
                    txt = str(txt_cfg.get('text') or w.get('text') or 'Başla')
                    try:
                        txt_color = pygame.Color(txt_cfg.get('color') or '#FFFFFF')
                    except Exception:
                        txt_color = WHITE
                    base_size = int((txt_cfg.get('font') or {}).get('size') or txt_cfg.get('size') or 30)
                    txt_size = int(base_size * 2.0)
                    deferred_texts.append((txt, txt_size, txt_color, rect.centerx, rect.centery))
            except Exception:
                continue

        if deferred_texts:
            from .core.utils import draw_text as _draw_text
            for txt, txt_size, txt_color, cx, cy in deferred_texts:
                try:
                    for dx, dy in ((1,1), (-1,1), (1,-1), (-1,-1)):
                        _draw_text(self.screen, txt, txt_size, cx+dx, cy+dy, (0,0,0))
                except Exception:
                    pass
                _draw_text(self.screen, txt, txt_size, cx, cy, txt_color)

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
        elif self.current_state == 'opening':
            self._render_designed_screen(self.opening_data, self.per_game_bg_surface)
        elif self.current_state == 'level_info':
            self._render_designed_screen(self.level_info_data, self.per_game_bg_surface)
        elif self.current_state == 'playing':
            # Önce gerçek oyun (sepet, düşen nesneler, HUD)
            draw_playing_screen(self.screen, self.game_state, self.level_manager, self.ui_manager, self.effect_manager, self.level_bgs, self.level_bg_surface)
            # Ardından tasarım overlay'i (sadece widget'lar), arkaplanı yeniden çizme
            if isinstance(self.level_overlay_data, dict):
                self._render_designed_screen(self.level_overlay_data, None, draw_background=False)
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
                # Tasarımdan gelen doğru SFX
                try:
                    if self.sfx_correct:
                        self.sfx_correct.play()
                except Exception:
                    pass
            else:
                if self.game_state.lose_life(reason="caught_wrong_item"):
                    return 'game_over'
                self.effect_manager.trigger_sad_effect(self.game_state.player.rect.centerx, self.game_state.player.rect.centery)
                # Tasarımdan gelen yanlış SFX
                try:
                    if self.sfx_wrong:
                        self.sfx_wrong.play()
                except Exception:
                    pass
        return None

    def remove_off_screen_items(self):
        for item in list(self.game_state.items):
            if item.rect.top > SCREEN_HEIGHT + 10:
                if item.item_type == self.level_manager.target_category:
                    self.level_manager.level_queue.append(item.text)
                item.kill()
