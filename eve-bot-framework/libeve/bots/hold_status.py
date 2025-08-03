import time
from libeve.bots import Bot

class HoldStatusBot(Bot):
    def __init__(
        self,
        check_interval=30,
        hold_full_percent=95,
        log_fn=print,
        *args, **kwargs
    ):
        super().__init__(log_fn=log_fn, *args, **kwargs)
        self.check_interval = check_interval
        self.hold_full_percent = hold_full_percent

    def log(self, msg, narrate=False):
        if self.log_fn:
            self.log_fn(msg)
        else:
            print(msg)
        if narrate:
            self.say(msg)

    def in_space(self):
        # Проверка: обновление не нужно, кнопка "undock" может быть только на станции
        return not self.tree.find_node({"_name": "undockButton"}, do_refresh=False)

    def inventory_open(self):
        self.tree.refresh()
        return self.tree.find_node({"_name": "ShipGeneralMiningHold"}, type="TreeViewEntryInventory", do_refresh=False) is not None

    def wait_for(self, predicate, timeout=5.0, poll=0.2):
        t0 = time.time()
        while time.time() - t0 < timeout:
            self.tree.refresh()
            if predicate():
                return True
            time.sleep(poll)
        return False

    def open_inventory(self):
        btn = self.tree.find_node({"_name": "inventory"}, type="ButtonInventory")
        if not btn:
            self.log("Нет кнопки инвентаря")
            raise SystemExit("Нет кнопки инвентаря")
        self.click_node(btn)
        ok = self.wait_for(
            lambda: self.tree.find_node({"_name": "ShipGeneralMiningHold"}, type="TreeViewEntryInventory", do_refresh=False)
        )
        if not ok:
            self.log("Mining Hold не найден после открытия инвентаря")
            raise SystemExit("Нет Mining Hold")

    def select_mining_hold(self):
        hold = self.tree.find_node({"_name": "ShipGeneralMiningHold"}, type="TreeViewEntryInventory", do_refresh=False)
        if not hold:
            self.open_inventory()
            hold = self.tree.find_node({"_name": "ShipGeneralMiningHold"}, type="TreeViewEntryInventory")
            if not hold:
                raise SystemExit("Нет Mining Hold")
        self.click_node(hold)
        ok = self.wait_for(
            lambda: self.tree.find_node(type="InvContCapacityGauge", do_refresh=False)
        )
        if not ok:
            self.log("Индикатор вместимости не найден после выбора Mining Hold")
            raise SystemExit("Нет индикатора трюма")

    def get_capacity(self):
        gauge = self.tree.find_node(type="InvContCapacityGauge", do_refresh=False)
        if not gauge:
            raise SystemExit("Нет индикатора трюма")
        for ch in getattr(gauge, "children", []):
            node = self.tree.nodes.get(ch)
            if node and node.attrs.get("_name") == "capacityText":
                cap_str = node.attrs.get("_setText", "0/0 m").strip()
                try:
                    ratio = cap_str.split("m")[0].strip()
                    cur, max_ = ratio.split("/")
                    cur = float(cur.replace(" ", "").replace(",", "."))
                    max_ = float(max_.replace(" ", "").replace(",", "."))
                    percent = (cur / max_ * 100) if max_ else 0
                    return cur, max_, percent
                except Exception:
                    break
        raise SystemExit("Ошибка вместимости")

    def is_hold_full(self):
        if not self.in_space():
            raise SystemExit("Не в космосе")
        self.select_mining_hold()
        cur, max_, percent = self.get_capacity()
        msg = f"Трюм {percent:.0f}%"
        self.log(f"{cur:.1f}/{max_:.1f} м³ ({percent:.1f}%)")
        self.say(msg)
        return percent >= self.hold_full_percent

    def check_hold(self):
        try:
            if not self.in_space():
                raise SystemExit("Не в космосе")
            is_full = self.is_hold_full()
        except SystemExit as e:
            self.log(f"Стоп: {e}")
            raise
        except Exception as ex:
            self.log(f"Ошибка: {ex}")
        time.sleep(self.check_interval)
