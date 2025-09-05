import re
import time
import json
from datetime import datetime

from libeve.bots import Bot
from libeve.bots.mining_drones import MiningDronesBot
from libeve.monitoring import ShipHealthMonitor
from libeve.bots.hold_status import HoldStatusBot
from libeve.utils import GoodBelt


class SurveyScanResults:
    MAX = 20

    @classmethod
    def update_max_asteroid_val(cls, current_num: int):
        """ Обновляет максимальное кол-во астероидов которое встречается в Survey Scan Results """
        if current_num > cls.MAX:

            cls.MAX = current_num

class OreSurveyPrioritySelectorBot(Bot):
    ORES = {
        "Massive Scordite",
        "Condensed Scordite",
        "Scordite",

        "Dense Veldspar",
        "Concentrated Veldspar",
        "Veldspar",

        "Solid Pyroxeres",
        "Rich Pyroxeres",
        "Pyroxeres"
    }

    ORES_KOF = {
        "Massive Scordite": 1.1,
        "Condensed Scordite": 0.99,
        "Scordite": 0.98,

        "Dense Veldspar": 0.30,
        "Concentrated Veldspar": 0.29,
        "Veldspar": 0.28,

        "Solid Pyroxeres": 0.25,
        "Viscous Pyroxeres": 0.24,
        "Pyroxeres": 0.23
    }

    ENTRY_RE = re.compile(
        r"^(?P<name>[^<]+)<t><right>(?P<amount>[\d\s]+)<t><right>(?P<volume>[\d\s\w]+)<t><right>(?P<distance>[\d\s\w]+)$"
    )
    LASER_RANGE_M = 14990
    DIST_PENALTY_PER_KM = 0.03
    NUM_LASERS = 2
    LASER_YIELD = 1500
    LASER_CYCLE_SEC = 180
    SHIP_SPEED_MPS = 300

    def __init__(self, *args, shield_threshold=50, shield_check_interval=5, **kwargs):
        super().__init__(*args, **kwargs)
        self.shield_threshold = shield_threshold
        self.shield_check_interval = shield_check_interval
        self._last_announced_shield = 100
        self._last_shield_check = 0

    def create_asteroid_log(self, all_entries):
        filtered_entries = sorted([
            {
                'volume': entry['volume'],
                'distance': entry['distance'],
                'distance_m': entry['distance_m'],
                'score': entry['score'],
                'kof': entry['kof'],
                'name': entry['name']
            }
            for entry in all_entries
        ], key=lambda x: x['score'], reverse=True)

        filename = rf"asteroids.json"
        with open(filename, "w") as file:
            json.dump(filtered_entries, file, indent=2)

    def get_hold_free_volume(self):
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
        try:
            holdbot.select_mining_hold()
            cur, max_, percent = holdbot.get_capacity()
            free = max_ - cur
            return max(free, 0)
        except Exception:
            return None

    def parse_volume(self, volume_str):
        v = volume_str.replace("m3", "").replace(" ", "").replace(",", ".")
        try:
            return float(v)
        except Exception:
            return 0

    def _asteroid_metrics(self, volume, distance_m, max_yield=None, debug_name=None, kof=None):
        orig_volume = volume
        debug_msgs = []

        distance_m = max((distance_m or 0) - self.LASER_RANGE_M, 0)
        if max_yield is not None:
            if volume > max_yield:
                debug_msgs.append(f"Трюм почти полон: свободно {max_yield:.0f} кубов, исходно {volume:.0f} кубов ({debug_name})")
                volume = max_yield
                debug_msgs.append(f"Объём добычи скорректирован до {volume:.0f} кубов")
            else:
                debug_msgs.append(f"Трюм свободен: {max_yield:.0f} кубов, добыча {volume:.0f} кубов ({debug_name})")
        travel_time = distance_m / self.SHIP_SPEED_MPS if (distance_m and self.SHIP_SPEED_MPS) else 0
        cycles = int(volume // (self.NUM_LASERS * self.LASER_YIELD))
        rest = volume % (self.NUM_LASERS * self.LASER_YIELD)
        total_yield = cycles * self.NUM_LASERS * self.LASER_YIELD + rest
        total_time = cycles * self.LASER_CYCLE_SEC
        last_cycle_partial = rest > 0
        partial_time = 0
        if last_cycle_partial:
            partial_time = (rest / (self.NUM_LASERS * self.LASER_YIELD)) * self.LASER_CYCLE_SEC
            total_time += partial_time
        total_time += travel_time
        penalty_kof = 1 - distance_m / 1000 * self.DIST_PENALTY_PER_KM
        score = min(volume, max_yield) * penalty_kof * kof
        debug_msgs.append(f"Будет {cycles} полных циклов и {int(partial_time)} секунд частичного (дистанция {distance_m or 0:.0f} метров)")
        return score, cycles, last_cycle_partial, partial_time, debug_msgs

    def check_shield_health(self, drones_bot=None):
        try:
            monitor = ShipHealthMonitor(self.tree, lambda status: self.notify_health_status(status, drones_bot))
            monitor.check()
        except Exception as e:
            self.say(f"Проблема щита: {e}")

    def notify_health_status(self, status, drones_bot=None):
        if "Shield" in status:
            try:
                shield_percent = int(status.split(": ")[1].replace("%", ""))
                for level in [90, 80, 70, 60, 50]:
                    if self._last_announced_shield > level >= shield_percent:
                        self.say(f"Щит {level}%")
                        break
                self._last_announced_shield = min(self._last_announced_shield, shield_percent)
                if shield_percent <= self.shield_threshold:
                    self.say("Щит критичен, ухожу")
                    from libeve.bots.set_location_and_autopilot import SetLocationAndStartAutopilotBot
                    # --- ОБНОВЛЕНИЕ: recall drones гарантирован ---
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
                            self.say("Дроны домой")
                            drones_bot.recall_blocking()
                        except Exception as e:
                            self.say(f"Ошибка дронов: {e}")
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
                    raise Exception("Эвакуация")
            except (ValueError, IndexError):
                self.say("Ошибка щита")

    def click_clear_in_survey_scan(self):
        self.tree.refresh()
        scan_view = self.tree.find_node({"_name": "SurveyScanView"}, type="SurveyScanView", do_refresh=False)
        if not scan_view:
            return False
        for button in self.tree.find_node({}, type="Button", select_many=True, do_refresh=False) or []:
            for ch_addr in getattr(button, "children", []):
                child = self.tree.nodes.get(ch_addr)
                if child and child.type == "EveLabelMedium" and child.attrs.get("_setText", "").strip().lower() == "clear":
                    self.say("Закрываю сканер")
                    self.click_node(button)
                    t0 = time.time()
                    while time.time() - t0 < 2.0:
                        self.tree.refresh()
                        if not self.tree.find_node({"_name": "SurveyScanView"}, type="SurveyScanView", do_refresh=False):
                            break
                        time.sleep(0.1)
                    return True
        return False

    def run_belt_scanner(self):
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
            self.click_clear_in_survey_scan()
            try:
                drones_in_space = drones_bot.drones_in_space()
                self.say(f"Ангар: {drones_bot.drones_in_bay()}, Космос: {drones_in_space}")
                if drones_in_space > 0:
                    self.say("Дроны домой")
                    drones_bot.recall_blocking()
                    t0 = time.time()
                    while time.time() - t0 < 3.0:
                        self.tree.refresh()
                        if drones_bot.drones_in_space() == 0:
                            break
                        time.sleep(0.1)
                    self.tree.refresh()
                    self.say(f"Ангар: {drones_bot.drones_in_bay()}, Космос: {drones_bot.drones_in_space()}")
                else:
                    self.say("Дроны уже дома")
            except Exception as e:
                self.say(f"Ошибка дронов: {e}")
        except Exception as e:
            self.say(f"Ошибка MiningDronesBot: {e}")
        from libeve.bots.asteroid_belt_scanner import AsteroidBeltScannerBot
        scanner_bot = AsteroidBeltScannerBot(
            log_fn=self.log_fn,
            pause_interrupt=self.pause_interrupt,
            pause_callback=self.pause_callback,
            stop_interrupt=self.stop_interrupt,
            stop_callback=self.stop_callback,
            stop_safely_interrupt=self.stop_safely_interrupt,
            stop_safely_callback=self.stop_safely_callback,
        )
        scanner_bot.tree = self.tree
        scanner_bot.go()

    def run_survey_scanner(self):
        from libeve.bots.ore_survey_scanner import OreSurveyScannerBot
        survey_bot = OreSurveyScannerBot(
            log_fn=self.log_fn,
            pause_interrupt=self.pause_interrupt,
            pause_callback=self.pause_callback,
            stop_interrupt=self.stop_interrupt,
            stop_callback=self.stop_callback,
            stop_safely_interrupt=self.stop_safely_interrupt,
            stop_safely_callback=self.stop_safely_callback,
        )
        survey_bot.tree = self.tree
        survey_bot.scan_and_report()

    def select_priority_group_and_report(self):
        cur_time = time.time()
        if (cur_time - self._last_shield_check) > self.shield_check_interval:
            self._last_shield_check = cur_time
            self.check_shield_health(None)
        self.tree.refresh()
        scan_view = self.tree.find_node({"_name": "SurveyScanView"}, type="SurveyScanView", do_refresh=False)
        if not scan_view:
            self.say("Сканер не найден, пробую запустить сканирование снова")
            from libeve.bots.ore_survey_scanner import OreSurveyScannerBot
            survey_bot = OreSurveyScannerBot(
                log_fn=self.log_fn,
                pause_interrupt=self.pause_interrupt,
                pause_callback=self.pause_callback,
                stop_interrupt=self.stop_interrupt,
                stop_callback=self.stop_callback,
                stop_safely_interrupt=self.stop_safely_interrupt,
                stop_safely_callback=self.stop_safely_callback,
            )
            survey_bot.tree = self.tree
            survey_bot.scan_and_report()
            return

        free_volume = self.get_hold_free_volume()
        if free_volume is not None:
            self.say(f"Свободно в трюме: {free_volume:.0f} кубов")

        all_entries = []
        for node in self.tree.nodes.values():
            if node.type == "TextBody" and node.attrs.get("_name") == "entryLabel":
                text = node.attrs.get("_setText", "")
                m = self.ENTRY_RE.match(text)
                if not m:
                    continue
                name = m.group("name").strip()
                if name not in self.ORES:
                    continue
                volume_str = m.group("volume")
                volume = self.parse_volume(volume_str)
                distance_str = m.group("distance").replace(" ", "")
                distance_m = None
                if distance_str.endswith("km"):
                    try:
                        distance_m = float(distance_str[:-2]) * 1000
                    except Exception:
                        distance_m = None
                elif distance_str.endswith("m"):
                    try:
                        distance_m = float(distance_str[:-1])
                    except Exception:
                        distance_m = None
                score, cycles, last_cycle_partial, partial_time, debug_msgs = self._asteroid_metrics(
                    volume, distance_m, max_yield=free_volume, debug_name=name, kof=self.ORES_KOF[name]
                )
                for msg in debug_msgs:
                    pass
                all_entries.append({
                    "name": name,
                    "volume": volume,
                    "volume_str": volume_str,
                    "distance": m.group("distance"),
                    "distance_m": distance_m,
                    "score": score,
                    "cycles": cycles,
                    "last_cycle_partial": last_cycle_partial,
                    "partial_time": partial_time,
                    "raw_text": text,
                    "node": node,
                    "kof": self.ORES_KOF[name],
                })

        SurveyScanResults.update_max_asteroid_val(len(all_entries))
        if len(all_entries) == SurveyScanResults.MAX:
            self.say(f'Астероидов {SurveyScanResults.MAX}')
            all_entries = all_entries[:len(all_entries) - 2]
        self.create_asteroid_log(all_entries)
        GoodBelt.set_asteroid_data(all_entries)

        def phrase(best):
            c = best['cycles']
            p = best['partial_time']
            if c > 0 and p > 0:
                return f"{c} полных цикла и частичный {int(p)} секунд"
            elif c > 0:
                return f"{c} полных цикла"
            elif p > 0:
                return f"частичный {int(p)} секунд"
            else:
                return "1 цикл"

        if all_entries:
            best = max(all_entries, key=lambda e: e['score'])
            node = best.get("node")
            if node:
                self.click_node(node, right_click=False)
                from libeve.bots.mining import MiningBot
                mining_bot = MiningBot(
                    log_fn=self.log_fn,
                    pause_interrupt=self.pause_interrupt,
                    pause_callback=self.pause_callback,
                    stop_interrupt=self.stop_interrupt,
                    stop_callback=self.stop_callback,
                    stop_safely_interrupt=self.stop_safely_interrupt,
                    stop_safely_callback=self.stop_safely_callback,
                )
                mining_bot.tree = self.tree
                mining_bot.go(
                    cycles=best["cycles"],
                    last_cycle_partial=best["last_cycle_partial"],
                    partial_time=best["partial_time"]
                )
            else:
                self.say("Астероид не найден")
                self.run_survey_scanner()
            return
        self.say("Руда не найдена")
        self.run_belt_scanner()
