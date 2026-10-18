# Następny etap — lokalny czat LLM

Decyzja użytkownika: gotowy model lokalny na NVIDIA RTX 4060 Laptop (8 GB),
bez zewnętrznego API jako domyślnego dostawcy. Ten plik jest planem,
nie deklaracją działającego czatu lub zainstalowanego modelu.

Kolejność po odbiorze SLAM:

1. Uruchomić lokalny runtime inferencji i dobrać niewielki model instrukcyjny
   z obsługą polskiego oraz odpowiedzi strukturalnych; sprawdzić pamięć i opóźnienia
   równocześnie z Gazebo. Wybór wersji i kwantyzacji potwierdzić pomiarem.
2. Pydantic AI tworzy istniejący MissionPlan, korzystając z listy dozwolonych
   celów i odczytu stanu. Wysyłanie misji przechodzi przez obecny MissionService,
   bez omijania blokad, idempotencji i walidacji.
3. Czat pod monitoringiem: wpisanie komendy, podgląd planu, identyfikator misji,
   rzeczywisty status wykonania i anulowanie. Nie deklarować sukcesu na podstawie
   samej odpowiedzi modelu. Odmawiać wykonania nieznanego celu lub niejasnego planu.
4. Zestaw poleceń PL/EN i błędów: brak sektora, nazwa spoza konfiguracji,
   prompt injection, aktywna misja, brak połączenia. Porównać poprawność planów
   i czasy w MLflow; logować nazwę/wersję modelu, prompt i konfigurację.
5. Później gotowy STT, TTS i RAG. YOLO/SAM współdzielą budżet GPU, więc
   nie zakładamy, że wszystkie modele mogą stale zajmować VRAM jednocześnie.
   Rozważyć osobne procesy, kolejkę i zwalnianie modeli po bezczynności.

Ścieżka wykonania: tekst → lokalny LLM → Pydantic MissionPlan → trwały wykonawca
→ Nav2 → potwierdzony wynik w czacie. LLM interpretuje polecenie; Nav2 nadal
odpowiada za trasę i sterowanie ruchem.
