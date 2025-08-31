import re
import time
from libeve.bots import Bot
from .ore_survey_priority_selector import OreSurveyPrioritySelectorBot
from libeve.bots.mining_drones import MiningDronesBot
from libeve.monitoring import ShipHealthMonitor

class OreSurveyScannerBot(Bot):
    ORE_RE = re.compile(r'^(.+?)\s*\[\s*(\d+)\s*\]$')

    def __init__(self, *args, shield_threshold=50, shield_check_interval=5, **kwargs):
        super().__init__(*args, **kwargs)
        self.shield_threshold = shield_threshold
        self.shield_check_interval = shield_check_interval
        self._last_announced_shield = 100
        self._last_shield_check = 0

    def check_shield_health(self, drones_bot=None):
        try:
            monitor = ShipHealthMonitor(self.tree, lambda status: self.notify_health_status(status, drones_bot))
            monitor.check()
        except Exception as e:
            self.say(f"Ошибка мониторинга щита: {e}")

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
                    self.say(f"Щит на {shield_percent}%, критическое состояние. Собираю дронов и запускаю автопилот.")
                    from libeve.bots.set_location_and_autopilot import SetLocationAndStartAutopilotBot
                    # Исправление: всегда пробуем вернуть дронов через новый MiningDronesBot, если drones_bot не передан
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

    def activate_survey_scanner(self):
        self.say("Включаю сканер руды", narrate=True)
        self.activate_module("SyrveyScanner")

    def get_ore_list(self):
        self.tree.refresh()
        scan_view = self.tree.find_node({"_name": "SurveyScanView"}, type="SurveyScanView")
        if not scan_view:
            return []
        ores = []
        for node in self._walk_children(scan_view):
            if node.type == "Container" and node.attrs.get("_name") == "labelClipper":
                for child_addr in getattr(node, "children", []):
                    label = self.tree.nodes.get(child_addr)
                    if label and label.type == "EveLabelMedium":
                        text = label.attrs.get("_setText", "")
                        if text:
                            ores.append(text)
        return ores

    def _walk_children(self, node):
        yield node
        for child_addr in getattr(node, "children", []):
            child = self.tree.nodes.get(child_addr)
            if child:
                yield from self._walk_children(child)

    def scan_and_report(self):
        self.activate_survey_scanner()
        # Классика: просто ждем 2 секунды, потом обновляем дерево
        time.sleep(2.5)
        self.tree.refresh()
        ores = self.get_ore_list()
        if not ores:
            self.say("Астероидов нет", narrate=True)
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
                drones_bot.recall_blocking()
            except Exception as e:
                self.say(f"Ошибка возврата дронов: {e}")
            from libeve.bots.asteroid_belt_scanner import AsteroidBeltScannerBot
            belt_scanner = AsteroidBeltScannerBot(
                log_fn=self.log_fn,
                pause_interrupt=self.pause_interrupt,
                pause_callback=self.pause_callback,
                stop_interrupt=self.stop_interrupt,
                stop_callback=self.stop_callback,
                stop_safely_interrupt=self.stop_safely_interrupt,
                stop_safely_callback=self.stop_safely_callback,
            )
            belt_scanner.tree = self.tree
            belt_scanner.go()
            return
        prio_bot = OreSurveyPrioritySelectorBot(
            log_fn=self.log_fn,
            pause_interrupt=self.pause_interrupt,
            pause_callback=self.pause_callback,
            stop_interrupt=self.stop_interrupt,
            stop_callback=self.stop_callback,
            stop_safely_interrupt=self.stop_safely_interrupt,
            stop_safely_callback=self.stop_safely_callback,
        )
        prio_bot.tree = self.tree
        prio_bot.select_priority_group_and_report()

    def scan_and_priority_report(self):
        self.scan_and_report()
