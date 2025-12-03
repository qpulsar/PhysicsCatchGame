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
        # Level oynanÄ±ÅŸ ekranÄ± iÃ§in tasarÄ±m katmanÄ± (widget overlay)
        self.level_overlay_data = None
        self.level_overlay_buttons = []  # list of {rect, action, text}
        # TasarÄ±m kaynaklÄ± sesler
        self.sfx_correct = None
        self.sfx_wrong = None
        # Tasarım kaynaklı sprite-sheet efekt yolları (6x5 grid varsayılan)
        self.effect_sheet_correct_path = None
        self.effect_sheet_wrong_path = None
        # Efekt çalışma zamanı parametreleri
        self.effect_sheet_correct_scale = 1.25
        self.effect_sheet_wrong_scale = 1.25
        self.effect_sheet_fps = 24
        # Designed level-info screen state
        self.level_info_data = None  # parsed JSON from editor
        self.level_info_buttons = []  # list of {rect, action, text}
        # Opening screen state (from editor)
        self.opening_data = None
        self.opening_buttons = []
        # DÃ¼ÅŸen nesneler iÃ§in sprite yÃ¼zeyleri (level_background_regions tabanlÄ±)
        self.item_base_surfaces: list[pygame.Surface] = []

        # Game Selection Screen
        self.mesh_bg = MeshBackground(SCREEN_WIDTH, SCREEN_HEIGHT, particle_color=LIGHT_GRAY, line_color=TEAL)
        self.games = self.db.get_games()
        self.carousel = Carousel(self.games, self.font) if self.games else None

        # BaÅŸlangÄ±Ã§ durumu: dÄ±ÅŸarÄ±dan bir oyun ID'si verilirse doÄŸrudan bilgi ekranÄ±na geÃ§
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
            # EÄŸer baÅŸlangÄ±Ã§ durumu verilmemiÅŸse ve editÃ¶rde 'opening' tanÄ±mlÄ±ysa Ã¶nce onu gÃ¶ster
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
        """Ana oyun dÃ¶ngÃ¼sÃ¼nÃ¼ Ã§alÄ±ÅŸtÄ±rÄ±r."""
        running = True
        while running:
            running = self.handle_events()
            self.update()
            self.draw()
            self.clock.tick(60)
        
        pygame.quit()
        sys.exit()

    def _load_default_backgrounds(self):
        """Yoksa hata vermeyen, esnek varsayÄ±lan arkaplan yÃ¼kleyici.

        Ã–ncelik sÄ±rasÄ±:
        1) img/backgrounds/{2..5}.jpg
        2) assets/images/ iÃ§indeki mevcut jpg/png dosyalarÄ±
        3) DÃ¼z renk yÃ¼zeyler (ayarlanmÄ±ÅŸ paletten)

        Returns:
            list[pygame.Surface]: Ekran boyutunda arkaplan yÃ¼zeyleri listesi
        """
        candidates = []
        # 1) legacy backgrounds
        for i in range(2, 6):
            p = os.path.join('img', 'backgrounds', f'{i}.jpg')
            if os.path.exists(p):
                candidates.append(p)
        # 2) assets/images altÄ±ndan al
        assets_img_dir = os.path.join('assets', 'images')
        if os.path.isdir(assets_img_dir):
            for fn in sorted(os.listdir(assets_img_dir)):
                if fn.lower().endswith(('.jpg', '.jpeg', '.png', '.bmp')):
                    candidates.append(os.path.join(assets_img_dir, fn))
        # GÃ¶rselleri yÃ¼kle
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
        """OynanÄ±ÅŸ overlay'i (tasarÄ±m) iÃ§in buton bÃ¶lgelerini hazÄ±rlar.

        Editor ekranÄ±nda 'button' tipli widget'lardan Rect ve action Ã§Ä±karÄ±r.
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
        """Belirtilen renkte ekran boyutunda yÃ¼zey Ã¼retir."""
        surf = pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT))
        surf.fill(color)
        return surf

    def _abs_project_path(self, rel: str) -> str | None:
        """Proje kÃ¶kÃ¼ne gÃ¶re gÃ¶reli yolu mutlak hale getirir.

        Screen Designer gÃ¶reli yollarÄ± (assets/...) kaydeder. Ã‡alÄ±ÅŸma dizini
        farklÄ± olduÄŸunda dosya bulunamayabilir; bu yardÄ±mcÄ±, oyunun konumuna gÃ¶re
        kÃ¶kten Ã§Ã¶zer.
        """
        try:
            if not rel:
                return None
            p = rel.replace('\\', '/').strip()
            if os.path.isabs(p):
                return p if os.path.exists(p) else None
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
            # Debug yazÄ±larÄ± temizlendi
            cand = os.path.join(project_root, p)
            return cand if os.path.exists(cand) else None
        except Exception:
            return None

    def _resolve_level_id(self, game_id: int, level_number: int) -> int | None:
        """Verilen oyun ve seviye numarasÄ± iÃ§in DB'deki seviye ID'sini dÃ¶ndÃ¼rÃ¼r.

        Editor, ekranlarÄ± genellikle `level_<id>` adÄ±yla kaydediyor. Oyun tarafÄ±nda
        numaradan ID'ye kÃ¶prÃ¼ kurmak iÃ§in bu yardÄ±mcÄ±yÄ± kullanÄ±yoruz.
        """
        try:
            levels = self.db.get_levels(game_id)
            for row in levels:
                # row bir dict: {'id': ..., 'level_number': ..., 'level_name': ...}
                if int(row.get('level_number', 0)) == int(level_number):
                    return int(row.get('id'))
        except Exception:
            return None
        return None

    def handle_events(self):
        """Girdi olaylarÄ±nÄ± iÅŸler ve durum geÃ§iÅŸlerini yÃ¶netir."""
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
                        print(f"EditÃ¶r baÅŸlatÄ±lamadÄ±: {e}")
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
                    # SeÃ§im sonrasÄ±: eÄŸer editÃ¶rde 'opening' tanÄ±mlÄ±ysa doÄŸrudan aÃ§Ä±lÄ±ÅŸ ekranÄ±na geÃ§
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
                        # Yeni seviyeye geçerken önce bilgi ekranını kontrol et
                        if not self._try_switch_to_level_info(self.selected_game_id, self.level_manager.level):
                            # Bilgi ekranı yoksa, yeni seviyenin varlıklarını yükleyerek başlat
                            self._start_playing(self.selected_game_id, self.level_manager.level)
                elif self.current_state == 'game_info' and (event.key == pygame.K_RETURN or event.key == pygame.K_SPACE):
                    self.start_game(self.selected_game_id)
        return True

    def handle_mouse_click(self, pos):
        if self.current_state == 'opening':
            # Opening ekranÄ±ndaki butonlara tÄ±kla
            for b in self.opening_buttons:
                if b['rect'].collidepoint(pos):
                    act = b.get('action')
                    if act in ('start_game', 'continue'):
                        # opening sonrasÄ± akÄ±ÅŸ: level info varsa gÃ¶sterilecek, yoksa oynanÄ±ÅŸ
                        # Screen Designer bazÄ± kurulumlarda seviye ekranlarÄ±nÄ± level_<DB id> adÄ±yla kaydediyor.
                        # Oyunda hem numaraya hem de DB id'ye gÃ¶re isimleri deneyelim.
                        if not self._try_switch_to_level_info(self.selected_game_id, 1):
                            self._start_playing(self.selected_game_id, 1)
                    elif act == 'back':
                        self.current_state = 'game_selection'
                    break
        elif self.current_state == 'game_info':
            if self.start_button_rect and self.start_button_rect.collidepoint(pos):
                self.start_game(self.selected_game_id)
        elif self.current_state == 'level_info':
            # Tasarlanan bilgi ekranÄ±ndaki butonlara tÄ±kla
            for b in self.level_info_buttons:
                if b['rect'].collidepoint(pos):
                    act = b.get('action')
                    if act in ('continue_level', 'continue', 'start_game', 'next_level'):
                        self._start_playing(self.selected_game_id, self.level_manager.level)
                    elif act == 'back':
                        self.current_state = 'game_selection'
                    break
        elif self.current_state == 'playing':
            if self.game_state.help_button_rect.collidepoint(pos):
                self.game_state.help_mode = not self.game_state.help_mode
            # Overlay buton aksiyonlarÄ±
            try:
                for b in self.level_overlay_buttons:
                    if b['rect'].collidepoint(pos):
                        act = b.get('action')
                        if act == 'toggle_help':
                            self.game_state.help_mode = not self.game_state.help_mode
                        elif act == 'back':
                            self.current_state = 'game_selection'
                        elif act == 'continue' or act == 'resume':
                            # Åžimdilik no-op; ileride pause desteÄŸi eklenebilir
                            pass
                        elif act == 'start_game':
                            # Zaten oyun iÃ§indeyiz; no-op
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
        """Sol-Ã¼st (tkinter NW) anchora gÃ¶re Ã§ok satÄ±rlÄ± metin Ã§izer.

        - '\n' satÄ±r sonlarÄ±nÄ± korur.
        - wrap_width verilirse kelime bazlÄ± sarma uygular.
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
    
    def _try_switch_to_level_info(self, game_id: int, level_num: int) -> bool:
        """Belirtilen seviye iÃ§in bilgi ekranÄ± varsa yÃ¼kler ve 'level_info' durumuna geÃ§er.

        Returns:
            bool: Bilgi ekranÄ± bulundu ve geÃ§iÅŸ yapÄ±ldÄ±ysa True, aksi halde False.
        """
        try:
            info = None
            lvl_id = self._resolve_level_id(game_id, level_num)
            candidates = [
                f"level_{level_num}_info",
                f"level_{lvl_id}_info" if lvl_id else None,
            ]
            for name in filter(None, candidates):
                info = self.db.get_screen(game_id, name)
                if info and isinstance(info, dict):
                    break
        except Exception:
            info = None
        
        if info and isinstance(info, dict):
            self.level_info_data = info
            self._prepare_level_info_widgets()
            self.current_state = 'level_info'
            return True
        return False

    def start_game(self, game_id):
        """Oyunu baÅŸlatÄ±r; sÄ±rayla aÃ§Ä±lÄ±ÅŸ ve seviye bilgi ekranlarÄ±nÄ± uygular.

        AkÄ±ÅŸ:
        - EÄŸer `screens` tablosunda 'opening' varsa Ã¶nce 'opening' durumunda gÃ¶sterilir.
        - SonrasÄ±nda `level_1_info` tasarÄ±mÄ± varsa 'level_info' durumu gÃ¶sterilir.
        - Aksi halde doÄŸrudan oynanÄ±ÅŸa geÃ§ilir.
        """
        self.selected_game_id = game_id
        self.game_state.reset()
        # AÃ§Ä±lÄ±ÅŸ ekranÄ±nÄ± kontrol et
        try:
            opening = self.db.get_screen(game_id, 'opening')
        except Exception:
            opening = None
        if opening and isinstance(opening, dict):
            self.opening_data = opening
            self._prepare_opening_widgets()
            self.current_state = 'opening'
            return
        # Bilgi ekranÄ±nÄ± kontrol et
        if self._try_switch_to_level_info(game_id, 1):
            return
        # Aksi halde doÄŸrudan oynanÄ±ÅŸa geÃ§
        self._start_playing(game_id, 1)

    def _start_playing(self, game_id, level_num=1):
        """Editördeki ayarları uygulayarak oyunu ve belirtilen seviyeyi başlatır."""
        try:
            print(f"[SpriteDBG] _start_playing: game_id={game_id} level={level_num}")
        except Exception:
            pass
        
        # Temizlik: Önceki seviyeden kalan tüm sprite'ları temizle
        if self.game_state.player:
            self.game_state.player.kill()
            self.game_state.player = None
        self.game_state.all_sprites.empty()
        self.game_state.items.empty()

        self.level_manager.setup_level(level_num, game_id)

        # Load level-specific background if available
        self.level_bg_surface = None
        try:
            settings_map = self.db.get_game_settings(game_id)
            lvl_key = f"level_{level_num}_background_path"
            lvl_key = f"level_{self.level_manager.level}_background_path"
            bg_path = settings_map.get(lvl_key)
            if bg_path and os.path.exists(bg_path):
                self.level_bg_surface = pygame.image.load(bg_path).convert()
        except Exception:
            self.level_bg_surface = None

        # Ek gÃ¼venlik: Tasarlanan seviye ekranÄ±nÄ±n JSON'undan arkaplanÄ± Ã§ek
        # (overlay bulunmasa bile arkaplan uygula)
        try:
            if self.level_bg_surface is None:
                lvl_num = self.level_manager.level
                lvl_id = self._resolve_level_id(game_id, lvl_num)
                candidates = [
                    f"level_{lvl_num}_screen",
                    f"level_{lvl_num}",
                    (f"level_{lvl_id}_screen" if lvl_id else None),
                    (f"level_{lvl_id}" if lvl_id else None),
                ]
                # debug log kaldÄ±rÄ±ldÄ±
                chosen_data = None
                chosen_name = None
                for name in filter(None, candidates):
                    data = self.db.get_screen(game_id, name)
                    if data and isinstance(data, dict):
                        chosen_data = data
                        chosen_name = name
                        break
                if chosen_data:
                    bg_rel = ((chosen_data.get('background') or {}).get('image')) or ''
                    path = self._abs_project_path(bg_rel) or (bg_rel if os.path.exists(bg_rel) else None)
                    if path:
                        try:
                            img = pygame.image.load(path).convert()
                            self.level_bg_surface = img
                        except Exception:
                            pass
        except Exception:
            pass

        # EARLY: DÃ¼ÅŸen nesneler iÃ§in sprite regionlarÄ±ndan base surface'leri, spawn baÅŸlamadan hazÄ±rlayalÄ±m
        try:
            self.item_base_surfaces = []
            lvl_num = self.level_manager.level
            lvl_id = self._resolve_level_id(game_id, lvl_num)
            print(f"[SpriteDBG] preparing item surfaces (early) for game_id={game_id}, level_num={lvl_num}, level_id={lvl_id}")

            def _early_load_item_surfaces(level_id: int) -> int:
                regions = self.db.get_level_background_regions(level_id)
                print(f"[SpriteDBG] item regions found: {len(regions)} for level_id={level_id}")
                for r in regions:
                    sheet_rel = r.get('sheet_path')
                    x, y, w, h = int(r.get('x', 0)), int(r.get('y', 0)), int(r.get('width', 0)), int(r.get('height', 0))
                    try:
                        sheet_abs = self._abs_project_path(sheet_rel) or (sheet_rel if sheet_rel and os.path.exists(sheet_rel) else None)
                        print(f"[SpriteDBG] region path: rel={sheet_rel} -> abs={sheet_abs}; size=({w}x{h})")
                        if not sheet_abs or w <= 0 or h <= 0:
                            continue
                        img = pygame.image.load(sheet_abs).convert_alpha()
                        rect = pygame.Rect(x, y, w, h).clip(pygame.Rect(0, 0, img.get_width(), img.get_height()))
                        if rect.width <= 0 or rect.height <= 0:
                            continue
                        self.item_base_surfaces.append(img.subsurface(rect).copy())
                    except Exception:
                        continue
                return len(self.item_base_surfaces)

            if lvl_id:
                cnt = _early_load_item_surfaces(lvl_id)
                if cnt == 0:
                    try:
                        levels = self.db.get_levels(game_id)
                        for row in levels:
                            other_id = int(row.get('id'))
                            if other_id == lvl_id:
                                continue
                            prev = len(self.item_base_surfaces)
                            found = _early_load_item_surfaces(other_id)
                            if found > prev:
                                try:
                                    self.level_manager.setup_level(int(row.get('level_number', 1)), game_id)
                                except Exception:
                                    pass
                                break
                    except Exception:
                        pass
            print(f"[SpriteDBG] item base surfaces ready (early): {len(self.item_base_surfaces)}")
            # Ultimate fallback: DB'de bÃ¶lge yoksa, assets/images iÃ§inden direkt gÃ¶rselleri kullan
            if not self.item_base_surfaces:
                try:
                    assets_dir = os.path.join(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')), 'assets', 'images')
                    added = 0
                    if os.path.isdir(assets_dir):
                        for fn in sorted(os.listdir(assets_dir)):
                            if not fn.lower().endswith(('.png', '.jpg', '.jpeg', '.bmp')):
                                continue
                            path = os.path.join(assets_dir, fn)
                            try:
                                img = pygame.image.load(path).convert_alpha()
                                # Basit Ã¶lÃ§ek: ITEM_WIDTH x ITEM_HEIGHT
                                surf = pygame.transform.smoothscale(img, (ITEM_WIDTH, ITEM_HEIGHT))
                                self.item_base_surfaces.append(surf)
                                added += 1
                                if added >= 8:
                                    break
                            except Exception:
                                continue
                    print(f"[SpriteDBG] fallback added surfaces from assets/images: {added}")
                except Exception:
                    pass
        except Exception:
            self.item_base_surfaces = []

        # Load paddle (basket) from the level's screen design
        self.paddle_surface = None
        basket_length = 128 # Default length
        
        # Efekt değişkenlerini varsayılanlarla başlat
        self.effect_correct_data = None
        self.effect_wrong_data = None
        self.effect_sheet_correct_path = None
        self.effect_sheet_wrong_path = None
        self.effect_sheet_correct_cols = 6
        self.effect_sheet_correct_rows = 5
        self.effect_sheet_wrong_cols = 6
        self.effect_sheet_wrong_rows = 5
        self.effect_sheet_fps = 24
        scale_pct = 60 # Default scaling percentage

        try:
            level_screen_name = f"level_{self.level_manager.level}"
            screen_data = self.db.get_screen(game_id, level_screen_name)

            if not screen_data:
                level_id = self._resolve_level_id(game_id, self.level_manager.level)
                if level_id:
                    level_screen_name = f"level_{level_id}"
                    screen_data = self.db.get_screen(game_id, level_screen_name)

            # 1. JSON'dan (screen_data) gelen ayarlar (Legacy ve Görsel Ayarları)
            if screen_data and 'level_settings' in screen_data:
                level_settings = screen_data['level_settings']
                basket_sprite_key = level_settings.get('basket_sprite')
                basket_length = int(level_settings.get('basket_length', 128))
                
                # Screen Designer: efekt sheetleri ve parametreleri (eski usul JSON)
                try:
                    ok_rel = str(level_settings.get('effect_correct_sheet') or '').strip()
                    bad_rel = str(level_settings.get('effect_wrong_sheet') or '').strip()
                    fps_val = int(level_settings.get('effect_fps', 24) or 24)
                    scale_pct = int(level_settings.get('effect_scale_percent', 60) or 60)
                    fps_val = max(5, min(60, fps_val))
                    scale_pct = max(10, min(200, scale_pct))
                    self.effect_sheet_fps = fps_val
                    
                    # Mutlak yolları çöz (JSON'dan geliyorsa)
                    ok_abs = self._abs_project_path(ok_rel) if ok_rel else None
                    bad_abs = self._abs_project_path(bad_rel) if bad_rel else None
                    if ok_abs and os.path.exists(ok_abs):
                        self.effect_sheet_correct_path = ok_abs
                    if bad_abs and os.path.exists(bad_abs):
                        self.effect_sheet_wrong_path = bad_abs
                        
                except Exception:
                    pass
            
            # 2. Veritabanı `levels` tablosundan gelen efekt ayarları (ÖNCELİKLİ)
            # Bu kısım JSON'dan bağımsız çalışır, böylece global efekt sistemi devreye girer.
            try:
                lvl_id_for_effects = self._resolve_level_id(game_id, self.level_manager.level)
                effect_sheet_override = None
                wrong_sheet_override = None
                
                if lvl_id_for_effects:
                    eff_cols = self.db.get_level_effect_settings(lvl_id_for_effects)
                    if eff_cols:
                        # A. Yeni FrameSequence Efektleri (Global Effects Table)
                        eff_corr_id = eff_cols.get('effect_correct_id')
                        eff_wrong_id = eff_cols.get('effect_wrong_id')
                        
                        if eff_corr_id:
                            eff_row = self.db.get_effect_by_id(int(eff_corr_id))
                            if eff_row and eff_row.get('params_json'):
                                try:
                                    self.effect_correct_data = json.loads(eff_row['params_json'])
                                    print(f"[AppDBG] Loaded correct effect data for level {self.level_manager.level}")
                                except: pass
                        
                        if eff_wrong_id:
                            eff_row = self.db.get_effect_by_id(int(eff_wrong_id))
                            if eff_row and eff_row.get('params_json'):
                                try:
                                    self.effect_wrong_data = json.loads(eff_row['params_json'])
                                    print(f"[AppDBG] Loaded wrong effect data for level {self.level_manager.level}")
                                except: pass

                        # B. Eski SpriteSheet Efektleri (Geriye dönük uyumluluk ve parametreler)
                        correct_id = eff_cols.get('effect_correct_sheet_id')
                        wrong_id = eff_cols.get('effect_wrong_sheet_id')
                        
                        if correct_id:
                            effect_sheet_override = self.db.get_effect_sheet_by_id(int(correct_id))
                        if wrong_id:
                            wrong_sheet_override = self.db.get_effect_sheet_by_id(int(wrong_id))
                            
                        # Override paths if defined in DB columns (legacy text columns)
                        if 'effect_correct_sheet' in eff_cols and eff_cols['effect_correct_sheet']:
                            path = self._abs_project_path(eff_cols['effect_correct_sheet'])
                            if path and os.path.exists(path):
                                self.effect_sheet_correct_path = path
                                
                        if 'effect_wrong_sheet' in eff_cols and eff_cols['effect_wrong_sheet']:
                            path = self._abs_project_path(eff_cols['effect_wrong_sheet'])
                            if path and os.path.exists(path):
                                self.effect_sheet_wrong_path = path

                        # FPS ve Scale
                        if 'effect_fps' in eff_cols:
                            try:
                                self.effect_sheet_fps = max(5, min(60, int(eff_cols.get('effect_fps'))))
                            except: pass
                        if 'effect_scale_percent' in eff_cols:
                            try:
                                scale_pct = max(10, min(200, int(eff_cols.get('effect_scale_percent'))))
                            except: pass

                # Apply overrides if structured sheets set (EffectSheets Table)
                if effect_sheet_override:
                    self.effect_sheet_correct_path = self._abs_project_path(effect_sheet_override.get('sheet_path')) or self.effect_sheet_correct_path
                    self.effect_sheet_fps = int(effect_sheet_override.get('fps', self.effect_sheet_fps))
                    if effect_sheet_override.get('scale'):
                        scale_pct = int(effect_sheet_override.get('scale', 1.0) * 100)
                    self.effect_sheet_correct_cols = int(effect_sheet_override.get('cols', 6))
                    self.effect_sheet_correct_rows = int(effect_sheet_override.get('rows', 5))
                
                if wrong_sheet_override:
                    self.effect_sheet_wrong_path = self._abs_project_path(wrong_sheet_override.get('sheet_path')) or self.effect_sheet_wrong_path
                    # FPS shared usually, but could be separate. Using shared for now or override if last.
                    # self.effect_sheet_fps = ... 
                    self.effect_sheet_wrong_cols = int(wrong_sheet_override.get('cols', 6))
                    self.effect_sheet_wrong_rows = int(wrong_sheet_override.get('rows', 5))

            except Exception as e:
                print(f"[AppDBG] Error loading DB effects: {e}")

            # Ölçek hesapla: hedef genişlik = basket_length * (scale_pct/100)
            def _calc_scale(sheet_path: str | None) -> float:
                try:
                    if not sheet_path or not os.path.exists(sheet_path):
                        return 1.25
                    img = pygame.image.load(sheet_path).convert_alpha()
                    # Varsayılan olarak correct cols kullanılıyor, path'e göre ayırt edilebilir ama basitleştirilmiş:
                    cols = self.effect_sheet_correct_cols if sheet_path == self.effect_sheet_correct_path else self.effect_sheet_wrong_cols
                    frame_w = max(1, img.get_width() // cols)
                    target_w = max(16, int(basket_length * scale_pct / 100.0))
                    return max(0.1, target_w / float(frame_w))
                except Exception:
                    return 1.25

            self.effect_sheet_correct_scale = _calc_scale(self.effect_sheet_correct_path)
            self.effect_sheet_wrong_scale = _calc_scale(self.effect_sheet_wrong_path)

            # Ön-yükleme: ilk tetiklemede gecikmeyi azalt
            try:
                if self.effect_sheet_correct_path:
                    self.effect_manager.preload_sheet(self.effect_sheet_correct_path)
                if self.effect_sheet_wrong_path:
                    self.effect_manager.preload_sheet(self.effect_sheet_wrong_path)
            except Exception:
                pass

            # Basket Sprite Loading
            if 'basket_sprite_key' in locals() and basket_sprite_key:
                region_info = self.db.get_sprite_region(basket_sprite_key)
                if region_info:
                    sheet_path_abs = self._abs_project_path(region_info['sheet_path'])
                    if sheet_path_abs:
                        sheet_img = pygame.image.load(sheet_path_abs).convert_alpha()
                        region_rect = pygame.Rect(region_info['x'], region_info['y'], region_info['width'], region_info['height'])
                        self.paddle_surface = sheet_img.subsurface(region_rect).copy()
        except Exception as e:
            print(f"[AppDBG] Critical error in _start_playing setup: {e}")
            pass

        # Create the player sprite
        if self.paddle_surface:
            self.game_state.player = Player(image=self.paddle_surface, length=basket_length)
        else:
            # Fallback to a default rectangle if no sprite is found
            fallback_surface = pygame.Surface((basket_length, 30))
            fallback_surface.fill(ORANGE)
            self.game_state.player = Player(image=fallback_surface, length=basket_length)
        
        self.game_state.all_sprites.add(self.game_state.player)

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
        """Overlay tasarÄ±mÄ±ndaki arkaplan gÃ¶rselini oynanÄ±ÅŸ arkaplanÄ± olarak uygular.

        TasarÄ±m ekranÄ±nda belirtilen `background.image` yolu mevcutsa `self.level_bg_surface`
        buna gÃ¶re set edilir. BÃ¶ylece level ekranÄ± tasarÄ±mdaki arkaplanla baÅŸlar.
        """
        data = self.level_overlay_data or {}
        bg_rel = ((data.get('background') or {}).get('image')) or ''
        path = self._abs_project_path(bg_rel) or (bg_rel if os.path.exists(bg_rel) else None)
        if path:
            try:
                img = pygame.image.load(path).convert()
                self.level_bg_surface = img
            except Exception:
                pass

    def _apply_overlay_paddle(self):
        """Overlay widget'larÄ±ndan paddle iÃ§in sprite tÃ¼retir (opsiyonel).

        EditÃ¶rde bir widget 'sprite' olup rolÃ¼/ismi paddle ise, ilgili sheet bÃ¶lgesi ya da
        doÄŸrudan gÃ¶rselden `self.paddle_surface` Ã¼retilir.
        Desteklenen ipuÃ§larÄ±: widget'ta `role=='paddle'` veya `name=='paddle'` ya da `action=='paddle'`.
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
        # Ã–ncelik: sprite sheet + frame -> doÄŸrudan image path
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
        # DoÄŸrudan image
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
        """Overlay tasarÄ±mÄ±ndaki genel ayarlarÄ± uygular.

        Desteklenen anahtarlar (TR ve EN):
        - HUD Sprite: yol -> UI help dÃ¼ÄŸmesi
        - YardÄ±m AlanÄ± / help_area: 'top-right' | 'top-left'
        - DoÄŸru SFX / sfx_correct, YanlÄ±ÅŸ SFX / sfx_wrong: ses dosya yollarÄ±
        """
        data = self.level_overlay_data or {}
        # Hem 'settings' hem de 'level_settings' kaynaklarÄ±nÄ± birleÅŸtir
        settings_map = {}
        try:
            base_settings = data.get('settings') or {}
            level_settings = data.get('level_settings') or {}
            settings_map = {**base_settings, **level_settings}
        except Exception:
            settings_map = (data.get('settings') or {})
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
            settings_map.get('YardÄ±m AlanÄ±')
            or settings_map.get('help_area')
            or settings_map.get('help')
        )
        try:
            if isinstance(help_area, str) and help_area:
                self.ui_manager.help_area = help_area
        except Exception:
            pass
        # SFX load
        corr = settings_map.get('DoÄŸru SFX') or settings_map.get('sfx_correct')
        wrong = settings_map.get('YanlÄ±ÅŸ SFX') or settings_map.get('sfx_wrong')
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
        # Paddle length (Sepet UzunluÄŸu)
        try:
            paddle_len = settings_map.get('Sepet UzunluÄŸu') or settings_map.get('paddle_length') or settings_map.get('basket_length')
            if paddle_len:
                settings.PLAYER_WIDTH = int(paddle_len)
        except Exception:
            pass
        # Paddle sprite from settings (Sepet Sprite / paddle_sprite / basket_sprite)
        try:
            paddle_path_raw = settings_map.get('Sepet Sprite') or settings_map.get('paddle_sprite') or settings_map.get('basket_sprite')
            if paddle_path_raw and isinstance(paddle_path_raw, str):
                # EditÃ¶r formatÄ±: "mor â€” assets/images/buttons.png"
                if ' â€” ' in paddle_path_raw:
                    paddle_path = paddle_path_raw.split(' â€” ', 1)[-1].strip()
                else:
                    paddle_path = paddle_path_raw

                path_abs = self._abs_project_path(paddle_path)
                if path_abs and os.path.exists(path_abs):
                    img = pygame.image.load(path_abs).convert_alpha()
                    self.paddle_surface = img
                    print(f"[SpriteDBG] paddle sprite from overlay settings applied: {path_abs}")
                elif os.path.exists(paddle_path):
                    img = pygame.image.load(paddle_path).convert_alpha()
                    self.paddle_surface = img
                    print(f"[SpriteDBG] paddle sprite from overlay settings applied: {paddle_path}")
        except Exception:
            pass
        # Music override from overlay
        try:
            music_path = settings_map.get('MÃ¼zik') or settings_map.get('music')
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
            if 'default_max_items' in settings_map:
                max_items_on_screen = int(settings_map.get('default_max_items'))
                self.level_manager.max_items_on_screen = max_items_on_screen
            
            if 'default_item_speed' in settings_map:
                item_speed = float(settings_map.get('default_item_speed'))
                self.level_manager.item_speed = item_speed
        except Exception:
            pass

        # Level oynanÄ±ÅŸ ekranÄ± iÃ§in tasarÄ±m overlay'ini yÃ¼kle (opsiyonel)
        # OlasÄ± isimler (her iki ÅŸema):
        # - level_<num>_screen, level_<num>_play, level_<num>
        # - level_<id>_screen,  level_<id>_play,  level_<id>
        self.level_overlay_data = None
        try:
            lvl_num = self.level_manager.level
            lvl_id = self._resolve_level_id(game_id, lvl_num)
            candidate_names = [
                f"level_{lvl_num}_screen",
                f"level_{lvl_num}_play",
                f"level_{lvl_num}",
                (f"level_{lvl_id}_screen" if lvl_id else None),
                (f"level_{lvl_id}_play" if lvl_id else None),
                (f"level_{lvl_id}" if lvl_id else None),
                "playing",
            ]
            # debug log kaldÄ±rÄ±ldÄ±
            for name in filter(None, candidate_names):
                data = self.db.get_screen(game_id, name)
                if data and isinstance(data, dict):
                    self.level_overlay_data = data
                    # debug log kaldÄ±rÄ±ldÄ±
                    break
        except Exception:
            self.level_overlay_data = None
        # Overlay butonlarÄ±nÄ± hazÄ±rla
        try:
            self._prepare_overlay_widgets()
        except Exception:
            self.level_overlay_buttons = []
        # Overlay'deki arkaplanÄ± level oynanÄ±ÅŸÄ±na uygula (varsa)
        try:
            self._apply_overlay_background()
        except Exception:
            pass
        # Overlay'den paddle sprite'Ä± tÃ¼ret (opsiyonel)
        try:
            self._apply_overlay_paddle()
        except Exception:
            pass
        # Overlay genel ayarlarÄ±nÄ± uygula (HUD sprite, help area, SFX)
        try:
            self._apply_overlay_settings()
        except Exception:
            pass

        # DÃ¼ÅŸen nesneler iÃ§in sprite regionlarÄ±ndan base surface'leri hazÄ±rla
        try:
            self.item_base_surfaces = []
            lvl_num = self.level_manager.level
            lvl_id = self._resolve_level_id(game_id, lvl_num)
            print(f"[SpriteDBG] preparing item surfaces for game_id={game_id}, level_num={lvl_num}, level_id={lvl_id}")

            def _load_item_surfaces_for_level(level_id: int) -> int:
                regions = self.db.get_level_background_regions(level_id)
                print(f"[SpriteDBG] item regions found: {len(regions)} for level_id={level_id}")
                for r in regions:
                    sheet_rel = r.get('sheet_path')
                    x, y, w, h = int(r.get('x', 0)), int(r.get('y', 0)), int(r.get('width', 0)), int(r.get('height', 0))
                    try:
                        # Resolve absolute path for relative asset paths
                        sheet_abs = self._abs_project_path(sheet_rel) or (sheet_rel if sheet_rel and os.path.exists(sheet_rel) else None)
                        print(f"[SpriteDBG] region path: rel={sheet_rel} -> abs={sheet_abs}; size=({w}x{h})")
                        if not sheet_abs:
                            print(f"[SpriteDBG] item sheet not found: rel={sheet_rel}")
                            continue
                        if w <= 0 or h <= 0:
                            print(f"[SpriteDBG] invalid region size: w={w}, h={h}")
                            continue
                        img = pygame.image.load(sheet_abs).convert_alpha()
                        rect = pygame.Rect(x, y, w, h)
                        rect = rect.clip(pygame.Rect(0, 0, img.get_width(), img.get_height()))
                        if rect.width <= 0 or rect.height <= 0:
                            print(f"[SpriteDBG] clipped rect empty for region: {x},{y},{w},{h} on {sheet_abs}")
                            continue
                        sub = img.subsurface(rect).copy()
                        self.item_base_surfaces.append(sub)
                    except Exception as e:
                        print(f"[SpriteDBG] failed to build item surface: {e}")
                        continue
                return len(self.item_base_surfaces)

            if lvl_id:
                count = _load_item_surfaces_for_level(lvl_id)
                # EÄŸer mevcut level'da yoksa, oyun iÃ§i deneyim iÃ§in diÄŸer level'lara bak
                if count == 0:
                    print("[SpriteDBG] no item regions for current level; searching other levels with regions...")
                    try:
                        levels = self.db.get_levels(game_id)
                        for row in levels:
                            other_id = int(row.get('id'))
                            if other_id == lvl_id:
                                continue
                            # GeÃ§ici listeyi temizlemeden deneyelim; sadece ilk bulunanÄ± kullan
                            prev_len = len(self.item_base_surfaces)
                            found = _load_item_surfaces_for_level(other_id)
                            if found > prev_len:
                                # Bu level'Ä± aktif yap (numarasÄ±na geÃ§)
                                try:
                                    self.level_manager.setup_level(int(row.get('level_number', 1)), game_id)
                                    print(f"[SpriteDBG] switched to level_number={row.get('level_number')} having item regions")
                                except Exception:
                                    pass
                                break
                    except Exception:
                        pass
            print(f"[SpriteDBG] item base surfaces ready: {len(self.item_base_surfaces)}")
            if not self.item_base_surfaces:
                print("[SpriteDBG] WARNING: item_base_surfaces is EMPTY; items will fallback to sheet or simple shapes.")
        except Exception as e:
            print(f"[SpriteDBG] preparing item base surfaces failed: {e}")
            self.item_base_surfaces = []

    def _prepare_level_info_widgets(self):
        """Editor JSON'undan buton bÃ¶lgelerini ve aksiyonlarÄ±nÄ± Ã§Ä±karÄ±r."""
        self.level_info_buttons = []
        data = self.level_info_data or {}
        widgets = data.get('widgets') or []
        for w in widgets:
            try:
                if w.get('type') == 'button':
                    x = int(w.get('x', 0)); y = int(w.get('y', 0))
                    # Ã¶lÃ§Ã¼ler sprite.frame ya da varsayÄ±lan Ã¼zerinden
                    fw = int(((w.get('sprite') or {}).get('frame') or {}).get('width', 180))
                    fh = int(((w.get('sprite') or {}).get('frame') or {}).get('height', 48))
                    rect = pygame.Rect(x, y, max(1, fw), max(1, fh))
                    action = str(w.get('action') or 'start_game')
                    text = str(((w.get('text_overlay') or {}).get('text')) or 'Buton')
                    self.level_info_buttons.append({'rect': rect, 'action': action, 'text': text})
            except Exception:
                continue

    def _prepare_opening_widgets(self):
        """Opening ekranÄ± iÃ§in buton bÃ¶lgelerini ve aksiyonlarÄ±nÄ± hazÄ±rlar."""
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
                    text = str(((w.get('text_overlay') or {}).get('text')) or 'BaÅŸla')
                    self.opening_buttons.append({'rect': rect, 'action': action, 'text': text})
            except Exception:
                continue

    def _render_designed_screen(self, data: dict | None, bg_surface: pygame.Surface | None = None, draw_background: bool = True):
        """Editor ile tasarlanan ekranlarÄ± (opening/level_info vb.) ortak biÃ§imde Ã§izer.

        DavranÄ±ÅŸ:
        - Arkaplan Ã¶nceliÄŸi (draw_background True ise): data.background.image -> bg_surface -> mesh arkaplan.
        - Widget tÃ¼rleri: label, sprite/image, button.
        - Label ve Button metinleri Ã¼st katmanda, hafif gÃ¶lgeli Ã§izilir.

        Args:
            data: Ekran JSON verisi (editor "screens" tablosundan).
            bg_surface: Varsa oyun/level Ã¶zel arkaplan yÃ¼zeyi.
            draw_background: False ise sadece widget'larÄ± Ã§izer (oynanÄ±ÅŸ Ã¼stÃ¼ overlay).
        """
        data = data or {}
        # Arkaplan
        if draw_background:
            try:
                bg_rel = ((data.get('background') or {}).get('image')) or ''
                path = self._abs_project_path(bg_rel) or (bg_rel if os.path.exists(bg_rel) else None)
                if path:
                    bg_img = pygame.image.load(path)
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
                    # Metin overlay (erteleyerek Ã¼st katmanda)
                    txt_cfg = (w.get('text_overlay') or {})
                    txt = str(txt_cfg.get('text') or w.get('text') or 'BaÅŸla')
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
        """Oyun durumunu gÃ¼nceller; oynanÄ±ÅŸ harici durumlarda erken dÃ¶ner."""
        if self.current_state != 'playing':
            return
            
        new_state = self.game_state.update(self.level_manager)
        if new_state == 'level_up':
            # Tebrikler ekranını atla, direkt sonraki seviye akışına gir
            if not self._try_switch_to_level_info(self.selected_game_id, self.level_manager.level):
                self._start_playing(self.selected_game_id, self.level_manager.level)
            return
        elif new_state:
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
            # Ã–nce gerÃ§ek oyun (sepet, dÃ¼ÅŸen nesneler, HUD)
            draw_playing_screen(self.screen, self.game_state, self.level_manager, self.ui_manager, self.effect_manager, self.level_bgs, self.level_bg_surface)
            # ArdÄ±ndan tasarÄ±m overlay'i (sadece widget'lar), arkaplanÄ± yeniden Ã§izme
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
        """Nesne doÄŸurma akÄ±ÅŸÄ±nÄ± yÃ¶netir ve eÅŸzamanlÄ± nesne sÄ±nÄ±rÄ±na uyar."""
        # HazÄ±r event yoksa Ã¼ret
        if self.level_manager.spawn_index >= len(self.level_manager.spawn_events) and not self.level_manager.is_level_complete():
            # min/max adetleri makul tut; LevelManager iÃ§eriden kalan doÄŸru Ã¶ÄŸeleri ekler
            self.level_manager.prepare_spawn_events(min_items=2, max_items=5)

        # Ekranda Ã§ok fazla nesne varsa bekle
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
        """Yeni bir dÃ¼ÅŸen nesne oluÅŸturur ve hÄ±zÄ±nÄ± ayarlardan uygular."""
        # Mevcut ise seviye sprite base yÃ¼zeylerinden birini kullan
        base = None
        try:
            pool_len = len(self.item_base_surfaces) if isinstance(getattr(self, 'item_base_surfaces', None), list) else 0
            print(f"[SpriteDBG] spawn_item: pool_len={pool_len} text='{text}' category='{category}'")
            if pool_len:
                import random as _rnd
                base = _rnd.choice(self.item_base_surfaces)
                print("[SpriteDBG] spawn_item: using base_surface from pool")
        except Exception as _:
            base = None
        item = Item(text, category, base_surface=base)
        print(f"[SpriteDBG] spawn_item: base_surface={base is not None} text='{text}' category='{category}'")
        # HÄ±z ayarÄ±: game settings Ã¼zerinden gelen deÄŸer
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
            cx = self.game_state.player.rect.centerx
            cy = self.game_state.player.rect.centery - max(2, int(self.game_state.player.rect.height * 0.25))
            
            if hit.item_type == self.level_manager.target_category:
                points = 5 if self.game_state.help_mode else 10
                self.game_state.score += points
                self.level_manager.caught_correct.append(hit.text)
                
                # 1. Frame Sequence Effect (Yeni Sistem)
                played = False
                if getattr(self, 'effect_correct_data', None):
                    try:
                        played = self.effect_manager.trigger_effect_by_data(
                            self.effect_correct_data,
                            cx, cy,
                            scale=self.effect_sheet_correct_scale, # Scale'i buradan alabiliriz veya datadan
                            follow_rect=self.game_state.player.rect,
                            offset=(0, -max(2, int(self.game_state.player.rect.height * 0.25)))
                        )
                    except Exception as e:
                        print(f"Frame effect error: {e}")
                        played = False

                # 2. Sprite Sheet Effect (Eski Sistem - Fallback)
                if not played:
                    try:
                        if self.effect_sheet_correct_path:
                            played = self.effect_manager.trigger_sprite_sheet(
                                self.effect_sheet_correct_path,
                                cx, cy,
                                cols=self.effect_sheet_correct_cols, rows=self.effect_sheet_correct_rows,
                                scale=self.effect_sheet_correct_scale,
                                fps=self.effect_sheet_fps,
                                follow_rect=self.game_state.player.rect,
                                offset=(0, -max(2, int(self.game_state.player.rect.height * 0.25)))
                            )
                    except Exception:
                        played = False
                
                # 3. Default Confetti (En son çare)
                if not played:
                    self.effect_manager.trigger_confetti(self.game_state.player.rect.centerx, self.game_state.player.rect.centery)
                
                # SFX
                try:
                    if self.sfx_correct:
                        self.sfx_correct.play()
                except Exception:
                    pass
            else:
                if self.game_state.lose_life(reason="caught_wrong_item"):
                    return 'game_over'
                
                # 1. Frame Sequence Effect (Yeni Sistem)
                played = False
                if getattr(self, 'effect_wrong_data', None):
                    try:
                        played = self.effect_manager.trigger_effect_by_data(
                            self.effect_wrong_data,
                            cx, cy,
                            scale=self.effect_sheet_wrong_scale,
                            follow_rect=self.game_state.player.rect,
                            offset=(0, -max(2, int(self.game_state.player.rect.height * 0.25)))
                        )
                    except Exception as e:
                        print(f"Frame effect error (wrong): {e}")
                        played = False

                # 2. Sprite Sheet Effect (Eski Sistem - Fallback)
                if not played:
                    try:
                        if self.effect_sheet_wrong_path:
                            played = self.effect_manager.trigger_sprite_sheet(
                                self.effect_sheet_wrong_path,
                                cx, cy,
                                cols=self.effect_sheet_wrong_cols, rows=self.effect_sheet_wrong_rows,
                                scale=self.effect_sheet_wrong_scale,
                                fps=self.effect_sheet_fps,
                                follow_rect=self.game_state.player.rect,
                                offset=(0, -max(2, int(self.game_state.player.rect.height * 0.25)))
                            )
                    except Exception:
                        played = False
                
                # 3. Sad Effect (En son çare)
                if not played:
                    self.effect_manager.trigger_sad_effect(self.game_state.player.rect.centerx, self.game_state.player.rect.centery)
                
                # SFX
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



