# Faza 5a — API i trwałe misje

Stan: 18.10.2026. Gotowe: kontrakty Pydantic 2, FastAPI, wykonawca sekwencji,
SQLite/SQLAlchemy, historia kroków i zdarzeń, klucze idempotencji, uv, pytest,
Ruff i workflow GitHub Actions. Nie ma jeszcze LLM ani głosu.

## Uruchomienie

Na Ubuntu 24.04 z ROS Jazzy i zależnościami symulacji opisanymi w
[install-and-run.md](install-and-run.md):

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/setup_project.sh
bash scripts/run_cockpit.sh
```

W drugim terminalu:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_control_panel.sh
```

Środowisko `.venv` używa systemowego Python 3.12 zgodnego z binariami ROS.
Nie trzeba go aktywować. Launcher uruchamia API z tego środowiska.
`setup_project.sh` instaluje uv 0.13.1 i synchronizuje zależności z `uv.lock`.

W panelu sterowania pod przyciskami jest formularz „Zaplanuj misję”.
Wpisz np. `A, BASE` i uruchom. Dostępne cele: A, B, C, BASE, P1–P5.
Jedna misja może zawierać 1–20 kroków. Każdy krok to przejazd, bez analizy obrazu.
Kolejny krok rusza po potwierdzonym wyniku Nav2 i zatrzymaniu robota.
Anulowanie dotyczy całej misji, a błąd pomija pozostałe kroki.
Nie uruchamiaj równocześnie diagnostycznego `go_to.py` ani ręcznego sterowania.

## API i architektura

Interaktywna dokumentacja: <http://127.0.0.1:8765/docs>.

- `GET /api/sectors`, `GET /api/status` — konfiguracja i telemetria.
- `POST /api/missions` — MissionPlan; `GET /api/missions` — historia.
- `GET /api/missions/{id}` oraz `/{id}/events` — zapis statusów i audyt.
- `POST /api/missions/{id}/cancel` — anulowanie konkretnej misji.
- Dotychczasowe `/api/goal` i `/api/cancel` korzystają z tego samego wykonawcy.
- `/stream/*.mjpg` — osobne strumienie kamer; obrazów nie zapisujemy w bazie.

Przykład przy gotowym Nav2:

```bash
curl -H 'Content-Type: application/json' -H 'Idempotency-Key: obchod-001' \
  -d '{"name":"Obchód A","steps":[{"target":"A"},{"target":"BASE"}]}' \
  http://127.0.0.1:8765/api/missions
```

Powtórzenie tego samego klucza i planu zwraca tę samą misję (HTTP 200 zamiast
202), również po restarcie. Inny plan z tym kluczem daje 409. Dla nowej misji
użyj nowego klucza. Przyciski przeglądarki zachowują klucz niepotwierdzonego
żądania w sessionStorage, by ponowienie nie dublowało przejazdu.

`src/roboinspect/contracts.py` definiuje plan, kroki, sektory i statusy.
`missions.py` jest deterministycznym wykonawcą, `store.py` zapisuje rekordy
transakcyjnie, `adapter.py` łączy go z kolejką ROS w `operator/server.py`.
HTTP nie steruje bezpośrednio callbackami ROS. Intencja kroku jest zapisywana
przed wysłaniem celu. Wynik musi mieć zgodny execution_id. Jeden proces jest
właścicielem robota (flock), a unikalny aktywny slot w bazie chroni przed dwiema
aktywnymi misjami. W tej wersji używamy jednego workera Uvicorn.

Utrata gotowości, niepotwierdzone wysłanie lub restart aktywnej misji dają
`uncertain`. Wykonawca żąda anulowania celów Nav2 i czeka na potwierdzenie,
gotowość i zerową prędkość. Potem oznacza misję jako `interrupted`.
Nie wznawia sam przejazdu ani pozostałych kroków. Przy braku potwierdzenia
pozostaje zablokowany. Limit kroku wynosi domyślnie 300 s, w API 10–900 s.
To mechanizm aplikacyjny dla symulatora, nie sprzętowy wyłącznik awaryjny.

## Dane i zakres

Historia jest w `data/missions.sqlite3` (SQLite WAL), poza Git.
Zatrzymaj kokpit przed kopiowaniem bazy albo użyj SQLite backup API.
Nie kasuj bazy ani plików blokad podczas działania.
`.env.example` opisuje opcjonalne zmienne; plik nie jest automatycznie wczytywany.
`ROBOINSPECT_DATABASE_URL` zmienia adres SQLAlchemy,
`ROBOINSPECT_OWNER_LOCK` zmienia ścieżkę blokady wykonawcy.

PostgreSQL jest przewidziany w planie. Sterownik można doinstalować przez
`.venv/bin/uv sync --extra postgres`, lecz serwer PostgreSQL nie został tutaj
wdrożony ani zweryfikowany. Domyślne uruchomienie nie wymaga Dockera.
Pydantic Graph i OpenTelemetry/Logfire pozostają na dalszą część fazy 5.
Obecny wykonawca ma własną maszynę stanów. GitHub Actions sprawdza aplikację,
nie uruchamia Gazebo i nie wykonuje deploymentu. Wynik na GitHub będzie
widoczny dopiero po wypchnięciu zmian.

## Testy

```bash
bash scripts/test_project.sh -q
```

Testy obejmują walidację, sekwencje, błąd/anulowanie, timeout, utratę gotowości,
restart bez ponawiania ruchu, korelację wyników, blokadę właściciela,
idempotencję, API i ochronę żądań POST. Systemowe pluginy pytest ROS są
wyłączone tylko dla tych testów aplikacji.

Testy rzeczywistej symulacji: [cockpit.md](cockpit.md).
Modele YOLO i SAM pozostają w [planie percepcji](perception-plan.md).

Test sekwencji na już działającym kokpicie:

```bash
/usr/bin/python3 scripts/check_missions.py
```

Ten test faktycznie porusza robotem: A → BASE, potem rozpoczyna i anuluje
kolejną sekwencję. Wynik zapisuje do `artifacts/phase5-missions/result.json`.

Wyniki odbioru na tym komputerze: [phase5-results.md](phase5-results.md).
