# Faza 3 — robot, sensory i ręczne sterowanie

## Zakres tej części

Do scenariuszy normal, blocked i unreachable dodano własny prosty robot różnicowy: dwa koła napędowe, podpory, niebieski korpus, maszt kamery i lidar. Robot startuje na polu BASE i jest skierowany wzdłuż osi +X świata. Kamera RGB ma 320 x 240 i 10 Hz, lidar 360 próbek i nominalnie 10 Hz, odometria 30 Hz. Rzeczywiste częstotliwości zależą od szybkości symulacji i renderowania.

Ten dokument opisuje ręczną diagnostykę sensorów i napędu. Dostępne są już Nav2, lokalizacja AMCL oraz kokpit z trzema kamerami i przyciskami — zobacz [cockpit.md](cockpit.md). Ręczne komendy nie omijają przeszkód; nie używaj ich podczas jazdy Nav2.

## 1. Uruchomienie

Zatrzymaj poprzedni hangar przez Ctrl+C i zamknij stare okno Gazebo. Opuść venv innego projektu, jeśli jest aktywny.

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_robot.sh
```

Powinien pojawić się dotychczasowy hangar z małym niebieskim robotem na turkusowym polu BASE. Kamera edytora nadal pokazuje hangar ukośnie z góry. Zbliż widok, jeśli robot jest niewielki.

Wariant z przeszkodą (po zatrzymaniu poprzedniej instancji):

```bash
bash scripts/run_robot.sh scenario:=blocked
```

## 2. Sprawdzenie sensorów

W drugim terminalu:

```bash
cd ~/Desktop/roboinspect-ai
source /opt/ros/jazzy/setup.bash
/usr/bin/python3 scripts/robot_status.py
```

Wynik powinien mieć `missing: []`, zawierać image/odom/scan, rozmiar obrazu 320 x 240 i 360 próbek lidaru. Odometria zaczyna się w lokalnym układzie odom, blisko [0, 0]; nie jest to światowa pozycja [-11, -7]. Samo run_robot.sh publikuje odom -> base_link; launch nawigacji dodaje ramki sensorów, a AMCL map -> odom.

Lidar zaczyna pomiar od 0.35 m, aby wyciąć geometrię własnego masztu. Oznacza to martwą strefę blisko robota; konfiguracja nawigacji uwzględnia promień robota 0.37 m i położenie sensora.

## 3. Krótki przejazd i skręt

W tym samym drugim terminalu:

```bash
/usr/bin/python3 scripts/robot_control.py forward
/usr/bin/python3 scripts/robot_control.py left
/usr/bin/python3 scripts/robot_control.py back
/usr/bin/python3 scripts/robot_control.py stop
```

Wykonuj polecenia pojedynczo, obserwując robota. Każda komenda trwa domyślnie sekundę, po czym program wysyła serię zerowych prędkości. Domyślna prędkość liniowa to 0.2 m/s, a skrętu 0.4 rad/s. Dostępne również `right`, `forward_left` i `--seconds`, ograniczone do maksymalnie 5 s. Ctrl+C podczas działania klienta również próbuje wysłać zatrzymanie. Nie jest to jeszcze niezależny watchdog na wypadek zabicia procesu lub utraty połączenia; surowa komenda cmd_vel może pozostać aktywna.

Przykład krótszego ruchu:

```bash
/usr/bin/python3 scripts/robot_control.py forward --seconds 0.5
```

Nie uruchamiaj jednocześnie dwóch klientów sterowania. To ręczne sterowanie prędkością, a nie zadawanie współrzędnych ani autonomiczna inspekcja.

Łagodny łuk do przodu w lewo przez 4 sekundy, a następnie zatrzymanie (0.2 m/s i 0.15 rad/s):

```bash
/usr/bin/python3 scripts/robot_control.py forward_left --seconds 4
```

Czas dotyczy wysyłania komendy według zegara komputera. Przy wolnym renderowaniu czas i droga ruchu w symulacji mogą być krótsze; połączenie ROS jest zestawiane przed rozpoczęciem odliczania.

## 4. Obraz z kamery

W kolejnym terminalu:

```bash
source /opt/ros/jazzy/setup.bash
ros2 run rqt_image_view rqt_image_view
```

W aplikacji wybierz `/roboinspect/camera/image`. To podgląd do sprawdzenia sensora przed wspólnym dashboardem. Odśwież listę tematów, jeśli uruchomiono go przed symulacją.

Alternatywnie zapisz jedną klatkę bez aplikacji graficznej:

```bash
cd ~/Desktop/roboinspect-ai
source /opt/ros/jazzy/setup.bash
/usr/bin/python3 scripts/robot_status.py --image artifacts/robot-camera.png
```

## Renderowanie na tym komputerze

Test sensorów z Ogre2 kończył się błędem EGL/Mesa i segfaultem. Sprawdzony wariant sensorów używa `ogre` i programowego renderowania Mesa llvmpipe. Skrypt ustawia te zmienne tylko dla uruchamianych procesów; nie instaluje ani nie zmienia sterownika systemowego. Przy starcie z oknem ten sam silnik jest wskazywany także dla widoku edytora; GUI użytkownik sprawdza osobno.

Ogre2 można wybrać parametrem `render_engine:=ogre2`, ale na tej konfiguracji test ten nie przeszedł. Wyłączenie domyślnego wymuszenia programowego renderowania jest możliwe przez `ROBOINSPECT_SOFTWARE_RENDERING=0`; przyspieszenie GPU nie zostało potwierdzone. Software rendering może obniżać płynność.

`headless:=true` uruchamia sam serwer i most ROS, bez GUI. Do sprawdzonego renderowania sensorów nadal potrzebny jest dostępny lokalny ekran; nie jest to potwierdzone wdrożenie na serwerze bez DISPLAY.

Źródło techniczne opcji silnika sensorów i nadpisania z CLI: https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/systems/sensors/Sensors.cc

## Test integracyjny

Test tworzy osobną domenę ROS i partycję Gazebo, sprawdza rzeczywiste wiadomości z sensorów, wykonuje krótki przejazd, sprawdza odometrię i zatrzymanie, a następnie zamyka swoje procesy:

```bash
cd ~/Desktop/roboinspect-ai
source /opt/ros/jazzy/setup.bash
/usr/bin/python3 scripts/check_robot_sim.py
```

Wymaga lokalnej komunikacji ROS/Gazebo oraz działającego renderowania. Wyniki, log i kamera są w `artifacts/robot-smoke/`, ignorowanym przez Git. Sukces oznacza `passed: true` i kod wyjścia 0. Test nie uruchamia autonomicznej nawigacji ani nie sprawdza wszystkich przeszkód.

`passed` dotyczy odczytu sensorów, przejazdu i zatrzymania. Zamykanie jest raportowane oddzielnie: na tym komputerze Gazebo/Ogre nie zawsze kończy się po SIGINT i ROS launch po 5 s wysyła SIGTERM. Procesy testowe są sprzątane, lecz bezbłędne zamykanie renderera pozostaje do dopracowania. Pola `shutdown_needed_sigterm` i `shutdown_segfault` oraz log pozwalają odróżnić tę sytuację od awarii podczas działania.

Sprawdzony wynik ruchu: około 0.30 m po komendzie 1.5 s, prędkość po zatrzymaniu 0 i brak zmiany pozycji w kolejnym odczycie. Odczytano klatkę RGB i 360 pomiarów lidaru. Obraz kamery obejrzano; widoczne jest wyposażenie hangaru. Użytkownik potwierdził działanie GUI, ręcznego sterowania i kamery.

## Pliki źródłowe

- `simulation/models/roboinspect/model.sdf` — model, napęd i sensory.
- `config/robot_bridge.yaml` — jednokierunkowe mosty ROS/Gazebo.
- `robotics/launch/hangar_robot.launch.py` — uruchamianie świata i mostu.
- `scripts/run_robot.sh` — wejście dla użytkownika.
- `scripts/build_hangar.py` — generuje również światy z robotem; po zmianie modelu uruchom ponownie `/usr/bin/python3 scripts/build_hangar.py`.

Mapy, TF, AMCL, Nav2 i nazwane cele są opisane w [navigation.md](navigation.md). Zalecany start całego stosu i trzech kamer: [cockpit.md](cockpit.md).
