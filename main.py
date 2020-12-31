import pygame
import os
import sys
import pygame_gui
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


def load_level(filename):
    filename = "data/" + filename
    with open(filename, 'r') as mapFile:
        level_map = [line.strip() for line in mapFile]
    max_width = max(map(len, level_map))
    return list(map(lambda x: x.ljust(max_width, '.'), level_map))


class Camera:
    # зададим начальный сдвиг камеры
    def __init__(self):
        self.dx = 0

    # сдвинуть объект obj на смещение камеры
    def apply(self, obj):
        obj.rect.x += self.dx

    # позиционировать камеру на объекте target
    def update(self, target):
        self.dx = target.dx
        target.dx = 0


class Asphalt(pygame.sprite.Sprite):
    def __init__(self, pos_x, pos_y):
        super().__init__(bound_group, all_sprites)
        self.image = load_image('Background/Constructions/asphalt.png')
        self.rect = self.image.get_rect().move(
            TILE_WIDTH * pos_x, TILE_HEIGHT * pos_y)


class Hero(pygame.sprite.Sprite):
    def __init__(self, pos_x, pos_y):
        super().__init__(all_sprites, hero_group)
        self.image = load_image('Sprites\Semen\Walk (1) — копия.png')
        self.rect = self.image.get_rect().move(pos_x * TILE_WIDTH - self.image.get_height() // 2,
                                               pos_y * TILE_HEIGHT - self.image.get_width() // 2)
        self.lower_bound = 200
        self.upper_bound = 600
        self.dx = 0

    def update(self, *args, **kwargs):
        keys = pygame.key.get_pressed()
        if keys[pygame.K_LEFT]:
            self.rect.x -= math.ceil(50 / FPS)
        if keys[pygame.K_RIGHT]:
            self.rect.x += math.ceil(50 / FPS)
        self.check_bounds()

    def check_bounds(self):
        if self.rect.x > 600:
            self.dx = 600 - self.rect.x
        elif self.rect.x < 200:
            self.dx = 200 - self.rect.x
        else:
            self.dx = 0


class BackGround(pygame.sprite.Sprite):
    def __init__(self, pos_x):
        super().__init__(all_sprites)
        self.image = load_image('Background\city_background_sunset — копия.png')
        self.rect = self.image.get_rect().move(pos_x, 0)


def generate_level(level):
    hero, pos_x, pos_y = None, None, None
    for y in range(len(level)):
        for x in range(len(level[y])):
            if level[y][x] == 'a':
                Asphalt(x, y)
            if level[y][x] == 'H':
                hero = Hero(x, y)
                pos_x, pos_y = x, y
    return hero, pos_x, pos_y


def terminate():
    pygame.quit()
    sys.exit()


def confirm_exit():
    pygame_gui.windows.UIConfirmationDialog(
        rect=pygame.Rect((250, 250), (500, 200)),
        manager=UIManager,
        window_title='Подтверждение',
        action_long_desc='Вы действительно хотите таскать мешки с сахаром?',
        action_short_name='Да!',
        blocking=True
    )


def show_credits_and_exit():
    """Показ титров с последуюзим выходом из игры"""


def end_screen():
    pass


def move_background(bg_first, bg_second):
    """Перемещение заднего фона"""
    if bg_first.rect.x < -4000:
        bg_first.rect.x = bg_second.rect.x + 4000
    if bg_second.rect.x < -4000:
        bg_second.rect.x = bg_first.rect.x + 4000
    if bg_first.rect.x > 4000:
        bg_first.rect.x = bg_second.rect.x - 4000
    if bg_second.rect.x > 4000:
        bg_second.rect.x = bg_first.rect.x - 4000


def play_game():            # TODO Сделать игру:D ага блять
    """Запуск игры (игрового цикла)"""
    camera = Camera()
    bg_first, bg_second = BackGround(-4000), BackGround(0)
    hero, hero_pos_x, hero_pos_y = generate_level(load_level('Levels/test_level1.txt'))
    running_game = True
    while running_game:
        for event_game in pygame.event.get():
            if event_game.type == pygame.QUIT:
                running_game = False

        hero_group.update(event)
        camera.update(hero)
        # обновляем положение всех спрайтов
        for sprite in all_sprites:
            camera.apply(sprite)

        # Движение BackGround`а (бесконечный фон)
        move_background(bg_first, bg_second)

        screen.fill((0, 0, 0))
        all_sprites.draw(screen)
        hero_group.draw(screen)
        pygame.display.flip()
    return


if __name__ == '__main__':
    # Инициализация
    pygame.init()
    SIZE = WIDTH, HEIGHT = 800, 600
    FPS = 60
    screen = pygame.display.set_mode(SIZE)

    pygame.display.set_caption('Everlasting Mario')
    pygame.display.set_icon(load_image(r'Sprites\Semen\Idle (7).png'))

    # Создание спарйт-групп
    bound_group = pygame.sprite.Group()
    hero_group = pygame.sprite.Group()
    enemy_group = pygame.sprite.Group()
    whero_group = pygame.sprite.Group()
    all_sprites = pygame.sprite.Group()

    # Константы для позиционирования объктов
    TILE_WIDTH, TILE_HEIGHT = 50, 50

    # Создаём менеджер интерфейса с темой для красивого отображения элементов
    UIManager = pygame_gui.UIManager(SIZE, 'base_theme.json')
    # Создаём кнопки
    start_game_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.rect.Rect((500, 60), (170, 40)),
        text='Начать игру',
        manager=UIManager,
    )
    load_game_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.rect.Rect((500, 110), (170, 40)),
        text='Загрузить',
        manager=UIManager
    )
    show_achievements_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.rect.Rect((500, 160), (170, 40)),
        text='Достижения',
        manager=UIManager
    )
    exit_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.rect.Rect((500, 210), (170, 40)),
        text='Выйти',
        manager=UIManager
    )

    # Фон меню
    image_menu = load_image(r'Background\Menu.jpg')

    running = True

    clock = pygame.time.Clock()

    while running:
        time_delta = clock.tick(FPS) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                confirm_exit()
            if event.type == pygame.USEREVENT:
                if event.user_type == pygame_gui.UI_CONFIRMATION_DIALOG_CONFIRMED:
                    running = False
                if event.user_type == pygame_gui.UI_BUTTON_PRESSED:
                    if event.ui_element == start_game_btn:
                        play_game()
                    if event.ui_element == load_game_btn:
                        """Загружаем сохранения"""          # TODO сделать сохранения
                    if event.ui_element == show_achievements_btn:
                        """Показываем достижения"""         # TODO сделать ачивки
                    if event.ui_element == exit_btn:
                        confirm_exit()

            UIManager.process_events(event)

        UIManager.update(time_delta)
        screen.blit(image_menu, (0, 0))
        UIManager.draw_ui(screen)
        pygame.display.flip()

    terminate()
