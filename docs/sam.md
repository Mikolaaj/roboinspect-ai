# Segmentacja SAM w inspekcjach

SAM 2.1 Tiny wyznacza maski obiektów wskazanych przez YOLO11s. Używa dokładnie tej samej surowej klatki kamery i ramek wykryć. Segmentacja odbywa się podczas postoju przed tablicą, a nie na każdej klatce wideo. Podczas jazdy lewy obraz kamery nadal pokazuje bieżące ramki YOLO.

## Uruchomienie i sprawdzenie

Na obecnym komputerze model jest już pobrany. Na nowym klonie wykonaj standardowe przygotowanie wizji (`bash scripts/setup_vision.sh`, które teraz obejmuje SAM). Jeżeli środowisko YOLO jest już gotowe, wystarczy:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/setup_sam.sh
```

Zatrzymanie całego projektu:

```bash
bash scripts/stop_cockpit.sh
```

Poczekaj na potwierdzenie zamknięcia. Uruchomienie kokpitu i sterowania:

```bash
bash scripts/run_cockpit.sh
```

W panelu odśwież stronę przez Ctrl+Shift+R. Wybierz Inspekcja sektora A (P1 i P2), B (P3 i P4) lub C (P5). Robot podjedzie kolejno do zielonych pól, zatrzyma się, wykona YOLO oraz SAM i wróci na czerwone pole sektora.

W kokpicie lub panelu sterowania rozwiń Historię detekcji z inspekcji. Wybierz nową obserwację. Widok obserwacji pozwala przełączyć YOLO + SAM na Tylko YOLO. Nakładka zawiera kolorowe półprzezroczyste maski, kontury i oryginalne etykiety YOLO. Przy obiekcie widać liczbę pikseli maski i jej udział w całym obrazie. Starsze obserwacje pozostają dostępne jako YOLO, z informacją o braku segmentacji.

Zapytaj czat: „Ile masek zapisano w ostatniej inspekcji sektora A?” lub „Jak działa segmentacja SAM?”. Pierwsze pytanie czyta zapisane wyniki inspekcji, drugie korzysta z instrukcji RAG. Zmiana instrukcji automatycznie unieważnia lokalny indeks RAG.

## Artefakty i dane

Każda nowa obserwacja ma:

- `raw.jpg`: surową klatkę kamery;
- `annotated.jpg`: ramki YOLO;
- `segmented.jpg`: maski SAM, kontury i ramki;
- `masks.png`: indeks obiektu na podglądzie (0 to tło, numer od 1 to kolejność wykrycia YOLO);
- `masks.npz`: dokładne, osobne maski każdego wykrycia, spakowane bitowo, z zachowaniem nakładania się obiektów.

Ostatnie trzy artefakty powstają, gdy SAM przetworzy ramki. Maski PNG/JPEG służą do podglądu. Pierwszy obiekt ma pierwszeństwo na wspólnych pikselach, ale NPZ zachowuje wszystkie nakładające się maski. Plik można pobrać przyciskiem Pobierz maski. Odtworzenie dla analizy danych:

```python
import numpy as np
with np.load("masks.npz", allow_pickle=False) as data:
    masks = np.unpackbits(data["packed"], axis=2, count=1280).astype(bool)
```

Szerokość odczytaj z raportu (`width`), zamiast zakładać 1280 dla innych danych. Wiersz `masks[i]` odpowiada `detections[i]` także wtedy, gdy model nie zwrócił poprawnej maski: wtedy maska jest pusta.

Metadane i adresy artefaktów są w trwałym raporcie SQL. Pydantic sprawdza powiązanie z wykryciami, liczbę masek, rozmiary i powierzchnię. Aplikacja dodatkowo weryfikuje obrazy i zawartość ograniczonego archiwum NPZ; nie odczytuje obiektów pickle. Anulowana inspekcja nie jest dopisywana do historii po otrzymaniu spóźnionego wyniku.

## Statusy i ograniczenia

`complete` oznacza niepustą maskę dla każdego wykrycia YOLO. `partial` oznacza brak maski dla części wykryć. To kompletność przetwarzania, nie pomiar poprawności. `no_detections` oznacza brak ramek YOLO: SAM nie uruchamia automatycznego segmentowania całej sceny. Przy `unavailable` lub `error` zapisujemy YOLO i informację o braku segmentacji, bez wymyślonych masek.

Klasa i pewność pochodzą z YOLO. SAM nie nadaje klasy, nie liczy unikalnych osób w całej misji i nie rozpoznaje usterek. `predicted_iou` jest oceną samego modelu, a nie rzeczywistym IoU względem ręcznych etykiet. Nie sumuj procentów masek jako pokrycia obrazu: maski mogą się nakładać. To gotowy model; EDA, ręczne etykiety, ocena jakości segmentacji i własny trening są następnymi etapami.

## RTX i wykonanie

Model: SAM 2.1 Tiny, rozmiar wejścia 1024, FP32, paczki po 4 ramki. Koduje obraz raz i współdzieli jego cechy między paczkami. Włączony jest `torch.inference_mode()`, bez zapisywania gradientów. YOLO i SAM używają wspólnej blokady w jednym procesie wizyjnym; nie uruchamiają równoległej inferencji na tym samym modelu. Pierwsza inspekcja obejmuje wczytanie SAM. Liczba masek jest ograniczona liczbą wykryć YOLO (maksymalnie 50).

Pełny scenariusz sprawdzający przy uruchomionym kokpicie:

```bash
.venv/bin/python scripts/check_sam.py --sector A
```

Skrypt ładuje Bielika pytaniem o instrukcję, wykonuje rzeczywistą misję, sprawdza artefakty i zapisuje próbkowane użycie pamięci całej RTX. Użycie całej karty obejmuje też Gazebo, Bielika i pulpit. Metryki PyTorch dotyczą wyłącznie procesu wizji, łącznie z YOLO; nie są osobnym pomiarem samego SAM. Próbkowanie co pół sekundy może pominąć krótki szczyt. Aktualne wyniki: `docs/verification/sam-inspection.json` (A) oraz `docs/verification/sam-inspection-c.json` (C z Bielikiem utrzymanym na RTX).

W MLflow wybierz Model training, eksperyment roboinspect-yolo i Runs. Znajdziesz model i SHA256 SAM, status, czas, liczbę masek, szczyt pamięci procesu wizji oraz artefakty `segmentation.json`, `segmented.jpg`, `masks.png` i `masks.npz`. Nie raportujemy mIoU bez ręcznych masek referencyjnych.

## Model i licencje

Wagi są przypięte w `config/sam.json` i sprawdzane SHA256 przed użyciem. Pochodzą z [oficjalnego wydania Ultralytics](https://github.com/ultralytics/assets/releases/download/v8.3.0/sam2.1_t.pt). Integracja korzysta z zainstalowanej, przypiętej wersji Ultralytics 8.3.228. [Dokumentacja SAM 2](https://docs.ultralytics.com/models/sam-2/) opisuje prompty ramkami i warianty modelu. [Meta SAM 2](https://github.com/facebookresearch/sam2) udostępnia informacje o modelu i jego licencji Apache 2.0; integracja Ultralytics podlega jej własnym warunkom AGPL-3.0/Enterprise. Zachowaj informacje licencyjne przy dystrybucji projektu.

## Wynik sprawdzenia na RTX 4060 Laptop

Rzeczywista inspekcja A zapisała 2 maski przy P1 i 6 przy P2, po czym robot wrócił do strefy A. Inspekcja C przy załadowanym Bieliku zapisała 2 maski przy P5 i zakończyła się poprawnie. Czas SAM wyniósł odpowiednio 0,497 s, 0,134 s i 0,779 s. Obejmuje różne klatki oraz zimny/ciepły model, więc nie jest porównaniem jakości ani stałym FPS.

W próbie C bazowe użycie pamięci całej RTX wynosiło 3551 MiB, najwyższa próbka 4274 MiB z 8188 MiB. Szczyt zaalokowanej pamięci PyTorch procesu wizji wyniósł 533,5 MiB. Te wartości mają różne zakresy i nie należy ich dodawać. Bielik był potwierdzony na GPU przed i po misji.

Potwierdzono artefakty w MLflow, odpowiedź czatu o liczbie masek oraz zachowanie danych po ponownym uruchomieniu. STOP podczas kolejnej inspekcji C anulował analizę i nie dopisał raportu. Dane źródłowe i przebieg: [inspekcja A](verification/sam-inspection.json), [inspekcja C](verification/sam-inspection-c.json), [MLflow i czat](verification/sam-mlflow-chat.json), [anulowanie](verification/sam-cancel.json).
