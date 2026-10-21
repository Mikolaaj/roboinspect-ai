# Docker Compose

## Zakres

Kontener `gateway` udostępnia panel, kokpit i publiczne wejście HTTP na 127.0.0.1:8765. Przekazuje strumienie kamer i żądania do lokalnego operatora na 127.0.0.1:8767. Jest to etap konteneryzacji warstwy HTTP, a nie przeniesienie całego wykonawcy misji do kontenera.

ROS 2, Gazebo, Nav2, SLAM, pojedynczy wykonawca misji, Bielik, Whisper, YOLO i SAM pozostają lokalnie. GPU działa jak w dotychczasowym uruchomieniu. Nie uruchamiamy drugiego właściciela robota ani drugiego wykonawcy misji.

Kontener `mlflow` udostępnia port 5001. Montuje istniejący katalog `data` pod tą samą absolutną ścieżką, dzięki czemu dotychczasowe adresy artefaktów pozostają poprawne. `docker compose down` nie usuwa danych hosta. Nie uruchamiaj równocześnie natywnego serwera MLflow i kontenera na tej samej bazie.

## Wymagania

Działający Docker Engine z Compose. Używamy host networking, żeby kontenery miały dostęp do lokalnego ROS API bez otwierania go w sieci LAN. Na Docker Desktop trzeba włączyć opcję host networking w ustawieniach sieci i ponownie uruchomić Desktop. Samo zainstalowanie polecenia `docker` nie wystarcza.

Dokumentacja: [host networking](https://docs.docker.com/engine/network/drivers/host/), [Compose networking](https://docs.docker.com/compose/how-tos/networking/).

Pozostałe zależności lokalne przygotuj według `install-and-run.md`. Pierwsza budowa pobiera obrazy i zależności. Nie zmieniaj nazwy ani położenia katalogu projektu bez migracji absolutnych adresów istniejących artefaktów MLflow.

## Zatrzymanie i uruchomienie

Zatrzymaj poprzedni tryb:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/stop_cockpit.sh
```

Uruchom tryb Compose jedną komendą:

```bash
bash scripts/run_compose.sh
```

Po gotowości otworzą się kokpit i panel sterowania. MLflow: http://127.0.0.1:5001.

Zatrzymanie: Ctrl+C w terminalu startowym albo w drugim terminalu:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/stop_compose.sh
```

Powrót do dotychczasowego trybu lokalnego:

```bash
bash scripts/run_cockpit.sh
```

## Sprawdzenie na żywo

1. `docker compose ps`: gateway i mlflow mają być healthy.
2. Sprawdź trzy kamery w kokpicie, wyślij misję A i powrót do bazy z panelu.
3. Sprawdź czat Bielika, inspekcję YOLO i SAM oraz historię.
4. W MLflow otwórz wcześniejszy eksperyment i jego artefakt. Wyślij nową wiadomość na czacie i znajdź jej run.
5. Zatrzymaj Compose, uruchom ponownie i sprawdź tę samą historię oraz run.
6. `docker compose logs --tail 100` pokazuje logi kontenerów; logi ROS pozostają w `artifacts/cockpit`.

Stan 21.10.2026: budowanie kontenerów, HTTP i trwałość MLflow potwierdzono testem integracyjnym w CI. Pełną sesję z robotem potwierdzono w trybie Kubernetes. Dowody i granice odbioru: [audyt projektu](project-audit.md).

## Automatyczna weryfikacja

Dodano izolowany test budowania obrazów, HTTP i trwałości MLflow po odtworzeniu kontenerów. Szczegóły oraz zakres bez ROS: [ci-containers.md](ci-containers.md). Wynik testu nie zastępuje ręcznego przejazdu i inspekcji w symulacji.
