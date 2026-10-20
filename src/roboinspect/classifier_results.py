"""Read-only presentation of local pilot training results, with constrained artifact paths."""

import html
import json
from pathlib import Path
from uuid import UUID

from .banner_conditions import ROOT
from .classifier import CLASSES


def latest_result(root=ROOT):
    path = root / "data/classifier/latest.json"
    if not path.is_file():
        return None
    index = json.loads(path.read_text())
    result_path = Path(index["results"])
    base = (root / "data/classifier/runs").resolve()
    if not result_path.resolve().is_relative_to(base) or result_path.name != "results.json":
        raise ValueError("Nieprawidłowy wynik treningu")
    if str(UUID(result_path.parent.name)) != result_path.parent.name:
        raise ValueError("Nieprawidłowy identyfikator treningu")
    report = json.loads(result_path.read_text())
    if report["config"]["snapshot_id"] != index["snapshot_id"]:
        raise ValueError("Niezgodny snapshot wyników")
    return report


def result_asset(root, name):
    if name not in (
        "baseline-test-confusion.svg",
        "resnet18-test-confusion.svg",
        "baseline-validation-confusion.svg",
        "resnet18-validation-confusion.svg",
    ):
        raise FileNotFoundError("Nieznany wykres")
    report = latest_result(root)
    if not report:
        raise FileNotFoundError("Brak treningu")
    path = Path(report["run_directory"]) / name
    base = (root / "data/classifier/runs").resolve()
    if path.is_symlink() or not path.resolve().is_relative_to(base) or not path.is_file():
        raise FileNotFoundError("Brak wykresu")
    return path


def training_page(root=ROOT):
    report = latest_result(root)
    opening = '<!doctype html><html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>RoboInspect · Trening klasyfikatora</title><link rel="stylesheet" href="/style.css"></head><body><main class="dataset-report"><a class="link" href="/control">Panel sterowania</a><h1>Pierwszy model stanu tablicy</h1>'
    if report is None:
        return (
            opening
            + "<p>Nie wykonano jeszcze treningu. Instrukcja znajduje się w docs/classifier-training.md.</p></main></body></html>"
        )
    cards = []
    for name, title in [
        ("baseline", "Model porównawczy: cechy obrazu + ridge"),
        ("resnet18", "ResNet18: dostrajany klasyfikator"),
    ]:
        value = report["test"][name]
        rows = "".join(
            "<tr><td>"
            + html.escape(label)
            + "</td>"
            + "".join(
                f"<td>{value['per_class'][label][metric]:.3f}</td>"
                for metric in ("precision", "recall", "f1")
            )
            + f"<td>{value['per_class'][label]['support']}</td></tr>"
            for label in CLASSES
        )
        cards.append(
            f'<article><h2>{title}</h2><p>Test: accuracy <strong>{value["accuracy"]:.1%}</strong> · macro F1 <strong>{value["macro_f1"]:.3f}</strong> · {value["n"]} kadrów</p><div class="dataset-table"><table><thead><tr><th>Klasa</th><th>Precision</th><th>Recall</th><th>F1</th><th>Próbki</th></tr></thead><tbody>{rows}</tbody></table></div><img src="/api/classifier/artifacts/{name}-test-confusion.svg" alt="Macierz pomyłek {name}"></article>'
        )
    chosen = html.escape(report["selection"]["selected"])
    snapshot = html.escape(report["config"]["snapshot_id"])
    counts = report["split_counts"]
    groups = report["source_group_counts"]
    mlflow_url = (
        "http://127.0.0.1:5001/#/experiments"  # No deployment or model loading from this page.
    )
    return (
        opening
        + f'<p class="help">Pilot na syntetycznych stanach tablic. Wynik nie dowodzi jakości na prawdziwych usterkach.</p><p>Wybrany model: <strong>{chosen}</strong>. Wybór na podstawie walidacji, przed oceną testową. Brak automatycznego wdrożenia do robota.</p><p>Dane: trening {counts["train"]}, walidacja {counts["validation"]}, test {counts["test"]}. Grupy zdjęć źródłowych: {groups["train"]}/{groups["validation"]}/{groups["test"]}.</p><p>Najlepsza epoka ResNet18: {report["selection"]["best_epoch"]}. Wagi ostatniego bloku i głowicy dostrojone na lokalnej RTX.</p><p class="help">Snapshot: {snapshot}</p><a class="link" href="{mlflow_url}" target="_blank" rel="noopener">Otwórz MLflow: roboinspect-classifier</a>'
        + "".join(cards)
        + '<p class="help">Wcześniejsze zbiorcze zatwierdzenia użytkownika zachowano. Nowe wycinki przeszły pilotażowy przegląd wizualny asystenta. Test zawiera tylko 40 kadrów z 5 zdjęć źródłowych. Wyników testowych nie używano do strojenia. Oceny pewności nie są skalibrowane.</p></main></body></html>'
    )
