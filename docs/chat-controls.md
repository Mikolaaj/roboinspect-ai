# Czat operatora: Enter, zatrzymanie i zakres odpowiedzi

## Obsługa

- **Enter** wysyła wiadomość. **Shift+Enter** dodaje nową linię. Wprowadzanie tekstu
  z aktywnym IME nie jest traktowane jako potwierdzenie wysłania.
- Podczas oczekiwania widoczne są obracające kółko i **Zatrzymaj odpowiedź**.
  Po walidacji pojawia się pełny tekst. Nie pokazujemy częściowego planu przed walidacją.
- **Zatrzymaj odpowiedź** anuluje konkretną oczekującą wiadomość i zamyka jej zapytanie
  HTTP do modelu. Spóźniona odpowiedź nie może wysłać misji. Przycisk nie wycofuje
  misji, która została już wcześniej przyjęta; wtedy użyj STOP lub anulowania jazdy.
- **STOP** w czacie (również literówka SOTP) działa bez czekania na Bielika. Anuluje
  oczekujące odpowiedzi, aktywną misję i operacje mapowania, wysyła zerową prędkość
  i uruchamia potwierdzenie zatrzymania. Kokpit, kamery i API pozostają dostępne.
  Nie jest to komenda wyłączenia aplikacji.
- STOP można wysłać Enterem również podczas analizy innej wiadomości.
- Rozmowy i anulowania pozostają zapisane. Nowa rozmowa archiwizuje wcześniejsze wpisy.

## Dwa tory

Polecenia ruchu są interpretowane do zamkniętego schematu Pydantic i przekazywane
wyłącznie do MissionService/Nav2. Niejednoznaczne cele i pytania nie tworzą misji.
Pytania o obsługę mają oddzielne generowanie odpowiedzi z publicznej instrukcji
operatora (`operator_policy.py`). Ten tor nie ma dostępu do wykonawcy misji.

Słaba odpowiedź, np. sam tytuł „Opis systemu…”, albo treść spoza zakresu jest zastępowana
sprawdzoną instrukcją operatora. MLflow zapisuje wówczas `operator_guide_fallback=1`.
To jawny mechanizm awaryjny opisu, a nie alternatywny parser sterujący ruchem.

## Ochrona zakresu

Model odpowiada o obsłudze: celach, kamerach, mapowaniu, nawigacji i przeglądaniu wyników.
W torze wyjaśnień nie dostaje konfiguracji, danych uwierzytelniających, ścieżek hosta,
źródeł ani poleceń instalacji/modyfikacji. Nie ma narzędzi odczytu plików lub terminala.
Rozpoznawane próby zmiany zasad, wydobycia instrukcji i konfiguracji dostają stałą odmowę.
Wyjście odpowiedzi opisowych podlega dodatkowej kontroli zakresu i jakości.

To ograniczenie asystenta operatora, nie mechanizm autoryzacji całego lokalnego API.
Filtry tekstowe nie stanowią dowodu odporności na każdy możliwy prompt injection;
główną granicą jest brak prywatnych danych i uprawnień wykonawczych w torze wyjaśnień
oraz niezależne bramki przed ruchem. Nie twierdzimy, że model jest nieomylny.

## Wyścigi i trwałość

Anulowanie i wysłanie misji używają tej samej blokady wykonawcy. Stan canceled jest
zapisywany przed zwróceniem potwierdzenia, a późna odpowiedź nie może go nadpisać.
Anulowane połączenie z Ollama jest zamykane; załadowane wagi mogą nadal pozostać
w pamięci do końca okresu bezczynności.

STOP zwiększa trwały `control_epoch`. Panel dołącza odczytaną wartość do nowych żądań,
więc opóźnione polecenie sprzed STOP jest odrzucane. Idempotency-Key zapobiega
powieleniu STOP; ponowienie starego żądania nie zatrzymuje nowej misji. Klienci API
powinni również przesyłać `control_epoch`; starsi klienci bez tego pola nie korzystają
z tej dodatkowej ochrony kolejności żądań.

STOP jest zapisywany w rozmowie od razu, a pomiar MLflow trafia do kolejki poza
krytyczną ścieżką zatrzymania (`stop_fast_path=1`). Awaria pomiarów nie blokuje STOP.
Po restarcie nie odtwarzamy poleceń ruchu.

## Sprawdzenie samodzielne

Zatrzymanie i start:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/stop_cockpit.sh && bash scripts/run_cockpit.sh
```

Terminal 2:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_control_panel.sh
```

Odśwież panel Ctrl+Shift+R. Wypróbuj „Opisz mi cały system”, Enter, Shift+Enter,
przycisk zatrzymania odpowiedzi i STOP podczas jazdy.

Test aplikacji: `bash scripts/test_project.sh -q`.
Test z fizycznym ruchem w symulacji (gotowy, bezczynny Nav2):
`.venv/bin/python scripts/check_chat_controls.py`.

Wynik próby rzeczywistej: [chat-controls.json](verification/chat-controls.json).

## Nowa rozmowa przy otwarciu panelu

Każde otwarcie lub odświeżenie panelu sterowania archiwizuje dotychczasową widoczną rozmowę i pokazuje powitanie. Oczekująca odpowiedź jest anulowana przed archiwizacją, więc nie wysyła później polecenia ruchu. Przyjęte misje pozostają aktywne. Powtórzenie żądania inicjalizacji tej samej strony nie archiwizuje jej nowych wiadomości.
