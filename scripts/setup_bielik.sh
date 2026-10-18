#!/usr/bin/env bash
# One-time local installation; no sudo or global system service.
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p data/ollama-runtime data/models artifacts
version=v0.40.6
runtime="$PWD/data/ollama-runtime"
model="$PWD/data/models/Bielik-4.5B-v3.0-Instruct-Q4_K_M.gguf"
if [[ ! -x "$runtime/bin/ollama" ]]; then
  curl -fL --retry 3 -C - -o "$runtime/ollama.tar.zst" "https://github.com/ollama/ollama/releases/download/$version/ollama-linux-amd64.tar.zst"
  tar --zstd -xf "$runtime/ollama.tar.zst" -C "$runtime"
fi
expected=39fb78db7c5e1582d3ef5bded109cd98606aabd5acbb5c98601155174b6763e1
if [[ ! -f "$model" ]] || ! echo "$expected  $model" | sha256sum --check --status; then
  curl -fL --retry 3 -C - -o "$model" 'https://huggingface.co/second-state/Bielik-4.5B-v3.0-Instruct-GGUF/resolve/5ed9534f824c7c184c21320f4d339e75569d0987/Bielik-4.5B-v3.0-Instruct-Q4_K_M.gguf'
fi
echo "$expected  $model" | sha256sum --check
export OLLAMA_HOST=127.0.0.1:11435 OLLAMA_MODELS="$PWD/data/ollama-models"
export OLLAMA_NO_CLOUD=true
export OLLAMA_MAX_LOADED_MODELS=1 OLLAMA_NUM_PARALLEL=1 OLLAMA_CONTEXT_LENGTH=4096
server_pid=''
cleanup(){ if [[ -n "$server_pid" ]]; then kill "$server_pid" 2>/dev/null || true; wait "$server_pid" 2>/dev/null || true; fi; }
trap cleanup EXIT
if ! curl -fsS "http://$OLLAMA_HOST/api/version" >/dev/null 2>&1; then
  "$runtime/bin/ollama" serve > artifacts/ollama-setup.log 2>&1 &
  server_pid=$!
  for _ in {1..60}; do
    if curl -fsS "http://$OLLAMA_HOST/api/version" >/dev/null 2>&1; then break; fi
    sleep 1
  done
fi
"$runtime/bin/ollama" create roboinspect-bielik:q4_k_m -f config/Bielik.Modelfile
printf '\nBielik gotowy. Uruchamiaj standardowo scripts/run_cockpit.sh i scripts/run_control_panel.sh.\n'
