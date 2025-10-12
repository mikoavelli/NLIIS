import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

class ChangeHandler(FileSystemEventHandler):
    def __init__(self, event_queue):
        super().__init__()
        self.event_queue = event_queue
        self.last_event_time = 0

    def on_any_event(self, event):
        if event.is_directory or not (event.src_path.endswith('.txt')):
            return

        meaningful_events = {'created', 'modified', 'deleted', 'moved'}
        if event.event_type not in meaningful_events:
            return

        current_time = time.time()
        if current_time - self.last_event_time > 2:
            print(f"Watcher: Detected meaningful event: {event.event_type} on {event.src_path}")
            self.last_event_time = current_time
            if self.event_queue:
                self.event_queue.put("rescan_needed")

class FileSystemWatcher:
    def __init__(self, path, event_queue):
        self.observer = Observer()
        self.path = path
        self.event_queue = event_queue

    def run(self):
        event_handler = ChangeHandler(self.event_queue)
        self.observer.schedule(event_handler, self.path, recursive=True)
        self.observer.start()
        print(f"Watcher: Started monitoring folder: {self.path}")
        try:
            while self.observer.is_alive():
                self.observer.join(1)
        finally:
            if self.observer.is_alive(): self.observer.stop()
            self.observer.join()
            print("Watcher: Observer stopped.")

    def stop(self):
        if self.observer.is_alive():
            self.observer.stop()