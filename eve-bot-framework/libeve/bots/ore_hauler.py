import time
from libeve.bots import Bot

# ------ ORE AUTOPILOT ------

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

# ------ ORE HAULER ------

class OreHaulerBot(Bot):
    def go(self):
        """
        Главный метод — точка входа для логики доставки руды.
        Определяет, находится ли бот на станции или в космосе,
        и запускает соответствующий сценарий.
        """
        if self.tree.find_node({"_name": "undockButton"}):
            self.say("Я в ангаре.")
            self.tree.refresh()

            # Открываем меню локаций
            btn = self.tree.find_node({"_name": "locations"})
            if not btn:
                self.say("Кнопка locations не найдена.")
                return

            self.click_node(btn)
            time.sleep(0.2)
            self.tree.refresh()
            time.sleep(0.2)

            # --- ОПРЕДЕЛЕНИЕ SOURCE (станции погрузки) ---
            source = self._find_place_node("source")
            if source:
                if self._set_route_node(source):
                    # Если нет markersParent — мы на нужной станции
                    if not self.tree.find_node({"_name": "markersParent"}):
                        self.say("Я на станции погрузки.")
                        self.handle_station_cargo("load")
                        return

            # --- ОПРЕДЕЛЕНИЕ DESTINATION (станции разгрузки) ---
            destination = self._find_place_node("destination")
            if destination:
                if self._set_route_node(destination):
                    if not self.tree.find_node({"_name": "markersParent"}):
                        self.say("Я на станции разгрузки.")
                        self.handle_station_cargo("unload")
                        return
                    else:
                        self.say("Я на промежуточной станции. Запускаю автопилот.")
                        self._run_autopilot()
                        return

        else:
            self.say("Я в космосе.")
            from libeve.bots.hold_status import HoldStatusBot
            status_bot = HoldStatusBot(hold_full_percent=95, log_fn=self.say)
            status_bot.tree = self.tree
            try:
                status_bot.select_mining_hold()
                cur, max_, percent = status_bot.get_capacity()
            except Exception as e:
                self.say(f"Ошибка трюма: {e}")
                return

            if percent < 5:
                self.say("Трюм пуст. Ставлю маршрут на станцию погрузки.")
                source = self._find_place_node("source")
                if source:
                    if self._set_route_node(source, say=True):
                        self._run_autopilot()
                else:
                    self.say("Станция погрузки не найдена.")
            else:
                self.say("Трюм не пуст. Ставлю маршрут на станцию разгрузки.")
                destination = self._find_place_node("destination")
                if destination:
                    if self._set_route_node(destination, say=True):
                        self._run_autopilot()
                else:
                    self.say("Станция разгрузки не найдена.")

    # ------------------------
    # ВСПОМОГАТЕЛЬНЫЕ МЕТОДЫ
    # ------------------------

    def _find_place_node(self, marker: str):
        """
        Поиск PlaceEntry по ключевому маркеру (source или destination).
        Возвращает подходящий node или None.
        """
        for node in self.tree.nodes.values():
            if node.type == "PlaceEntry":
                for ch in getattr(node, "children", []):
                    child = self.tree.nodes.get(ch)
                    if child and marker in child.attrs.get("_setText", "").lower():
                        return node
        return None

    def _set_route_node(self, node, say=False):
        """
        Кликает по PlaceEntry правой кнопкой и выбирает 'Set Destination'.
        Если меню 'Set Destination' не найдено, значит маршрут уже установлен —
        это не ошибка.
        """
        self.click_node(node, right_click=True)
        time.sleep(0.2)
        menu = self.tree.find_node({"_name": "context_menu_Set Destination"})
        if menu:
            self.click_node(menu)
            time.sleep(0.2)
            self.tree.refresh()
            time.sleep(0.2)
            return True
        else:
            if say:
                self.say("Маршрут уже установлен.")
            return True  # Нет меню — это не ошибка, маршрут уже стоит

    def _run_autopilot(self):
        """
        Запуск автопилота на текущем дереве интерфейса.
        """
        # Чтобы избежать рекурсии: используем класс, определённый выше!
        bot = OreAutoPilotBot()
        bot.tree = self.tree
        bot.go()

    # ------------------------
    # ОСТАЛЬНЫЕ МЕТОДЫ
    # ------------------------

    def inventory_open(self):
        """
        Проверяет открыт ли инвентарь.
        """
        self.tree.refresh()
        time.sleep(0.5)
        inventory_station = self.tree.find_node({"_name": "InventoryStation"}, type="InventoryPrimary")
        inventory_label = self.tree.find_node({"_setText": "Inventory"}, type="Label")
        if inventory_station and inventory_label:
            self.say("Инвентарь найден (стандартный тип)")
            return True
        elif inventory_label:
            self.say("Инвентарь найден (альтернативный тип)")
            return True
        else:
            self.say("Инвентарь не найден")
            return False

    def open_inventory(self):
        """
        Открывает окно инвентаря.
        """
        btn = self.tree.find_node({"_name": "inventory"}, type="ButtonInventory")
        if not btn:
            self.say("Нет кнопки инвентаря")
            return False
        self.say("Открываю инвентарь")
        self.click_node(btn)
        time.sleep(0.6)
        self.tree.refresh()
        time.sleep(0.5)
        return self.inventory_open()

    def select_mining_hold(self):
        """
        Выделение Mining Hold.
        """
        hold = self.tree.find_node({"_name": "ShipGeneralMiningHold"}, type="TreeViewEntryInventory")
        if not hold:
            self.open_inventory()
            t0 = time.time()
            while time.time() - t0 < 5:
                hold = self.tree.find_node({"_name": "ShipGeneralMiningHold"}, type="TreeViewEntryInventory")
                if hold:
                    break
                time.sleep(0.5)
            if not hold:
                self.say("Нет Mining Hold")
                return False
        self.say("Выбираю Mining Hold")
        self.click_node(hold)
        time.sleep(0.5)
        t1 = time.time()
        while time.time() - t1 < 3:
            self.tree.refresh()
            time.sleep(0.3)
            ores = self.ore_in_hold()
            if ores:
                return True
        return True  # Даже если пусто, но hold выбран — это не ошибка

    def ore_in_hold(self):
        """
        Возвращает список руды в трюме.
        """
        return [
            n for n in self.tree.find_node({}, type="Label", select_many=True) or []
            if n.attrs.get("_name") == "itemNameLabel"
        ]

    def select_item_hangar(self):
        """
        Открытие Item Hangar.
        """
        hangar = self.item_hangar()
        if not hangar:
            self.open_inventory()
            t0 = time.time()
            while time.time() - t0 < 5:
                hangar = self.item_hangar()
                if hangar:
                    break
                time.sleep(0.5)
            if not hangar:
                self.say("Нет Item Hangar!")
                return False
        self.say("Выбираю Item Hangar")
        self.click_node(hangar)
        self.tree.refresh()
        time.sleep(0.5)
        return True

    def ore_in_hangar(self):
        """
        Возвращает список руды в ангаре.
        """
        self.tree.refresh()
        labels = self.tree.find_node({}, type="Label", select_many=True) or []
        return [
            n for n in labels if n.attrs.get("_name") == "itemNameLabel"
        ]

    def item_hangar(self):
        """
        Возвращает узел ItemHangar.
        """
        return self.tree.find_node({"_name": "ItemHangar"}, type="TreeViewEntryWithTag")

    def close_interfering_windows(self, max_attempts=3, delay=1.2):
        """
        Закрывает мешающие диалоговые окна («ok_dialog_button»).
        Делаем несколько попыток, увеличенная задержка после закрытия.
        Возвращает True, если получилось закрыть; False иначе.
        """
        for attempt in range(max_attempts):
            self.tree.refresh()
            dialog_window = self.tree.find_node({"_name": "ok_dialog_button"}, type="Button")
            if dialog_window:
                self.say(f"Закрываю диалог (попытка {attempt + 1})")
                self.click_node(dialog_window)
                time.sleep(delay)
                self.tree.refresh()
            else:
                # окно закрыто
                return True
        self.say("Не удалось закрыть диалоговое окно за несколько попыток!")
        return False

    def transfer_ore(self):
        """
        Перемещает всё из Mining Hold в Item Hangar.
        """
        hangar = self.item_hangar()
        if not hangar:
            self.say("Нет ItemHangar")
            return False
        ores = self.ore_in_hold()
        if not ores:
            self.say("Нет руды в Hold")
            return True
        for o in ores:
            name = o.attrs.get("_setText", "").replace("<center>", "").strip()
            self.say(f"Переношу {name}")
            self.drag_node_to_node(o, hangar)
            time.sleep(0.5)
        self.tree.refresh()
        time.sleep(0.6)
        if not self.ore_in_hold():
            self.say("Руда перенесена")
            return True
        self.say("Руда осталась в Hold!")
        return False

    def load_ore_to_hold(self):
        """
        Загружает руду из Item Hangar в Mining Hold до полного заполнения или пока руда не закончится в ангаре.
        """
        if not self.select_item_hangar():
            return False
        hold = self.tree.find_node({"_name": "ShipGeneralMiningHold"}, type="TreeViewEntryInventory")
        if not hold:
            self.say("Нет Mining Hold для загрузки")
            return False
        while True:
            ores = self.ore_in_hangar()
            if not ores:
                self.say("В ангаре нет руды для загрузки")
                break
            for o in ores:
                name = o.attrs.get("_setText", "").replace("<center>", "").strip()
                self.say(f"Загружаю {name} в Mining Hold")
                self.drag_node_to_node(o, hold)
                time.sleep(0.5)
                self.tree.refresh()
                time.sleep(0.2)
                # Проверяем, появилось ли окно диалога после попытки загрузки!
                dialog_window = self.tree.find_node({"_name": "ok_dialog_button"}, type="Button")
                if dialog_window:
                    self.say("Операция загрузки прервана — появилось диалоговое окно (вероятно, трюм заполнен)")
                    self.click_node(dialog_window)
                    time.sleep(0.5)
                    self.tree.refresh()
                    break  # Выходим из FOR -- трюм полон
            else:
                # Если не было break, продолжаем следующий while (проверка следующей порции руды)
                continue
            # Если break изнутри for (hold заполнен или ошибка) -- выходим из while.
            break

        if self.ore_in_hold():
            self.say("Руда загружена в трюм")
            return True
        else:
            self.say("Не удалось загрузить руду в трюм или Mining Hold пуст!")
            return False

    def handle_station_cargo(self, operation: str):
        """
        Операция с грузом — загрузка или выгрузка на станции.
        После завершения ставит новый маршрут (source или destination)
        и запускает автопилот.
        """
        self.say(f"Операция на станции: {operation}")
        self.tree.refresh()
        time.sleep(0.5)

        # Открываем инвентарь, если не открыт
        if not self.inventory_open():
            if not self.open_inventory():
                self.say("Не удалось открыть инвентарь")
                return False

        if operation == "unload":
            if not self.select_mining_hold():
                self.say("Не удалось выбрать Mining Hold")
                return False
            ores = self.ore_in_hold()
            if not ores:
                self.say("Руды нет для выгрузки.")
            else:
                res = self.transfer_ore()
                if not res:
                    self.say("Ошибка при попытке выгрузить руду.")
                else:
                    self.say("Руда выгружена в Item Hangar.")
            self._set_route_and_autopilot('source')
            return True

        elif operation == "load":
            res = self.load_ore_to_hold()
            # Прерывание (interrupted=True) теперь считается обычным успешным выходом!
            if res:
                self.say("Загрузка руды завершена.")
            else:
                self.say("Ошибка при попытке загрузить руду в трюм.")
            self._set_route_and_autopilot('destination')
            return True
        else:
            self.say(f"Неизвестная операция handle_station_cargo: {operation}")
            return False

    def _set_route_and_autopilot(self, where: str):
        """
        Вызывает поиск точки назначения (source/destination),
        устанавливает маршрут и запускает автопилот.
        Использует ранее выделенные _find_place_node и _set_route_node.
        """
        node = self._find_place_node(where)
        if node:
            if self._set_route_node(node, say=True):
                self._run_autopilot()
        else:
            self.say(f"Станция {where} не найдена.")
