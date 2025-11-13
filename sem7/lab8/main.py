from tkinter import ttk, scrolledtext, messagebox
from idlelib.tooltip import Hovertip

import tkinter as tk
import subprocess
import threading
import pyttsx3

EXAMPLE_TEXT = "To be, or not to be, that is the question that was asked in 1601. Hello my comrad! How are you doing?"


class SpeechSynthesisApp:
    def __init__(self, _root):
        self.root = _root
        self.root.title("Speech Synthesis System (Variant 5: English)")
        self.root.geometry("800x900")

        self.is_speaking = False
        self.espeak_process = None
        self.player_process = None

        self.accents = []
        self.voice_variants = {
            "Male 1": "m1", "Male 2": "m2", "Male 3": "m3", "Male 4": "m4",
            "Male 5": "m5", "Male 6": "m6", "Male 7": "m7",
            "Female 1": "f1", "Female 2": "f2", "Female 3": "f3",
            "Female 4": "f4", "Female 5": "f5",
            "Croak": "croak", "Whisper": "whisper"
        }
        threading.Thread(target=self._get_accents, daemon=True).start()

        self.setup_styles()
        self.setup_ui()

        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def _get_accents(self):
        """Uses pyttsx3 only to get the list of system accents (languages)."""
        try:
            engine = pyttsx3.init()
            all_voices = engine.getProperty('voices')
            self.accents = [
                v for v in all_voices if 'english' in v.name.lower() or 'en' in v.id.lower()
            ]
            engine.stop()
            # Update the GUI in the main thread
            self.root.after(0, self.populate_accents)
        except Exception as e:
            messagebox.showerror("TTS Error",
                                 f"Failed to get accent list: {e}\nPlease ensure 'espeak-ng' is installed.")
            self.root.destroy()

    def populate_accents(self):
        """Populates the dropdown with accents."""
        if not self.accents:
            self.accent_combo['values'] = ['No English accents found']
            self.accent_combo.current(0)
            self.accent_combo.config(state="disabled")
            self.speak_button.config(state="disabled")
            return

        accent_names = [f"{v.name} ({v.id.split('/')[-1]})" for v in self.accents]
        self.accent_combo['values'] = accent_names
        self.accent_combo.current(0)

    @staticmethod
    def setup_styles():
        """Configures the styles."""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("TButton", padding=6, font=('TkDefaultFont', 11))
        style.configure("TLabel", padding=5, font=('TkDefaultFont', 11))

    def setup_ui(self):
        """Creates the graphical user interface."""
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        text_frame = ttk.LabelFrame(main_frame, text="Text to Synthesize", padding="10")
        text_frame.pack(fill=tk.BOTH, expand=True, pady=5)

        self.text_input = scrolledtext.ScrolledText(text_frame, wrap=tk.WORD, height=15, font=('TkDefaultFont', 12))
        self.text_input.pack(fill=tk.BOTH, expand=True)
        self.text_input.insert(tk.END, EXAMPLE_TEXT)

        settings_frame = ttk.LabelFrame(main_frame, text="Synthesis Settings", padding="10")
        settings_frame.pack(fill=tk.X, expand=False, pady=5)
        settings_frame.columnconfigure(1, weight=1)

        ttk.Label(settings_frame, text="Accent:").grid(row=0, column=0, sticky="w", padx=5, pady=5)
        self.accent_combo = ttk.Combobox(settings_frame, state="readonly", width=40)
        self.accent_combo.grid(row=0, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(settings_frame, text="Voice:").grid(row=1, column=0, sticky="w", padx=5, pady=5)
        self.voice_combo = ttk.Combobox(settings_frame, state="readonly", width=40)
        self.voice_combo['values'] = list(self.voice_variants.keys())
        self.voice_combo.current(8)  # Default to 'Female 2'
        self.voice_combo.grid(row=1, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(settings_frame, text="Rate (words/min):").grid(row=2, column=0, sticky="w", padx=5, pady=5)
        self.rate_scale = ttk.Scale(settings_frame, from_=80, to=450, orient=tk.HORIZONTAL)
        self.rate_scale.set(160)
        self.rate_scale.grid(row=2, column=1, sticky="ew", padx=5, pady=5)

        ttk.Label(settings_frame, text="Volume:").grid(row=3, column=0, sticky="w", padx=5, pady=5)
        self.volume_scale = ttk.Scale(settings_frame, from_=0.0, to=1.0, orient=tk.HORIZONTAL)
        self.volume_scale.set(1.0)
        self.volume_scale.grid(row=3, column=1, sticky="ew", padx=5, pady=5)
        Hovertip(self.volume_scale, "Change will be applied on the next synthesis", hover_delay=500)

        button_frame = ttk.Frame(main_frame)
        button_frame.pack(fill=tk.X, pady=10)
        button_frame.columnconfigure(0, weight=1)
        button_frame.columnconfigure(1, weight=1)

        self.speak_button = ttk.Button(button_frame, text="Synthesize Speech", command=self.start_speech_thread)
        self.speak_button.grid(row=0, column=0, sticky="ew", padx=5)

        self.stop_button = ttk.Button(button_frame, text="Stop", command=self.stop_speech, state="disabled")
        self.stop_button.grid(row=0, column=1, sticky="ew", padx=5)

    def start_speech_thread(self):
        """Starts speech synthesis in a separate thread."""
        text = self.text_input.get("1.0", tk.END).strip()
        if not text or self.is_speaking:
            return
        threading.Thread(target=self._speak, args=(text,), daemon=True).start()

    def _speak(self, text):
        """Calls espeak-ng and aplay directly via subprocess."""
        self.is_speaking = True
        self.root.after(0, self.update_ui_for_speaking)

        try:
            selected_accent_index = self.accent_combo.current()
            base_accent_id = self.accents[selected_accent_index].id

            selected_voice_name = self.voice_combo.get()
            voice_variant = self.voice_variants[selected_voice_name]

            final_voice = f"{base_accent_id}+{voice_variant}"

            rate = int(self.rate_scale.get())
            volume = int(self.volume_scale.get() * 200)

            espeak_command = ["espeak-ng", "-v", final_voice, "-s", str(rate), "-a", str(volume), "--stdout", text]
            player_command = ["aplay", "-q", "-"]

            self.espeak_process = subprocess.Popen(espeak_command, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            self.player_process = subprocess.Popen(player_command, stdin=self.espeak_process.stdout,
                                                   stderr=subprocess.PIPE)

            self.player_process.wait()
            espeak_err = self.espeak_process.stderr.read().decode()
            if espeak_err:
                print(f"espeak-ng error: {espeak_err}")

        except FileNotFoundError:
            self.root.after(0, messagebox.showerror, "Error",
                            "Command 'espeak-ng' or 'aplay' not found. Please ensure 'espeak-ng' and 'alsa-utils' are installed.")
        except Exception as e:
            self.root.after(0, messagebox.showerror, "Runtime Error", f"An error occurred: {e}")
        finally:
            self.is_speaking = False
            self.espeak_process = None
            self.player_process = None
            self.root.after(0, self.update_ui_for_idle)

    def stop_speech(self):
        """Safely stops playback by killing the processes."""
        if self.player_process and self.player_process.poll() is None:
            self.player_process.terminate()
        if self.espeak_process and self.espeak_process.poll() is None:
            self.espeak_process.terminate()

    def update_ui_for_speaking(self):
        """Updates the GUI for the 'speaking' state."""
        self.speak_button.config(state="disabled")
        self.stop_button.config(state="normal")
        self.accent_combo.config(state="disabled")
        self.voice_combo.config(state="disabled")
        self.rate_scale.config(state="disabled")
        self.volume_scale.config(state="disabled")

    def update_ui_for_idle(self):
        """Updates the GUI for the 'idle' state."""
        self.speak_button.config(state="normal")
        self.stop_button.config(state="disabled")
        self.accent_combo.config(state="readonly")
        self.voice_combo.config(state="readonly")
        self.rate_scale.config(state="normal")
        self.volume_scale.config(state="normal")

    def on_closing(self):
        """Properly stops processes on closing."""
        self.stop_speech()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = SpeechSynthesisApp(root)
    root.mainloop()
