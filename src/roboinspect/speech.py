"""Bounded, offline speech recognition. This service cannot dispatch robot commands."""

import hashlib
import json
import threading
import time
from io import BytesIO
from pathlib import Path

import av
import numpy as np
from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parents[2]
VOCABULARY = "RoboInspect. Polecenia robota: Jedź do sektora A. Jedź do sektora B. Jedź do sektora C. Wróć do bazy. Punkty P1 P2 P3 P4 P5."

AUDIO_TYPES = {"audio/webm", "audio/ogg", "audio/wav", "audio/x-wav", "audio/mp4"}


class SpeechError(Exception):
    def __init__(self, message, code=422):
        super().__init__(message)
        self.code = code


class Transcript(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    language: str = "pl"
    duration_seconds: float
    latency_seconds: float
    model: str = "whisper-small"
    device: str
    tracking_error: bool = False


def decode_bounded(data, max_seconds):
    """Decode only the accepted duration, including containers with false/missing metadata."""
    chunks = []
    count = 0
    try:
        with av.open(BytesIO(data)) as container:
            if not container.streams.audio:
                raise SpeechError("Nagranie nie zawiera dźwięku.")
            stream = container.streams.audio[0]
            stream.thread_type = "NONE"
            resampler = av.AudioResampler(format="s16", layout="mono", rate=16000)
            for frame in container.decode(stream):
                for out in resampler.resample(frame):
                    samples = out.to_ndarray().reshape(-1)
                    count += samples.size
                    if count > max_seconds * 16000:
                        raise SpeechError(f"Nagranie może trwać najwyżej {max_seconds} sekund.")
                    chunks.append(samples)
            for out in resampler.resample(None):
                samples = out.to_ndarray().reshape(-1)
                count += samples.size
                if count > max_seconds * 16000:
                    raise SpeechError("Nagranie jest za długie.")
                chunks.append(samples)
    except SpeechError:
        raise
    except Exception as exc:
        raise SpeechError("Nie można odczytać nagrania. Spróbuj nagrać je ponownie.") from exc
    if count < 4000:
        raise SpeechError("Nagranie jest za krótkie. Powiedz całe polecenie.")
    audio = np.concatenate(chunks).astype(np.float32) / 32768.0
    if float(np.sqrt(np.mean(audio**2))) < 0.001:
        raise SpeechError("Nie słychać mowy. Sprawdź mikrofon i spróbuj ponownie.")
    return audio


class SpeechService:
    def __init__(self, config=None, model_factory=None, tracker=None):
        self.config = config or json.loads((ROOT / "config/speech.json").read_text())
        self.path = ROOT / self.config["model_directory"]
        self.factory = model_factory
        self.model = None
        self.lock = threading.Lock()
        self.tracker = tracker or self.track

    def runtime(self):
        ready = all(
            (self.path / name).is_file()
            for name in [
                "model.bin",
                "config.json",
                "tokenizer.json",
                "vocabulary.txt",
                "manifest.json",
            ]
        )
        return {
            "available": ready,
            "loaded": self.model is not None,
            "busy": self.lock.locked(),
            "model": "whisper-small",
            "device": self.config["device"],
            "max_seconds": self.config["max_seconds"],
            "max_bytes": self.config["max_bytes"],
        }

    def transcribe(self, data):
        if len(data) > self.config["max_bytes"]:
            raise SpeechError("Nagranie jest za duże.", 413)
        if not self.lock.acquire(blocking=False):
            raise SpeechError("Whisper analizuje inne nagranie. Spróbuj ponownie za chwilę.", 429)
        try:
            started = time.monotonic()
            audio = decode_bounded(data, self.config["max_seconds"])
            if self.model is None:
                if self.factory is None:
                    if not self.runtime()["available"]:
                        raise SpeechError(
                            "Whisper nie jest zainstalowany. Uruchom bash scripts/setup_whisper.sh.",
                            503,
                        )
                    self.verify_model()
                    from faster_whisper import WhisperModel

                    factory = WhisperModel
                else:
                    factory = self.factory
                self.model = factory(
                    str(self.path),
                    device=self.config["device"],
                    compute_type=self.config["compute_type"],
                    cpu_threads=self.config["cpu_threads"],
                    num_workers=1,
                    local_files_only=True,
                )
            segments, _ = self.model.transcribe(
                audio,
                language="pl",
                beam_size=5,
                initial_prompt=VOCABULARY,
                vad_filter=True,
                condition_on_previous_text=False,
                no_speech_threshold=0.6,
                log_prob_threshold=-1.0,
                word_timestamps=False,
            )
            parts = [
                s.text.strip() for s in segments if s.no_speech_prob < 0.6 and s.avg_logprob > -1.0
            ]
            result_text = " ".join(parts).strip()
            if not result_text:
                raise SpeechError("Nie rozpoznano wyraźnej mowy. Nagraj polecenie jeszcze raz.")
            if len(result_text) > 2000:
                raise SpeechError("Rozpoznana wypowiedź jest za długa. Użyj krótszego polecenia.")
            result = Transcript(
                text=result_text,
                duration_seconds=len(audio) / 16000,
                latency_seconds=time.monotonic() - started,
                device=self.config["device"],
            )
            try:
                self.tracker(result)
            except Exception:
                result.tracking_error = True
            return result
        except SpeechError:
            raise
        except Exception as exc:
            raise SpeechError(
                "Lokalny Whisper nie mógł przetworzyć nagrania. Spróbuj ponownie.", 503
            ) from exc
        finally:
            self.lock.release()

    def verify_model(self):
        try:
            manifest = json.loads((self.path / "manifest.json").read_text())
            if (
                manifest["repository"] != self.config["repository"]
                or manifest["revision"] != self.config["revision"]
            ):
                raise ValueError("Model revision mismatch")
            for name in ["config.json", "model.bin", "tokenizer.json", "vocabulary.txt"]:
                with (self.path / name).open("rb") as model_file:
                    digest = hashlib.file_digest(model_file, "sha256").hexdigest()
                if digest != manifest["sha256"][name]:
                    raise ValueError("Model checksum mismatch")
        except (ValueError, KeyError, OSError) as exc:
            raise SpeechError(
                "Pliki Whispera są niepełne lub zmienione. Uruchom bash scripts/setup_whisper.sh.",
                503,
            ) from exc

    def track(self, result):
        from mlflow.tracking import MlflowClient

        client = MlflowClient(tracking_uri=f"sqlite:///{ROOT / 'data/mlflow.db'}")
        exp = client.get_experiment_by_name("roboinspect-whisper")
        eid = (
            exp.experiment_id
            if exp
            else client.create_experiment(
                "roboinspect-whisper", artifact_location=(ROOT / "data/mlflow-artifacts").as_uri()
            )
        )
        run = client.create_run(eid)
        try:
            client.log_param(
                run.info.run_id,
                "vocabulary_sha256",
                hashlib.sha256(VOCABULARY.encode()).hexdigest(),
            )
            client.log_param(run.info.run_id, "beam_size", 5)
            for key in ["repository", "revision", "device", "compute_type", "cpu_threads"]:
                client.log_param(run.info.run_id, key, self.config[key])
            for key, value in {
                "audio_seconds": result.duration_seconds,
                "latency_seconds": result.latency_seconds,
                "real_time_factor": result.latency_seconds / result.duration_seconds,
                "characters": len(result.text),
            }.items():
                client.log_metric(run.info.run_id, key, value)
            client.set_tag(run.info.run_id, "dispatch", "draft_only")
            client.set_terminated(run.info.run_id)
        except Exception:
            client.set_terminated(run.info.run_id, status="FAILED")
            raise
