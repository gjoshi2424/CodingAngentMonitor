import json
import logging
import os
from pathlib import Path
from typing import Any

_CLAUDE_LOG_ROOT_ENV_VAR = "CLAUDE_LOG_ROOT"
_DEFAULT_CLAUDE_LOG_ROOT = Path.home() / ".claude" / "projects"

logger = logging.getLogger(__name__)


def parse_jsonl_log(file_path: str | Path) -> list[dict[str, Any]]:
    path = Path(file_path).expanduser()
    trajectory: list[dict[str, Any]] = []
    pending_reasoning = ""
    reasoning_from_thinking = False  # don't let text blocks overwrite thinking

    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.strip()
            if not line:
                continue

            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Invalid JSON on line %d of %s", line_number, path)
                raise ValueError(
                    f"Invalid JSON on line {line_number} of {path}"
                ) from exc

            if entry.get("type") != "assistant":
                continue

            message = entry.get("message") or {}
            blocks = message.get("content") or []
            if not isinstance(blocks, list):
                continue

            for block in blocks:
                if not isinstance(block, dict):
                    continue

                block_type = block.get("type")

                if block_type == "thinking":
                    # Claude Code logs redact thinking to an empty string with an
                    # encrypted signature — only capture it when non-empty.
                    text = _coerce_reasoning(block.get("thinking"))
                    if text:
                        pending_reasoning = text
                        reasoning_from_thinking = True
                    continue

                if block_type == "text":
                    # Only capture text-block content when no thinking-based
                    # reasoning is already pending; thinking takes precedence.
                    if not reasoning_from_thinking:
                        text = _coerce_reasoning(block.get("text"))
                        if text:
                            pending_reasoning = text
                    continue

                if block_type != "tool_use":
                    continue

                tool_name = block.get("name") or ""
                tool_args = block.get("input")
                if not isinstance(tool_args, dict):
                    tool_args = {}

                # Fall back to the tool's own description field when no explicit
                # reasoning block preceded this call (common in Claude Code logs).
                reasoning = (
                    pending_reasoning
                    or _coerce_reasoning(tool_args.get("description"))
                    or "[no reasoning provided]"
                )

                trajectory.append(
                    {
                        "step": len(trajectory) + 1,
                        "reasoning": reasoning,
                        "tool_call": {
                            "tool": str(tool_name),
                            "args": tool_args,
                        },
                    }
                )
                # Don't reset pending_reasoning — it persists until a new
                # thinking block overrides it, so consecutive tool calls
                # within the same reasoning context share the same reasoning.

    return trajectory


def load_latest_log() -> list[dict[str, Any]]:
    latest_log = find_latest_log_file()
    return parse_jsonl_log(latest_log)


def find_latest_log_file() -> Path:
    log_root = _resolve_log_root()
    log_files = [path for path in log_root.rglob("*.jsonl") if path.is_file()]

    if not log_files:
        raise FileNotFoundError(f"No .jsonl logs found under {log_root}")

    return max(log_files, key=lambda path: path.stat().st_mtime)


def _resolve_log_root() -> Path:
    configured_root = os.getenv(_CLAUDE_LOG_ROOT_ENV_VAR)
    if configured_root:
        return Path(configured_root).expanduser()

    return _DEFAULT_CLAUDE_LOG_ROOT


def _coerce_reasoning(value: Any) -> str:
    if isinstance(value, str):
        return value

    return ""