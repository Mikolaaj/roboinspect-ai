# Pierwszy test Gazebo

To przykład z zainstalowanego pakietu ros_gz_sim_demos, nie docelowy hangar RoboInspect. Nie kopiuje plików świata do repo ani nie wymaga Nav2. Celem jest sprawdzenie grafiki i komunikacji ROS/Gazebo przed budową własnego świata.

## Uruchomienie

W terminalu graficznej sesji użytkownika:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/demo_diff_drive.sh
```

Pozostaw terminal otwarty. Oczekiwany rezultat: okno Gazebo z podłożem i dwoma pojazdami, niebieskim i zielonym. RViz jest wyłączony dla prostszego testu. Symulacja uruchamia się od razu.

## Sprawdzenie ruchu

W drugim terminalu, po załadowaniu świata:

```bash
source /opt/ros/jazzy/setup.bash
ros2 topic pub --once /model/vehicle_blue/cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.2}, angular: {z: 0.0}}'
```

Niebieski pojazd powinien jechać do przodu. Pojedyncza komenda nie jest czasowo ograniczona; zatrzymaj go kolejnym poleceniem:

```bash
ros2 topic pub --once /model/vehicle_blue/cmd_vel geometry_msgs/msg/Twist '{linear: {x: 0.0}, angular: {z: 0.0}}'
```

Tematy wynikają z konfiguracji zainstalowanego diff_drive.launch.py. Ruch przez most ROS pozostaje do sprawdzenia w działającej sesji; test serwera opisany poniżej go nie weryfikuje.

## Zakończenie

W terminalu uruchomienia wciśnij Ctrl+C. Sprawdź, czy okno i procesy przykładu się zamknęły.

## Jeśli grafika nie działa

Zachowaj komunikaty terminala. Rozróżniamy uruchomienie serwera od działania renderera GUI. Na rozpoznanym komputerze nvidia-smi nie łączy się ze sterownikiem NVIDIA; sama ta informacja nie rozstrzyga, czy Gazebo może renderować przez inny dostępny układ. W tym kroku nie zmieniamy sterowników.

## Co sprawdzono 17.10.2026

- ROS 2 Jazzy i pakiety ros_gz_sim/bridge/sim-demos są obecne.
- Gazebo Sim 8.11.0 załadowało lokalny świat diff_drive.sdf i zakończyło 100 kroków bez GUI z kodem 0.
- Log potwierdził inicjalizację świata i obu systemów DiffDrive.
- W ograniczonym środowisku narzędzia wystąpił błąd getifaddrs; ten sam test z dostępem do interfejsów sieciowych zakończył się poprawnie.
- Wyświetlanie GUI i ruch przez most ROS nie zostały jeszcze potwierdzone.
- Nav2 nie jest zainstalowane; to osobny krok po potwierdzeniu działania przykładu.
