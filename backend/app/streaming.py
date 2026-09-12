"""In-memory fan-out for one edge/offline API process.

Events are deliberately small JSON records so the same contract can later be backed
by Redis/NATS for multi-process shore-side deployments.
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Any


class SurveyEventHub:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue[dict[str, Any]]]] = defaultdict(set)
        self._state: dict[str, dict[str, Any]] = {}

    async def publish(self, survey_id: str, event: str, **payload: Any) -> None:
        message = {"event": event, "survey_id": survey_id, **payload}
        if event in {"processing.started", "processing.stage", "processing.complete", "processing.failed"}:
            self._state[survey_id] = message
        for queue in list(self._subscribers[survey_id]):
            await queue.put(message)

    def subscribe(self, survey_id: str) -> asyncio.Queue[dict[str, Any]]:
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._subscribers[survey_id].add(queue)
        if survey_id in self._state:
            queue.put_nowait(self._state[survey_id])
        else:
            queue.put_nowait({"event": "stream.ready", "survey_id": survey_id})
        return queue

    def unsubscribe(self, survey_id: str, queue: asyncio.Queue[dict[str, Any]]) -> None:
        self._subscribers[survey_id].discard(queue)


event_hub = SurveyEventHub()
