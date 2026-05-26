import asyncio
import json
import logging

import openai

import db
from alerting import AlertManager
from monitor import judge_step

logger = logging.getLogger(__name__)


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
        logger.info("Session %d started: source=%s log_path=%s", session_id, source, log_path)

        for step in trajectory:
            try:
                judgment = await asyncio.to_thread(judge_step, self.client, step)
            except Exception as exc:
                logger.warning("Judge unavailable for step %d: %s", step["step"], exc)
                judgment = {
                    "divergence_score": 0.0,
                    "flagged": False,
                    "explanation": f"Judge unavailable: {exc}",
                    "rule_name": None,
                    "severity": None,
                    "error": True,
                }
            logger.info(
                "Step %d processed: tool=%s score=%.2f flagged=%s",
                step["step"],
                step["tool_call"]["tool"],
                judgment["divergence_score"],
                judgment["flagged"],
            )
            if judgment["flagged"]:
                logger.warning(
                    "Step %d flagged: rule=%s severity=%s score=%.2f",
                    step["step"],
                    judgment.get("rule_name"),
                    judgment.get("severity"),
                    judgment["divergence_score"],
                )
            payload = _build_payload(step, judgment)
            await self.alert_manager.send(step, judgment, session_id)
            await db.save_step(session_id, payload)
            yield f"data: {json.dumps(payload)}\n\n"

        await db.close_session(session_id)
        logger.info("Session %d closed", session_id)
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