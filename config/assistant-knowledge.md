# Historyczna kopia instrukcji

Bieżącym źródłem RAG są dokumenty w knowledge/operator/. Ta kopia nie jest indeksowana i może opisywać wcześniejszy stan.

# Publiczna instrukcja operatora

overview: RoboInspect to symulacja mobilnego robota w hangarze. Możesz zlecać przejazdy między sektorami A, B i C oraz bazą BASE. Robot planuje trasę i omija przeszkody, a trzy kamery pozwalają obserwować przejazd. W panelu sprawdzisz pozycję, wynik misji i historię. Możesz też tworzyć i zapisywać mapę hali.
controls: W panelu sterowania wybierz przycisk A, B, C lub Powrót do bazy. Możesz też napisać w czacie „Jedź do B i wróć do bazy” i nacisnąć Enter lub Wyślij. Kroki misji wykonają się kolejno. Wynik pokazuje panel i wiadomość z misją; samo przyjęcie polecenia nie oznacza dojazdu. Nie ma dodatkowego okna potwierdzenia.
navigation: Nav2 odpowiada za planowanie trasy i prowadzenie robota do wybranego celu. Korzysta z mapy oraz odczytów czujników, aby omijać przeszkody. Ty wskazujesz sektor w panelu lub czacie i obserwujesz postęp. Jeśli przejazd się nie powiedzie, panel pokaże błąd i pozostałe kroki zostaną pominięte.
mapping: SLAM tworzy mapę hangaru podczas ruchu robota na podstawie pomiarów odległości. Pod przyciskami jazdy wybierz Rozpocznij mapowanie, aby uruchomić obchód. Zapisz mapę zachowuje jej wersję, a Resetuj mapę rozpoczyna świeżą mapę. Zakończ mapowanie zapisuje wynik i przywraca zwykłą nawigację z robotem w bazie. Kropka na mapie pokazuje pozycję robota.
cameras: Kokpit pokazuje trzy widoki: obraz z kamery robota, kamerę podążającą za robotem z boku i monitoring całej hali z góry. Pierwszy pozwala zobaczyć to, co znajduje się przed robotem. Widok boczny ułatwia obserwację jego ruchu, a monitoring pokazuje położenie w całym hangarze.
stop: Napisz w czacie STOP, aby przerwać odpowiedzi asystenta, anulować misję i zatrzymać obchód mapowania. Przycisk Anuluj przejazd służy do anulowania misji. Przycisk Zatrzymaj odpowiedź przerywa tylko analizę wiadomości; nie cofa już przyjętej misji. Panel pozostaje otwarty, aby pokazać potwierdzenie zatrzymania.
results: MLflow służy do przeglądania wyników działania asystenta. W widoku Model training wybierz eksperyment roboinspect-bielik i listę Runs. Zobaczysz czas odpowiedzi, poprawność formatu i informację, czy przyjęto misję. Przyjęcie misji nie potwierdza dojazdu — wynik przejazdu sprawdzaj w panelu robota.

Źródłem używanym przez asystenta jest GUIDE w src/roboinspect/operator_policy.py.
Ten plik jest czytelną kopią dokumentacyjną. Nie zawiera konfiguracji ani instrukcji modyfikacji.

## Głos i czerwone strefy

Mikrofon nagrywa do 30 sekund. Lokalny Whisper wpisuje tekst do czatu, operator sprawdza go i wysyła. Samo nagranie nie uruchamia misji. Do szybkiego zatrzymania użyj Anuluj przejazd lub tekstowego STOP.

A prowadzi do jednej czerwonej strefy przed P1/P2, B przed P3/P4, C przed P5. Robot ustawia kamerę w kierunku tablic.

## Trasa i mapa 2D

Pod kamerami, obok mapy SLAM, znajduje się schemat całego hangaru z przeszkodami i pozycją robota. Żółta linia pokazuje aktualny plan Nav2, żółty punkt bieżący cel. Linia jest też na podłodze świata w kamerach. Zmiana planu po wykryciu przeszkody zmienia wizualizację. Po dojeździe i anulowaniu linia oraz punkt znikają.

## Ustawienie magazynu

Pod mapowaniem wybierz Standardowe ustawienie magazynu, Usuń wszystkie przeszkody lub Losuj przeszkody. Usuwane są skrzynie, regał, stół i wolnostojące słupy; ściany i tablice pozostają. Losowanie zachowuje przejścia do czerwonych stref i punktów P. Zmiana wymaga zakończenia jazdy i mapowania, odświeża świat i mapę oraz ustawia robota w BASE. Wynik znajdziesz w historii. Zapisane mapy i wcześniejsze operacje pozostają zachowane.

## Inspekcja zdjęć

Wybierz Inspekcja sektora A, B lub C. Robot odwiedzi kolejno tablice P i po zapisaniu detekcji wróci na czerwone pole sektora. A obejmuje P1/P2, B P3/P4, C P5. Zmień zdjęcia na banerach losuje nowe fotografie i odświeża symulację, wracając do BASE. W kokpicie rozwiń historię detekcji. YOLO11s rozpoznaje 80 klas, person to człowiek, numer oznacza obiekt w jednej klatce, procent to pewność detektora. Możesz zapytać, co robot widział w sektorze A. Czat poda ostatnie zapisane wyniki i datę; aktualne zdjęcia mogły się zmienić.
