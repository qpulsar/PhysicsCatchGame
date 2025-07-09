# screens.py
import pygame
from utils import draw_text
from settings import SCREEN_WIDTH, SCREEN_HEIGHT, WHITE, BACKGROUND_COLOR

def show_game_over_screen(screen):
    import os
    finish_bg = pygame.image.load(os.path.join('img', 'backgrounds', '6.jpg'))
    finish_bg = pygame.transform.scale(finish_bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
    restart_button_rect = pygame.Rect((SCREEN_WIDTH-300)//2, SCREEN_HEIGHT//2+40, 300, 70)
    exit_button_rect = pygame.Rect((SCREEN_WIDTH-300)//2, SCREEN_HEIGHT//2+130, 300, 70)
    button_color = (30, 144, 255)
    button_hover_color = (0, 191, 255)
    font_big = pygame.font.Font(None, 60)
    font_small = pygame.font.Font(None, 36)
    while True:
        screen.blit(finish_bg, (0, 0))
        draw_text(screen, "OYUN BİTTİ!", 64, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 70, (255,69,0))
        draw_text(screen, "Yeniden başlatmak veya çıkmak için bir seçim yapın.", 32, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2, (0,0,0))
        mouse_pos = pygame.mouse.get_pos()
        # Restart button
        restart_hover = restart_button_rect.collidepoint(mouse_pos)
        pygame.draw.rect(screen, button_hover_color if restart_hover else button_color, restart_button_rect, border_radius=15)
        restart_label = font_big.render("Yeniden Başlat", True, (255,255,255))
        screen.blit(restart_label, restart_label.get_rect(center=restart_button_rect.center))
        # Exit button
        exit_hover = exit_button_rect.collidepoint(mouse_pos)
        pygame.draw.rect(screen, button_hover_color if exit_hover else button_color, exit_button_rect, border_radius=15)
        exit_label = font_big.render("Çıkış", True, (255,255,255))
        screen.blit(exit_label, exit_label.get_rect(center=exit_button_rect.center))
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.MOUSEBUTTONDOWN:
                if restart_hover:
                    return True
                elif exit_hover:
                    return False
            if event.type == pygame.KEYDOWN:
                if event.key == pygame.K_r:
                    return True
                elif event.key == pygame.K_ESCAPE:
                    return False

def show_level_up_screen(screen):
    screen.fill(BACKGROUND_COLOR)
    draw_text(screen, "Seviye Atladi!", 64, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 - 50, WHITE)
    draw_text(screen, "Devam etmek için bir tuşa basın", 32, SCREEN_WIDTH // 2, SCREEN_HEIGHT // 2 + 20, WHITE)
    pygame.display.flip()
    waiting = True
    while waiting:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.KEYUP:
                waiting = False

import os

def show_splash_screen(screen):
    splash_bg = pygame.image.load(os.path.join('img', 'backgrounds', '1.jpg'))
    splash_bg = pygame.transform.scale(splash_bg, (SCREEN_WIDTH, SCREEN_HEIGHT))
    button_width = 220
    button_height = 70
    button_color = (30, 144, 255)
    button_hover_color = (0, 191, 255)
    button_rect = pygame.Rect((SCREEN_WIDTH - button_width)//2, SCREEN_HEIGHT//2 + 40, button_width, button_height)
    help_button_img = pygame.image.load(os.path.join('img', 'button_help.png'))
    help_button_img = pygame.transform.scale(help_button_img, (40, 40))
    help_button_rect = pygame.Rect(10, 10, 40, 40)

    running = True
    while running:
        screen.blit(splash_bg, (0, 0))
        draw_text(screen, "Fiziksel Büyüklükleri Yakala!", 54, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 4, (65, 105, 225))
        draw_text(screen, "Doğru büyüklükleri topla, yanlışlardan kaç!", 32, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 4 + 70, (0, 0, 0))
        draw_text(screen, "Başlamak için aşağıdaki butona tıkla.", 28, SCREEN_WIDTH / 2, SCREEN_HEIGHT / 2 - 30, (0, 0, 0))

        mouse_pos = pygame.mouse.get_pos()
        is_hover = button_rect.collidepoint(mouse_pos)
        color = button_hover_color if is_hover else button_color
        pygame.draw.rect(screen, color, button_rect, border_radius=15)
        draw_text(screen, "Başlat", 40, SCREEN_WIDTH/2, button_rect.centery, (255,255,255))
        # Yardım butonu
        screen.blit(help_button_img, help_button_rect)
        pygame.display.flip()
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                pygame.quit()
                exit()
            if event.type == pygame.MOUSEBUTTONDOWN and is_hover:
                running = False
            if event.type == pygame.KEYDOWN and event.key == pygame.K_RETURN:
                running = False
