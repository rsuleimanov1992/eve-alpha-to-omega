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
