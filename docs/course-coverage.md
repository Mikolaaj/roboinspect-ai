# Pokrycie kursu

Stan: 21.10.2026. To zestawienie działającego projektu, nie lista wszystkich technologii, które trzeba do niego dołożyć. Wymagania projektu końcowego i ograniczenia oceniono osobno w [audycie](project-audit.md).

| Obszar | Zastosowanie w projekcie | Ograniczenie |
|---|---|---|
| Python i inżynieria oprogramowania | Moduły, klasy, kontrakty, obsługa błędów, procesy, konfiguracja, Ruff, pytest, uv i lockfile | Część starszych skryptów ROS ma inną konwencję formatowania niż kod aplikacji |
| REST API i Pydantic | FastAPI, walidacja planów i danych, status, misje, anulowanie i historia | Używamy Pydantic, bez biblioteki Pydantic AI; trwała baza to SQLite |
| ML i przygotowanie danych | Cechy obrazu, EDA, kontrola plików, duplikatów i przecieków, przegląd etykiet, podział według zdjęcia źródłowego | Mały zbiór syntetyczny, bez niezależnej oceny rzeczywistych usterek |
| Uczenie modeli i optymalizacja | Ridge z wyborem alpha na walidacji, transfer learning ResNet18, augmentacja, early stopping, accuracy i macro F1 | Ograniczone strojenie, bez Optuny; dalszy trening odłożony |
| Deep learning i computer vision | YOLO11s, SAM 2.1 Tiny, PyTorch CUDA, własny pilotażowy klasyfikator | YOLO i SAM mają gotowe wagi; klasyfikator nie jest w misjach |
| NLP i asystenci | Lokalny Bielik, strukturalne plany, rozdzielenie pytań i poleceń, STOP, RAG i źródła | Bez dostrajania Bielika; zabezpieczenia ograniczają ryzyko, nie gwarantują odporności na każdą manipulację |
| Mowa | Whisper small, lokalna transkrypcja, edycja przed wysłaniem | Brak odpowiedzi głosowej TTS |
| MLOps i wersjonowanie | MLflow, parametry, metryki, artefakty, hashe danych/wag/promptów, snapshoty i ewaluacje | Brak automatycznej promocji klasyfikatora do produkcji; nie każdy run ma tracing GenAI |
| Testy i CI | Testy Python/JavaScript, Ruff, testy kontenerów i klastra, GitHub Actions | Testy CI z atrapą operatora nie potwierdzają fizyki ani inferencji GPU |
| Docker | Obrazy gateway i MLflow, Compose, test trwałości danych | ROS i modele AI pozostają na hoście |
| Kubernetes i CD | kind, Deployment, Service, ConfigMap, Secret, PV/PVC, sondy, GHCR, wdrożenie i rollback obrazów | Jeden lokalny węzeł; kolejne CD wymaga runnera; rollback nie cofa migracji bazy |
| Monitoring | Prometheus, metryki HTTP i gotowości, reguły alertów | Brak pełnego monitoringu GPU i zewnętrznego powiadamiania |
| Robotyka, rozszerzenie projektu | Gazebo, ROS 2, Nav2, AMCL, SLAM, kamery, lidar, mapy i trasy | Symulacja; nie wykonano wdrożenia na fizycznego robota |

Nie trzeba dodawać PostgreSQL, LangGraph, Agno, Spark, MCP, TTS ani Grafany tylko dla listy technologii. PDF wymaga przejścia przez analizę, uczenie, implementację i wdrożenie; dopuszcza wdrożenie lokalne. Samo użycie gotowych modeli nie zastępuje części dotyczącej własnego uczenia. W tym projekcie tę część dokumentuje pilotaż ridge/ResNet18.

## Co dalej

1. Sprawdzić instalację na czystym Ubuntu według README i zanotować wynik.
2. Przygotować krótkie demo, pokazujące również EDA i wyniki własnego treningu.
3. Jeśli wrócimy do uczenia: nowe zdjęcia i warunki, niezależny test, szersze strojenie oraz integracja klasyfikatora z inspekcją.

Dalszy trening i integracja klasyfikatora pozostają odłożone na życzenie użytkownika.

## Dowody

- [Dane 200 próbek](verification/dataset-200.json), [trening i metryki](verification/classifier-training.json).
- [RAG](verification/rag-evaluation.json), [inspekcje SAM](verification/sam-inspection.json).
- [Test kontenerów](verification/compose-ci.json), [test klastra](verification/kubernetes-ci.json).
- [Rzeczywista sesja Kubernetes](verification/kubernetes-live.json), [udane wydanie GHCR i CD](verification/ghcr-cd.json).

Historyczny pomiar postoju sprzed LLM i wizji znajduje się w [resources-idle.json](verification/resources-idle.json). Nie opisuje obecnego obciążenia całej aplikacji.
