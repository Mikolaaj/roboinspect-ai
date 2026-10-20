# Pokrycie kursu i dalsza kolejność

Stan: 18.10.2026. Odniesienie: lokalna lista zagadnień kursu opracowana
z dostępnych transkrypcji. Poniżej rozróżniamy wykonane funkcje od planów.

| Obszar kursu | Co jest obecnie w repo | Granica obecnego zakresu |
|---|---|---|
| Python i OOP | Klasy, dziedziczenie Node ROS, moduły, wyjątki, menedżery kontekstu, pliki JSON, CLI i subprocess | Nie wszystkie zaawansowane konstrukcje kursu muszą mieć zastosowanie |
| Integracja systemów | ROS, most Gazebo, kolejka poleceń, callbacki, osobne procesy, logi i restart | ROS/Gazebo to rozszerzenie robotyczne projektu, nie dowód zrealizowania modułów ML |
| Testowanie | Własne testy integracyjne/E2E na rzeczywistej symulacji, anulowanie, brak trasy, pozycja ground truth | Dodano pytest/fixtures, Ruff i workflow GitHub Actions; CI czeka na push |
| REST/API | FastAPI, kontrakty Pydantic, stan/cel/anulowanie, sekwencje misji i historia SQLite | PostgreSQL, Pydantic Graph i tracing pozostają w planie |
| Robotyka: rozszerzenie projektu | SLAM Toolbox, mapa z lidaru, eksport do AMCL/Nav2 | Kontrolowany obchód normalnej hali; brak autonomicznej eksploracji |
| LLM i NLP | Lokalny Bielik 4.5B Q4_K_M, JSON Schema, walidacja Pydantic, czat i trwałe misje, lokalny Whisper z mikrofonem | Polecenia interpretowane osobno; Pydantic AI, RAG i TTS pozostają w planie |
| MLOps / MLflow | Lokalne eksperymenty, wersja promptu, parametry i metryki, ewaluacja poleceń | Brak treningu wag i rejestru własnego modelu wizyjnego |
| Obrazy i GPU | RGB, JPEG/MJPEG, trzy kamery, NVIDIA RTX i pomiary zasobów | Nie ma jeszcze modeli detekcji/segmentacji ani własnego treningu |
| Repo i odtwarzanie | Repo Git, konfiguracje, launchery, instrukcje, zapis wyników testów | Dodano uv/pyproject/lockfile; kontenery i automatyczny deployment pozostają w planie |

Gotowe: platforma robotyczna, czerwone strefy inspekcji, lokalny czat AI i mikrofon z Whisperem oraz pomiarami MLflow.
Pozostają uczenie modeli, EDA, RAG, Optuna, Docker, Kubernetes i deployment CD.
Wykorzystujemy kontrakty Pydantic bez biblioteki Pydantic AI. Podstawowe CI jest
skonfigurowane; nowy etap wymaga wypchnięcia zmian. Instrukcja i wyniki:
[bielik-chat.md](bielik-chat.md), [bielik-results.md](bielik-results.md).

## Historyczny pomiar zasobów przed dodaniem LLM

Próbka 5.16 s, robot zatrzymany w BASE, trzy kamery, Nav2 i backend;
CPU przeglądarki nie jest wliczone w procesy projektu. Próba została
uruchomiona tymczasowo po zamknięciu kokpitu i ponownie zamknięta.

- CPU projektu: 284.3% przy konwencji 100% = jeden logiczny CPU,
  czyli około 2.84 jednostki CPU z 20 logicznych. Pomiar względem całej
  pojemności procesora: 14.4%.
- Obciążenie całej karty NVIDIA: średnio 1.2%, próbki 0/3/1/1/1%.
- Zajęta pamięć całej karty: 72 MiB z 8188 MiB, około 0.9%.
- GPU renderuje sensory; fizyka, Nav2, ROS i kodowanie/serwowanie obrazu
  nadal obciążają CPU. Miary CPU i GPU mają różne definicje i nie sumują się
  do podziału pracy na 100%. Niskie GPU przy małych obrazach nie oznacza
  braku akceleracji; proces Gazebo na RTX potwierdzono osobnym testem.

To krótki pomiar postoju, bez YOLO/SAM, STT i lokalnego LLM. Nie określa
przyszłego zapasu wydajności przy inferencji. Wynik źródłowy:
[verification/resources-idle.json](verification/resources-idle.json).

## Następne fazy

Numeracja pozostaje zgodna z plan-faz.md. Podstawowe trzy widoki z fazy 4
wykonano wcześniej w fazie 3; wygładzanie/nakładki będą rozwijane dalej.

| Faza | Rezultat |
|---|---|
| Uzupełnienie 1 | uv/pyproject/lockfile, Ruff, pytest, podstawowe GitHub Actions |
| 5 | Pydantic, FastAPI, wykonawca i trwała historia misji, PostgreSQL |
| 6 — wdrożono | Czat Bielik, walidowany plan Pydantic i pomiary MLflow; biblioteka Pydantic AI pozostaje opcjonalna |
| 7 | Mikrofon, gotowy STT, korekta transkrypcji, TTS |
| 8 | RAG: procedury techniczne, wyszukiwanie i odpowiedzi oparte na danych |
| 9 | Dane obrazowe, EDA, etykiety klas/boxów/masek i poprawne splity |
| 10 | Własny model defektów, porównanie algorytmów, YOLO baseline/fine-tuning, SAM, Optuna i MLflow |
| 11 | Inspekcja w misji: YOLO + SAM + ocena defektu, nakładki na kamerze i raport |
| 12 | Ewaluacje całego systemu, odporność na błędy, tracing |
| 13 | Docker i Compose, powtarzalne uruchomienie usług |
| 14 | Kubernetes, registry, automatyczny deployment CI/CD i rollback |
| 15 | Odbiór na drugim komputerze, pełna instrukcja, demo i release |
| 16 — dodatkowo | Porównania np. LangGraph, Agno, Spark, MCP, ONNX, Grafana |

Założenia YOLO + SAM: [perception-plan.md](perception-plan.md). Wersji modeli
nie wybieramy teraz; wspólny budżet RTX 8 GB sprawdzimy przy ich wdrażaniu.

## Rozszerzenie: głos i punkty inspekcyjne

Dodano lokalny Whisper small, nagrywanie z mikrofonu, walidację audio, edytowalną transkrypcję oraz osobny eksperyment MLflow. Sektory prowadzą do czerwonych stref przed tablicami. Głos korzysta z istniejącego wykonawcy misji po sprawdzeniu i wysłaniu tekstu przez operatora. Szczegóły: [instrukcja](voice-and-inspection-zones.md).

## Inspekcja obrazów

Gotowy YOLO11s na lokalnej RTX przetwarza rzeczywisty obraz kamery Gazebo. Pydantic waliduje plany inspekcji i dane wykryć. Trwały wykonawca misji łączy Nav2 z analizą zdjęcia; SQLite zachowuje obserwacje, REST udostępnia historię, a MLflow eksperyment roboinspect-yolo. Zapisane wyniki stanowią źródło odpowiedzi czatu. SAM, trening detektora i RAG wektorowy nie są częścią tego etapu.

## Aktualizacja 19.10: RAG operatora

Dodano lokalne embeddingi EmbeddingGemma na CPU, publiczny zbiór instrukcji, fragmentację, wersjonowany indeks wektorowy, wyszukiwanie i źródła w odpowiedziach Bielika. Metryki i ewaluacja są w MLflow. [Zakres i ograniczenia](rag.md). Gotowy YOLO oraz RAG są wdrożone; SAM, EDA, własny trening, Optuna, Docker i Kubernetes pozostają do wykonania. Historyczne tabele powyżej opisują wcześniejszy stan.

## Aktualizacja: segmentacja SAM

Dodano gotowy SAM 2.1 Tiny, prompty ramkami YOLO, osobne maski obiektów, walidację Pydantic, trwałe artefakty i pomiary MLflow. [Szczegóły](sam.md). Ten etap pokrywa integrację segmentacji; własny trening i pomiary jakości względem ręcznych masek pozostają do wykonania.

## Aktualizacja: przygotowanie danych i EDA

Dodano syntetyczne warianty tablic, deterministyczne grupowanie źródeł, zbieranie rzeczywistych klatek kamery z pochodzeniem etykiet, kontrolę duplikatów, podstawowe miary obrazów i raport EDA z MLflow. [Zakres](dataset.md). Jest to pilot do przeglądu; własny trening, Optuna i niezależna ocena modelu pozostają do wykonania.

## Aktualizacja: kontrola etykiet

Przegląd próbek obejmuje korektę etykiet, zatwierdzanie/odrzucanie, audyt decyzji i kontrolę rewizji. EDA oraz manifest uwzględniają statusy przeglądu i pokrycie klas w częściach zbioru. Własny trening i Optuna nadal pozostają kolejnymi etapami.

## Aktualizacja: trening i ewaluacja klasyfikatora

Dodano porównanie klasycznego modelu ridge z dostrajanym ResNet18 na GPU, preprocessing i augmentację obrazów, wersjonowanie snapshotu i modeli, seed, early stopping, wybór modelu na walidacji oraz końcową ocenę testową. MLflow zapisuje parametry, metryki klas, macierze pomyłek, przebieg uczenia i modele. Pokrywa to pierwszy praktyczny trening ML/DL i część MLOps. Zbiór pozostaje małym pilotem syntetycznym. Optuna, integracja własnego modelu z misjami, niezależna ocena oraz wdrożenie kontenerowe nadal pozostają do wykonania. [Instrukcja](classifier-training.md).

### CI obrazów Docker

GitHub Actions obejmuje testy aplikacji, walidację Compose, budowanie obrazów oraz izolowany test HTTP i trwałości runu/artefaktu MLflow po odtworzeniu kontenerów. Pokrywa to konteneryzację i automatyczną weryfikację integracji. Publikacja obrazów, CD, Kubernetes i rollback pozostają kolejnymi etapami. Szczegóły: [ci-containers.md](ci-containers.md).

## Etap wydań i Kubernetes

Dodano publikowanie obrazów GHCR po testach, tagi według SHA, SBOM i provenance; lokalny klaster kind z Deployment, Service, ConfigMap, Secret, PV/PVC, limitami zasobów i sondami; skrypt aktualizacji oraz automatyczny powrót do poprzednich obrazów; Prometheus z metrykami i regułami alertów. Workflow ręcznego CD wymaga skonfigurowania dedykowanego runnera GitHub. ROS, symulacja i modele GPU nadal działają lokalnie. Trening własnego modelu pozostaje odłożony.

Nie oznacza to pełnego pokrycia całego kursu: wdrożenie jest lokalne i jednowęzłowe, a część treningowa wymaga dalszej pracy. Szczegóły: [Kubernetes](kubernetes.md), [wydania i CD](releases-and-cd.md), [monitoring](monitoring.md).
