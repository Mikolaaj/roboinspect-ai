# Środowisko — stan etapu symulacji

Aktualizacja z 17.10.2026. Pakiety Nav2 zainstalował użytkownik. Konfiguracja renderowania dotyczy procesów projektu, bez zmiany sterownika systemowego.

| Element | Wynik |
|---|---|
| System | Ubuntu 24.04.4 LTS |
| RAM | około 32 GB |
| ROS | Jazzy /opt/ros/jazzy; działają mosty, sensory i Nav2 |
| Gazebo | Gazebo Sim 8.11.0; sprawdzone Ogre na NVIDIA RTX oraz Mesa llvmpipe |
| Docker | polecenie dostępne; działania silnika nie sprawdzono |
| Domyślny python3 | 3.14.0 |
| /usr/bin/python3 | 3.12.3 |
| uv | nie znaleziono w aktualnym PATH |
| NVIDIA | RTX 4060 Laptop GPU; nvidia-smi działa, sterownik 595.99.02 (18.10.2026) |

## Odtwarzanie i dalsze sprawdzenia

1. Uruchomić scripts/doctor.sh i zachować wyniki lokalnie.
2. Na nowym komputerze sprawdzić wersje ROS/Gazebo oraz przejazdy według docs/cockpit.md.
3. Sprawdzić renderowanie i sprzętową akcelerację; sam błąd nvidia-smi nie ustala przyczyny ani nie dowodzi, że GUI nie działa.
4. Oddzielić środowisko ROS od środowiska usług Python. Nie zmieniać globalnego interpretera jako sposobu konfiguracji projektu.
5. Dopiero po sprawdzeniu kompatybilności przypiąć Python i zależności w pyproject.toml/lockfile.

Sterownik NVIDIA nie był zmieniany przez projekt; w sprawdzeniu 18.10.2026 działa. Systemowy Python 3.12 z pakietami ROS i python3-pil wystarcza do bieżącego kokpitu. Pełne zależności i polecenia instalacji: docs/cockpit.md; zależności późniejszych usług AI zostaną dodane osobno.
