# game.py
import pygame
import random
from player import Player
from item import Item
from effects import ConfettiParticle, SadEffect
from utils import draw_text, get_new_item
from settings import *
from arduino import connect_arduino, read_arduino

score = 0
lives = 3
level = 1


def game_loop():
    global score, lives, level
    import os
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Fiziksel Büyüklükler Oyunu")
    clock = pygame.time.Clock()
    font = pygame.font.Font(None, 36)

    # --- Arka Planlar ve Yardım Butonu ---
    level_bgs = [pygame.image.load(os.path.join('img', 'backgrounds', f'{i}.jpg')) for i in range(2,6)]
    level_bgs = [pygame.transform.scale(bg, (SCREEN_WIDTH, SCREEN_HEIGHT)) for bg in level_bgs]
    if not level_bgs:
        level_bgs = [pygame.Surface((SCREEN_WIDTH, SCREEN_HEIGHT)) for _ in range(4)]
    help_button_img = pygame.image.load(os.path.join('img', 'button_help.png'))
    help_button_img = pygame.transform.scale(help_button_img, (40, 40))
    help_button_rect = pygame.Rect(10, 10, 40, 40)
    help_mode = False

    all_sprites = pygame.sprite.Group()
    items = pygame.sprite.Group()
    player = Player()
    all_sprites.add(player)

    confetti_particles = []
    sad_effect = None

    item_spawn_delay = 40
    item_spawn_timer = 0

    running = True
    while running:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
            # Help butonuna tıklama kontrolü
            if event.type == pygame.MOUSEBUTTONDOWN:
                if help_button_rect.collidepoint(event.pos):
                    help_mode = not help_mode
            # ESC ile help kapama
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_ESCAPE and help_mode:
                    help_mode = False

        keys = pygame.key.get_pressed()
        move_left = keys[pygame.K_LEFT]
        move_right = keys[pygame.K_RIGHT]
        player.update(move_left, move_right)

        # Yeni item oluşturma
        item_spawn_timer += 1
        if item_spawn_timer >= item_spawn_delay:
            text, item_type = get_new_item(level)
            item = Item(text, item_type)
            all_sprites.add(item)
            items.add(item)
            item_spawn_timer = 0

        # Itemları güncelle
        for item in items:
            item.update()
            if item.rect.top > SCREEN_HEIGHT:
                item.kill()
                lives -= 1
                sad_effect = SadEffect()

        # Çarpışma kontrolü
        hits = pygame.sprite.spritecollide(player, items, True)
        for hit in hits:
            score += 10
            confetti_particles.extend([ConfettiParticle() for _ in range(10)])
            # Kullanıcı topladığı item'ı kaydet
            current_category = LEVEL_TARGETS[level]
            if 'collected_items_by_level' not in locals():
                if not hasattr(game_loop, 'collected_items_by_level'):
                    game_loop.collected_items_by_level = {lvl: set() for lvl in LEVEL_TARGETS.keys()}
                collected_items_by_level = game_loop.collected_items_by_level
            else:
                collected_items_by_level = game_loop.collected_items_by_level
            if hasattr(hit, 'text'):
                collected_items_by_level[level].add(hit.text)

        # Efektleri güncelle
        if sad_effect:
            sad_effect.update()
            if sad_effect.life <= 0:
                sad_effect = None
        for c in confetti_particles[:]:
            c.update()
            if c.life <= 0:
                confetti_particles.remove(c)

        # Seviye atlama
        if score >= level * 100:
            level += 1
            lives += 1
            from screens import show_level_up_screen
            show_level_up_screen(screen)

        # Oyun bitti mi?
        if lives <= 0:
            from screens import show_game_over_screen
            restart = show_game_over_screen(screen)
            if restart:
                # Tüm değişkenleri sıfırla
                score = 0
                lives = 3
                level = 1
                all_sprites.empty()
                items.empty()
                player = Player()
                all_sprites.add(player)
                confetti_particles.clear()
                sad_effect = None
                item_spawn_timer = 0
                continue
            else:
                running = False

        # Çizim
        # Level arka planı
        bg_idx = min(level-1, len(level_bgs)-1)
        screen.blit(level_bgs[bg_idx], (0, 0))
        all_sprites.draw(screen)
        for c in confetti_particles:
            c.draw(screen)
        if sad_effect:
            sad_effect.draw(screen)
        # Yardım butonu
        screen.blit(help_button_img, help_button_rect)
        # Yardım modu açıkken kalan büyüklükleri göster
        if help_mode:
            # Sağda ince transparan overlay sütunu
            overlay_width = 220
            overlay = pygame.Surface((overlay_width, SCREEN_HEIGHT), pygame.SRCALPHA)
            overlay.fill((0, 0, 0, 204))  # %80 transparan siyah
            screen.blit(overlay, (SCREEN_WIDTH - overlay_width, 0))
            # Kalan item'ları bul
            current_category = LEVEL_TARGETS[level]
            all_items = list(ALL_QUANTITIES[current_category])
            # Kullanıcının topladığı item'lar: her level için ayrı takip edilmeli
            if 'collected_items_by_level' not in locals():
                if not hasattr(game_loop, 'collected_items_by_level'):
                    game_loop.collected_items_by_level = {lvl: set() for lvl in LEVEL_TARGETS.keys()}
                collected_items_by_level = game_loop.collected_items_by_level
            else:
                collected_items_by_level = game_loop.collected_items_by_level
            remaining_items = [item for item in all_items if item not in collected_items_by_level[level]]
            # Overlay kutusu (sağ sütun)
            box_x = SCREEN_WIDTH - overlay_width + 10
            box_y = 30
            box_width = overlay_width - 20
            box_height = SCREEN_HEIGHT - 60
            pygame.draw.rect(screen, (255,255,255,220), (box_x, box_y, box_width, box_height), border_radius=18)
            draw_text(screen, f"Kalanlar", 28, box_x + box_width//2, box_y + 28, (30,30,120))
            # Kalan item'ları yazdır (dikey sütun)
            for idx, item_name in enumerate(remaining_items):
                draw_text(screen, f"- {item_name}", 22, box_x + box_width//2, box_y + 60 + idx*26, (50,50,50))
            draw_text(screen, "ESC: Kapat", 18, box_x + box_width//2, box_y + box_height - 24, (100,100,100))
        draw_text(screen, f"Skor: {score}", 32, 80, 30, BLACK)
        draw_text(screen, f"Can: {lives}", 32, 80, 70, BLACK)
        draw_text(screen, f"Seviye: {level}", 32, 80, 110, BLACK)
        pygame.display.flip()
    pygame.quit()
