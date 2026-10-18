import json
import threading
import wave
from io import BytesIO
from types import SimpleNamespace

import numpy as np
import pytest
from fastapi.testclient import TestClient

from roboinspect.api import create_app
from roboinspect.speech import ROOT, SpeechError, SpeechService, decode_bounded


def recording(seconds=1, silent=False):
    samples = np.zeros(round(seconds * 16000), dtype=np.int16)
    if not silent:
        samples = (np.sin(np.arange(samples.size) / 16000 * 440 * 2 * np.pi) * 4000).astype(
            np.int16
        )
    out = BytesIO()
    with wave.open(out, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        wav.writeframes(samples.tobytes())
    return out.getvalue()


class Model:
    def transcribe(self, *args, **kwargs):
        assert kwargs["language"] == "pl"
        return iter(
            [SimpleNamespace(text="Jedź do A.", no_speech_prob=0.01, avg_logprob=-0.1)]
        ), None


def speech_service(**kwargs):
    return SpeechService(
        model_factory=lambda *args, **kw: Model(), tracker=lambda _: None, **kwargs
    )


@pytest.mark.parametrize(
    "data, seconds",
    [(b"broken", 30), (recording(0.1), 30), (recording(silent=True), 30), (recording(2), 1)],
)
def test_audio_validation_and_duration_cap(data, seconds):
    with pytest.raises(SpeechError):
        decode_bounded(data, seconds)


def test_transcript_is_draft_and_never_dispatches(service):
    with TestClient(
        create_app(service, speech=speech_service()), base_url="http://127.0.0.1:8765"
    ) as client:
        response = client.post(
            "/api/speech/transcribe", content=recording(), headers={"Content-Type": "audio/wav"}
        )
        assert response.status_code == 200
        assert response.json()["text"] == "Jedź do A."
        assert not service.robot.calls
        assert service.store.active() is None


def test_audio_host_origin_size_and_mime(service):
    with TestClient(
        create_app(service, speech=speech_service()), base_url="http://127.0.0.1:8765"
    ) as client:
        for headers, expected in [
            ({"Content-Type": "audio/wav", "Origin": "https://other.test"}, 403),
            ({"Content-Type": "audio/wav", "Host": "evil.test"}, 403),
            ({"Content-Type": "text/html"}, 415),
            ({"Content-Type": "audio/wav", "Content-Length": "2097153"}, 413),
        ]:
            assert (
                client.post("/api/speech/transcribe", content=b"file", headers=headers).status_code
                == expected
            )

        # Chunked bodies are also capped when Content-Length is absent.
        def chunks():
            yield b"0" * 1048576
            yield b"1" * 1048577

        assert (
            client.post(
                "/api/speech/transcribe", content=chunks(), headers={"Content-Type": "audio/webm"}
            ).status_code
            == 413
        )
        assert (
            client.post(
                "/api/cancel", content=recording(), headers={"Content-Type": "audio/wav"}
            ).status_code
            == 415
        )


def test_speech_contention_does_not_queue_more_work():
    speech = speech_service()
    with speech.lock, pytest.raises(SpeechError) as error:
        speech.transcribe(recording())
    assert error.value.code == 429


def test_low_confidence_and_silence_never_become_text():
    class Uncertain(Model):
        def transcribe(self, *args, **kwargs):
            return iter(
                [SimpleNamespace(text="Jedź do A", no_speech_prob=0.9, avg_logprob=-2)]
            ), None

    speech = SpeechService(model_factory=lambda *a, **k: Uncertain(), tracker=lambda _: None)
    with pytest.raises(SpeechError, match="wyraźnej mowy"):
        speech.transcribe(recording())


def test_model_is_local_and_tracking_failure_preserves_transcript():
    calls = []

    def factory(*args, **kwargs):
        calls.append(kwargs)
        return Model()

    def tracker(_):
        raise RuntimeError("tracking down")

    speech = SpeechService(model_factory=factory, tracker=tracker)
    assert speech.transcribe(recording()).tracking_error
    assert speech.transcribe(recording()).text == "Jedź do A."
    assert len(calls) == 1
    assert calls[0]["local_files_only"] is True
    assert calls[0]["num_workers"] == 1


def test_stop_remains_available_while_whisper_is_busy(service):
    entered, release = threading.Event(), threading.Event()

    class Slow(Model):
        def transcribe(self, *args, **kwargs):
            entered.set()
            assert release.wait(5)
            return super().transcribe(*args, **kwargs)

    speech = SpeechService(model_factory=lambda *a, **k: Slow(), tracker=lambda _: None)
    with TestClient(create_app(service, speech=speech), base_url="http://127.0.0.1:8765") as client:
        responses = []
        worker = threading.Thread(
            target=lambda: responses.append(
                client.post(
                    "/api/speech/transcribe",
                    content=recording(),
                    headers={"Content-Type": "audio/wav"},
                )
            )
        )
        worker.start()
        try:
            assert entered.wait(3)
            stop = client.post(
                "/api/chat", json={"text": "STOP"}, headers={"Idempotency-Key": "voice-stop"}
            )
            assert stop.status_code in (200, 202)
            assert stop.json()["action"] == "stop"
            assert worker.is_alive()
        finally:
            release.set()
            worker.join(5)
        assert responses[0].status_code == 200
        assert service.store.active() is None


def test_missing_model_has_clear_error(tmp_path):
    config = json.loads((ROOT / "config/speech.json").read_text())
    config["model_directory"] = str(tmp_path / "missing")
    speech = SpeechService(config=config)
    assert not speech.runtime()["available"]
    with pytest.raises(SpeechError, match="setup_whisper") as error:
        speech.transcribe(recording())
    assert error.value.code == 503


def test_tampered_local_model_is_rejected_before_loading(tmp_path):
    import hashlib

    config = json.loads((ROOT / "config/speech.json").read_text())
    config["model_directory"] = str(tmp_path)
    names = ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"]
    for name in names:
        (tmp_path / name).write_bytes(b"original")
    digest = hashlib.sha256(b"original").hexdigest()
    manifest = {
        "repository": config["repository"],
        "revision": config["revision"],
        "sha256": {name: digest for name in names},
    }
    (tmp_path / "manifest.json").write_text(json.dumps(manifest))
    speech = SpeechService(config=config)
    speech.verify_model()
    (tmp_path / "model.bin").write_bytes(b"corrupt")
    with pytest.raises(SpeechError, match="niepełne lub zmienione"):
        speech.verify_model()
