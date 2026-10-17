# Środowisko — wstępne rozpoznanie

Odczyt z 17.10.2026, bez instalacji i zmiany konfiguracji systemu.

| Element | Wynik |
|---|---|
| System | Ubuntu 24.04.4 LTS |
| RAM | około 32 GB |
| ROS | katalog /opt/ros/jazzy jest obecny; przykładu nie uruchomiono |
| Gazebo | polecenie gz dostępne; renderowania nie sprawdzono |
| Docker | polecenie dostępne; działania silnika nie sprawdzono |
| Domyślny python3 | 3.14.0 |
| /usr/bin/python3 | 3.12.3 |
| uv | nie znaleziono w aktualnym PATH |
| NVIDIA | nvidia-smi nie może połączyć się ze sterownikiem; przyczyna nieustalona |

## Następne sprawdzenia

1. Uruchomić scripts/doctor.sh i zachować wyniki lokalnie.
2. Zweryfikować wersje zainstalowanych pakietów ROS/Gazebo i działanie przykładu.
3. Sprawdzić renderowanie i sprzętową akcelerację; sam błąd nvidia-smi nie ustala przyczyny ani nie dowodzi, że GUI nie działa.
4. Oddzielić środowisko ROS od środowiska usług Python. Nie zmieniać globalnego interpretera jako sposobu konfiguracji projektu.
5. Dopiero po sprawdzeniu kompatybilności przypiąć Python i zależności w pyproject.toml/lockfile.

Brakujące instalacje i naprawa sterownika nie zostały wykonane. Ten dokument opisuje stan zastany, a nie komplet wymagań końcowej aplikacji.
