import pygame
import os
import sys
import argparse
import inspect
from settings import SCREEN_WIDTH, SCREEN_HEIGHT
from game.app import Game



if __name__ == "__main__":
    # Add project root to sys.path to handle relative imports
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

    parser = argparse.ArgumentParser(description="FizikselB Oyunu")
    parser.add_argument("--game-id", type=int, default=None, help="Editörden seçili oyunun ID'si")
    parser.add_argument("--from-editor", action="store_true", help="Editörden başlatıldığını belirtir")
    args = parser.parse_args()

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Fiziksel Büyüklükleri Yakala!")

    # Basit çalışma zamanı tanılama logu (doğru dosya ve sınıf mı?)
    try:
        print(f"[RunDBG] main: __file__={__file__}")
        print(f"[RunDBG] main: cwd={os.getcwd()}")
        print(f"[RunDBG] args: game_id={args.game_id}, from_editor={args.from_editor}")
        print(f"[RunDBG] Game class at: {inspect.getfile(Game)} (module={Game.__module__})")
    except Exception:
        pass

    # Editörden geldiyse seçili oyunla başla ve açılış ekranını göster
    if args.game_id:
        game = Game(screen, force_game_id=args.game_id)
        # Açılış ekranını (varsa) hemen gösterecek akışı başlat
        game.start_game(args.game_id)
    else:
        game = Game(screen)

    game.run()



