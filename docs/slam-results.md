# Odbiór SLAM — 18.10.2026

Wykonano pełny obchód 8 punktów, powrót do BASE, zapis rastra i natywnego grafu.
Mapa referencyjna: `maps/slam/hangar_slam.yaml`; 603 × 449 komórek, 0.05 m/komórkę.
Rozpoznane komórki: 257374, zajęte: 3973. Po eksporcie i wczytaniu przez map_server
liczba rozpoznanych komórek pozostaje identyczna; nieznane obszary pozostają nieznane.

Po zatrzymaniu SLAM uruchomiono AMCL + Nav2 na zapisanej mapie i wykonano:

| Cel | Wynik | Błąd pozycji względem Gazebo |
|---|---|---|
| A | succeeded | 0.094 m |
| B | succeeded | 0.106 m |
| C | succeeded | 0.115 m |
| BASE | succeeded | 0.100 m |

Dodatkowo sprawdzono trzy zmieniające się obrazy, odrzucenie drugiego celu,
anulowanie podczas ruchu i zatrzymanie robota. Testy aplikacji: 30 zaliczonych;
Ruff check i format poprawne. Pozostaje jedno ostrzeżenie zależności Starlette
dotyczące przyszłej zmiany klienta testowego; testy nie mają błędów.

Raporty: [mapowanie](verification/slam-mapping.json),
[nawigacja na mapie SLAM](verification/slam-navigation.json).

Zakres: przygotowana trasa pomiarowa scenariusza normal, lidar i odometria,
jawne przesunięcie układu mapy względem BASE. To nie autonomiczna eksploracja.
Pierwsza próba zatrzymała się przed przeszkodą; finalny obchód korzysta z
ciągłej pozycji TF korygowanej przez SLAM. Poprawiono też eksport progu wolnych
komórek i dodano test zachowania nieznanych obszarów po ponownym wczytaniu.

Lokalny graf ma około 49 MiB i pozostaje w ignorowanym `data/maps/`.
Repo zawiera tylko niewielki raster, podgląd i metadane mapy referencyjnej.
Instrukcja: [slam.md](slam.md). Następny etap: [lokalny LLM](llm-local-plan.md).
