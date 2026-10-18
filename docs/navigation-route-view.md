# Mapa 2D hangaru i rzeczywista trasa Nav2

W kokpicie, pod kamerami i telemetrią, znajdują się dwie mapy obok siebie: dotychczasowa mapa SLAM oraz schemat całego hangaru z góry. Na telefonie układają się jedna pod drugą.

## Uruchomienie i sprawdzenie

Najpierw zatrzymaj poprzednią sesję, poczekaj na potwierdzenie, potem uruchom:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/stop_cockpit.sh
bash scripts/run_cockpit.sh
```

Przy pierwszym uruchomieniu skrypt buduje mały klient transportu Gazebo. Potrzebne są g++, pkg-config i biblioteki deweloperskie Gazebo Transport 13 / Messages 10 z używanej instalacji ROS/Gazebo. Na obecnym komputerze są dostępne. Kod klienta znajduje się w robotics/visualization/pose_client.cpp, lokalny plik wykonywalny w ignorowanym artifacts/bin. Klient jest przebudowywany po zmianie źródła; nie ma dodatkowej komendy startowej.

1. W panelu sterowania zleć przejazd do A, B lub C.
2. W kokpicie przewiń do map. Turkusowa kropka oznacza robota, żółta linia plan Nav2, żółty punkt aktualny cel.
3. Na obrazie każdej kamery linia znajduje się na podłodze świata symulacji. Jest widoczna wtedy, gdy dany fragment trasy mieści się w kadrze i nie zasłania go przeszkoda.
4. Po dotarciu, anulowaniu lub STOP linia i punkt celu znikają. Przy misji wieloetapowej pokazywany jest plan do bieżącego punktu.
5. Ctrl+C w terminalu uruchomienia lub stop_cockpit.sh zamyka cały stos.

## Skąd pochodzą dane

Schemat 2D bazuje na statycznych kolizjach scenariusza SDF, granicach sektorów, bazie i czerwonych strefach. Nie jest zdjęciem z monitoringu ani zastępczą mapą SLAM. Współrzędne schematu są zgodne z mapą nawigacyjną projektu. Robot jest rysowany z lokalizacji TF, tej samej co na mapie SLAM.

Przeszkody statyczne mają kolor szary. Pomarańczowa warstwa przedstawia komórki przeszkód z /global_costmap/costmap; wyświetlane są komórki lethal, bez kosztów inflacji. Jest to stan czujników i pamięci mapy kosztów, więc przeszkoda nie znika automatycznie tylko dlatego, że usunięto obiekt: potrzebne jest ponowne oczyszczenie obszaru przez pomiary.

Żółta linia pochodzi bezpośrednio z nav_msgs/Path publikowanego na /plan przez Nav2. Nie generujemy prostej kreski od robota do celu. To plan globalny, nie dokładna prognoza toru kół sterownika lokalnego. Gdy lidar wykryje nową przeszkodę, mapa kosztów się aktualizuje i Nav2 przelicza trasę. Oba widoki korzystają z nowego planu. Nie wyprzedzamy pomiarów czujników: nieznany, jeszcze niewykryty obiekt nie zmienia planu.

Plan musi mieć ramę map, aktualny znacznik czasu i koniec zgodny z bieżącym celem. Nie przyjmujemy planów poprzedniej misji, opóźnionych wiadomości ani nieprawidłowych współrzędnych. Plan starszy niż 3 s jest ukrywany do czasu kolejnej aktualizacji; punkt aktywnego celu pozostaje. Przy utracie połączenia mapa ukrywa trasę, cel i pozycję zamiast pokazywać je jako aktualne.

## Wizualizacja w Gazebo

Generator świata tworzy stałą pulę 160 odcinków i jeden znacznik celu. To wyłącznie elementy wizualne bez kolizji, umieszczone około 4.5 cm nad podłogą. Linia ma przezroczystość 0.42, cel 0.20. Nie modyfikuje przeszkód ani mapy używanej przez planowanie. Ukryte elementy są przenoszone pod podłogę.

Osobny proces ROS route_visualizer pobiera telemetrię z adaptera i przekazuje pozycje całej puli przez jeden trwały klient Gazebo i usługę /world/roboinspect_hangar/set_pose_vector. Nie wywołuje transportu na executorze sterowania ruchem. Aktualizacje są ograniczone do 2.5 Hz; niezmieniona geometria odświeża się co 2 s. Długie plany mają ograniczoną liczbę elementów; powyżej około 88 m odcinki mogą mieć przerwy. Pełna polilinia pozostaje dostępna na mapie 2D.

Po restarcie świata lub przejściu do SLAM proces wizualizacji dostaje nową partycję Gazebo i czyści poprzednią trasę. Brak telemetrii przez 2 s także ukrywa linię. Błąd renderera jest raportowany osobno, bez zmieniania misji i sterowania robotem.

API tylko do odczytu: /api/hangar z układem scenariusza oraz pola route, route_visual, observed_obstacles i obstacles_fresh w /api/status. Brak nowego API do podawania dowolnych współrzędnych ruchu.

## Weryfikacja

```bash
bash scripts/test_project.sh -q
```

Test z nagłą przeszkodą wymaga działającego kokpitu i wolnego robota. Rozpoczyna przejazd do C, wstawia tymczasową skrzynię około 2 m przed robotem na planie Nav2, sprawdza nowy plan i pomiary czujników, anuluje misję, a następnie usuwa skrzynię:

```bash
source /opt/ros/jazzy/setup.bash
.venv/bin/python scripts/check_route_visualization.py
```

Opcja --use-active używa już uruchomionego przejazdu. Raport i zdjęcia trafiają do artifacts/route-check. Nie używaj tego testu w trakcie własnej misji: test kończy się jej anulowaniem.

Wykonane 18.10.2026: 99 testów Python i 5 testów nagrywania JavaScript przeszło. Kamera FPV, kamera podążająca oraz monitoring pokazały linię świata. W teście dynamicznym rewizja planu wzrosła z 50 do 52; wykryta skrzynia została ominięta, odstęp polilinii od jej środka wyniósł około 1.28 m, a nowy plan pojawił się w około 1.6 s. Sprawdzono usunięcie linii i celu po anulowaniu i po dojeździe do BASE. Wyniki: [raport](verification/route-replanning.json).

Oficjalny interfejs transportu: [Gazebo UserCommands](https://github.com/gazebosim/gz-sim/blob/gz-sim8/src/systems/user_commands/UserCommands.cc).
