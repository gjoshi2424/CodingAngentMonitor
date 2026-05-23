import asyncio
import json

import openai

from monitor import judge_step


class TrajectoryStreamer:
    def __init__(self):
        self.client = openai.OpenAI(
            base_url="http://localhost:11434/v1", api_key="ollama"
        )

    async def stream_steps(self, trajectory: list[dict]):
        for step in trajectory:
            judgment = await asyncio.to_thread(judge_step, self.client, step)
            yield f"data: {json.dumps(_build_payload(step, judgment))}\n\n"

        yield 'data: {"done": true}\n\n'


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
    }