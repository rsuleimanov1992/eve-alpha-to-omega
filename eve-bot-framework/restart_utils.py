import pyautogui
import subprocess
from time import sleep


LAUNCHER_PATH = r"C:\Users\user\AppData\Local\eve-online\eve-online.exe"


def image_click(btn: str):
    for _ in range(40):
        try:
            location = pyautogui.locateCenterOnScreen(btn, confidence=0.9)
            pyautogui.moveTo(location)
            pyautogui.click()
            print(f'Кнопка {btn} нажата!')
            return
        except pyautogui.ImageNotFoundException:
            sleep(1)
    print(f'Кнопка {btn} НЕ найдена!')


def start_game():
    subprocess.Popen(LAUNCHER_PATH)
    image_click('eve-bot-framework/images/play.png')
    image_click('eve-bot-framework/images/character.png')
    image_click('eve-bot-framework/images/no_chat.png')
    sleep(20)

def restart_game():
    for _ in range(3):
        subprocess.call(['taskkill', '/F', '/IM', 'exefile.exe'])

    start_game()
