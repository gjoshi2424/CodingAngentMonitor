import openai
from dotenv import load_dotenv
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

load_dotenv()

from monitor import judge_step  # noqa: E402
from parser import load_latest_log  # noqa: E402

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

client = openai.OpenAI()


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
