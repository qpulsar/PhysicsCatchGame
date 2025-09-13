import pygame
import os
import sys
from settings import SCREEN_WIDTH, SCREEN_HEIGHT
from game.app import Game



if __name__ == "__main__":
    # Add project root to sys.path to handle relative imports
    sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '.')))

    pygame.init()
    screen = pygame.display.set_mode((SCREEN_WIDTH, SCREEN_HEIGHT))
    pygame.display.set_caption("Fiziksel Büyüklükleri Yakala!")
    
    game = Game(screen)
    game.run()



