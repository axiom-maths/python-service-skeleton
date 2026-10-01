"""An example scheduled Lambda. Delete it once a real one exists.

It shows the shape a handler should take rather than doing anything useful: the Lambda
entry point stays thin — read configuration, call a plain function, log the outcome —
and the work is in a function a test can call with no AWS anywhere.

Configuration arrives as environment variables that the stack sets, never by the
handler reaching into AWS for it. That keeps the tests credential-free.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


@dataclass(frozen=True)
class Beat:
    environment: str
    scheduled_time: str


def beat(event: dict[str, Any], environment: str) -> Beat:
    """The work, such as it is. Raises on an event it cannot make sense of.

    Raising is the right response to bad input in a scheduled Lambda: after its last
    Attempt the Run is a Failure, the event goes to the dead-letter queue and the alarm
    fires, where returning quietly would look exactly like success.
    """
    scheduled_time = event.get("scheduled_time")
    if not isinstance(scheduled_time, str):
        raise ValueError(f"event has no scheduled_time: {event!r}")
    return Beat(environment=environment, scheduled_time=scheduled_time)


def handler(event: dict[str, Any], context: object) -> dict[str, str]:
    result = beat(event, environment=os.environ["ENVIRONMENT"])
    # The message is an event name, and the detail is in `extra`. With the function's
    # JSON log format each key arrives as its own field, so Logs Insights can filter on
    # `scheduled_time` rather than parsing it back out of a sentence.
    logger.info(
        "heartbeat",
        extra={"environment": result.environment, "scheduled_time": result.scheduled_time},
    )
    return {"status": "ok", "scheduled_time": result.scheduled_time}
