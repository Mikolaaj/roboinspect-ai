# Ustawienie magazynu i wskaźnik pracy czatu

W panelu sterowania, pod mapowaniem i nad historią, znajdują się trzy przyciski:

- **Standardowe ustawienie magazynu** przywraca oryginalne pozycje ośmiu obiektów wyposażenia.
- **Usuń wszystkie przeszkody** usuwa osiem obiektów z całego świata: cztery skrzynie, stół, regał i dwa wolnostojące słupy. Ściany, tablice inspekcyjne, kamery i robot pozostają.
- **Losuj przeszkody** ustawia te same obiekty w nowych pozycjach w przypisanych sektorach.

Zmiana jest dostępna w zwykłym scenariuszu przy gotowej nawigacji, bez aktywnej jazdy lub mapowania. Odświeża symulację i zgodną mapę nawigacyjną, a robot zaczyna w BASE. Podczas przełączania sterowanie jest zablokowane. Zwykle trwa to kilkanaście sekund. Nie zamykaj wtedy terminala. Postęp, wynik i błędy są we wspólnej historii operacji.

## Przejścia i mapy

Generator zachowuje korytarze szerokości 2,2 m do stref A/B/C oraz pas inspekcyjny przed tablicami. Sprawdza osiągalność BASE, A/B/C i P1 do P5 na siatce z przeszkodami powiększonymi o 0,45 m. Nieakceptowalny układ nie zostaje uruchomiony. To sprawdzenie geometrii statycznej; nie gwarantuje dojazdu po późniejszym ręcznym zablokowaniu trasy.

Każdy układ ma trwały identyfikator, a losowy także ziarno. Powtórzenie tego samego żądania nie tworzy innego losowania. Świat, mapa i pozycje są w ignorowanym katalogu `data/warehouse/versions`. Wybrany układ pozostaje po restarcie. Oryginalne pliki świata nie są nadpisywane.

Mapa nawigacyjna jest generowana z geometrii aktualnego świata. Nie jest nowym pomiarem SLAM. Możesz następnie uruchomić mapowanie przyciskami. Wcześniejsze mapy SLAM i historia pozostają zapisane, ale mapa innego układu nie jest automatycznie używana do nowej sceny. Mapa 2D i wszystkie kamery pokazują aktualny układ.

## Czat

Po zakończeniu nagrania obracające kółko z napisem „Whisper rozpoznaje nagranie…” wskazuje lokalną transkrypcję. Po jej zakończeniu sprawdź tekst i wyślij Enterem albo przyciskiem Wyślij. Nagranie nie uruchamia samodzielnie misji.

Podczas odpowiedzi modelu kółko ma napis „Bielik przygotowuje odpowiedź…”. Znika po wyniku, błędzie lub anulowaniu. Przycisk Zatrzymaj odpowiedź nadal przerywa analizę. Animacja respektuje ograniczenie ruchu ustawione w systemie.

## Uruchomienie i sprawdzenie

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/stop_cockpit.sh
bash scripts/run_cockpit.sh
```

Jedna komenda startu otwiera kokpit i panel sterowania. Poczekaj na gotowość Nav2. Zmień układ, obserwuj trzy kamery i mapę 2D, następnie zleć przejazd do A, B, C i BASE. Przyciski podczas jazdy powinny być niedostępne. W historii rozwiń Przebieg operacji.

Testy bez uruchomionej symulacji:

```bash
bash scripts/test_project.sh -q
```

Testy integracyjne zmieniające scenę, przy działającym bezczynnym kokpicie:

```bash
source /opt/ros/jazzy/setup.bash
.venv/bin/python scripts/check_warehouse.py clear
.venv/bin/python scripts/check_warehouse.py random
.venv/bin/python scripts/check_cockpit.py --existing --goals A B C BASE --output-dir artifacts/warehouse-navigation
.venv/bin/python scripts/check_warehouse.py standard
```

Raporty lokalne są w `artifacts/warehouse-check` i `artifacts/warehouse-navigation`. Odbiór sprawdza rzeczywiste modele Gazebo, zgodność mapy 2D, trzy kamery, powtórzenie żądania i stan robota. Testy jednostkowe sprawdzają osiem ziaren losowych, dostęp do wszystkich celów oraz blokady operacji. Testy JavaScript obejmują zakończenie i nakładanie się etapów transkrypcji i generowania.

## Wyniki odbioru

- Rzeczywisty świat Gazebo po usunięciu: zero z ośmiu obiektów wyposażenia, robot i tablice zachowane.
- Rzeczywisty losowy świat: osiem obiektów w nowych pozycjach, zgodny schemat 2D i trzy kamery.
- Pełny restart odtworzył ten sam identyfikator i ziarno układu.
- 121 testów Pythona oraz osiem testów JavaScript przeszło poprawnie.
- W przeglądarce potwierdzono kółko podczas odpowiedzi Bielika i jego zniknięcie po wyniku. Mikrofon fizyczny nie był ponownie nagrywany w tym odbiorze; cykl wskaźnika Whisper jest pokryty testami JavaScript.

Raporty: [usuwanie](verification/warehouse-clear.json), [losowanie](verification/warehouse-random.json), [restart](verification/warehouse-restart.json), [interfejs](verification/warehouse-ui.json).

Rzeczywiste przejazdy w losowym układzie A, B, C i BASE zakończyły się powodzeniem, z błędem pozycji poniżej 0,30 m. Sprawdzono również anulowanie podczas ruchu: [raport nawigacji](verification/warehouse-navigation.json).

Przywrócenie oryginalnego wyposażenia, trzech kamer i zgodnej mapy również przeszło poprawnie: [standardowy magazyn](verification/warehouse-standard.json). Po odbiorze pozostawiono zapisany tryb standardowy i wyłączono testowy kokpit.
