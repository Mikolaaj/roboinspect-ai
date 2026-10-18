# Założenia późniejszej percepcji — YOLO + SAM

Dodano na życzenie użytkownika 18.10.2026. Status: plan faz 9–11,
bez instalacji modeli, pobierania wag ani uruchamiania inferencji teraz.

## Przepływ obrazu

Kamera FPV → YOLO → bounding box obiektu → SAM → maska obiektu →
własny model oceny defektu → nakładka na obrazie i zapis wyniku inspekcji.

YOLO ma lokalizować docelowy obiekt/panel. Gotowe wagi będą punktem wyjścia;
rozpoznawanie naszych paneli lub uszkodzeń może wymagać własnych etykiet i
fine-tuningu. SAM ma segmentować wskazany obszar, wykorzystując box/punkt jako
prompt. Maski z promptów opisuje [oficjalne repozytorium SAM](https://github.com/facebookresearch/segment-anything).
Dobór wersji rodziny SAM i modelu YOLO nastąpi na etapie implementacji,
z zapisaniem licencji i wersji wag. Nie zakładamy konkretnego FPS ani tego,
że największe warianty zmieszczą się jednocześnie z symulatorem na GPU.

Maska panelu nie jest diagnozą uszkodzenia. Klasyfikację stanu, np. normalny,
rysa, pęknięcie, nadal ocenia osobny model uczony i porównywany w projekcie.
SAM nie zastępuje zaplanowanego EDA, treningu, ewaluacji i MLflow.

## Integracja z kokpitem

- Widok FPV zachowuje opcję surowego obrazu i nakładki boxów/masek.
- Wynik zawiera identyfikator kadru, czas, panel, model i jego wersję.
- Osobny worker percepcji nie blokuje ROS/Nav2 ani strumieni kamer.
- Ograniczona kolejka zapobiega analizowaniu zaległych klatek.
- Porównamy inspekcję po zatrzymaniu z analizą co wybraną liczbę klatek.
- YOLO i SAM mają korzystać z RTX; budżet VRAM jest wspólny z Gazebo
  i ewentualnymi lokalnymi modelami STT/LLM, jeśli je wybierzemy.

## Dane i kryteria

Faza 9: boxy i referencyjne maski; podział po scenach/obiektach, bez mieszania
podobnych klatek między trening i test. Etykiety oceny pochodzą z generatora
lub niezależnych adnotacji; automatyczne maski SAM mogą pomagać w anotacji,
ale nie są samodzielnym dowodem swojej poprawności.

Faza 10: metryki detekcji (precision/recall, mAP), masek (IoU/Dice) i
klasyfikacji defektów, razem z pomiarem opóźnienia, FPS i VRAM.
Eksperymenty i artefakty zapisujemy w MLflow.

Faza 11: rzeczywista misja inspekcyjna pokazuje box, maskę i wynik oceny
na aktualnym kadrze; raport zachowuje dowód obrazowy oraz wersje modeli.
Brak detekcji, błędna maska i stary kadr muszą być jawnie obsłużone.
