# Prezentacja końcowa projektu

## Przygotowanie

Wybierz jeden tryb: Compose lub Kubernetes. Zatrzymaj poprzednią sesję. Sprawdź wolne miejsce, dostęp do Dockera oraz przygotowane modele. Do prezentacji nie jest potrzebny trening własnego klasyfikatora.

## Scenariusz

1. Uruchom kokpit jedną komendą i pokaż kamerę robota, widok trzeciej osoby oraz monitoring hali.
2. Wyślij robota do sektora A przyciskiem i pokaż pozycję na mapie oraz aktualizowaną trasę.
3. Napisz do Bielika polecenie przejazdu do B i powrotu do bazy. Pokaż walidację misji oraz jej historię.
4. Nagraj krótką komendę. Sprawdź tekst z lokalnego Whispera przed wysłaniem.
5. Uruchom inspekcję sektora A. Pokaż dojazd do zielonych pól P1/P2, YOLO na kamerze oraz zapis segmentacji SAM.
6. Zapytaj Bielika o wykrycia w sektorze A. Porównaj odpowiedź z zapisanym raportem; pewność detekcji nie jest gwarancją poprawności.
7. Zapytaj o obsługę systemu i pokaż odpowiedź RAG ze źródłami.
8. Otwórz MLflow i pokaż parametry, metryki oraz artefakty konkretnego wywołania.
9. Otwórz Monitoring, sprawdź target oraz `roboinspect_executor_ready`.
10. W trybie Kubernetes pokaż Deployment, Service, Secret, ConfigMap i PVC; test automatyczny demonstruje trwałość danych i odzyskanie po błędnym wdrożeniu.
11. Pokaż workflow testów oraz publikację obrazów na GitHub po wysłaniu zmian. Nie przedstawiaj zapisanej konfiguracji jako uruchomionej publikacji.
12. Zatrzymaj system i uruchom ponownie, aby pokazać zachowaną historię inspekcji i MLflow.

## Co wyjaśnić

- LLM interpretuje język, ale nie steruje bezpośrednio kołami. Zweryfikowane misje wykonuje Nav2.
- SLAM buduje mapę, kamera i modele analizują obraz, a ROS łączy symulację z aplikacją.
- Pydantic waliduje kontrakty, FastAPI udostępnia HTTP, SQLite zachowuje historię, MLflow rejestruje eksperymenty.
- Docker i Kubernetes obejmują usługi HTTP oraz MLflow. GPU i symulacja pozostają lokalne.
- Własny klasyfikator jest osobnym pilotażem. Bieżące inspekcje używają YOLO i SAM.
- To demonstracja lokalna na danych syntetycznych, bez deklaracji gotowości do sterowania fizycznym robotem w przestrzeni ludzi.

## Dokumenty do repozytorium

README prowadzi do instalacji, architektury, danych, modeli, wyników testów, wydań, Kubernetes i monitoringu. Przed oddaniem porównaj wymagania PDF projektu z `course-coverage.md`; nie deklaruj pełnego pokrycia kursu bez sprawdzenia szczegółowych wymagań.
