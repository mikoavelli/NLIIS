import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import queue
import os
import time
import webbrowser
import csv
from collections import Counter

from language_detector import LanguageDetector
from watcher import FileSystemWatcher

# --- Constants ---
ROOT_DOCS_FOLDER = "corpus_root"
CHECK_QUEUE_TIME = 2000


class MainApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Automatic Language Recognition System")
        self.root.geometry("1200x700")

        self.create_menu()
        self.setup_styles()
        self.detector = LanguageDetector()
        self.setup_ui()
        self.event_queue = queue.Queue()

        if not os.path.exists(ROOT_DOCS_FOLDER):
            os.makedirs(ROOT_DOCS_FOLDER)
            messagebox.showinfo("Setup",
                                f"Root folder '{ROOT_DOCS_FOLDER}' was created.\nPlease add subfolders and .html files to it for detection.")

        self.root.after(100, self.update_file_detections)
        self.start_watcher_thread()
        self.check_queue_for_updates()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    @staticmethod
    def setup_styles():
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("Treeview", rowheight=25)
        style.configure("Treeview.Heading", font=('TkDefaultFont', 10, 'bold'))

    def create_menu(self):
        menubar = tk.Menu(self.root)
        file_menu = tk.Menu(menubar, tearoff=0)
        file_menu.add_command(label="Export Results to CSV...", command=self.export_results_to_csv)
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.root.quit)
        menubar.add_cascade(label="File", menu=file_menu)
        help_menu = tk.Menu(menubar, tearoff=0)
        help_menu.add_command(label="About...", command=self.show_help_dialog)
        menubar.add_cascade(label="Help", menu=help_menu)
        self.root.config(menu=menubar)

    def setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill="both", expand=True)

        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill="x", pady=5)
        btn_refresh = ttk.Button(top_frame, text="Refresh Detections", command=self.update_file_detections)
        btn_refresh.pack(side="right", padx=5)
        btn_export = ttk.Button(top_frame, text="Export to CSV", command=self.export_results_to_csv)
        btn_export.pack(side="right")

        self.status_var = tk.StringVar(value="System ready. Monitoring for file changes...")
        status_bar = ttk.Label(main_frame, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        table_frame = ttk.Frame(main_frame)
        table_frame.pack(pady=10, fill="both", expand=True)

        columns = ("File", "N-Gram Method", "Alphabet Method", "Neural Net Method", "LLM (phi3)")
        self.tree_results = ttk.Treeview(table_frame, columns=columns, show="headings")
        self.tree_results.heading("File", text="File Path", anchor='w')
        self.tree_results.column("File", width=400, anchor='w')
        self.tree_results.heading("N-Gram Method", text="N-Gram Result", anchor='center')
        self.tree_results.column("N-Gram Method", width=150, anchor='center')
        self.tree_results.heading("Alphabet Method", text="Alphabet Result", anchor='center')
        self.tree_results.column("Alphabet Method", width=150, anchor='center')
        self.tree_results.heading("Neural Net Method", text="Neural Net Result", anchor='center')
        self.tree_results.column("Neural Net Method", width=150, anchor='center')
        # --- NEW: Configure the LLM column ---
        self.tree_results.heading("LLM (phi3)", text="LLM Result (phi3)", anchor='center')
        self.tree_results.column("LLM (phi3)", width=150, anchor='center')

        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree_results.yview)
        vsb.pack(side="right", fill="y")
        self.tree_results.configure(yscrollcommand=vsb.set)
        self.tree_results.pack(side="left", fill="both", expand=True)
        self.tree_results.bind("<Double-1>", self.on_item_double_click)

        stats_frame = ttk.LabelFrame(main_frame, text="Summary Statistics", padding="10")
        stats_frame.pack(pady=10, fill="x", expand=False)
        self.stats_label_var = tk.StringVar(value="Statistics will be shown here after a scan.")
        stats_label = ttk.Label(stats_frame, textvariable=self.stats_label_var, justify=tk.LEFT)
        stats_label.pack(anchor='w')

    def update_file_detections(self):
        """Scans the root folder, runs all language detections, and updates statistics."""
        self.status_var.set("Scanning files and detecting languages (this may take a moment with LLM)...")
        self.root.config(cursor="watch")
        self.root.update_idletasks()

        self.tree_results.delete(*self.tree_results.get_children())

        filepaths_to_scan = []
        for dirpath, _, filenames in os.walk(ROOT_DOCS_FOLDER):
            for filename in filenames:
                if filename.endswith(".html"):
                    filepaths_to_scan.append(os.path.join(dirpath, filename))

        if not filepaths_to_scan:
            self.status_var.set("No '.html' files found in 'corpus_root'.")
            self.root.config(cursor="")
            return

        start_time = time.time()
        for filepath in filepaths_to_scan:
            # Run all four detections
            res_ngram = self.detector.detect_by_ngram(filepath)
            res_alpha = self.detector.detect_by_alphabet(filepath)
            res_nn = self.detector.detect_by_nn(filepath)
            res_llm = self.detector.detect_by_llm(filepath)  # <-- NEW CALL

            display_path = os.path.relpath(filepath, '.')
            values = (display_path, res_ngram.upper(), res_alpha.upper(), res_nn.upper(), res_llm.upper())  # <-- ADDED
            self.tree_results.insert("", "end", values=values, iid=filepath)

        end_time = time.time()
        self.root.config(cursor="")
        self.status_var.set(
            f"Detection for {len(filepaths_to_scan)} files completed in {end_time - start_time:.2f}s. Monitoring...")

        self.update_summary_statistics()

    def start_watcher_thread(self):
        self.watcher = FileSystemWatcher(path=ROOT_DOCS_FOLDER, event_queue=self.event_queue)
        self.thread = threading.Thread(target=self.watcher.run, daemon=True)
        self.thread.start()

    def check_queue_for_updates(self):
        try:
            if self.event_queue.get_nowait() == "rescan_needed":
                self.status_var.set("File change detected! Rescanning...")
                self.update_file_detections()
        except queue.Empty:
            pass
        finally:
            self.root.after(CHECK_QUEUE_TIME, self.check_queue_for_updates)

    def on_item_double_click(self, event):
        selected_item = self.tree_results.selection()
        if not selected_item: return
        filepath = selected_item[0]
        try:
            webbrowser.open(f"file://{os.path.abspath(filepath)}")
        except Exception as e:
            messagebox.showerror("Error", f"Could not open file: {filepath}\n\n{e}")

    def update_summary_statistics(self):
        """Calculates and displays summary statistics for all results."""
        all_items = self.tree_results.get_children()
        if not all_items:
            self.stats_label_var.set("No files to analyze.")
            return

        ngram_results = [self.tree_results.item(item, 'values')[1] for item in all_items]
        alpha_results = [self.tree_results.item(item, 'values')[2] for item in all_items]
        nn_results = [self.tree_results.item(item, 'values')[3] for item in all_items]
        llm_results = [self.tree_results.item(item, 'values')[4] for item in all_items]  # <-- NEW

        ngram_counts = Counter(ngram_results)
        alpha_counts = Counter(alpha_results)
        nn_counts = Counter(nn_results)
        llm_counts = Counter(llm_results)

        stats_text = (
            f"Total Files Analyzed: {len(all_items)}\n\n"
            f"N-Gram Method:      {', '.join(f'{lang}: {count}' for lang, count in ngram_counts.items())}\n"
            f"Alphabet Method:    {', '.join(f'{lang}: {count}' for lang, count in alpha_counts.items())}\n"
            f"Neural Net Method:  {', '.join(f'{lang}: {count}' for lang, count in nn_counts.items())}\n"
            f"LLM (phi3) Method:  {', '.join(f'{lang}: {count}' for lang, count in llm_counts.items())}"  # <-- NEW
        )
        self.stats_label_var.set(stats_text)

    def export_results_to_csv(self):
        """Saves the current results in the table to a CSV file."""
        all_items = self.tree_results.get_children()
        if not all_items:
            messagebox.showwarning("No Data", "There are no results in the table to export.")
            return
        filepath = filedialog.asksaveasfilename(
            defaultextension=".csv", filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
            title="Save Results As...")
        if not filepath: return
        try:
            with open(filepath, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(
                    ["File Path", "N-Gram Method", "Alphabet Method", "Neural Net Method", "LLM (phi3) Method"])
                for item in all_items:
                    writer.writerow(self.tree_results.item(item, 'values'))
            messagebox.showinfo("Success", f"Results successfully exported to:\n{filepath}")
        except IOError as e:
            messagebox.showerror("Export Error", f"Could not save file:\n{e}")

    def show_help_dialog(self):
        """Displays a custom, well-formatted help/about window."""
        help_window = tk.Toplevel(self.root)
        help_window.title("About This Application")
        help_window.resizable(False, False)
        help_text = "..."
        main_frame = ttk.Frame(help_window, padding="15")
        main_frame.pack(expand=True, fill="both")
        help_label = ttk.Label(main_frame, text=help_text.strip(), wraplength=550, justify=tk.LEFT)
        help_label.pack(pady=(0, 15))
        ok_button = ttk.Button(main_frame, text="OK", command=help_window.destroy)
        ok_button.pack()
        help_window.transient(self.root)
        help_window.grab_set()
        self.root.wait_window(help_window)

    def on_closing(self):
        print("Application shutting down.")
        if hasattr(self, 'watcher'): self.watcher.stop()
        self.root.destroy()


if __name__ == "__main__":
    root = tk.Tk()
    app = MainApp(root)
    root.mainloop()