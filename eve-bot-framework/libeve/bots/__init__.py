from libeve.utils import get_screensize, window_enumeration_handler
from libeve.interface import UITree
import sys
import time
import threading
import win32api, win32con, win32gui
import win32com.client
import pythoncom
from libeve import KEYMAP
from voice_func import say_ffplay


speaker = win32com.client.Dispatch("SAPI.SpVoice")


def speak_in_thread(message):
    pythoncom.CoInitialize()
    try:
        speaker.Speak(message)
    finally:
        pythoncom.CoUninitialize()


class Bot(object):
    def __init__(
        self,
        log_fn=print,
        pause_interrupt: threading.Event = None,
        pause_callback=None,
        stop_interrupt: threading.Event = None,
        stop_callback=None,
        stop_safely_interrupt: threading.Event = None,
        stop_safely_callback=None,
    ):
        self.log_fn = log_fn
        self.pause_interrupt = pause_interrupt
        self.pause_callback = pause_callback
        self.stop_interrupt = stop_interrupt
        self.stop_callback = stop_callback
        self.stop_safely_interrupt = stop_safely_interrupt
        self.stop_safely_callback = stop_safely_callback
        self.stopping_safely = False
        self.paused = False
        self.tree = None

    def initialize(self):
        self.say("Запуск")
        self.say(f"Экран: {get_screensize()}", narrate=False)
        self.tree = UITree()
        self.say("Готово")

    def check_pause_interrupt(self):
        while self.pause_interrupt and self.pause_interrupt.is_set():
            if not self.paused:
                self.paused = True
                if self.pause_callback and callable(self.pause_callback):
                    self.pause_callback()
            time.sleep(0.25)
        if self.paused:
            self.paused = False
            if self.pause_callback and callable(self.pause_callback):
                self.pause_callback()

    def stop(self):
        self.tree = None

    def check_stop_interrupt(self):
        if self.stop_interrupt and self.stop_interrupt.is_set():
            if self.stop_callback and callable(self.stop_callback):
                self.stop()
                self.stop_callback()
                sys.exit(1)

    def check_stop_safely_interrupt(self):
        if self.stop_safely_interrupt and self.stop_safely_interrupt.is_set():
            if (
                not self.stopping_safely
                and self.stop_safely_callback
                and callable(self.stop_safely_callback)
            ):
                self.log_fn("Безопасная остановка")
                self.stopping_safely = True
                self.ensure_within_station()
                self.stop_safely_callback()
                sys.exit(1)

    def check_interrupts(self):
        self.check_pause_interrupt()
        self.check_stop_interrupt()
        self.check_stop_safely_interrupt()

    def speak(self, text):
        if not say_ffplay(text, rate=1.5):
            threading.Thread(target=speak_in_thread, args=(text,)).start()

    def say(self, text, narrate=True):
        self.check_interrupts()
        self.log_fn(text)
        if narrate:
            self.speak(text)

    def focus(self, prefix="eve - "):
        self.check_interrupts()
        top_windows = []
        win32gui.EnumWindows(window_enumeration_handler, top_windows)
        for i in top_windows:
            if prefix in i[1].lower():
                win32gui.ShowWindow(i[0], 5)
                win32gui.SetForegroundWindow(i[0])
                break
        # Ставим короткую паузу 0.2сек для срабатывания фокуса
        time.sleep(0.2)

    def move_cursor_to_node(self, node):
        if isinstance(node, list):  # КОСТЫЛЬ!!! почему то вместо ноды сюда попадает пустой лист
            return 0, 0             # после перезапуска

        self.check_interrupts()
        x = int(node.x * self.tree.width_ratio) + node.attrs.get("_displayWidth", 0) // 2
        y = int(node.y * self.tree.height_ratio) + node.attrs.get("_displayHeight", 0) // 2
        win32api.SetCursorPos((x, y))
        # Делаем короткую паузу, чтобы система успела отрисовать курсор
        time.sleep(0.1)
        return x, y

    def click_node(self, node, right_click=False, times=1, expect=[], expect_args={}):
        self.check_interrupts()
        x, y = self.move_cursor_to_node(node)
        down_event = win32con.MOUSEEVENTF_RIGHTDOWN if right_click else win32con.MOUSEEVENTF_LEFTDOWN
        up_event = win32con.MOUSEEVENTF_RIGHTUP if right_click else win32con.MOUSEEVENTF_LEFTUP
        for i in range(times):
            win32api.mouse_event(down_event, x, y, 0, 0)
            time.sleep(0.05)   # Было: 0.05
            win32api.mouse_event(up_event, x, y, 0, 0)
            time.sleep(0.15)   # Было: 0.15
        for expectation in expect:
            if not self.wait_for(expectation, until=10, **expect_args):
                win32api.mouse_event(down_event, x, y, 0, 0)
                time.sleep(0.05)
                win32api.mouse_event(up_event, x, y, 0, 0)
                time.sleep(0.10)
                while not (tmp_node := self.tree.find_node(address=node.address, do_refresh=False)):
                    time.sleep(0.3)
                node = tmp_node
                return self.click_node(
                    node=node,
                    right_click=right_click,
                    times=times,
                    expect=expect,
                    expect_args=expect_args
                )
        # Короткая пауза для UI-отклика
        time.sleep(0.07)
        return x, y

    def drag_node_to_node(self, src_node, dest_node):
        self.check_interrupts()
        x, y = self.move_cursor_to_node(src_node)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTDOWN, x, y, 0, 0)
        time.sleep(0.15)
        x, y = self.move_cursor_to_node(dest_node)
        win32api.mouse_event(win32con.MOUSEEVENTF_LEFTUP, x, y, 0, 0)
        time.sleep(0.15)
        return x, y

    def wait_for(
        self,
        query={},
        address=None,
        type=None,
        select_many=False,
        contains=False,
        until=0,
    ):
        self.check_interrupts()
        started = time.time()
        node = None
        while not (
            node := self.tree.find_node(query, address, type, select_many, contains)
        ):
            if until and time.time() - started >= until:
                break
            time.sleep(0.15)
        return node
    
    def quit_if_connection_lost(self):
        if self.tree.find_node({"_setText": "Connection Lost"}):
            raise Exception('Connection Lost')

    def undock(self):
        undock_btn = self.wait_for({"_setText": "Undock"}, type="LabelThemeColored")
        self.say("Undock")
        self.click_node(undock_btn)
        self.wait_for_overview()

    def wait_for_overview(self):
        self.wait_for({"_setText": "Overview"}, type="EveLabelSmall", contains=True)

    def wait_until_warp_finished(self):
        self.wait_for({"_setText": "Warp Drive Active"})
        self.say("Варп актив")
        while self.tree.find_node({"_setText": "Warp Drive Active"}):
            time.sleep(0.2)
        self.say("Прыжок окончен")
        time.sleep(0.2)

    def wait_until_jump_finished(self):
        self.wait_for({"_setText": "Jumping"})
        self.say("Прыжок")
        while self.tree.find_node({"_setText": "Jumping"}):
            time.sleep(0.5)
        time.sleep(0.2)

    def recall_drones(self):
        if not self.wait_for({"_setText": "Drones in Bay (0)"}, type="EveLabelMedium", until=5):
            return
        self.say("Возврат дронов")
        drones_in_space = self.wait_for(
            {"_setText": "Drones in Local Space ("},
            type="EveLabelMedium",
            contains=True,
        )
        self.click_node(drones_in_space, right_click=True)
        return_btn = self.wait_for(
            {"_setText": "Return to Drone Bay ("}, type="EveLabelMedium", contains=True
        )
        self.click_node(return_btn)
        # Ожидаем максимум до 3 сек
        self.wait_for({"_setText": "Drones in Local Space (0)"}, type="EveLabelMedium", until=3)
        # Нет рекурсии/ожидания по 2 секунды

    def ensure_within_station(self):
        undock_btn = self.wait_for({"_setText": "Undock"}, type="LabelThemeColored", until=5)
        if undock_btn:
            return
        self.recall_drones()
        while True:
            self.wait_for_overview()
            self.say("Ищу станцию")
            time.sleep(0.5)
            station = self.wait_for({"_text": self.station}, type="OverviewLabel", until=10)
            if not station:
                warpto_tab = self.wait_for({"_setText": "WarpTo"}, type="LabelThemeColored")
                self.click_node(
                    warpto_tab,
                    times=2,
                    expect=[{"_text": self.station}],
                    expect_args={"type": "OverviewLabel"},
                )
                station = self.wait_for({"_text": self.station}, type="OverviewLabel")
            self.click_node(station)
            dock_btn = self.wait_for({"_name": "selectedItemDock"}, type="Container")
            self.click_node(dock_btn)
            if self.wait_for({"_setText": "Establishing Warp Vector"}, until=5):
                self.wait_until_warp_finished()
            break
        self.wait_for({"_setText": "Undock"}, type="LabelThemeColored")
        time.sleep(0.5)

    def fleetup(self):
        if not self.wait_for({"_name": "fleetwindow"}, type="FleetWindow", until=5):
            self.wait_for({"_setText": "Join Fleet?"}, type="EveCaptionLarge")
            yes_btn = self.wait_for({"_setText": "Yes"}, type="LabelThemeColored")
            self.click_node(yes_btn)
        self.say("Флот готов")

    def is_module_active(self, slot_key):
        slot = self.tree.find_node({"_name": KEYMAP[slot_key]}, type="ShipSlot")
        if not slot:
            return False
        for glow in self.tree.find_node({"_name": "glow"}, type="Sprite", select_many=True, do_refresh=False) or []:
            if self.tree.nodes[glow.parent].attrs.get("_name") == KEYMAP[slot_key]:
                return True
        return False

    def activate_module(self, slot_key):
        if not self.is_module_active(slot_key):
            slot = self.tree.find_node({"_name": KEYMAP[slot_key]}, type="ShipSlot", do_refresh=False)
            if slot:
                self.click_node(slot)
                t0 = time.time()
                while time.time() - t0 < 2:
                    if self.is_module_active(slot_key):
                        break
                    time.sleep(0.2)

    def deactivate_module(self, slot_key):
        if self.is_module_active(slot_key):
            self.say(f"Деактивирую модуль в слоте {slot_key}")
            slot = self.tree.find_node({"_name": KEYMAP[slot_key]}, type="ShipSlot", do_refresh=False)
            if slot:
                self.click_node(slot)
                t0 = time.time()
                while time.time() - t0 < 2:
                    if not self.is_module_active(slot_key):
                        break
                    time.sleep(0.2)
