#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
export KUBECONFIG="$PWD/data/deploy/kubeconfig"
exec data/deploy/bin/kubectl --context kind-roboinspect -n roboinspect get pods,svc,pvc
