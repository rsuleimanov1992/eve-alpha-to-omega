import ctypes
import win32gui
from datetime import datetime


def get_screensize():
    return ctypes.windll.user32.GetSystemMetrics(
        0
    ), ctypes.windll.user32.GetSystemMetrics(1)


def with_node(query={}, address=None, select_many=False, contains=False):
    def inner(func):
        def wrapper(self):
            node = self.tree.find_node(query, address, select_many, contains)
            return func(self, node)

        return wrapper

    return inner


def window_enumeration_handler(hwnd, top_windows):
    top_windows.append((hwnd, win32gui.GetWindowText(hwnd)))


class CustomLog:
    start = None

    @classmethod
    def set_start(cls):
        cls.start = datetime.now()
        cls.write_log('Начинаю')
    
    @classmethod
    def create_sla_log(cls):
        if cls.start is None:
            return
        diff = abs(datetime.now() - cls.start)
        total_seconds = int(diff.total_seconds())
        minutes = total_seconds // 60
        seconds = total_seconds % 60
        cls.start = None
        cls.write_log(f'Задача выполнена за {minutes} минут, {seconds} секунд\n')

    @classmethod
    def write_log(cls, log_text: str):
        if not log_text.endswith('\n'):
            log_text += '\n'

        with open('log', 'a', encoding='utf-8') as f:
            f.write(f"[{datetime.now().strftime('%d.%m.%Y %H:%M:%S')}] - {log_text}")


class GoodBelt:
    belt_node = None
    asteroid_data = None

    __BELT_THRESHOLD = 20000

    @classmethod
    def set_belt_node(cls, belt_node):
        """ Сохранит ноду пояса астероидов куда собрался лететь """
        cls.belt_node = belt_node

    @classmethod
    def set_asteroid_data(cls, asteroid_data):
        """ Сохранит данные астероидов для дальнейшего вычисления """
        cls.asteroid_data = asteroid_data

    @classmethod
    def get_belt_node(cls):
        """ Отдаст ноу если в поясе астероидов много скордита """
        if cls.belt_node and cls.asteroid_data:
            total = sum(asteroid.get('volume') for asteroid in cls.asteroid_data
                        if 'scordite' in asteroid.get('name').lower())
            if total < cls.__BELT_THRESHOLD:
                cls.belt_node, cls.asteroid_data = None, None
            CustomLog.write_log(f'Скордита {total}')
        else:
            CustomLog.write_log(f'НЕД ДАННЫХ {bool(cls.belt_node)} {bool(cls.asteroid_data)}')
            cls.belt_node, cls.asteroid_data = None, None
        return cls.belt_node
