# RoboInspect AI

Robot inspekcyjny w hangarze Gazebo, sterowany tekstem przez lokalnego Bielika, z walidacją Pydantic, nawigacją Nav2/SLAM i eksperymentami MLflow. Głos i percepcja wizyjna są w planie.

## Status

Działają: hangar A/B/C, robot z kamerą i lidarem, trzy widoki, Nav2/AMCL,
mapowanie SLAM z panelu, FastAPI, kontrakty Pydantic, trwałe misje i historia SQLite.
Panel ma czat z lokalnym Bielikiem 4.5B Q4_K_M oraz zapisywaną rozmowę;
MLflow rejestruje interpretacje i eksperymenty. Gotowe modele nie są jeszcze
własnym treningiem. Mikrofon, RAG, YOLO/SAM oraz Docker/Kubernetes to dalsze etapy.
Instrukcje: [API i misje](docs/missions.md), [czat i MLflow](docs/bielik-chat.md).

## Docelowe działanie

Operator wydaje polecenie „Sprawdź panele w sektorze B i wróć do bazy”. Gotowy LLM tworzy walidowany plan, wykonawca zleca nawigację, a własny model analizuje obraz. Wyniki trafiają do raportu. Głos jest przetwarzany przez gotowy model STT.

Planowana percepcja: YOLO do detekcji + SAM do masek obiektów, z własnym modelem oceny defektów. Modele nie są jeszcze wdrożone; [założenia](docs/perception-plan.md).

Kokpit ma trzy kamery: robota, widok podążający i monitoring z góry. W panelu sterowania dotychczasowe funkcje są po lewej, a zapisywany czat po prawej. Mikrofon dojdzie później.

## Uruchomienie kokpitu

Jednorazowo po pobraniu repo: `bash scripts/setup_project.sh`, a następnie `bash scripts/setup_bielik.sh` i `bash scripts/setup_whisper.sh`.

Zatrzymanie poprzedniej sesji: `bash scripts/stop_cockpit.sh`.

Jedna komenda uruchamia cały stos i otwiera dwie karty: kokpit oraz sterowanie z czatem.

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_cockpit.sh
```

Dodatkowy terminal nie jest potrzebny. `bash scripts/run_control_panel.sh` pozostaje skrótem do ponownego otwarcia samego panelu.

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

Zaliczono próby normal (A → B → P3 → C → BASE), blocked (B → C → BASE) oraz unreachable (oczekiwany błąd B). Sprawdzono trzy kamery, anulowanie w ruchu, zatrzymanie i ponowny start. Wyniki i granice odbioru: [docs/phase3-results.md](docs/phase3-results.md). API, trwałe misje, SLAM i czat są już wdrożone. Najnowszy odbiór: [Bielik i MLflow](docs/bielik-results.md). Głos i inspekcja zdjęć są opisane poniżej.

## Dokumentacja i odtwarzalność

Instrukcja instalacji, konfiguracji, uruchamiania, treningu i wdrożenia będzie rozwijana razem z implementacją. Każda faza musi mieć sprawdzony rezultat. Pełny odbiór obejmuje uruchomienie na czystym środowisku według instrukcji.

## Dane i sekrety

Klucze API przechowujemy poza Git. Duże dane, wagi modeli, nagrania i lokalne logi nie są commitowane. Konfiguracja przykładowa będzie dodana wraz z pierwszą usługą.

## SLAM · mapa i robot w panelu

Uruchomienie wymaga jednej komendy: `bash scripts/run_cockpit.sh`. W panelu pod A/B/C/BASE są przyciski:
rozpocznij mapowanie, zapisz mapę, resetuj mapę i zakończ mapowanie.
Na mapie widać kropkę robota. Operacje i ich postęp trafiają do wspólnej
historii z misjami, a wybrana mapa jest pamiętana po restarcie.

Zatrzymanie całości: `bash scripts/stop_cockpit.sh`.
Pełna instrukcja i narzędzia diagnostyczne: [docs/slam.md](docs/slam.md).

## Lokalny czat Bielik i eksperymenty MLflow

Panel sterowania ma czat po prawej stronie. Otwarcie lub odświeżenie panelu rozpoczyna świeżą rozmowę, archiwizując wcześniejsze wpisy. Bielik 4.5B Q4_K_M
interpretuje tekst, Pydantic waliduje dozwolone cele, a istniejący wykonawca misji
przekazuje je do Nav2. MLflow zapisuje konfigurację, interpretacje i wyniki pomiarów.
Przygotowanie modelu, dwie komendy uruchomienia i testy opisano w [instrukcji czatu](docs/bielik-chat.md).

Czat zaczyna się powitaniem; „Nowa rozmowa” archiwizuje dotychczasowe wiadomości.
Wyjaśnienia mają osobny tor i publiczną instrukcję operatora w `src/roboinspect/operator_policy.py`.
Enter wysyła wiadomość, Shift+Enter dodaje linię, a STOP zatrzymuje analizę i ruch robota.
Szczegóły: [sterowanie czatem i ograniczenia](docs/chat-controls.md).

## Mikrofon i czerwone strefy

Panel obsługuje lokalny Whisper: nagraj, sprawdź rozpoznany tekst i wyślij. Cele A/B/C to teraz po jednej czerwonej strefie przed tablicami. [Instrukcja głosu i stref](docs/voice-and-inspection-zones.md).

## Mapa 2D i aktualna trasa

Kokpit pokazuje schemat całego hangaru obok mapy SLAM, pozycję robota i aktualny plan Nav2. Ta sama półprzezroczysta żółta linia jest widoczna w świecie Gazebo i kamerach. [Obsługa i test nagłej przeszkody](docs/navigation-route-view.md).

## Ustawienie magazynu

Pod mapowaniem są przyciski przywrócenia standardowego wyposażenia, usunięcia przeszkód i losowania układu z zachowaniem przejść. Zmiana odświeża świat i mapę, ustawia robota w BASE i trafia do historii. [Instrukcja i wyniki](docs/warehouse-controls.md).

## Inspekcja zdjęć YOLO

Kamera FPV ma 1280×720. Banery P1 do P5 wyświetlają fotografie z lokalnego zestawu COCO128. W sterowaniu są przyciski inspekcji sektorów oraz zmiany zdjęć. Robot odwiedza każdą tablicę i wraca na czerwone pole. Kokpit pokazuje detekcję YOLO11s na RTX i trwałą historię klatek, a czat odpowiada na pytania o zapisane wyniki. [Instalacja, obsługa i ograniczenia](docs/vision-inspection.md), [pochodzenie modeli i zdjęć](docs/third-party/vision.md).
