# Faza 2 — hangar i sektory

## Co jest gotowe

Własny świat o wymiarach 30 x 22 m, bez pobieranych modeli z Internetu:

- A: niebieski sektor serwisowy, stół i panele P1/P2.
- B: zielony sektor inspekcyjny, skrzynie i panele P3/P4.
- C: bursztynowy sektor magazynowy, regał i panel P5.
- BASE: turkusowe pole startowe w południowo-zachodniej części.
- Główny korytarz z żółtymi kreskami na południu.
- Ściany, słupy, regał, stół, skrzynie i stojaki z geometrią kolizji.
- Żółte pola przed panelami oznaczają przyszłe pozycje obserwacji.
- Napisy sektorów i paneli to lokalna geometria, bez zewnętrznych fontów/tekstur.

Dach pominięto, a południowa ściana jest niższa i ma otwór wejściowy, aby można było oglądać układ z góry. Otwór nie jest bramą z animacją.

Poniższe polecenia dotyczą pustego hangaru fazy 2. Robot został dodany w osobnym wariancie opisanym w [instrukcji robota](robot.md). Nav2 i trzy kamery są dostępne przez [kokpit](cockpit.md). Sam run_hangar.sh otwiera pusty świat i jedną kamerę edytora Gazebo. Stan paneli jest jednakowy; klasy defektów powstaną w fazie danych i uczenia.

## Uruchomienie

1. Zatrzymaj poprzedni przykład dwoma pojazdami: Ctrl+C w jego terminalu, a następnie zamknij pozostałe okno Gazebo.
2. Wyjdź z venv innego projektu, jeśli jest aktywny (`deactivate`).
3. Uruchom:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_hangar.sh
```

Powinien pojawić się hangar w widoku ukośnym z góry. Skrypt rozwiązuje ścieżkę względem repo, więc może działać również z innego katalogu. Ctrl+C w terminalu kończy symulację.

## Co obejrzeć

1. Widać trzy kolorowe pola A, B i C, turkusową bazę oraz żółty korytarz.
2. Przy północnej ścianie znajdują się panele: P1/P2 w A, P3/P4 w B i P5 w C.
3. Przed każdym panelem jest małe żółte pole obserwacji.
4. W A stoi stół, w B są skrzynie, a w C regał.
5. Zbliż i obróć widok dostępnymi kontrolkami Gazebo; sprawdź, czy elementy są na podłodze i napisy są czytelne.
6. W panelu Entity tree można znaleźć modele po nazwach, np. panel_P3, base_paint, rack_C.

Renderowanie GUI wymaga sprawdzenia na ekranie użytkownika. Automatyczna walidacja SDF i test bez okna nie gwarantują jakości widoku ani działania sterownika grafiki.

## Wariant z przeszkodą

Zatrzymaj poprzedni świat przez Ctrl+C, a potem:

```bash
bash scripts/run_hangar.sh blocked
```

Między sektorami B i C powinna pojawić się dodatkowa duża czerwona przeszkoda (`scenario_blocker`). Utrudnia bezpośrednie przejście w poprzek, ale pozostawia południowy korytarz. Ten wariant nie oznacza całkowitego odcięcia panelu ani przetestowanego automatycznego omijania.

## Walidacja techniczna

```bash
source /opt/ros/jazzy/setup.bash
gz sdf -k simulation/worlds/hangar_normal.sdf
gz sdf -k simulation/worlds/hangar_blocked.sdf
```

Oba wyniki powinny zawierać `Valid.`. Krótki test serwera bez grafiki:

```bash
timeout 30s bash scripts/run_hangar.sh normal -s --iterations 200
```

Proces powinien sam się zakończyć; kod 124 z timeout oznacza przekroczenie limitu, a nie zaliczenie testu. W środowisku ograniczającym interfejsy sieciowe może wystąpić getifaddrs — nie jest to automatycznie błąd geometrii świata.

## Konfiguracja i odtwarzanie

Źródło geometrii: `scripts/build_hangar.py`. Wygenerowane pliki:

- `simulation/worlds/hangar_normal.sdf`;
- `simulation/worlds/hangar_blocked.sdf`;
- `config/hangar.json` — metry, układ world, granice sektorów, baza i pozycje obserwacji.

Przebudowa bez dodatkowych bibliotek Python:

```bash
/usr/bin/python3 scripts/build_hangar.py
```

Generator nadpisuje konfigurację i sześć światów: normal, blocked i unreachable, każdy bez robota oraz z robotem. Wariant unreachable zamyka cel B i służy do testu braku trasy. Zmiany układu wprowadzaj w generatorze, aby kolejna przebudowa ich nie usunęła. Po zmianie uruchom walidację i sprawdź świat ponownie.

## Sprawdzenia wykonane 17.10.2026

- Oba światy poprawne według `gz sdf -k`.
- Oba światy wykonały 200 iteracji serwera Gazebo, kończąc z kodem 0.
- Nazwy modeli są unikalne; 38 modeli w normal, 39 w blocked; każdy świat ma 5 paneli.
- Baza i 5 pozycji obserwacji nie przecinają obwiedni przeszkód przy promieniu 0.35 m. To kontrola punktów, nie sprawdzenie całej trasy ani zatwierdzenie wymiarów przyszłego robota.
- Oznaczenia podłogi, litery i miejsca obserwacji nie mają kolizji; wyposażenie i granice mają kolizje.

Kryterium odbioru tej części: potwierdzenie wyglądu obu scenariuszy. Aktualne próby fizycznych przejazdów opisują docs/cockpit.md i docs/phase3-results.md.
