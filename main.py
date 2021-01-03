import pygame
import os
import sys
import pygame_gui
import math
import shutil
from copy import deepcopy
import random


def load_image(name, colorkey=None, directory='data'):
    fullname = os.path.join(directory, name)
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
    def __init__(self, pos_x, pos_y, *groups):
        super().__init__(*groups)
        self.image = load_image(r'Background/Constructions/asphalt.png')
        self.rect = self.image.get_rect().move(
            TILE_WIDTH * pos_x, TILE_HEIGHT * pos_y)


class Hero(pygame.sprite.Sprite):
    def __init__(self, pos_x, pos_y, *groups):
        super().__init__(*groups)
        self.image = load_image(r'Sprites\Semen\Walk (1).png')
        self.rect = self.image.get_rect().move(pos_x * TILE_WIDTH,
                                               pos_y * TILE_HEIGHT - self.image.get_height() // 2)

        self.lower_bound = 200
        self.upper_bound = WIDTH - self.lower_bound
        self.vx = 50
        self.vx_timer = 1
        self.dx = 0

        self.jump_vy = 0
        self.jump_timer = 0

        self.down_vy = 0
        self.down_timer = 0

    def update(self, *args, **kwargs):
        keys = pygame.key.get_pressed()

        in_jump, in_fall = False, False   # Чтобы нельзя было прыгать в воздухе

        # Если идёт "анимация" прыжка
        if self.jump_timer != 0:
            in_jump = True
            # Если мы ни во что не упираемся сверху
            if 2 not in self.collide_asphalt():
                if self.jump_timer % 3 < 2:
                    self.rect.y -= math.ceil(self.jump_vy / FPS)
                    self.jump_vy -= 1
                self.jump_timer -= 1
            else:
                self.jump_vy = 0
                self.jump_timer = 0

        # Если персонаж не пересекается с асфальтом снизу или сбоку, значит он падает
        elif 1 not in (collide := self.collide_asphalt()) and 0 not in collide:
            if self.down_timer == 0:
                self.down_vy = 1
                self.down_timer = HEIGHT
            if self.down_timer % 3 < 2:
                self.rect.y += math.ceil(self.down_vy / FPS)
                self.down_vy += 1
            self.down_timer -= 1
            in_fall = True

        else:
            self.down_timer = 0
            self.down_vy = 0
            in_fall = False

        # Перемещаем персонажа
        if keys[pygame.K_RIGHT]:
            if (self.jump_timer % 3 < 2 and in_jump) or (self.down_timer % 3 < 2 and in_fall) or \
                    (not in_jump and not in_fall and self.vx_timer % 3 < 2):
                self.rect.x += math.ceil(self.vx / FPS)
            self.vx_timer = (self.vx_timer + 1) % 3
        if keys[pygame.K_LEFT]:
            if (self.jump_timer % 3 < 2 and in_jump) or (self.down_timer % 3 < 2 and in_fall) or \
                    (not in_jump and not in_fall and self.vx_timer % 3 < 2):
                self.rect.x -= math.ceil(self.vx / FPS)
            self.vx_timer = (self.vx_timer + 1) % 3
        if keys[pygame.K_UP] and not in_jump and not in_fall:
            self.jump_vy = 125
            self.jump_timer = 250

        # Если после перемещения, персонаж начинает пересекаться с асфальтом справа или слева,
        # то перемещаем его в самое близкое положение, где он не будет пересекаться с асфальтом
        if 1 in (collide := self.collide_asphalt()):
            self.rect.x = collide[1]

        self.check_bounds()

    def collide_asphalt(self):
        """Проверяет пересечение с асфальтом и возвращает словарь в котором ключами будут:
            0, если персонаж пересекается с асфальтом снизу,
            1, если пересекается с асфальтом справа или слева,
            2, если пересекается с асфальтом сверху"""

        res = {}
        for collide in pygame.sprite.spritecollide(self, bound_group, False):
            if abs(collide.rect.y - self.rect.y - self.rect.h) <= 5:
                res[0] = True
            elif abs(collide.rect.y + collide.rect.h - self.rect.y) <= 5:
                res[2] = True
            elif collide.rect.x + collide.rect.w < self.rect.x + self.rect.w:
                res[1] = collide.rect.x + collide.rect.w
            elif collide.rect.x > self.rect.x:
                res[1] = collide.rect.x - self.rect.w
        return res

    def check_bounds(self):
        self.dx = max(min(self.upper_bound - self.rect.x, 0),
                      max(self.lower_bound - self.rect.x, -1))


class BackGround(pygame.sprite.Sprite):
    def __init__(self, pos_x, *groups):
        super().__init__(*groups)
        self.image = load_image(r'Background\city_background_sunset — копия.png')
        self.rect = self.image.get_rect().move(pos_x, 0)


def generate_level(level, hero_groups, asphalt_groups):
    hero, pos_x, pos_y = None, None, None
    for y in range(len(level)):
        for x in range(len(level[y])):
            if level[y][x] == 'a':
                Asphalt(x, y, *asphalt_groups)
            if level[y][x] == 'H':
                hero = Hero(x, y, *hero_groups)
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
    """Показ титров с последующим выходом из игры"""


def end_screen():
    pass


def move_background(bg_first, bg_second):
    """Перемещение заднего фона"""
    img_width = bg_first.rect.width
    bg_first.rect.x %= -img_width
    bg_second.rect.x %= img_width


def play_game():            # TODO Сделать игру:D ага *****; за буквами следи
    """Запуск игры (игрового цикла)"""

    camera = Camera()
    bg_first, bg_second = BackGround(-4000, all_sprites), BackGround(0, all_sprites)
    hero, hero_pos_x, hero_pos_y = generate_level(load_level('Levels/test_level1.txt'),
                                                  (all_sprites, hero_group),
                                                  (bound_group, all_sprites))

    running_game = True
    while running_game:
        game_time_delta = clock.tick() / 1000
        for event_game in pygame.event.get():
            if event_game.type == pygame.QUIT or (event_game.type == pygame.KEYDOWN and
                                                  event_game.key == pygame.K_ESCAPE):
                pygame_gui.windows.UIConfirmationDialog(
                    rect=pygame.Rect((250, 250), (500, 200)),
                    manager=UIManager,
                    window_title='Подтверждение',
                    action_long_desc='Вы действительно хотите вернуться к Алисе?',
                    action_short_name='О да!',
                    blocking=True
                )
            if event_game.type == pygame.USEREVENT:
                if event_game.user_type == pygame_gui.UI_CONFIRMATION_DIALOG_CONFIRMED:
                    running_game = False

            UIManager.process_events(event_game)

        UIManager.update(game_time_delta)

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
        UIManager.draw_ui(screen)
        pygame.display.flip()

    return


def show_achievements_storage():
    bg = load_image(r'Background/Achievements.jpg')
    screen.blit(bg, (0, 0))

    img_coords = [
        (119, 98), (398, 98), (654, 98),
        (258, 215), (548, 215),
        (145, 359), (398, 359), (651, 359)
    ]
    text_coords = [
        (92, 189), (369, 189), (625, 189),
        (228, 307), (517, 307),
        (115, 451), (368, 451), (622, 451)
    ]

    # Перебираем и отрисовываем достижения
    for i, achievement in enumerate(achievements):
        if achievement[3]:
            text = load_image(f'Achievements/{achievement[1]}')
            img = load_image(f'Achievements/{achievement[0]}')
        else:
            text = load_image(f'Achievements/{achievement[2]}')
            img = load_image('Achievements/Unopened_achievement.png')

        screen.blit(img, img_coords[i])
        screen.blit(text, text_coords[i])

    running_achievements = True

    while running_achievements:
        for event_achievement in pygame.event.get():
            if event_achievement.type == pygame.QUIT or (event_achievement.type == pygame.KEYDOWN and
                                                         event_achievement.key == pygame.K_ESCAPE):
                running_achievements = False

        pygame.display.flip()

    return


def check_saves(page):
    """Вспомогательная функция для экрана с сохранениями, которая возвращает список 9
       булевских значений, каждый из которых True, если соответствующее сохранение на заданной
       странице page существует"""

    return [os.path.isdir(f'Saves/{page}/{cell}') for cell in range(1, 10)]


def load_buttons(page):
    """Вспомогательная функция для экрана с сохранениями, которая возвращает:
       1) результат работы check_saves(page)
       2) список уже расположенных кнопок на заданной странице page с уже заданными надписями,
                в зависимости от того, существует ли соответствующее этой кнопки сохранение или нет
       3) список уже расположенных кнопок для переключения между страницами"""

    saves = check_saves(page)
    buttons = []
    page_buttons = []

    for i in range(3):
        for j in range(3):
            buttons.append(pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect((122 + 209 * j, 74 + 155 * i), (175, 110)),
                manager=UIManager,
                text=f'{3 * i + j + 1}. {"Пусто" if not saves[3 * i + j] else ""}',
                object_id="saved_image_btn"
            ))
            page_buttons.append(pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect(46, 17 + 50 * (i * 3 + j + 1), 40, 40),
                manager=UIManager,
                text=str(i * 3 + j + 1),
                object_id="page_btn" if i * 3 + j + 1 != page else "clicked_page_btn"
            ))

    return saves, buttons, page_buttons


def kill_buttons(arr):
    for btn in arr:
        btn.kill()


def show_load_screen():
    bg = load_image(r'Background/Load_screen.jpg')

    current_page = 1
    saves, buttons, page_buttons = load_buttons(current_page)
    load_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect(171, 522, 209, 48),
        manager=UIManager,
        text='Загрузить',
        object_id="tool_btn"
    )
    remove_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect(440, 522, 209, 48),
        manager=UIManager,
        text='Удалить',
        object_id="tool_btn"
    )
    last_clicked = None

    running_load_screen = True

    while running_load_screen:
        load_time_delta = clock.tick() / 1000
        for event_load in pygame.event.get():
            if event_load.type == pygame.QUIT or (event_load.type == pygame.KEYDOWN and
                                                  event_load.key == pygame.K_ESCAPE):
                running_load_screen = False

            if event_load.type == pygame.USEREVENT:
                # Удаление подтверждено - удаляем сохранение, перезагружаем все кнопки и
                #                                             сбрасываем все выделения и запоминания
                if event_load.user_type == pygame_gui.UI_CONFIRMATION_DIALOG_CONFIRMED:
                    shutil.rmtree(rf'Saves/{current_page}/{last_clicked}')
                    kill_buttons(buttons)
                    kill_buttons(page_buttons)

                    saves, buttons, page_buttons = load_buttons(current_page)
                    bg = load_image(r'Background/Load_screen.jpg')
                    last_clicked = None

                if event_load.user_type == pygame_gui.UI_BUTTON_PRESSED:
                    # Нажата кнопка с сохранением - запомним её номер и визуально выделим ячейку
                    if event_load.ui_element in buttons:
                        i = buttons.index(event_load.ui_element)
                        last_clicked = i + 1
                        bg = load_image(rf'Background/Load_screen_selected_{last_clicked}.jpg')

                    # Нажата кнопка смены страницы - перезагрузим все кнопки, сбросим все выделения
                    #                                                                   и запоминания
                    if event_load.ui_element in page_buttons:
                        kill_buttons(buttons)
                        kill_buttons(page_buttons)

                        current_page = page_buttons.index(event_load.ui_element) + 1
                        saves, buttons, page_buttons = load_buttons(current_page)
                        bg = load_image(r'Background/Load_screen.jpg')
                        last_clicked = None

                    # Нажата кнопка загрузки - если выделено правильное сохранение, загрузим игру
                    if event_load.ui_element == load_btn:
                        if last_clicked is not None and saves[last_clicked - 1]:
                            load_game(rf'Saves/{current_page}/{last_clicked}')

                    # Нажата кнопка удаления - если выделено правильное сохранение, запросим
                    #                                                               подтверждение
                    if event_load.ui_element == remove_btn:
                        if last_clicked is not None and saves[last_clicked - 1]:
                            pygame_gui.windows.UIConfirmationDialog(
                                rect=pygame.Rect((250, 250), (500, 200)),
                                manager=UIManager,
                                window_title='Подтверждение',
                                action_long_desc='Вы действительно хотите удалить это сохранение?',
                                action_short_name='Да',
                                blocking=True
                            )

            UIManager.process_events(event_load)

        # Отрисовываем сначала фон, потом изображения сохранений, затем кнопки
        screen.blit(bg, (0, 0))
        for i in range(3):
            for j in range(3):
                if saves[3 * i + j]:
                    img = load_image(rf'{current_page}\{3 * i + j + 1}\preview.jpg',
                                     directory='Saves')
                    screen.blit(img, (122 + 209 * j, 74 + 155 * i))
        UIManager.update(load_time_delta)
        UIManager.draw_ui(screen)
        pygame.display.flip()

    # Перед возвращением в меню, удалим все созданные кнопки
    kill_buttons(buttons)
    kill_buttons(page_buttons)
    load_btn.kill()
    remove_btn.kill()
    return


def load_game(path):    # TODO Реализовать загрузку
    pass


if __name__ == '__main__':
    # Инициализация
    pygame.init()
    SIZE = WIDTH, HEIGHT = 800, 600
    FPS = 60
    screen = pygame.display.set_mode(SIZE)

    # Список достижений [(имя изображения, имя открытой напдиси, имя закрытой надписи,
    #                                                            получено/не получено)]
    achievements = [('test_img.png', 'test_font_opened.png', 'test_font_unopened.png', False)] * 8

    pygame.display.set_caption('Everlasting Mario')
    pygame.display.set_icon(load_image(r'Sprites\Semen\Idle (7).png'))

    # Константы для позиционирования объктов
    TILE_WIDTH, TILE_HEIGHT = 50, 50

    # Создаём менеджер интерфейса с темой для красивого отображения элементов
    UIManager = pygame_gui.UIManager(SIZE, 'base_theme.json')
    # Создаём кнопки
    start_game_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.rect.Rect((46, 53), (300, 60)),
        text='Начать игру',
        manager=UIManager,
    )
    load_game_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.rect.Rect((46, 153), (300, 60)),
        text='Загрузить',
        manager=UIManager
    )
    show_achievements_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.rect.Rect((46, 253), (300, 60)),
        text='Достижения',
        manager=UIManager
    )
    exit_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.rect.Rect((46, 353), (300, 60)),
        text='Выйти',
        manager=UIManager
    )

    # Фон меню
    image_menu = load_image(r'Background\Menu_normal.jpg')

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

                # Изменяем фон в зависимости он наведённости на одну из кнопок
                if event.user_type == pygame_gui.UI_BUTTON_ON_UNHOVERED:
                    image_menu = load_image(r'Background\Menu_normal.jpg')
                if event.user_type == pygame_gui.UI_BUTTON_ON_HOVERED:
                    if event.ui_element == start_game_btn:
                        image_menu = load_image(r'Background\Menu_play.jpg')
                    if event.ui_element == load_game_btn:
                        image_menu = load_image(r'Background\Menu_surprised.jpg')
                    if event.ui_element == show_achievements_btn:
                        image_menu = load_image(r'Background\Menu_embarrassed.jpg')
                    if event.ui_element == exit_btn:
                        image_menu = load_image(r'Background\Menu_angry.jpg')

                if event.user_type == pygame_gui.UI_BUTTON_PRESSED:
                    start_game_btn.hide()
                    show_achievements_btn.hide()
                    load_game_btn.hide()
                    exit_btn.hide()

                    if event.ui_element == start_game_btn:
                        # Создание спарйт-групп
                        bound_group = pygame.sprite.Group()
                        hero_group = pygame.sprite.Group()
                        enemy_group = pygame.sprite.Group()
                        whero_group = pygame.sprite.Group()
                        all_sprites = pygame.sprite.Group()

                        play_game()
                    if event.ui_element == load_game_btn:
                        show_load_screen()
                    if event.ui_element == show_achievements_btn:
                        show_achievements_storage()
                    if event.ui_element == exit_btn:
                        confirm_exit()

                    start_game_btn.show()
                    show_achievements_btn.show()
                    load_game_btn.show()
                    exit_btn.show()

            UIManager.process_events(event)

        UIManager.update(time_delta)
        screen.blit(image_menu, (0, 0))
        UIManager.draw_ui(screen)
        pygame.display.flip()

    terminate()
