import pygame
import os
import sys
import pygame_gui
import math
import shutil
import random
import datetime
import json
import cv2
from functools import total_ordering
from threading import Thread


class ExitToMenuException(Exception):
    pass


@total_ordering
class INF:
    def __init__(self, minus_inf=False):
        self.minus = minus_inf

    def __eq__(self, other):
        return isinstance(other, INF) and self.minus == other.minus

    def __gt__(self, other):
        return self != other and not self.minus


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
        self.image = bound_image
        self.rect = self.image.get_rect().move(
            TILE_WIDTH * pos_x, TILE_HEIGHT * pos_y)


class BackGround(pygame.sprite.Sprite):
    def __init__(self, pos_x, background_image, *groups):
        super().__init__(*groups)
        self.image = background_image
        self.rect = self.image.get_rect().move(pos_x, 0)
        self.mask = pygame.mask.from_surface(self.image)


class BookParticle(pygame.sprite.Sprite):
    def __init__(self, x, y):
        super().__init__(all_sprites, particles_group)
        self.image = DICTIONARY_SPRITES['BookParticles']
        self.rect = self.image.get_rect().move(x, y)


class Book(pygame.sprite.Sprite):
    def __init__(self, image, pos_x, pos_y, number, *groups):
        super().__init__(*groups)
        self.image = image
        self.rect = self.image.get_rect().move(TILE_WIDTH * pos_x, TILE_HEIGHT * pos_y + 10)
        self.base_pos_y = self.rect.y
        self.vy = 1
        self.move_timer = 0
        self.mask = pygame.mask.from_surface(self.image)
        self.pos_x = pos_x
        self.effect = BookParticle(self.rect.x - 17, self.rect.y - 15)
        self.number = number

    def update(self):
        if not self.move_timer:
            self.rect.y += self.vy
            self.move_timer = 75
            if not (self.base_pos_y <= self.rect.y <= self.base_pos_y + 10) or collide_asphalt(self):
                self.vy *= -1
        else:
            self.move_timer -= 1

    def kill(self):
        self.effect.kill()
        super().kill()


class Projectile(pygame.sprite.Sprite):
    def __init__(self, x, y, sprite, route, *groups):
        super().__init__(*groups)
        self.image = sprite
        self.rect = self.image.get_rect().move(x, y)
        self.route = route
        self.vx = 100
        self.vx_timer = 1

        self.mask = pygame.mask.from_surface(self.image)

    def update(self):
        sprite = pygame.sprite.spritecollideany(self, bound_group)
        if sprite:
            if isinstance(sprite, MagicShield):
                audio.make_sound(9)
            self.kill()

        if self.vx_timer % 3 < 2 and self.route == 'Right':
            self.rect.x += math.ceil(self.vx / FPS)
        if self.vx_timer % 3 < 2 and self.route == 'Left':
            self.rect.x -= math.ceil(self.vx / FPS)
        self.vx_timer = (self.vx_timer + 1) % 3


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
        if settings['go_right'] in directions:
            if (self.jump_timer % 3 < 2 and in_jump) or (self.down_timer % 3 < 2 and in_fall) or \
                    (not in_jump and not in_fall and self.vx_timer % 3 < 2):
                self.is_rotate = False
                super().update()
                self.rect.x += math.ceil(self.vx / FPS)
                self.absolute_x += math.ceil(self.vx / FPS)
                motion = True
            self.vx_timer = (self.vx_timer + 1) % 3
        if settings['go_left'] in directions:
            if (self.jump_timer % 3 < 2 and in_jump) or (self.down_timer % 3 < 2 and in_fall) or \
                    (not in_jump and not in_fall and self.vx_timer % 3 < 2):
                self.is_rotate = True
                super().update()
                self.absolute_x -= math.ceil(self.vx / FPS)
                self.rect.x -= math.ceil(self.vx / FPS)
                motion = True
            self.vx_timer = (self.vx_timer + 1) % 3
        if settings['jump'] in directions and not in_jump and not in_fall:
            audio.make_sound(6)
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
    def __init__(self, sheet, columns, rows, pos_x, pos_y, *groups, boss_minions=False):
        super().__init__(sheet, columns, rows, pos_x, pos_y, *groups)
        if not boss_minions:
            self.left_bound = TILE_WIDTH * (pos_x - random.randint(min(3, pos_x), min(6, pos_x)))
            self.right_bound = TILE_WIDTH * (pos_x + random.randint(3, 5))
        else:
            self.left_bound = INF(minus_inf=True)
            self.right_bound = INF()
        self.is_go_left = True

        self.timer_damage = 200
        self.cur_timer_damage = 0

    def update(self, *args):
        if self.cur_timer_damage > 0:
            self.cur_timer_damage -= 1

        swap = False

        collide = super().update([settings['go_left'] if self.is_go_left else
                                  settings['go_right']])

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

        self.is_hitted = False  # Для отображение красного эффекта по бокам

        # Частота Снарядов
        self.projectile_timer = 500
        self.projectile_current_time = 0

    def update(self, *args):
        self.is_hitted = False
        keys = pygame.key.get_pressed()
        directions = []
        for key in [settings['go_right'], settings['go_left'],
                    settings['jump']]:
            if keys[key]:
                directions.append(key)
        super().update(directions)

        # Выпускание снаряда
        if keys[settings['shoot']] and self.projectile_current_time == 0:
            audio.make_sound(2)
            if self.is_rotate:
                Projectile(self.rect.x, self.rect.y + 10,
                           DICTIONARY_SPRITES['Projectile'], 'Left',
                           all_sprites, projectile_group)
            else:
                Projectile(self.rect.x + self.rect.w, self.rect.y + 10,
                           DICTIONARY_SPRITES['Projectile'], 'Right',
                           all_sprites, projectile_group)

            self.projectile_current_time = self.projectile_timer

        if self.projectile_current_time > 0:
            self.projectile_current_time -= 1

        collides = pygame.sprite.spritecollide(self, enemy_group, False)
        for sprite in collides:
            if pygame.sprite.collide_mask(self, sprite) and sprite.cur_timer_damage == 0:
                self.is_hitted = True
                self.health -= 20
                sprite.cur_timer_damage = sprite.timer_damage

        collides = pygame.sprite.spritecollide(self, boss_projectile_group, False)
        for sprite in collides:
            if pygame.sprite.collide_mask(self, sprite) and sprite.cur_timer_damage == 0:
                self.is_hitted = True
                self.health -= 20
                sprite.cur_timer_damage = sprite.timer_damage

        self.check_bounds()

    def collide_books(self):
        # Проверка пересечения с книгами
        books = pygame.sprite.spritecollide(self, book_group, False)
        for book in books:
            if pygame.sprite.collide_mask(self, book):
                audio.make_sound(4)
                self.counter_books += 1
                book.kill()

    def check_bounds(self):
        self.dx = max(min(self.upper_bound - self.rect.x, 0),
                      max(self.lower_bound - self.rect.x, -1))


class WHero(pygame.sprite.Sprite):
    def __init__(self, image, pos_x, pos_y, name, *groups):
        super().__init__(*groups)
        self.image = image
        self.name = name
        self.rect = self.image.get_rect().move(pos_x * TILE_WIDTH, pos_y * TILE_HEIGHT -
                                               self.image.get_height())
        self.is_flip = True

    def fall(self):
        while not pygame.sprite.spritecollideany(self, bound_group):
            self.rect.y += 1
        self.rect.y -= 1

    def update(self, *args, **kwargs):
        if self.rect.x + self.rect.w < game.hero.rect.x and not self.is_flip:
            self.flip_image()
        if self.rect.x > game.hero.rect.x + game.hero.rect.w and self.is_flip:
            self.flip_image()

    def change_pos(self, is_in_camera, x, y):
        """Добавляет к координате x, y,
        Параметр camera показывает должен ли персонаж в это время находится в кадре"""
        self.rect.x += x
        self.rect.y += y

    def flip_image(self):
        """Отрожает изображение"""
        self.image = pygame.transform.flip(self.image, True, False)
        self.is_flip = not self.is_flip


class FallingAsphalt(pygame.sprite.Sprite):
    def __init__(self, pos_x, pos_y, image, *groups, check_collide=True):
        super().__init__(*groups)
        self.image = image
        self.rect = self.image.get_rect().move(
            TILE_WIDTH * pos_x, TILE_HEIGHT * pos_y)
        self.down_vy = 0
        self.down_timer = 0
        self.check_collide = check_collide
        self.cur_timer_damage = 0
        self.timer_damage = 100

    def update(self):
        if not self.check_collide or \
                (1 not in (collide := collide_asphalt(self)) and 0 not in collide):
            if self.down_timer == 0:
                self.down_vy = 1
                self.down_timer = HEIGHT
            if self.down_timer % 3 < 2:
                self.rect.y += math.ceil(self.down_vy / FPS)
                self.down_vy += 1
            self.down_timer -= 1
        else:
            self.down_timer = 0
            self.down_vy = 0

        if self.rect.y > 600:
            self.kill()


class MagicShield(pygame.sprite.Sprite):
    def __init__(self, x, y, img, *groups):
        super().__init__(*groups)
        self.image = img
        self.rect = self.image.get_rect().move(x, y)


class BossHP(pygame.sprite.Sprite):
    def __init__(self, x, y, img, *groups):
        super().__init__(*groups)
        self.image = img
        self.x, self.y = x, y
        self.rect = self.image.get_rect().move(x, y)

    def update(self, *args, **kwargs) -> None:
        self.rect.x = self.x
        self.rect.y = self.y


class BossProjectile(pygame.sprite.Sprite):
    def __init__(self, x, y, sprite, destination_x, destination_y, *groups):
        super().__init__(*groups)
        self.image = sprite
        self.rect = self.image.get_rect().move(x, y)
        self.mask = pygame.mask.from_surface(self.image)
        self.cur_timer_damage = 0
        self.timer_damage = 100

        d1, d2 = destination_x - x, destination_y - y
        self.vx = math.ceil(d1 / 200)
        self.vy = math.ceil(d2 / 200)

        if self.vx == 0 and self.vy == 0:
            self.kill()

        self.vx_timer = 1

    def update(self):
        sprite = pygame.sprite.spritecollideany(self, bound_group)
        if sprite:
            if not isinstance(sprite, MagicShield):
                self.kill()

        if self.vx_timer % 3 < 2:
            self.rect.x += self.vx
            self.rect.y += self.vy

        self.vx_timer = (self.vx_timer + 1) % 3


class Boss(WHero):
    def __init__(self, image, pos_x, pos_y, name, *groups, hp=100):
        super().__init__(image, pos_x, pos_y, name, *groups)
        self.y = pos_y * TILE_HEIGHT
        self.hp = hp
        self.hp_image = BossHP(170, 0, DICTIONARY_SPRITES[f'boss_hp_{self.hp}'], all_sprites)
        self.shield = MagicShield(self.rect.x - 40, self.rect.y - 25,
                                  DICTIONARY_SPRITES['magic_shield'], all_sprites, bound_group)

        self.projectile_delay = 1000

    def update(self, *args, **kwargs):
        super().update(*args, **kwargs)

        collide_projectiles = pygame.sprite.spritecollide(self, projectile_group, False)
        for sprite in collide_projectiles:
            if pygame.sprite.collide_mask(self, sprite):
                self.hp -= 10
                self.hp_image.kill()
                self.hp_image = BossHP(170, 0, DICTIONARY_SPRITES[f'boss_hp_{self.hp}'], all_sprites)
                sprite.kill()

        if not self.projectile_delay:
            self.projectile_delay = 1000
            BossProjectile(self.rect.x, self.rect.y, DICTIONARY_SPRITES['BossProjectile'],
                           hero_group.sprites()[0].rect.x, hero_group.sprites()[0].rect.y,
                           all_sprites, boss_projectile_group)
            audio.make_sound(12)
        else:
            self.projectile_delay -= 1

    def break_shield(self):
        audio.make_sound(10)
        self.shield.kill()
        self.fall()

    def kill(self):
        self.hp_image.kill()
        super().kill()


class AudioManager:
    def __init__(self):
        # Загружаем звуковые эффекты
        self.sounds = {
            1: pygame.mixer.Sound(rf'Data\Audio\SoundEffects\button_hovered.wav'),
            2: pygame.mixer.Sound(rf'Data\Audio\SoundEffects\projectile_sound.wav'),
            3: pygame.mixer.Sound(rf'Data\Audio\SoundEffects\hit.wav'),
            4: pygame.mixer.Sound(rf'Data\Audio\SoundEffects\collect_book.wav'),
            5: pygame.mixer.Sound(rf'Data\Audio\SoundEffects\fall.wav'),
            6: pygame.mixer.Sound(rf'Data\Audio\SoundEffects\jump.wav'),
            7: pygame.mixer.Sound(rf'Data\Audio\SoundEffects\achievement_sound.wav'),
            8: pygame.mixer.Sound(rf'Data\Audio\SoundEffects\portal.wav'),
            9: pygame.mixer.Sound(rf'Data\Audio\SoundEffects\shield.wav'),
            10: pygame.mixer.Sound(rf'Data\Audio\SoundEffects\shield_break.wav'),
            11: pygame.mixer.Sound(rf'Data\Audio\SoundEffects\teleport.wav'),
            12: pygame.mixer.Sound(rf'Data\Audio\SoundEffects\knife_throw.wav')
        }

    @staticmethod
    def change_volume(volume):
        pygame.mixer.music.set_volume(volume / 100)

    @staticmethod
    def play_music(music_file_name):
        pygame.mixer.music.load(rf'Data\Audio\Music\{music_file_name}')
        pygame.mixer.music.set_volume(settings['music_volume'] / 100)
        pygame.mixer.music.play(-1)

    @staticmethod
    def stop_music():
        pygame.mixer.music.stop()

    def make_sound(self, sound_id):
        if sound_id in self.sounds and self.sounds[sound_id] != '':
            self.sounds[sound_id].play()

    def change_sound(self, sound_id, song):
        self.sounds[sound_id] = song

    def get_sound(self, sound_id):
        return self.sounds[sound_id]


class GameManager:
    def level_init(self, level_data, load_from_save=False):
        global CUR_LEVEL

        if load_from_save:
            page, cell = level_data
            map_path = f'Saves/{page}/{cell}/map.txt'
            with open(f'Saves/{page}/{cell}/data.json', 'r', encoding='utf-8') as f:
                load_data = json.load(f)
            level_data = int(load_data['level'])
            self.LP = load_data["LP"]
        else:
            try:
                x = self.LP
            except AttributeError:
                self.LP = {"LP_Lena": 0, "LP_Alisa": 0, "LP_Miku": 0, "LP_Slavya": 0, "LP_Ulyana": 0}
            map_path = f'Levels/level{level_data}'

        story_lines = \
            open(rf'Data/Levels/data_level{level_data}', 'r', encoding='utf-8').readlines()
        queue = list(map(int, story_lines[1].strip().split()))

        self.boss_achievement_condition = False
        self.cur_dialog_in_progress = -1
        self.draw_hit_effect = False
        self.camera = Camera()
        self.bg_first = \
            BackGround(-4000, DICTIONARY_SPRITES[f'Background{level_data}'], all_sprites, background_group)
        self.bg_second = \
            BackGround(0, DICTIONARY_SPRITES[f'Background{level_data}'], all_sprites, background_group)
        self.hero, self.hero_pos_x, self.hero_pos_y, self.coord_checkpoints, self.exit_pos = \
            generate_level(load_level(map_path, is_save=load_from_save), (all_sprites, hero_group),
                           (bound_group, all_sprites))
        for sprite in whero_group.sprites():
            sprite.fall()

        self.queue_dialogs = [0] * len(queue)
        self.dialogs_text = get_level_dialog(level_data)
        for cnt, x in self.coord_checkpoints:
            self.queue_dialogs[queue.index(cnt)] = x

        self.cur_dialog = []
        self.dialog_number = 0

        self.hero.dx = max(self.hero.upper_bound - self.hero.rect.x,
                           self.hero.lower_bound - self.hero.rect.x) - \
                       self.hero.upper_bound + self.hero.lower_bound
        self.camera.update(self.hero)
        # обновляем положение всех спрайтов
        for sprite in all_sprites:
            self.camera.apply(sprite)
        for sprite in invisible_bound:
            self.camera.apply(sprite)

        if load_from_save:
            CUR_LEVEL = int(load_data['level'])
            self.dialog_number = int(load_data['dialog_number'])
            self.cur_dialog = load_data['cur_dialog']
            self.hero.health = int(load_data['hp'])
            self.hero.all_books = int(load_data['all_books'])
            self.hero.counter_books = int(load_data['collected_books'])
            self.cur_dialog_in_progress = int(load_data['cur_dialog_in_progress'])
            if self.cur_dialog_in_progress != -1:
                self.dialog_number -= 1

            return self.start_level(level_data, preinited=True)

    def start_level(self, level, preinited=False):
        levels = {1: self.play_level_1, 2: self.play_level_2, 4: self.play_level_4,
                  3: self.play_level_3, 5: self.play_level_5}
        if not preinited:
            show_image_smoothly(DICTIONARY_SPRITES.get(f'Level_{level}_intro',
                                                       pygame.Surface((800, 600))), screen.copy(),
                                DICTIONARY_SPRITES[f'Background{level}'])
            self.level_init(level)
        return levels[level]()

    def play_level_1(self):
        audio.play_music('Level1_theme.mp3')

        without_enemies_and_books_group = pygame.sprite.Group()
        for sprite in all_sprites.sprites():
            if not isinstance(sprite, Enemy) and not isinstance(sprite, Book):
                without_enemies_and_books_group.add(sprite)

        running_game = True

        while running_game:
            game_time_delta = clock.tick() / 1000

            if self.hero.health <= 0:
                restart = show_death_screen()
                if restart:
                    return 1, "restart"
                return 1, "death"

            if self.hero.absolute_x <= self.exit_pos <= self.hero.absolute_x + self.hero.rect.w and \
                    len(self.queue_dialogs) == self.dialog_number:
                return 1, "passed"

            if self.dialog_number < len(self.dialogs_text) and self.hero.state and \
                    self.hero.absolute_x <= self.queue_dialogs[self.dialog_number] <= \
                    self.hero.absolute_x + self.hero.rect.w:
                if self.dialog_number >= 3 and self.hero.counter_books == self.hero.all_books:
                    self.cur_dialog = self.dialogs_text[self.dialog_number]
                    self.dialog_number += 1
                elif self.dialog_number <= 2:
                    self.cur_dialog = self.dialogs_text[self.dialog_number]
                    self.dialog_number += 1

            if self.dialog_number <= 2 or not enemy_group.sprites():
                self.hero.projectile_current_time = 100

            for event_game in pygame.event.get():
                if event_game.type == pygame.QUIT or (event_game.type == pygame.KEYDOWN and
                                                      event_game.key ==
                                                      settings['pause']):
                    try:
                        active_pause_menu()
                    except ExitToMenuException:
                        running_game = False

                UIManager.process_events(event_game)

            UIManager.update(game_time_delta)
            all_sprites.update()

            # Движение BackGround`а (бесконечный фон)
            move_background(self.bg_first, self.bg_second)

            self.camera.update(self.hero)
            # обновляем положение всех спрайтов
            for sprite in all_sprites:
                self.camera.apply(sprite)
            for sprite in invisible_bound:
                self.camera.apply(sprite)

            screen.fill((0, 0, 0))
            if self.hero.is_hitted and self.dialog_number == 3 and not self.draw_hit_effect:
                self.draw_hit_effect = True
                draw_hit_effect()
            else:
                self.draw_hit_effect = False

            if self.dialog_number <= 2:
                without_enemies_and_books_group.draw(screen)
                self.hero.health = 100
            else:
                self.hero.collide_books()
                all_sprites.draw(screen)
            book_group.draw(screen)

            UIManager.draw_ui(screen)
            if self.dialog_number != 3:
                pygame.display.flip()
            if self.cur_dialog:
                try:
                    show_dialog(self.cur_dialog, start_from=self.cur_dialog_in_progress)
                except ExitToMenuException:
                    running_game = False
                self.cur_dialog = []
                self.cur_dialog_in_progress = -1

            if self.dialog_number == 3:
                draw_text_data([f"Собрать книги. {self.hero.counter_books}/{self.hero.all_books}",
                                f"HP: {self.hero.health}"])
                pygame.display.flip()

        self.LP['LP_Lena'] += 9
        return 1, "not passed"

    def play_level_2(self):
        audio.play_music('A Promise From Distant Days.mp3')
        Lena_achievement = False
        Lena = None

        all_sprites_without_Lena = pygame.sprite.Group()
        for sprite in all_sprites.sprites():
            if not isinstance(sprite, WHero):
                all_sprites_without_Lena.add(sprite)
            elif sprite.name != 'Lena':
                all_sprites_without_Lena.add(sprite)
            else:
                Lena = sprite

        running_game = True

        while running_game:
            self.hero.projectile_current_time = 100
            game_time_delta = clock.tick() / 1000

            if self.hero.health <= 0:
                restart = show_death_screen()
                if restart:
                    return 2, "restart"
                return 2, "death"

            if pygame.sprite.collide_mask(Lena, self.hero) and self.dialog_number == 2 and not \
                    self.cur_dialog and self.hero.state and not Lena_achievement:
                self.cur_dialog = [['Семен', 'Лена! Привет, почему ты не отвечаешь на телефон',
                                    'Semen'],
                                   ['Лена', 'А? Что? Где я? Что я здесь делаю?', 'Lena'],
                                   ['Семен', 'Что случилось?', 'Semen'],
                                   ['Лена', 'А, ой, это же мой уровень', 'Lena'],
                                   ['Семен', 'Что? Какой уровень?', 'Semen']]
                self.LP['LP_Lena'] += 1
                Lena_achievement = True
                give_achievement('2')

            if self.dialog_number < len(self.dialogs_text) and self.hero.state and \
                    self.hero.absolute_x <= self.queue_dialogs[self.dialog_number] <= \
                    self.hero.absolute_x + self.hero.rect.w:
                if self.dialog_number == 1:
                    audio.play_music("Door To Nightmare.mp3")
                self.cur_dialog = self.dialogs_text[self.dialog_number]
                self.dialog_number += 1

            if self.hero.absolute_x <= self.exit_pos <= self.hero.absolute_x + self.hero.rect.w and \
                    len(self.queue_dialogs) == self.dialog_number:
                return 2, "passed"

            for event_game in pygame.event.get():
                if event_game.type == pygame.QUIT or (event_game.type == pygame.KEYDOWN and
                                                      event_game.key ==
                                                      settings['pause']):
                    try:
                        active_pause_menu()
                    except ExitToMenuException:
                        running_game = False

                UIManager.process_events(event_game)
                all_sprites.update()

            UIManager.update(game_time_delta)
            all_sprites.update()
            self.hero.collide_books()

            # Движение BackGround`а (бесконечный фон)
            move_background(self.bg_first, self.bg_second)

            self.camera.update(self.hero)
            # обновляем положение всех спрайтов
            for sprite in all_sprites:
                self.camera.apply(sprite)
            for sprite in invisible_bound:
                self.camera.apply(sprite)

            screen.fill((0, 0, 0))

            if self.dialog_number == 2:
                all_sprites.draw(screen)
            else:
                all_sprites_without_Lena.draw(screen)
            hero_group.draw(screen)
            if self.dialog_number == 2:
                draw_text_data([f"Найти Лену"])
            UIManager.draw_ui(screen)
            pygame.display.flip()

            if self.cur_dialog:
                try:
                    show_dialog(self.cur_dialog, start_from=self.cur_dialog_in_progress)
                except ExitToMenuException:
                    running_game = False
                self.cur_dialog = []
                self.cur_dialog_in_progress = -1

            if Lena_achievement:
                Lena.kill()

        return 2, "not passed"

    def play_level_3(self):
        draw_sprites = all_sprites.copy()
        Pioneer, Slavya = None, None
        text = [""]

        for sprite in draw_sprites.sprites():
            if isinstance(sprite, WHero) and sprite.name == "Pioneer":
                Pioneer = sprite
            elif isinstance(sprite, WHero) and sprite.name == "Slavya":
                Slavya = sprite

        draw_sprites.remove(Slavya)

        for sprite in book_group.sprites():
            draw_sprites.remove(sprite)
        for sprite in enemy_group.sprites():
            draw_sprites.remove(sprite)
        for sprite in particles_group.sprites():
            draw_sprites.remove(sprite)

        end_tasks = False
        first_card = False

        audio.play_music('I Want To Play.mp3')

        running_game = True

        while running_game:
            game_time_delta = clock.tick() / 1000

            if self.hero.health <= 0:
                restart = show_death_screen()
                if restart:
                    return 3, "restart"
                return 3, "death"

            if self.dialog_number < len(self.dialogs_text) and self.hero.state and \
                    self.hero.absolute_x <= self.queue_dialogs[self.dialog_number] <= \
                    self.hero.absolute_x + self.hero.rect.w and ((self.dialog_number == 2 and end_tasks) or
                                                                 self.dialog_number != 2):
                self.cur_dialog = self.dialogs_text[self.dialog_number]
                self.dialog_number += 1
                text = [""]
                first_card = True
                if self.dialog_number == 2:
                    draw_sprites.remove(Pioneer)
                    Pioneer.change_pos(False, -115 * 50, -100)
                    Pioneer.fall()
                if self.dialog_number == 3:
                    audio.play_music('Forest Maiden.mp3')
                    draw_sprites.add(Slavya)
                if self.dialog_number == 6:
                    Slavya.change_pos(False, -43 * 50, 0)
                if self.dialog_number == 8:
                    audio.play_music('A Promise From Distant Days.mp3')
                    draw_sprites.add(Pioneer)
                    draw_sprites.remove(Slavya)
                if self.dialog_number == 9:
                    draw_sprites.remove(Pioneer)

            if self.hero.absolute_x <= self.exit_pos <= self.hero.absolute_x + self.hero.rect.w and \
                    len(self.queue_dialogs) == self.dialog_number:
                return 3, "passed"
            for event_game in pygame.event.get():
                if event_game.type == pygame.QUIT or (event_game.type == pygame.KEYDOWN and
                                                      event_game.key ==
                                                      settings['pause']):
                    try:
                        active_pause_menu()
                    except ExitToMenuException:
                        running_game = False

                if (event_game.type == pygame.KEYDOWN and event_game.key == settings['skip_quest'] and self.dialog_number == 2) or \
                        self.hero.counter_books == 5:
                    end_tasks = True

                UIManager.process_events(event_game)
                all_sprites.update()

            if self.dialog_number == 2 and not end_tasks:
                text = [f"Собрать документы:{self.hero.counter_books}/5", f"HP:{self.hero.health}/100"]

            if self.dialog_number == 2 and self.hero.counter_books == 5:
                end_tasks = True
                text = [""]

            if self.hero.is_hitted and self.dialog_number == 2 and not self.draw_hit_effect:
                self.draw_hit_effect = True
                draw_hit_effect()
            else:
                self.draw_hit_effect = False

            UIManager.update(game_time_delta)
            all_sprites.update()
            self.hero.collide_books()

            # Движение BackGround`а (бесконечный фон)
            move_background(self.bg_first, self.bg_second)

            self.camera.update(self.hero)
            # обновляем положение всех спрайтов
            for sprite in all_sprites:
                self.camera.apply(sprite)
            for sprite in invisible_bound:
                self.camera.apply(sprite)

            screen.fill((0, 0, 0))

            draw_sprites.draw(screen)
            hero_group.draw(screen)
            draw_text_data(text)

            if self.dialog_number == 2 and not first_card and not end_tasks:
                particles_group.draw(screen)
                book_group.draw(screen)
                enemy_group.draw(screen)
                self.hero.collide_books()
                projectile_group.draw(screen)
            elif self.dialog_number == 2 and first_card:
                first_card = False
            else:
                self.hero.projectile_current_time = 100
                self.hero.health = 100

            UIManager.draw_ui(screen)
            pygame.display.flip()

            if self.cur_dialog:
                try:
                    show_dialog(self.cur_dialog, start_from=self.cur_dialog_in_progress)
                except ExitToMenuException:
                    running_game = False
                self.cur_dialog = []
                self.cur_dialog_in_progress = -1

        self.LP['LP_Slavya'] += self.hero.counter_books * 2

        return 3, "not passed"

    def play_level_4(self):
        audio.play_music('boss_phase1_theme.mp3')

        check_alive = False
        running_game = True
        fight_starting = 0
        rain_count = 0
        rain_delay = 1000

        rain_sprites = pygame.sprite.Group()

        while running_game:
            game_time_delta = clock.tick() / 1000

            if check_alive and not len(enemy_group.sprites()):
                self.cur_dialog = self.dialogs_text[self.dialog_number]
                self.dialog_number += 1
                check_alive = False
            elif self.dialog_number == 0 and self.hero.state and \
                    self.hero.absolute_x <= self.queue_dialogs[self.dialog_number] <= \
                    self.hero.absolute_x + self.hero.rect.w:
                self.cur_dialog = self.dialogs_text[self.dialog_number]
                self.dialog_number += 1

            if not rain_count and rain_delay != 1000 and not len(rain_sprites.sprites()):
                self.cur_dialog = self.dialogs_text[self.dialog_number]
                self.dialog_number += 1
                rain_delay = 1000

            if self.hero.health <= 0:
                restart = show_death_screen()
                if restart:
                    return 4, "restart"
                return 4, "death"

            for event_game in pygame.event.get():
                if event_game.type == pygame.QUIT or (event_game.type == pygame.KEYDOWN and
                                                      event_game.key == settings['pause']):
                    try:
                        active_pause_menu(cant_save=True)
                    except ExitToMenuException:
                        running_game = False

                UIManager.process_events(event_game)

            UIManager.update(game_time_delta)
            if fight_starting == 0:
                all_sprites.update()
            else:
                bound_group.update()
                fight_starting -= 1
                if fight_starting == 0:
                    for i in range(5):
                        Enemy(DICTIONARY_SPRITES['Enemy'], 4, 1,
                              self.hero.rect.x // TILE_WIDTH - 10 + i, 9,
                              enemy_group, all_sprites, boss_minions=True)
                        Enemy(DICTIONARY_SPRITES['Enemy'], 4, 1,
                              self.hero.rect.x // TILE_WIDTH + 10 - i, 9,
                              enemy_group, all_sprites, boss_minions=True)
                    check_alive = True

            if rain_count:
                if rain_delay:
                    rain_delay -= 1
                else:
                    rain_delay = 50 * rain_count
                    rain_count -= 1
                    FallingAsphalt(round(self.hero.rect.x / TILE_WIDTH), -1,
                                   DICTIONARY_SPRITES['Bound'],
                                   all_sprites, enemy_group, rain_sprites, check_collide=False)

            # Движение BackGround`а (бесконечный фон)
            move_background(self.bg_first, self.bg_second)

            self.camera.update(self.hero)
            # обновляем положение всех спрайтов
            for sprite in all_sprites:
                self.camera.apply(sprite)
            for sprite in invisible_bound:
                self.camera.apply(sprite)

            screen.fill((0, 0, 0))
            all_sprites.draw(screen)

            if self.hero.is_hitted and not self.draw_hit_effect:
                self.draw_hit_effect = True
                draw_hit_effect()
            else:
                self.draw_hit_effect = False

            draw_text_data([f"HP: {self.hero.health}"])

            UIManager.draw_ui(screen)
            pygame.display.flip()
            if self.cur_dialog:
                try:
                    show_dialog(self.cur_dialog)
                    if self.dialog_number == 1:
                        for i in range(6):
                            FallingAsphalt(self.hero.rect.x // TILE_WIDTH - 12, -i * 10,
                                           DICTIONARY_SPRITES['Bound'], all_sprites, bound_group)
                            fight_starting = 1000
                    elif self.dialog_number == 2:
                        rain_count = 20
                    elif self.dialog_number == 3:
                        audio.make_sound(8)
                        self.boss_achievement_condition = self.hero.health == 100
                        return 4, "passed"

                except ExitToMenuException:
                    running_game = False
                self.cur_dialog = []

        return 4, "not passed"

    def play_level_5(self):
        audio.play_music('boss_phase2_theme.mp3')

        left_book, right_book = book_group.sprites()
        boss = boss_group.sprites()[0]
        running_game = True
        shield_activated = True
        phase = 1

        while running_game:
            game_time_delta = clock.tick() / 1000

            if self.hero.health <= 0:
                restart = show_death_screen()
                if restart:
                    return 5, "restart"
                return 5, "death"

            for event_game in pygame.event.get():
                if event_game.type == pygame.QUIT or (event_game.type == pygame.KEYDOWN and
                                                      event_game.key == settings['pause']):
                    try:
                        active_pause_menu(cant_save=True)
                    except ExitToMenuException:
                        running_game = False

                UIManager.process_events(event_game)

            UIManager.update(game_time_delta)

            # Движение BackGround`а (бесконечный фон)
            move_background(self.bg_first, self.bg_second)

            self.camera.update(self.hero)
            # обновляем положение всех спрайтов
            for sprite in all_sprites:
                self.camera.apply(sprite)
            for sprite in invisible_bound:
                self.camera.apply(sprite)

            screen.fill((0, 0, 0))
            all_sprites.draw(screen)
            book_group.draw(screen)

            if self.hero.is_hitted and not self.draw_hit_effect:
                self.draw_hit_effect = True
                draw_hit_effect()
            else:
                self.draw_hit_effect = False

            draw_text_data([f"HP: {self.hero.health}"])

            UIManager.draw_ui(screen)
            all_sprites.update()

            self.hero.collide_books()
            if shield_activated and self.hero.counter_books == self.hero.all_books:
                boss.break_shield()
                shield_activated = False
                phase += 1
            if (boss.hp == 50 and phase == 2) or (boss.hp == 20 and phase == 4):
                lb, rb = left_book, right_book
                if phase == 4:
                    lb, rb = rb, lb
                boss.kill()
                Boss(DICTIONARY_SPRITES['Pioneer']['static'],
                     lb.pos_x - (self.hero.absolute_x - self.hero.rect.x) // TILE_WIDTH,
                     lb.rect.y // TILE_HEIGHT + 1, 'Pioneer',
                     all_sprites, boss_group, hp=70 - 20 * (phase == 4))
                boss = boss_group.sprites()[0]
                Book(random.choice(DICTIONARY_SPRITES['Books']),
                     rb.pos_x - 1 - (self.hero.absolute_x - self.hero.rect.x) // TILE_WIDTH,
                     rb.rect.y // TILE_HEIGHT, 0, book_group, all_sprites)
                shield_activated = True
                self.hero.all_books += 1
                phase += 1
                audio.make_sound(11)
            if boss.hp == 0 and self.dialog_number == 0:
                self.cur_dialog = self.dialogs_text[self.dialog_number]
                self.dialog_number += 1

            pygame.display.flip()
            if self.cur_dialog:
                try:
                    show_dialog(self.cur_dialog)
                    if self.dialog_number == 1:
                        boss.kill()
                        show_image_smoothly(DICTIONARY_SPRITES['Level_8_intro'],
                                            screen.copy(), DICTIONARY_SPRITES['EmptyMenu'])
                        if self.hero.health == 100 and self.boss_achievement_condition:
                            give_achievement('3')
                        return 5, "passed"
                except ExitToMenuException:
                    running_game = False
                self.cur_dialog = []

        return 5, "not passed"


def show_image_smoothly(image, bg_start=None, bg_end=None, mode=0):
    """Создаёт плавный переход от bg_start к bg_end с использованием image
       mode:
            0 - плавное появление изображения image и его затухание
            1 - только затухание
            2 - только появление
    """

    if mode == 1:
        bg = bg_end or DICTIONARY_SPRITES['Background1']
    else:
        bg = bg_start or DICTIONARY_SPRITES['EmptyMenu']
    alpha = 255 * (mode == 1)
    delta = (mode == 0 or mode == 2) + (mode != 1) - 1
    while True:
        for evnt in pygame.event.get():
            if evnt.type == pygame.QUIT or evnt.type == pygame.KEYDOWN or \
                    evnt.type == pygame.MOUSEBUTTONDOWN:
                return

        image.set_alpha(alpha)
        alpha += delta
        screen.blit(bg, (0, 0))
        screen.blit(image, (0, 0))
        pygame.display.flip()

        clock.tick(200)
        if alpha == 255:
            if mode == 2:
                break
            clock.tick(1)
            delta *= -1
            bg = bg_end or DICTIONARY_SPRITES['Background1']

        if alpha == 0 and delta == -1:
            break


def make_choice(choices):
    """Заставляет пользователя сделать выбор меджу вариантами, перечисленными
       в списке choices
       Возвращает индекс варианта, выбранного пользователем"""

    if not choices:
        raise ValueError('Нельзя сделать выбор из пустого списка')

    choice_size = 50
    height = (5 + choice_size) * len(choices)
    top_left = (HEIGHT - height) // 2
    dark_effect = pygame.transform.scale(DICTIONARY_SPRITES['DarkScreen'], (WIDTH - 20, height))
    screen.blit(dark_effect, (10, top_left))
    bg = screen.copy()

    buttons = []
    for i, choice in enumerate(choices):
        btn = pygame_gui.elements.UIButton(
            manager=UIManager,
            relative_rect=pygame.Rect(15, top_left + 5 + (choice_size + 5) * i,
                                      WIDTH - 30, choice_size),
            text=choice,
            object_id='#choice_btn'
        )
        buttons.append(btn)

    run_choice = True
    chosen = -1

    while run_choice:
        choice_time_delta = clock.tick() / 1000
        for event_choice in pygame.event.get():
            if event_choice.type == pygame.QUIT or (event_choice.type == pygame.KEYDOWN and
                                                    event_choice.key ==
                                                    settings['pause']):
                for btn in buttons:
                    btn.hide()
                active_pause_menu()
                for btn in buttons:
                    btn.show()
            if event_choice.type == pygame.USEREVENT:
                if event_choice.user_type == pygame_gui.UI_BUTTON_PRESSED:
                    if event_choice.ui_element in buttons:
                        chosen = buttons.index(event_choice.ui_element)
                        run_choice = False

            UIManager.process_events(event_choice)

        screen.blit(bg, (0, 0))
        UIManager.update(choice_time_delta)
        UIManager.draw_ui(screen)
        pygame.display.flip()

    kill_buttons(buttons)
    return chosen


def draw_hit_effect_core(make_sound):
    make_sound and audio.make_sound(3)
    hit_effect = pygame_gui.elements.UIImage(
        manager=UIManager,
        image_surface=DICTIONARY_SPRITES['HitEffect'],
        relative_rect=DICTIONARY_SPRITES['HitEffect'].get_rect()
    )
    UIManager.draw_ui(screen)
    clock.tick(10)
    hit_effect.kill()


def draw_hit_effect(make_sound=True):
    th = Thread(target=draw_hit_effect_core, args=(make_sound,))
    th.start()


def collide_asphalt(sprite):
    """Проверяет пересечение с асфальтом и возвращает словарь в котором ключами будут:
        0, если персонаж пересекается с асфальтом снизу,
        1, если пересекается с асфальтом справа или слева,
        2, если пересекается с асфальтом сверху"""

    res = {}
    for collide in pygame.sprite.spritecollide(sprite, bound_group, False):
        if collide != sprite:
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


def load_level(filename, is_save=False):
    if not is_save:
        filename = "data/" + filename
    with open(filename, 'r') as mapFile:
        level_map = [map_line.strip() for map_line in mapFile]
    max_width = max(map(len, level_map))
    return list(map(lambda x: x.ljust(max_width, '.'), level_map))


def generate_level(level, hero_groups, asphalt_groups):
    """H - герой, a - асфальт, b - книга, E - враг, i - невидимая стена,
       e - выход с уровня, g - пол (большой спрайт асфальта),
       c - checkpoint место где герои разговаривают,
       L - Лена, P - Пионер, B - Босс, S - Славя
       """
    hero, pos_x, pos_y, cnt_books = None, None, None, 0
    coord_checkpoints, cur_checkpoint, exit_pos = [], 0, 0
    for y in range(len(level)):
        for x in range(len(level[y])):
            if level[y][x] == 'a':
                Bound(x, y, DICTIONARY_SPRITES['Bound'], *asphalt_groups)
            if level[y][x] == 'H':
                hero = Hero(DICTIONARY_SPRITES['Hero'], 8, 2, x, y, *hero_groups)
                pos_x, pos_y = x, y
            if level[y][x] == 'b':
                cnt_books += 1
                Book(random.choice(DICTIONARY_SPRITES['Books']), x, y, cnt_books, all_sprites, book_group)
            if level[y][x] == "E":
                Enemy(DICTIONARY_SPRITES['Enemy'], 4, 1, x, y,
                      enemy_group, all_sprites)
            if level[y][x] == 'i':
                Bound(x, y, DICTIONARY_SPRITES['InvisibleBound'], bound_group, invisible_bound)
            if level[y][x] == 'g':
                Bound(x, y, DICTIONARY_SPRITES['BigBound'], *asphalt_groups)
            if level[y][x] == 'c':
                coord_checkpoints.append((cur_checkpoint + 1, x * TILE_WIDTH))
                cur_checkpoint += 1
            if level[y][x] == 'e':
                exit_pos = TILE_WIDTH * x
            if level[y][x] == 'L':
                WHero(DICTIONARY_SPRITES['Lena']['static'], x, y, 'Lena', whero_group, all_sprites)
            if level[y][x] == 'P':
                WHero(DICTIONARY_SPRITES['Pioneer']['static'], x, y, 'Pioneer', whero_group, all_sprites)
            if level[y][x] == 'S':
                WHero(DICTIONARY_SPRITES['Slavya']['static'], x, y, 'Slavya', whero_group, all_sprites)
            if level[y][x] == 'B':
                Boss(DICTIONARY_SPRITES['Pioneer']['static'], x, y, 'Pioneer', all_sprites, boss_group)
    hero.all_books = cnt_books
    return hero, pos_x, pos_y, coord_checkpoints, exit_pos


def draw_text_data(text):
    for i in range(len(text)):
        cur_text = COUNTER_BOOKS_FONT.render(text[i], True, name_colors[CURRENT_THEME])
        screen.blit(cur_text, (0, i * 35))


def terminate():
    # Перед выходом запишем информацию о достижениях
    with open('Data/Achievements/statistic.json', 'w', encoding='utf-8') as f_:
        json.dump(achievements, f_)

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


def move_background(bg_first, bg_second):
    """Перемещение заднего фона"""
    img_width = bg_first.rect.width
    bg_first.rect.x %= -img_width
    bg_second.rect.x %= img_width


def show_death_screen():
    global LoadData
    text = pygame_gui.elements.UITextBox(
        manager=UIManager,
        relative_rect=pygame.Rect(150, 100, 550, 100),
        html_text='Вы поглощены Совенком!',
        object_id='#death_text'
    )
    restart_btn = pygame_gui.elements.UIButton(
        manager=UIManager,
        relative_rect=pygame.Rect(270, 200, 300, 70),
        text='Перезапустить уровень',
        object_id="#death_btn"
    )
    load_btn = pygame_gui.elements.UIButton(
        manager=UIManager,
        relative_rect=pygame.Rect(270, 280, 300, 70),
        text='Загрузить',
        object_id="#death_btn"
    )
    exit_to_menu_btn = pygame_gui.elements.UIButton(
        manager=UIManager,
        relative_rect=pygame.Rect(270, 360, 300, 70),
        text='Выйти в меню',
        object_id="#death_btn"
    )
    exit_from_death_btn = pygame_gui.elements.UIButton(
        manager=UIManager,
        relative_rect=pygame.Rect(270, 440, 300, 70),
        text='Выйти из игры',
        object_id="#death_btn"
    )
    death_settings_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect(5, 555, 40, 40),
        manager=UIManager,
        text='',
        object_id='settings_icon'
    )

    death_screen = True

    while death_screen:
        death_time_delta = clock.tick() / 1000
        for event_death in pygame.event.get():
            if event_death.type == pygame.QUIT:
                if exit_confirmation_circle('Подтверждение',
                                            'Вы действительно хотите выйти из игры?'):
                    kill_buttons([text, restart_btn, load_btn,
                                  exit_to_menu_btn, exit_from_death_btn])
                    if CURRENT_THEME != 'Pioneer':
                        terminate()
                    else:

                        set_bus_to_hell()
                        audio.play_music('Main_theme.mp3')
                        return

            if event_death.type == pygame.USEREVENT:
                if event_death.user_type == pygame_gui.UI_BUTTON_ON_HOVERED:
                    audio.make_sound(1)

                if event_death.user_type == pygame_gui.UI_BUTTON_PRESSED:

                    if event_death.ui_element in {load_btn, death_settings_btn}:
                        for el in [text, restart_btn, load_btn, exit_to_menu_btn,
                                   exit_from_death_btn, death_settings_btn]:
                            el.hide()
                        if event_death.ui_element == load_btn:
                            LoadData = show_load_screen()
                            if LoadData is not None:
                                return
                        else:
                            show_settings_menu()
                        for el in [text, restart_btn, load_btn, exit_to_menu_btn,
                                   exit_from_death_btn, death_settings_btn]:
                            el.show()

                    elif event_death.ui_element == restart_btn:
                        kill_buttons([text, restart_btn, load_btn, exit_to_menu_btn,
                                      exit_from_death_btn, death_settings_btn])
                        return True

                    elif event_death.ui_element == exit_to_menu_btn:
                        if exit_confirmation_circle('Подтверждение',
                                                    f'Вы действительно хотите вернуться к '
                                                    f'{names[CURRENT_THEME]}?'):
                            kill_buttons([text, restart_btn, load_btn,
                                          exit_to_menu_btn, exit_from_death_btn])
                            audio.play_music('Main_theme.mp3')
                            return

                    elif event_death.ui_element == exit_from_death_btn:
                        pygame.event.post(pygame.event.Event(pygame.QUIT))

            UIManager.process_events(event_death)

        screen.fill((0, 0, 0))
        screen.blit(DICTIONARY_SPRITES['DeathScreen'], (0, 0))
        screen.blit(DICTIONARY_SPRITES['HitEffect'], (0, 0))
        UIManager.update(death_time_delta)
        UIManager.draw_ui(screen)
        pygame.display.flip()


def active_pause_menu(image=None, cant_save=False):
    global LoadData
    # Запоминаем исходное изображение экране, уменьшенное до нужных размеров,
    # чтобы в случае сохранения сохранить его в качестве превью
    if image is None:
        preview_to_save = pygame.transform.scale(screen, (175, 110))
        screen.blit(DICTIONARY_SPRITES['DarkScreen'], (0, 0))
        bg = screen.copy()
    else:
        preview_to_save = pygame.transform.scale(image, (175, 110))
        image.blit(DICTIONARY_SPRITES['DarkScreen'], (0, 0))
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
    pause_settings_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect(5, 555, 40, 40),
        manager=UIManager,
        text='',
        object_id='settings_icon'
    )

    pause_activated = True

    while pause_activated:
        pause_time_delta = clock.tick() / 1000
        for event_pause in pygame.event.get():
            if event_pause.type == pygame.QUIT or (event_pause.type == pygame.KEYDOWN and
                                                   event_pause.key ==
                                                   settings['pause']):
                pause_activated = False

            # Закрываем игру или возвращаем константу, которая даст сигнал о выходе в меню,
            # в зависимости от подтверждённого диалога (что сделать нам помогает quit_game)
            if event_pause.type == pygame.USEREVENT:
                if event_pause.user_type == pygame_gui.UI_BUTTON_ON_HOVERED:
                    audio.make_sound(1)
                if event_pause.user_type == pygame_gui.UI_BUTTON_PRESSED:
                    # Попытка выхода из игры - запрашиваем подтверждение
                    if event_pause.ui_element == exit_from_pause_btn:
                        if exit_confirmation_circle('Подтверждение',
                                                    'Вы действительно хотите выйти из игры?'):
                            kill_buttons([release_pause_btn, save_game_btn, load_game_from_pause_btn,
                                          exit_to_menu_btn, exit_from_pause_btn, pause_settings_btn])
                            if CURRENT_THEME != 'Pioneer':
                                terminate()
                            else:

                                set_bus_to_hell()
                                audio.play_music('Main_theme.mp3')
                                raise ExitToMenuException

                    # Попытка выхода в меню - запрашиваем подтверждение
                    if event_pause.ui_element == exit_to_menu_btn:
                        if exit_confirmation_circle('Подтверждение',
                                                    f'Вы действительно хотите вернуться '
                                                    f'к {names[CURRENT_THEME]}?'):
                            kill_buttons([release_pause_btn, save_game_btn, load_game_from_pause_btn,
                                          exit_to_menu_btn, exit_from_pause_btn, pause_settings_btn])
                            audio.play_music('Main_theme.mp3')
                            raise ExitToMenuException

                    # Выходим из режима паузы
                    if event_pause.ui_element == release_pause_btn:
                        pause_activated = False

                    # Запускаем меню загрузки/сохранения, предварительно убрав с экрана кнопки
                    if event_pause.ui_element in {load_game_from_pause_btn, save_game_btn,
                                                  pause_settings_btn}:
                        for btn in [release_pause_btn, save_game_btn, load_game_from_pause_btn,
                                    exit_to_menu_btn, exit_from_pause_btn, pause_settings_btn]:
                            btn.hide()

                        if event_pause.ui_element == load_game_from_pause_btn:
                            LoadData = show_load_screen(ask_for_confirm=True)
                            if LoadData is not None:
                                raise ExitToMenuException
                        elif event_pause.ui_element == save_game_btn:
                            if not cant_save:
                                show_load_screen(save_instead_of_load=True, preview=preview_to_save)
                            else:
                                pygame_gui.windows.ui_message_window.UIMessageWindow(
                                    manager=UIManager,
                                    rect=pygame.Rect(200, 200, 500, 200),
                                    html_message="Хах! Привет от Пионера! Сохраниться не выйдет!"
                                )
                        else:
                            show_settings_menu()

                        for btn in [release_pause_btn, save_game_btn, load_game_from_pause_btn,
                                    exit_to_menu_btn, exit_from_pause_btn, pause_settings_btn]:
                            btn.show()

            UIManager.process_events(event_pause)

        screen.fill((0, 0, 0))
        screen.blit(bg, (0, 0))
        UIManager.update(pause_time_delta)
        UIManager.draw_ui(screen)
        pygame.display.flip()

    kill_buttons([release_pause_btn, save_game_btn, load_game_from_pause_btn, exit_to_menu_btn,
                  exit_from_pause_btn, pause_settings_btn])
    return


def show_dialog(data, start_from=-1, queue=None):
    """Принимает список кортежей [(Имя говорящего, фраза, стандартизирование имя говорящего)]"""
    number_queue = 0
    if queue is None:
        queue = []

    bg = screen.copy()

    ln = len(data)
    cur_phrase = max(start_from, 0)
    text_box = pygame_gui.elements.ui_text_box.UITextBox(
        relative_rect=pygame.Rect(70, 490, 700, 110),
        manager=UIManager,
        html_text='',
        object_id='#dialog_text_box'
    )

    while True:
        dialog_time_delta = clock.tick() / 1000
        for event_dialog in pygame.event.get():
            if event_dialog.type == pygame.QUIT or (event_dialog.type == pygame.KEYDOWN and
                                                    event_dialog.key ==
                                                    settings['pause']):
                x = screen.copy()
                text_box.hide()
                active_pause_menu(x)
                text_box.show()

            elif event_dialog.type == pygame.MOUSEBUTTONDOWN:
                if event_dialog.button == pygame.BUTTON_WHEELUP:
                    cur_phrase = max(0, cur_phrase - 1)
                elif event_dialog.button == pygame.BUTTON_LEFT:
                    cur_phrase += 1
            elif event_dialog.type == pygame.KEYDOWN and event_dialog.key == \
                    settings['shoot']:
                cur_phrase += 1

            UIManager.process_events(event_dialog)

        if cur_phrase >= ln:
            text_box.kill()
            return

        screen.blit(bg, (0, 0))
        """
        if data[cur_phrase][0] == 'ways':
            if len(queue) <= number_queue:
                data[cur_phrase] = data[cur_phrase][0]
            else:
                data[cur_phrase] = data[cur_phrase][queue[number_queue]]
                number_queue += 1
        """
        if data[cur_phrase][0] == "Комм" or data[cur_phrase][0] == "Разум" or data[cur_phrase][0] == "Разработчики":
            text_box.html_text = data[cur_phrase][1]
        else:
            text_box.html_text = f"<font color='{name_colors[data[cur_phrase][2]]}'>" + \
                                 data[cur_phrase][0] + ':</font><br>- ' + data[cur_phrase][1]
            screen.blit(load_image(rf'Sprites/{data[cur_phrase][2]}/dialog_preview.png'), (6, 490))
        text_box.rebuild()
        game.cur_dialog_in_progress = cur_phrase

        UIManager.update(dialog_time_delta)
        UIManager.draw_ui(screen)
        pygame.display.flip()


def get_level_dialog(level):
    dialogs = []
    file_story = open(fr"Data\Story\Level{level}\story", "r", encoding='utf-8').readlines()
    tmp_dialogs = []
    choice_dialog = []
    flag_choice = False
    for i in file_story:
        i = i.strip()
        if i == '!next!':
            dialogs.append(tmp_dialogs)
            tmp_dialogs = []
        elif i == '!or!':
            tmp_dialogs[-1].append(choice_dialog)
            choice_dialog = []
        elif i == '!begin or!':
            tmp_dialogs.append([])
            choice_dialog = []
            flag_choice = True
        elif i == "!end or!":
            tmp_dialogs[-1].append(choice_dialog)
            choice_dialog = []
            flag_choice = False
        else:
            i = i.split(' $$ ')
            if flag_choice:
                choice_dialog.append((i[1], i[2], i[0]))
            else:
                tmp_dialogs.append((i[1], i[2], i[0]))
    return dialogs


def show_achievements_storage():
    bg = load_image(r'Background/Achievements.jpg')
    screen.blit(bg, (0, 0))

    img_coords = [
        (115, 98), (392, 94), (650, 98),
        (254, 215), (544, 215),
        (141, 359), (394, 359), (647, 359)
    ]
    closed_img_coords = [
        (115, 98), (394, 98), (650, 98),
        (254, 215), (544, 215),
        (141, 359), (394, 359), (647, 359)
    ]
    text_coords = [
        (90, 188), (370, 185), (620, 188),
        (224, 299), (514, 299),
        (110, 443), (364, 443), (617, 443)
    ]

    # Перебираем и отрисовываем достижения
    for i in range(1, 9):
        i = str(i)
        if achievements[i]['opened'] == "1":
            img, text = ACHIEVEMENTS_IMAGES[i]
            screen.blit(img, img_coords[int(i) - 1])
        else:
            img, text = ACHIEVEMENTS_IMAGES['0']
            screen.blit(img, closed_img_coords[int(i) - 1])

        screen.blit(text, text_coords[int(i) - 1])

    running_achievements = True

    while running_achievements:
        for event_achievement in pygame.event.get():
            if event_achievement.type == pygame.QUIT or (event_achievement.type == pygame.KEYDOWN and
                                                         event_achievement.key ==
                                                         settings['pause']):
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
                  необходимо передать preview - превью нового сохранения,
    """

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

    load = None  # Если было загружено сохранение
    last_clicked = None
    running_load_screen = True
    confirm_func = False  # Чтобы не запутаться, подтверждён ли диалог удаления или
    #                                                                 загрузки/сохранения

    while running_load_screen:
        load_time_delta = clock.tick() / 1000
        for event_load in pygame.event.get():
            if event_load.type == pygame.QUIT or (event_load.type == pygame.KEYDOWN and
                                                  event_load.key ==
                                                  settings['pause']):
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
                            load = (current_page, last_clicked)
                            running_load_screen = False
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
                                    load = (current_page, last_clicked)
                                    running_load_screen = False

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
    return load


def save_game(page, cell, preview, overwrite=False):
    """Сохраняет игру в клетку cell на странице page
       preview - картинка, отображающаяся в экране загрузок,
       overwrite - было ли до этого сохранение в этой же клетке этой страницы
                    (нужно ли предварительное очищение папки)"""

    # Если идёт перезапись - очистим папку
    if overwrite:
        shutil.rmtree(rf'Saves/{page}/{cell}')

    # Создадим новую папку и сохраним в неё превью, а также время сохранения в отдельный файл
    os.makedirs(rf'Saves/{page}/{cell}')
    pygame.image.save(preview, rf'Saves/{page}/{cell}/preview.jpg')
    with open(rf'Saves/{page}/{cell}/date.txt', 'w', encoding='utf-8') as f:
        f.write(datetime.datetime.now().strftime("%d.%m.%Y %H:%M"))

    # Сохраним в файл всю важную техинформацию о сессии
    with open(rf'Saves/{page}/{cell}/data.json', 'w', encoding='utf-8') as f:
        save_data = {"level": CUR_LEVEL,
                     "dialog_number": game.dialog_number,
                     "hp": game.hero.health,
                     "all_books": game.hero.all_books,
                     "collected_books": game.hero.counter_books,
                     "cur_dialog": game.cur_dialog,
                     "cur_dialog_in_progress": game.cur_dialog_in_progress,
                     "LP": game.LP}
        json.dump(save_data, f)

    # Сохраним карту уровня (расстановку врагом, книг, главного героя и т.д.)
    with open(rf'Saves/{page}/{cell}/map.txt', 'w', encoding='utf-8') as f, \
            open(rf'Data/Levels/level{CUR_LEVEL}', 'r', encoding='utf-8') as raw_map:
        # Скопируем изначальную карту
        map_lines = []
        for map_line in raw_map.readlines():
            map_lines.append(list(map_line))

        # Удалим из неё информацию о подвижных объектах
        for i in range(len(map_lines)):
            for j in range(len(map_lines[i])):
                if map_lines[i][j] in {'H', 'b', 'E'}:
                    map_lines[i][j] = '.'

        # Вычислим расположение подвижных обхектов и сохраним эту информацию на карте
        hr = hero_group.sprites()[0]
        map_lines[hr.rect.y // TILE_HEIGHT + 1][math.ceil(hr.absolute_x / TILE_WIDTH)] = 'H'
        for enm in enemy_group.sprites():
            enm_pos = enm.absolute_x // TILE_WIDTH
            while map_lines[enm.rect.y // TILE_HEIGHT + 1][enm_pos] != '.':
                enm_pos += 1
            map_lines[enm.rect.y // TILE_HEIGHT + 1][enm_pos] = 'E'

        for bk in book_group:
            map_lines[bk.rect.y // TILE_HEIGHT][bk.pos_x] = 'b'

        f.write(''.join(map(lambda x: ''.join(x), map_lines)))


def give_achievement_core(achievement_id):
    """Выдаёт достижение, запоминая его получение и визиализируя это события на экране"""
    if achievements[achievement_id]['opened'] == '0':
        achievements[achievement_id]['opened'] = '1'
        audio.make_sound(7)
        text_box = pygame_gui.elements.UITextBox(
            manager=UIManager,
            relative_rect=pygame.Rect(650, 5, 145, 50),
            html_text='',
            object_id='#achievemets'
        )
        img, text = ACHIEVEMENTS_IMAGES[achievement_id]
        ach_img = pygame_gui.elements.UIImage(
            manager=UIManager,
            image_surface=img,
            relative_rect=pygame.Rect(656, 9, img.get_rect().w, img.get_rect().h)
        )
        ach_text = pygame_gui.elements.UIImage(
            manager=UIManager,
            image_surface=text,
            relative_rect=pygame.Rect(700, 15, text.get_rect().w, text.get_rect().h)
        )

        UIManager.draw_ui(screen)
        clock.tick(1)
        kill_buttons([text_box, ach_img, ach_text])


def give_achievement(achievement_id):
    """Оболочка для функции выдачи достижения, запускающая его на дургом ядре,
       чтобы не останавливать процесс игры во время получение """
    th = Thread(target=give_achievement_core, args=(achievement_id,))
    th.start()


def set_bus_to_hell():
    """Вспомогательная функция для темы Пионера при попытке выхода"""

    global bus_to_hell, image_menu

    bus_to_hell = True
    give_achievement('1')
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


def start_screen():
    """Заставочное видео при запуске игры"""

    camera = cv2.VideoCapture(r'Data\Video\information.mp4')
    i = 1

    run_video = True
    next_video = False
    while run_video:
        for video_event in pygame.event.get():
            if video_event.type == pygame.QUIT or video_event.type == pygame.MOUSEBUTTONDOWN or \
                    video_event.type == pygame.KEYDOWN:
                if i == 1:
                    next_video = True
                elif i == 2:
                    run_video = False

        ret, frame = camera.read()
        if not ret or next_video:
            next_video = False
            camera = cv2.VideoCapture(r'Data\Video\start_screen.mp4')
            ret, frame = camera.read()
            if i == 1:
                i += 1
                audio.play_music('Sergey Eybog - Memories.mp3')

        screen.fill([0, 0, 0])
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        frame = frame.swapaxes(0, 1)
        pygame.surfarray.blit_array(screen, frame)
        pygame.display.update()
        clock.tick(30)

    camera.release()
    cv2.destroyAllWindows()


def check_verdict(verdict):
    """Парсинг вердикта после завершения уровня (пройден ли уровень, какой следующий и т.д.)"""

    go_next_level = False
    cur_level = verdict[0]

    if verdict[1] == 'passed':
        go_next_level = True
        cur_level += 1
    if verdict[1] == 'restart':
        go_next_level = True

    return cur_level, go_next_level


def sum_dict(first_dict, second_dict):
    union_dict = first_dict
    for key, value in second_dict.items():
        union_dict[key] = value
    return union_dict


def save_new_settings(setts):
    global settings
    settings = setts.copy()
    with open('Data/settings.json', 'w', encoding='utf-8') as setts_save:
        json.dump(setts, setts_save)


def remake_buttons(container, setts, ru_names, dy=0):
    """Вспомогательная функция для меню настроек,
       пересоздающая подвижные элементы при движении слайдера"""

    text_array, btn_array = [], []
    for i, (key, value) in enumerate(setts.items()):
        text_array.append(pygame_gui.elements.UILabel(
            manager=UIManager,
            relative_rect=pygame.Rect(38, 50 + 40 * i - dy, 190, 35),
            text=ru_names[key],
            container=container,
            object_id='settings_text'
        ))
        if i == 0:
            slider = pygame_gui.elements.UIHorizontalSlider(
                manager=UIManager,
                container=container,
                relative_rect=pygame.Rect(233, 50 - dy, 465, 35),
                start_value=setts['music_volume'],
                value_range=(0, 100),
                object_id='slider'
            )
        else:
            btn_array.append(pygame_gui.elements.UIButton(
                manager=UIManager,
                container=container,
                text=pygame.key.name(value).capitalize(),
                relative_rect=pygame.Rect(233, 50 + 40 * i - dy, 465, 35),
                object_id="settings_button")
            )

    return slider, btn_array, text_array


def exit_confirmation_circle(title, desc):
    """Создаёт окно UIConfiramtionDialog с названием title и описанием desc
       Возвращает True, если получено подтверждение; False - в ином случае"""

    bg = screen.copy()
    pygame_gui.windows.UIConfirmationDialog(
        rect=pygame.Rect((250, 250), (500, 200)),
        manager=UIManager,
        window_title=title,
        action_long_desc=desc,
        action_short_name='Да',
        blocking=True
    )

    while True:
        td = clock.tick() / 1000
        for tech_event in pygame.event.get():
            UIManager.process_events(tech_event)
            if tech_event.type == pygame.USEREVENT:
                if tech_event.user_type == pygame_gui.UI_CONFIRMATION_DIALOG_CONFIRMED:
                    return True
                elif tech_event.user_type == pygame_gui.UI_WINDOW_CLOSE:
                    return False
        screen.fill((0, 0, 0))
        screen.blit(bg, (0, 0))
        UIManager.update(td)
        UIManager.draw_ui(screen)
        pygame.display.flip()


def show_settings_menu():
    ru_names = {'music_volume': 'Громкость музыки', 'go_right': 'Идти вправо',
                'go_left': 'Идти влево', 'jump': 'Прыжок', 'shoot': 'Выстрел',
                'pause': 'Пауза', 'skip_quest': 'Завершить задание'}
    en_names = {value: key for key, value in ru_names.items()}

    bg = DICTIONARY_SPRITES['Settings_bg']
    new_settings = settings.copy()

    panel = pygame_gui.elements.UIPanel(
        manager=UIManager,
        relative_rect=pygame.Rect(0, 0, 800, 600),
        starting_layer_height=0,
        object_id='#settings'
    )
    slider = pygame_gui.elements.UIVerticalScrollBar(
        manager=UIManager,
        container=panel,
        relative_rect=pygame.Rect(715, 50, 35, 525),
        visible_percentage=1,
        object_id='slider'
    )

    volume_slider, buttons, texts = remake_buttons(panel, new_settings, ru_names)
    run_settings = True
    is_changed = False
    key_is_changing = -1  # Индекс нажатой кнопки, значение которой нужно изменить

    while run_settings:
        settings_time_delta = clock.tick() / 1000
        for event_settings in pygame.event.get():
            UIManager.process_events(event_settings)

            if event_settings.type == pygame.QUIT or (event_settings.type == pygame.KEYDOWN and
                                                      event_settings.key ==
                                                      settings['pause'] and key_is_changing == -1):
                # Если были сделаны изменения, то запросим подтверждение сохранения новых значений
                if is_changed:
                    if exit_confirmation_circle('Настройки изменены', 'Сохранить изменения?'):
                        save_new_settings(new_settings)
                run_settings = False

            elif event_settings.type == pygame.USEREVENT:
                if event_settings.user_type == pygame_gui.UI_BUTTON_PRESSED:
                    # Нажата кнопка, значение которой нужно изменить
                    if event_settings.ui_element in buttons:
                        # Если до этого была другая кнопка, но её значение так и не изменили,
                        # то вернём ей изначальное значение
                        if key_is_changing != -1:
                            if buttons[key_is_changing].text == '':
                                buttons[key_is_changing].text = \
                                    pygame.key.name(settings[en_names[texts[key_is_changing + 1]
                                                    .text]]).capitalize()
                        # Запомим индекс нажатой кнопки
                        # и вместо значение кнопки будем показывать пустое место
                        key_is_changing = buttons.index(event_settings.ui_element)
                        buttons[key_is_changing].text = ''
                        for btn in buttons:
                            btn.rebuild()

            elif event_settings.type == pygame.KEYDOWN:
                # Если нажата клавишу и до этого была выделена нужная кнопка,
                # то изменим её значение на нажатую кнопку
                if key_is_changing != -1:
                    volume_slider.kill()
                    kill_buttons(texts)
                    kill_buttons(buttons)
                    new_settings[en_names[texts[key_is_changing + 1].text]] = event_settings.key
                    volume_slider, buttons, texts = remake_buttons(panel, new_settings, ru_names,
                                                                   dy=slider.scroll_position)
                    is_changed = True
                    key_is_changing = -1

        if slider.check_has_moved_recently():
            # При движении вертикального слайдера вручную передвигаем все подвижыне элементы на
            # экраны, таким образом создавая эффект пролистывания
            volume_slider.kill()
            kill_buttons(texts)
            kill_buttons(buttons)
            volume_slider, buttons, texts = remake_buttons(panel, new_settings, ru_names,
                                                           dy=slider.scroll_position)

        if volume_slider.get_current_value() != settings['music_volume']:
            # Если изменена громкость музыки, то помимо запоминания нового значения сразу
            # же изменим значение громкости в аудиоменеджере
            is_changed = True
            new_settings['music_volume'] = volume_slider.get_current_value()
            audio.change_volume(new_settings['music_volume'])

        screen.fill((0, 0, 0))
        screen.blit(bg, (0, 0))
        UIManager.update(settings_time_delta)
        UIManager.draw_ui(screen)
        pygame.display.flip()

    panel.kill()
    slider.kill()


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

    DICTIONARY_SPRITES = {'Hero': load_image(r'Sprites\Semen\Semen_variant2.1.png'),
                          'Enemy': load_image(r'Sprites\Semen\Semen-test2.png'),
                          'Background1': load_image(r'Background\city_background_sunset.png'),
                          'Background2': load_image(r'Background\city_background_3.png'),
                          'Background3': load_image(r'Background\city_background_day.png'),
                          'Background4': load_image(r'Background\city_background_night.png'),
                          'Background5': load_image(r'Background\city_background_night.png'),
                          'Bound': load_image(r'Background\Constructions\asphalt.png'),
                          'InvisibleBound': load_image(r'Background\Constructions\empty.png'),
                          'Projectile': load_image(r'Background\Constructions\bag.png'),
                          'BossProjectile': load_image(r'Background\Constructions\knifes.png'),
                          'BigBound': load_image(r'Background\Constructions\ground.jpg'),
                          'HitEffect': load_image(r'Background\Hit_effect.png'),
                          'DeathScreen': load_image(r'Background\Death_screen.png'),
                          'DarkScreen': load_image(r'Background\Dark.png'),
                          'BookParticles': load_image(rf'Background\Constructions\effect.png'),
                          'Books': [load_image(rf'Background\Constructions\book{i}.png')
                                    for i in range(1, 7)],
                          'Settings_bg': load_image(rf'Background\Menu_dark.jpg'),
                          'Level_1_intro': load_image(r'Background\First_level_intro.png'),
                          'Level_2_intro': load_image(r'Background\Second_level_intro.png'),
                          'Level_4_intro': load_image(r'Background\Fourth_level_intro.jpg'),
                          'Level_3_intro': load_image(r'Background\Third_level_intro.png'),
                          'Level_5_intro': load_image(r'Background\flash.png'),
                          'EmptyMenu': load_image(r'Background\Menu_empty.jpg'),
                          'magic_shield': load_image(r'Background\shield.png'),
                          'boss_hp_100': load_image(r'Background\hp100.png'),
                          'boss_hp_90': load_image(r'Background\hp90.png'),
                          'boss_hp_80': load_image(r'Background\hp80.png'),
                          'boss_hp_70': load_image(r'Background\hp70.png'),
                          'boss_hp_60': load_image(r'Background\hp60.png'),
                          'boss_hp_50': load_image(r'Background\hp50.png'),
                          'boss_hp_40': load_image(r'Background\hp40.png'),
                          'boss_hp_30': load_image(r'Background\hp30.png'),
                          'boss_hp_20': load_image(r'Background\hp20.png'),
                          'boss_hp_10': load_image(r'Background\hp10.png'),
                          'boss_hp_0': load_image(r'Background\hp0.png'),
                          'Alisa': r'',
                          'Lena': {'static': load_image(r'Sprites\Lena\Lena_spite_state_pos.png'), 'dynamic': r''},
                          'Miku': {'static': r'', 'dynamic': r''},
                          'Ulyana': {'static': r'', 'dynamic': r''},
                          'Slavya': {'static': load_image(r'Sprites\Slavya\Sidewalk\slavay_state_pos.png'),
                                     'dynamic': load_image(r'Sprites\Slavya\Sidewalk\slavay2.png')},
                          'UVAO': {'static': r'', 'dynamic': r''},
                          'Zhenya': {'static': r'', 'dynamic': r''},
                          'OD': {'static': r'', 'dynamic': r''},
                          'Pioneer': {'static': load_image(r'Sprites\Semen\Pioneer_state_pos.png'),
                                      'dynamic': load_image(r'Sprites\Semen\Semen-test2.png')}}

    ACHIEVEMENTS_IMAGES = {"0": (load_image('Achievements/Unopened_achievement.png'),
                                 load_image('Achievements/unopened_title.png')),
                           "1": (load_image('Achievements/bus_to_hell.png'),
                                 load_image('Achievements/road_to_hell.png')),
                           "2": (load_image('Achievements/Lena-detector.png'),
                                 load_image('Achievements/Lena-detector_text.png')),
                           "3": (load_image('Achievements/Invulnerable.png'),
                                 load_image('Achievements/Invulnerable-text.png')),
                           "4": (load_image('Achievements/unopened_title.png'),
                                 load_image('Achievements/unopened_title.png')),
                           "5": (load_image('Achievements/unopened_title.png'),
                                 load_image('Achievements/unopened_title.png')),
                           "6": (load_image('Achievements/unopened_title.png'),
                                 load_image('Achievements/unopened_title.png')),
                           "7": (load_image('Achievements/unopened_title.png'),
                                 load_image('Achievements/unopened_title.png')),
                           "8": (load_image('Achievements/unopened_title.png'),
                                 load_image('Achievements/unopened_title.png'))
                           }

    names = {'Alisa': 'Алисе', 'Miku': 'Мику', 'Lena': 'Лене', 'Slavya': 'Славе',
             'Ulyana': 'Ульяне', 'Zhenya': 'Жене', 'UVAO': 'Юле',
             'Pioneer': 'Пионеру',
             'OD': 'Ольге Дмитриевне'}

    name_colors = {'Alisa': '#fe8800', 'Lena': '#b470ff', 'Miku': '#7fffd4', 'OD': '#32CD32',
                   'Slavya': '#f2c300', 'Ulyana': '#ff533a', 'Zhenya': '#0000CD', 'UVAO': '#A0522D',
                   'Semen': '#F5DEB3', 'Pioneer': '#8B0000', "None": "#F5DEB3"}

    with open('Data/settings.json', 'r', encoding='utf-8') as f:
        settings = json.load(f)

    SIZE = WIDTH, HEIGHT = 800, 600
    FPS = 60

    # Инициализация
    pygame.init()
    screen = pygame.display.set_mode(SIZE)

    with open('Data/Achievements/statistic.json', 'r', encoding='utf-8') as f:
        achievements = json.load(f)

    pygame.display.set_caption('Everlasting Memories')
    pygame.display.set_icon(load_image(r'Sprites\Semen\Idle (7).png'))

    clock = pygame.time.Clock()
    audio = AudioManager()
    start_screen()
    start_screen_transition = screen.copy()

    # Константы для позиционирования объктов
    TILE_WIDTH, TILE_HEIGHT = 50, 50
    # Константа шрифта
    COUNTER_BOOKS_FONT = pygame.font.Font(r'Data\Fonts\Third_font.ttf', 35)

    # Считывание данных файла прохождения (data.json) и заполение данных
    FlagGoNextLevel = False
    LoadData = None
    RestartLevelEvent = pygame.event.custom_type()
    MAX_LEVEL = 5
    CUR_LEVEL = 1

    game = GameManager()

    # Объеденим базовую тему с нужными нами цветами кнопок
    with open(r'Data\Themes\theme_Base.json', 'r') as base:
        a = json.load(base)
    with open(rf'Data\Themes\theme_{CURRENT_THEME}.json', 'r') as colours:
        b = json.load(colours)
    with open(r'Data\Themes\temp.json', 'w') as result:
        json.dump(sum_dict(b, a), result)

    # Создаём менеджер интерфейса с темой для красивого отображения элементов
    UIManager = pygame_gui.UIManager(SIZE, rf'Data/Themes/temp.json')

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
    settings_btn = pygame_gui.elements.UIButton(
        relative_rect=pygame.Rect(5, 555, 40, 40),
        manager=UIManager,
        text='',
        object_id='settings_icon'
    )
    # Фон меню
    image_menu = load_image(rf'Background\Menu\{CURRENT_THEME}\Menu_normal.jpg')

    running = True
    bus_to_hell = False
    Verdict = (None, None)

    # Включаем музыку
    audio.play_music('Main_theme.mp3')

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
            if event.type == pygame.USEREVENT or FlagGoNextLevel:
                if not FlagGoNextLevel and \
                        event.user_type == pygame_gui.UI_CONFIRMATION_DIALOG_CONFIRMED:
                    running = False

                if not FlagGoNextLevel and not bus_to_hell:
                    # Изменяем фон в зависимости он наведённости на одну из кнопок
                    if event.user_type == pygame_gui.UI_BUTTON_ON_UNHOVERED:
                        image_menu = load_image(rf'Background\Menu\{CURRENT_THEME}\Menu_normal.jpg')
                    if event.user_type == pygame_gui.UI_BUTTON_ON_HOVERED:
                        audio.make_sound(1)
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
                                if Lenas_instability >= 90:
                                    image_menu = load_image(
                                        rf'Background\Menu\{CURRENT_THEME}\Menu_exit_knife.jpg')

                if FlagGoNextLevel or event.user_type == pygame_gui.UI_BUTTON_PRESSED:
                    start_game_btn.hide()
                    show_achievements_btn.hide()
                    load_game_btn.hide()
                    exit_btn.hide()
                    settings_btn.hide()

                    if FlagGoNextLevel or event.ui_element == start_game_btn:
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
                        boss_group = pygame.sprite.Group()
                        boss_projectile_group = pygame.sprite.Group()
                        particles_group = pygame.sprite.Group()


                        if LoadData is not None:
                            LoadDataBackup = LoadData
                            Verdict = game.level_init(LoadData, load_from_save=True)
                            if LoadData is LoadDataBackup:
                                LoadData = None
                        else:
                            Verdict = game.start_level(CUR_LEVEL)

                        CUR_LEVEL, FlagGoNextLevel = check_verdict(Verdict)
                        if LoadData is not None:
                            FlagGoNextLevel = True
                        if CUR_LEVEL > MAX_LEVEL:
                            FlagGoNextLevel = False
                        pygame.event.Event(RestartLevelEvent)

                        audio.play_music('Main_theme.mp3')

                    elif event.ui_element == load_game_btn:
                        LoadData = show_load_screen()
                        if LoadData is not None:
                            FlagGoNextLevel = True
                            pygame.event.post(pygame.event.Event(RestartLevelEvent))

                    elif event.ui_element == show_achievements_btn:
                        show_achievements_storage()
                    elif event.ui_element == settings_btn:
                        show_settings_menu()
                    elif event.ui_element == exit_btn:
                        if CURRENT_THEME != 'Pioneer':
                            confirm_exit()
                        else:
                            set_bus_to_hell()

                    if not bus_to_hell and not FlagGoNextLevel:
                        start_game_btn.show()
                        show_achievements_btn.show()
                        load_game_btn.show()
                        exit_btn.show()
                        settings_btn.show()

            UIManager.process_events(event)

        UIManager.update(time_delta)
        if not FlagGoNextLevel:
            screen.blit(image_menu, (0, 0))
        UIManager.draw_ui(screen)
        if start_screen_transition is not None:
            show_image_smoothly(start_screen_transition, bg_end=screen.copy(), mode=1)
            start_screen_transition = None
        pygame.display.flip()

    terminate()
