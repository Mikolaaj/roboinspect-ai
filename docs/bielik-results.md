# Bielik i czat — wynik weryfikacji 18.10.2026

Wdrożono lokalnego Bielika 4.5B v3.0 Instruct Q4_K_M przez Ollama 0.40.6,
walidację Pydantic, trwały czat po prawej stronie panelu i MLflow 3.17.1.
Czat przekazuje misje przez istniejący MissionService. Nie zastępuje Nav2,
nie udostępnia modelowi cmd_vel, współrzędnych ani terminala.

## Sprawdzenia

- `bash scripts/test_project.sh -q`: **53 testy przeszły**, Ruff check i format
  przeszły. Dwa ostrzeżenia pochodzą z zależności Starlette/httpx oraz MLflow/SQLAlchemy.
- Odtworzenie zależności z zamrożonego lockfile: `uv sync --frozen --offline` — poprawne.
- SHA256 wag zgodne z `config/bielik.json`. Inferencja przez lokalny port 11435,
  chmura Ollama wyłączona. Gazebo i model korzystają z RTX 4060 Laptop.
- Ollama `/api/ps`: size_vram **3 181 463 469 bajtów (~2.96 GiB)** dla modelu
  z kontekstem 4096. To zajętość przy tej konfiguracji, nie stałe maksimum dla innych modeli.
- Pierwsza próba promptu: **7/12** trafnych interpretacji, w tym niebezpieczne zgadywanie
  celu dla „jedź tam”. Błędów nie ukryto: [pierwszy raport](verification/bielik-evaluation-v1.json).
- Po poprawie promptu (jedna wiadomość systemowa, pełne przykłady JSON) i dodaniu kontroli
  celów wskazanych w tekście: **22/22** przypadki poprawne.
  [Raport](verification/bielik-evaluation.json). Mediana czasu lokalnej interpretacji
  w tej próbie przy działającym Gazebo: około **0.65 s**. Pierwsze zimne uruchomienie
  w początkowej próbie trwało około 43 s; nie należy oczekiwać 0.65 s przy zimnym starcie.
- Rzeczywisty przejazd z czatu „Jedź do sektora A i wróć do bazy”: **A → BASE,
  oba kroki succeeded, robot zatrzymany**, powiązany run MLflow.
  [Raport Nav2](verification/bielik-navigation.json).
- Pełne zatrzymanie i ponowne uruchomienie kokpitu: zachowane wszystkie trzy dotychczasowe
  tury rozmowy z tymi samymi identyfikatorami, treścią i potwierdzonym wynikiem misji.
  [Raport restartu](verification/bielik-restart.json).

MLflow przechowuje również nieudane próby, wersję i hash promptu, parametry modelu,
metryki oraz artefakty interakcji. Test JSON nie jest tym samym co trafność interpretacji;
`expected_match` w ewaluacji porównuje akcję i uporządkowaną listę celów ze wzorcem.
Próbki zużycia GPU dotyczą całej karty w chwili pomiaru, nie samego Gazebo ani średniego obciążenia.

- Anulowanie przez Bielika podczas rzeczywistego ruchu: **canceled**, prędkość
  liniowa i kątowa zero. [Raport anulowania](verification/bielik-cancel.json).

- Po dłuższej rozmowie finalny interpreter odpowiada na „Gdzie teraz jesteś?” rzeczywistą
  pozycją bez tworzenia dodatkowej misji. [Raport regresji kontekstu](verification/bielik-context.json).

## Zakres wyników

22 polecenia to mały test funkcjonalny, nie dowód niezawodności na dowolnych wypowiedziach.
Część przykładów występuje także w prompcie; rozszerzenie zawiera dodatkowe sformułowania.
Dodatkowo po próbie dłuższej rozmowy oddzielono trwałą historię od interpretacji
bieżącego polecenia (prompt v3): poprzednie komendy nie trafiają ponownie do modelu.
Dodatkowa kontrola odrzuca wymyślone cele, lecz nie zastępuje pełnej oceny semantyki.
Nie trenowano ani nie dostrajano wag. Mikrofon, Whisper, RAG, YOLO i SAM są następnymi etapami.

Instrukcja użytkownika: [bielik-chat.md](bielik-chat.md).

## Aktualizacja — powitanie i wyjaśnienia systemu

Czat rozpoczyna się powitaniem; wcześniejsze rozmowy demonstracyjne są archiwizowane,
a nie usuwane. Nowe rozmowy pozostają trwałe. Dodano „Nowa rozmowa” i opis bieżących
funkcji w `config/assistant-knowledge.md` (prompt v4). Pytania instruktażowe otrzymują
odpowiedź opisową; nie uruchamiają jazdy. Sprawdzono 56 testów aplikacji oraz 26/26
przypadków klasyfikacji, w tym pytania o SLAM, MLflow i wysłanie robota do sektora.
Raport: [bielik-welcome-evaluation.json](verification/bielik-welcome-evaluation.json).
Metryka dopasowania sprawdza akcję i cele, nie jest automatyczną oceną wszystkich
faktów ani poprawności językowej odpowiedzi opisowej.

## Aktualizacja — kontrola odpowiedzi i ograniczony asystent operatora

Wersja promptów v5 rozdziela planowanie misji i odpowiedzi o obsłudze. Do toru
wyjaśnień trafia wyłącznie publiczna instrukcja operatora. Dodano Enter/Shift+Enter,
trzy animowane kropki, przerwanie połączenia inferencji i osobny szybki STOP.
Słabe odpowiedzi opisowe są zastępowane instrukcją operatora, co jest oznaczane w MLflow.

Próba rzeczywista: STOP podczas jazdy i analizy został przyjęty po około 0.062 s;
potwierdzenie zerowej prędkości uzyskano po około 0.82 s. Misja i analiza anulowane,
ponowienie STOP idempotentne, żądanie ze starym control_epoch odrzucone. Robot wrócił
po próbie do BASE. To wynik tej próby, nie gwarancja czasu zatrzymania.
Raport: [chat-controls.json](verification/chat-controls.json).

W przeglądarce sprawdzono Enter, Shift+Enter, animację, przycisk zatrzymania odpowiedzi
oraz wysłanie STOP Enterem podczas analizy. Osobno sprawdzono wyścigi anulowania,
spóźnioną odpowiedź modelu, przerwanie eksportu mapy i wyścig przyjęcia misji.
Instrukcja i granice ochrony: [chat-controls.md](chat-controls.md).

Końcowa regresja tej aktualizacji: **72 testy aplikacji przeszły**, Ruff i kontrola
składni JavaScript poprawne; **26/26** przypadków klasyfikacji i wyjaśnień przeszło
na lokalnym modelu. Dwa ostrzeżenia pochodzą z zależności, nie są błędami testów.
Raport modelu: [chat-policy-evaluation.json](verification/chat-policy-evaluation.json),
sprawdzenia interfejsu: [chat-controls-ui.json](verification/chat-controls-ui.json).
