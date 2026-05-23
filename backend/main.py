import asyncio
import time
from contextlib import asynccontextmanager
from pathlib import Path

import openai
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

load_dotenv()

from monitor import judge_step  # noqa: E402
from parser import load_latest_log, parse_jsonl_log  # noqa: E402

# ---------------------------------------------------------------------------
# Globals initialised in lifespan startup
# ---------------------------------------------------------------------------
log_queue: asyncio.Queue
_main_loop: asyncio.AbstractEventLoop
_last_events: dict[str, float] = {}

_CLAUDE_LOG_ROOT = Path.home() / ".claude" / "projects"
_DEBOUNCE_SECONDS = 2.0
_seen_counts: dict[str, int] = {}


# ---------------------------------------------------------------------------
# Watchdog event handler
# ---------------------------------------------------------------------------
class _LogFileEventHandler(FileSystemEventHandler):
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

        now = time.monotonic()
        if now - _last_events.get(path, 0.0) < _DEBOUNCE_SECONDS:
            return
        _last_events[path] = now

        try:
            trajectory = parse_jsonl_log(path)
        except Exception:
            return

        prev = _seen_counts.get(path, 0)
        new_steps = trajectory[prev:]
        if not new_steps:
            return
        _seen_counts[path] = len(trajectory)
        _main_loop.call_soon_threadsafe(log_queue.put_nowait, new_steps)


# ---------------------------------------------------------------------------
# FastAPI lifespan: start/stop the observer
# ---------------------------------------------------------------------------
@asynccontextmanager
async def lifespan(app: FastAPI):
    global log_queue, _main_loop

    log_queue = asyncio.Queue()
    _main_loop = asyncio.get_event_loop()

    handler = _LogFileEventHandler()
    observer = Observer()
    observer.schedule(handler, str(_CLAUDE_LOG_ROOT), recursive=True)
    observer.start()

    yield

    observer.stop()
    observer.join()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = openai.OpenAI(base_url="http://localhost:11434/v1", api_key="ollama")


async def stream_analysis(websocket: WebSocket, trajectory: list[dict]) -> None:
    for step in trajectory:
        judgment = judge_step(client, step)
        await websocket.send_json(
            {
                "step": step["step"],
                "reasoning": step["reasoning"],
                "tool": step["tool_call"]["tool"],
                "args": step["tool_call"]["args"],
                "divergence_score": judgment["divergence_score"],
                "flagged": judgment["flagged"],
                "explanation": judgment["explanation"],
                "rule_name": judgment.get("rule_name"),
                "severity": judgment.get("severity"),
            }
        )

    await websocket.send_json({"done": True})


@app.get("/")
async def health_check():
    return {"status": "ok"}


@app.websocket("/ws/analyze")
async def analyze(websocket: WebSocket):
    await websocket.accept()

    data = await websocket.receive_json()
    trajectory = data["trajectory"]

    await stream_analysis(websocket, trajectory)


@app.websocket("/ws/analyze/live")
async def analyze_live(websocket: WebSocket):
    await websocket.accept()

    trajectory = load_latest_log()
    await stream_analysis(websocket, trajectory)


@app.websocket("/ws/watch")
async def watch(websocket: WebSocket):
    await websocket.accept()

    try:
        while True:
            new_steps = await log_queue.get()
            await stream_analysis(websocket, new_steps)
    except Exception:
        pass
