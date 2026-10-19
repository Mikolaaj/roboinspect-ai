# Panel operatora

Start: `bash scripts/run_cockpit.sh`. Komenda otwiera kokpit i sterowanie w dwóch kartach domyślnej przeglądarki. Opcja `--no-browser` nie otwiera kart.

Stop: Ctrl+C w terminalu uruchomienia lub `bash scripts/stop_cockpit.sh`. Poczekaj na zakończenie przed ponownym startem.

Interfejs używa lokalnych SVG Phosphor, systemowego fontu i bezpośredniego HTML/CSS/JS. Nie wymaga CDN. Sektory mają litery w okręgach. Na telefonie pasek Sterowanie / Czat przewija do właściwej sekcji. Historia, SLAM, misje i rozmowy zachowują dotychczasowe działanie.

Nieaktywna karta ogranicza pobieranie statusu, historii i czatu oraz wyłącza strumienie kamer. Kamery poza widocznym obszarem także zwalniają połączenie. Te zmiany dotyczą wyłącznie przeglądarki: nawigacja i obsługa STOP pozostają po stronie serwera.

## Kolejne etapy

1. Głos: lokalny Whisper, mikrofon i ten sam walidowany wykonawca misji.
2. RAG: odpowiedzi o obsłudze oparte na dokumentacji i źródłach.
3. Obraz: dane i EDA, YOLO, segmentacja SAM, ocena jakości oraz MLflow.
4. Inspekcje: rozpoznawanie usterek, dowody z kamer i raport misji.
5. Stabilność: budżet VRAM, ewaluacje, testy integracji i obsługa awarii.
6. Wdrożenie: Docker Compose, Kubernetes, CD i instrukcja na drugim komputerze.

## Historie w panelach

Kokpit i panel sterowania mają rozwijaną historię detekcji, a bezpośrednio pod nią historię przejazdów i mapowania. Każda historia przewija się we własnym obszarze o ograniczonej wysokości, również na telefonie. W kokpicie bieżący stan robota znajduje się nad historiami. Formularz „Zaplanuj misję” usunięto z panelu; misje nadal można zlecać przyciskami i czatem.

Przycisk „MLflow” w nagłówku panelu sterowania otwiera lokalny panel eksperymentów (http://127.0.0.1:5001/) w nowej karcie. MLflow uruchamia się razem z kokpitem.
