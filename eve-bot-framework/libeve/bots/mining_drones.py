import re
import time
import win32api
import win32con
from libeve.bots import Bot

class MiningDronesBot(Bot):
    def find_drones_window(self):
        self.tree.refresh()
        return self.tree.find_node({"_name": "droneview"}, type="DronesWindow", do_refresh=False)

    def find_drone_label(self, label):
        for node in self.tree.find_node({}, type="EveLabelMedium", select_many=True, do_refresh=False) or []:
            if node.attrs.get("_setText", "").startswith(label):
                return node
        return None

    def drones_in_bay(self):
        label = self.find_drone_label("Drones in Bay")
        if not label:
            return 0
        m = re.search(r"\((\d+)", label.attrs.get("_setText", ""))
        return int(m.group(1)) if m else 0

    def drones_in_space(self):
        label = self.find_drone_label("Drones in Space")
        if not label:
            return 0
        m = re.search(r"\((\d+)", label.attrs.get("_setText", ""))
        return int(m.group(1)) if m else 0

    def all_drones_in_bay(self):
        label_space = self.find_drone_label("Drones in Space")
        return self.drones_in_space() == 0 and (label_space is not None)

    def send_key(self, key):
        key = key.lower()
        if key == 'shift+f':
            win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
            win32api.keybd_event(ord('F'), 0, 0, 0)
            time.sleep(0.1)
            win32api.keybd_event(ord('F'), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
        elif key == 'shift+r':
            win32api.keybd_event(win32con.VK_SHIFT, 0, 0, 0)
            win32api.keybd_event(ord('R'), 0, 0, 0)
            time.sleep(0.1)
            win32api.keybd_event(ord('R'), 0, win32con.KEYEVENTF_KEYUP, 0)
            win32api.keybd_event(win32con.VK_SHIFT, 0, win32con.KEYEVENTF_KEYUP, 0)
        elif key == 'f':
            win32api.keybd_event(ord('F'), 0, 0, 0)
            time.sleep(0.1)
            win32api.keybd_event(ord('F'), 0, win32con.KEYEVENTF_KEYUP, 0)

    def focus_drones_window(self):
        drones_label = self.tree.find_node({"_setText": "Drones"}, type="Label", do_refresh=False)
        if drones_label:
            self.click_node(drones_label)
            # time.sleep(0.2)1
        else:
            win = self.find_drones_window()
            if win:
                self.click_node(win)
                # time.sleep(0.2)

    def release_and_mine(self):
        self.tree.refresh()
        if not self.find_drones_window():
            self.say("Нет окна дронов - пропускаю работу с дронами")
            return False
        if self.drones_in_bay() > 0 and self.drones_in_space() == 0:
            self.say("Выпускаю дронов")
            self.send_key('shift+f')
            for _ in range(10):
                time.sleep(0.5)
                if self.drones_in_space() > 0:
                    self.say(f"Дроны выпущены: {self.drones_in_space()}")
                    break
        elif self.drones_in_space() > 0:
            self.say(f"Дроны уже в космосе: {self.drones_in_space()}")
        else:
            self.say("Нет дронов в наличии")
            return False
        self.focus_drones_window()         # <--- важно для F!
        self.say("Команда добычи дронов")
        self.send_key('f')
        return True

    def recall(self):
        self.tree.refresh()
        if not self.find_drones_window():
            self.say("Нет окна дронов - дронов нет")
            return
        if self.drones_in_space() > 0:
            self.say("Возвращаю дронов в ангар")
            self.focus_drones_window()
            self.send_key('shift+r')
            for _ in range(20):
                time.sleep(0.5)
                if self.drones_in_space() == 0:
                    self.say("Дроны возвращены в ангар")
                    break
            else:
                self.say("Дроны не вернулись в ангар за отведенное время")
        else:
            self.say("Дроны уже в ангаре")

    def recall_blocking(self, check_interval=1, timeout=60):
        self.tree.refresh()
        if not self.find_drones_window():
            self.say("Нет окна дронов - дронов нет")
            return
        if self.drones_in_space() == 0:
            self.say("Дроны уже в ангаре")
            return
        self.say("Возвращаю дронов в ангар (ожидание подтверждения!)")
        self.focus_drones_window()
        self.send_key('shift+r')
        waited = 0
        while waited < timeout:
            self.tree.refresh()
            if self.all_drones_in_bay():
                self.say("Дроны возвращены в ангар (подтверждено)")
                return
            time.sleep(check_interval)
            waited += check_interval
        self.say("Дроны не вернулись за отведенное время!")
