#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
target_dir="$PWD/data/deploy/bin"
mkdir -p "$target_dir"
[[ "$(uname -m)" == x86_64 ]] || { echo 'Ten skrypt obsługuje Linux x86_64'; exit 1; }
curl -fsSL --retry 2 https://dl.k8s.io/release/v1.34.1/bin/linux/amd64/kubectl -o "$target_dir/kubectl"
curl -fsSL --retry 2 https://dl.k8s.io/release/v1.34.1/bin/linux/amd64/kubectl.sha256 -o "$target_dir/kubectl.sha256"
curl -fsSL --retry 2 https://github.com/kubernetes-sigs/kind/releases/download/v0.30.0/kind-linux-amd64 -o "$target_dir/kind"
curl -fsSL --retry 2 https://github.com/kubernetes-sigs/kind/releases/download/v0.30.0/kind-linux-amd64.sha256sum -o "$target_dir/kind.sha256"
python3 - <<'PY'
from pathlib import Path
import hashlib
for name in ('kind','kubectl'):
 p=Path('data/deploy/bin')/name
 assert hashlib.sha256(p.read_bytes()).hexdigest()==(p.parent/(name+'.sha256')).read_text().split()[0], name
 p.chmod(0o755)
 print(name, 'checksum OK')
PY
