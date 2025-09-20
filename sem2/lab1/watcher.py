import time
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler


class ChangeHandler(FileSystemEventHandler):
    def __init__(self, event_queue):
        super().__init__()
        self.queue = event_queue

    def on_any_event(self, event):
        """Signal that a meaningful change occurred for any .txt file event."""

        meaningful_events = {'created', 'modified', 'deleted', 'moved'}

        if event.event_type not in meaningful_events:
            return

        is_txt_event = False
        if hasattr(event, 'src_path') and event.src_path.endswith('.txt'):
            is_txt_event = True
        if hasattr(event, 'dest_path') and event.dest_path.endswith('.txt'):
            is_txt_event = True

        if not event.is_directory and is_txt_event:
            print(f"Watcher: Detected meaningful event: {event.event_type} on path: {event.src_path}")
            if self.queue.empty():
                self.queue.put("rescan_needed")


class FileSystemWatcher:
    def __init__(self, path, event_queue):
        self.observer = Observer()
        self.path = path
        self.queue = event_queue
        self._stop_event = time.sleep

    def run(self):
        """Starts the file system monitoring."""
        event_handler = ChangeHandler(self.queue)
        self.observer.schedule(event_handler, self.path, recursive=True)
        self.observer.start()
        print(f"Watcher: Started monitoring folder: {self.path}")
        try:
            while self.observer.is_alive():
                self.observer.join(1)
        except Exception as e:
            print(f"Watcher: Observer loop interrupted by an error: {e}")
        finally:
            if self.observer.is_alive():
                self.observer.stop()
            self.observer.join()
            print("Watcher: Observer stopped.")

    def stop(self):
        """Signals the observer to stop."""
        if self.observer.is_alive():
            self.observer.stop()