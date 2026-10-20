#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
python3 - <<'PY'
from pathlib import Path
import json, os, signal, time
path=Path('artifacts/kubernetes-runtime.json')
if not path.exists():
 print('Brak zapisanego aktywnego kokpitu Kubernetes. Jeśli trwa start, użyj Ctrl+C w terminalu startowym.')
 raise SystemExit(0)
s=json.loads(path.read_text()); pid=int(s['pid'])
proc=Path(f'/proc/{pid}')
if not proc.exists():
 path.unlink(); print('Proces już nie istnieje.'); raise SystemExit(0)
if proc.joinpath('stat').read_text().split()[21]!=s['start'] or b'scripts/run_kubernetes.py' not in proc.joinpath('cmdline').read_bytes():
 raise SystemExit('PID nie należy do tej sesji; nie zatrzymano procesu.')
os.kill(pid,signal.SIGINT)
print('Zamykanie, poczekaj...')
for _ in range(180):
 if not path.exists(): print('Zamknięto.'); break
 time.sleep(1)
else: raise SystemExit('Sprawdź terminal startowy i artifacts/kubernetes.')
PY
# Also stop application pods left by an interrupted manager. Keep PVC and data.
if [[ -f data/deploy/kubeconfig && -x data/deploy/bin/kubectl ]]; then
  export KUBECONFIG="$PWD/data/deploy/kubeconfig"
  if data/deploy/bin/kubectl --context kind-roboinspect get namespace roboinspect >/dev/null 2>&1; then
    data/deploy/bin/kubectl --context kind-roboinspect -n roboinspect scale deployment --all --replicas=0
  fi
fi
