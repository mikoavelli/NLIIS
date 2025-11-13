# main.py
import tkinter as tk
from tkinter import ttk, scrolledtext, messagebox
import threading
import queue
import json

from command_processor import CommandProcessor
from config import (
    CONFIG, CURRENT_LANG, AVAILABLE_LANGS, MODELS_FOUND,
    VOSK_RATE, ALSA_CHANNELS, ALSA_FORMAT, ALSA_PERIOD_SIZE, ALSA_DEVICE,
    COLOR_PARTIAL_TEXT, COLOR_FINAL_TEXT, LANGUAGE_CHOICE_FILE
)

import alsaaudio
import vosk


class SpeechRecognitionApp:
    def __init__(self, root):
        self.root = root

        if not MODELS_FOUND:
            self.root.withdraw()
            messagebox.showerror("Fatal Error", CONFIG['messages']['error_no_models'])
            self.root.destroy()
            return

        self.root.title(CONFIG['ui']['title'])
        self.root.geometry("950x950")

        try:
            model_path = CONFIG['model_path']
            self.model = vosk.Model(model_path)
        except Exception as e:
            messagebox.showerror("Model Load Error", CONFIG['messages']['error_model_load'].format(e))
            self.root.destroy()
            return

        self.is_listening = False
        self.listening_thread = None
        self.gui_queue = queue.Queue()
        self.commands_win = None

        self.command_processor = CommandProcessor(
            self.log_message, self.clear_log_widget, self.on_closing, CONFIG
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
        control_frame.columnconfigure(3, weight=1)

        ttk.Label(control_frame, text=CONFIG['ui']['lang_label']).grid(row=0, column=0, sticky="w", padx=(0, 5))
        self.lang_combo = ttk.Combobox(control_frame, values=AVAILABLE_LANGS, state="readonly")
        self.lang_combo.set(CURRENT_LANG)
        self.lang_combo.grid(row=0, column=1, sticky="w", padx=(0, 20))
        self.lang_combo.bind("<<ComboboxSelected>>", self.on_language_change)

        self.commands_button = ttk.Button(
            control_frame,
            text=CONFIG['ui']['show_commands_button'],
            command=self.show_commands_window
        )
        self.commands_button.grid(row=0, column=2, sticky="w", padx=(0, 20))

        status_text, status_color = CONFIG['ui']['status']['idle']
        self.status_label = ttk.Label(control_frame, text=status_text, style="Status.TLabel", foreground=status_color)
        self.status_label.grid(row=0, column=3, sticky="e", padx=(10, 0))

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=(5, 10))
        self.listen_button = ttk.Button(button_frame, text=CONFIG['ui']['start_button'], command=self.start_listening)
        self.listen_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(0, 5))
        self.stop_button = ttk.Button(button_frame, text=CONFIG['ui']['stop_button'], command=self.stop_listening,
                                      state="disabled")
        self.stop_button.pack(side=tk.LEFT, expand=True, fill=tk.X, padx=(5, 0))

        display_frame = ttk.Frame(main_frame)
        display_frame.pack(fill=tk.BOTH, expand=True)
        display_frame.rowconfigure(0, weight=2)
        display_frame.rowconfigure(1, weight=3)
        log_frame = ttk.LabelFrame(display_frame, text=CONFIG['ui']['log_label'], padding="10")
        log_frame.grid(row=0, column=0, sticky="nsew", pady=(0, 10))
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, state="disabled", font=('TkDefaultFont', 10))
        self.log_text.pack(fill=tk.BOTH, expand=True)
        recognized_frame = ttk.LabelFrame(display_frame, text=CONFIG['ui']['recognized_text_label'], padding="10")
        recognized_frame.grid(row=1, column=0, sticky="nsew")
        self.recognized_text = scrolledtext.ScrolledText(recognized_frame, wrap=tk.WORD, state="disabled",
                                                         font=('TkDefaultFont', 12))
        self.recognized_text.pack(fill=tk.BOTH, expand=True)

        commands_frame = ttk.LabelFrame(main_frame, text=CONFIG['ui']['commands_label'], padding="10")
        commands_frame.pack(fill=tk.X, pady=(10, 0))
        command_list_preview = "\n".join(
            [f"- {phrase}" for phrase in list(self.command_processor.command_phrases.values())[:3]]) + "\n..."
        ttk.Label(commands_frame, text=command_list_preview, justify=tk.LEFT).pack(anchor="w")

    def show_commands_window(self):
        """Creates a non-blocking Toplevel window to display all commands."""
        if self.commands_win is not None and self.commands_win.winfo_exists():
            self.commands_win.lift()
            return

        self.commands_win = tk.Toplevel(self.root)
        self.commands_win.title(CONFIG['ui']['commands_window_title'])
        self.commands_win.resizable(False, False)

        phrases = self.command_processor.command_phrases.values()
        command_text = "\n".join([f"- {phrase}" for phrase in phrases])

        frame = ttk.Frame(self.commands_win, padding="15")
        frame.pack(expand=True, fill="both")

        label = ttk.Label(frame, text=command_text, justify=tk.LEFT, font=('TkDefaultFont', 11))
        label.pack()

    def on_language_change(self, event):
        selected_lang = self.lang_combo.get()
        with open(LANGUAGE_CHOICE_FILE, 'w') as f:
            f.write(selected_lang)
        self.listen_button.config(state="disabled")
        self.stop_button.config(state="disabled")

        from config import ALL_LANG_DATA
        messagebox.showinfo(
            ALL_LANG_DATA[selected_lang]['ui']['lang_changed_title'],
            ALL_LANG_DATA[selected_lang]['ui']['lang_changed_msg']
        )

    def start_listening(self):
        self.is_listening = True
        self.update_ui_for_listening()
        self.log_message(CONFIG['messages']['listening_started'])
        self.listening_thread = threading.Thread(target=self._listen_loop, daemon=True)
        self.listening_thread.start()

    def stop_listening(self):
        if self.is_listening:
            self.is_listening = False
            self.log_message(CONFIG['messages']['listening_stopped'])

    def _listen_loop(self):
        try:
            inp = alsaaudio.PCM(
                type=alsaaudio.PCM_CAPTURE, mode=alsaaudio.PCM_NONBLOCK, device=ALSA_DEVICE,
                channels=ALSA_CHANNELS, rate=VOSK_RATE, format=ALSA_FORMAT, periodsize=ALSA_PERIOD_SIZE
            )
        except alsaaudio.ALSAAudioError as e:
            self.gui_queue.put(("log", CONFIG['messages']['error_alsa'].format(e)))
            self.gui_queue.put(("idle", None))
            return

        rec = vosk.KaldiRecognizer(self.model, VOSK_RATE)
        self.gui_queue.put(("status", CONFIG['ui']['status']['speak']))
        executed_commands_in_utterance = set()
        while self.is_listening:
            length, data = inp.read()
            if length > 0:
                is_final = rec.AcceptWaveform(data)
                if is_final:
                    result_dict = json.loads(rec.Result())
                    final_text = result_dict.get('text', '')
                    self.gui_queue.put(("recognized", final_text))
                    self.command_processor.execute_if_found(final_text, executed_commands_in_utterance)
                    executed_commands_in_utterance.clear()
                else:
                    partial_dict = json.loads(rec.PartialResult())
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
                    self.status_label.config(text=data[0], foreground=data[1])
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
        status_text, status_color = CONFIG['ui']['status']['listening']
        self.status_label.config(text=status_text, foreground=status_color)

    def update_ui_for_idle(self):
        self.listen_button.config(state="normal")
        self.stop_button.config(state="disabled")
        status_text, status_color = CONFIG['ui']['status']['idle']
        self.status_label.config(text=status_text, foreground=status_color)
        self.update_recognized_text("")

    def on_closing(self):
        self.is_listening = False
        self.root.destroy()

    def clear_log_widget(self):
        self.log_text.config(state="normal")
        self.log_text.delete('1.0', tk.END)
        self.log_text.config(state="disabled")


if __name__ == "__main__":
    app_root = tk.Tk()
    app = SpeechRecognitionApp(app_root)
    if MODELS_FOUND:
        app_root.mainloop()
