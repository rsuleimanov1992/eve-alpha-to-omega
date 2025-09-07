import time
from datetime import datetime, timezone, timedelta
from libeve.bots import Bot
from libeve.utils import CustomLog



class InventoryTransferBot(Bot):
    def __init__(
        self,
        log_fn=print,
        *args, **kwargs
    ):
        super().__init__(log_fn=log_fn, *args, **kwargs)


    def check_server_restart_time(self):
        """Проверка времени до рестарта сервера EVE (14:00 МСК)"""
        # Московское время
        msk_tz = timezone(timedelta(hours=3))
        now_msk = datetime.now(msk_tz)
        
        # Проверяем если сейчас 13:50-14:00 МСК
        if now_msk.hour == 13 and now_msk.minute >= 50:
            return True
        return False


    def log(self, msg):
        if self.log_fn:
            self.log_fn(msg)
        else:
            print(msg)
        self.say(msg)


    def at_station(self):
        undock_btn = self.tree.find_node({"_name": "undockButton"})
        return undock_btn is not None


    def in_space(self):
        return not self.tree.find_node({"_name": "undockButton"})


    def inventory_open(self):
        self.tree.refresh()
        time.sleep(0.5)  # увеличенная задержка после refresh
        inventory_station = self.tree.find_node({"_name": "InventoryStation"}, type="InventoryPrimary")
        inventory_label = self.tree.find_node({"_setText": "Inventory"}, type="Label")
        if inventory_station and inventory_label:
            self.log("Инвентарь найден (стандартный тип)")
            return True
        elif inventory_label:
            self.log("Инвентарь найден (альтернативный тип)")
            return True
        else:
            self.log("Инвентарь не найден")
            return False


    def open_inventory(self):
        btn = self.tree.find_node({"_name": "inventory"}, type="ButtonInventory")
        if not btn:
            self.log("Нет кнопки инвентаря")
            return False
        self.log("Открываю инвентарь")
        self.click_node(btn)
        time.sleep(0.6)  # увеличенная задержка после клика
        self.tree.refresh()
        time.sleep(0.5)  # увеличенная задержка после refresh
        return self.inventory_open()


    def select_mining_hold(self):
        # Ждём появления Mining Hold до 5 секунд
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
                self.log("Нет Mining Hold")
                return False


        self.log("Выбираю Mining Hold")
        self.click_node(hold)
        time.sleep(0.5)  # увеличенная задержка после клика


        # Ждём появления содержимого после клика (до 3 сек)
        t1 = time.time()
        while time.time() - t1 < 3:
            self.tree.refresh()
            time.sleep(0.3)
            ores = self.ore_in_hold()
            if ores:
                return True
        return True  # Даже если пусто, но hold выбран — это не ошибка


    def ore_in_hold(self):
        return [
            n for n in self.tree.find_node({}, type="Label", select_many=True) or []
            if n.attrs.get("_name") == "itemNameLabel"
        ]


    def item_hangar(self):
        return self.tree.find_node({"_name": "ItemHangar"}, type="TreeViewEntryWithTag")


    def transfer_ore(self):
        hangar = self.item_hangar()
        if not hangar:
            self.log("Нет ItemHangar")
            return False
        ores = self.ore_in_hold()
        if not ores:
            self.log("Нет руды в Hold")
            return True
        for o in ores:
            name = o.attrs.get("_setText", "").replace("<center>", "").strip()
            # self.log(f"Переношу {name}")
            self.drag_node_to_node(o, hangar)
            time.sleep(0.5)  # увеличенная задержка после каждого drag
        self.tree.refresh()
        time.sleep(0.6)  # увеличенная задержка после refresh
        if not self.ore_in_hold():
            self.log("Руда перенесена")
            return True
        self.log("Руда осталась в Hold!")
        return False


    # def check_time_should_exit(self):
    #     now = datetime.now()
    #     if (now.hour == 13 and now.minute >= 30) or (now.hour == 14 and now.minute <= 10):
    #         self.say("Время завершить работу. Останавливаю бота!")
    #         exit(0)


    def launch_autopilot(self):
        from libeve.bots.set_location_and_autopilot import SetLocationAndStartAutopilotBot
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


    def transfer(self):
        # Проверка времени рестарта сервера
        if self.check_server_restart_time():
            self.log("Близится рестарт сервера EVE (14:00 МСК). Переходим в режим ожидания.")
            while True:
                time.sleep(60)  # Вечный сон по минуте
        
        # self.check_time_should_exit()
        if not self.at_station() or self.in_space():
            self.log("Перенос невозможен")
            # self.check_time_should_exit()
            return


        if not self.inventory_open():
            if not self.open_inventory():
                self.log("Не открыть инвентарь")
                # self.check_time_should_exit()
                return
            if not self.inventory_open():
                self.log("Не открыть инвентарь")
                # self.check_time_should_exit()
                return


        if not self.select_mining_hold():
            self.log("Не выбрать Mining Hold")
            # self.check_time_should_exit()
            return


        ores = self.ore_in_hold()
        if not ores:
            self.log("Руды нет")
            self.launch_autopilot()
            # self.check_time_should_exit()
            return


        if not self.transfer_ore():
            self.log("Ошибка переноса руды")
            # self.check_time_should_exit()
            return


        self.log("Груз перенесён")
        CustomLog.create_sla_log()
        # self.check_time_should_exit()
        self.launch_autopilot()
