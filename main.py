import pygame
import os
import sys
import pygame_gui
import math
import shutil
import random
import datetime


class ExitToMenuException(Exception):
    pass


class AnimatedSprite(pygame.sprite.Sprite):
    def __init__(self, sheet, columns, rows, *groups):
        super().__init__(*groups)
        self.cnt_frames = 0
        self.frames_lefts = []
        self.frames_rights = []
        self.static_timer = 50
        self.timer = self.static_timer
        self.cut_sheet(sheet, columns, rows)
        self.is_rotate = False
        self.cur_frame = 0
        self.image = self.frames_rights[self.cur_frame]

    def cut_sheet(self, sheet, columns, rows):
        self.rect = pygame.Rect(0, 0, sheet.get_width() // columns,
                                sheet.get_height() // rows)
        for j in range(rows):
            for i in range(columns):
                frame_location = (self.rect.w * i, self.rect.h * j)
                self.frames_rights.append(sheet.subsurface(pygame.Rect(
                    frame_location, self.rect.size)))
                self.frames_lefts.append(pygame.transform.flip(self.frames_rights[-1], True, False))
        self.cnt_frames = len(self.frames_lefts)

    def set_timer(self, m):
        self.static_timer = m
        self.timer = self.static_timer

    def update(self, *args):
        if self.timer == 0:
            self.cur_frame = (self.cur_frame + 1) % self.cnt_frames
            if self.is_rotate:
                self.image = self.frames_lefts[self.cur_frame]
            else:
                self.image = self.frames_rights[self.cur_frame]
            self.timer = self.static_timer
        else:
            self.timer -= 1


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


class Bound(pygame.sprite.Sprite):
    def __init__(self, pos_x, pos_y, bound_image, *groups):
        super().__init__(*groups)
        self.image = load_image(bound_image)
        self.rect = self.image.get_rect().move(
            TILE_WIDTH * pos_x, TILE_HEIGHT * pos_y)


class Book(pygame.sprite.Sprite):
    def __init__(self, pos_x, pos_y, *groups):
        super().__init__(*groups)
        self.image = load_image(r"Background\Constructions\redbook.png")
        self.rect = self.image.get_rect().move(TILE_WIDTH * pos_x, TILE_HEIGHT * pos_y + 10)
        self.mask = pygame.mask.from_surface(self.image)


class BackGround(pygame.sprite.Sprite):
    def __init__(self, pos_x, background_image, *groups):
        super().__init__(*groups)
        self.image = load_image(background_image)
        self.rect = self.image.get_rect().move(pos_x, 0)
        self.mask = pygame.mask.from_surface(self.image)


class Projectile(pygame.sprite.Sprite):
    def __init__(self, x, y, sprite, route, *groups):
        super().__init__(*groups)
        self.image = load_image(sprite)
        self.rect = self.image.get_rect().move(x, y)
        self.route = route
        self.vx = 100
        self.vx_timer = 1

        self.mask = pygame.mask.from_surface(self.image)

    def update(self):
        collides = pygame.sprite.spritecollide(self, bound_group, False)
        for sprite in collides:
            if pygame.sprite.collide_mask(self, sprite):
                self.kill()

        if self.vx_timer % 3 < 2 and self.route == 'Right':
            self.rect.x += math.ceil(self.vx / FPS)
        if self.vx_timer % 3 < 2 and self.route == 'Left':
            self.rect.x -= math.ceil(self.vx / FPS)
        self.vx_timer = (self.vx_timer + 1) % 3


class BaseEnemy(AnimatedSprite):
    def __init__(self, sheet, columns, rows, pos_x, pos_y, *groups):
        super().__init__(sheet, columns, rows, *groups)
        self.set_timer(60)
        self.absolute_x = pos_x * TILE_WIDTH
        self.rect = self.image.get_rect().move(pos_x * TILE_WIDTH,
                                               pos_y * TILE_HEIGHT - self.image.get_height() // 2)
        self.state = True

        # Начальная скорость, счетчик действий для горизонтального движения
        self.vx = 50
        self.vx_timer = 1

        # Начальная скорость, счетчик действий для падения
        self.down_vy = 0
        self.down_timer = 0

        # Начальная скорость, счетчик действий для прыжка
        self.jump_vy = 0
        self.jump_timer = 0

        self.mask = pygame.mask.from_surface(self.image)

    def update(self, directions):
        motion = False  # Двигался ли герой
        in_jump, in_fall = False, False  # Что бы нельзя было прыгать в воздухе

        # Если идёт "анимация" прыжка
        if self.jump_timer != 0:
            in_fall = True
            # Если мы ни во что не упираемся сверху
            if 2 not in collide_asphalt(self):
                if self.jump_timer % 3 < 2:
                    self.rect.y -= math.ceil(self.jump_vy / FPS)
                    self.jump_vy -= 1
                self.jump_timer -= 1
            else:
                self.jump_vy = 0
                self.jump_timer = 0

        # Если персонаж не пересекается с асфальтом снизу или сбоку, значит он падает
        elif 1 not in (collide := collide_asphalt(self)) and 0 not in collide:
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
        if pygame.K_RIGHT in directions:
            if (self.jump_timer % 3 < 2 and in_jump) or (self.down_timer % 3 < 2 and in_fall) or \
                    (not in_jump and not in_fall and self.vx_timer % 3 < 2):
                self.is_rotate = False
                super().update()
                self.rect.x += math.ceil(self.vx / FPS)
                self.absolute_x += math.ceil(self.vx / FPS)
                motion = True
            self.vx_timer = (self.vx_timer + 1) % 3
        if pygame.K_LEFT in directions:
            if (self.jump_timer % 3 < 2 and in_jump) or (self.down_timer % 3 < 2 and in_fall) or \
                    (not in_jump and not in_fall and self.vx_timer % 3 < 2):
                self.is_rotate = True
                super().update()
                self.absolute_x -= math.ceil(self.vx / FPS)
                self.rect.x -= math.ceil(self.vx / FPS)
                motion = True
            self.vx_timer = (self.vx_timer + 1) % 3
        if pygame.K_UP in directions and not in_jump and not in_fall:
            motion = True
            self.jump_vy = 125
            self.jump_timer = 2 * self.jump_vy

        if not motion and self.cur_frame != 0:
            super().update()
        if motion and self.is_rotate:
            self.image = self.frames_lefts[self.cur_frame]
        elif motion and not self.is_rotate:
            self.image = self.frames_rights[self.cur_frame]

        if in_fall or in_jump:
            self.state = False
        else:
            self.state = True

        # Если после перемещения, персонаж начинает пересекаться с асфальтом справа или слева,
        # то перемещаем его в самое близкое положение, шде он не будет пересекаться с асфальтом
        if 1 in (collide := collide_asphalt(self)):
            old_x = self.rect.x
            self.rect.x = collide[1]
            self.absolute_x += self.rect.x - old_x
            return True

        return False


class Enemy(BaseEnemy):
    def __init__(self, sheet, columns, rows, pos_x, pos_y, *groups):
        super().__init__(sheet, columns, rows, pos_x, pos_y, *groups)
        self.left_bound = TILE_WIDTH * (pos_x - random.randint(min(3, pos_x), min(6, pos_x)))
        self.right_bound = TILE_WIDTH * (pos_x + random.randint(3, 5))
        self.is_go_left = True

        self.timer_damage = 200
        self.cur_timer_damage = 0

    def update(self, *args):
        if self.cur_timer_damage > 0:
            self.cur_timer_damage -= 1

        swap = False

        collide = super().update([pygame.K_LEFT if self.is_go_left else pygame.K_RIGHT])

        if self.absolute_x >= self.right_bound:
            swap = True
            self.is_go_left = True
        if self.absolute_x <= self.left_bound:
            swap = True
            self.is_go_left = False

        if collide and not swap:
            self.is_go_left = not self.is_go_left
        collide_projectiles = pygame.sprite.spritecollide(self, projectile_group, False)
        for sprite in collide_projectiles:
            if pygame.sprite.collide_mask(self, sprite):
                self.kill()
                sprite.kill()


class Hero(BaseEnemy):
    def __init__(self, sheet, columns, rows, pos_x, pos_y, *groups):
        super().__init__(sheet, columns, rows, pos_x, pos_y, *groups)
        self.set_timer(30)
        self.counter_books = 0
        self.health = 100

        # Задаем границы для камеры и изменение координат героя при выходе за границы
        self.lower_bound = 200
        self.upper_bound = 600
        self.dx = 0

        # Частота Снарядов
        self.projectile_timer = 500
        self.projectile_current_time = 0

    def update(self, *args):
        keys = pygame.key.get_pressed()
        directions = []
        for key in [pygame.K_RIGHT, pygame.K_LEFT, pygame.K_UP]:
            if keys[key]:
                directions.append(key)
        super().update(directions)

        # Проверка пересечения с книгами
        books = pygame.sprite.spritecollide(self, book_group, False)
        for book in books:
            if pygame.sprite.collide_mask(self, book):
                self.counter_books += 1
                book.kill()

        # Выпускание снаряда
        if keys[pygame.K_SPACE] and self.projectile_current_time == 0:
            if self.is_rotate:
                Projectile(self.rect.x, self.rect.y + 10,
                           r'Background\Constructions\bag.png', 'Left',
                           all_sprites, projectile_group)
            else:
                Projectile(self.rect.x + self.rect.w, self.rect.y + 10,
                           r'Background\Constructions\bag.png', 'Right',
                           all_sprites, projectile_group)

            self.projectile_current_time = self.projectile_timer

        if self.projectile_current_time > 0:
            self.projectile_current_time -= 1

        collides = pygame.sprite.spritecollide(self, enemy_group, False)
        for sprite in collides:
            if pygame.sprite.collide_mask(self, sprite) and sprite.cur_timer_damage == 0:
                self.health -= 20
                sprite.cur_timer_damage = sprite.timer_damage
        self.check_bounds()

    def check_bounds(self):
        self.dx = max(min(self.upper_bound - self.rect.x, 0),
                      max(self.lower_bound - self.rect.x, -1))


def collide_asphalt(sprite):
    """Проверяет пересечение с асфальтом и возвращает словарь в котором ключами будут:
        0, если персонаж пересекается с асфальтом снизу,
        1, если пересекается с асфальтом справа или слева,
        2, если пересекается с асфальтом сверху"""

    res = {}
    for collide in pygame.sprite.spritecollide(sprite, bound_group, False):
        if abs(collide.rect.y - sprite.rect.y - sprite.rect.h) <= 5:
            res[0] = True
        elif abs(collide.rect.y + collide.rect.h - sprite.rect.y) <= 5:
            res[2] = True
        elif collide.rect.x + collide.rect.w < sprite.rect.x + sprite.rect.w:
            res[1] = collide.rect.x + collide.rect.w
        elif collide.rect.x > sprite.rect.x:
            res[1] = collide.rect.x - sprite.rect.w
    return res


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


def generate_level(level, hero_groups, asphalt_groups):
    # H - герой, a - асфальт, b - книга, E - враг, i - невидимая стена, c - checkpoint место где герои разговаривают
    hero, pos_x, pos_y, cnt_books, coord_checkpoints, cur_checkpoint, exit_pos = None, None, None, 0, [], 0, 0
    for y in range(len(level)):
        for x in range(len(level[y])):
            if level[y][x] == 'a':
                Bound(x, y, r'Background/Constructions/asphalt.png', *asphalt_groups)
            if level[y][x] == 'H':
                hero = Hero(load_image(r"Sprites\Semen\Semen_variant2.1.png"), 8, 2, x, y, *hero_groups)
                pos_x, pos_y = x, y
            if level[y][x] == 'b':
                cnt_books += 1
                Book(x, y, all_sprites, book_group)
            if level[y][x] == "E":
                Enemy(load_image(r"Sprites\Semen\Semen-test2.png"), 4, 1, x, y,
                      enemy_group, all_sprites)
            if level[y][x] == 'i':
                Bound(x, y, r'Background\Constructions\empty.png', bound_group, invisible_bound)
            if level[y][x] == 'g':
                Bound(x, y, r'Background\Constructions\ground.jpg', *asphalt_groups)
            if level[y][x] == 'c':
                coord_checkpoints.append((cur_checkpoint + 1, x * TILE_WIDTH))
                cur_checkpoint += 1
            if level[y][x] == 'e':
                exit_pos = TILE_WIDTH * x
    hero.all_books = cnt_books
    return hero, pos_x, pos_y, coord_checkpoints, exit_pos


def draw_hero_data(hero):
    text = COUNTER_BOOKS_FONT.render(f"Собрано книг: {hero.counter_books}/{hero.all_books}, "
                                     f"{hero.health}", True, (125, 0, 0))
    screen.blit(text, (0, 0))


def terminate():
    pygame.quit()
    sys.exit()


def confirm_exit():
    message = 'Вы действительно хотите '
    if CURRENT_THEME == 'OD':
        message += 'таскать мешки с сахаром?'
    elif CURRENT_THEME == 'Alisa':
        message += 'быть побитым гитарой?'
    elif CURRENT_THEME == 'Miku':
        message += 'попасть под обстрел словами?'
    elif CURRENT_THEME == 'Lena':
        message = 'Вдоль, а не поперек, верно?'
    elif CURRENT_THEME == 'Ulyana':
        message += 'обнаружить сороконожку под котлетой?'
    elif CURRENT_THEME == 'Slavya':
        message += 'подметать площадь все оставшиеся дни смены?'
    elif CURRENT_THEME == 'Zhenya':
        message += 'получить Достоевским по голове?'
    elif CURRENT_THEME == 'UVAO':
        message += 'быть расцарапаным с ног до головы?'
    pygame_gui.windows.UIConfirmationDialog(
        rect=pygame.Rect((250, 250), (500, 200)),
        manager=UIManager,
        window_title='Подтверждение',
        action_long_desc=message,
        action_short_name='Да!',
        blocking=True,
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


def active_pause_menu(image=None):
    # Запоминаем исходное изображение экране, уменьшенное до нужных размеров,
    # чтобы в случае сохранения сохранить его в качестве превью
    if image is None:
        preview_to_save = pygame.transform.scale(screen, (175, 110))
        screen.blit(load_image(r'Background/Dark.png'), (0, 0))
        bg = screen.copy()
    else:
        preview_to_save = pygame.transform.scale(image, (175, 110))
        image.blit(load_image(r'Background/Dark.png'), (0, 0))
        bg = image.copy()

    # Создаём кнопки
    release_pause_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.rect.Rect((46, 53), (350, 60)),
        text='Продолжить',
        manager=UIManager
    )
    save_game_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.rect.Rect((46, 153), (350, 60)),
        text='Сохранить',
        manager=UIManager
    )
    load_game_from_pause_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.rect.Rect((46, 253), (350, 60)),
        text='Загрузить',
        manager=UIManager
    )
    exit_to_menu_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.rect.Rect((46, 353), (350, 60)),
        text='Выйти в меню',
        manager=UIManager
    )
    exit_from_pause_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.rect.Rect((46, 453), (350, 60)),
        text='Выйти из игры',
        manager=UIManager
    )

    pause_activated = True
    quit_game = False  # Чтобы не спутать подтверждение диалога выхода из игры и выхода в меню

    while pause_activated:
        pause_time_delta = clock.tick() / 1000
        for event_pause in pygame.event.get():
            if event_pause.type == pygame.QUIT or (event_pause.type == pygame.KEYDOWN and
                                                   event_pause.key == pygame.K_ESCAPE):
                pause_activated = False

            # Закрываем игру или возвращаем константу, которая даст сигнал о выходе в меню,
            # в зависимости от подтверждённого диалога (что сделать нам помогает quit_game)
            if event_pause.type == pygame.USEREVENT:
                if event_pause.user_type == pygame_gui.UI_CONFIRMATION_DIALOG_CONFIRMED:
                    kill_buttons([release_pause_btn, save_game_btn, load_game_from_pause_btn,
                                  exit_to_menu_btn, exit_from_pause_btn])
                    if quit_game:
                        if CURRENT_THEME != 'Pioneer':
                            terminate()
                        else:

                            set_bus_to_hell()
                            raise ExitToMenuException

                    else:
                        raise ExitToMenuException

                if event_pause.user_type == pygame_gui.UI_BUTTON_PRESSED:
                    # Попытка выхода из игры - запрашиваем подтверждение
                    if event_pause.ui_element == exit_from_pause_btn:
                        pygame_gui.windows.UIConfirmationDialog(
                            rect=pygame.Rect(250, 250, 500, 200),
                            manager=UIManager,
                            window_title='Подтверждение',
                            action_short_name='Да',
                            action_long_desc='Вы действительно хотите выйти из игры?',
                            blocking=True
                        )
                        quit_game = True

                    # Попытка выхода в меню - запрашиваем подтверждение
                    if event_pause.ui_element == exit_to_menu_btn:
                        quit_game = False
                        names = {'Alisa': 'Алисе', 'Miku': 'Мику', 'Lena': 'Лене', 'Slavya': 'Славе',
                                 'Ulyana': 'Ульяне', 'Zhenya': 'Жене', 'UVAO': 'Юле',
                                 'Pioneer': 'Пионеру',
                                 'OD': 'Ольге Дмитриевне'}
                        pygame_gui.windows.UIConfirmationDialog(
                            rect=pygame.Rect((250, 250), (500, 200)),
                            manager=UIManager,
                            window_title='Подтверждение',
                            action_long_desc=f'Вы действительно хотите вернуться к '
                                             f'{names[CURRENT_THEME]}?',
                            action_short_name='О да!',
                            blocking=True
                        )

                    # Выходим из режима паузы
                    if event_pause.ui_element == release_pause_btn:
                        pause_activated = False

                    # Запускаем меню загрузки/сохранения, предварительно убрав с экрана кнопки
                    if event_pause.ui_element == load_game_from_pause_btn or \
                            event_pause.ui_element == save_game_btn:
                        for btn in [release_pause_btn, save_game_btn, load_game_from_pause_btn,
                                    exit_to_menu_btn, exit_from_pause_btn]:
                            btn.hide()

                        if event_pause.ui_element == load_game_from_pause_btn:
                            show_load_screen(ask_for_confirm=True)
                        else:
                            show_load_screen(save_instead_of_load=True, preview=preview_to_save)

                        for btn in [release_pause_btn, save_game_btn, load_game_from_pause_btn,
                                    exit_to_menu_btn, exit_from_pause_btn]:
                            btn.show()

            UIManager.process_events(event_pause)

        screen.fill((0, 0, 0))
        screen.blit(bg, (0, 0))
        UIManager.update(pause_time_delta)
        UIManager.draw_ui(screen)
        pygame.display.flip()

    kill_buttons([release_pause_btn, save_game_btn, load_game_from_pause_btn, exit_to_menu_btn,
                  exit_from_pause_btn])
    return


def show_dialog(data):
    """Принимает список кортежей [(Имя говорящего, фраза)]"""
    bg = screen.copy()

    ln = len(data)
    cur_phrase = 0
    text_box = pygame_gui.elements.ui_text_box.UITextBox(
        relative_rect=pygame.Rect(50, 490, 700, 110),
        manager=UIManager,
        html_text='',
        object_id='#dialog_text_box'
    )

    while True:
        dialog_time_delta = clock.tick() / 1000
        for event_dialog in pygame.event.get():
            if event_dialog.type == pygame.QUIT or (event_dialog.type == pygame.KEYDOWN and
                                                    event_dialog.key == pygame.K_ESCAPE):
                x = screen.copy()
                text_box.hide()
                active_pause_menu(x)
                text_box.show()

            elif event_dialog.type == pygame.MOUSEBUTTONDOWN:
                if event_dialog.button == pygame.BUTTON_WHEELUP:
                    cur_phrase = max(0, cur_phrase - 1)
                elif event_dialog.button == pygame.BUTTON_LEFT:
                    cur_phrase += 1
            elif event_dialog.type == pygame.KEYDOWN and event_dialog.key == pygame.K_SPACE:
                cur_phrase += 1

            UIManager.process_events(event_dialog)

        if cur_phrase >= ln:
            text_box.kill()
            return

        if data[cur_phrase][0] == "Комм":
            text_box.html_text = data[cur_phrase][1]
        else:
            text_box.html_text = "<font color='#5F9EA0'>" + data[cur_phrase][0] + ':</font><br>- ' + \
                                 data[cur_phrase][1]
        text_box.rebuild()

        UIManager.update(dialog_time_delta)
        screen.blit(bg, (0, 0))
        UIManager.draw_ui(screen)
        pygame.display.flip()


def get_level_dialog(level):
    dialogs = []
    file_story = open(fr"Data\Story\Level{level}\story.txt", "r", encoding='utf-8').readlines()
    tmp_dialogs = []
    for i in file_story:
        i = i.strip()
        if i == '!next!':
            dialogs.append(tmp_dialogs)
            tmp_dialogs = []
        else:
            tmp_dialogs.append((i[0:i.find('$$') - 1], i[i.find('$$') + 2: -1]))
    return dialogs


def level_1():
    camera = Camera()
    bg_first = BackGround(-4000, r'Background\city_background_sunset — копия.png', [all_sprites, background_group])
    bg_second = BackGround(0, r'Background\city_background_sunset — копия.png', [all_sprites, background_group])
    hero, hero_pos_x, hero_pos_y, coord_checkpoints, exit_pos = generate_level(load_level('Levels/test_level1'),
                                                                     (all_sprites, hero_group),
                                                                     (bound_group, all_sprites))

    without_enemies_group = pygame.sprite.Group()
    for sprite in all_sprites.sprites():
        if not isinstance(sprite, Enemy):
            without_enemies_group.add(sprite)

    tmp = [2, 3, 1, 4, 5]
    queue_dialogs = [0 for i in range(len(tmp))]
    dialogs_text = get_level_dialog(1)
    for cnt, x in coord_checkpoints:
        queue_dialogs[tmp.index(cnt)] = x

    running_game = True
    cur_dialog = []
    dialog_number = 0
    while running_game:
        game_time_delta = clock.tick() / 1000

        if hero.health <= 0:
            return "death"

        if hero.absolute_x <= exit_pos <= hero.absolute_x + hero.rect.w and len(queue_dialogs) == dialog_number:
            return "passed"

        print(exit_pos)
        if dialog_number < len(dialogs_text) and hero.state and \
                hero.absolute_x <= queue_dialogs[dialog_number] <= hero.absolute_x + hero.rect.w:
            if dialog_number >= 3 and hero.counter_books == hero.all_books:
                cur_dialog = dialogs_text[dialog_number]
                dialog_number += 1
            elif dialog_number <= 2:
                cur_dialog = dialogs_text[dialog_number]
                dialog_number += 1

        if dialog_number <= 2 or enemy_group.sprites():
            for sprite in projectile_group.sprites():
                sprite.kill()

        for event_game in pygame.event.get():
            if event_game.type == pygame.QUIT or (event_game.type == pygame.KEYDOWN and
                                                  event_game.key == pygame.K_ESCAPE):
                try:
                    active_pause_menu()
                except ExitToMenuException:
                    running_game = False

            UIManager.process_events(event_game)
            all_sprites.update()

        UIManager.update(game_time_delta)
        all_sprites.update()

        # Движение BackGround`а (бесконечный фон)
        move_background(bg_first, bg_second)

        camera.update(hero)
        # обновляем положение всех спрайтов
        for sprite in all_sprites:
            camera.apply(sprite)
        for sprite in invisible_bound:
            camera.apply(sprite)

        screen.fill((0, 0, 0))

        if dialog_number <= 2:
            without_enemies_group.draw(screen)
            hero.health = 100
        else:
            all_sprites.draw(screen)

        UIManager.draw_ui(screen)
        pygame.display.flip()
        if cur_dialog:
            try:
                show_dialog(cur_dialog)
            except ExitToMenuException:
                running_game = False
            cur_dialog = []

        if dialog_number > 2:
            draw_hero_data(hero)
    return


def play_game(level):  # TODO Сделать игру:D ага *****; за буквами следи;
    """Запуск игры (игрового цикла)"""

    if level == 1:
        return level_1()
    camera = Camera()
    bg_first = BackGround(-4000, r'Background\city_background_sunset — копия.png', all_sprites)
    bg_second = BackGround(0, r'Background\city_background_sunset — копия.png', all_sprites)
    hero, hero_pos_x, hero_pos_y, coord_checkpoints = generate_level(load_level('Levels/test_level1.txt'),
                                                  (all_sprites, hero_group),
                                                  (bound_group, all_sprites))
    running_game = True
    cur_dialog = []
    while running_game:
        game_time_delta = clock.tick() / 1000

        if hero.health <= 0:
            return

        for event_game in pygame.event.get():
            if event_game.type == pygame.QUIT or (event_game.type == pygame.KEYDOWN and
                                                  event_game.key == pygame.K_ESCAPE):
                try:
                    active_pause_menu()
                except ExitToMenuException:
                    running_game = False

            UIManager.process_events(event_game)
            all_sprites.update()

        UIManager.update(game_time_delta)
        all_sprites.update()

        # Движение BackGround`а (бесконечный фон)
        move_background(bg_first, bg_second)

        camera.update(hero)
        # обновляем положение всех спрайтов
        for sprite in all_sprites:
            camera.apply(sprite)
        for sprite in invisible_bound:
            camera.apply(sprite)

        screen.fill((0, 0, 0))

        all_sprites.draw(screen)
        hero_group.draw(screen)
        draw_hero_data(hero)
        UIManager.draw_ui(screen)
        pygame.display.flip()
        if cur_dialog:
            try:
                show_dialog(cur_dialog)
            except ExitToMenuException:
                running_game = False
            cur_dialog = []

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
            if saves[3 * i + j]:
                with open(rf'Saves/{page}/{3 * i + j + 1}/date.txt', 'r', encoding='utf-8') as f:
                    date = f.read()
            else:
                date = 'Пусто'
            buttons.append(pygame_gui.elements.UIButton(
                relative_rect=pygame.Rect((122 + 209 * j, 74 + 155 * i), (175, 110)),
                manager=UIManager,
                text=f'{3 * i + j + 1}. {date}',
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


def show_load_screen(ask_for_confirm=False, save_instead_of_load=False, preview=None):
    """ask_for_confirm - запрашивать ли подтверждение при загрузке
       (подтверждение необходимо в случае загрузки из меню паузы)

       Если save_instead_of_load is True, тогда будет кнопка загрузить, вместо кнопки загрузки

       Также если save_instead_of_load is True,
                  необходимо передать preview - превью нового сохранения"""

    bg = load_image(r'Background/Load_screen.jpg')

    current_page = 1
    saves, buttons, page_buttons = load_buttons(current_page)
    func_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect(171, 522, 209, 48),
        manager=UIManager,
        text='Загрузить' if save_instead_of_load is False else 'Сохранить',
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
    confirm_func = False  # Чтобы не запутаться, подтверждён ли диалог удаления или
    #                                                                 загрузки/сохранения

    while running_load_screen:
        load_time_delta = clock.tick() / 1000
        for event_load in pygame.event.get():
            if event_load.type == pygame.QUIT or (event_load.type == pygame.KEYDOWN and
                                                  event_load.key == pygame.K_ESCAPE):
                running_load_screen = False

            if event_load.type == pygame.USEREVENT:
                # Если confirm_func is True, тогда подтверждена загрузка/сохранение, и мы
                # загружаем/сохраняем игру, иначе подтверждено удаление - удаляем сохранение,
                # перезагружаем все кнопки и сбрасываем все выделения и запоминания
                if event_load.user_type == pygame_gui.UI_CONFIRMATION_DIALOG_CONFIRMED:
                    if confirm_func:
                        if save_instead_of_load:
                            # Подтверждена попытка перезаписи сохранения
                            save_game(current_page, last_clicked, preview, overwrite=True)
                        else:
                            # Подтверждена загрузка сохранения
                            load_game(rf'Saves/{current_page}/{last_clicked}')
                    else:
                        # Подтверждено удаление сохранения
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

                    # Нажата кнопка загрузки - если выделено правильное сохранение, тогда,
                    # если необходимо подтвержение (ask_to_confirm), запросим подтверждение,
                    # иначе - загрузим игру
                    if event_load.ui_element == func_btn:
                        if save_instead_of_load and last_clicked is not None:
                            if saves[last_clicked - 1]:
                                # Попытка перезаписи сохранения - запросим подтверждение
                                confirm_func = True
                                pygame_gui.windows.UIConfirmationDialog(
                                    rect=pygame.Rect((250, 250), (500, 200)),
                                    manager=UIManager,
                                    window_title='Подтверждение',
                                    action_long_desc='Вы действительно хотите '
                                                     'перезаписать это сохранение?',
                                    action_short_name='Да',
                                    blocking=True
                                )
                            else:
                                # Сохранение в новым слот - подтверждение не требуется
                                save_game(current_page, last_clicked, preview)
                                kill_buttons(buttons)
                                kill_buttons(page_buttons)

                                saves, buttons, page_buttons = load_buttons(current_page)
                                bg = load_image(r'Background/Load_screen.jpg')
                                last_clicked = None

                        else:
                            if last_clicked is not None and saves[last_clicked - 1]:
                                if ask_for_confirm:
                                    # Необходимо подтверждение загрузки
                                    confirm_func = True
                                    pygame_gui.windows.UIConfirmationDialog(
                                        rect=pygame.Rect((250, 250), (500, 200)),
                                        manager=UIManager,
                                        window_title='Подтверждение',
                                        action_long_desc='Вы действительно хотите '
                                                         'загрузить это сохранение?',
                                        action_short_name='Да',
                                        blocking=True
                                    )
                                else:
                                    # Загружаем
                                    load_game(rf'Saves/{current_page}/{last_clicked}')

                    # Нажата кнопка удаления - если выделено правильное сохранение, запросим
                    #                                                               подтверждение
                    if event_load.ui_element == remove_btn:
                        confirm_func = False
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
    func_btn.kill()
    remove_btn.kill()
    return


def save_game(page, cell, preview, overwrite=False):
    if overwrite:
        shutil.rmtree(rf'Saves/{page}/{cell}')

    os.makedirs(rf'Saves/{page}/{cell}')
    pygame.image.save(preview, rf'Saves/{page}/{cell}/preview.jpg')
    with open(rf'Saves/{page}/{cell}/date.txt', 'w', encoding='utf-8') as f:
        f.write(datetime.datetime.now().strftime("%d.%m.%Y %H:%M"))


def load_game(path):  # TODO Реализовать загрузку
    pass


def set_bus_to_hell():
    global bus_to_hell, image_menu

    bus_to_hell = True
    start_game_btn.hide()
    show_achievements_btn.hide()
    load_game_btn.hide()
    exit_btn.hide()
    pygame_gui.windows.ui_message_window.UIMessageWindow(
        rect=pygame.Rect((150, 170), (550, 250)),
        manager=UIManager,
        window_title="Выхода нет!",
        html_message=f"Тебе не сбежать отсюда, "
                     f"{os.getlogin()}! "
                     f"Наш автобус отправляется в ад! "
                     f"Аха-ха-ха!"
    )
    image_menu = load_image(rf'Background\Menu\{CURRENT_THEME}\Menu_you_cant_escape.jpg')


if __name__ == '__main__':
    # Разнообразие в студию!
    CURRENT_THEME = random.choice(
        ['Alisa'] * 400 +  # 40%
        ['Miku'] * 250 +  # 25%
        ['Lena'] * 100 +  # 10%
        ['Ulyana'] * 100 +  # 10%
        ['Slavya'] * 50 +  # 5%
        ['UVAO'] * 40 +  # 4%
        ['Zhenya'] * 30 +  # 3%
        ['OD'] * 29 +  # 2.9%
        ['Pioneer']  # 0.1%
    )

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
    # Константа шрифта
    COUNTER_BOOKS_FONT = pygame.font.Font(None, 35)

    # Создаём менеджер интерфейса с темой для красивого отображения элементов
    UIManager = pygame_gui.UIManager(SIZE, rf'Data/Themes/theme_{CURRENT_THEME}.json')
    # Создаём кнопки
    start_game_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.rect.Rect((46, 53), (300, 60)),
        text='Начать игру',
        manager=UIManager
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
    image_menu = load_image(rf'Background\Menu\{CURRENT_THEME}\Menu_normal.jpg')

    running = True
    bus_to_hell = False

    clock = pygame.time.Clock()

    while running:
        time_delta = clock.tick(FPS) / 1000
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                if bus_to_hell:
                    running = False
                else:
                    if CURRENT_THEME == 'Pioneer':
                        set_bus_to_hell()
                    else:
                        confirm_exit()
            if event.type == pygame.USEREVENT:
                if event.user_type == pygame_gui.UI_CONFIRMATION_DIALOG_CONFIRMED:
                    running = False

                if not bus_to_hell:
                    # Изменяем фон в зависимости он наведённости на одну из кнопок
                    if event.user_type == pygame_gui.UI_BUTTON_ON_UNHOVERED:
                        image_menu = load_image(rf'Background\Menu\{CURRENT_THEME}\Menu_normal.jpg')
                    if event.user_type == pygame_gui.UI_BUTTON_ON_HOVERED:
                        if event.ui_element == start_game_btn:
                            image_menu = \
                                load_image(rf'Background\Menu\{CURRENT_THEME}\Menu_play.jpg')
                        if event.ui_element == load_game_btn:
                            image_menu = \
                                load_image(rf'Background\Menu\{CURRENT_THEME}\Menu_load.jpg')
                        if event.ui_element == show_achievements_btn:
                            image_menu = \
                                load_image(rf'Background\Menu\{CURRENT_THEME}\Menu_achievements.jpg')
                        if event.ui_element == exit_btn:
                            image_menu = \
                                load_image(rf'Background\Menu\{CURRENT_THEME}\Menu_exit.jpg')
                            if CURRENT_THEME == 'Lena':
                                Lenas_instability = random.randrange(0, 100)
                                if Lenas_instability >= 80:
                                    image_menu = load_image(
                                        rf'Background\Menu\{CURRENT_THEME}\Menu_exit_knife.jpg')

                if event.user_type == pygame_gui.UI_BUTTON_PRESSED:
                    start_game_btn.hide()
                    show_achievements_btn.hide()
                    load_game_btn.hide()
                    exit_btn.hide()

                    if event.ui_element == start_game_btn:
                        # Создание спарйт-групп
                        bound_group = pygame.sprite.Group()
                        background_group = pygame.sprite.Group()
                        hero_group = pygame.sprite.Group()
                        enemy_group = pygame.sprite.Group()
                        whero_group = pygame.sprite.Group()
                        all_sprites = pygame.sprite.Group()
                        book_group = pygame.sprite.Group()
                        projectile_group = pygame.sprite.Group()
                        invisible_bound = pygame.sprite.Group()

                        play_game(1)
                    if event.ui_element == load_game_btn:
                        show_load_screen()
                    if event.ui_element == show_achievements_btn:
                        show_achievements_storage()
                    if event.ui_element == exit_btn:
                        if CURRENT_THEME != 'Pioneer':
                            confirm_exit()
                        else:
                            set_bus_to_hell()

                    if not bus_to_hell:
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
