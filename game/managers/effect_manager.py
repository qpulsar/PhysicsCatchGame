"""Effect Manager Module

This module provides classes for managing visual effects in the game,
including confetti and sad effects.
"""

import random
import os
from typing import List, Optional, Tuple, Dict

import pygame

from settings import *
from game.core.utils import get_resource_path

class ConfettiParticle:
    def __init__(self, x: float, y: float):
        self.x = x + random.uniform(-50, 50)
        self.y = y + random.uniform(-50, 50)
        self.radius = random.randint(3, 7)
        self.color = random.choice([RED, GREEN, BLUE, YELLOW, ORANGE, PURPLE])
        self.speed_x = random.uniform(-3, 3)
        self.speed_y = random.uniform(1, 6)
        self.life = random.randint(15, 30)
    
    def update(self) -> None:
        self.x += self.speed_x
        self.y += self.speed_y
        self.life -= 0.1
    
    def draw(self, surface: pygame.Surface) -> None:
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), int(self.radius))

class SadEffect:
    def __init__(self, x: float, y: float):
        self.x = x
        self.y = y
        self.radius = 60
        self.life = 30
        self.shake = 0
    
    def update(self) -> None:
        self.shake = (self.shake + 1) % 4
        self.life -= 1
    
    def draw(self, surface: pygame.Surface) -> None:
        if self.life > 0:
            offset_x = random.randint(-self.shake, self.shake)
            offset_y = random.randint(-self.shake, self.shake)
            pygame.draw.circle(
                surface, 
                (255, 0, 0, 100),
                (int(self.x) + offset_x, int(self.y) + offset_y), 
                self.radius, 
                3
            )

class EffectManager:
    def __init__(self):
        self.confetti_particles: List[ConfettiParticle] = []
        self.sad_effect: Optional[SadEffect] = None
        self.confetti_timer: int = 0
        self.sad_timer: int = 0
        self._sheet_cache: Dict[str, pygame.Surface] = {}
        self._active_sheet_anims: List["_SheetAnimState"] = []
        self._active_frame_anims: List["_FrameAnimState"] = []

    class _SheetAnimState:
        """Önceden kesilmiş ve ölçeklenmiş kareleri oynatan animasyon state."""
        def __init__(self, frames: List[pygame.Surface], pos_x: float, pos_y: float, fps: int = 24, *, follow_rect: Optional[pygame.Rect] = None, offset: Tuple[int, int] | None = None):
            self.frames = frames
            self.pos_x = pos_x
            self.pos_y = pos_y
            self.fps = max(1, fps)
            self.frame_duration = int(1000 / self.fps)
            self.total_frames = len(frames)
            self.current = 0
            self.last_tick = pygame.time.get_ticks()
            self.follow_rect = follow_rect
            self.offset = offset if offset is not None else (0, 0)

        def update(self) -> bool:
            now = pygame.time.get_ticks()
            if now - self.last_tick >= self.frame_duration:
                self.current += 1
                self.last_tick = now
            return self.current < self.total_frames

        def draw(self, surface: pygame.Surface) -> None:
            if self.current >= self.total_frames:
                return
            frame = self.frames[self.current]
            if self.follow_rect is not None:
                cx = self.follow_rect.centerx + int(self.offset[0])
                cy = self.follow_rect.centery + int(self.offset[1])
            else:
                cx, cy = int(self.pos_x), int(self.pos_y)
            rect = frame.get_rect(center=(cx, cy))
            surface.blit(frame, rect)

    class _FrameAnimState:
        """Serbest koordinatlı kareleri oynatan animasyon state."""
        def __init__(self, frames: List[pygame.Surface], pos_x: float, pos_y: float, frame_ms: int = 120, *, follow_rect: Optional[pygame.Rect] = None, offset: Tuple[int, int] | None = None):
            self.frames = frames
            self.pos_x = pos_x
            self.pos_y = pos_y
            self.frame_duration = max(10, frame_ms)
            self.total_frames = len(frames)
            self.current = 0
            self.last_tick = pygame.time.get_ticks()
            self.follow_rect = follow_rect
            self.offset = offset if offset is not None else (0, 0)

        def update(self) -> bool:
            now = pygame.time.get_ticks()
            if now - self.last_tick >= self.frame_duration:
                self.current += 1
                self.last_tick = now
            return self.current < self.total_frames

        def draw(self, surface: pygame.Surface) -> None:
            if self.current >= self.total_frames:
                return
            frame = self.frames[self.current]
            if self.follow_rect is not None:
                cx = self.follow_rect.centerx + int(self.offset[0])
                cy = self.follow_rect.centery + int(self.offset[1])
            else:
                cx, cy = int(self.pos_x), int(self.pos_y)
            rect = frame.get_rect(center=(cx, cy))
            surface.blit(frame, rect)
    
    def trigger_confetti(self, x: float, y: float, count: int = 40) -> None:
        self.confetti_particles = [ConfettiParticle(x, y) for _ in range(count)]
        self.confetti_timer = 25
    
    def trigger_sad_effect(self, x: float, y: float) -> None:
        self.sad_effect = SadEffect(x, y)
        self.sad_timer = 30

    def trigger_basket_shake(self, player) -> None:
        if hasattr(player, 'apply_shake'):
            player.apply_shake(intensity=8, duration=15)
    
    def update(self) -> None:
        self._update_confetti()
        self._update_sad_effect()
        self._update_sheet_anims()
        self._update_frame_anims()
    
    def _update_confetti(self) -> None:
        if self.confetti_timer > 0:
            self.confetti_timer -= 1
            for particle in self.confetti_particles[:]:
                particle.update()
                if particle.life <= 0:
                    self.confetti_particles.remove(particle)
    
    def _update_sad_effect(self) -> None:
        if self.sad_effect:
            self.sad_effect.update()
            self.sad_timer -= 1
            if self.sad_timer <= 0 or self.sad_effect.life <= 0:
                self.sad_effect = None
    
    def draw(self, surface: pygame.Surface) -> None:
        self._draw_confetti(surface)
        self._draw_sad_effect(surface)
        self._draw_sheet_anims(surface)
        self._draw_frame_anims(surface)
    
    def _draw_confetti(self, surface: pygame.Surface) -> None:
        for particle in self.confetti_particles:
            particle.draw(surface)
    
    def _draw_sad_effect(self, surface: pygame.Surface) -> None:
        if self.sad_effect and self.sad_effect.life > 0:
            self.sad_effect.draw(surface)
    
    def clear_effects(self) -> None:
        self.confetti_timer = 0
        self.sad_timer = 0
        self._active_sheet_anims.clear()
        self._active_frame_anims.clear()

    def trigger_sprite_sheet(self, sheet_path: str, pos_x: float, pos_y: float, *,
                             cols: int = 6, rows: int = 5,
                             target_w: int = 0, scale: float = 1.0,
                             fps: int = 24,
                             follow_rect: Optional[pygame.Rect] = None,
                             offset: Tuple[int, int] | None = None) -> bool:
        """Sprite-sheet animasyonunu tetikler.

        Editördeki _slice_effect_sheet mantığının birebir karşılığı:
        - Kareleri grid olarak keser
        - Her kareyi target_w'ye göre ölçekler (editördeki gibi)
        - target_w verilmezse, dışarıdan gelen scale faktörünü kullanır
        """
        try:
            if not sheet_path:
                return False
            sheet = self._get_sheet(sheet_path)
            if not sheet:
                return False
            
            sw, sh = sheet.get_size()
            cw = sw // cols
            ch = sh // rows

            frames = []
            for r in range(rows):
                for c in range(cols):
                    gx = c * cw
                    gy = r * ch
                    crop = sheet.subsurface(pygame.Rect(gx, gy, cw, ch)).copy()

                    # Editördeki mantık: scale = target_w / frame.width
                    if target_w > 0:
                        s = target_w / max(1, crop.get_width())
                    else:
                        s = scale
                    
                    if abs(s - 1.0) > 0.01:
                        tw = max(1, int(crop.get_width() * s))
                        th = max(1, int(crop.get_height() * s))
                        crop = pygame.transform.smoothscale(crop, (tw, th))
                    frames.append(crop)
            
            anim = self._SheetAnimState(frames, pos_x, pos_y, fps=fps,
                                        follow_rect=follow_rect, offset=offset)
            self._active_sheet_anims.append(anim)
            return True
        except Exception as e:
            print(f"[EffectManager] Sheet trigger error: {e}")
            return False

    def preload_sheet(self, sheet_path: str) -> bool:
        return self._get_sheet(sheet_path) is not None

    def _get_sheet(self, path: str) -> Optional[pygame.Surface]:
        if path in self._sheet_cache:
            return self._sheet_cache[path]
        # Yol çözümleme: doğrudan veya get_resource_path ile
        actual = path
        if not os.path.exists(actual):
            actual = get_resource_path(path)
        if not os.path.exists(actual):
            return None
        try:
            img = pygame.image.load(actual).convert_alpha()
            self._sheet_cache[path] = img
            return img
        except Exception:
            return None

    def trigger_effect_by_data(self, effect_data: Dict, pos_x: float, pos_y: float,
                               target_w: int = 0, scale: float = 1.0,
                               follow_rect: Optional[pygame.Rect] = None,
                               offset: Tuple[int, int] | None = None) -> bool:
        """Frame-sequence efektini tetikler.
        
        Editördeki _produce_effect_frames mantığının birebir karşılığı:
        - Her kareyi JSON'daki x,y,w,h ile keser
        - Her kareyi target_w'ye göre AYRI AYRI ölçekler
        - target_w verilmezse, dışarıdan gelen scale faktörünü kullanır
        """
        if not effect_data:
            return False
        try:
            etype = effect_data.get('type')
            if etype == 'frame_sequence':
                img_path = effect_data.get('image_path', '').replace('\\', '/')
                # Yol çözümleme
                resolved = self._resolve_effect_path(img_path)
                if not resolved:
                    return False
                
                sheet = self._get_sheet(resolved)
                if not sheet:
                    return False
                
                frames_conf = effect_data.get('frames', [])
                if not frames_conf:
                    return False
                
                scaled_frames = []
                for fr in frames_conf:
                    try:
                        fx = int(fr.get('x', 0))
                        fy = int(fr.get('y', 0))
                        fw = int(fr.get('w', 0))
                        fh = int(fr.get('h', 0))
                        if fw <= 0 or fh <= 0:
                            continue
                        
                        # Sınır kontrolü
                        fw = min(fw, sheet.get_width() - fx)
                        fh = min(fh, sheet.get_height() - fy)
                        if fw <= 0 or fh <= 0:
                            continue
                        
                        crop = sheet.subsurface(pygame.Rect(fx, fy, fw, fh)).copy()
                        
                        # Editördeki mantık: scale = target_w / crop.width (her kare ayrı)
                        if target_w > 0:
                            s = target_w / max(1, crop.get_width())
                        else:
                            s = scale
                        
                        if abs(s - 1.0) > 0.01:
                            tw = max(1, int(crop.get_width() * s))
                            th = max(1, int(crop.get_height() * s))
                            crop = pygame.transform.smoothscale(crop, (tw, th))
                        scaled_frames.append(crop)
                    except Exception:
                        continue
                
                if not scaled_frames:
                    return False
                
                frame_ms = int(effect_data.get('frame_ms', 120))
                anim = self._FrameAnimState(scaled_frames, pos_x, pos_y,
                                            frame_ms=frame_ms,
                                            follow_rect=follow_rect, offset=offset)
                self._active_frame_anims.append(anim)
                return True
            return False
        except Exception as e:
            print(f"[EffectManager] Data trigger error: {e}")
            return False

    def _resolve_effect_path(self, img_path: str) -> Optional[str]:
        """Efekt görsel yolunu çözümler (get_resource_path ile proje kökü destekli)."""
        if not img_path:
            return None
        # 1. Doğrudan varsa
        if os.path.exists(img_path):
            return img_path
        # 2. get_resource_path ile dene (proje kökü bazlı)
        candidate = get_resource_path(img_path)
        if os.path.exists(candidate):
            return candidate
        # 3. assets/ altında dene
        candidate = get_resource_path(os.path.join('assets', img_path))
        if os.path.exists(candidate):
            return candidate
        # 4. assets/effects/ altında dene
        candidate = get_resource_path(os.path.join('assets', 'effects', os.path.basename(img_path)))
        if os.path.exists(candidate):
            return candidate
        return None

    def _update_sheet_anims(self) -> None:
        self._active_sheet_anims = [a for a in self._active_sheet_anims if a.update()]

    def _draw_sheet_anims(self, surface: pygame.Surface) -> None:
        for a in self._active_sheet_anims:
            a.draw(surface)

    def _update_frame_anims(self) -> None:
        self._active_frame_anims = [a for a in self._active_frame_anims if a.update()]

    def _draw_frame_anims(self, surface: pygame.Surface) -> None:
        for a in self._active_frame_anims:
            a.draw(surface)
