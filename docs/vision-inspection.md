# Inspekcja zdjęć kamerą robota

## Przygotowanie i start

Zatrzymaj poprzednią instancję. Na komputerze autora zależności i zdjęcia zostały już przygotowane.

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/stop_cockpit.sh
# Tylko przy pierwszej instalacji na nowym komputerze:
bash scripts/setup_vision.sh
bash scripts/run_cockpit.sh
```

Jedna komenda startowa uruchamia symulację, Nav2, detektor, Bielika, MLflow i otwiera kokpit oraz sterowanie. Zatrzymanie całości: `bash scripts/stop_cockpit.sh` lub Ctrl+C w terminalu kokpitu. Nie aktywuj środowiska detektora w terminalu ROS; kokpit zarządza nim sam.

Detektor używa oddzielnego środowiska `data/vision/env`: PyTorch 2.7.1 CUDA 12.8, torchvision 0.22.1 i Ultralytics 8.3.228. Rozdzielenie unika konfliktów bibliotek ROS i Whisper. Skrypt pobiera oficjalne wagi YOLO11s oraz COCO128 i sprawdza SHA256. Lokalne dane, wagi i środowisko są ignorowane przez Git. Instalacja CUDA zajmuje kilka GB.

## Obsługa

1. Poczekaj na Nav2 i informację `YOLO11s · cuda:0 · kamera aktywna` w kokpicie.
2. W sterowaniu pod celami jazdy wybierz **Inspekcja sektora A**, B lub C.
3. Robot jedzie na pole sektora, odwiedza każdą tablicę P, zatrzymuje się, czeka dwie sekundy, analizuje aktualny obraz i wraca na czerwone pole tego sektora.
4. A obejmuje P1/P2, B obejmuje P3/P4, C obejmuje P5. Po misji robot pozostaje w sektorze; Powrót do bazy jest osobnym poleceniem.
5. W kokpicie rozwiń **Historia detekcji z inspekcji** i wybierz obserwację. Zobaczysz datę, tablicę, zdjęcie z ramkami, klasy, numer obiektu i pewność. Bieżące ramki YOLO są bezpośrednio na lewym podglądzie Kamera robota; nie ma osobnego okna detekcji.
6. Pod ustawieniami magazynu kliknij **Zmień zdjęcia na banerach**, aby zmienić zdjęcia P1 do P5. Ta operacja wymaga bezczynnego robota, odświeża świat i wraca do BASE. Przeszkody i ich układ pozostają. Historia inspekcji jest zachowana.

Zdjęcia przydzielane są bez powtórzeń między pięcioma tablicami, z zestawu 24 fotografii zawierających ludzi, zwierzęta, pojazdy i przedmioty. Po zmianie każde P ma inne zdjęcie niż poprzednio. Wybór jest zachowywany po restarcie. Losowanie przeszkód nie zmienia wybranych zdjęć.

## Model i interpretacja

Kamera FPV: 1280×720, do 8 klatek/s symulacji, lekko skierowana do góry. Pozostałe kamery mają dotychczasowe rozmiary. Faktyczna częstość zależy od wydajności całego komputera i symulacji.

YOLO11s jest gotowym detektorem 80 klas COCO. `person` oznacza człowieka, `dog` psa, `cat` kota. Nie rozpoznaje tożsamości osób ani dowolnych klas poza zestawem treningowym. Próg pewności wynosi 0,30. Procent jest wynikiem pewności modelu, nie gwarancją poprawności ani oceną dokładności całego systemu.

Podgląd używa rozmiaru wejścia 640, zapis inspekcyjny 960, z zachowaniem proporcji. Każda analiza odczytuje obraz ROS kamery FPV przez lokalne API; detektor nie odczytuje etykiet COCO, przypisania zdjęć ani pliku tekstury jako źródła predykcji. Numer, np. `person 1`, identyfikuje wykrycie tylko w jednej klatce. Powtarzane klatki i wizyty nie są sumowane jako różne osoby. Jedna inspekcja zapisuje jeden raport na tablicę.

Niektóre zdjęcia mogą nie dać wykryć lub powodować błędy, szczególnie przy małym obiekcie i obserwacji z dystansu. Nie wymuszamy oczekiwanych klas na podstawie nazwy zdjęcia. Ten etap nie obejmuje SAM ani treningu modelu.

## Historia, czat i MLflow

Raporty są trwałe w tabeli `inspection_reports` bazy misji. Obrazy surowe i z ramkami są w `data/inspections/<id>`. Raport zawiera sektor, tablicę, identyfikatory misji/kroku, czas, pozycję, parametry klatki, listę wykryć, liczby klas oraz model i urządzenie.

W czacie zapytaj np. „Co robot widział w sektorze A?”, „Jakie zdjęcia widział w sektorze B?” lub „Ile detekcji było w sektorze C?”. Tor odczytu bierze ostatnią zapisaną misję pasującego sektora. Podaje datę oraz oddzielne wyniki tablic; nie zgaduje na podstawie fotografii przypisanej do banera. Brak inspekcji jest jawnie zgłaszany. To odczyt uporządkowanej historii, nie RAG wektorowy. Pytania nie uruchamiają ruchu. Publiczna instrukcja Bielika opisuje nowe przyciski i ograniczenia detekcji.

MLflow: eksperyment `roboinspect-yolo`, metryki liczby wykryć i czasu analizy, parametry modelu/urządzenia/progu, identyfikatory misji, sektora i tablicy oraz obraz z ramkami. Awaria MLflow nie zmienia wyniku misji i nie usuwa raportu. Nie raportujemy accuracy/mAP bez oddzielnego oznaczonego zbioru walidacyjnego.

## API i bezpieczeństwo wykonania

- POST `/api/inspect/A` (analogicznie B/C): `{}`, wymagany Idempotency-Key. Powtórzenie żądania zwraca tę samą misję.
- POST `/api/warehouse/pictures`: `{}`, wymagany Idempotency-Key.
- GET `/api/inspections`: trwałe raporty; obrazy pod adresami w raporcie.
- GET `/api/vision` i `/api/vision/frame.jpg`: aktualny stan i obraz z ramkami.

Host/Origin i typ JSON są sprawdzane jak dla innych komend. Wewnętrzny proces detektora nasłuchuje wyłącznie na 127.0.0.1:8766 i wymaga tokenu bieżącego kokpitu. Nie przyjmuje dowolnych URL ani ścieżek obrazów od przeglądarki. Odczytuje wyłącznie kamerę tego kokpitu.

Pydantic dopuszcza analizę P dopiero po kroku dojazdu do tego samego P. Wykonawca sprawdza zatrzymanie, detektor ponownie sprawdza pozycję przy tablicy i aktualność kamery. Późny wynik anulowanej analizy nie przechodzi do następnego celu i nie staje się udanym raportem. Restart nie odtwarza niepewnej jazdy. Anuluj przejazd i tekstowy STOP działają także podczas analizy.

## Testy

```bash
bash scripts/test_project.sh -q
# Przy działającym kokpicie z bezczynnym robotem, test porusza robotem:
.venv/bin/python scripts/check_inspection.py --sectors A B C
```

Lokalny raport i klatki są w `artifacts/inspection-check`. Test sprawdza odwiedzenie każdego P, powrót na pole sektora, rozdzielczość, CUDA, trwałe wyniki i idempotencję. Testy jednostkowe obejmują walidację planów, kolejność, anulowanie, awarię detektora i brak podwójnego liczenia powtórzonych inspekcji.

Dodatkowy odbiór zmiany zdjęć (wymaga bezczynnego kokpitu i środowiska ROS):

```bash
source /opt/ros/jazzy/setup.bash
.venv/bin/python scripts/check_banner_change.py
```

Odbiór STOP podczas analizy, najlepiej gdy robot jest już w sektorze C (robot może dojechać do C):

```bash
.venv/bin/python scripts/check_inspection_cancel.py
```

Pełna lista wersji środowiska detektora jest w `config/vision-requirements.lock`; `vision-requirements.txt` zawiera zależności bezpośrednie. Ziarno zdjęć jest niezależne od układu wyposażenia i pozostaje w `data/vision/selection.json`.

## Wynik odbioru wdrożenia

Przeszły rzeczywiste misje A (P1/P2), B (P3/P4) i C (P5), z powrotem na czerwone pola. Każda klatka miała 1280×720, a detekcja działała na CUDA. Po zmianie zdjęć inspekcja P5 rozpoznała niedźwiedzia z pewnością 91,8%; pomiar MLflow miał status FINISHED. STOP podczas analizy anulował krok i nie zapisał spóźnionego raportu. Sprawdzono oba widoki mobilne przy szerokości 390 px.

- [Wszystkie sektory](verification/inspection-sectors.json)
- [Nowe zdjęcie po zmianie](verification/inspection-after-change.json)
- [Zmiana pięciu rzeczywistych tekstur Gazebo](verification/inspection-banner-change.json)
- [Zapis MLflow](verification/inspection-mlflow.json)
- [STOP w trakcie analizy](verification/inspection-cancel.json)
- [Interfejs i testy](verification/inspection-ui.json)

To odbiór integracji i przykładowych predykcji, nie statystyczna ocena dokładności YOLO.

Po pełnym restarcie potwierdzono rzeczywiste nowe tekstury w Gazebo, zachowanie sześciu raportów i odpowiedź czatu o ostatniej obserwacji sektora C bez nowej misji: [odbiór restartu](verification/inspection-restart.json).

Otwarcie lub odświeżenie panelu sterowania automatycznie rozpoczyna świeżą rozmowę. Oczekujące odpowiedzi poprzedniej rozmowy są anulowane, stare wpisy archiwizowane. Już przyjęta misja robota trwa dalej; samo otwarcie panelu nie jest STOP.

## Zielone pola obserwacji P1 do P5

Każde zielone pole ma 1×1 m, środek zgodny z celem Nav2 P i oznaczenie kierunku patrzenia na tablicę. Zielone pola są widoczne w kamerach, na mapie SLAM/nawigacyjnej i schemacie 2D. Są wyłącznie oznaczeniem podłogi, bez kolizji i bez przeszkody dla lidaru. Zapisane wcześniej losowe układy również otrzymują pola przy starcie. Czerwone pola sektorów nadal służą jako miejsca powrotu po inspekcji; w sektorze C pole P5 mieści się w dotychczasowej strefie C.
