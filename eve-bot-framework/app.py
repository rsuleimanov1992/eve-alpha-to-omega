import sys
import tkinter as tk
from tkinter import ttk, filedialog
import json
import os.path
import threading
import time
from time import sleep

import libeve.driver
from api import api, BotView
from libeve.utils import CustomLog


class Application(object):
    def __init__(self, run_number: int):
        BotView.app = self
        self.root = tk.Tk()
        self.root.title("EVE Online - Bot Application")
        self.root.geometry("1024x768")
        self.bot_loaded = False
        self.bot_config_file = None
        self.bot_config = dict()
        self.bot_log = []
        self.driver = None
        self.run_thread = None
        self.api_thread = threading.Thread(
            target=api.run, kwargs=dict(host="0.0.0.0", debug=False, use_reloader=False)
        )
        self.api_thread.daemon = True
        self.api_thread.start()
        self.pause_interrupt = threading.Event()
        self.stop_interrupt = threading.Event()
        self.stop_safely_interrupt = threading.Event()
        self.run_number = run_number
        self.reset_run_thread()

        self.setup_ui()
        self._browse_file()

        if self.bot_loaded:
            self.initiate_driver()

        self.show()

    def setup_ui(self):
        # Основной фрейм
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Метка для текущего выбранного бота
        bot_label_frame = ttk.Frame(main_frame)
        bot_label_frame.grid(row=0, column=0, sticky=tk.W, pady=2)
        ttk.Label(bot_label_frame, text="Bot: ").pack(side=tk.LEFT)
        self.currently_selected_bot = ttk.Label(bot_label_frame, text="<No Bot Selected>")
        self.currently_selected_bot.pack(side=tk.LEFT)

        # Кнопки управления
        button_frame = ttk.Frame(main_frame)
        button_frame.grid(row=1, column=0, sticky=tk.W, pady=2)
        self.run_button = ttk.Button(button_frame, text="Run", command=self.run, state='disabled')
        self.run_button.pack(side=tk.LEFT, padx=2)
        self.pause_button = ttk.Button(button_frame, text="Pause", command=self.pause, state='disabled')
        self.pause_button.pack(side=tk.LEFT, padx=2)
        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop, state='disabled')
        self.stop_button.pack(side=tk.LEFT, padx=2)
        self.stop_safely_button = ttk.Button(button_frame, text="Stop Safely", command=self.stop_safely, state='disabled')
        self.stop_safely_button.pack(side=tk.LEFT, padx=2)

        # Лог
        self.bot_log_text = tk.Text(main_frame, height=38, width=100, state='disabled')
        self.bot_log_text.grid(row=2, column=0, pady=2)

        # Выбор файла конфигурации
        file_frame = ttk.Frame(main_frame)
        file_frame.grid(row=3, column=0, sticky=tk.W, pady=2)
        self.bot_config_entry = ttk.Entry(file_frame, width=25, state='readonly')
        self.bot_config_entry.pack(side=tk.LEFT, padx=2)
        ttk.Button(file_frame, text="Browse", command=self.browse_file).pack(side=tk.LEFT, padx=2)

        # Сохранение лога
        ttk.Button(main_frame, text="Сохранить лог", command=self.save_log).grid(row=4, column=0, sticky=tk.W, pady=2)

    def browse_file(self):
        file_path = filedialog.askopenfilename()
        if file_path:
            self.bot_config_entry.config(state='normal')
            self.bot_config_entry.delete(0, tk.END)
            self.bot_config_entry.insert(0, file_path)
            self.bot_config_entry.config(state='readonly')
            self.load({"bot_config_file": file_path})

    def _browse_file(self):
        file_path_map = {
            'set_location_and_autopilot': r'eve-bot-framework\examples\set_location_and_autopilot.json',
            'asteroid_belt_scanner': r'eve-bot-framework\examples\asteroid_belt_scanner.json',
            'autopilot_simple': r'eve-bot-framework\examples\autopilot_simple.json',
        }

        if self.run_number > 1:
            file_path = file_path_map['set_location_and_autopilot']
        else:
            file_path = None
            if len(sys.argv) > 1:
                for key in file_path_map.keys():
                    command = sys.argv[1]
                    if command in key:
                        file_path = file_path_map[key]
                        break

        if file_path:
            self.load({"bot_config_file": file_path})

    def reset_run_thread(self):
        if self.run_thread is not None:
            del self.run_thread
        self.run_thread = threading.Thread(target=self.initiate_driver)
        self.run_thread.daemon = True

    def log(self, message):
        self.bot_log.append(message)
        self.bot_log_text.config(state='normal')
        self.bot_log_text.delete(1.0, tk.END)
        self.bot_log_text.insert(tk.END, "\n".join(self.bot_log))
        self.bot_log_text.config(state='disabled')
        self.bot_log_text.see(tk.END)

    def initiate_driver(self):
        try:
            self.log("starting bot...")
            self.driver = libeve.driver.BotDriver(
                self.bot_config_file,
                log_fn=self.log,
                pause_interrupt=self.pause_interrupt,
                pause_callback=self.pause_callback,
                stop_interrupt=self.stop_interrupt,
                stop_callback=self.stop_callback,
                stop_safely_interrupt=self.stop_safely_interrupt,
                stop_safely_callback=self.stop_safely_callback,
            )
            self.driver.bot.initialize()
            self.driver.start()
        except Exception as e:
            self.log(f"error: {e}")
        finally:
            self.run_button.config(state='normal')
            self.pause_button.config(state='disabled')
            self.stop_button.config(state='disabled')
            self.stop_safely_button.config(state='disabled')
            self.reset_run_thread()
            self.log("bot finished...")

    def bot_is_running(self):
        return self.run_thread.is_alive()

    def run(self):
        if not self.bot_is_running():
            self.run_thread.start()
            self.run_button.config(state='disabled')
            self.pause_button.config(state='normal')
            self.stop_button.config(state='normal')
            self.stop_safely_button.config(state='normal')
        else:
            self.log("bot is already running!")

    def pause(self):
        self.pause_button.config(state='disabled')
        self.stop_button.config(state='disabled')
        self.stop_safely_button.config(state='disabled')
        if self.pause_interrupt.is_set():
            self.log("resuming execution...")
            self.pause_interrupt.clear()
            self.pause_button.config(text="Pause")
        else:
            self.log("pausing execution...")
            self.pause_interrupt.set()
            self.pause_button.config(text="Play")

    def pause_callback(self):
        self.pause_button.config(state='normal')
        if not self.driver.bot.paused:
            self.stop_button.config(state='normal')
            self.stop_safely_button.config(state='normal')
        else:
            self.log("paused!")

    def stop(self):
        self.pause_button.config(state='disabled')
        self.stop_button.config(state='disabled')
        self.stop_safely_button.config(state='disabled')
        self.stop_interrupt.set()

    def stop_callback(self):
        self.run_button.config(state='normal')
        self.pause_button.config(state='disabled')
        self.stop_button.config(state='disabled')
        self.stop_safely_button.config(state='disabled')
        self.stop_interrupt.clear()
        self.reset_run_thread()
        self.log("stopped execution!")

    def stop_safely(self):
        self.pause_button.config(state='disabled')
        self.stop_button.config(state='disabled')
        self.stop_safely_button.config(state='disabled')
        self.stop_safely_interrupt.set()

    def stop_safely_callback(self):
        self.run_button.config(state='normal')
        self.pause_button.config(state='disabled')
        self.stop_button.config(state='disabled')
        self.stop_safely_button.config(state='disabled')
        self.stop_safely_interrupt.clear()
        self.reset_run_thread()
        self.log("safely stopped execution!")

    def load(self, values):
        if not os.path.exists(values["bot_config_file"]):
            self.log(f'file does not exist: "{values["bot_config_file"]}"')
            return

        with open(values["bot_config_file"], encoding="utf-8") as f:
            self.bot_config = json.load(f)

        if not self.bot_config:
            self.log(f'invalid bot config: "{values["bot_config_file"]}"')
            self.bot_config = dict()
            return

        self.log(f'loaded bot file: "{values["bot_config_file"]}"')
        self.currently_selected_bot.config(text=self.bot_config.get("uses", "Unknown"))
        self.run_button.config(state='normal')
        self.bot_config_file = values["bot_config_file"]
        self.bot_loaded = True

    def save_log(self):
        try:
            with open("bot_log.txt", "w", encoding="utf-8") as f:
                f.write(self.bot_log_text.get(1.0, tk.END))
            self.log("Лог сохранён в файл bot_log.txt")
        except Exception as ex:
            self.log(f"Ошибка сохранения лога: {ex}")

    def show(self):
        self.root.mainloop()


if __name__ == "__main__":
    for i in range(1, 1000000000):
        try:
            print(f"---> RUN NUMBER {i} <---")
            Application(run_number=i)
            break
        except Exception as e:
            error = f'---> ERROR {e} <---'
            print(error)
            CustomLog.write_log(error)
            sleep(5)
