# Pokrycie kursu i dalsza kolejność

Stan: 18.10.2026. Odniesienie: lokalna lista zagadnień kursu opracowana
z dostępnych transkrypcji. Poniżej rozróżniamy wykonane funkcje od planów.

| Obszar kursu | Co jest obecnie w repo | Granica obecnego zakresu |
|---|---|---|
| Python i OOP | Klasy, dziedziczenie Node ROS, moduły, wyjątki, menedżery kontekstu, pliki JSON, CLI i subprocess | Nie wszystkie zaawansowane konstrukcje kursu muszą mieć zastosowanie |
| Integracja systemów | ROS, most Gazebo, kolejka poleceń, callbacki, osobne procesy, logi i restart | ROS/Gazebo to rozszerzenie robotyczne projektu, nie dowód zrealizowania modułów ML |
| Testowanie | Własne testy integracyjne/E2E na rzeczywistej symulacji, anulowanie, brak trasy, pozycja ground truth | Dodano pytest/fixtures, Ruff i workflow GitHub Actions; CI czeka na push |
| REST/API | FastAPI, kontrakty Pydantic, stan/cel/anulowanie, sekwencje misji i historia SQLite | PostgreSQL, Pydantic Graph i tracing pozostają w planie |
| Robotyka — rozszerzenie projektu | SLAM Toolbox, mapa z lidaru, eksport do AMCL/Nav2 | Kontrolowany obchód normalnej hali; brak autonomicznej eksploracji |
| Obrazy i GPU | RGB, JPEG/MJPEG, trzy kamery, NVIDIA RTX i pomiary zasobów | Nie ma jeszcze modeli detekcji/segmentacji ani własnego treningu |
| Repo i odtwarzanie | Repo Git, konfiguracje, launchery, instrukcje, zapis wyników testów | Dodano uv/pyproject/lockfile; kontenery i automatyczny deployment pozostają w planie |

Gotowe: robotyczna platforma do przyszłego AI. Pozostają do implementacji
uczenie modeli, EDA, LLM/Pydantic AI, głos, RAG, MLflow/Optuna, Docker,
Kubernetes i deployment CD. Podstawowe CI jest już skonfigurowane. Samo zainstalowanie narzędzia lub wpisanie go w plan
nie oznacza wykorzystania go w projekcie.

## Aktualny pomiar zasobów

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
| 6 | Czat, gotowy LLM przez Pydantic AI, walidowany plan i pomiary MLflow |
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
