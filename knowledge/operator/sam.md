# Segmentacja SAM podczas inspekcji

SAM 2.1 Tiny wyznacza kształt obiektów wskazanych ramkami YOLO na tej samej klatce kamery robota. Działa automatycznie podczas inspekcji, gdy robot stoi na zielonym polu przed tablicą P. Podczas jazdy kamera pokazuje YOLO bez ciągłej segmentacji SAM.

W kokpicie lub panelu sterowania rozwiń Historię detekcji z inspekcji i wybierz nową obserwację. W Widoku obserwacji wybierz YOLO + SAM, aby zobaczyć półprzezroczyste kolorowe maski i kontury. Tylko YOLO pokazuje same ramki na tej samej klatce. Obok obiektów jest powierzchnia maski w pikselach i procent całego obrazu. Przycisk Pobierz maski zachowuje dokładne dane masek do dalszej analizy. Starsze obserwacje bez SAM pozostają dostępne.

SAM nie nadaje klas i nie wykrywa usterek. Klasa i pewność pochodzą z YOLO, maska opisuje przewidywany kształt. Nakładające się maski mogą należeć do różnych obiektów, więc procentów powierzchni nie należy sumować jako pokrycia obrazu. Brak ramek YOLO oznacza brak segmentacji. Status częściowa, błąd lub niedostępna jest widoczny przy obserwacji; wynik YOLO nadal zostaje zapisany. Błąd segmentacji nie oznacza braku obiektów. Parametr predicted_iou to własna ocena modelu SAM, a nie pomiar poprawności względem ręcznych etykiet.

Możesz zapytać, ile masek zapisano w ostatniej inspekcji sektora A lub punktu P1. Czat odczyta dane ostatniej zapisanej misji; nie opisuje w ten sposób obrazu na żywo. W MLflow, w eksperymencie roboinspect-yolo i widoku Runs, zobaczysz też model SAM, status, liczbę masek, czas i pamięć procesu wizyjnego. Artefakty obejmują obraz z maskami i ich dane.
