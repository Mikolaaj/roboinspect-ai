# Weryfikacja GHCR i jednorazowego CD: 21.10.2026

Wdrożono rewizję `56593d79702b8eb6106bcfac1a18499ddfd12ea0`.

## Wyniki

- [Application checks](https://github.com/Mikolaaj/roboinspect-ai/actions/runs/39494533374): sukces testów aplikacji, kontenerów, Kubernetes oraz obu publikacji GHCR.
- [Deploy local Kubernetes](https://github.com/Mikolaaj/roboinspect-ai/actions/runs/39622237254): sukces, wykonany na laptopie przez `roboinspect-local-cd`.
- W klastrze użyto obrazów `ghcr.io/mikolaaj/roboinspect-ai-gateway:sha-56593d79702b8eb6106bcfac1a18499ddfd12ea0` i analogicznego obrazu `mlflow`.
- Po wdrożeniu sprawdzono trzy kamery, FPV 1280×720, gotowość Nav2, renderowanie RTX 4060, krótką misję BASE i metryki wykonawcy.
- Runner miał opcję `--ephemeral`: po jednym zadaniu zakończył działanie i automatycznie wyrejestrował się z GitHuba. Lokalny klucz i pliki rejestracji zostały usunięte. Nie instalowano stałej usługi runnera.
- Token GHCR był krótkotrwałym GITHUB_TOKEN; katalog konfiguracji logowania usunięto przez trap po zakończeniu joba. Nie utworzono stałego PAT ani imagePullSecret.
- Zmienna repozytorium `ROBOINSPECT_ROOT` wskazuje lokalny projekt. Zapisana wersja w `data/deploy/release.json` zachowuje wybrane obrazy przy kolejnych uruchomieniach.

## Kolejne uruchomienia

Zwykły kokpit nadal uruchamia się jedną komendą:

```bash
cd ~/Desktop/roboinspect-ai
bash scripts/run_kubernetes.sh
```

Zatrzymanie:

```bash
bash scripts/stop_kubernetes.sh
```

Działające obrazy są w pamięci klastra kind, więc zwykły restart tego samego klastra nie wymaga aktywnego runnera. Usunięcie klastra lub jego cache obrazów będzie wymagało ponownego dostarczenia obrazów.

Do kolejnego CD z GitHuba trzeba ponownie zarejestrować runnera i uruchomić go na czas zadania. Lista Runners może być pusta po tym teście i jest to oczekiwane. Nie traktuj ponownego kliknięcia Run workflow bez runnera jako automatycznego startu aplikacji na wyłączonym laptopie.

## Poprawki ujawnione przez prawdziwe CI

1. Narzędzia Kubernetes przekazują ROBOINSPECT_ROOT, UID i GID bez zależności od lokalnego `.env`. Regresję sprawdza `test_deploy_environment.py`.
2. Test integralności manifestu zawsze zmienia etykietę na inną, zamiast czasem przypisywać tę samą wartość. Nie zmienia to danych, treningu ani pracy modeli.
3. Skrypt wdrożenia pobiera obrazy z GHCR, ładuje je do kind i dopiero potem aktualizuje Deployment. Nie wymaga trwałego tokenu w klastrze.

Raport maszynowy: [ghcr-cd.json](verification/ghcr-cd.json). Starszy test rollbacku: [kubernetes-ci.json](verification/kubernetes-ci.json).
