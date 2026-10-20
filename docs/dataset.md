# Warianty tablic, zbieranie danych i EDA

Ten etap przygotowuje dane do przyszłego modelu stanu tablicy. Nie trenuje modelu i nie przedstawia etykiet symulacji jako przewidywań YOLO/SAM.

## Obsługa w panelu

Zatrzymanie:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/stop_cockpit.sh
```

Poczekaj na potwierdzenie. Uruchomienie kokpitu i panelu:

```bash
bash scripts/run_cockpit.sh
```

Odśwież stronę przez Ctrl+Shift+R. Pod ustawieniem magazynu rozwiń sekcję **Dane do modelu usterek**.

1. Wybierz stan: poprawny obraz, pęknięcia, zabrudzenie, zasłonięcie lub brak obrazu. Wariant mieszany daje po jednym stanie na każdej z pięciu tablic.
2. Wybierz część zbioru: treningową, walidacyjną lub testową.
3. Zaznacz zapisywanie próbek i wybierz Zastosuj stan tablic. Operacja wymaga zakończenia misji i mapowania. Odświeża świat, a robot wraca do BASE. Trafia do historii operacji.
4. Uruchom inspekcje A, B i C. Każda zakończona analiza tablicy zapisuje jedną próbkę, także gdy YOLO nie wykryje obiektów.
5. Wybierz Przelicz EDA, następnie Raport danych. Raport pokazuje liczebność klas, podział, braki, duplikaty, jasność, kontrast, wariancję krawędzi i podgląd kadrów. Udostępnia JSON, manifest CSV i podział źródeł.

Wyłączenie zapisywania nie kasuje wcześniejszych próbek. Zmiana samych zdjęć nadal działa i respektuje wybraną część zbioru. Zmiana przeszkód nie zmienia etykiet stanu tablic.

## Co jest zapisywane

Próbki pochodzą z rzeczywistej kamery Gazebo używanej przez inspekcję, a nie z plików tekstur lub obrazów z ramkami YOLO. Dane znajdują się lokalnie w `data/dataset/samples/<id obserwacji>/`:

- `frame.jpg`: nieoznaczona, pełna klatka kamery;
- `crop.jpg`: przybliżony wycinek docelowej tablicy, jeżeli projekcja geometrii mieści się w kadrze;
- `metadata.json`: klasa stanu, pochodzenie etykiety, zdjęcie źródłowe i jego SHA256, część zbioru, scena, ziarno transformacji, wersja generatora, identyfikatory misji i obserwacji, czas kamery, pozycja, kierunek, rozmiar obrazu i ROI.

Etykieta pochodzi z manifestu sceny (`synthetic_scene_manifest`). Manifest jest skojarzony z aktywnym światem, a zbieranie wymaga zgodnego identyfikatora sceny w odpowiedzi procesu wizyjnego. Nie jest podawany do inferencji YOLO/SAM jako cecha lub odpowiedź. Generator nie dopisuje nazw klas do obrazów. Dane nie są zbierane ze spóźnionej odpowiedzi anulowanej inspekcji. Zbieranie następuje po zapisaniu zakończonej obserwacji, a błąd zbioru nie kasuje raportu YOLO/SAM.

Domyślny świat bez skonfigurowanego profilu pokazuje poprawne zdjęcia i nie zbiera danych. Włączenie zbierania jest częścią jawnej operacji panelu.

## Podział bez mieszania źródeł

Źródłem jest lokalny zestaw 24 fotografii COCO128. Grupy według SHA256 oryginału są deterministycznie przypisane przed generowaniem wariantów: 14 do treningu, 5 do walidacji i 5 do testu. Zduplikowany oryginał ma jedną grupę niezależnie od jego nazwy.

Każda scena zbioru korzysta wyłącznie ze zdjęć należących do jednej części. To ważne również dla pełnych klatek, na których może być widoczna sąsiednia tablica. Wszystkie warianty, powtórzenia i kadry tego samego źródła zachowują podział. EDA sprawdza grupy wszystkich tablic sceny oraz identyczne pełne kadry i wycinki pomiędzy częściami. Nie jest to wykrywanie wszystkich semantycznych lub prawie identycznych zdjęć; przed treningiem potrzebny jest również przegląd wizualny.

Polityka: `source-sha256-v1-2026`. Wersja generatora: `board-conditions-v1`. Zdjęcia źródłowe, transformacje i ich parametry są osobno wersjonowane w manifestach. Zmieniając generator, należy zmienić jego wersję.

## Kontrola jakości przed treningiem

Wycinek jest oszacowany z geometrii tablicy, pozycji i kierunku robota oraz parametrów kamery. Używa nominalnej wysokości kamery 0,90 m i nie koryguje błędów lokalizacji, przechyłu ani perspektywy homografią. Każda próbka ma `pending_review`; niewidoczna lub niepełna tablica daje `needs_retake`. Żadna próbka nie jest automatycznie uznawana za gotową do treningu.

Przed treningiem trzeba sprawdzić, czy wycinek obejmuje właściwą tablicę i czy klasa jest czytelna. Trzeba też zebrać więcej przykładów, uwzględnić różne punkty widzenia i oświetlenie, ocenić niezrównoważenie oraz odfiltrować duplikaty. Brakujące klasy i części zbioru są wypisane w EDA. Bieżący pilot z jednego obchodu to zaledwie pięć przykładów: nie wystarcza do wiarygodnego treningu ani oceny.

Maski SAM nie stanowią ręcznych masek usterek. `complete` przy SAM oznacza kompletność segmentacji obiektów, nie poprawne wykrycie pęknięcia lub zabrudzenia. Własny model usterek powstanie w kolejnym etapie po przeglądzie danych.

## Przygotowanie i odtwarzanie

Standardowe przygotowanie wizji zapewnia fotografie i bazowe tekstury. Warianty aktywnych tablic generują się lokalnie podczas zastosowania profilu. Opcjonalne przygotowanie pełnego katalogu 240 tekstur (24 źródła × 5 stanów × 2 ziarna):

```bash
.venv/bin/python scripts/prepare_dataset_assets.py
```

`data/dataset/assets.json` opisuje wyłącznie tekstury, nie próbki z kamery. Nie są one wliczane do zbioru inspekcji.

Pełny test na uruchomionej symulacji:

```bash
.venv/bin/python scripts/check_dataset.py
```

Skrypt zmienia świat na mieszaną scenę treningową, wykonuje wszystkie sektory i sprawdza pięć klas oraz EDA. Trwa kilka minut i porusza robotem. Wyniki są w `docs/verification/dataset-pilot.json`. Testy jednostkowe i API:

```bash
bash scripts/test_project.sh -q
```

Raporty EDA są lokalnie w `data/dataset/reports/`. Eksperyment MLflow `roboinspect-dataset` zapisuje liczebności, błędy podziału, duplikaty, wersję snapshotu, CSV i plan podziału. Raporty inspekcji zachowują pochodzenie etykiet w swoim eksperymencie YOLO. Bieżące dane, zdjęcia, tekstury i modele są ignorowane przez Git; kod, konfiguracja i wyniki weryfikacji pozostają w repo.

## Licencje i ograniczenia

Warianty są syntetycznymi przeróbkami tych samych fotografii COCO, których pochodzenie opisano w [informacjach o danych wizji](third-party/vision.md). Zachowujemy oryginalne adresy i hashe. Klasa „brak obrazu” jest pustą powierzchnią tablicy, a nie nieobecnością fizycznego stojaka. Pęknięcia, zabrudzenia i zasłonięcia to proste generowane efekty. Wynik na takich danych nie dowodzi jakości na prawdziwych uszkodzeniach urządzeń.

## Wynik pilotażu 19.10.2026

Pełny obchód sektorów A, B i C zapisał pięć rzeczywistych klatek kamery, po jednej dla każdego stanu tablicy. Wszystkie mają status `pending_review` i należą do części treningowej. EDA wykazała zero błędów podziału, ale wskazała brak próbek walidacyjnych i testowych. Trening pozostaje wyłączony. Osobno wygenerowano 240 tekstur, które nie są próbkami treningowymi z kamery.

Sprawdzono przycisk EDA w panelu, trwałość danych po ponownym uruchomieniu, raport HTML oraz eksporty JSON i CSV. Raport mieści się w widoku mobilnym 390 px bez poziomego przewijania strony.

## Sesja zbierania do 16:22, 19.10.2026

Automatyczne zbieranie trwało od 15:43:04 do 16:20:33. Pozostawiono zapas na EDA i zamknięcie; wszystkie procesy kokpitu zamknięto o 16:20:53. Dodano 24 próbki, łącznie 31: trening 22, walidacja 4, test 5. Wykonano 14 udanych misji sektorowych i jedną przerwaną z potwierdzeniem zatrzymania. Nie zmieniano tempa fizyki ani nie trenowano modeli.

EDA nie wykazała dokładnych duplikatów ani przecieku między częściami zbioru. Wszystkie 62 pliki obrazów (klatki i wycinki) przeszły kontrolę odczytu. Walidacja nadal nie zawiera klas `dirty` i `missing`; trzeba je uzupełnić przed oceną klasyfikatora. Wszystkie próbki pozostają do ręcznego przeglądu. Wyniki: `docs/verification/dataset-session-2026-10-19.json`. MLflow: eksperyment `roboinspect-dataset`, run `e44d50c9d0c34b01a5790e3a12991b0d`.

Skrypt `scripts/collect_dataset_session.py --until <ISO timestamp z przesunięciem strefy>` wymaga uruchomionego kokpitu. Zmienia sceny, porusza robotem, zapisuje audyt w `artifacts/dataset-session`, a na końcu przelicza EDA i zatrzymuje cały kokpit. Może zakończyć zbieranie wcześniej, pozostawiając zapas na domknięcie ostatniej misji. W tej wersji błąd komunikacji kończy sesję i uruchamia procedurę zatrzymania.

## Przegląd i zatwierdzanie próbek

W panelu sterowania rozwiń **Dane do modelu usterek** i wybierz **Przejrzyj i zatwierdź próbki**. Osobny ekran `/dataset/review` pokazuje pełną klatkę oraz wycinek tablicy. Filtruj według statusu, części zbioru i stanu tablicy. Przyciski poprzedniej/następnej próbki umożliwiają przegląd całego zbioru, pobieranego stronami po 20 pozycji.

Porównaj obraz z etykietą, ewentualnie popraw stan i dodaj uwagę. **Zatwierdź i przejdź dalej** zapisuje decyzję i przechodzi do kolejnej próbki. **Odrzuć** wyklucza próbkę z przyszłego treningu bez usuwania obrazów. **Cofnij do przeglądu** odwołuje zatwierdzenie lub odrzucenie. Aby wrócić do odrzuconej próbki, wybierz filtr **Odrzucone**. Historię decyzji znajdziesz pod formularzem. Zmiana filtra lub użycie przycisku następnej próbki nie zapisuje samej edycji etykiety: zapisz ją jednym z przycisków decyzji.

Oryginalna etykieta, pochodzenie danych i podział źródeł pozostają zachowane. Każda decyzja zapisuje datę, poprzedni stan, nową etykietę i uwagę. Zapis jest atomowy, a kontrola rewizji zapobiega nadpisaniu decyzji z drugiej karty. Zatwierdzenie wymaga istniejącego wycinka, poprawnych hashy klatki i wycinka oraz zgodności grup zdjęć z częścią zbioru. Po decyzji odświeżenie strony zachowuje stan. Brak wycinka oznacza odrzucenie i ponowienie obserwacji, nie automatyczne zatwierdzenie.

Licznik **Do przeglądu** pomija odrzucone i zatwierdzone próbki. **Gotowe do treningu** oznacza zatwierdzone obserwacje we wszystkich częściach zbioru, nie wystarczającą liczebność ani uruchomiony trening. Po przeglądzie wybierz **Przelicz EDA**: CSV zawiera statusy i `training_ready`, a raport pokazuje liczebność klas w częściach zbioru i brakujące zatwierdzone klasy (`approved_missing_by_split`). Części walidacyjnej i testowej nie używamy do uczenia wag modelu. Własny trening pozostaje oddzielnym, jeszcze niewdrożonym etapem.

Weryfikacja przeglądu 19.10.2026: pełny zestaw 175 testów Python i 8 JavaScript przeszedł. Po dodatkowym teście EDA uruchomiono ponownie 20 testów modułu danych, również poprawnie. W przeglądarce zatwierdzono wizualnie próbkę P2 z pęknięciami (`3c0b38f7`), potwierdzono filtr i trwałość po odświeżeniu oraz układ mobilny 390 px. Pozostałe próbki nie zostały automatycznie zatwierdzone. Dodatkowe inspekcje B/C uzupełniły walidację: obecnie 34 próbki (trening 22, walidacja 7, test 5), każda część zawiera pięć klas. Jedna zatwierdzona, 33 do przeglądu. EDA bez dokładnych duplikatów i błędów podziału. Szczegóły: `docs/verification/dataset-review.json`. Nadal jest to mały pilot, nie zbiór wystarczający do wiarygodnej oceny modelu.

## Zbieranie do zadanej liczby próbek

`scripts/collect_dataset_target.py --total 200` uzupełnia istniejący zbiór do dokładnie 200 obserwacji, zachowując pierwotne rekordy i decyzje. Przyjmuje podział 60/20/20 (120 treningowych, 40 walidacyjnych i 40 testowych) oraz równe liczebności pięciu klas w każdej części. Nie usuwa danych, aby wymusić cel. Jeśli istniejąca klasa przekracza docelową liczebność, kończy pracę z błędem.

To osobny tryb akwizycji, nie test nawigacji: w izolowanej instancji Gazebo robot ma nieruchome podwozie i jest ustawiany przed P1–P5. Zmieniają się zdjęcia źródłowe, parametry syntetycznych usterek oraz pozycja kamery: przesunięcie boczne do 22 cm, odległość od -18 do +12 cm względem punktu obserwacji, kierunek do około 3,7 stopnia. Kamera zachowuje oryginalną geometrię i rozdzielczość 1280×720; wycinek powstaje dopiero z odczytanej klatki RGB. Nie są to kopie tekstur ani obrazy z ramek YOLO. Nie ma jazdy Nav2 ani inferencji YOLO/SAM dla tych nowych rekordów.

Kolektor działa na oddzielnym ROS_DOMAIN_ID i GZ_PARTITION, blokuje równoczesny start kokpitu i kończy swoje procesy po osiągnięciu celu. Nie zmienia utrwalonego profilu tablic panelu operatora. Wymaga wyłączonego kokpitu oraz skonfigurowanego lokalnego Gazebo i renderera.

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/stop_cockpit.sh
source /opt/ros/jazzy/setup.bash
.venv/bin/python scripts/collect_dataset_target.py --total 200
```

Nowe próbki mają `collection_mode=staged_static_robot_camera`, źródło pozycji `gazebo_set_pose_static_fixture`, identyfikator partii i znaną pozycję robota w metadanych. Nie odpowiadają wykonanym misjom w bazie; ich `mission_id` pozostaje pusty. Dotychczasowe inspekcje Nav2 zachowują swoje powiązania. Surowe obrazy są w `data/inspections/<id>/raw.jpg`, klatki i wycinki w `data/dataset/samples/<id>/`. Audyt i światy użyte do zebrania danych są w `artifacts/dataset-target/`.

Nowe dane pozostają `pending_review`. Zakończenie obejmuje EDA, sprawdzenie dokładnych duplikatów i rozdzielenia grup źródłowych oraz zapis `docs/verification/dataset-200.json`. Kontrola pełnego widoku tablicy jest geometryczna; nie zastępuje przeglądu wizualnego. Dwieście obserwacji to warianty istniejących 24 fotografii źródłowych, nie 200 niezależnych zdjęć. Zwiększenie liczby kadrów nie usuwa ograniczeń małego, syntetycznego zbioru.

### Ukończony zbiór 200 próbek

Po wznowieniu przerwanej sesji dodano brakujące 15 obserwacji testowych. Stan końcowy: **200 próbek**, trening **120**, walidacja **40**, test **40**. Każda klasa ma 24 próbki treningowe, 8 walidacyjnych i 8 testowych. Zachowano wcześniejsze 34 zatwierdzenia; 166 nowych obserwacji wymaga przeglądu. Nie uruchamiano treningu.

Sprawdzono sumy kontrolne i odczyt wszystkich 400 plików klatek/wycinków. EDA nie wykazała dokładnych duplikatów ani błędów podziału. Zbiór obejmuje 34 obserwacje z inspekcji Nav2 i 166 kadrów z kontrolowanych pozycji symulatora; metoda jest zapisana w metadanych i eksporcie CSV. Zdjęcia źródłowe nadal tworzą 14 grup treningowych, 5 walidacyjnych i 5 testowych. Wyniki: `docs/verification/dataset-200.json`.

Przy normalizacji metadanych wcześniejszej przerwanej partii techniczny identyfikator ujęcia przeniesiono z `mission_id` do `capture_reference_id`. Dla kontrolowanych ujęć `mission_id` jest pusty, ponieważ nie wykonywano dla nich misji Nav2. Nie zmieniono zdjęć, etykiet ani statusów przeglądu. Wszystkie procesy kolektora zakończyły pracę.

## Aktualizacja: pierwszy trening

Po wizualnym przeglądzie 166 nowych wycinków asystent zapisał indywidualne decyzje z odwołaniami do arkuszy w historii próbek. Wszystkie 200 obserwacji ma obecnie status zatwierdzony. Wcześniejsze zbiorcze zatwierdzenia użytkownika zachowano, dlatego ten zbiór nadal wymaga traktowania jako pilot. Zapisano stały snapshot 120/40/40, wytrenowano baseline oraz dostrajany ResNet18 i wykonano końcową ocenę testową. [Wyniki, instrukcja i ograniczenia](classifier-training.md). EDA sama nie uruchamia ani nie dopuszcza treningu: dedykowany pipeline ponownie waliduje zatwierdzony snapshot.
