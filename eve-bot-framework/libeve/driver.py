import json
import os
import time
import threading
import traceback
from .bots.autopilot import AutoPilotBot
from .bots.inventory_transfer import InventoryTransferBot
from .bots.hold_status import HoldStatusBot
from .bots.set_location_and_autopilot import SetLocationAndStartAutopilotBot
from .bots.asteroid_belt_scanner import AsteroidBeltScannerBot
from .bots.autopilot_simple import AutoPilotSimpleBot
from .bots.ore_survey_scanner import OreSurveyScannerBot
from .bots.ore_survey_priority_selector import OreSurveyPrioritySelectorBot
from .bots.mining import MiningBot
from .bots.mining_drones import MiningDronesBot
from .bots.ore_hauler import OreHaulerBot
from .bots.ore_autopilot import OreAutoPilotBot

class BotDriver(object):

    registered_bots = {
                        "AutoPilotBot": AutoPilotBot,
                        "InventoryTransferBot": InventoryTransferBot,
                        "HoldStatusBot": HoldStatusBot,
                        "SetLocationAndStartAutopilotBot": SetLocationAndStartAutopilotBot,
                        "AsteroidBeltScannerBot": AsteroidBeltScannerBot,
                        "AutoPilotSimpleBot": AutoPilotSimpleBot,
                        "OreSurveyScannerBot": OreSurveyScannerBot,
                        "OreSurveyPrioritySelectorBot": OreSurveyPrioritySelectorBot,
                        "MiningBot": MiningBot,
                        "MiningDronesBot": MiningDronesBot,
                        "OreHaulerBot": OreHaulerBot,
                        "OreAutoPilotBot": OreAutoPilotBot,
                      }

    def __init__(
        self,
        driver_filename,
        log_fn=print,
        pause_interrupt: threading.Event = None,
        pause_callback=None,
        stop_interrupt: threading.Event = None,
        stop_callback=None,
        stop_safely_interrupt: threading.Event = None,
        stop_safely_callback=None,
    ):
        self.driver_filename = driver_filename
        with open(self.driver_filename) as driver_file:
            self.driver = json.load(driver_file)
        self.muted = not self.driver.get("with_narration", False)
        self.bot_name = self.driver.get("uses")
        self.start_from = self.driver.get("start_from")
        self.focus_enabled = self.driver.get("focus", False)
        self.loop = self.driver.get("loop", False)
        self.args = self.driver.get("args", {})
        self.started = False
        self.log_fn = log_fn
        self.pause_interrupt = pause_interrupt
        self.pause_callback = pause_callback
        self.stop_interrupt = stop_interrupt
        self.stop_callback = stop_callback
        self.stop_safely_interrupt = stop_safely_interrupt
        self.stop_safely_callback = stop_safely_callback
        if not self.bot_name:
            raise Exception(f"`uses` key must be present in {self.driver_filename}")
        if self.bot_name not in BotDriver.registered_bots:
            raise Exception(f"`{self.bot_name}` is not a registered bot")
        self.bot = BotDriver.registered_bots[self.bot_name](
            log_fn=self.log_fn,
            pause_interrupt=self.pause_interrupt,
            pause_callback=self.pause_callback,
            stop_interrupt=self.stop_interrupt,
            stop_callback=self.stop_callback,
            stop_safely_interrupt=self.stop_safely_interrupt,
            stop_safely_callback=self.stop_safely_callback,
            **self.args,
        )

    def start(self):
        if not self.bot.tree:
            self.log_fn("bot is not initialized!")
            return
        try:
            while True:
                for step in self.driver.get("steps", list()):
                    if not self.started and self.start_from and self.start_from != step:
                        continue
                    if self.focus_enabled:
                        self.bot.focus()
                    self.started = True
                    fn = getattr(self.bot, step)
                    if not (fn and callable(fn)):
                        raise Exception(
                            f"`{step}` is not a registered action in bot `{self.bot_name}`"
                        )
                    self.log_fn(f"== running step: {step}")
                    fn()
                if not self.loop:
                    break
        except Exception as e:
            traceback.print_exc()
            self.log_fn("ERROR: Bot failed with an exception")
            self.bot.say("Error, attention needed")
        finally:
            self.bot.tree.cleanup()
