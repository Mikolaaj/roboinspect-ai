import json
import threading

import numpy as np
import pytest
from test_chat import Tracker

from roboinspect.chat import BielikPlanner, ChatService, InferenceCanceled
from roboinspect.rag import (
    UNAVAILABLE,
    UNKNOWN,
    Retrieval,
    RetrievalCanceled,
    Retriever,
    Source,
    documents,
)


def source():
    return Source(
        id="mapping-1",
        title="Mapowanie SLAM",
        text="SLAM tworzy mapę hangaru. W panelu wybierz Rozpocznij mapowanie, następnie Zakończ mapowanie, aby zapisać wynik i przywrócić nawigację.",
        score=0.8,
        url="/guide#mapping-1",
    )


class Search:
    def __init__(self, result=None):
        self.result = result or Retrieval(sources=[source()], corpus_sha256="test")

    def search(self, text, cancel):
        if cancel.is_set():
            raise RetrievalCanceled()
        return self.result


def planner(monkeypatch, response):
    value = BielikPlanner()
    value.retriever = Search()
    monkeypatch.setattr(
        value, "_request", lambda *args: {"message": {"content": json.dumps(response)}}
    )
    return value


def test_answer_sources_persist_and_never_move_robot(service, monkeypatch):
    p = planner(
        monkeypatch, {"supported": True, "answer": source().text, "citations": ["mapping-1"]}
    )
    chat = ChatService(service, p, Tracker())
    row, _ = chat.submit("Jak rozpocząć mapowanie?", "rag")
    chat.process(row)
    saved = chat.get(row["id"])
    assert saved["status"] == "answered"
    assert saved["sources"][0]["id"] == "mapping-1"
    assert saved["rag"]["corpus_sha256"] == "test"
    assert not service.robot.calls and service.store.active() is None
    assert chat.history()[0]["sources"] == saved["sources"]


def test_fabricated_citation_or_unsafe_answer_falls_back_to_evidence(monkeypatch):
    for response in [
        {"supported": True, "answer": source().text, "citations": ["invented"]},
        {
            "supported": True,
            "answer": "Sekret i hasło w /home/operator/.env. " * 5,
            "citations": ["mapping-1"],
        },
    ]:
        p = planner(monkeypatch, response)
        answer, metrics = p.interpret("Jak działa SLAM?", {})
        assert answer.message == source().text
        assert metrics["operator_guide_fallback"] == 1


def test_unknown_and_offline_do_not_call_generator(monkeypatch):
    p = BielikPlanner()
    monkeypatch.setattr(p, "_request", lambda *args: pytest.fail("No generation without evidence"))
    for result, expected in [(Retrieval(), UNKNOWN), (Retrieval(available=False), UNAVAILABLE)]:
        p.retriever = Search(result)
        answer, metrics = p.explain("Jaka jutro pogoda?", "overview", threading.Event())
        assert answer.message == expected and not answer.retrieval.sources
        assert metrics["rag_abstained"] == 1


def test_retrieval_cancellation_is_chat_cancellation(monkeypatch):
    p = planner(monkeypatch, {})
    canceled = threading.Event()
    canceled.set()
    with pytest.raises(InferenceCanceled):
        p.explain("Jak działa mapa?", "mapping", canceled)


def test_cache_rebuilds_when_document_changes_and_ranking_is_semantic(tmp_path):
    corpus = tmp_path / "corpus"
    corpus.mkdir()
    (corpus / "mapping.md").write_text("# Mapa\n\nBudowanie mapy.")
    (corpus / "voice.md").write_text("# Mowa\n\nNagrywanie głosu.")
    calls = []

    def encode(texts, cancel):
        calls.append(texts)
        return np.array(
            [
                [1.0, 0.0] if ("map" in text.lower() or "otoczenie" in text) else [0.0, 1.0]
                for text in texts
            ]
        )

    retriever = Retriever(corpus, tmp_path / "index.json", encode)
    assert retriever.search("poznaj otoczenie").sources[0].id == "mapping-1"
    assert len(calls) == 2
    retriever.search("poznaj otoczenie")
    assert len(calls) == 3  # document vectors reused, query freshly embedded
    (corpus / "mapping.md").write_text("# Mapa\n\nNowa mapa hangaru.")
    result = retriever.search("poznaj otoczenie")
    assert len(calls) == 5 and "Nowa" in result.sources[0].text
    (corpus / "secret.md").symlink_to(corpus / "mapping.md")
    with pytest.raises(ValueError):
        documents(corpus)


def test_stop_does_not_wait_for_retriever(service):
    p = BielikPlanner()

    class Exploding:
        def search(self, *args):
            pytest.fail("STOP must bypass retrieval")

    p.retriever = Exploding()
    chat = ChatService(service, p, Tracker())
    row, _ = chat.submit("STOP", "stop-rag")
    assert row["action"] == "stop" and row["status"] == "answered"


def test_relevant_short_explanation_does_not_need_old_topic_keywords(monkeypatch):
    answer = "Procent oznacza pewność modelu w rozpoznaniu obiektu na zdjęciu. Nie jest gwarancją poprawności i może być wysoki także przy błędnym rozpoznaniu."
    p = planner(monkeypatch, {"supported": True, "answer": answer, "citations": ["mapping-1"]})
    result, metrics = p.explain("Co oznacza procent?", "inspection", threading.Event())
    assert result.message == answer
    assert metrics["operator_guide_fallback"] == 0


def test_generator_can_abstain_even_if_retriever_found_similar_text(monkeypatch):
    p = planner(
        monkeypatch,
        {
            "supported": False,
            "answer": "W instrukcji nie ma informacji, które pozwalałyby odpowiedzieć na takie pytanie. Brakuje danych o tej funkcji i nie będę zgadywać.",
            "citations": [],
        },
    )
    answer, metrics = p.explain("Czy robot potrafi latać?", "overview", threading.Event())
    assert answer.message == UNKNOWN and not answer.retrieval.sources
    assert metrics["rag_abstained"] == 1


def test_public_guide_contains_only_escaped_operator_documents(service, monkeypatch):
    from fastapi.testclient import TestClient

    from roboinspect.api import create_app

    monkeypatch.setattr(
        "roboinspect.api.documents",
        lambda: [
            {
                "id": "safe-1",
                "title": "<script>bad</script>",
                "text": "<img onerror=bad>",
                "url": "/guide#safe-1",
            }
        ],
    )
    with TestClient(create_app(service), base_url="http://127.0.0.1:8765") as client:
        result = client.get("/guide")
    assert result.status_code == 200
    assert "<script>bad" not in result.text and "&lt;script&gt;bad" in result.text
    assert "default-src 'none'" in result.headers["content-security-policy"]


def test_route_is_not_invented_on_the_slam_raster(monkeypatch):
    answer = "Żółta linia na mapie SLAM pokazuje trasę do celu. Po dojeździe robota do sektora linia znika, a panel pokazuje wynik przejazdu."
    p = planner(monkeypatch, {"supported": True, "answer": answer, "citations": ["mapping-1"]})
    result, metrics = p.explain("Co oznacza żółta linia?", "navigation", threading.Event())
    assert result.message == source().text
    assert metrics["operator_guide_fallback"] == 1
