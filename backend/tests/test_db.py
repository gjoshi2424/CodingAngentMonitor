"""Async tests for the SQLite persistence layer in db.py."""

from pathlib import Path

import aiosqlite
import pytest

import db


@pytest.fixture(autouse=True)
def use_temp_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point db._DB_PATH at a fresh temp file for every test."""
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(db, "_DB_PATH", db_path)
    return db_path


def _step_payload(
    step: int = 1,
    flagged: bool = False,
    rule_name: str | None = None,
    severity: str | None = None,
) -> dict:
    return {
        "step": step,
        "reasoning": "test reasoning",
        "tool": "Read",
        "args": {"path": "foo.txt"},
        "divergence_score": 0.1,
        "flagged": flagged,
        "explanation": "looks fine",
        "rule_name": rule_name,
        "severity": severity,
    }


# ---------------------------------------------------------------------------
# init_db
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_init_db_creates_sessions_and_steps_tables(use_temp_db: Path):
    await db.init_db()

    async with aiosqlite.connect(use_temp_db) as conn:
        cursor = await conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
        tables = {row[0] for row in await cursor.fetchall()}

    assert "sessions" in tables
    assert "analysis_steps" in tables


@pytest.mark.asyncio
async def test_init_db_is_idempotent(use_temp_db: Path):
    await db.init_db()
    await db.init_db()  # second call must not raise


# ---------------------------------------------------------------------------
# create_session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_create_session_returns_positive_int(use_temp_db: Path):
    await db.init_db()
    session_id = await db.create_session("mock")
    assert isinstance(session_id, int)
    assert session_id > 0


@pytest.mark.asyncio
async def test_create_session_increments_id(use_temp_db: Path):
    await db.init_db()
    id1 = await db.create_session("mock")
    id2 = await db.create_session("live")
    assert id2 > id1


@pytest.mark.asyncio
async def test_create_session_stores_source_and_log_path(use_temp_db: Path):
    await db.init_db()
    session_id = await db.create_session("live", "/tmp/agent.jsonl")
    session = await db.get_session(session_id)
    assert session["source"] == "live"
    assert session["log_path"] == "/tmp/agent.jsonl"


# ---------------------------------------------------------------------------
# save_step / get_session_steps
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_save_step_persists_data(use_temp_db: Path):
    await db.init_db()
    session_id = await db.create_session("mock")
    await db.save_step(session_id, _step_payload())

    steps = await db.get_session_steps(session_id)
    assert len(steps) == 1
    step = steps[0]
    assert step["tool"] == "Read"
    assert step["reasoning"] == "test reasoning"
    assert step["divergence_score"] == pytest.approx(0.1)


@pytest.mark.asyncio
async def test_save_step_deserialises_args(use_temp_db: Path):
    await db.init_db()
    session_id = await db.create_session("mock")
    await db.save_step(session_id, _step_payload())

    steps = await db.get_session_steps(session_id)
    assert steps[0]["args"] == {"path": "foo.txt"}


@pytest.mark.asyncio
async def test_save_step_flagged_field_is_bool(use_temp_db: Path):
    await db.init_db()
    session_id = await db.create_session("mock")
    await db.save_step(session_id, _step_payload(flagged=True))

    steps = await db.get_session_steps(session_id)
    assert steps[0]["flagged"] is True


@pytest.mark.asyncio
async def test_get_session_steps_ordered_by_step_number(use_temp_db: Path):
    await db.init_db()
    session_id = await db.create_session("mock")

    for i in [3, 1, 2]:
        payload = _step_payload(step=i)
        await db.save_step(session_id, payload)

    steps = await db.get_session_steps(session_id)
    assert [s["step"] for s in steps] == [1, 2, 3]


# ---------------------------------------------------------------------------
# close_session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_close_session_sets_completed_at(use_temp_db: Path):
    await db.init_db()
    session_id = await db.create_session("mock")
    await db.close_session(session_id)

    session = await db.get_session(session_id)
    assert session["completed_at"] is not None


@pytest.mark.asyncio
async def test_close_session_sets_total_steps_and_flagged_count(use_temp_db: Path):
    await db.init_db()
    session_id = await db.create_session("mock")

    await db.save_step(session_id, _step_payload(step=1, flagged=True))
    await db.save_step(session_id, _step_payload(step=2, flagged=False))
    await db.save_step(session_id, _step_payload(step=3, flagged=True))
    await db.close_session(session_id)

    session = await db.get_session(session_id)
    assert session["total_steps"] == 3
    assert session["flagged_count"] == 2


# ---------------------------------------------------------------------------
# list_sessions
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_list_sessions_returns_most_recent_first(use_temp_db: Path):
    await db.init_db()
    id1 = await db.create_session("mock", "log1.jsonl")
    id2 = await db.create_session("live", "log2.jsonl")

    sessions = await db.list_sessions()
    assert sessions[0]["id"] == id2
    assert sessions[1]["id"] == id1


@pytest.mark.asyncio
async def test_list_sessions_empty_when_no_sessions(use_temp_db: Path):
    await db.init_db()
    sessions = await db.list_sessions()
    assert sessions == []


# ---------------------------------------------------------------------------
# get_session
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_session_returns_none_for_missing_id(use_temp_db: Path):
    await db.init_db()
    result = await db.get_session(9999)
    assert result is None


@pytest.mark.asyncio
async def test_get_session_returns_correct_row(use_temp_db: Path):
    await db.init_db()
    session_id = await db.create_session("watch", "/path/to/log.jsonl")
    session = await db.get_session(session_id)
    assert session["id"] == session_id
    assert session["source"] == "watch"
