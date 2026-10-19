# Instalacja na nowym komputerze i uruchomienie

Sprawdzany zestaw: Ubuntu 24.04, ROS 2 Jazzy, Gazebo Harmonic (Sim 8),
systemowy Python 3.12. Na obecnym komputerze ROS i zależności są już dostępne;
wystarczą dwie komendy startowe z końca tego dokumentu.

## 1. ROS 2 Jazzy na Ubuntu 24.04

Poniższe czynności dotyczą nowego systemu. Bazują na
[oficjalnej instrukcji ROS Jazzy](https://docs.ros.org/en/jazzy/Installation/Ubuntu-Install-Debs.html)
i jej [źródle](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Installation/Ubuntu-Install-Debs.rst).

Sprawdź system i locale:

```bash
cat /etc/os-release
locale
```

Wymagany jest locale UTF-8; polskie pl_PL.UTF-8 jest odpowiednie. Jeżeli system
nie ma UTF-8, skonfiguruj je zgodnie z instrukcją ROS przed kontynuowaniem.

Dodaj oficjalne repozytorium ROS. Sposób instalacji pakietu źródeł opisuje
[oficjalny plik instrukcji](https://github.com/ros2/ros2_documentation/blob/jazzy/source/Installation/_Apt-Repositories.rst).
Komendy pobierają pakiet konfiguracyjny z organizacji ros-infrastructure:

```bash
sudo apt update
sudo apt install software-properties-common curl python3 git
sudo add-apt-repository universe
```

```bash
ros_source_version=$(curl -fsSL https://api.github.com/repos/ros-infrastructure/ros-apt-source/releases/latest | python3 -c 'import json,sys; print(json.load(sys.stdin)["tag_name"])')
curl -fL -o /tmp/ros2-apt-source.deb "https://github.com/ros-infrastructure/ros-apt-source/releases/download/${ros_source_version}/ros2-apt-source_${ros_source_version}.noble_all.deb"
sudo dpkg -i /tmp/ros2-apt-source.deb
sudo apt update
sudo apt upgrade
sudo apt install ros-jazzy-desktop
```

Nie dodawaj drugiego, niezależnego repozytorium Gazebo innej wersji.
Zależności projektu pobierz przez pakiety ROS:

```bash
sudo apt install ros-jazzy-ros-gz ros-jazzy-navigation2 \
  ros-jazzy-nav2-bringup ros-jazzy-slam-toolbox ros-jazzy-tf2-ros python3-pil python3-venv
source /opt/ros/jazzy/setup.bash
ros2 pkg prefix nav2_bringup
/usr/bin/python3 -c 'import rclpy; from PIL import Image; print("Zależności OK")'
```

## 2. Repozytorium

Jeżeli repozytorium nie jest jeszcze sklonowane (SSH GitHub musi być skonfigurowane):

```bash
cd ~/Desktop
git clone git@github.com:Mikolaaj/roboinspect-ai.git
cd roboinspect-ai
```

Kod kokpitu musi być w pobieranej wersji repozytorium. Lokalne zmiany trzeba
wcześniej zapisać w commitach i wypchnąć, aby były dostępne na drugim komputerze.

## 3. Jedna komenda startowa

Najpierw zatrzymaj poprzednią sesję i poczekaj na zakończenie:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/stop_cockpit.sh
```

Następnie uruchom:

```bash
bash scripts/run_cockpit.sh
```

Komenda uruchamia Gazebo, kamery, ROS, Nav2, serwer, Bielika i MLflow. Otwiera dwie karty przeglądarki: kokpit oraz panel sterowania. `--no-browser` pomija otwieranie obu kart. Skrót `run_control_panel.sh` jest opcjonalny.

Jeśli przeglądarka nie otworzy się automatycznie, użyj adresów:

- kokpit: http://127.0.0.1:8765/
- sterowanie: http://127.0.0.1:8765/control

Nie uruchamiaj obok drugiej symulacji ani osobnego Nav2. Poczekaj na zielony
status i trzy obrazy, następnie sprawdź A → B → C → BASE oraz anulowanie w ruchu.
Ctrl+C w terminalu 1 zamyka całość. Zamknięcie karty przeglądarki nie zatrzymuje
misji. Warianty hali i diagnostyka: [cockpit.md](cockpit.md).

## 4. Weryfikacja

Zamknij kokpit przed testami:

```bash
bash scripts/check_phase3.sh
```

Wyniki zapiszą się w artifacts/. Testy wymagają aktywnej sesji graficznej także
przy wyłączonym oknie Gazebo, ponieważ obecna konfiguracja renderuje sensory
przez wyświetlacz. Tryb serwerowy bez żadnego wyświetlacza nie został zatwierdzony.

Projekt domyślnie wybiera Ogre i NVIDIA RTX, jeśli sterownik jest dostępny;
w przeciwnym razie używa programowego renderowania Mesa. Opcje: [gpu.md](gpu.md).
To sprawdzony wariant na obecnym laptopie. Inna karta/sterownik i wydajność trzech
kamer wymagają sprawdzenia na nowym komputerze; sam poprawny apt install nie
potwierdza działania renderowania. Zobacz docs/environment.md.


## Zależności API i misji (faza 5a)

Przed pierwszym startem kokpitu uruchom `bash scripts/setup_project.sh`.
Instrukcja, baza danych, panel sekwencji i testy: [missions.md](missions.md).

## Lokalny model i MLflow

Po przygotowaniu `.venv` na nowym komputerze wykonaj jednorazowo:

```bash
bash scripts/setup_bielik.sh
```

Instalacja jest lokalna, wymaga curl i obsługi zstd w tar. Pobiera około 4.3 GB
silnika i wag; sprawdza sumę kontrolną modelu. Potem standardowy `run_cockpit.sh`
uruchamia również Ollama i MLflow, i otwiera kokpit oraz panel z czatem.
Zatrzymanie: `bash scripts/stop_cockpit.sh`. Szczegóły: [bielik-chat.md](bielik-chat.md).

## Lokalny mikrofon

Jednorazowo `bash scripts/setup_whisper.sh` po instalacji zależności. Standardowy start pozostaje jedną komendą. [Obsługa i testy głosu oraz nowych stref](voice-and-inspection-zones.md). Do testów programu wymagany jest Node.js 18+; CI używa Node.js 22.

## Wizualizacja trasy

run_cockpit.sh automatycznie buduje klienta z robotics/visualization/pose_client.cpp. Wymaga g++, pkg-config oraz bibliotek Gazebo Transport 13 / Messages 10 z instalacji ROS. Po zmianie światów zrestartuj cały kokpit. [Mapa 2D i trasy](navigation-route-view.md).

## Detekcja na tablicach

Przed pierwszym uruchomieniem inspekcji wykonaj `bash scripts/setup_vision.sh`. Detektor ma osobne środowisko i startuje razem z `bash scripts/run_cockpit.sh`. Pełna instrukcja: [inspekcja zdjęć](vision-inspection.md).
