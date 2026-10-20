# CI: testy aplikacji i kontenerów

Workflow `.github/workflows/ci.yml` uruchamia się dla push i pull request. Nie publikuje obrazów i nie wdraża aplikacji.

## Kolejność

1. Job `test` instaluje zależności z `uv.lock`, uruchamia Ruff, testy Python oraz JavaScript.
2. Job `containers`, po sukcesie testów, waliduje Compose i buduje oba obrazy z właściwych Dockerfile.
3. `scripts/check_compose_ci.py` uruchamia odizolowany projekt Compose na losowych portach, z tymczasową bazą MLflow.
4. Sprawdza gotowość bramy, stronę panelu, przekazanie żądania HTTP i blokadę prywatnego endpointu.
5. Tworzy eksperyment, run, metrykę i artefakt MLflow. Usuwa kontenery, tworzy je ponownie i odczytuje metrykę oraz zawartość artefaktu.
6. Zapisuje wynik JSON i logi kontenerów. GitHub dołącza je jako artefakt `compose-check-results`, również przy niepowodzeniu testu, jeśli pliki powstały.

Test kontenerów używa małego serwera HTTP zamiast ROS. Nie jest testem Gazebo, nawigacji, YOLO, SAM ani GPU. Te elementy sprawdzamy lokalnie. Test nie montuje użytkowego katalogu danych i nie zatrzymuje działających kontenerów kokpitu.

## Uruchomienie lokalne

Z dowolnego terminala z dostępem do Dockera:

```bash
cd ~/Desktop/roboinspect-ai
python3 scripts/check_compose_ci.py
```

Skrypt sam buduje obrazy i usuwa własne kontenery po zakończeniu. Wynik: `artifacts/compose-ci/result.json`; logi: `artifacts/compose-ci/containers.log`.

## Sprawdzenie na GitHub

Po wysłaniu commita otwórz repozytorium, zakładkę Actions, workflow Application checks. Oba joby, `test` i `containers`, powinny zakończyć się sukcesem. Wynik lokalny nie oznacza jeszcze zakończonego uruchomienia na GitHub.

Dalsze etapy: publikacja wersjonowanych obrazów w rejestrze, wdrożenie usług HTTP i MLflow na Kubernetes, procedura rollback. Nie są częścią tego workflow.

Dokumentacja: [artefakty GitHub Actions](https://docs.github.com/actions/configuring-and-managing-workflows/persisting-workflow-data-using-artifacts), [projekty Compose](https://docs.docker.com/compose/intro/compose-application-model/).

## Wynik lokalny 20.10.2026

Oba obrazy zbudowano i uruchomiono. Test HTTP oraz odczyt metryki i artefaktu MLflow po usunięciu i ponownym utworzeniu kontenerów zakończyły się sukcesem. Raport: [compose-ci.json](verification/compose-ci.json). Pełny zestaw aplikacji: 193 testy Python, testy JavaScript i kontrole Ruff przeszły. Pipeline na GitHub wymaga wysłania tych zmian do repozytorium.

## Rozszerzenie pipeline

Dodano osobny job `kubernetes`, który tworzy lokalny kind i sprawdza storage, monitoring i odzyskanie po błędnym obrazie. Publikacja `publish` zależy od sukcesu `test`, `containers` i `kubernetes`; działa wyłącznie dla push do main. Szczegóły: [wydania i CD](releases-and-cd.md).
