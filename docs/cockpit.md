# Kokpit i panel sterowania — faza 3

## Dwie komendy

Zatrzymaj poprzednie ręczne uruchomienia Gazebo/Nav2 i `robot_control.py`.
Nie uruchamiaj ich obok kokpitu — pierwsza komenda uruchamia już cały stos.

Terminal 1:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_cockpit.sh
```

Otworzy się przeglądarka z `http://127.0.0.1:8765/` i trzema obrazami:

1. FPV — przednia kamera robota, 320×240, zadane 10 FPS czasu symulacji.
2. Kamera z boku/za robotem — 640×360, zadane 5 FPS. Jej pozycja jest
   związana z robotem; kamera podąża za jego ruchem i skrętem.
3. Monitoring — nieruchoma kamera na wysokości 23 m, 640×480, zadane 4 FPS.
   Obejmuje całą halę, z północą u góry.

To obrazy renderowane przez Gazebo, nie schematy ani zrzuty ekranu edytora.
Gazebo działa domyślnie bez okna edytora; jego fizyka i sensory pracują normalnie.
Poczekaj na trzy oznaczenia „NA ŻYWO” i zielony status Nav2. Przy uruchamianiu
lokalizacja może potrzebować kilkunastu sekund. Zatrzymana symulacja oznacza
brak gotowości, nawet jeśli proces Nav2 nadal istnieje.

Terminal 2:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_control_panel.sh
```

Druga komenda otwiera `/control` na tym samym serwerze. Nie uruchamia drugiego
robota, Nav2 ani backendu. Możesz też kliknąć „Panel sterowania” w kokpicie.
Przeglądarka systemowa może otworzyć panel w karcie; można przenieść ją na drugi
monitor. Jeśli automatyczne otwarcie nie działa, otwórz adres podany w terminalu.

## Sprawdzenie ręczne

1. Wybierz A. Przyciski innych celów zostaną zablokowane na czas przejazdu.
2. Obserwuj ruch równocześnie w trzech widokach. Kamera boczna ma trzymać
   robota w kadrze; kamera górna pozostaje nieruchoma.
3. Po stanie „Dotarł do celu” wybierz B, następnie C i Powrót do bazy.
4. Wyślij kolejny cel i w trakcie rzeczywistego ruchu kliknij „Anuluj przejazd”.
   Poczekaj na „Anulowano” i zerową prędkość.
5. Ctrl+C **w terminalu 1** zamyka backend, Nav2 i symulację. Samo zamknięcie
   kart przeglądarki nie kończy przejazdu. Alternatywnie w dowolnym terminalu
   użyj `bash scripts/stop_cockpit.sh`, również gdy kokpit uruchomiono w tle. Ponowne uruchomienie pierwszej komendy
   rozpoczyna nową sesję od bazy.

Domyślna tolerancja Nav2 wynosi 0.10 m położenia i 0.15 rad orientacji
w estymacji lokalizacji. Testy osobno sprawdzają rzeczywistą pozycję Gazebo;
tolerancja estymacji nie oznacza gwarantowanej dokładności fizycznej.

Anulowanie korzysta z akcji Nav2. Nie jest niezależnym zatrzymaniem awaryjnym
sprzętu. Nie steruj jednocześnie z `go_to.py`, `robot_control.py` ani innego
klienta ROS. Jeden backend odrzuca drugi cel w czasie aktywnego zadania.

## Warianty hali

Po Ctrl+C i zakończeniu poprzedniej sesji:

```bash
bash scripts/run_cockpit.sh --scenario blocked
```

Czerwona przeszkoda zamyka część przejścia B/C. Sprawdź B → C → BASE.
Uruchamianie dobiera zgodny świat i mapę jednym argumentem.

Scenariusz braku trasy:

```bash
bash scripts/run_cockpit.sh --scenario unreachable
```

B jest otoczone zamkniętymi ścianami. Przycisk B ma ostatecznie zwrócić błąd
przejazdu, a nie sukces. Nav2 może wcześniej wykonywać próby odzyskania trasy.
Można je przerwać przyciskiem anulowania. To osobny, odtwarzalny test;
nie zmienia standardowej hali.

Dodatkowe opcje:

```bash
bash scripts/run_cockpit.sh --no-browser
bash scripts/run_cockpit.sh --gazebo-gui
bash scripts/run_cockpit.sh --port 8770
```

Panel sterowania automatycznie odczytuje port aktywnego kokpitu. Opcja
`--gazebo-gui` dodatkowo otwiera edytor Gazebo i zwiększa obciążenie renderowania.
Domyślnie tryb auto wybiera NVIDIA RTX przy działającym sterowniku;
`--rendering cpu` wybiera Ogre + Mesa llvmpipe;
trzy kamery zwiększają obciążenie renderowania. Szczegóły: [gpu.md](gpu.md). Zadane FPS dotyczą czasu symulacji,
więc spowolnienie fizyki obniży liczbę klatek na sekundę zegarową.

## Instalacja na Ubuntu 24.04

Pełna instrukcja nowego systemu, klonowania i startu: [install-and-run.md](install-and-run.md).
Najpierw skonfiguruj ROS 2 Jazzy według tej instrukcji. Zależności
tego etapu (na obecnym komputerze dostępne):

```bash
sudo apt update
sudo apt install ros-jazzy-navigation2 ros-jazzy-nav2-bringup \
  ros-jazzy-ros-gz ros-jazzy-tf2-ros python3-pil
```

Skrypty używają `/usr/bin/python3` 3.12 z ROS Jazzy. Nie korzystają z pyenv 3.14
ani środowiska `.venv` innego projektu. Nie trzeba instalować Node/npm ani
bibliotek frontendowych. Pliki świata i mapy są wersjonowane. Po zmianie geometrii:

```bash
/usr/bin/python3 scripts/build_hangar.py
/usr/bin/python3 scripts/build_navigation_maps.py
```

Potem uruchom kokpit ponownie i powtórz testy.

## Architektura

Gazebo Sensors → ros_gz_bridge → tematy ROS Image → `operator/server.py`
(Pillow koduje JPEG) → trzy strumienie MJPEG HTTP → lokalna przeglądarka.
Zapamiętywana jest najnowsza klatka, bez kolejki zaległych obrazów. Każda kamera
ma niezależny strumień; status podaje wiek ostatniej odebranej klatki.
Brak klatek lub utrata HTTP powodują widoczny komunikat o braku obrazu.

Przyciski → lokalne JSON API → kolejka poleceń → pojedynczy executor rclpy →
NavigateToPose → Nav2 → `/roboinspect/cmd_vel`. Wątki HTTP nie wywołują akcji
ROS bezpośrednio. Panel pokazuje feedback dystansu, pozycję AMCL, prędkość
odometrii i historię zdarzeń bieżącego procesu. Limit przejazdu wynosi 300 s
czasu zegarowego; po nim backend wysyła anulowanie.

Ten adapter HTTP jest lokalnym interfejsem etapu symulacji. Trwałe misje,
FastAPI/Pydantic, sekwencje misji i historia SQLite są już dostępne w fazie 5a: [instrukcja](missions.md). Czat i modele LLM pozostają do kolejnych faz.
Historia tutaj znika po ponownym uruchomieniu. Kamera podążająca jest sztywno
związana z robotem; dodatkowe wygładzanie i nakładka trasy to rozwinięcia
pierwotnej fazy 4, nie warunek działania tych trzech podglądów.

## Testy i diagnostyka

Pełne próby wykonują prawdziwą fizykę, akcje Nav2 i obrazy; mogą trwać kilka minut:

```bash
source /opt/ros/jazzy/setup.bash
/usr/bin/python3 scripts/check_cockpit.py --scenario normal
/usr/bin/python3 scripts/check_cockpit.py --scenario blocked
/usr/bin/python3 scripts/check_cockpit.py --scenario unreachable
```

Nie uruchamiaj ich równolegle z kokpitem — mają blokadę przed podwójnym startem.
Wszystkie trzy próby uruchomisz także przez `bash scripts/check_phase3.sh`.
Test sam uruchamia i zamyka stos, używa oddzielnych ROS_DOMAIN_ID/GZ_PARTITION,
a wyniki zapisuje w `artifacts/cockpit-check-NAZWA/result.json`. Sprawdza trzy
niepuste obrazy, odrzucanie nieprawidłowego/drugiego celu, anulowanie podczas
ruchu i zatrzymanie. Dla normal wykonuje A → B → P3 → C → BASE, dla blocked B → C → BASE,
weryfikując końcową pozycję bezpośrednio z Gazebo z tolerancją 0.50 m.
Dla unreachable oczekuje błędu B. Potrzebny jest dostęp do wyświetlacza do
renderowania sensorów nawet przy wyłączonym oknie edytora.

Logi ręcznego uruchomienia: `artifacts/cockpit/{simulation,navigation,operator}.log`.
Komunikat o zajętym porcie: zamknij poprzedni kokpit albo wybierz `--port`.
Przyciski zablokowane: sprawdź gotowość Nav2 i czy symulacja nie jest zatrzymana.
Błąd celu: zajrzyj do `navigation.log`; panel nie traktuje odrzucenia/abortu jako
udanego dojazdu. Jeśli obraz przestał się aktualizować po restarcie backendu,
odśwież kartę.


Po aktualizacji do fazy 5a uruchom raz `bash scripts/setup_project.sh`.
Panel `/control` zawiera również formularz sekwencji i trwałą historię.
