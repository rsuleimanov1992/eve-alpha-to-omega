import time
from libeve.bots import Bot
from libeve.bots.autopilot import AutoPilotBot
from libeve.utils import CustomLog


class SetLocationAndStartAutopilotBot(Bot):
    def in_space(self):
        return not self.tree.find_node({"_name": "undockButton"}, type="UndockButton")

    def open_locations(self):
        self.tree.refresh()
        loc_win = self.tree.find_node({"_name": "locations"}, type="LocationsWindow")
        if loc_win:
            return
        btn = self.tree.find_node({"_name": "locations"}, type="ButtonWindow")
        if not btn:
            self.say("Нет Locations")
            raise SystemExit("Нет кнопки Locations")
        self.click_node(btn)
        for _ in range(5):
            self.tree.refresh()
            loc_win = self.tree.find_node({"_name": "locations"}, type="LocationsWindow")
            if loc_win:
                break
        if not loc_win:
            self.say("Locations не открылось")
            raise SystemExit("Не открылось окно Locations")

    def find_placeentry_by_label(self, label_text):
        self.tree.refresh()
        for node in self.tree.nodes.values():
            if node.type == "PlaceEntry":
                for child_addr in getattr(node, "children", []):
                    child = self.tree.nodes.get(child_addr)
                    if (
                        child
                        and child.type == "EveLabelMedium"
                        and label_text.lower() in child.attrs.get("_setText", "").lower()
                    ):
                        return node
        return None

    def click_location_entry(self, label_text):
        entry_node = self.find_placeentry_by_label(label_text)
        if not entry_node:
            self.say(f"'{label_text}' не найден")
            raise SystemExit(f"PlaceEntry c подписью '{label_text}' не найден")
        self.click_node(entry_node, right_click=True)
        self.tree.refresh()
        set_dest = self.tree.find_node(
            {"_name": "context_menu_Set Destination"}, type="MenuEntryView"
        )
        return set_dest

    def undock(self):
        self.tree.refresh()
        undock_btn = self.tree.find_node(
            {"_name": "undockButton"}, type="UndockButton"
        )
        # if not undock_btn:
        #     self.say("Нет undockButton")
        #     raise SystemExit("Нет undockButton")
        self.say("Выхожу из дока")
        CustomLog.set_start()
        self.click_node(undock_btn)
        for _ in range(30):
            self.tree.refresh()
            if not self.tree.find_node({"_name": "undockButton"}, type="UndockButton"):
                break
            time.sleep(1)
        if not self.tree.find_node({"_name": "undockButton"}, type="UndockButton"):
            time.sleep(1)
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
        else:
            self.say("Не удалось покинуть станцию")

    def go(self):
        try:
            from libeve.bots.mining_drones import MiningDronesBot
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

        self.open_locations()
        time.sleep(0.3)
        label_text = "homestation" if self.in_space() else "mining"
        set_dest = self.click_location_entry(label_text)
        if set_dest:
            self.click_node(set_dest)
            autopilot = AutoPilotBot(
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
        else:
            self.undock()
