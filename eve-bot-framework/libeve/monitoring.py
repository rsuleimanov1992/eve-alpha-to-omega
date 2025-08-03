class ShipHealthMonitor:
    def __init__(self, tree, notify_fn):
        self.tree = tree
        self.notify_fn = notify_fn
        self.prev = {"shield": None, "armor": None, "structure": None, "capacitor": None}

    def in_space(self):
        # Если нет кнопки undock, то мы в космосе
        return not self.tree.find_node({"_name": "undockButton"}, type="UndockButton")

    def check(self):
        if not self.in_space():
            # Не в космосе — не мониторим и сбрасываем запомненные значения
            for k in self.prev:
                self.prev[k] = None
            return
        for k in ("shield", "armor", "structure"):
            v = self._get_gauge_value(f"{k}Gauge")
            if v is not None and v != self.prev[k]:
                self.notify_fn(f"{k.capitalize()}: {v}%")
                self.prev[k] = v

        # Мониторинг капаситора
        cap = self._get_capacitor_percent()
        if cap is not None and cap != self.prev["capacitor"]:
            self.notify_fn(f"Capacitor: {cap}%")
            self.prev["capacitor"] = cap

    def _get_gauge_value(self, name):
        node = self.tree.find_node({"_name": name}, type="ShipHudSpriteGauge")
        if node:
            val = node.attrs.get("_lastValue")
            if val is not None:
                return round(float(val) * 100)
        return None

    def _get_capacitor_percent(self):
        # Ищем контейнер капаситора
        cap_container = self.tree.find_node({}, type="CapacitorContainer")
        if not cap_container:
            return None
        total_marks = 0
        active_marks = 0
        for child in getattr(cap_container, "children", []):
            node = self.tree.nodes.get(child)
            if node and node.type == "Transform" and node.attrs.get("_name") == "powerColumn":
                for pmark_addr in getattr(node, "children", []):
                    pmark = self.tree.nodes.get(pmark_addr)
                    if pmark and pmark.type == "Sprite" and pmark.attrs.get("_name") == "pmark":
                        total_marks += 1
                        color = pmark.attrs.get("_color", {})
                        # Обычно aPercent > 10 — деление считается "заряжённым"
                        if color.get("aPercent", 0) > 10:
                            active_marks += 1
        if total_marks == 0:
            return None
        return int(active_marks * 100 / total_marks)
