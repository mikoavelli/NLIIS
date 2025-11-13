import datetime
import subprocess
from tkinter import messagebox


class CommandProcessor:
    def __init__(self, logger_func, log_clear_func, close_func, lang_config):
        self._log = logger_func
        self._clear_log_widget = log_clear_func
        self._close_app = close_func
        self.config = lang_config

        self.method_map = {
            'SHOW_AUTHOR': self.show_author,
            'READ_FIRST_LINE': self.read_first_line,
            'SHOW_THEME': self.show_theme,
            'CLEAR_LOG': self.clear_log,
            'SHOW_TIME': self.show_current_time,
            'OPEN_MONITORING': self.open_monitoring_tool,
            'CLOSE_APP': self.close_application,
        }
        self.command_phrases = self.config['commands']

    def execute_if_found(self, text, executed_commands):
        for internal_name, phrase in self.command_phrases.items():
            if phrase in text and internal_name not in executed_commands:
                self._log(self.config['messages']['command_detected'].format(phrase))
                method_to_call = self.method_map.get(internal_name)
                if method_to_call:
                    method_to_call()
                executed_commands.add(internal_name)
                break

    def show_author(self):
        messagebox.showinfo(
            self.config['messages']['author_title'],
            self.config['messages']['author_content']
        )

    def read_first_line(self):
        messagebox.showinfo(
            self.config['messages']['first_line_title'],
            self.config['messages']['first_line_content']
        )

    def show_theme(self):
        messagebox.showinfo(
            self.config['messages']['theme_title'],
            self.config['messages']['theme_content']
        )

    def clear_log(self):
        self._clear_log_widget()
        self._log(self.config['messages']['log_cleared'])

    def show_current_time(self):
        now = datetime.datetime.now()
        formatted_time = now.strftime("%Y-%m-%d %H:%M:%S")
        messagebox.showinfo(
            self.config['messages']['time_title'],
            self.config['messages']['time_content'].format(formatted_time)
        )

    def open_monitoring_tool(self):
        self._log(self.config['messages']['action_launch_btop'])
        try:
            subprocess.Popen(["gnome-terminal", "--", "btop"])
        except FileNotFoundError:
            error_msg = self.config['messages']['error_btop']
            self._log(f"ERROR: {error_msg}")
            messagebox.showerror("Error", error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred: {e}"
            self._log(f"ERROR: {error_msg}")
            messagebox.showerror("Error", error_msg)

    def close_application(self):
        self._log(self.config['messages']['action_closing'])
        self._close_app()
