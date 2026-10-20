#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 scripts/prepare_compose_env.py
export ROBOINSPECT_ROOT="$PWD" ROBOINSPECT_UID="$(id -u)" ROBOINSPECT_GID="$(id -g)"
if ! docker info >/dev/null 2>&1; then
  echo 'Brak dostępu do silnika Docker.' >&2
  echo 'Sprawdź: docker context ls oraz docker --context default info' >&2
  echo 'Jeśli systemowy Docker działa, przełącz: docker context use default' >&2
  echo 'Jeśli brakuje uprawnień, administrator musi nadać dostęp do Dockera.' >&2
  exit 1
fi
if [[ -f artifacts/cockpit-runtime.json ]]; then
  echo 'Najpierw zatrzymaj lokalny kokpit: bash scripts/stop_cockpit.sh'
  exit 1
fi
compose=(docker compose -f compose.yaml -f compose.monitoring.yaml)
mkdir -p data/mlflow-artifacts artifacts
# Build before starting any owned processes.
"${compose[@]}" build
"${compose[@]}" up -d mlflow
cleanup() {
  trap - EXIT INT TERM
  bash scripts/stop_cockpit.sh
  "${compose[@]}" down
}
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
"${compose[@]}" up -d gateway prometheus
bash scripts/run_cockpit.sh --port 8767 --external-mlflow --no-browser "$@" &
runtime_pid=$!
for ((i=0; i<240; i++)); do
  if ! kill -0 "$runtime_pid" 2>/dev/null; then wait "$runtime_pid"; exit 1; fi
  if curl -fsS http://127.0.0.1:8765/health/ready >/dev/null 2>&1; then
    xdg-open http://127.0.0.1:8765/ >/dev/null 2>&1 || true
    xdg-open http://127.0.0.1:8765/control >/dev/null 2>&1 || true
    echo 'Gotowe: kokpit i sterowanie na porcie 8765, MLflow na 5001. Ctrl+C zatrzymuje całość.'
    wait "$runtime_pid"
    exit $?
  fi
  sleep 1
done
echo 'Brak gotowości. Sprawdź docker compose logs i artifacts/cockpit/. Docker Desktop wymaga włączenia host networking.' >&2
exit 1
