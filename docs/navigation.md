# Faza 3 — nawigacja do nazwanych celów

Zalecany start całego stosu: `bash scripts/run_cockpit.sh`. Panel przycisków:
`bash scripts/run_control_panel.sh`. Szczegóły w [cockpit.md](cockpit.md).
Poniższe uruchomienie w osobnych terminalach służy diagnostyce; nie łącz go
z działającym kokpitem.

Nav2 Jazzy jest zainstalowane. Stos obejmuje map server, AMCL, Navfn,
Regulated Pure Pursuit, costmapy, zachowania awaryjne i lifecycle manager.
Konfiguracja: `config/nav2.yaml`, cele: `config/navigation-goals.json`.

## Uruchomienie

Zatrzymaj poprzednią symulację i ręczne sterowanie przez Ctrl+C.
Lokalizacja początkowa zakłada świeży start robota w BASE [-11, -7, 0].
Nie resetuj samego świata podczas działania Nav2; po resecie uruchom oba procesy ponownie.

Terminal 1:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_robot.sh
```

Terminal 2 (po pojawieniu się robota):

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_navigation.sh
```

Poczekaj na `Managed nodes are active`. Terminal 3:

```bash
cd ~/Desktop/roboinspect-ai
source /opt/ros/jazzy/setup.bash
/usr/bin/python3 scripts/go_to.py A
```

Po zakończeniu przejazdu możesz zlecić powrót:

```bash
/usr/bin/python3 scripts/go_to.py BASE
```

Dostępne nazwy: BASE, A, B, C, P1–P5. `Nav2 status: 4` oznacza sukces.
Ctrl+C w kliencie wysyła żądanie anulowania; limit czasu domyślnie 180 s
również anuluje przejazd. Nie uruchamiaj równocześnie ręcznego sterowania
ani dwóch klientów celów. Jest to sterowanie symulacją, bez certyfikowanego
zatrzymania awaryjnego i bez niezależnego watchdogu napędu.

Kamera nadal działa w `ros2 run rqt_image_view rqt_image_view`, temat
`/roboinspect/camera/image`. To etap nawigacji; panel z trzema widokami,
czat, LLM i głos będą dodane osobno.

## Mapy i ramki

Mapy 640×480, 0.05 m/piksel, początek [-16, -12, 0] powstały z rzutu
statycznych kolizji świata, bez SLAM. AMCL dopasowuje lidar do mapy i
publikuje map -> odom. Most Gazebo dostarcza odom -> base_link;
launch nawigacji dodaje nieruchome ramki sensorów. Regał jest na mapie
zachowawczo wypełnionym obrysem, więc skan może różnić się od rzutu.

Odtwarzanie map:

```bash
/usr/bin/python3 scripts/build_hangar.py
/usr/bin/python3 scripts/build_navigation_maps.py
```

Wariant z blokadą wymaga `scenario:=blocked` w OBU komendach startowych.
Sama osiągalność dziewięciu celów na siatce nie potwierdza wszystkich
przejazdów. Testuj kolejne trasy w symulacji, obserwując ruch i przeszkody.

Instalacja na innym Ubuntu 24.04 z ROS Jazzy:

```bash
sudo apt update
sudo apt install ros-jazzy-navigation2 ros-jazzy-nav2-bringup
```

## Test integracyjny

```bash
source /opt/ros/jazzy/setup.bash
/usr/bin/python3 scripts/check_navigation.py
```

Test uruchamia własny serwer symulacji i Nav2 z odrębnymi ROS_DOMAIN_ID
oraz GZ_PARTITION. Sprawdza rzeczywiste sensory, sukces akcji do A,
pozycję z Gazebo (maksymalnie 0.40 m od celu) i zatrzymanie. Wymaga dostępu do
wyświetlacza do renderowania sensorów także w trybie bez okna. Wynik i logi
zapisuje w `artifacts/navigation-check/`. Błąd odometrii jest zapisywany diagnostycznie, ponieważ poślizg podczas skrętów
może powodować rozbieżność z pozycją świata. Ten test nie zastępuje prób
wszystkich tras, przeszkód i anulowania.

Sprawdzenie 17.10.2026: wariant normal, BASE -> A, Nav2 status 4,
końcowa pozycja świata [-8.814, -0.987] przy celu [-9, -1], błąd 0.187 m,
końcowe prędkości liniowa i kątowa 0. Sensory pozostały dostępne.
Odometria rozminęła się z oczekiwaną pozycją o 0.942 m; lokalizacja AMCL
korygowała tę rozbieżność. Późniejsze testy obejmują A/B/P3/C/BASE, wariant blocked i anulowanie.
Aktualny wynik odbioru: [phase3-results.md](phase3-results.md).
