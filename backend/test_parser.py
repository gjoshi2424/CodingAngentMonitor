import json
import os
import tempfile
import unittest
from pathlib import Path

from parser import load_latest_log, parse_jsonl_log


class ParseJsonlLogTests(unittest.TestCase):
    def test_reasoning_persists_until_next_thinking_block(self) -> None:
        log_entries = [
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "thinking", "thinking": "Inspect the project"}
                    ]
                },
                "timestamp": "2026-05-23T10:00:00Z",
                "uuid": "1",
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {"type": "text", "text": "Starting the search."}
                    ]
                },
                "timestamp": "2026-05-23T10:00:01Z",
                "uuid": "2",
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Glob",
                            "input": {"pattern": "**/*.py"},
                        }
                    ]
                },
                "timestamp": "2026-05-23T10:00:02Z",
                "uuid": "3",
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Grep",
                            "input": {"pattern": "main"},
                        }
                    ]
                },
                "timestamp": "2026-05-23T10:00:03Z",
                "uuid": "4",
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "thinking",
                            "thinking": "Read the most relevant file next",
                        }
                    ]
                },
                "timestamp": "2026-05-23T10:00:04Z",
                "uuid": "5",
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "input": {"path": "backend/main.py"},
                        }
                    ]
                },
                "timestamp": "2026-05-23T10:00:05Z",
                "uuid": "6",
            },
        ]

        steps = parse_jsonl_log(self._write_log(log_entries))

        self.assertEqual(
            steps,
            [
                {
                    "step": 1,
                    "reasoning": "Inspect the project",
                    "tool_call": {
                        "tool": "Glob",
                        "args": {"pattern": "**/*.py"},
                    },
                },
                {
                    "step": 2,
                    "reasoning": "Inspect the project",
                    "tool_call": {
                        "tool": "Grep",
                        "args": {"pattern": "main"},
                    },
                },
                {
                    "step": 3,
                    "reasoning": "Read the most relevant file next",
                    "tool_call": {
                        "tool": "Read",
                        "args": {"path": "backend/main.py"},
                    },
                },
            ],
        )

    def test_tool_without_prior_thinking_uses_empty_reasoning(self) -> None:
        log_entries = [
            {
                "type": "user",
                "message": {"content": [{"type": "text", "text": "hi"}]},
                "timestamp": "2026-05-23T10:00:00Z",
                "uuid": "1",
            },
            {
                "type": "assistant",
                "message": {
                    "content": [
                        {
                            "type": "tool_use",
                            "name": "Read",
                            "input": {"path": "README.md"},
                        }
                    ]
                },
                "timestamp": "2026-05-23T10:00:01Z",
                "uuid": "2",
            },
        ]

        steps = parse_jsonl_log(self._write_log(log_entries))

        self.assertEqual(
            steps,
            [
                {
                    "step": 1,
                    "reasoning": "",
                    "tool_call": {
                        "tool": "Read",
                        "args": {"path": "README.md"},
                    },
                }
            ],
        )

    def test_load_latest_log_selects_newest_jsonl_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            older_log = root / "older" / "old.jsonl"
            newer_log = root / "newer" / "new.jsonl"

            self._write_entries_to_path(
                older_log,
                [
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "tool_use",
                                    "name": "Read",
                                    "input": {"path": "older.txt"},
                                }
                            ]
                        },
                        "timestamp": "2026-05-23T10:00:00Z",
                        "uuid": "1",
                    }
                ],
            )
            self._write_entries_to_path(
                newer_log,
                [
                    {
                        "type": "assistant",
                        "message": {
                            "content": [
                                {
                                    "type": "thinking",
                                    "thinking": "Inspect the newest log",
                                },
                                {
                                    "type": "tool_use",
                                    "name": "Read",
                                    "input": {"path": "newer.txt"},
                                },
                            ]
                        },
                        "timestamp": "2026-05-23T10:00:01Z",
                        "uuid": "2",
                    }
                ],
            )

            old_mtime = newer_log.stat().st_mtime - 10
            os.utime(older_log, (old_mtime, old_mtime))

            self.addCleanup(os.environ.pop, "CLAUDE_LOG_ROOT", None)
            os.environ["CLAUDE_LOG_ROOT"] = tmpdir

            steps = load_latest_log()

            self.assertEqual(
                steps,
                [
                    {
                        "step": 1,
                        "reasoning": "Inspect the newest log",
                        "tool_call": {
                            "tool": "Read",
                            "args": {"path": "newer.txt"},
                        },
                    }
                ],
            )

    def _write_log(self, entries: list[dict]) -> Path:
        tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(tmpdir.cleanup)

        path = Path(tmpdir.name) / "sample.jsonl"
        self._write_entries_to_path(path, entries)

        return path

    def _write_entries_to_path(self, path: Path, entries: list[dict]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            for entry in entries:
                handle.write(json.dumps(entry))
                handle.write("\n")


if __name__ == "__main__":
    unittest.main()