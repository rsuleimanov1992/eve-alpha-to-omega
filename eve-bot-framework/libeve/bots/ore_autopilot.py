import time
from libeve.bots import Bot

class OreAutoPilotBot(Bot):
    def __init__(self, target_location=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.target_location = target_location

    def say(self, msg, narrate=True):
        if self.log_fn:
            self.log_fn(msg)
        super().say(msg, narrate=narrate)

    def go(self):
        while True:
            route = self.find_route()
            if not route:
                break
            self.handle_undock()
            waypoint = self.get_first_waypoint(route)
            if not waypoint:
                continue
            if not self.jump_through_stargate(waypoint):
                self.dock_at_station()
        self.on_arrive_station()

    def on_arrive_station(self):
        self.say("Прибыл на станцию, вызываю погрузку/выгрузку!")
        self.say("Ожидаю загрузки интерфейса станции...")
        self.tree.refresh()
        from libeve.bots.ore_hauler import OreHaulerBot
        hauler = OreHaulerBot(
            log_fn=self.log_fn,
            pause_interrupt=self.pause_interrupt,
            pause_callback=self.pause_callback,
            stop_interrupt=self.stop_interrupt,
            stop_callback=self.stop_callback,
            stop_safely_interrupt=self.stop_safely_interrupt,
            stop_safely_callback=self.stop_safely_callback,
        )
        hauler.tree = self.tree
        hauler.go()

    def find_route(self):
        self.tree.refresh()
        route = self.wait_for({"_name": "markersParent"}, type="Container", until=5)
        if not route:
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
        self.say("ПКМ по точке маршрута")
        self.click_node(waypoint, right_click=True)
        jump_btn = self.wait_for({"_setText": "Jump Through Stargate"}, until=1.0)
        if not jump_btn:
            self.say("Не найдена кнопка 'Jump Through Stargate', ищу 'Jump Through'")
            jump_btn = self.wait_for({"_setText": "Jump Through"}, contains=True, until=1.0)
        if not jump_btn:
            self.say("Не найдена кнопка прыжка, возможно, это конечная точка")
            return False
        if jump_btn:
            self.say("Нажимаю на прыжок")
            self.click_node(jump_btn)
            jumped = False
            if self.wait_for({"_setText": "Establishing Warp Vector"}, until=3):
                self.say("Варп начат")
                self.wait_until_warp_finished()
                jumped = True
            if self.wait_for({"_setText": "Jumping"}, until=5):
                self.say("Прыжок начат")
                self.wait_until_jump_finished()
                self.say("Прыжок завершён")
                jumped = True
            if jumped:
                return True
            else:
                self.say("Варп или прыжок не начат, повторяю попытку")
                return False
        return False

    def handle_undock(self):
        self.tree.refresh()
        undock_btn = self.tree.find_node({"_name": "undockButton"}, type="UndockButton")
        if undock_btn:
            self.say("Выход из дока")
            self.click_node(undock_btn)
            time.sleep(7)
            for _ in range(10):
                self.tree.refresh()
                if not self.tree.find_node({"_name": "undockButton"}, type="UndockButton"):
                    break
            return True
        return False

    def dock_at_station(self):
        self.tree.refresh()
        dock_btn = self.wait_for({"_setText": "Dock"}, until=2)
        if dock_btn:
            self.say("Стыковка")
            self.click_node(dock_btn)
            self.after_dock_handle_approach()
            return True
        else:
            self.say("Кнопка 'Dock' не найдена")
        return False

    def after_dock_handle_approach(self):
        afterburner_activated = False
        max_wait_time = 60
        start_time = time.time()
        while True:
            if time.time() - start_time > max_wait_time:
                self.say("Слишком долгое ожидание стыковки, прерываю")
                break
            self.tree.refresh()
            approaching = None
            for node in self.tree.nodes.values():
                if node.type == "CaptionLabel" and "approaching" in node.attrs.get("_setText", "").lower():
                    approaching = node
                    break
            if approaching and not afterburner_activated:
                self.say("Приближаюсь к станции! Включаю Afterburner")
                self._activate_afterburner()
                afterburner_activated = True
            in_station = self.tree.find_node({"_name": "undockButton"}, type="UndockButton")
            if in_station:
                self.say("Успешно в доке")
                break

    def _activate_afterburner(self):
        self.activate_module("AfterBurner")
