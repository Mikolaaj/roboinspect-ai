"""Local semantic retrieval over an explicit public operator corpus, never the repository."""

import asyncio
import hashlib
import json
import math
import re
import threading
import time
from pathlib import Path
from uuid import uuid4

import httpx
import numpy as np
from pydantic import Field

from .contracts import StrictModel
from .operator_policy import normalized

ROOT = Path(__file__).resolve().parents[2]
CORPUS = ROOT / "knowledge/operator"
MODEL = "embeddinggemma:300m"
WEIGHTS_SHA256 = "0800cbac9c2064dde519420e75e512a83cb360de3ad5df176185dc69652fc515"
URL = "http://127.0.0.1:11436"
UNKNOWN = "Nie znalazłem wystarczającej informacji w instrukcji operatora. Zapytaj o sterowanie, mapowanie, kamery, inspekcje lub MLflow."
UNAVAILABLE = "Wyszukiwanie w instrukcji jest chwilowo niedostępne. Spróbuj ponownie. Do zatrzymania robota użyj STOP lub Anuluj przejazd."


class RetrievalCanceled(Exception):
    pass


class Source(StrictModel):
    id: str
    title: str
    text: str
    score: float
    url: str


class Retrieval(StrictModel):
    sources: list[Source] = Field(default_factory=list)
    corpus_sha256: str = ""
    weights_sha256: str = WEIGHTS_SHA256
    model: str = MODEL
    seconds: float = 0
    available: bool = True


async def post(payload, cancel):
    async with httpx.AsyncClient(timeout=60, trust_env=False) as client:
        task = asyncio.create_task(client.post(URL + "/api/embed", json=payload))
        try:
            while not task.done():
                if cancel.is_set():
                    raise RetrievalCanceled()
                await asyncio.wait({task}, timeout=0.05)
            if cancel.is_set():
                raise RetrievalCanceled()
            response = await task
            response.raise_for_status()
            return response.json()["embeddings"]
        finally:
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass


def embed(texts, cancel):
    values = np.asarray(
        asyncio.run(
            post(
                {
                    "model": MODEL,
                    "input": texts,
                    "truncate": False,
                    "keep_alive": "10m",
                    "options": {"num_gpu": 0, "num_ctx": 2048},
                },
                cancel,
            )
        ),
        dtype=np.float32,
    )
    if values.ndim != 2 or len(values) != len(texts) or not np.isfinite(values).all():
        raise ValueError("Invalid embedding response")
    norms = np.linalg.norm(values, axis=1, keepdims=True)
    if np.any(norms < 1e-8):
        raise ValueError("Empty embedding")
    return values / norms


def documents(corpus=CORPUS):
    """Only approved files. No recursive crawl, user uploads, symlinks or private config."""
    chunks = []
    for path in sorted(corpus.glob("*.md")):
        if path.is_symlink():
            raise ValueError("Symlinks are not operator documents")
        content = path.read_text(encoding="utf-8")
        title, body = content.split("\n", 1)
        title = title.lstrip("# ").strip()
        # Sentence boundaries keep procedures together within a bounded embedding input.
        sentences = body.strip().split(". ")
        parts, current = [], ""
        for sentence in sentences:
            if len(current) + len(sentence) > 1000 and current:
                parts.append(current.strip())
                current = ""
            current += sentence + ". "
        if current.strip():
            parts.append(current.strip().rstrip(".") + ".")
        for index, text in enumerate(parts):
            chunks.append(
                {
                    "id": f"{path.stem}-{index + 1}",
                    "title": title,
                    "text": text,
                    "url": f"/guide#{path.stem}-{index + 1}",
                }
            )
    if not chunks:
        raise ValueError("Operator corpus is empty")
    return chunks


class Retriever:
    def __init__(self, corpus=CORPUS, cache=None, encoder=embed):
        self.corpus = corpus
        self.cache = cache or ROOT / "data/rag/index.json"
        self.encoder = encoder
        self.lock = threading.Lock()

    def index(self, cancel):
        chunks = documents(self.corpus)
        digest = hashlib.sha256(json.dumps(chunks, ensure_ascii=False).encode()).hexdigest()
        with self.lock:
            try:
                data = json.loads(self.cache.read_text())
                if (
                    data["sha256"] == digest
                    and data["model"] == MODEL
                    and data.get("weights_sha256") == WEIGHTS_SHA256
                ):
                    vectors = np.asarray(data["vectors"], dtype=np.float32)
                    if (
                        vectors.ndim == 2
                        and len(vectors) == len(chunks)
                        and np.isfinite(vectors).all()
                    ):
                        return chunks, vectors, digest
            except (OSError, ValueError, KeyError):
                pass
            vectors = self.encoder(
                [f"title: {c['title']} | text: {c['text']}" for c in chunks], cancel
            )
            if cancel.is_set():
                raise RetrievalCanceled()
            self.cache.parent.mkdir(parents=True, exist_ok=True)
            temp = self.cache.with_name(f".{self.cache.name}.{uuid4().hex}.tmp")
            temp.write_text(
                json.dumps(
                    {
                        "sha256": digest,
                        "model": MODEL,
                        "weights_sha256": WEIGHTS_SHA256,
                        "vectors": vectors.tolist(),
                    }
                )
            )
            temp.replace(self.cache)
            return chunks, vectors, digest

    def search(self, question, cancel=None):
        cancel = cancel or threading.Event()
        started = time.monotonic()
        try:
            # Reject unrelated questions before embedding. This is a scope gate, not a planner.
            scope = r"robot|roboinspect|system|otoczen|hangar|hal[aię]|sektor|baz[ayę]|sterow|misj|przejazd|map|slam|nav2|lidar|kamer|obraz|widok|monitor|zolt|tras|mikrofon|glos|nagry|nagran|mow|whisper|mlflow|wynik|eksperyment|inspek|detek|wykry|yolo|person|pewn|procent|tablic|baner|zdjec|sam\b|segment|mask|masek|dane|zbior|etykiet|usterk|wariant|pekn|zabrud|zaslon|histori|przeszk|magazyn|stop|zatrzym|anul|enter|wyslij|rozmow|polecen|p[1-5]\b"
            if not re.search(scope, normalized(question)):
                return Retrieval(seconds=time.monotonic() - started)
            chunks, vectors, digest = self.index(cancel)
            query = self.encoder(["task: search result | query: " + question], cancel)[0]
            semantic = vectors @ query

            # Light lexical reranking helps exact UI labels and Polish short questions.
            def terms(text):
                return {
                    word[:5]
                    for word in re.findall(r"[a-z0-9]+", normalized(text))
                    if len(word) >= 4
                }

            query_terms = terms(question)
            doc_terms = [terms(c["title"] + " " + c["text"]) for c in chunks]
            weights = {
                term: math.log(1 + len(chunks) / (1 + sum(term in d for d in doc_terms)))
                for term in query_terms
            }
            total = sum(weights.values()) or 1
            lexical = np.array(
                [sum(weights[t] for t in query_terms & d) / total for d in doc_terms]
            )
            scores = semantic + 0.15 * lexical
            order = np.argsort(-scores)[:3]
            sources = [
                Source(**chunks[i], score=round(float(scores[i]), 5))
                for i in order
                if semantic[i] >= 0.28 and scores[i] >= scores[order[0]] - 0.12
            ]
            return Retrieval(
                sources=sources, corpus_sha256=digest, seconds=time.monotonic() - started
            )
        except RetrievalCanceled:
            raise
        except (httpx.HTTPError, OSError, ValueError, KeyError):
            return Retrieval(available=False, seconds=time.monotonic() - started)
