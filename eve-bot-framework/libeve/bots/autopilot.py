import time
from libeve.bots import Bot

class AutoPilotBot(Bot):
    def go(self):
        while True:
            route = self.find_route()
            if not route:
                break
            self.handle_undock()
            waypoint = self.get_first_waypoint(route)
            if not waypoint:
                time.sleep(0.1)
                continue
            if not self.jump_through_stargate(waypoint):
                if self.dock_at_station():
                    self.say("Стыковка успешна. Запускаю разгрузку.")
                    from libeve.bots.inventory_transfer import InventoryTransferBot
                    inv_bot = InventoryTransferBot(
                        log_fn=self.log_fn,
                        pause_interrupt=self.pause_interrupt,
                        pause_callback=self.pause_callback,
                        stop_interrupt=self.stop_interrupt,
                        stop_callback=self.stop_callback,
                        stop_safely_interrupt=self.stop_safely_interrupt,
                        stop_safely_callback=self.stop_safely_callback,
                    )
                    inv_bot.tree = self.tree
                    inv_bot.transfer()
            self.wait_until_ready_for_next_action()

    def wait_until_ready_for_next_action(self, timeout=60):
        t0 = time.time()
        while time.time() - t0 < timeout:
            self.tree.refresh()
            route = self.find_route()
            in_station = self.tree.find_node({"_name": "undockButton"}, type="UndockButton", do_refresh=False)
            if route or in_station:
                break
            time.sleep(0.3)

    def say(self, msg, **kwargs):
        if hasattr(self, 'log_fn') and self.log_fn:
            self.log_fn(msg)
        super().say(msg, **kwargs)

    def find_route(self):
        self.tree.refresh()
        route = self.wait_for({"_name": "markersParent"}, type="Container", until=5)
        if not route:
            self.say("Нет маршрута")
            return None
        return route

    def get_first_waypoint(self, route):
        if route and route.children:
            waypoint_id = route.children[0]
            waypoint = self.tree.nodes.get(waypoint_id)
            if not waypoint:
                return None
            return waypoint
        return None

    def jump_through_stargate(self, waypoint):
        self.tree.refresh()
        self.say("ПКМ по точке")
        self.click_node(waypoint, right_click=True)
        jump_btn = self.wait_for({"_setText": "Jump Through Stargate"}, until=0.3)
        if not jump_btn:
            self.say("Ищу Dock")
            jump_btn = self.wait_for({"_setText": "Jump Through"}, contains=True, until=0.3)
        if jump_btn:
            self.say("Прыжок")
            self.click_node(jump_btn)
            jumped = False
            if self.wait_for({"_setText": "Establishing Warp Vector"}, until=2):
                self.wait_until_warp_finished()
                jumped = True
            if self.wait_for({"_setText": "Jumping"}, until=4):
                self.wait_until_jump_finished()
                self.say("Прыжок завершён")
                jumped = True
            if jumped:
                return True
            else:
                self.say("Варп/прыжок не начат")
        return False

    def handle_undock(self):
        self.tree.refresh()
        undock_btn = self.tree.find_node({"_name": "undockButton"}, type="UndockButton", do_refresh=False)
        if undock_btn:
            self.say("Выход из дока")
            self.click_node(undock_btn)
            t0 = time.time()
            while time.time() - t0 < 20:
                self.tree.refresh()
                if not self.tree.find_node({"_name": "undockButton"}, type="UndockButton", do_refresh=False):
                    break
                time.sleep(0.5)
            return True
        return False

    def dock_at_station(self):
        self.tree.refresh()
        dock_btn = self.wait_for({"_setText": "Dock"}, until=1)
        if dock_btn:
            self.say("Стыковка")
            self.click_node(dock_btn)
            t0 = time.time()
            while time.time() - t0 < 40:
                self.tree.refresh()
                if self.tree.find_node({"_name": "undockButton"}, type="UndockButton", do_refresh=False):
                    break
                time.sleep(0.5)
            self.after_dock_handle_approach()
            return True
        else:
            self.say("Dock не найден")
        return False

    def after_dock_handle_approach(self):
        afterburner_activated = False
        while True:
            self.tree.refresh()
            approaching = None
            for node in self.tree.nodes.values():
                if node.type == "CaptionLabel" and "approaching" in node.attrs.get("_setText", "").lower():
                    approaching = node
                    break
            # if approaching and not afterburner_activated:
            #     self.say("Approaching! Afterburner")
            #     self._activate_afterburner()
            #     afterburner_activated = True
            in_station = self.tree.find_node({"_name": "undockButton"}, type="UndockButton", do_refresh=False)
            if in_station:
                self.say("В доке")
                break
            time.sleep(1)

    def _activate_afterburner(self):
        self.activate_module("AfterBurner")
