import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
import os
import json
import datetime
import subprocess

import alsaaudio
import vosk

MODEL_PATH = "model"
VOSK_RATE = 16000
ALSA_CHANNELS = 1
ALSA_FORMAT = alsaaudio.PCM_FORMAT_S16_LE
ALSA_PERIOD_SIZE = 1024
ALSA_DEVICE = 'default'

STATUS_IDLE = ("Status: Idle", "blue")
STATUS_LISTENING = ("Status: Listening...", "orange")
STATUS_SPEAK = ("Status: Speak now...", "orange")
STATUS_RECOGNIZING = ("Status: Recognizing (offline)...", "green")
COLOR_PARTIAL_TEXT = "gray"
COLOR_FINAL_TEXT = "black"


class CommandProcessor:
    """Handles the logic for recognizing and executing voice commands."""

    def __init__(self, logger_func, log_clear_func, close_func):
        self._log = logger_func
        self._clear_log_widget = log_clear_func
        self._close_app = close_func

        self.command_map = {
            "who is the author": self.show_author,
            "read the first line": self.read_first_line,
            "what is the theme": self.show_theme,
            "clear the log": self.clear_log,
            "show current time": self.show_current_time,
            "open monitoring tool": self.open_monitoring_tool,
            "close yourself": self.close_application
        }

    def execute_if_found(self, text, executed_commands):
        """
        Checks text for a command and executes it if it hasn't been executed in this utterance.
        """
        for command_phrase, action_func in self.command_map.items():
            if command_phrase in text and command_phrase not in executed_commands:
                self._log(f"Command detected: '{command_phrase}'")
                action_func()
                executed_commands.add(command_phrase)
                break

    def show_author(self):
        author = "William Shakespeare"
        self._log(f"RESULT: The author of this work is {author}.")
        messagebox.showinfo("Author", f"The author of this piece is {author}.")

    def read_first_line(self):
        line = "Shall I compare thee to a summer's day?"
        self._log(f"RESULT: The first line is: '{line}'")
        messagebox.showinfo("First Line", f"The first line is:\n'{line}'")

    def show_theme(self):
        theme = "The central theme is the eternal beauty of the beloved, preserved through the power of poetry."
        self._log("RESULT: Displayed the main theme.")
        messagebox.showinfo("Theme", theme)

    def clear_log(self):
        self._clear_log_widget()
        self._log("Log cleared.")

    def show_current_time(self):
        now = datetime.datetime.now()
        formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
        self._log(f"RESULT: Displaying current time: {formatted_time}")
        messagebox.showinfo("Current Time", f"The current date and time is:\n{formatted_time}")

    def open_monitoring_tool(self):
        self._log("ACTION: Attempting to launch 'btop' in gnome-terminal.")
        try:
            command = ["gnome-terminal", "--", "btop"]
            subprocess.Popen(command)
        except FileNotFoundError:
            error_msg = "Could not open monitoring tool. Please ensure 'gnome-terminal' and 'btop' are installed."
            self._log(f"ERROR: {error_msg}")
            messagebox.showerror("Error", error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            self._log(f"ERROR: {error_msg}")
            messagebox.showerror("Error", error_msg)

    def close_application(self):
        self._log("ACTION: Closing application as commanded.")
        self._close_app()


class SpeechRecognitionApp:
    def __init__(self, _root):
        self.root = _root
        self.root.title("Speech Recognition System")
        self.root.geometry("950x900")

        if not os.path.exists(MODEL_PATH):
            messagebox.showerror("Error", f"Vosk model not found. Ensure the '{MODEL_PATH}' directory exists.")
            self.root.destroy()
            return

        try:
            self.model = vosk.Model(MODEL_PATH)
        except Exception as e:
            messagebox.showerror("Model Load Error", f"Failed to load Vosk model: {e}")
            self.root.destroy()
            return

        self.is_listening = False
        self.listening_thread = None
        self.gui_queue = queue.Queue()

        self.command_processor = CommandProcessor(
            self.log_message,
            self.clear_log_widget,
            self.on_closing
        )

        self.setup_styles()
        self.setup_ui()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.process_queue()

    @staticmethod
    def setup_styles():
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=6, font=('TkDefaultFont', 11))
        style.configure("TLabel", padding=5, font=('TkDefaultFont', 11))
        style.configure("Status.TLabel", font=('TkDefaultFont', 12, 'bold'))

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        control_frame = ttk.Frame(main_frame)
        control_frame.pack(fill=tk.X, pady=(0, 10))
        control_frame.columnconfigure(1, weight=1)

        self.listen_button = ttk.Button(control_frame, text="Start Listening", command=self.start_listening)
        self.listen_button.grid(row=0, column=0, padx=(0, 10))
        self.stop_button = ttk.Button(control_frame, text="Stop", command=self.stop_listening, state="disabled")
        self.stop_button.grid(row=0, column=1, padx=(0, 10))
        self.status_label = ttk.Label(control_frame, text=STATUS_IDLE[0], style="Status.TLabel",
                                      foreground=STATUS_IDLE[1])
        self.status_label.grid(row=0, column=2, sticky="e", padx=(10, 0))

        display_frame = ttk.Frame(main_frame)
        display_frame.pack(fill=tk.BOTH, expand=True)
        display_frame.rowconfigure(0, weight=1)
        display_frame.rowconfigure(1, weight=3)

        log_frame = ttk.LabelFrame(display_frame, text="Event and Command Log", padding="10")
        log_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state="disabled", font=('TkDefaultFont', 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)

        recognized_frame = ttk.LabelFrame(display_frame, text="Recognized Text", padding="10")
        recognized_frame.grid(row=1, column=0, sticky="nsew")
        self.recognized_text = scrolledtext.ScrolledText(recognized_frame, wrap=tk.WORD, state="disabled",
                                                         font=('TkDefaultFont', 12))
        self.recognized_text.pack(fill=tk.BOTH, expand=True)

        commands_frame = ttk.LabelFrame(main_frame, text="Available Voice Commands", padding="10")
        commands_frame.pack(fill=tk.X, pady=(10, 0))
        command_list = "\n".join([f"- {cmd}" for cmd in self.command_processor.command_map.keys()])
        ttk.Label(commands_frame, text=command_list, justify=tk.LEFT).pack(anchor="w")

    def start_listening(self):
        self.is_listening = True
        self.update_ui_for_listening()
        self.log_message("Starting microphone listener via pyalsaaudio...")
        self.listening_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listening_thread.start()

    def stop_listening(self):
        if self.is_listening:
            self.is_listening = False
            self.log_message("Listening stopped by user.")

    def _listen_loop(self):
        try:
            inp = alsaaudio.PCM(
                type=alsaaudio.PCM_CAPTURE, mode=alsaaudio.PCM_NONBLOCK, device=ALSA_DEVICE,
                channels=ALSA_CHANNELS, rate=VOSK_RATE, format=ALSA_FORMAT, periodsize=ALSA_PERIOD_SIZE
            )
        except alsaaudio.ALSAAudioError as e:
            self.gui_queue.put(("log", f"ALSA Error: {e}"))
            self.gui_queue.put(("idle", None))
            return

        rec = vosk.KaldiRecognizer(self.model, VOSK_RATE)
        self.gui_queue.put(("status", STATUS_SPEAK))

        executed_commands_in_utterance = set()

        while self.is_listening:
            length, data = inp.read()
            if length > 0:
                is_final = rec.AcceptWaveform(data)

                if is_final:
                    result_json = rec.Result()
                    result_dict = json.loads(result_json)
                    final_text = result_dict.get('text', '')

                    self.gui_queue.put(("recognized", final_text))
                    self.command_processor.execute_if_found(final_text, executed_commands_in_utterance)
                    executed_commands_in_utterance.clear()
                else:
                    partial_json = rec.PartialResult()
                    partial_dict = json.loads(partial_json)
                    partial_text = partial_dict.get('partial', '')

                    self.gui_queue.put(("partial_update", partial_text))
                    self.command_processor.execute_if_found(partial_text, executed_commands_in_utterance)

        inp.close()
        self.gui_queue.put(("idle", None))

    def process_queue(self):
        try:
            while not self.gui_queue.empty():
                task, data = self.gui_queue.get_nowait()
                if task == "status":
                    text, color = data
                    self.status_label.config(text=text, foreground=color)
                elif task == "partial_update":
                    self.update_recognized_text(data, is_partial=True)
                elif task == "recognized":
                    self.update_recognized_text(data, is_partial=False)
                elif task == "log":
                    self.log_message(data, internal=True)
                elif task == "idle":
                    self.update_ui_for_idle()
        finally:
            self.root.after(100, self.process_queue)

    def log_message(self, message, internal=False):
        if not internal:
            self.gui_queue.put(("log", message))
            return
        self.log_text.config(state="normal")
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)
        self.log_text.config(state="disabled")

    def update_recognized_text(self, text, is_partial=False):
        self.recognized_text.config(state="normal")
        self.recognized_text.delete("1.0", tk.END)
        self.recognized_text.insert("1.0", text.capitalize())
        color = COLOR_PARTIAL_TEXT if is_partial else COLOR_FINAL_TEXT
        self.recognized_text.config(foreground=color)
        self.recognized_text.config(state="disabled")

    def update_ui_for_listening(self):
        self.listen_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.status_label.config(text=STATUS_LISTENING[0], foreground=STATUS_LISTENING[1])

    def update_ui_for_idle(self):
        self.listen_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.status_label.config(text=STATUS_IDLE[0], foreground=STATUS_IDLE[1])
        self.update_recognized_text("")

    def on_closing(self):
        self.is_listening = False
        self.root.destroy()

    def clear_log_widget(self):
        self.log_text.config(state="normal")
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state="disabled")


if __name__ == "__main__":
    root = tk.Tk()
    app = SpeechRecognitionApp(root)
    root.mainloop()
