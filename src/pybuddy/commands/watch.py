"""The 'watch' command — monitors a directory for file changes."""

import time

from rich.console import Console

from pybuddy.output.terminal import print_watch_event

console = Console()


def run_watch(directory: str = ".", notify: bool = False):
    """Watch a directory and analyze Python files on save."""
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    class PyBuddyHandler(FileSystemEventHandler):
        def __init__(self):
            self._last_event = {}

        def on_modified(self, event):
            if event.is_directory:
                return
            path = event.src_path
            if not (path.endswith(".py") or path.endswith(".ipynb")):
                return

            # Debounce: ignore events within 2 seconds of the last one for same file
            now = time.time()
            if path in self._last_event and now - self._last_event[path] < 2:
                return
            self._last_event[path] = now

            self._analyze(path, notify)

        def _analyze(self, file_path, notify_enabled):
            print_watch_event(file_path)
            try:
                from pybuddy.commands.analyze import run_analyze

                run_analyze(file_path, offline=False)

                if notify_enabled:
                    from pybuddy.output.notifier import notify as desktop_notify

                    desktop_notify(
                        "PyBuddy",
                        f"Nuovi suggerimenti per {file_path}",
                    )
            except Exception as e:
                console.print(f"  [red]Errore durante l'analisi: {e}[/red]")

    observer = Observer()
    handler = PyBuddyHandler()
    observer.schedule(handler, directory, recursive=True)
    observer.start()

    console.print(
        f"\n  [yellow]👀 PyBuddy sta sorvegliando[/yellow] [bold]{directory}[/bold]"
    )
    console.print("  [dim]Salva un file .py o .ipynb per ricevere suggerimenti. Ctrl+C per fermare.[/dim]\n")

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        console.print("\n[yellow]👋 PyBuddy smette di sorvegliare. A presto![/yellow]")
    observer.join()
