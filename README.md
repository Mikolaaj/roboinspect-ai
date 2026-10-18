# RoboInspect AI

Robot inspekcyjny w hangarze Gazebo, sterowany tekstem i głosem, z Pydantic AI, własnym modelem wizyjnym oraz procesem MLOps i CI/CD.

## Status

Projekt: działająca symulacja oraz rdzeń fazy 5 (API i misje). własny hangar A/B/C i robot z ręcznym sterowaniem, kamerą, lidarem oraz odometrią przez ROS. Dostępny jest też wariant z przeszkodą. Dostępne są Nav2 z AMCL, cele nawigacyjne, kokpit z trzema kamerami i panel przycisków. Działają FastAPI, kontrakty Pydantic, sekwencje misji i trwała historia SQLite. Agent LLM i trening pozostają do implementacji. Instrukcja: [API i misje](docs/missions.md).

## Docelowe działanie

Operator wydaje polecenie „Sprawdź panele w sektorze B i wróć do bazy”. Gotowy LLM tworzy walidowany plan, wykonawca zleca nawigację, a własny model analizuje obraz. Wyniki trafiają do raportu. Głos jest przetwarzany przez gotowy model STT.

Planowana percepcja: YOLO do detekcji + SAM do masek obiektów, z własnym modelem oceny defektów. Modele nie są jeszcze wdrożone; [założenia](docs/perception-plan.md).

Panel operatora ma trzy kolumny: kamerę robota, widok podążający za nim oraz monitoring hangaru z góry z czatem i mikrofonem poniżej.

## Uruchomienie kokpitu

Jednorazowo po pobraniu repo: `bash scripts/setup_project.sh`.

Terminal 1 — symulacja, Nav2 i trzy obrazy w przeglądarce:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_cockpit.sh
```

Terminal 2 — przyciski A/B/C/BASE i anulowanie:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_control_panel.sh
```

Domyślnie renderowanie wybiera RTX przy działającym sterowniku. Wymuszenie:
`bash scripts/run_cockpit.sh --rendering gpu`; wariant CPU: `--rendering cpu`.
Szczegóły i niezależny test GPU: [docs/gpu.md](docs/gpu.md).

Poczekaj na zielony status Nav2 i trzy obrazy. Ctrl+C w terminalu 1 zamyka cały stos.
Nie uruchamiaj równolegle starszych skryptów symulacji/nawigacji. Warianty:
`--scenario blocked` (obejście blokady), `--scenario unreachable` (B bez trasy).
Pełna instrukcja, zależności i testy: [docs/cockpit.md](docs/cockpit.md).

## Diagnostyka środowiska

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/doctor.sh
```

Skrypt tylko odczytuje stan środowiska. Nie instaluje pakietów i nie uruchamia symulatora.

- [Plan realizacji i kryteria ukończenia faz](docs/plan-faz.md)
- [Co z kursu już działa, zasoby i dalsze fazy](docs/course-coverage.md)
- [Instalacja na nowym komputerze i start](docs/install-and-run.md)
- [Stan środowiska i kolejne kroki](docs/environment.md)
- [Pierwszy test symulacji Gazebo](docs/first-simulation.md)
- [Hangar: uruchomienie, sektory i sprawdzenie świata](docs/hangar.md)
- [Robot: uruchomienie, sensory i ręczne sterowanie](docs/robot.md)
- [Nawigacja: uruchomienie Nav2 i jazda do sektorów](docs/navigation.md)
- [Kokpit: trzy kamery, przyciski, warianty hali i testy](docs/cockpit.md)

Własny świat uruchomisz poleceniem:

```bash
bash scripts/run_hangar.sh
```

Hangar z robotem i mostem ROS:

```bash
bash scripts/run_robot.sh
```

## Odbiór bieżącej fazy

Zaliczono próby normal (A → B → P3 → C → BASE), blocked (B → C → BASE) oraz unreachable (oczekiwany błąd B). Sprawdzono trzy kamery, anulowanie w ruchu, zatrzymanie i ponowny start. Wyniki i granice odbioru: [docs/phase3-results.md](docs/phase3-results.md). Następne etapy to modele Pydantic/API, trwałe misje, a następnie czat LLM i głos.

## Dokumentacja i odtwarzalność

Instrukcja instalacji, konfiguracji, uruchamiania, treningu i wdrożenia będzie rozwijana razem z implementacją. Każda faza musi mieć sprawdzony rezultat. Pełny odbiór obejmuje uruchomienie na czystym środowisku według instrukcji.

## Dane i sekrety

Klucze API przechowujemy poza Git. Duże dane, wagi modeli, nagrania i lokalne logi nie są commitowane. Konfiguracja przykładowa będzie dodana wraz z pierwszą usługą.

## SLAM — mapa i robot w panelu

Uruchamianie nadal wymaga dwóch komend: `bash scripts/run_cockpit.sh` oraz
`bash scripts/run_control_panel.sh`. W panelu pod A/B/C/BASE są przyciski:
rozpocznij mapowanie, zapisz mapę, resetuj mapę i zakończ mapowanie.
Na mapie widać kropkę robota. Operacje i ich postęp trafiają do wspólnej
historii z misjami, a wybrana mapa jest pamiętana po restarcie.

Zatrzymanie całości: `bash scripts/stop_cockpit.sh`.
Pełna instrukcja i narzędzia diagnostyczne: [docs/slam.md](docs/slam.md).
