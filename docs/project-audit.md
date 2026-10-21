# Podsumowanie i sprawdzenie projektu

Data: 21.10.2026. Projekt: RoboInspect AI.

## Wniosek

Działa pełny scenariusz robota z gotowymi modelami: polecenie, walidacja, nawigacja, analiza obrazu, historia i odpowiedź asystenta. Istnieje też osobny pilot własnego uczenia. Wdrożenie lokalne z CI/CD jest potwierdzone. Główne rzeczy do domknięcia przed oddaniem to próba instalacji na czystym komputerze oraz prezentacja z czytelnym omówieniem danych i ograniczeń modelu.

Nie deklarujemy, że własny klasyfikator jest wdrożony w inspekcjach ani że projekt ma potwierdzoną skuteczność na rzeczywistych usterkach.

## Porównanie z PDF projektu końcowego

Źródło: lokalny „Projekt końcowy Inzynier AI grupa 28.03.2026.pdf”, slajdy „Założenia” i „End-to-end”. PDF podaje termin 4.12.2026 i dopuszcza wdrożenie lokalne lub GCP. Przykładowe stosy technologiczne nie są obowiązkową listą bibliotek.

| Wymaganie | Ocena | Co to potwierdza |
|---|---|---|
| Eksploracyjna analiza danych | Spełnione w pilotażowym zakresie | Raport EDA: klasy i splity, miary obrazu, pliki, duplikaty, pochodzenie i kontrola przecieków. Cechy jasności, kontrastu i krawędzi. Brak szerokiej analizy rzeczywistych defektów |
| Przetestowanie kilku algorytmów | Spełnione w pilocie | Porównanie cech obrazu + ridge z dostrajanym ResNet18 na wspólnym podziale |
| Optymalizacja hiperparametrów | Częściowo | Alpha ridge wybierane spośród 0.1/1/10 na walidacji; wybór epoki CNN i early stopping. Learning rates CNN są ustalone, nie wykonano szerokiego wyszukiwania. Optuna nie jest wymogiem PDF |
| OOP, wzorce i SOLID | Zastosowane, bez formalnej pełnej oceny | Oddzielone kontrakty, API, logika misji, magazyn danych i adapter ROS. Testy weryfikują zachowanie, nie dowodzą spełnienia każdej zasady SOLID |
| Pipeline przetwarzania danych | Spełnione w pilocie | Kamera, próbki, przegląd, grupowanie źródeł, snapshot, preprocessing, trening, walidacja i test |
| Testy jednostkowe | Spełnione | Bieżący komplet 198 testów Python i 8 JavaScript; Ruff i formatowanie poprawne |
| API i konteneryzacja | Spełnione dla warstwy usług | FastAPI/Pydantic, kontenery gateway/MLflow. Wykonawca ROS i modele GPU pozostają na hoście |
| Wdrożenie na klaster i CI/CD | Spełnione lokalnie | kind, trwałość MLflow, testy, GHCR, udane ręczne CD i test rollbacku obrazów |
| Jeden ciąg analiza → uczenie → implementacja → wdrożenie | Częściowo połączone | Wszystkie obszary mają implementację, ale własny klasyfikator ma osobne wyniki i predykcję. Misje używają YOLO/SAM. Dla najmocniejszego demonstratora warto w przyszłości połączyć klasyfikator z inspekcją |

Ostateczny odbiór należy do prowadzącego. Własny trening i jego integracja pozostają odłożone zgodnie z decyzją użytkownika, nie dopisujemy ich jako ukończonych funkcji robota.

## Własny model: co naprawdę zmierzono

- 200 syntetycznych obserwacji, podział 120/40/40. Pięć klas: clean, cracked, dirty, occluded, missing.
- Podział grupowy według źródłowej fotografii: 14/5/5 grup. Warianty jednego zdjęcia nie powinny przechodzić między częściami.
- Test: ridge accuracy 0.65, macro F1 0.664; ResNet18 accuracy i macro F1 1.0.
- Test ma 40 skorelowanych kadrów z pięciu źródeł. Wynik 1.0 nie oznacza bezbłędnego wykrywania realnych usterek.
- YOLO i SAM korzystają z gotowych wag. Bielik i Whisper również nie były tutaj trenowane.

Dowody: [dataset-200.json](verification/dataset-200.json), [classifier-training.json](verification/classifier-training.json), [opis treningu](classifier-training.md).

## Co sprawdzono teraz

Bez zatrzymywania działającej sesji i bez zlecania nowej misji:

- `bash scripts/test_project.sh -q`: **198 testów Python i 8 testów JavaScript poprawnych**, Ruff i formatowanie poprawne.
- Jedno ostrzeżenie deprecacji SQLAlchemy w zależności MLflow. Nie spowodowało błędu testów.
- `/health/ready`: ready=true.
- `/api/status`: Nav2 gotowe, robot bez aktywnej misji w BASE; renderowanie GPU, NVIDIA GeForce RTX 4060 Laptop GPU.
- `/api/chat/runtime`: model Bielika dostępny, jeszcze niezaładowany. Ładowanie przy użyciu jest oczekiwane.
- `/api/speech/runtime`: Whisper small dostępny, CPU, jeszcze niezaładowany.
- MLflow `/health`: HTTP 200; Prometheus `/-/ready`: HTTP 200.
- Kubernetes: gateway, mlflow i prometheus Running, każdy 1/1 Ready; PVC Bound.

Nie wykonywano teraz ponownie treningu, pełnej inspekcji, nagrania mikrofonu, testu rollbacku ani instalacji od zera. Wcześniejsze próby są zapisane w `docs/verification/`. Nowy klon bez lokalnego `data/` nie zawiera historii ani wytrenowanych modeli tego laptopa.

## Wcześniejsze potwierdzenia

- [Kubernetes z robotem](verification/kubernetes-live.json): trzy kamery, przejazd A → BASE i powrót połączenia po wymianie poda.
- [GHCR i CD](verification/ghcr-cd.json): obrazy według SHA, gotowe usługi, przejazd BASE i ponowny start bez runnera.
- [CI](https://github.com/Mikolaaj/roboinspect-ai/actions/runs/39494533374) i [CD](https://github.com/Mikolaaj/roboinspect-ai/actions/runs/39622237254): zapisane zakończenia success dla wersji `56593d79702b8eb6106bcfac1a18499ddfd12ea0`.
- [Kubernetes bez ROS](verification/kubernetes-ci.json): odtworzenie MLflow, metryki, odzyskanie po błędnym obrazie.
- [SAM](verification/sam-inspection.json), [RAG](verification/rag-evaluation.json), [kontenery](verification/compose-ci.json).

Raporty historyczne dotyczą podanych prób, nie stanowią gwarancji każdej przyszłej konfiguracji.

## Granice i następne kroki

1. **Odtwarzalność:** wykonać instalację na drugim komputerze lub czystym Ubuntu. Obecny przegląd kodu i testy tego nie zastępują.
2. **Prezentacja:** pokazać tekst/głos, przejazd, inspekcję, SAM, odpowiedź ze źródłami, EDA, wyniki pilota oraz MLflow i monitoring. [Scenariusz](demo.md).
3. **Uczenie, później:** niezależne zdjęcia i warunki, szersza optymalizacja oraz ewentualne włączenie klasyfikatora do inspekcji.
4. **Eksploatacja:** lokalny klaster nie ma wysokiej dostępności. Prometheus przechowuje dane w emptyDir. Rollback obrazu nie odwraca schematu bazy. Nowe CD wymaga ponownie podłączonego runnera.

Nie ma potrzeby dodawania kolejnych bibliotek wyłącznie dla pokrycia nazw z kursu. Aktualna mapa obszarów: [course-coverage.md](course-coverage.md).
