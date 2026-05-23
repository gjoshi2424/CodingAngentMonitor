import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv()

_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
]

from log_watcher import LogWatcher
from parser import load_latest_log
from streaming import TrajectoryStreamer
from trajectory import MOCK_TRAJECTORY

watcher = LogWatcher()
streamer = TrajectoryStreamer()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=watcher.create_lifespan())

    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins,
        allow_methods=["GET"],
        allow_headers=["*"],
    )

    @app.get("/")
    async def health_check():
        return {"status": "ok"}

    @app.get("/analyze/mock")
    async def analyze_mock():
        return StreamingResponse(
            streamer.stream_steps(MOCK_TRAJECTORY), media_type="text/event-stream"
        )

    @app.get("/analyze/live")
    async def analyze_live():
        trajectory = load_latest_log()
        return StreamingResponse(
            streamer.stream_steps(trajectory), media_type="text/event-stream"
        )

    @app.get("/watch")
    async def watch():
        async def _generator():
            q = watcher.subscribe()
            try:
                while True:
                    new_steps = await q.get()
                    async for chunk in streamer.stream_steps(new_steps):
                        yield chunk
            finally:
                watcher.unsubscribe(q)

        return StreamingResponse(_generator(), media_type="text/event-stream")

    return app


app = create_app()
