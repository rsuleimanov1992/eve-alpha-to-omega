import time
import re
import random
import os
import datetime
from libeve.bots import Bot
from libeve.bots.ore_survey_scanner import OreSurveyScannerBot
from libeve.bots.mining_drones import MiningDronesBot
from libeve.monitoring import ShipHealthMonitor


class AsteroidBeltScannerBot(Bot):
    def __init__(self, *args, shield_threshold=50, shield_check_interval=5, **kwargs):
        super().__init__(*args, **kwargs)
        self.blacklisted_belts = set()
        self.shield_threshold = shield_threshold
        self.shield_check_interval = shield_check_interval
        self._last_announced_shield = 100
        self._last_shield_check = 0
        self._blacklist_file = 'belt_blacklist.txt'
        self._blacklist_reset_time = None
        self._load_blacklist()

    def _load_blacklist(self):
        if not os.path.exists(self._blacklist_file):
            self._blacklist_reset_time = datetime.datetime.now()
            self.blacklisted_belts = set()
            return
        with open(self._blacklist_file, 'r', encoding='utf-8') as f:
            lines = f.read().splitlines()
        if not lines:
            self._blacklist_reset_time = datetime.datetime.now()
            self.blacklisted_belts = set()
            return
        try:
            self._blacklist_reset_time = datetime.datetime.strptime(lines[0], '%Y-%m-%d %H:%M')
        except Exception:
            self._blacklist_reset_time = datetime.datetime.now()
        self.blacklisted_belts = set(lines[1:])

    def _save_blacklist(self):
        with open(self._blacklist_file, 'w', encoding='utf-8') as f:
            reset_time_str = self._blacklist_reset_time.strftime('%Y-%m-%d %H:%M') if self._blacklist_reset_time else datetime.datetime.now().strftime('%Y-%m-%d %H:%M')
            f.write(reset_time_str + '\n')
            for belt in self.blacklisted_belts:
                f.write(belt + '\n')

    def _reset_blacklist_if_needed(self):
        now = datetime.datetime.now()
        today_14 = now.replace(hour=14, minute=0, second=0, microsecond=0)
        if self._blacklist_reset_time is None or self._blacklist_reset_time < today_14 <= now:
            self.blacklisted_belts = set()
            self._blacklist_reset_time = today_14
            self._save_blacklist()
            self.say("Черный список астероидных поясов сброшен.")

    def _add_to_blacklist(self, belt_name):
        self._reset_blacklist_if_needed()
        if belt_name not in self.blacklisted_belts:
            self.blacklisted_belts.add(belt_name)
            self._save_blacklist()

    def _is_blacklisted(self, belt_name):
        self._reset_blacklist_if_needed()
        return belt_name in self.blacklisted_belts

    def send_key_combination(self, combination):
        try:
            import win32con
            import win32api
            if combination.lower() == 'alt+d':
                win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)
                win32api.keybd_event(ord('D'), 0, 0, 0)
                time.sleep(0.05)
                win32api.keybd_event(ord('D'), 0, win32con.KEYEVENTF_KEYUP, 0)
                win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)
                time.sleep(0.05)
        except ImportError:
            self.say("win32api не установлен, эмуляция Alt+D невозможна.")

    def ensure_directional_scanner_open(self, timeout=3):
        if self.find_directional_scanner():
            return True
        self.say("Открываю Directional Scanner (alt+d)")
        self.send_key_combination('alt+d')
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.find_directional_scanner():
                return True
            time.sleep(0.2)
        self.say("Directional Scanner не найден, уходим на автопилот.")
        self.run_autopilot()
        return False

    def find_directional_scanner(self):
        return any(
            lab.attrs.get("_setText", "") == "Directional Scanner"
            for lab in self.tree.find_node({}, type="Label", select_many=True) or []
        )

    def do_directional_scan_and_check(self, timeout=3):
        self.click_directional_scan_button()
        t0 = time.time()
        while time.time() - t0 < timeout:
            if self.pirates_stronghold_check():
                return True
            time.sleep(0.2)
        return False

    def click_directional_scan_button(self):
        for btn in self.tree.find_node({}, type="ScanButton", select_many=True, do_refresh=False) or []:
            for lab in self.tree.find_node({}, type="EveLabelMedium", select_many=True, do_refresh=False) or []:
                if lab.attrs.get("_setText", "") == "Scan":
                    self.click_node(btn)
                    return True
        self.say("Кнопка Scan не найдена")
        return False

    def pirates_stronghold_check(self):
        for label in self.tree.find_node({}, type="Label", select_many=True, do_refresh=False) or []:
            if "Stronghold" in label.attrs.get("_setText", ""):
                self.say(f"Обнаружен Stronghold: {label.attrs.get('_setText','')}")
                self.say("Запускаю автопилот на станцию.")
                self.run_autopilot()
                return True
        return False

    def parse_distance(self, text):
        t = text.replace(" ", "").replace(",", ".").lower()
        if "au" in t:
            try:
                return float(t.replace("au", "")) * 149597870
            except Exception:
                pass
        if "km" in t:
            try:
                return float(t.replace("km", ""))
            except Exception:
                pass
        if "m" in t:
            try:
                return float(t.replace("m", "")) / 1000
            except Exception:
                pass
        return float('inf')
        
    def find_selected_item_window(self):
        self.tree.refresh()
        for node in self.tree.find_node({"_name": "content"}, type="Container", select_many=True, do_refresh=False) or []:
            labels = [
                self.tree.nodes.get(l)
                for c in getattr(node, "children", [])
                for h in getattr(self.tree.nodes.get(c), "children", []) or []
                for m in getattr(self.tree.nodes.get(h), "children", []) or []
                for w in getattr(self.tree.nodes.get(m), "children", []) or []
                for l in getattr(self.tree.nodes.get(w), "children", []) or []
            ]
            if any(label and label.type == "Label" and label.attrs.get("_setText") == "Selected Item" for label in labels):
                return node
        return None

    def find_child_by_name(self, node, type_, name):
        if not node: return None
        stack = [node]
        while stack:
            current = stack.pop()
            if current.type == type_ and current.attrs.get("_name") == name:
                return current
            stack.extend([self.tree.nodes.get(ch) for ch in getattr(current, "children", []) or [] if self.tree.nodes.get(ch)])
        return None

    def find_button(self, window_node, name):
        return self.find_child_by_name(window_node, "SelectedItemButton", name)

    def get_label_text(self, window_node):
        cont = self.find_child_by_name(window_node, "ScrollContainer", "labelCont")
        if not cont: return None
        for ch in getattr(cont, "children", []):
            clip = self.tree.nodes.get(ch)
            if not clip or clip.attrs.get("_name") != "clipCont": continue
            for cc in getattr(clip, "children", []):
                main = self.tree.nodes.get(cc)
                if not main or main.attrs.get("_name") != "mainCont": continue
                for lab in getattr(main, "children", []):
                    label = self.tree.nodes.get(lab)
                    if label and label.type == "EveLabelMedium":
                        return label.attrs.get("_setText", "")
        return None

    def parse_object_distance(self, label_text):
        if not label_text or "<br>" not in label_text:
            return label_text or "", None
        name, dist = label_text.split("<br>", 1)
        m = re.search(r"([0-9\s.,]+)\s*(km|m)\b", dist.strip().lower())
        if not m:
            return name.strip(), None
        value, unit = m.groups()
        value = value.replace(" ", "").replace(",", ".")
        try:
            value = float(value)
        except Exception:
            return name.strip(), None
        meters = value * 1000 if unit == "km" else value
        return name.strip(), meters

    def check_shield_health(self, drones_bot=None):
        try:
            monitor = ShipHealthMonitor(self.tree, lambda status: self.notify_health_status(status, drones_bot))
            monitor.check()
        except Exception as e:
            self.say(f"Ошибка мониторинга здоровья щита: {e}")
            
    def notify_health_status(self, status, drones_bot=None):
        if "Shield" in status:
            try:
                shield_percent = int(status.split(": ")[1].replace("%", ""))
                announce_levels = [90, 80, 70, 60, 50]
                for level in announce_levels:
                    if self._last_announced_shield > level >= shield_percent:
                        self.say(f"Щит {level}%")
                        break
                self._last_announced_shield = min(self._last_announced_shield, shield_percent)
                if shield_percent <= self.shield_threshold:
                    self.say(f"Щит на {shield_percent}%, критическое состояние. Собираю дронов и запускаю автопилот.")
                    from libeve.bots.set_location_and_autopilot import SetLocationAndStartAutopilotBot
                    # -- Исправление: всегда пытаемся вернуть дронов --
                    if drones_bot is None:
                        try:
                            drones_bot = MiningDronesBot(
                                log_fn=self.log_fn,
                                pause_interrupt=self.pause_interrupt,
                                pause_callback=self.pause_callback,
                                stop_interrupt=self.stop_interrupt,
                                stop_callback=self.stop_callback,
                                stop_safely_interrupt=self.stop_safely_interrupt,
                                stop_safely_callback=self.stop_safely_callback,
                            )
                            drones_bot.tree = self.tree
                        except Exception as e:
                            self.say(f"Ошибка создания MiningDronesBot: {e}")
                            drones_bot = None
                    if drones_bot:
                        try:
                            self.say("Возвращаю дронов перед уходом на автопилот.")
                            drones_bot.recall_blocking()
                        except Exception as e:
                            self.say(f"Ошибка возврата дронов: {e}")
                    autopilot = SetLocationAndStartAutopilotBot(
                        log_fn=self.log_fn,
                        pause_interrupt=self.pause_interrupt,
                        pause_callback=self.pause_callback,
                        stop_interrupt=self.stop_interrupt,
                        stop_callback=self.stop_callback,
                        stop_safely_interrupt=self.stop_safely_interrupt,
                        stop_safely_callback=self.stop_safely_callback,
                    )
                    autopilot.tree = self.tree
                    autopilot.go()
                    raise Exception("Эвакуация из-за низкого щита")
            except (ValueError, IndexError):
                self.say("Ошибка обработки состояния щита")

    def get_shield_percent(self):
        try:
            node = self.tree.find_node({"_name": "shieldGauge"}, type="ShipHudSpriteGauge", do_refresh=False)
            if node:
                val = node.attrs.get("_lastValue")
                if val is not None:
                    return round(float(val) * 100)
        except Exception:
            pass
        return 100

    def in_space(self):
        return not self.tree.find_node({"_name": "undockButton"}, type="UndockButton", do_refresh=False)

    def switch_to_mining_tab(self, timeout=5):
        self.tree.refresh()
        t0 = time.time()
        while time.time() - t0 < timeout:
            for node in self.tree.find_node({}, type="EveLabelMedium", select_many=True, do_refresh=False) or []:
                if node.attrs.get("_setText", "").lower() == "mining":
                    self.click_node(node)
                    t1 = time.time()
                    while time.time() - t1 < 2:
                        self.tree.refresh()
                        time.sleep(0.2)
                    return True
            time.sleep(0.2)
        self.say("Нет вкладки Mining!")
        return False
        
    def collect_sorted_belts(self):
        self.tree.refresh()
        belts = []
        for entry in self.tree.find_node({}, type="OverviewScrollEntry", select_many=True, do_refresh=False) or []:
            labels = []
            for child_addr in getattr(entry, "children", []):
                node = self.tree.nodes.get(child_addr)
                if node and node.type == "OverviewLabel":
                    labels.append(node)
            name_node = None
            dist_node = None
            for l in labels:
                t = l.attrs.get("_text", "").strip()
                if "asteroid belt" in t.lower():
                    name_node = l
                elif any(x in t.lower() for x in ("m", "km", "au")):
                    dist_node = l
            if name_node and dist_node:
                dist_val = self.parse_distance(dist_node.attrs.get("_text", ""))
                belts.append((name_node, dist_val))
        belts = [b for b in belts if b[1] != float('inf')]
        belts.sort(key=lambda x: x[1])
        return [b[0] for b in belts]
        
    def asteroids_in_belt(self):
        self.tree.refresh()
        asteroids = []
        for entry in self.tree.find_node({}, type="OverviewScrollEntry", select_many=True, do_refresh=False) or []:
            labels = []
            for child_addr in getattr(entry, "children", []):
                node = self.tree.nodes.get(child_addr)
                if node and node.type == "OverviewLabel":
                    labels.append(node)
            name = None
            distance = None
            for l in labels:
                t = l.attrs.get("_text", "").strip()
                if t.lower().startswith("asteroid") and "belt" not in t.lower():
                    name = l
                elif any(x in t for x in ("km", "m", "au")):
                    distance = l
            if name and distance:
                asteroids.append((name, distance))
        return asteroids

    def approach_closest_asteroid(self, asteroids):
        drones_released = False
        drones_bot = MiningDronesBot(
            log_fn=self.log_fn,
            pause_interrupt=self.pause_interrupt,
            pause_callback=self.pause_callback,
            stop_interrupt=self.stop_interrupt,
            stop_callback=self.stop_callback,
            stop_safely_interrupt=self.stop_safely_interrupt,
            stop_safely_callback=self.stop_safely_callback,
        )
        drones_bot.tree = self.tree

        def release_drones_only():
            self.tree.refresh()
            if not drones_bot.find_drones_window():
                self.say("Нет окна дронов - пропускаю работу с дронами")
                return False
            if drones_bot.drones_in_bay() > 0 and drones_bot.drones_in_space() == 0:
                self.say("Выпускаю дронов")
                drones_bot.send_key('shift+f')
                t0 = time.time()
                while time.time() - t0 < 5:
                    time.sleep(0.2)
                    if drones_bot.drones_in_space() > 0:
                        self.say(f"Дроны выпущены: {drones_bot.drones_in_space()}")
                        break
            return True

        asteroids = [a for a in asteroids if a]
        if not asteroids:
            self.say("Нет целей")
            self.run_autopilot()
            return

        sorted_asteroids = sorted(
            asteroids,
            key=lambda x: self.parse_distance(x[1].attrs.get("_text", ""))
        )

        for asteroid_node, _ in sorted_asteroids:
            if not drones_released:
                try:
                    release_drones_only()
                    drones_released = True
                except Exception as e:
                    self.say(f"Ошибка запуска дронов: {e}")

            self.say(f"Выбираю: {asteroid_node.attrs.get('_text', '')}")
            self.click_node(asteroid_node)
            t0 = time.time()
            win = None
            while time.time() - t0 < 3:
                win = self.find_selected_item_window()
                if win:
                    break
                time.sleep(0.2)
            if not win:
                self.say("Не найдено окно Selected Item")
                continue
                
            label_text = self.get_label_text(win)
            _, meters = self.parse_object_distance(label_text) if label_text else (None, None)
            btn_approach = self.find_button(win, "selectedItemApproach")
            
            if btn_approach and meters is not None and meters > 19500:
                self.say("Приближаюсь к цели")
                self.click_node(btn_approach)
                self.activate_module("ALT1")
                t0 = time.time()
                while time.time() - t0 < 30:
                    self.tree.refresh()
                    win = self.find_selected_item_window()
                    label_text = self.get_label_text(win) if win else None
                    _, meters = self.parse_object_distance(label_text) if label_text else (None, None)
                    if meters is not None and meters <= 19500:
                        break
                    if (time.time() - self._last_shield_check) > self.shield_check_interval:
                        self._last_shield_check = time.time()
                        self.check_shield_health(drones_bot)
                    time.sleep(0.5)

            for _ in range(60):
                cur_time = time.time()
                if (cur_time - self._last_shield_check) > self.shield_check_interval:
                    self._last_shield_check = cur_time
                    self.check_shield_health(drones_bot)

                self.tree.refresh()
                win = self.find_selected_item_window()
                label_text = self.get_label_text(win) if win else None
                _, meters = self.parse_object_distance(label_text) if label_text else (None, None)

                if meters is None:
                    self.say("Дистанция не определена, возможно цель исчезла")
                    break

                if meters <= 19500:
                    self.say(f"Близко: {asteroid_node.attrs.get('_text', '')} ({meters:.0f} м)")
                    self.run_ore_survey_scan()
                    return

                time.sleep(0.2)
                
        self.say("Нет целей для сближения")
        self.run_autopilot()

    def run_ore_survey_scan(self):
        ore_bot = OreSurveyScannerBot(
            log_fn=self.log_fn,
            pause_interrupt=self.pause_interrupt,
            pause_callback=self.pause_callback,
            stop_interrupt=self.stop_interrupt,
            stop_callback=self.stop_callback,
            stop_safely_interrupt=self.stop_safely_interrupt,
            stop_safely_callback=self.stop_safely_callback,
        )
        ore_bot.tree = self.tree
        ore_bot.scan_and_report()

    def go(self):
        self._reset_blacklist_if_needed()
        if not self.ensure_directional_scanner_open():
            return
        if self.do_directional_scan_and_check():
            return

        self._last_shield_check = 0
        if not self.in_space():
            self.say("Не в космосе")
            return
        if not self.switch_to_mining_tab():
            self.say("Нет Mining")
            return
        
        asteroids = self.asteroids_in_belt()
        if len(asteroids) >= 3:
            self.say(f"Астероидов не менее чем: {len(asteroids)}")
            self.approach_closest_asteroid(asteroids)
            return

        belt_nodes = self.collect_sorted_belts()
        self.say(f"Пояса: {len(belt_nodes)}")
        if not belt_nodes:
            self.say("Нет поясов")
            self.blacklisted_belts.clear()
            self._save_blacklist()
            self.run_autopilot()
            return
        belts_left = belt_nodes.copy()
        while belts_left:
            belt_node = random.choice(belts_left)
            belt_name = belt_node.attrs.get("_text", "")
            if self._is_blacklisted(belt_name):
                belts_left.remove(belt_node)
                continue

            warp_success = self.warp_to_belt(belt_node)
            if warp_success:
                self.wait_until_warp_finished()
                t0 = time.time()
                while time.time() - t0 < 3:
                    self.tree.refresh()
                    if self.in_space():
                        break
                    time.sleep(0.2)
                if not self.ensure_directional_scanner_open():
                    return
                if self.do_directional_scan_and_check():
                    return
            else:
                self.say("В поясе")
                self.close_context_menu()
                t0 = time.time()
                while time.time() - t0 < 1:
                    self.tree.refresh()
                    time.sleep(0.2)

            asteroids = self.asteroids_in_belt()
            if len(asteroids) >= 1:
                self.say(f"Астероидов не менее чем: {len(asteroids)}")
                self.approach_closest_asteroid(asteroids)
                return
            else:
                self.say("Пусто, чс")
                self._add_to_blacklist(belt_name)
                belts_left.remove(belt_node)

        self.say("Нет аномалий")
        self.blacklisted_belts.clear()
        self._save_blacklist()
        self.run_autopilot()

    def warp_to_belt(self, belt_node):
        self.say(f"Варп: {belt_node.attrs.get('_text', '')}")
        self.click_node(belt_node, right_click=True)
        t0 = time.time()
        while time.time() - t0 < 2:
            warp_menu = self.tree.find_node({"_name": "context_menu_Warp to Within"}, type="MenuEntryView")
            if warp_menu:
                self.click_node(warp_menu)
                return True
            time.sleep(0.2)
        return False

    def close_context_menu(self):
        self.send_key('esc')
        time.sleep(0.1)

    def send_key(self, key):
        try:
            import pyautogui
            pyautogui.press(key)
        except ImportError:
            self.say("pyautogui не установлен, send_key не работает.")
            pass

    def run_autopilot(self):
        from libeve.bots.set_location_and_autopilot import SetLocationAndStartAutopilotBot
        try:
            drones_bot = MiningDronesBot(
                log_fn=self.log_fn,
                pause_interrupt=self.pause_interrupt,
                pause_callback=self.pause_callback,
                stop_interrupt=self.stop_interrupt,
                stop_callback=self.stop_callback,
                stop_safely_interrupt=self.stop_safely_interrupt,
                stop_safely_callback=self.stop_safely_callback,
            )
            drones_bot.tree = self.tree
            self.say("Возвращаю дронов перед запуском автопилота.")
            drones_bot.recall_blocking()
        except Exception as e:
            self.say(f"Ошибка возврата дронов (перед автопилотом): {e}")
        autopilot_bot = SetLocationAndStartAutopilotBot(
            log_fn=self.log_fn,
            pause_interrupt=self.pause_interrupt,
            pause_callback=self.pause_callback,
            stop_interrupt=self.stop_interrupt,
            stop_callback=self.stop_callback,
            stop_safely_interrupt=self.stop_safely_interrupt,
            stop_safely_callback=self.stop_safely_callback,
        )
        autopilot_bot.tree = self.tree
        autopilot_bot.go()
