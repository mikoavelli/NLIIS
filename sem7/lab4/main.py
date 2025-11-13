import tkinter as tk
from ui import MachineTranslationApp


def main():
    """Initializes and runs the Tkinter application."""
    root = tk.Tk()
    MachineTranslationApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
