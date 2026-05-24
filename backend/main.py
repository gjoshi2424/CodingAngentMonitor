import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

load_dotenv()

_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
]

import db
from log_watcher import LogWatcher
from parser import find_latest_log_file, load_latest_log
from streaming import TrajectoryStreamer
from trajectory import MOCK_TRAJECTORY

watcher = LogWatcher()
streamer = TrajectoryStreamer()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=watcher.create_lifespan(on_startup=db.init_db))

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
            streamer.stream_steps(MOCK_TRAJECTORY, source="mock"),
            media_type="text/event-stream",
        )

    @app.get("/analyze/live")
    async def analyze_live():
        log_path = str(find_latest_log_file())
        trajectory = load_latest_log()
        return StreamingResponse(
            streamer.stream_steps(trajectory, source="live", log_path=log_path),
            media_type="text/event-stream",
        )

    @app.get("/watch")
    async def watch():
        async def _generator():
            q = watcher.subscribe()
            try:
                while True:
                    new_steps, log_path = await q.get()
                    async for chunk in streamer.stream_steps(
                        new_steps, source="watch", log_path=log_path
                    ):
                        yield chunk
            finally:
                watcher.unsubscribe(q)

        return StreamingResponse(_generator(), media_type="text/event-stream")

    @app.get("/sessions")
    async def list_sessions():
        return await db.list_sessions()

    @app.get("/sessions/{session_id}")
    async def get_session(session_id: int):
        session = await db.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        steps = await db.get_session_steps(session_id)
        return {"session": session, "steps": steps}

    return app


app = create_app()
