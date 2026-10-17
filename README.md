# RoboInspect AI

Robot inspekcyjny w hangarze Gazebo, sterowany tekstem i głosem, z Pydantic AI, własnym modelem wizyjnym oraz procesem MLOps i CI/CD.

## Status

Projekt w fazie 0–1. Obecnie repo zawiera plan, dokumentację startową i diagnostykę środowiska. Symulacja hangaru, dashboard, agent i trening nie są jeszcze zaimplementowane.

## Docelowe działanie

Operator wydaje polecenie „Sprawdź panele w sektorze B i wróć do bazy”. Gotowy LLM tworzy walidowany plan, wykonawca zleca nawigację, a własny model analizuje obraz. Wyniki trafiają do raportu. Głos jest przetwarzany przez gotowy model STT.

Panel operatora ma trzy kolumny: kamerę robota, widok podążający za nim oraz monitoring hangaru z góry z czatem i mikrofonem poniżej.

## Pierwszy krok

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/doctor.sh
```

Skrypt tylko odczytuje stan środowiska. Nie instaluje pakietów i nie uruchamia symulatora.

- [Plan realizacji i kryteria ukończenia faz](docs/plan-faz.md)
- [Stan środowiska i kolejne kroki](docs/environment.md)

## Najbliższy kamień milowy

Uruchomić istniejący przykład ROS 2/Gazebo, sprawdzić renderowanie i dopiero potem zbudować hangar z sektorami A/B/C. Polecenia uruchomienia demo będą dodawane po ich rzeczywistym sprawdzeniu.

## Dokumentacja i odtwarzalność

Instrukcja instalacji, konfiguracji, uruchamiania, treningu i wdrożenia będzie rozwijana razem z implementacją. Każda faza musi mieć sprawdzony rezultat. Pełny odbiór obejmuje uruchomienie na czystym środowisku według instrukcji.

## Dane i sekrety

Klucze API przechowujemy poza Git. Duże dane, wagi modeli, nagrania i lokalne logi nie są commitowane. Konfiguracja przykładowa będzie dodana wraz z pierwszą usługą.
