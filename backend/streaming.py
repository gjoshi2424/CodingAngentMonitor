import asyncio
import json

import openai

import db
from alerting import AlertManager
from monitor import judge_step


class TrajectoryStreamer:
    def __init__(self):
        self.client = openai.OpenAI(
            base_url="http://localhost:11434/v1", api_key="ollama"
        )
        self.alert_manager = AlertManager()

    async def stream_steps(
        self,
        trajectory: list[dict],
        source: str,
        log_path: str | None = None,
    ):
        session_id = await db.create_session(source, log_path)

        for step in trajectory:
            try:
                judgment = await asyncio.to_thread(judge_step, self.client, step)
            except Exception as exc:
                judgment = {
                    "divergence_score": 0.0,
                    "flagged": False,
                    "explanation": f"Judge unavailable: {exc}",
                    "rule_name": None,
                    "severity": None,
                    "error": True,
                }
            payload = _build_payload(step, judgment)
            await self.alert_manager.send(step, judgment, session_id)
            await db.save_step(session_id, payload)
            yield f"data: {json.dumps(payload)}\n\n"

        await db.close_session(session_id)
        yield f"data: {json.dumps({'done': True, 'session_id': session_id})}\n\n"


def _build_payload(step: dict, judgment: dict) -> dict:
    return {
        "step": step["step"],
        "reasoning": step["reasoning"],
        "tool": step["tool_call"]["tool"],
        "args": step["tool_call"]["args"],
        "divergence_score": judgment["divergence_score"],
        "flagged": judgment["flagged"],
        "explanation": judgment["explanation"],
        "rule_name": judgment.get("rule_name"),
        "severity": judgment.get("severity"),
        "error": judgment.get("error", False),
    }