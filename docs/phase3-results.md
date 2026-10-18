# Odbiór fazy 3 — robot, nawigacja i kokpit

Weryfikacja końcowa: 18.10.2026. Faza 3 w uzgodnionym zakresie została zaliczona.
Podstawowy kokpit z fazy 4 włączono do tego etapu na życzenie użytkownika.

## Wyniki rzeczywistych przejazdów

| Scenariusz | Cel | Stan | Błąd pozycji świata Gazebo |
|---|---|---|---|
| normal | A | succeeded | 0.087 m |
| normal | B | succeeded | 0.120 m |
| normal | P3 | succeeded | 0.161 m |
| normal | C | succeeded | 0.195 m |
| normal | BASE | succeeded | 0.341 m |
| blocked | B | succeeded | 0.163 m |
| blocked | C | succeeded | 0.140 m |
| blocked | BASE | succeeded | 0.378 m |
| unreachable | B | failed | cel nieosiągnięty — oczekiwany brak trasy |

W każdym scenariuszu sprawdzono trzy niepuste obrazy kamer, blokowanie drugiego
celu, nieprawidłowy cel, anulowanie podczas rzeczywistego ruchu i zatrzymanie.
Zmiana pozycji po anulowaniu wyniosła 0.000 m w kolejnej obserwacji.
Każdy launcher zakończył pracę kodem 0. Potwierdzono ponowny start na tym samym
porcie oraz odrzucenie próby uruchomienia drugiego kokpitu.

## Obrazy i wydajność

| Próba | FPV FPS | Kamera podążająca FPS | Monitoring FPS | Czas symulacji / zegarowy |
|---|---:|---:|---:|---:|
| normal | 9.49 | 5.00 | 2.50 | 0.96 |
| blocked | 9.49 | 4.50 | 3.00 | 0.96 |

Pomiar FPS: krótka, dwusekundowa próbka odbioru klatek w backendzie po starcie,
nie pomiar opóźnienia obrazu na ekranie ani długoterminowy benchmark. Renderowanie
Ogre + Mesa llvmpipe; kamera FPV 320×240, podążająca 640×360, monitoring 640×480.
Trzy widoki i obsługę przycisków sprawdzono również w przeglądarce.

## Konfiguracja i odtworzenie

AMCL: 120 promieni, aktualizacja po 0.05 m / 0.05 rad. Goal checker: 0.10 m /
0.15 rad, ponownie sprawdza położenie podczas ustawiania orientacji. Tolerancja
estymacji Nav2 nie jest gwarancją fizycznej dokładności. W testach niezależnie
od sukcesu akcji odczytano pozycję bezpośrednio z Gazebo; próg odbioru wynosi 0.50 m.
Pierwsza próba na starszych ustawieniach wykazała około 0.60 m błędu powrotu;
po poprawkach powtórzono cały wariant normal i sprawdzono blocked.

Polecenia, zależności i ograniczenia: [cockpit.md](cockpit.md).
Instalacja na nowym komputerze: [install-and-run.md](install-and-run.md).
Wyniki liczbowe i skróty konfiguracji: [verification/phase3.json](verification/phase3.json).
Pełne lokalne logi: artifacts/cockpit-check-{normal,blocked,unreachable}/.

## Granice odbioru

Nie zatwierdzono wszystkich kombinacji tras ani dojazdów P1/P2/P4/P5. Brak trasy
sprawdzono na znanym zamkniętym B; nie oznacza to walidacji dowolnej dynamicznej
przeszkody. Historia panelu jest w pamięci procesu. Nie ma jeszcze LLM, trwałych
misji, mikrofonu ani niezależnego zatrzymania awaryjnego fizycznego robota.
Wygładzanie podążającej kamery, nakładka trasy i szersze pomiary wydajności są
rozwinięciami fazy 4. Odbiór nowego komputera wymaga ponownych testów.

## Poprawka izolacji i sprawdzenie RTX — 18.10.2026

W rzeczywistej sesji użytkownika wykryto pozostawione natywne serwery Gazebo
i mieszanie zegarów. Sam kod zakończenia launchera nie wystarczał do ich wykrycia.
Dodano osobny GZ_PARTITION dla startu kokpitu i sprzątanie zapamiętanych procesów
potomnych. Sprawdzono gotowość Nav2, stabilny zegar oraz brak natywnych serwerów
po zamknięciu i ponowny start. Test akceptacyjny kontroluje teraz te pozostałości.

Sterownik RTX działa. Renderowanie GPU potwierdzono jednocześnie przez
GL_RENDERER NVIDIA i proces Gazebo na karcie w nvidia-smi. Krótki test na GPU
obejmował trzy obrazy, anulowanie podczas ruchu i A → BASE: odpowiednio około
0.037 m i 0.311 m błędu pozycji świata. CPU nadal obsługuje fizykę i ROS/Nav2.
Pierwotne pełne próby normal/blocked opisane wyżej wykonano na renderowaniu
programowym. Wyniki próby GPU: [verification/gpu.json](verification/gpu.json).
Szczegóły wyboru urządzenia: [gpu.md](gpu.md).
