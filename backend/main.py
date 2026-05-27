import logging
import os

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

load_dotenv()


def _configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )


_configure_logging()

_cors_origins = [
    o.strip()
    for o in os.getenv("CORS_ORIGINS", "http://localhost:3000").split(",")
]

_API_KEY: str | None = os.getenv("API_KEY") or None
_bearer = HTTPBearer(auto_error=False)


async def require_api_key(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> None:
    """Validate API key from Bearer header or ?api_key query param.

    No-op when API_KEY env var is not set (auth disabled).
    EventSource clients cannot send headers, so the query param path
    exists specifically to support the SSE endpoints.
    """
    if _API_KEY is None:
        return
    if credentials is not None and credentials.credentials == _API_KEY:
        return
    if request.query_params.get("api_key") == _API_KEY:
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or missing API key",
        headers={"WWW-Authenticate": "Bearer"},
    )

import db
from log_watcher import LogWatcher
from parser import find_latest_log_file, load_latest_log
from streaming import TrajectoryStreamer
from trajectory import MOCK_TRAJECTORY

logger = logging.getLogger(__name__)

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

    @app.get("/analyze/mock", dependencies=[Depends(require_api_key)])
    async def analyze_mock():
        return StreamingResponse(
            streamer.stream_steps(MOCK_TRAJECTORY, source="mock"),
            media_type="text/event-stream",
        )

    @app.get("/analyze/live", dependencies=[Depends(require_api_key)])
    async def analyze_live():
        log_path = str(find_latest_log_file())
        trajectory = load_latest_log()
        return StreamingResponse(
            streamer.stream_steps(trajectory, source="live", log_path=log_path),
            media_type="text/event-stream",
        )

    @app.get("/watch", dependencies=[Depends(require_api_key)])
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

    @app.get("/sessions", dependencies=[Depends(require_api_key)])
    async def list_sessions():
        return await db.list_sessions()

    @app.get("/sessions/{session_id}", dependencies=[Depends(require_api_key)])
    async def get_session(session_id: int):
        session = await db.get_session(session_id)
        if session is None:
            raise HTTPException(status_code=404, detail="Session not found")
        steps = await db.get_session_steps(session_id)
        return {"session": session, "steps": steps}

    return app


app = create_app()
