from __future__ import annotations

import logging

import pytest

from python_service_skeleton.handlers import heartbeat


def test_beat_reads_the_scheduled_time() -> None:
    result = heartbeat.beat({"scheduled_time": "2026-10-01T06:00:00Z"}, environment="test")
    assert result == heartbeat.Beat(environment="test", scheduled_time="2026-10-01T06:00:00Z")


def test_beat_refuses_an_event_without_a_scheduled_time() -> None:
    # A quiet return here would look exactly like success; raising sends the event to
    # the dead-letter queue, which is what raises the alarm.
    with pytest.raises(ValueError, match="scheduled_time"):
        heartbeat.beat({}, environment="test")


def test_handler_logs_the_beat_as_fields(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    monkeypatch.setenv("ENVIRONMENT", "test")

    with caplog.at_level(logging.INFO, logger=heartbeat.__name__):
        response = heartbeat.handler({"scheduled_time": "2026-10-01T06:00:00Z"}, context=None)

    assert response == {"status": "ok", "scheduled_time": "2026-10-01T06:00:00Z"}
    (record,) = caplog.records
    assert record.getMessage() == "heartbeat"
    assert record.__dict__["scheduled_time"] == "2026-10-01T06:00:00Z"
