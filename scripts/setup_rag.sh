#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
runtime="$PWD/data/ollama-runtime/bin/ollama"
if [[ ! -x "$runtime" ]]; then
  echo 'Najpierw przygotuj Bielika: bash scripts/setup_bielik.sh'
  exit 1
fi
mkdir -p artifacts data/rag
export OLLAMA_HOST=127.0.0.1:11436 OLLAMA_MODELS="$PWD/data/ollama-models"
export OLLAMA_NO_CLOUD=true OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1
export CUDA_VISIBLE_DEVICES=-1
server_pid=''
cleanup(){ if [[ -n "$server_pid" ]]; then kill "$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true; fi; }
trap cleanup EXIT
if ! curl -fsS "http://$OLLAMA_HOST/api/version" >/dev/null 2>&1; then
  "$runtime" serve > artifacts/rag-setup.log 2>&1 &
  server_pid=$!
  for _ in {1..30}; do
    if curl -fsS "http://$OLLAMA_HOST/api/version" >/dev/null 2>&1; then break; fi
    sleep 1
  done
fi
"$runtime" pull embeddinggemma:300m
expected=0800cbac9c2064dde519420e75e512a83cb360de3ad5df176185dc69652fc515
echo "$expected  $OLLAMA_MODELS/blobs/sha256-$expected" | sha256sum --check
PYTHONPATH=src .venv/bin/python - <<'PY'
from roboinspect.rag import Retriever
import threading
r=Retriever()
chunks,vectors,digest=r.index(threading.Event())
print(f'RAG gotowy: {len(chunks)} fragmentów, {vectors.shape[1]} wymiarów, wersja {digest[:12]}')
PY
