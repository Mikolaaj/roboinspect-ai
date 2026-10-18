# Bielik: czat do sterowania robotem i MLflow

## Przygotowanie jednorazowe

Zatrzymaj kokpit przed zmianą środowiska:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/stop_cockpit.sh
bash scripts/setup_project.sh
bash scripts/setup_bielik.sh
```

Wymagania: Ubuntu 24.04, działający sterownik NVIDIA (`nvidia-smi`), ROS Jazzy,
zależności istniejącej symulacji, curl, tar z obsługą zstd. Skrypt pobiera około
1.4 GB silnika i 2.9 GB wag. Potrzeba też miejsca na rozpakowany silnik oraz
kopię wag w magazynie Ollama. Nie instaluje usług systemowych ani nie wymaga sudo.
Dane modeli i rozmowy są ignorowane przez Git. Model pobierany jest jednorazowo;
po przygotowaniu inferencja działa lokalnie bez klucza API.

Używamy modelu SpeakLeash Bielik 4.5B v3.0 Instruct z **kwantyzacją społecznościową
second-state Q4_K_M**. Źródło, niezmienny commit i SHA256 znajdują się w
`config/bielik.json`; instalator sprawdza SHA256. Szablon konwersacji jest oparty
na instrukcji wydawcy modelu. Jest to gotowy model, bez własnego treningu.

## Codzienne uruchamianie — dwie komendy

Zatrzymanie poprzedniej sesji:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/stop_cockpit.sh
```

Terminal 1:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_cockpit.sh
```

Terminal 2:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_control_panel.sh
```

Panel: http://127.0.0.1:8765/control, kamery: http://127.0.0.1:8765/,
MLflow: http://127.0.0.1:5001. Kokpit zarządza procesami Ollama, MLflow,
Gazebo, Nav2/SLAM i API. Ctrl+C w terminalu kokpitu lub stop_cockpit.sh
zatrzymuje procesy; rozmowy, misje i eksperymenty pozostają na dysku.

## Sprawdzenie ręczne

1. Poczekaj na Nav2 gotowe. Po prawej widoczny jest czat, po lewej dotychczasowe
   przyciski, mapa, planowanie i historia.
2. Wpisz „Cześć”, a potem „Gdzie teraz jesteś?”. Pytanie o stan odczytuje rzeczywisty
   snapshot i historię, nie opis pozycji wymyślony przez model.
3. Wpisz „Jedź do B i wróć do bazy”. Powinna powstać jedna misja B → BASE;
   śledź kamery i wynik Nav2 pod wiadomością. Przyjęcie nie oznacza dojazdu.
4. „Anuluj bieżący przejazd” anuluje misję widoczną przed rozpoczęciem inferencji.
   Przycisk anulowania po lewej pozostaje dostępny niezależnie od pracy modelu.
5. „Jedź do Z” powinno wywołać doprecyzowanie bez misji. Model może mylnie zrozumieć
   tekst mimo poprawnego JSON; testy oceniają semantykę, walidacja nie dowodzi rozumienia.
6. Odśwież panel i uruchom kokpit ponownie: rozmowa pozostaje. Wcześniejsze wiadomości
   można wczytywać przyciskiem. Nieukończone po restarcie odpowiedzi są oznaczane jako
   przerwane i nigdy nie są automatycznie wykonywane ponownie.
7. W MLflow otwórz eksperyment `roboinspect-bielik`: sprawdź parametry, metryki,
   identyfikator misji i plik `interaction.json` z promptem oraz interpretacją.

## Architektura i granice

Tekst → kolejka czatu → lokalne Ollama/Bielik → JSON Schema → walidacja Pydantic
→ istniejący MissionService → trwały zapis misji → Nav2 → rzeczywisty wynik w czacie.

Akcje modelu to navigate, status, cancel, chat i clarify. Cele to wyłącznie
A/B/C/BASE/P1–P5, maksymalnie 20 kroków. Model nie dostaje terminala, dowolnych
współrzędnych ani bezpośredniego cmd_vel. Nie steruje mapowaniem; służą do tego
istniejące przyciski. Aktywna misja, mapowanie lub brak gotowości blokują nowy ruch.

POST /api/chat zapisuje wiadomość i zwraca 202 bez oczekiwania na inferencję.
Wymaga Idempotency-Key; ponowne wysłanie tego samego klucza nie tworzy nowej misji.
Jeden worker obsługuje jedną odpowiedź naraz. Timeout modelu 90 s. STOP obsługiwany jest bez modelu; polecenia jazdy interpretuje Bielik. Wyjaśnienia
mają osobny tor i mogą korzystać z publicznej instrukcji operatora po wykryciu słabej odpowiedzi. Błąd modelu jest widoczny w rozmowie.
Rozmowa jest wspólna dla lokalnego operatora i utrwalona w tabeli chat_turns w tej
samej bazie co misje. GET /api/chat obsługuje `before` i `limit` do wczytywania całości.
Każda wiadomość jest interpretowana osobno z aktualnym stanem robota. Pełna rozmowa
pozostaje w bazie i interfejsie, ale wcześniejsze polecenia nie są ponownie podawane
planerowi. Wskaż cel w każdej nowej komendzie; samo „tam” lub „tak” wymaga doprecyzowania.

Ollama nasłuchuje na loopback:11435 i ma osobny magazyn `data/ollama-models`.
Kontekst 4096, jeden model i jedna inferencja naraz; keep_alive 2 min zwalnia wagi po
bezczynności. GPU służy do inferencji i renderowania, CPU do fizyki, ROS i API.
Nie zakładamy, że przyszłe YOLO, SAM i Whisper zmieszczą się stale razem w VRAM.

## MLflow i ewaluacja

Lokalny backend SQLite `data/mlflow.db`, artefakty `data/mlflow-artifacts`.
Każda odpowiedź rejestruje nazwę modelu, kwantyzację, prompt/version/hash, kontekst,
czas odpowiedzi, zgodność schematu, przyjęcie misji i liczbę tokenów.
Dostępne pomiary GPU są **próbką całego GPU po inferencji**, nie średnią z przebiegu
ani zużyciem wyłącznie przez model. Brak nvidia-smi nie tworzy fikcyjnych zer.
Zapis eksperymentu następuje po trwałym zapisie wyniku; awaria MLflow nie ponawia
ruchu i jest sygnalizowana w czacie. Zawartość rozmowy i prompt trafiają do lokalnych
artefaktów MLflow — to celowy zapis do odtwarzania eksperymentów.

Ewaluacja prawdziwego modelu, bez poruszania robotem (kokpit musi działać):

```bash
cd ~/Desktop/roboinspect-ai
.venv/bin/python scripts/evaluate_bielik.py
```

Raport: `artifacts/bielik-evaluation.json`. `expected_match` w MLflow porównuje
intencję i kolejność celów z etykietą. To osobna metryka od poprawności JSON.
Testy aplikacji używają kontrolowanego planera, więc nie wymagają pobierania wag
w CI; test rzeczywistego modelu jest oddzielny i zapisuje również błędne przypadki.

```bash
bash scripts/test_project.sh -q
```

Diagnostyka: `artifacts/cockpit/ollama.log`, `mlflow.log`, `operator.log`.
Sprawdzenie inferencji GPU:

```bash
OLLAMA_HOST=127.0.0.1:11435 data/ollama-runtime/bin/ollama ps
nvidia-smi
```

Mikrofon/Whisper, RAG, YOLO/SAM i dostrajanie nie należą do tej implementacji.

Źródła: https://huggingface.co/speakleash/Bielik-4.5B-v3.0-Instruct-GGUF,
https://huggingface.co/second-state/Bielik-4.5B-v3.0-Instruct-GGUF,
https://docs.ollama.com/capabilities/structured-outputs,
https://mlflow.org/docs/latest/ml/tracking/tracking-api .

Po gotowości Nav2 można uruchomić także pełny test **z fizycznym ruchem w symulacji**:

```bash
.venv/bin/python scripts/check_chat.py
```

Wysyła on przez czat misję A → BASE, sprawdza idempotencję, czeka na rzeczywisty
wynik Nav2 oraz sprawdza powiązanie eksperymentu MLflow. Raporty odbioru:
[bielik-results.md](bielik-results.md).

## Powitanie i nowa rozmowa

Czat pokazuje własne powitanie: „Cześć! Podaj mi misję do wykonania albo zapytaj
 o działanie systemu…”. Wcześniejsze rozmowy demonstracyjne odłożono do archiwum.
Nowe wiadomości nadal pozostają po odświeżeniu i restarcie. Przycisk **Nowa rozmowa**
odkłada bieżące wiadomości do archiwum, bez usuwania danych, misji i eksperymentów.
Nie przerywa przejazdu. Jest zablokowany podczas oczekiwania na odpowiedź modelu.
Archiwum jest dostępne przez GET `/api/chat?include_archived=true` (z paginacją
`before`/`limit`). POST `/api/chat/new` wymaga Idempotency-Key i JSON `{}`.

Opis bieżącej implementacji dla Bielika znajduje się w `config/assistant-knowledge.md`.
Można pytać np. „Jak działa system?”, „Co robi SLAM?” lub „Jak sprawdzić MLflow?”.
Pytania instruktażowe o wysłanie robota mają wymuszony tryb odpowiedzi opisowej;
nie są traktowane jak polecenia jazdy. To opis w prompcie, a nie pełny RAG.
Powitanie jest elementem interfejsu i nie tworzy sztucznego eksperymentu MLflow.

Aktualna obsługa Enter, zatrzymania i zakresu odpowiedzi: [chat-controls.md](chat-controls.md).
