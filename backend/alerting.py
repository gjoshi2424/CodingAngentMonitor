"""Slack alerting for high-severity monitor flags."""

from __future__ import annotations

import logging
import os
import time

import httpx

logger = logging.getLogger(__name__)

_DEDUP_WINDOW_SECONDS = 60


class AlertManager:
    """Sends Slack alerts for high-severity step flags.

    Reads SLACK_WEBHOOK_URL and BASE_URL from the environment.
    If SLACK_WEBHOOK_URL is not set, all sends are silent no-ops.
    HTTP failures are caught and logged — they never propagate to callers.
    Duplicate alerts for the same rule_name within _DEDUP_WINDOW_SECONDS are suppressed.
    """

    def __init__(self) -> None:
        self._webhook_url: str | None = os.getenv("SLACK_WEBHOOK_URL")
        self._base_url: str | None = os.getenv("BASE_URL", "").rstrip("/") or None
        self._last_sent: dict[str, float] = {}

    async def send(self, step: dict, judgment: dict, session_id: int) -> None:
        """Fire a Slack alert if severity is high and dedup window has passed."""
        if not self._webhook_url:
            return
        if judgment.get("severity") != "high":
            return

        rule_name: str = judgment.get("rule_name") or "unknown_rule"
        now = time.monotonic()
        if now - self._last_sent.get(rule_name, 0) < _DEDUP_WINDOW_SECONDS:
            logger.debug("Alert suppressed (dedup): rule=%s", rule_name)
            return

        self._last_sent[rule_name] = now
        payload = self._build_payload(step, judgment, session_id)

        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.post(self._webhook_url, json=payload)
                response.raise_for_status()
        except Exception as exc:
            logger.error("Slack alert failed: %s", exc)

    def _build_payload(self, step: dict, judgment: dict, session_id: int) -> dict:
        tool = step["tool_call"]["tool"]
        rule_name = judgment.get("rule_name") or "unknown"
        explanation = judgment.get("explanation", "")
        step_num = step["step"]

        session_link = ""
        if self._base_url:
            session_link = f"\n<{self._base_url}/sessions/{session_id}|View session {session_id}>"

        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {
                        "type": "plain_text",
                        "text": ":rotating_light: High-Severity Agent Flag",
                    },
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*Step:* {step_num}"},
                        {"type": "mrkdwn", "text": f"*Tool:* `{tool}`"},
                        {"type": "mrkdwn", "text": f"*Rule:* `{rule_name}`"},
                        {"type": "mrkdwn", "text": f"*Severity:* HIGH"},
                    ],
                },
                {
                    "type": "section",
                    "text": {
                        "type": "mrkdwn",
                        "text": f"*Explanation:* {explanation}{session_link}",
                    },
                },
            ]
        }
