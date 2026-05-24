import asyncio
import time
from collections.abc import Callable, Coroutine
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from parser import parse_jsonl_log

_CLAUDE_LOG_ROOT = Path.home() / ".claude" / "projects"
_DEBOUNCE_SECONDS = 2.0

# Queue items are (new_steps, log_path) tuples so consumers know the source file.
_QueueItem = tuple[list[dict], str]


class LogWatcher:
    def __init__(self, log_root: Path = _CLAUDE_LOG_ROOT):
        self.log_root = log_root
        self._subscribers: list[asyncio.Queue[_QueueItem]] = []
        self._main_loop: asyncio.AbstractEventLoop | None = None
        self._last_events: dict[str, float] = {}
        self._seen_counts: dict[str, int] = {}

    def subscribe(self) -> asyncio.Queue[_QueueItem]:
        q: asyncio.Queue[_QueueItem] = asyncio.Queue()
        self._subscribers.append(q)
        return q

    def unsubscribe(self, q: asyncio.Queue[_QueueItem]) -> None:
        try:
            self._subscribers.remove(q)
        except ValueError:
            pass

    def create_lifespan(
        self,
        on_startup: Callable[[], Coroutine[Any, Any, None]] | None = None,
    ):
        @asynccontextmanager
        async def lifespan(app: FastAPI):
            if on_startup is not None:
                await on_startup()

            self._main_loop = asyncio.get_running_loop()

            handler = _LogFileEventHandler(self)
            observer = Observer()
            observer.schedule(handler, str(self.log_root), recursive=True)
            observer.start()

            yield

            observer.stop()
            observer.join()

        return lifespan

    def handle_log_file_event(self, path: str) -> None:
        now = time.monotonic()
        if now - self._last_events.get(path, 0.0) < _DEBOUNCE_SECONDS:
            return
        self._last_events[path] = now

        try:
            trajectory = parse_jsonl_log(path)
        except Exception:
            return

        prev = self._seen_counts.get(path, 0)
        new_steps = trajectory[prev:]
        if not new_steps or self._main_loop is None:
            return

        self._seen_counts[path] = len(trajectory)
        for q in list(self._subscribers):
            self._main_loop.call_soon_threadsafe(q.put_nowait, (new_steps, path))


class _LogFileEventHandler(FileSystemEventHandler):
    def __init__(self, watcher: LogWatcher):
        self.watcher = watcher

    def on_created(self, event) -> None:
        self._handle(event)

    def on_modified(self, event) -> None:
        self._handle(event)

    def _handle(self, event) -> None:
        if event.is_directory:
            return

        path = str(event.src_path)
        if not path.endswith(".jsonl"):
            return

        self.watcher.handle_log_file_event(path)