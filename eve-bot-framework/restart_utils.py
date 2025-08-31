import pyautogui
import subprocess
from time import sleep
import win32api
import win32con


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


def off_interface():
    win32api.keybd_event(win32con.VK_CONTROL, 0, 0, 0)
    win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
    win32api.keybd_event(win32con.VK_F9, 0, 0, 0)
    sleep(0.05)
    win32api.keybd_event(win32con.VK_F9, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
    win32api.keybd_event(win32con.VK_CONTROL, 0, win32con.KEYEVENTF_KEYUP, 0)


def start_game():
    subprocess.Popen(LAUNCHER_PATH)
    play = InterfaceElement('eve-bot-framework/images/play.png')
    claim = InterfaceElement('eve-bot-framework/images/claim.png')
    close = InterfaceElement('eve-bot-framework/images/close.png')
    character = InterfaceElement('eve-bot-framework/images/character.png')
    no_chat = InterfaceElement('eve-bot-framework/images/no_chat.png')

    while not no_chat.is_was_pressed:
        play.click()
        claim.click()
        close.click()
        character.click()
        no_chat.click()
        sleep(1)

    off_interface()
    sleep(15)


def close_game():
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
