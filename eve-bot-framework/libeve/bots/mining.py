import re
import time
from libeve.bots import Bot
from libeve.bots.hold_status import HoldStatusBot
from libeve.bots.set_location_and_autopilot import SetLocationAndStartAutopilotBot
from libeve.bots.mining_drones import MiningDronesBot
from libeve.monitoring import ShipHealthMonitor

class MiningBot(Bot):
    def __init__(
        self,
        approach_distance_m=14990,
        lock_distance_m=46000,
        laser_distance_m=14990,
        shield_threshold=40,
        shield_check_interval=3,
        *args, **kwargs
    ):
        super().__init__(*args, **kwargs)
        self.approach_distance_m = approach_distance_m
        self.lock_distance_m = lock_distance_m
        self.laser_distance_m = laser_distance_m
        self.shield_threshold = shield_threshold
        self.shield_check_interval = shield_check_interval
        self._last_announced_shield = 100
        self._cycle_start_time = None
        self._moved_since_last_scan = False
        self.evacuating = False
        self.ship_stop_distance = 11000

    def align_to_homestation(self):
        self.say("Разгон на станцию")
        self.tree.refresh()
        loc_win = self.tree.find_node({"_name": "locations"}, type="LocationsWindow", do_refresh=False)
        if not loc_win:
            btn = self.tree.find_node({"_name": "locations"}, type="ButtonWindow", do_refresh=False)
            if not btn:
                return
            self.click_node(btn)
            t0 = time.time()
            while time.time() - t0 < 5:
                self.tree.refresh()
                loc_win = self.tree.find_node({"_name": "locations"}, type="LocationsWindow", do_refresh=False)
                if loc_win:
                    break
                time.sleep(0.2)
            if not loc_win:
                self.say("Не открылось окно Locations")
                return
        self.tree.refresh()
        entry_node = None
        for node in self.tree.nodes.values():
            if node.type == "PlaceEntry":
                for child_addr in getattr(node, "children", []):
                    child = self.tree.nodes.get(child_addr)
                    if (
                        child
                        and child.type == "EveLabelMedium"
                        and "homestation" in child.attrs.get("_setText", "").lower()
                    ):
                        entry_node = node
                        break
            if entry_node:
                break
        if not entry_node:
            self.say("homestation не найден")
            return
        self.click_node(entry_node, right_click=True)
        self.tree.refresh()
        t1 = time.time()
        align_menu = None
        while time.time() - t1 < 2:
            align_menu = self.tree.find_node(
                {"_name": "context_menu_Align to"}, type="MenuEntryView", do_refresh=False
            )
            if align_menu:
                break
            time.sleep(0.1)
        if align_menu:
            self.click_node(align_menu)
        else:
            self.say("Нет пункта Align to")

    def _activate_lasers_if_needed(self):
        activated = False
        if not self.is_module_active("F1"):
            self.activate_module("F1")
            activated = True
        if not self.is_module_active("F2"):
            self.activate_module("F2")
            activated = True
        if activated:
            self._cycle_start_time = time.time()

    def _deactivate_lasers(self):
        self.deactivate_module("F1")
        self.deactivate_module("F2")
        self.check_hold_and_handle()

    def _lasers_are_active(self):
        return self.is_module_active("F1") or self.is_module_active("F2")

    def _both_lasers_active(self):
        return self.is_module_active("F1") and self.is_module_active("F2")

    def _stop_ship(self):
        self.say("Останавливаю корабль")
        self.deactivate_module("AfterBurner")
        time.sleep(0.3)
        stop_btn = self.tree.find_node({"type": "StopButton"}, type="StopButton", do_refresh=False)
        if not stop_btn:
            stop_btn = self.tree.find_node({"_hint": "Stop The Ship"}, type="StopButton", do_refresh=False)
        if stop_btn:
            self.click_node(stop_btn)
            time.sleep(0.3)
        else:
            self.say("Кнопка Stop не найдена!")

    def _find_selected_item_window(self):
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

    def _find_child_by_name(self, node, type_, name):
        if not node: return None
        stack = [node]
        while stack:
            current = stack.pop()
            if current.type == type_ and current.attrs.get("_name") == name:
                return current
            stack.extend([self.tree.nodes.get(ch) for ch in getattr(current, "children", []) or [] if self.tree.nodes.get(ch)])
        return None

    def _find_button(self, window_node, name):
        return self._find_child_by_name(window_node, "SelectedItemButton", name)

    def _get_label_text(self, window_node):
        cont = self._find_child_by_name(window_node, "ScrollContainer", "labelCont")
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

    def _parse_object_distance(self, label_text):
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

    def _is_target_locked(self, win):
        btn_unlock = self._find_button(win, "selectedItemUnLockTarget")
        btn_lock = self._find_button(win, "selectedItemLockTarget")
        return bool(btn_unlock) and not btn_lock

    def _lock_target(self, win):
        btn = self._find_button(win, "selectedItemLockTarget")
        if btn:
            self.say("Беру в таргет")
            self.click_node(btn)

    def _approach(self, win):
        self.activate_module("AfterBurner")
        btn = self._find_button(win, "selectedItemApproach")
        label_text = self._get_label_text(win)
        _, meters = self._parse_object_distance(label_text) if label_text else (None, None)
        if btn and meters is not None and meters > self.approach_distance_m:
            self.say("Приближаюсь к цели")
            self.click_node(btn)
            self._moved_since_last_scan = True

    def deactivate_lasers_before_scan(self):
        if self._lasers_are_active():
            self.say("Лазеры активны, выключаю перед сканированием.")
            self._deactivate_lasers()

    def run_ore_scanner(self):
        from libeve.bots.ore_survey_scanner import OreSurveyScannerBot
        self.say("Запускаю сканер руды.")
        scanner = OreSurveyScannerBot(
            log_fn=self.log_fn,
            pause_interrupt=self.pause_interrupt,
            pause_callback=self.pause_callback,
            stop_interrupt=self.stop_interrupt,
            stop_callback=self.stop_callback,
            stop_safely_interrupt=self.stop_safely_interrupt,
            stop_safely_callback=self.stop_safely_callback,
        )
        scanner.tree = self.tree
        scanner.scan_and_report()

    def run_ore_priority_selector(self):
        from libeve.bots.ore_survey_priority_selector import OreSurveyPrioritySelectorBot
        self.say("Пропускаю сканирование, выбираю астероид через priority selector.")
        selector = OreSurveyPrioritySelectorBot(
            log_fn=self.log_fn,
            pause_interrupt=self.pause_interrupt,
            pause_callback=self.pause_callback,
            stop_interrupt=self.stop_interrupt,
            stop_callback=self.stop_callback,
            stop_safely_interrupt=self.stop_safely_interrupt,
            stop_safely_callback=self.stop_safely_callback,
        )
        selector.tree = self.tree
        selector.select_priority_group_and_report()

    def wait_after_scan(self, duration, shield_check_fn):
        t_scan = time.time()
        while time.time() - t_scan < duration:
            self.check_interrupts()
            shield_check_fn()
            time.sleep(0.1)

    def _call_autopilot_with_drones(self, drones_bot):
        if self.evacuating:
            return
        self.evacuating = True
        if self._lasers_are_active():
            self._deactivate_lasers()
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
                self.say("Возвращаю дронов перед эвакуацией.")
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

    def check_hold_and_handle(self, drones_bot=None):
        if self.evacuating:
            return False
        try:
            holdbot = HoldStatusBot(
                log_fn=self.log_fn,
                pause_interrupt=self.pause_interrupt,
                pause_callback=self.pause_callback,
                stop_interrupt=self.stop_interrupt,
                stop_callback=self.stop_callback,
                stop_safely_interrupt=self.stop_safely_interrupt,
                stop_safely_callback=self.stop_safely_callback,
            )
            holdbot.tree = self.tree
            is_full = holdbot.is_hold_full()
            if is_full:
                self.say("Трюм полон. Отключаю модули и возвращаю дронов. Хвала создателю!")
                self.align_to_homestation()
                if drones_bot is None:
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
                self._call_autopilot_with_drones(drones_bot)
                return True
        except Exception as e:
            self.say(f"Ошибка проверки трюма: {e}")
        return False

    def check_shield_health(self, drones_bot=None):
        if self.evacuating:
            return
        try:
            monitor = ShipHealthMonitor(self.tree, lambda status: self.notify_health_status(status, drones_bot))
            monitor.check()
        except Exception as e:
            self.say(f"Ошибка мониторинга здоровья щита: {e}")

    def notify_health_status(self, status, drones_bot=None):
        if self.evacuating:
            return
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
                    self._call_autopilot_with_drones(drones_bot)
                    return
            except (ValueError, IndexError):
                self.say("Ошибка обработки состояния щита")

    def mining_sequence(self, interval=0.2, cycles=None, last_cycle_partial=False, partial_time=0):
        last_approach = False
        last_locked = False
        lasers_active = False
        drones_active = False
        last_shield_check = time.time()
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
        stuck_timer_start = None
        mining_cycles_done = 0
        laser_cycle_length = 180

        def do_periodic_checks():
            now = time.time()
            nonlocal last_shield_check
            if (now - last_shield_check) > self.shield_check_interval:
                last_shield_check = now
                self.check_shield_health(drones_bot)
            if self.evacuating:
                return True
            return False

        def _check_and_stop_ship_if_needed(win):
            label_text = self._get_label_text(win) if win else None
            _, meters = self._parse_object_distance(label_text) if label_text else (None, None)
            if self.is_module_active('AfterBurner') and meters is not None and meters <= self.ship_stop_distance:
                self._stop_ship()

        self.tree.refresh()
        win = self._find_selected_item_window()
        target_locked = False
        meters = None
        if win:
            target_locked = self._is_target_locked(win)
            label_text = self._get_label_text(win)
            _, meters = self._parse_object_distance(label_text) if label_text else (None, None)

        if target_locked:
            self.say("Цель уже захвачена при запуске бота.")
            if meters is not None and meters <= self.laser_distance_m:
                if not self._both_lasers_active():
                    self.check_hold_and_handle()
                    self.say("Не все лазеры были включены, включаю.")
                    self._activate_lasers_if_needed()
                    lasers_active = True
                else:
                    self.say("Лазеры уже включены.")
                    self._cycle_start_time = time.time()
                    self.say("Начинаю полный цикл добычи.", narrate=True)
            else:
                self.say("Цель вне радиуса лазеров или неизвестно расстояние.")
            try:
                drones_bot.release_and_mine()
                drones_active = True
            except Exception:
                pass

        while not self.evacuating:
            self.check_interrupts()
            if do_periodic_checks():
                break
            try:
                self.tree.refresh()
            except Exception as e:
                self.say(f"Ошибка обновления дерева UI: {e}")
                time.sleep(interval)
                continue

            win = self._find_selected_item_window()
            _check_and_stop_ship_if_needed(win)

            label_text = self._get_label_text(win) if win else None
            _, meters = self._parse_object_distance(label_text) if label_text else (None, None)

            btn_lock = self._find_button(win, "selectedItemLockTarget") if win else None
            btn_unlock = self._find_button(win, "selectedItemUnLockTarget") if win else None

            if not btn_lock and not btn_unlock:
                self.deactivate_lasers_before_scan()
                if self._moved_since_last_scan:
                    self.run_ore_scanner()
                else:
                    self.run_ore_priority_selector()
                self.wait_after_scan(interval, lambda: self.check_shield_health(drones_bot))
                self._moved_since_last_scan = False
                stuck_timer_start = None
                continue

            name, meters = self._parse_object_distance(label_text) if label_text else (None, None)
            btn_approach = self._find_button(win, "selectedItemApproach")
            need_approach = meters is not None and meters > self.approach_distance_m

            if need_approach:
                if stuck_timer_start is None:
                    stuck_timer_start = time.time()
                elif (time.time() - stuck_timer_start) > 180:
                    self.say("Похоже, застряли в астероидах. Эвакуация.")
                    self._call_autopilot_with_drones(drones_bot)
                    return
            else:
                stuck_timer_start = None

            if need_approach and not last_approach and btn_approach:
                self._approach(win)
                last_approach = True
            if not need_approach:
                last_approach = False

            target_locked = self._is_target_locked(win)
            LOCK_ATTEMPTS = 3
            if meters is not None and meters <= self.lock_distance_m and btn_lock and not btn_unlock and not last_locked:
                for attempt in range(LOCK_ATTEMPTS):
                    self._lock_target(win)
                    if meters is not None and meters <= self.laser_distance_m:
                        if not self._both_lasers_active():
                            self.say("Включаю оба лазера")
                            self._activate_lasers_if_needed()
                            lasers_active = True
                        else:
                            self._cycle_start_time = time.time()
                    else:
                        self.say("Цель слишком далеко для лазеров, жду сближения")

                    t_lock = time.time()
                    locked = False
                    while time.time() - t_lock < 2:
                        self.check_interrupts()
                        if (time.time() - last_shield_check) > self.shield_check_interval:
                            last_shield_check = time.time()
                            self.check_shield_health(drones_bot)
                        if self.evacuating:
                            return
                        time.sleep(0.2)
                        win = self._find_selected_item_window()
                        btn_lock = self._find_button(win, "selectedItemLockTarget") if win else None
                        btn_unlock = self._find_button(win, "selectedItemUnLockTarget") if win else None
                        if btn_unlock and not btn_lock:
                            locked = True
                            break
                    try:
                        drones_bot.release_and_mine()
                        drones_active = True
                    except Exception as e:
                        self.say(f"Ошибка выпуска дронов: {e}")
                    if locked:
                        last_locked = True
                        break
                else:
                    self.deactivate_lasers_before_scan()
                    self.say("Не удалось взять в таргет, ищу новую цель.")
                    if self._moved_since_last_scan:
                        self.run_ore_scanner()
                    else:
                        self.run_ore_priority_selector()
                    self.wait_after_scan(0.3, lambda: self.check_shield_health(drones_bot))
                    self._moved_since_last_scan = False
                    stuck_timer_start = None
                    continue
            if meters is not None and (meters > self.lock_distance_m or target_locked):
                last_locked = False

            lasers_should_be_active = target_locked and (meters is not None) and meters <= self.laser_distance_m
            if lasers_should_be_active:
                if not self._both_lasers_active():
                    self.check_hold_and_handle()
                    self.say("Обнаружено, что хотя бы один лазер выключен. Включаю.")
                    self._activate_lasers_if_needed()
                    lasers_active = True
                else:
                    self._cycle_start_time = self._cycle_start_time or time.time()
            else:
                lasers_active = False

            if self._lasers_are_active() and cycles is not None and self._cycle_start_time is not None:
                if mining_cycles_done < cycles and (time.time() - self._cycle_start_time) >= laser_cycle_length:
                    mining_cycles_done += 1
                    self.say(f"Завершён цикл добычи {mining_cycles_done}")
                    self._cycle_start_time = time.time()
                if mining_cycles_done >= cycles:
                    if last_cycle_partial and partial_time > 0:
                        self.say(f"Выполняю частичный цикл ({partial_time:.1f} секунд)")
                        self._cycle_start_time = time.time()
                        t0 = time.time()
                        while time.time() - t0 < partial_time:
                            self.check_interrupts()
                            if do_periodic_checks():
                                return
                            win = self._find_selected_item_window()
                            _check_and_stop_ship_if_needed(win)
                            btn_lock = self._find_button(win, "selectedItemLockTarget") if win else None
                            btn_unlock = self._find_button(win, "selectedItemUnLockTarget") if win else None
                            target_locked = btn_unlock and not btn_lock
                            if not target_locked:
                                self.say("Цель потеряна во время частичного цикла. Завершаю досрочно.")
                                break
                            if not self._both_lasers_active():
                                self.say("Один из лазеров отключён во время частичного цикла. Включаю оба лазера заново.")
                                self._activate_lasers_if_needed()
                            time.sleep(0.2)
                        self.say("Добыча завершена.")
                        if self._lasers_are_active():
                            self._deactivate_lasers()
                        win = self._find_selected_item_window()
                        btn_unlock = self._find_button(win, "selectedItemUnLockTarget") if win else None
                        if btn_unlock:
                            self.say("Снимаю цель")
                            self.click_node(btn_unlock)
                            t_unlock = time.time()
                            while time.time() - t_unlock < 0.3:
                                self.check_interrupts()
                                if do_periodic_checks():
                                    return
                                time.sleep(0.1)
                        self.deactivate_lasers_before_scan()
                        if self._moved_since_last_scan:
                            self.run_ore_scanner()
                        else:
                            self.run_ore_priority_selector()
                        self.wait_after_scan(interval, lambda: self.check_shield_health(drones_bot))
                        self._moved_since_last_scan = False
                        break
            time.sleep(interval)

    def go(self, cycles=None, last_cycle_partial=False, partial_time=0):
        self._cycle_start_time = None
        self.evacuating = False
        self.mining_sequence(cycles=cycles, last_cycle_partial=last_cycle_partial, partial_time=partial_time)
