# Renderowanie na NVIDIA RTX i praca CPU

Stan sprawdzony 18.10.2026: NVIDIA GeForce RTX 4060 Laptop GPU, sterownik
595.99.02. Sterownik działa; nie był instalowany ani zmieniany przez skrypty projektu.

## Start

Domyślna komenda wybiera RTX, jeśli nvidia-smi i biblioteki NVIDIA są dostępne:

```bash
bash scripts/run_cockpit.sh
```

Jawne wymaganie NVIDIA:

```bash
bash scripts/run_cockpit.sh --rendering gpu
```

Tryb awaryjny, renderowanie programowe:

```bash
bash scripts/run_cockpit.sh --rendering cpu
```

Przed zmianą trybu zamknij poprzednią sesję przez Ctrl+C albo
`bash scripts/stop_cockpit.sh`. Panel przycisków
uruchamia się nadal przez `bash scripts/run_control_panel.sh`. Stopka kokpitu
pokazuje wybrane urządzenie renderujące.

Podział pracy: GPU renderuje sensory RGB i GPU lidar; CPU nadal obsługuje
fizykę, ROS, Nav2, przetwarzanie komunikatów oraz kodowanie JPEG/serwer UI.
Nie jest to przeniesienie całej symulacji ani Nav2 na CUDA. Małe obrazy i
ograniczone FPS nie muszą mocno obciążać RTX-a.

Tryb auto wybiera GPU po pomyślnym sprawdzeniu sterownika, inaczej CPU.
Nie oznacza automatycznej naprawy sterownika ani restartu na CPU po błędzie
kontekstu OpenGL; w takim przypadku sprawdź simulation.log i wybierz cpu.
Tryb gpu zgłasza błąd, jeżeli sterownik jest niedostępny.

Dla samodzielnego run_robot.sh można wybrać tryb zmienną procesu:

```bash
ROBOINSPECT_RENDERING=gpu bash scripts/run_robot.sh
ROBOINSPECT_RENDERING=cpu bash scripts/run_robot.sh
```

Dawne ROBOINSPECT_SOFTWARE_RENDERING=1 jest nadal obsługiwane, jeśli nie
podano nowej opcji/zmiennej. Jawne --rendering gpu ma pierwszeństwo.

## Weryfikacja rzeczywistego GPU

Przy działającym kokpicie:

```bash
/usr/bin/python3 scripts/check_gpu.py
nvidia-smi
```

check_gpu.py sprawdza jednocześnie: gotowość Nav2, trzy zmieniające się
obrazy, proces natywnego serwera Gazebo na karcie NVIDIA oraz nazwę NVIDIA
w GL_RENDERER. Zapisuje raport w artifacts/gpu-check/result.json.
Sama nazwa trybu w stopce nie zastępuje tego testu.

Sprawdzenie ruchu przez ten sam interfejs co przyciski obejmuje A → BASE
oraz anulowanie w ruchu; zapis wyniku opisuje docs/phase3-results.md.
Pełne próby wszystkich scenariuszy: bash scripts/check_phase3.sh.

## Implementacja i źródło ustawień

scripts/rendering.py ustawia środowisko tylko procesom projektu. Usuwa
wymuszenia llvmpipe/Mesa przy wyborze GPU i stosuje PRIME Render Offload:
__NV_PRIME_RENDER_OFFLOAD=1, __GLX_VENDOR_LIBRARY_NAME=nvidia oraz bibliotekę
EGL NVIDIA. Podstawą jest [oficjalna dokumentacja NVIDIA](https://docs.nvidia.com/datacenter/tesla/driver-installation-guide/optimus-laptops-and-multi-gpu-desktop-systems.html).
Pozostawiono sprawdzony silnik Ogre. Nie zmieniamy globalnych ustawień X/Wayland,
konfiguracji sterownika ani domyślnej karty innych aplikacji.

## Izolacja i zamykanie

Każdy start kokpitu otrzymuje własny GZ_PARTITION, chyba że test podał go
jawnie. Zapobiega to mieszaniu zegarów i sensorów między serwerami Gazebo.
Przy zamykaniu launcher zapamiętuje potomne procesy, kończy ROS i usuwa
pozostały natywny serwer gz również wtedy, gdy jego launcher Ruby zakończył
się wcześniej. To poprawka do wykrytego problemu pozostawionych procesów.
