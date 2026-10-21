# Obrazy, wydania i CD

## CI i GHCR

Workflow Application checks uruchamia testy aplikacji, test kontenerów i integracyjny test Kubernetes. Po ich sukcesie push do main publikuje dwa obrazy:

- `ghcr.io/mikolaaj/roboinspect-ai-gateway:sha-<pełny SHA commita>`
- `ghcr.io/mikolaaj/roboinspect-ai-mlflow:sha-<pełny SHA commita>`

Publikacja używa GITHUB_TOKEN z uprawnieniem packages:write tylko w zadaniu publish. Pull request nie publikuje obrazów. Obrazy otrzymują oznaczenie repozytorium i rewizji, SBOM oraz provenance. Nie używamy tagu latest do wdrażania wersji z GHCR. SHA jest identyfikatorem wydania, a nie deklaracją istnienia GitHub Release.

Pierwsza publikacja wymaga wysłania zmian i sukcesu pipeline. Repozytorium nie zawiera klucza do rejestru. Pakiety mogą pozostać prywatne. Workflow CD loguje Docker krótkotrwałym GITHUB_TOKEN z packages:read w tymczasowym katalogu konfiguracji. Skrypt pobiera obrazy i ładuje je bezpośrednio do kind przed wdrożeniem. Nie jest potrzebny stały PAT ani imagePullSecret. Przy ręcznym uruchomieniu lokalnym wymagane jest własne zalogowanie Dockera do GHCR.

## Aktualizacja działającego klastra

Najpierw uruchom projekt w trybie Kubernetes. Zakończ przejazd i operacje mapowania. W drugim terminalu podaj pełny SHA, który przeszedł publikację:

```bash
cd ~/Desktop/roboinspect-ai
.venv/bin/python scripts/deploy_kubernetes.py --revision PELNY_40_ZNAKOWY_SHA
```

Skrypt najpierw pobiera obrazy z GHCR i ładuje je do kind, następnie zapisuje obecne obrazy i aktualizuje wdrożenia i czeka na gotowość. Przy niepowodzeniu przywraca wcześniejsze obrazy i sprawdza gotowość. Nowe obrazy i ich identyfikatory są zapisywane w `data/deploy/release.json`, aby kolejne uruchomienie zachowało wybrane wydanie.

Ręczny rollback:

```bash
.venv/bin/python scripts/deploy_kubernetes.py --revision PELNY_40_ZNAKOWY_SHA --rollback
```

Parametr SHA jest walidowany także w trybie rollback, ale wybór poprzedniej rewizji odbywa się przez historię Deployment. Klaster zachowuje pięć rewizji. Rollback dotyczy obrazu i szablonu poda, nie danych w bazie. Pierwsza instalacja nie ma poprzedniej wersji.

## Ręcznie uruchamiane CD z GitHub

Workflow Deploy local Kubernetes jest gotowy do podłączenia do dedykowanego runnera na laptopie:

1. GitHub Settings > Actions > Runners > New self-hosted runner. Użyj instrukcji i krótkotrwałego tokenu wyświetlonego przez GitHub. Nie zapisuj tokenu w repozytorium.
2. Nadaj runnerowi dodatkową etykietę `roboinspect-deploy`. Runner musi mieć dostęp do Dockera i projektu oraz uruchomione lokalne usługi Kubernetes.
3. Dodaj zmienną repozytorium `ROBOINSPECT_ROOT` z absolutną ścieżką projektu.
4. Utwórz środowisko GitHub `local-robot`. Ogranicz możliwość wdrażania do zaufanych użytkowników i main.
5. W Actions wybierz Deploy local Kubernetes > Run workflow i podaj pełny opublikowany SHA. Opcja rollback uruchamia cofnięcie.

Workflow jest ręczny i nie wykonuje kodu pull request na laptopie sterującym robotem. Nie instaluje ani nie rejestruje runnera samodzielnie. Bez rejestracji runnera zadanie pozostanie w kolejce; lokalny skrypt wdrożeniowy nadal działa.

Stan kodu i stan wdrożenia to różne rzeczy. Sam zapis workflow nie oznacza, że obrazy zostały opublikowane lub wdrożone. Sprawdź Actions oraz `kubectl get deployments`.

Dokumentacja: [publikowanie do GHCR](https://docs.github.com/en/actions/tutorials/publish-packages/publish-docker-images), [rollback](https://kubernetes.io/docs/reference/kubectl/generated/kubectl_rollout/kubectl_rollout_undo/).

## Wykonany test

Publikacja i jednorazowe CD zostały zweryfikowane 21.10.2026. Runner po sukcesie został wyrejestrowany. Szczegóły, linki do zielonych workflow i ograniczenia kolejnych uruchomień: [ghcr-cd-results.md](ghcr-cd-results.md).
