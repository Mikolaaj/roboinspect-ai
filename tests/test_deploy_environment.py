import importlib.util
import os
from pathlib import Path

spec = importlib.util.spec_from_file_location(
    "kube_common", Path(__file__).resolve().parents[1] / "scripts/kube_common.py"
)
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)


def test_kubernetes_commands_do_not_depend_on_local_dotenv(monkeypatch):
    for key in ("ROBOINSPECT_ROOT", "ROBOINSPECT_UID", "ROBOINSPECT_GID", "KUBECONFIG"):
        monkeypatch.delenv(key, raising=False)
    result = common.env()
    assert result["ROBOINSPECT_ROOT"] == str(common.ROOT)
    assert result["ROBOINSPECT_UID"] == str(os.getuid())
    assert result["ROBOINSPECT_GID"] == str(os.getgid())
    assert result["KUBECONFIG"] == str(common.STATE / "kubeconfig")
    assert result["PATH"].split(os.pathsep)[0] == str(common.BIN)
