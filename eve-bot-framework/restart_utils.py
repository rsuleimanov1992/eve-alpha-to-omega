import win32api
import win32con
import win32gui
import pyautogui
import subprocess
from time import sleep

from voice_func import say_ffplay

LAUNCHER_PATH = r"C:\Users\adm\AppData\Local\eve-online\eve-online.exe"

class InterfaceElement:
    def __init__(self, path):
        self.path = path
        self.is_was_pressed = False

    def click(self, confidence=0.9):
        try:
            location = pyautogui.locateCenterOnScreen(self.path, confidence=confidence)
            pyautogui.moveTo(location)
            sleep(5)
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

def find_and_restore_eve_window():
    """Находит конкретные окна EVE и разворачивает их если они свернуты"""
    def enum_windows_proc(hwnd, windows):
        if win32gui.IsWindowVisible(hwnd):
            window_text = win32gui.GetWindowText(hwnd)
            # Строгая маска: 'EVE' или 'EVE - *' или точный лаунчер
            if (window_text == 'EVE' or 
                window_text.startswith('EVE - ') or 
                window_text == 'Программа запуска EVE Online'):
                windows.append((hwnd, window_text))
        return True
    
    windows = []
    win32gui.EnumWindows(enum_windows_proc, windows)
    
    print(f"Найдено окон EVE: {len(windows)}")
    for hwnd, window_text in windows:
        print(f"Окно: '{window_text}' (hwnd: {hwnd})")
    
    # Приоритет: сначала ищем окно игры ('EVE' или 'EVE - *'), затем лаунчер
    game_window = None
    launcher_window = None
    
    for hwnd, window_text in windows:
        if window_text == 'EVE' or window_text.startswith('EVE - '):
            game_window = (hwnd, window_text)
        elif window_text == 'Программа запуска EVE Online':
            launcher_window = (hwnd, window_text)
    
    # Если есть окно игры - работаем только с ним, лаунчер игнорируем
    if game_window:
        target_window = game_window
    elif launcher_window:
        target_window = launcher_window  
    else:
        # Если окна не найдены - запускаем лаунчер
        print("Окно EVE не найдено")
        print("Запускаю лаунчер!")
        say_ffplay('Окна игры не найдены, запускаю лаунчер')
        subprocess.Popen(LAUNCHER_PATH)
        return False
    
    hwnd, window_text = target_window
    try:
        # Проверяем, свернуто ли окно
        if win32gui.IsIconic(hwnd):
            print(f"Окно '{window_text}' свернуто, разворачиваю")
            say_ffplay('Окно игры свернуто, разворачиваю')
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            sleep(1)
            # Выводим окно на передний план
            win32gui.SetForegroundWindow(hwnd)
            print("Окно развернуто")
            return True
        else:
            # Проверяем, активно ли окно
            current_window = win32gui.GetForegroundWindow()
            if current_window != hwnd:
                print(f"Вывожу окно '{window_text}' на передний план")
                win32gui.SetForegroundWindow(hwnd)
            else:
                print(f"Окно '{window_text}' уже активно")
            return True
    except Exception as e:
        print(f"Ошибка при работе с окном '{window_text}': {e}")
        return False

def start_game():
    # Проверяем, не запущена ли уже игра
    def check_game_running():
        def enum_windows_proc(hwnd, windows):
            if win32gui.IsWindowVisible(hwnd):
                window_text = win32gui.GetWindowText(hwnd)
                if window_text == 'EVE' or window_text.startswith('EVE - '):
                    windows.append((hwnd, window_text))
            return True
        
        windows = []
        win32gui.EnumWindows(enum_windows_proc, windows)
        return len(windows) > 0
    
    # Если игра уже запущена - закрываем её
    if check_game_running():
        say_ffplay('Игра уже запущена, закрываю её')
        print('Обнаружена запущенная игра, закрываю...')
        subprocess.call(['taskkill', '/F', '/IM', 'exefile.exe'])
        sleep(2)
    
    say_ffplay('Запускаю клиент игры')
    subprocess.Popen(LAUNCHER_PATH)
    play = InterfaceElement('eve-bot-framework/images/play.png')
    claim = InterfaceElement('eve-bot-framework/images/claim.png')
    close = InterfaceElement('eve-bot-framework/images/close.png')
    character = InterfaceElement('eve-bot-framework/images/character.png')
    no_chat = InterfaceElement('eve-bot-framework/images/no_chat.png')
    online = InterfaceElement('eve-bot-framework/images/online.png')
    online2 = InterfaceElement('eve-bot-framework/images/online2.png')

    play_clicked = False

    while not no_chat.is_was_pressed:
        if online.find() or online2.find():
            if play.click():
                say_ffplay('Сервер работает!, вхожу ха-хааааааааааааа!')
                play_clicked = True
        
        # Если кнопка play была нажата, проверяем окно игры через несколько секунд
        if play_clicked:
            sleep(5)  # Даем время на запуск игры
            find_and_restore_eve_window()
            play_clicked = False
        
        claim.click()
        sleep(1)
        close.click()
        sleep(1)
        character.click()
        sleep(1)
        no_chat.click()
        sleep(1)

    # Финальная проверка окна перед отключением интерфейса
    find_and_restore_eve_window()
    #off_interface()
    sleep(40)

def close_game():
    say_ffplay('Закрываю игру')
    for _ in range(2):
        subprocess.call(['taskkill', '/F', '/IM', 'exefile.exe'])
        sleep(1)
    
    # Закрываем лаунчер
    subprocess.call(['taskkill', '/F', '/IM', 'eve-online.exe'])
    sleep(2)
    
    # Перезапускаем лаунчер
    subprocess.Popen(LAUNCHER_PATH)
    say_ffplay('Лаунчер перезапущен')

def restart_game():
    close_game()
    start_game()

def connection_lost_observer():
    """ Следит за ошибками которые показывает интерфейс игры и состоянием окна """
    connection_lost = InterfaceElement('eve-bot-framework/images/connection_lost.png')
    check_counter = 0
    
    while True:
        if connection_lost.click(0.8):
            print('ИНТЕРФЕЙС ИГРЫ ВЫДАЛ ОШИБКУ!!! ЗАКРЫВАЕМ ИГРУ')
            close_game()
        
        # Каждые 30 секунд проверяем состояние окна (3 цикла по 10 секунд)
        check_counter += 1
        if check_counter >= 3:
            find_and_restore_eve_window()
            check_counter = 0
            
        sleep(10)
