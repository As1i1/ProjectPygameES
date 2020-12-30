import pygame
import os
import sys
import math
from copy import deepcopy
import random


def load_image(name, colorkey=None):
    fullname = os.path.join('data', name)
    if not os.path.isfile(fullname):
        print(f"Файл с изображением '{fullname}' не найден")
        sys.exit()
    image = pygame.image.load(fullname)
    if colorkey is not None:
        image = image.convert()
        if colorkey == -1:
            colorkey = image.get_at((0, 0))
        image.set_colorkey(colorkey)
    return image


def terminate():
    pygame.quit()
    sys.exit()


def normal_exit():
    """Нормальный выход из игры (с вызовом титров)"""


def end_screen():
    pass


if __name__ == '__main__':
    pygame.init()
    WIDTH, HEIGHT = 800, 600
    size = WIDTH, HEIGHT
    screen = pygame.display.set_mode(size)
    image_menu = load_image('Background\Menu.jpg')
    running = True
    while running:
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                terminate()
        screen.blit(image_menu, (0, 0))
        pygame.display.flip()