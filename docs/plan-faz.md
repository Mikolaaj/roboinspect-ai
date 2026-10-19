# RoboInspect AI — plan realizacji krok po kroku

Status: plan docelowy; stan wykonania opisują README.md i docs/phase3-results.md. Data: 17.10.2026.

Aktualizacja zakresu: na życzenie użytkownika podstawowy kokpit z trzema kamerami
i panel A/B/C/BASE przeniesiono z fazy 4 do bieżącej fazy 3. Dodatkowe
wygładzanie kamery, nakładki trasy oraz dalsze pomiary fazy 4 pozostają
odrębnymi ulepszeniami.

Cel: robot mobilny w wirtualnym hangarze Gazebo, sterowany poleceniami tekstowymi lub głosowymi, wykonujący inspekcje za pomocą własnego modelu wizyjnego. Gotowy LLM interpretuje tekst, gotowy STT transkrybuje mowę, a własne eksperymenty ML dotyczą obrazów. Projekt obejmuje testy, MLOps, CI/CD i instrukcję odtworzenia na innym komputerze.

Uzupełnienie z 18.10.2026: w późniejszej percepcji dodamy YOLO do detekcji
oraz SAM do segmentacji obiektów z kamery robota. To zaplanowane funkcje,
jeszcze niezaimplementowane. Podział ról, dane i pomiary: [perception-plan.md](perception-plan.md).

Aktualizacja czatu: bieżący czat tekstowy Bielik znajduje się po prawej stronie
**panelu sterowania**, zgodnie z najnowszą decyzją użytkownika. Dotychczasowe
sterowanie i historia są po lewej; trzy kamery pozostają w kokpicie.
Instrukcja: [bielik-chat.md](bielik-chat.md). Poniższy szkic opisuje wcześniejszy
układ docelowy; nie jest zrzutem aktualnego interfejsu.

## Docelowy ekran operatora

Trzy kolumny, trzy rzeczywiste widoki symulacji i czat w trzeciej kolumnie:

```text
+---------------------+---------------------+--------------------------+
| 1. KAMERA ROBOTA     | 2. TRZECIA OSOBA     | 3. MONITORING HANGARU     |
|                     |                     |                          |
| Obraz z kamery RGB  | Kamera za/nad       | Kamera wysoko nad halą   |
| na robocie          | robotem, podążająca | Cały hangar, sektory,    |
| Wynik inspekcji     | za jego ruchem      | robot i trasa/markery    |
|                     |                     +--------------------------+
|                     |                     | CZAT Z ROBOTEM           |
|                     |                     | Historia i statusy       |
|                     |                     | [Wpisz polecenie...]     |
|                     |                     | [Mikrofon] [Wyślij]      |
+---------------------+---------------------+--------------------------+
| Misja | krok | sektor | połączenie | czas obserwacji | STOP | raport |
+--------------------------------------------------------------------+
```

Widok z góry to obraz całej hali z wirtualnej kamery monitoringu. Dodatkowa mapa 2D z trasą jest nakładką lub przełączanym widokiem, a nie zamiennikiem tego obrazu. Trzecioosobowa kamera ma podążać za robotem; nie wystarczy statyczny zrzut ani wyłącznie okno Gazebo.

Docelowo panel działa w przeglądarce, a Gazebo odpowiada za fizykę i renderowanie. Trzy strumienie i UI wymagają osobnej integracji — nie zakładamy, że samo uruchomienie Gazebo automatycznie tworzy taki dashboard. Wersja deweloperska może korzystać z osobnych okien, ale końcowy scenariusz obejmuje jeden ekran operatora.

## Świat i zakres funkcjonalny

- Baza / punkt startu i powrotu robota.
- Sektor A — serwisowy: panele P1 i P2.
- Sektor B — inspekcyjny: panele P3 i P4 z wariantami defektów.
- Sektor C — magazynowy: regały, skrzynie, palety i panel P5.
- Korytarze łączące sektory oraz oznaczenia nazw widoczne w symulacji.
- Stałe przeszkody: ściany, słupy, regały, skrzynie.
- Przeszkoda zmienna: skrzynia/paleta blokująca jeden korytarz.
- Wariant scenariusza z całkowicie niedostępnym punktem inspekcji.
- Strefa wyłączona z nawigacji i kilka zdefiniowanych pozycji inspekcji z orientacją kamery.

Przykłady poleceń: „Jedź do sektora B”, „Sprawdź panel P3”, „Obejrzyj wszystkie panele w sektorze A i wróć do bazy”, „Pokaż raport ostatniej misji”. Polecenia niejednoznaczne wymagają doprecyzowania. Nazwy sektorów i współrzędne są w konfiguracji, nie w pamięci LLM.

Jeden robot i znana mapa stanowią zakres zaliczeniowy. SLAM od zera, flota, manipulator i dron są rozbudową. Panele w pierwszej wersji są oceniane ze zdefiniowanych punktów obserwacji; ogólne wykrywanie dowolnego panelu w obrazie nie jest warunkiem podstawowego demo.

## Zasada przechodzenia przez fazy

Każda faza ma zadania, rezultat i sprawdzalne kryterium zakończenia. Przed przejściem dalej zapisujemy działającą wersję w repo, aktualizujemy instrukcję i rejestrujemy wynik sprawdzenia. Fazy 0–15 tworzą pełną wersję zaliczeniową. Faza 16 jest dodatkowym programem eksperymentów z alternatywnymi narzędziami kursu.

### Faza 0 — wymagania i sprawdzenie środowiska

Zadania:

- Ustalić sprzęt, system, zasoby GPU/RAM i działanie renderowania Gazebo.
- Sprawdzić kompatybilny zestaw ROS 2/Gazebo/Nav2 na małym przykładzie i zapisać konkretne wersje.
- Spisać trzy widoki, komendy, sektory, klasy defektów i scenariusze błędów.
- Wybrać gotowe modele/backendy LLM, STT i TTS; określić tryb lokalny/API i sposób konfiguracji.
- Ustalić mierniki i budżet wywołań; cele liczbowe doprecyzować po baseline.

Rezultat: docs/requirements.md, docs/environment.md i decyzje architektoniczne.

Kryterium: działa prosty przykład symulacji, zapisano wersje i uzgodniono zakres pierwszego demo. Jeśli używany jest kontener lub maszyna wirtualna, od razu sprawdzić GPU, okna i komunikację ROS.

### Faza 1 — repozytorium, struktura, dokumentacja i pierwsze CI

Zadania:

- Utworzyć repozytorium Git i podstawową strukturę monorepo.
- Dodać README, licencję, .gitignore, .env.example i zasady obsługi sekretów.
- Skonfigurować uv, pyproject.toml, lockfile i wspólne komendy deweloperskie.
- Zdefiniować podstawowe kontrakty Pydantic: Sector, RobotState, MissionPlan i MissionStep.
- Dodać Ruff, kontrolę typów i pierwszy sensowny test kontraktu.
- Uruchomić GitHub Actions sprawdzające kod przy pull requestach.
- Zapisać plan faz jako zadania/issues; samo utworzenie zdalnego repo wymaga osobnej realizacji, nie następuje przez powstanie tego dokumentu.

Rezultat: uruchamialny szkielet i zielone CI.

Kryterium: świeży klon pozwala odtworzyć środowisko i uruchomić sprawdzenia według README; w repo nie ma kluczy ani dużych danych.

### Faza 2 — hangar, sektory i przeszkody

Zadania:

- Zbudować świat Gazebo: podłoga, ściany, oświetlenie i wyposażenie.
- Dodać bazę, sektory A/B/C, panele i punkty inspekcji.
- Zdefiniować geometrię kolizji, nie tylko wygląd obiektów.
- Przygotować konfigurację nazw, współrzędnych, orientacji i granic sektorów.
- Dodać scenariusze: normalny przejazd, obejście przeszkody i brak dojazdu.
- Rozdzielić wizualne oznaczenia operatora od obrazu używanego do uczenia; etykiety defektów nie mogą być widoczną podpowiedzią dla klasyfikatora.

Rezultat: wersjonowane pliki świata i scenariuszy, sectors.yaml oraz ilustracja układu.

Kryterium: za każdym uruchomieniem można odtworzyć ten sam scenariusz i zweryfikować położenie wszystkich punktów; robot fizycznie nie przenika przeszkód.

### Faza 3 — robot, sensory i nawigacja

Zadania:

- Wstawić gotowy model mobilnego robota, z odpowiednimi gabarytami i kolizjami.
- Skonfigurować kamerę RGB, odometrię i sensor odległości potrzebny nawigacji.
- Uporządkować układy współrzędnych i czas symulacji.
- Skonfigurować znaną mapę, lokalizację i Nav2.
- Wykonać dojazd do nazwanych punktów, powrót i anulowanie zadania bez LLM.
- Sprawdzić omijanie przeszkody i raportowanie braku trasy.

Rezultat: deterministyczny adapter nawigacji i pliki launch.

Kryterium: skrypt/przycisk prowadzi robota baza -> B -> P3 -> baza; niedostępny cel zwraca błąd, a STOP przerywa aktywną misję. Nie obiecywać idealnej nawigacji poza zdefiniowanymi scenariuszami bez pomiarów.

### Faza 4 — trzy kamery i pierwszy dashboard

Zadania:

- Udostępnić obraz kamery na robocie.
- Dodać kamerę nad/za robotem, z podążaniem i wygładzaniem ruchu.
- Dodać stałą kamerę wysoko nad hangarem, obejmującą całą halę.
- Zbudować wspólny frontend w trzech kolumnach; w trzeciej zostawić miejsce na czat pod monitoringiem.
- Zintegrować strumienie obrazu przez jawnie wybrany i opisany most do przeglądarki.
- Dodać czas ostatniej klatki, status połączenia i stan „obraz niedostępny”.
- Dodać telemetrię, oznaczenia sektorów, cel i trasę; sprawdzić zgodność układów współrzędnych przy nakładkach.
- Wyznaczyć rozsądne FPS/rozdzielczość i ograniczyć buforowanie; cel dobrać po pomiarze na docelowym komputerze.

Rezultat: działający panel trzech perspektyw bez chatbotowego sterowania.

Kryterium: jeden przejazd robota widać równocześnie z przodu, z trzeciej osoby i z góry; kamera śledząca rzeczywiście podąża, a widok hangaru nie gubi robota. Opóźnienia i zużycie GPU są zmierzone. To wczesna faza, ponieważ trzy widoki są ważnym wymaganiem i ryzykiem integracyjnym.

### Faza 5 — API i trwałe wykonanie misji

Stan 18.10: wykonany rdzeń 5a — uv, testy, workflow CI, FastAPI, Pydantic,
własny wykonawca sekwencji i SQLite. PostgreSQL, Pydantic Graph i tracing
pozostają do wykonania. [Instrukcja i zakres](missions.md).

Zadania:

- Uzupełnić zaległe elementy fazy 1: pyproject/uv i lockfile, Ruff, pytest oraz podstawowe CI; samo istnienie repo i skryptów testowych nie oznacza ich wykonania.
- Zbudować FastAPI: sektory, stan robota, tworzenie/status/anulowanie misji i wyniki.
- Wprowadzić kontrakty Pydantic i walidację domenową.
- Zaimplementować wykonawcę misji / Pydantic Graph ze stanami i obsługą błędów.
- Dodać PostgreSQL do zapisywania statusów i historii.
- Dodać idempotency key, pojedynczego właściciela robota i powiązanie zdarzeń z mission_id.
- Przesyłać statusy do dashboardu; oddzielić telemetrię od dużych strumieni wideo.
- Podłączyć logowanie i tracing OpenTelemetry/Logfire.

Rezultat: kompletna misja uruchamiana przez API, jeszcze z planu utworzonego bez LLM.

Kryterium: duplikat żądania nie uruchamia drugiego przejazdu; restart API nie kasuje historii, a stan wykonywanej misji jest uzgadniany z adapterem. Utrata połączenia nie jest raportowana jako sukces.

### Faza 5b — SLAM przed czatem

- Osobny tryb mapowania SLAM Toolbox, bez AMCL i Nav2.
- Kontrolowany obchód hali z pozycją SLAM i kontrolą przeszkód lidarem.
- Podgląd mapy, zapis rastra i grafu, jawne uzgodnienie układów współrzędnych.
- Ponowny start AMCL + Nav2 na zapisanej mapie i test przejazdów.
- Instrukcja: [slam.md](slam.md). SLAM nie zastępuje dalszych zadań PostgreSQL i tracing.

### Faza 6 — chatbot tekstowy i gotowy LLM

Zadania:

- Dodać działający czat w trzeciej kolumnie.
- Podłączyć gotowy LLM przez Pydantic AI i konfigurację dostawcy/modelu.
- Umożliwić odczyt sektorów i stanu oraz tworzenie typowanego MissionPlan.
- Obsłużyć „jedź do B”, inspekcję P3, powrót i złożoną misję z kilku kroków.
- Pytać o doprecyzowanie, kiedy brakuje celu.
- Oddzielić odpowiedź konwersacyjną od potwierdzonego statusu wykonania.
- Utworzyć zbiór komend PL/EN i baseline ewaluacyjny.
- Zapisywać w MLflow wyniki porównania promptów/modeli: konfigurację, wersję zbioru, poprawność planu, czas i koszt, jeśli dostępny.

Rezultat: pierwsza pionowa ścieżka tekst -> gotowy LLM -> walidowany plan -> ruch robota -> status w czacie.

Kryterium: ustalony zestaw komend działa na symulatorze; nieistniejący sektor nie powoduje wymyślenia współrzędnych; czat nie ogłasza zakończenia przed zdarzeniem z wykonawcy.

### Faza 7: mikrofon, gotowy STT i odpowiedzi głosowe

Stan: mikrofon i lokalny Whisper są wdrożone, włącznie z edycją transkrypcji i pomiarami MLflow. TTS pozostaje do dodania. Poniższa lista opisuje pełny zakres fazy.

Zadania:

- Dodać push-to-talk, podgląd stanu nagrywania i wysyłkę audio.
- Podłączyć gotowy model STT; oba wejścia prowadzą do tego samego kontraktu tekstowego.
- Pokazywać rozpoznaną treść, umożliwić korektę i ograniczyć przypadkowe wysłania.
- Dodać TTS krótkich odpowiedzi i wyciszanie odtwarzania podczas nagrywania, aby ograniczyć pętlę podsłuchiwania własnego głosu.
- Obsłużyć zgodę na mikrofon i wymagania przeglądarki; opisać localhost/HTTPS dla trybu sieciowego.
- Rozdzielić obróbkę audio od głównej pętli API, z użyciem workera/kolejki tam, gdzie potrzebne.
- Porównać poprawność transkrypcji i wynikowej misji dla własnych nagrań; wyniki eksperymentów zapisać w MLflow.

Rezultat: „Jedź do sektora C” wypowiedziane do mikrofonu uruchamia tę samą ścieżkę co prompt.

Kryterium: działa nagranie, transkrypcja, korekta, plan, przejazd i odpowiedź; odmowa dostępu do mikrofonu pozostawia działający czat tekstowy.

### Faza 8 — wiedza techniczna, RAG i historia

Zadania:

- Przygotować własne instrukcje inspekcji i opisy paneli/sektorów.
- Zaimplementować ingest, chunking, embeddingi i indeks, np. ChromaDB.
- Zwracać odpowiedzi z identyfikatorem dokumentu/sekcji.
- Łączyć pytania z historią misji i raportami w PostgreSQL.
- Dodać ocenę pobranych dokumentów i zgodności odpowiedzi z dowodami.
- Dodać cache odpowiedzi/wyników odczytu z wersją danych; nie cache'ować statusu robota tak, jak statycznej instrukcji.

Rezultat: „Jak sprawdzić panel P3?” i „Co wykryłeś w poprzedniej misji?” mają odpowiedzi oparte na właściwych danych.

Kryterium: brak dokumentu lub obrazu prowadzi do jawnego braku informacji; instrukcja nie może zmieniać dozwolonych akcji robota. Poprawność RAG oceniona na małym zbiorze pytań.

### Faza 9 — dane do własnego modelu i EDA

Zadania:

- Przygotować warianty paneli: bez defektu, rysa, pęknięcie.
- Generować obrazy z różnych scen, materiałów, oświetlenia i kątów.
- Zapisywać etykiety, metadane, seed i manifest wersji danych.
- Przeanalizować liczności klas, błędne obrazy, duplikaty i wpływ warunków.
- Podzielić dane po scenach/instancjach/rodzinach tekstur; odseparować test przed strojeniem.
- Przygotować zestaw o zmienionych warunkach do badania odporności.
- Uruchomić MLflow tracking z trwałym przechowywaniem metadanych i artefaktów; to osobna funkcja od bazy aplikacji, nawet jeśli korzysta z tej samej instancji PostgreSQL.
- Przygotować bounding boxy dla docelowych klas YOLO oraz referencyjne maski do oceny SAM; dane syntetyczne lub ręczne adnotacje są podstawą oceny, maski wygenerowane przez SAM nie zastępują niezależnego ground truth.

Rezultat: odtwarzalny dataset, raport EDA i jawny split train/validation/test.

Kryterium: można odtworzyć dane z konfiguracji; podobne klatki tej samej sceny nie są rozdzielone między trening i test, a etykiety nie trafiają do wejścia modelu.

### Faza 10 — trening, Optuna i MLflow

Zadania:

- Porównać HOG + SVM, małą CNN w PyTorch i transfer learning.
- Dodać augmentacje, sensowny baseline i pomiar inferencji.
- Dobrać hiperparametry przez Optuna na walidacji.
- Logować w MLflow parametry, metryki, wersje danych/kodu i artefakty.
- Zmierzyć macro-F1, recall defektów, fałszywe alarmy i macierz pomyłek.
- Wybrać model według jawnych kryteriów jakości i czasu.
- Zarejestrować wybraną wersję, zapisać model card i końcową ocenę na teście.
- Dodać baseline detekcji YOLO i, jeśli potrzebne, fine-tuning dla paneli/defektów; nie zakładać, że gotowe wagi rozpoznają nasze klasy przemysłowe.
- Porównać konfiguracje YOLO + SAM: jakość detekcji/masek, opóźnienie i VRAM wspólnie z działającym Gazebo. Wersję i rozmiar SAM dobierzemy po pomiarach na RTX 4060 8 GB.

Rezultat: porównanie algorytmów i wersjonowany model gotowy do wykorzystania przez usługę.

Kryterium: trening uruchamia się z konfiguracji, wynik jest powiązany z danymi i kodem, a zbiór testowy nie służy do wyboru parametrów. Cele jakości ustalić po baseline; nie wpisywać wymyślonych wyników do README.

### Faza 11 — inspekcja w działającej misji i raporty

Zadania:

- Dodać InspectPanel: dojazd, stabilizacja kadru, pobranie aktualnego obrazu i inferencja.
- Podłączyć YOLO do lokalizacji obiektu oraz SAM do wyznaczania jego maski z boxa/punktu; maskę i box wyświetlać jako przełączaną nakładkę FPV.
- Zachować własny model oceny defektów: maska obiektu nie oznacza automatycznego rozpoznania uszkodzenia. Łączyć detekcję, segmentację i ocenę z tym samym kadrem i czasem.
- Uruchamiać percepcję w osobnym workerze z ograniczoną kolejką; zmierzyć tryb klatek okresowych i inspekcji po zatrzymaniu. Nie blokować Nav2 ani trzech podglądów inferencją.
- Obsłużyć brak obrazu, zbyt stary obraz i niską pewność wyniku.
- Powiązać każdy wynik z panelem, misją, obrazem i wersją modelu.
- Wyświetlać wynik w panelu FPV i na monitoringu hangaru.
- Dodać raport z miniaturami, wykonanymi/niewykonanymi punktami i błędami.
- Generować opis tekstowy/TTS na podstawie zapisanych danych, bez dopisywania defektów przez LLM.
- Zachować artefakty lokalnie lub w MinIO, z identyfikatorami dostępnymi przez API.

Rezultat: pełna misja inspekcyjna tekstem lub głosem.

Kryterium: na scenariuszu ze znanym defektem można prześledzić komendę -> misję -> kadr -> wersję modelu -> raport. Nie zakładamy, że model zawsze trafia; błędy są mierzone i zachowane do analizy.

### Faza 12 — testy całego systemu, błędy i ewaluacja

Zadania:

- Rozszerzyć testy jednostkowe i integracyjne pisane w poprzednich fazach.
- Dodać testy symulacji: normalny przejazd, przeszkoda, brak trasy, anulowanie.
- Testować brak LLM/STT/kamery/bazy, utratę telemetrii i ponowne wysłanie żądania.
- Sprawdzić spójność trzech kamer, komunikatów czatu i statusu misji.
- Dodać ewaluacje planów i RAG, Pydantic Evals/LLM-as-a-judge tam, gdzie uzasadnione.
- Mierzyć misje zakończone, częściowe i błędne, opóźnienia, koszty, poprawność raportów i reakcję na STOP.
- Dodać śledzenie całej ścieżki przez mission_id w OpenTelemetry/Logfire.

Rezultat: raport jakości systemu i lista ograniczeń.

Kryterium: testy mają niezależne oczekiwane wyniki; sukces nawigacji potwierdza wykonawca/symulator, nie sam tekst LLM. Zachowano rzeczywiste wyniki ewaluacji w MLflow.

### Faza 13 — odtwarzalne uruchomienie i Docker Compose

Zadania:

- Konteneryzować API, UI, percepcję i zadania offline.
- Przygotować Compose dla PostgreSQL, Redis, MLflow i storage według potrzeb.
- Dodać healthchecki, wolumeny, konfigurację i obsługę gotowości usług.
- Przypiąć wersję modelu; aplikacja nie pobiera bez kontroli zmiennego „najnowszego” artefaktu przy każdym starcie.
- Zdefiniować granicę: Gazebo/ROS lokalnie lub w przetestowanym profilu kontenerowym, usługi aplikacyjne w Compose.
- Dodać mały profil demo z przykładowymi danymi i gotowym modelem; trening nie jest wymagany do pierwszego uruchomienia.
- Zweryfikować most API/kamer między środowiskami i dokumentować porty.

Rezultat: powtarzalny start oraz zatrzymanie systemu z zachowaniem danych.

Kryterium: z nowego klonu da się uruchomić demo według instrukcji; żaden krok nie zależy od nieopisanego pliku ani ręcznej zmiany w kontenerze. GPU i renderer mają jawne wymagania/profil.

### Faza 14 — Kubernetes i pełne CI/CD

Zadania:

- Wdrożyć aplikacyjną część na lokalny klaster.
- Przygotować Deployment, Service, ConfigMap, Secret, PVC i sondy.
- Dodać Kustomize: baza i overlaye dev/prod-demo.
- Ustawić limity zasobów i kontrolowane rolling updates.
- Skonfigurować GitHub Actions: testy -> obrazy -> registry z tagiem SHA -> dev -> smoke test -> prod-demo.
- Zapewnić działający runner z dostępem do klastra i opisać jego konfigurację.
- Sprawdzić rollback oraz zgodność wersji API i modelu.
- Skierować aplikację do jednego adaptera robota; skalowanie nie może tworzyć wielu właścicieli tej samej misji.
- HPA demonstrować na stateless API/percepcji po pomiarze, nie na pojedynczym symulatorze lub sterowniku robota.

Rezultat: rzeczywiście wykonane automatyczne wdrożenie i test powdrożeniowy.

Kryterium: istnieje zapis udanego pipeline'u, dostępne demo i sprawdzona procedura cofnięcia. Klaster jest połączony z lokalną symulacją i trzema widokami; sam komplet YAML nie wystarcza.

### Faza 15 — dokumentacja końcowa i odbiór na drugim komputerze

Zadania:

- Uporządkować README, architekturę, API, dane, eksperymenty i ograniczenia.
- Przeprowadzić uruchomienie na czystym profilu lub drugim komputerze z obsługiwanym systemem/GPU.
- Skorygować instrukcję według wykrytych braków; odnotować dokładne przetestowane środowisko.
- Nagrać demo trzech widoków, czatu, mikrofonu, inspekcji i raportu.
- Przygotować krótkie omówienie MLflow, testów i CI/CD.
- Wykonać release repo i dołączyć wyniki pomiarów, a nie planowane wartości.

Rezultat: repozytorium do oceny z kompletną instrukcją odtworzenia.

Kryterium: druga osoba wykonuje scenariusz tekstowy i głosowy bez pomocy autora; w repo opisano każdy wymagany krok, przewidywane ekrany i sposoby sprawdzenia poprawnego działania.

### Faza 16 — dodatkowe eksperymenty z narzędziami kursu

Ta faza rozszerza pokrycie narzędzi, które dublują rolę podstawowego stosu lub wymagają dodatkowego zakresu. Każdy eksperyment otrzymuje osobny katalog i wyniki, aby nie destabilizować działającego demo.

- LangGraph: alternatywna implementacja małego workflow i porównanie z Pydantic Graph na tym samym zbiorze zadań.
- Agno: drugi backend agenta, oceniany tymi samymi komendami co Pydantic AI.
- Haystack i BM25: alternatywny pipeline RAG i porównanie wyszukiwania słownego, wektorowego oraz hybrydowego.
- Spark/PySpark i Spark SQL: przetwarzanie większego wygenerowanego archiwum telemetrii; raport czasu misji, błędów i metryk według sektorów. Przy małych danych uwzględnić koszt uruchomienia i porównać z prostszym rozwiązaniem.
- MCP/FastMCP: serwer odczytu sektorów, statusów i raportów; akcje przechodzą przez istniejący walidator misji.
- ONNX: eksport wybranego modelu, kontrola zgodności predykcji i benchmark inferencji, ewentualnie na Jetsonie.
- Prometheus/Grafana: dashboard metryk usług i misji; Helm/Argo CD jako dodatkowy wariant pakowania/wdrażania.
- Conda: udokumentowany alternatywny profil treningowy, jeśli wymagany; główna ścieżka projektu pozostaje przypięta i testowana.

Kryterium: każde porównanie ma stały zbiór testowy, konfigurację i wyniki w MLflow. Dodanie frameworka bez mierzalnego zastosowania nie jest uznawane za ukończenie eksperymentu.

## MLflow w całym projekcie

| Obszar | Co zapisujemy w MLflow |
|---|---|
| Gotowy LLM | Nazwa/model/dostawca, wersja promptu i zbioru, poprawność planu, koszt i opóźnienie |
| Głos | Konfiguracja STT, zbiór nagrań, błędy transkrypcji i poprawność wynikowej misji |
| RAG | Konfiguracja chunkingu/retrievera, jakość pobierania i odpowiedzi |
| Własny model CV | Parametry, dane i splity, metryki, obrazy, macierz pomyłek, model i wersja |
| System | Wersje usług/modeli, scenariusze, skuteczność i czas misji |
| Eksperymenty dodatkowe | Porównania backendów, workflow, wyszukiwania, eksportu i przetwarzania danych |

MLflow służy do eksperymentów i artefaktów. Bieżąca historia i stan misji pozostają w bazie aplikacji, a tracing usług w OpenTelemetry/Logfire. Nie obiecujemy automatycznego śledzenia każdej biblioteki: tam, gdzie brak gotowej integracji, zapisujemy jawne parametry, metryki i artefakty własnym kodem. Nie zapisujemy sekretów; treści/nagrania eksperymentalne podlegają świadomie ustalonej retencji.

## Struktura repozytorium

```text
roboinspect-ai/
  README.md
  pyproject.toml
  uv.lock
  .env.example
  apps/operator-ui/
  services/api/
  services/mission-worker/
  services/perception/
  services/audio-worker/
  packages/contracts/
  packages/mission-domain/
  packages/agents/
  packages/robot-adapter/
  robotics/ros2_ws/src/
  simulation/worlds/
  simulation/models/
  simulation/cameras/
  simulation/scenarios/
  config/sectors.yaml
  config/inspection-points.yaml
  ml/data_pipeline/
  ml/eda/
  ml/training/
  ml/evaluation/
  evals/commands/
  evals/audio/
  evals/rag/
  experiments/alternatives/
  knowledge/procedures/
  tests/unit/
  tests/integration/
  tests/simulation/
  tests/e2e/
  deploy/compose/
  deploy/k8s/base/
  deploy/k8s/overlays/dev/
  deploy/k8s/overlays/prod-demo/
  scripts/
  docs/
  .github/workflows/
```

## Co musi zawierać instrukcja uruchomienia

Instrukcja powstaje od fazy 1 i jest aktualizowana po każdej fazie. Ostatecznie obejmuje:

1. Sprawdzony system, wersje ROS/Gazebo, wymagania CPU/RAM/GPU i wolne miejsce.
2. Klonowanie repo, zależności, lockfile i przygotowanie środowiska.
3. .env.example i objaśnienia: model LLM, STT/TTS, klucze, adresy, porty i ustawienia; bez prawdziwych sekretów.
4. Pobranie małych danych demo i przypiętej wersji modelu; alternatywnie pełny trening.
5. Uruchomienie storage, baz, kolejki i MLflow.
6. Uruchomienie Gazebo, robota, Nav2, kamer i adaptera.
7. Start API, workerów i panelu operatora.
8. Adres dashboardu i sprawdzenie trzech widoków.
9. Dostęp do mikrofonu, audio, localhost/HTTPS i rozwiązanie problemów z uprawnieniami.
10. Pierwszy scenariusz tekstowy, potem głosowy — z oczekiwanymi zdarzeniami i raportem.
11. Generowanie danych, EDA, baseline, tuning, trening i odczyt eksperymentów w MLflow.
12. Uruchamianie testów i ewaluacji, z rozróżnieniem atrap i płatnych usług.
13. Start w Compose i wdrożenie Kubernetes wraz z wymaganym runnerem CI/CD.
14. Logi/tracing, diagnostykę pustego obrazu, brakującego modelu, błędnej nawigacji i braku połączenia.
15. Zatrzymanie, wznowienie i reset scenariusza; oddzielne polecenie kasowania danych z opisem skutków.
16. Ograniczenia: symulacja, dane syntetyczne, niepewność modeli i nieobsługiwane platformy.
17. Licencje i pochodzenie robotów, światów, modeli, bibliotek oraz danych.

Projektowane komendy docelowe mogą mieć formę `make doctor`, `make demo`, `make test`, `make train`, `make eval` i `make down`. W tej chwili to nazwy planowanych interfejsów, nie istniejące polecenia. Instrukcja końcowa musi pokazywać faktycznie wykonane i sprawdzone komendy, łącznie z krokami zależnymi od systemu.

## Kolejność i plan czasowy

Orientacyjny podział do 4.12.2026, przy znacznym regularnym nakładzie pracy i gotowym modelu robota:

| Tydzień | Priorytet |
|---|---|
| 1 | Fazy 0–3: środowisko, repo, hangar i przejazd |
| 2 | Fazy 4–6: trzy widoki, API i czat tekstowy |
| 3 | Fazy 7–9: głos, mały RAG i dane/EDA |
| 4 | Fazy 10–11: trening, MLflow i pełna inspekcja |
| 5 | Faza 12 i dopracowanie: testy, błędy, ewaluacje i UI |
| 6 | Fazy 13–14: Compose, Kubernetes i wykonane CI/CD |
| 7 | Faza 15: drugi komputer, poprawki, dokumentacja i demo |

Faza 16 wymaga dodatkowego czasu lub ograniczenia innych rozszerzeń. Trzy strumienie i dopracowany panel zwiększają wcześniejszy zakres: aktualna orientacyjna estymacja dla faz 0–15 to 150–220 godzin, zależnie od sprzętu i znajomości ROS/web. Wynik faz 0–4 pozwoli tę estymację urealnić. To plan, nie gwarancja terminu.

Kamienie milowe:

- M1: hangar, robot, trzy widoki i ręcznie zadany przejazd.
- M2: „Jedź do B” z klawiatury i mikrofonu działa na tym samym wykonawcy.
- M3: własny model ocenia obrazy, a wynik jest w raporcie i MLflow.
- M4: projekt przechodzi testy, wdrożenie i uruchomienie z instrukcji na czystym środowisku.

## Scenariusz końcowej prezentacji

1. Uruchomienie repo według README i pokazanie trzech widoków.
2. Tekstowe „Jedź do sektora B” oraz śledzenie przejazdu.
3. Głosowe „Sprawdź panel P3 i wróć do bazy”.
4. Wynik modelu, obraz dowodowy, raport i odpowiedź głosowa.
5. Niejasna komenda i pytanie doprecyzowujące.
6. Przeszkoda / niedostępny punkt i prawidłowa obsługa niepowodzenia.
7. STOP podczas ruchu i potwierdzenie anulowania.
8. MLflow: porównanie modeli i konfiguracja użytej wersji.
9. CI/CD: testy, obraz, wykonany deployment i rollback.
10. Ograniczenia oraz kierunki dalszego rozwoju.

## Aktualizacja: lokalna mowa i strefy inspekcji

Mikrofon i Whisper small są wdrożone. Rozpoznany tekst operator sprawdza i wysyła do tego samego czatu. Dodano lokalne metryki ASR w MLflow oraz po jednej czerwonej strefie przed tablicami w A/B/C. Następne prace: RAG operatora, dane/EDA, YOLO i SAM, własny model defektów, pełne raporty inspekcji, następnie Docker, Kubernetes i CD. Instrukcja: [głos i strefy](voice-and-inspection-zones.md).

## Aktualizacja 19.10: RAG

Wdrożono podstawę fazy 8: lokalne wyszukiwanie instrukcji i odpowiedzi Bielika ze źródłami, indeks na CPU, ewaluacja i MLflow. Szczegóły: [rag.md](rag.md). Gotowy YOLO i inspekcje również działają. Następnie SAM, dane/EDA i własny model, a później konteneryzacja oraz deployment.
