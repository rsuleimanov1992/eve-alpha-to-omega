import win32api
import win32con
import pyautogui
import subprocess
from time import sleep

from voice_func import say_ffplay

LAUNCHER_PATH = r"C:\Users\adm\AppData\Local\eve-online\eve-online.exe"
# LAUNCHER_PATH = r"C:\Users\user\AppData\Local\eve-online\eve-online.exe"


class InterfaceElement:
    def __init__(self, path):
        self.path = path
        self.is_was_pressed = False

    def click(self, confidence=0.9):
        try:
            location = pyautogui.locateCenterOnScreen(self.path, confidence=confidence)
            pyautogui.moveTo(location)
            pyautogui.click()
            print(f'Кнопка {self.path} нажата!')
            self.is_was_pressed = True
            return True
        except pyautogui.ImageNotFoundException:
            return False

    def find(self, confidence=0.9):
        try:
            pyautogui.locateCenterOnScreen(self.path, confidence=confidence)
            return True
        except pyautogui.ImageNotFoundException:
            return False


def off_interface():
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
    win32api.keybd_event(win32con.VK_F9, 0, 0, 0)
    sleep(0.05)
    win32api.keybd_event(win32con.VK_F9, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


def start_game():
    say_ffplay('Запускаю клиент игры')
    subprocess.Popen(LAUNCHER_PATH)
    play = InterfaceElement('eve-bot-framework/images/play.png')
    claim = InterfaceElement('eve-bot-framework/images/claim.png')
    close = InterfaceElement('eve-bot-framework/images/close.png')
    character = InterfaceElement('eve-bot-framework/images/character.png')
    no_chat = InterfaceElement('eve-bot-framework/images/no_chat.png')
    online = InterfaceElement('eve-bot-framework/images/online.png')
    online2 = InterfaceElement('eve-bot-framework/images/online2.png')

    while not no_chat.is_was_pressed:
        if online.find() or online2.find():
            if play.click():
                say_ffplay('Сервер работает!, вхожу ха-хааааааааааааа!')
        claim.click()
        close.click()
        character.click()
        no_chat.click()
        sleep(1)

    off_interface()
    sleep(20)


def close_game():
    say_ffplay('Закрываю игру')
    for _ in range(2):
        subprocess.call(['taskkill', '/F', '/IM', 'exefile.exe'])
        sleep(1)


def restart_game():
    close_game()
    start_game()


def connection_lost_observer():
    """ Следит за ошибками которые показывает интерфейс игры """
    connection_lost = InterfaceElement('eve-bot-framework/images/connection_lost.png')
    while True:
        if connection_lost.click(0.8):
            print('ИНТЕРФЕЙС ИГРЫ ВЫДАЛ ОШИБКУ!!! ЗАКРЫВАЕМ ИГРУ')
            close_game()
        sleep(10)
