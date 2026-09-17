import asyncio
import time

import app.main as main_module


class _Repository:
    def __init__(self):
        self.saved = None

    def replace_detections(self, survey_id, detections):
        self.saved = (survey_id, detections)


class _EventHub:
    def __init__(self):
        self.events = []

    async def publish(self, survey_id, event, **payload):
        self.events.append((survey_id, event, payload))


def test_cpu_inference_does_not_block_asyncio_event_loop(monkeypatch):
    repository = _Repository()
    hub = _EventHub()

    def slow_pipeline(*_args, **_kwargs):
        time.sleep(0.2)
        yield {"id": "detection-1"}

    monkeypatch.setattr(main_module, "repository", repository)
    monkeypatch.setattr(main_module, "event_hub", hub)
    monkeypatch.setattr(main_module, "iter_pipeline", slow_pipeline)

    async def scenario():
        worker = asyncio.create_task(
            main_module._process_in_background(
                "survey-1", "/tmp/source.png", {}, None, False
            )
        )
        await asyncio.sleep(0.03)
        assert not worker.done(), "inference blocked the event loop until completion"
        assert any(event == "processing.stage" for _, event, _ in hub.events)
        await worker

    asyncio.run(scenario())
    assert repository.saved == ("survey-1", [{"id": "detection-1"}])
    assert hub.events[-1][1] == "processing.complete"
