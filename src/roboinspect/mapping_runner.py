"""Single supervisor-owned executor for durable mapping operations."""

import json
import subprocess
import time

from roboinspect.contracts import MappingAction, MissionStatus
from roboinspect.operations import WAREHOUSE_KINDS


class MappingCanceled(Exception):
    pass


class MappingRunner:
    def __init__(self, manager, store):
        self.manager, self.store = manager, store
        self.current = None
        self.process = None
        self.log = None
        self.log_path = None
        self.logged = 0

    def progress(self, message):
        self.store.update_operation(self.current.id, message=message)

    def canceled(self, message):
        self.store.update_operation(self.current.id, status=MissionStatus.CANCELED, message=message)
        self.current = None
        self.process = None
        if self.log:
            self.log.close()
            self.log = None

    def save(self):
        self.progress("Zapisywanie mapy i grafu SLAM…")
        name = "hangar_" + self.current.id.replace("-", "")
        command = [
            str(self.manager.root / ".venv/bin/python"),
            str(self.manager.root / "scripts/slam_tools.py"),
            "save",
            "--name",
            name,
            "--operation-id",
            self.current.id,
        ]
        with (self.manager.log_dir / f"save-{self.current.id}.log").open("w") as output:
            process = subprocess.Popen(
                command,
                cwd=self.manager.root,
                stdout=output,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            deadline = time.monotonic() + 60
            while process.poll() is None:
                if self.store.operation(self.current.id).cancel_requested:
                    self.manager.stop(process)
                    raise MappingCanceled()
                if self.manager.shutdown.wait(0.2) or time.monotonic() > deadline:
                    self.manager.stop(process)
                    raise RuntimeError("Zapis mapy przerwany lub przekroczył limit czasu")
            if process.returncode:
                raise RuntimeError(f"Zapis mapy nie powiódł się; zobacz save-{self.current.id}.log")
        path = self.manager.root / "data/maps" / f"{name}.yaml"
        if not path.is_file():
            raise RuntimeError("Brak pliku zapisanej mapy")
        self.store.update_operation(
            self.current.id, saved_map=str(path), message=f"Zapisano wersję mapy: {path.name}"
        )
        return path

    def tick(self):
        if self.current and self.process:
            job = self.store.operation(self.current.id)
            lines = self.log_path.read_text(errors="replace").splitlines()
            for line in lines[self.logged :]:
                if line.startswith("PASS: punkt"):
                    self.progress(line.replace("PASS: punkt", "Ukończono punkt"))
            self.logged = len(lines)
            if job.cancel_requested:
                self.manager.stop(self.process)
                self.canceled("Obchód przerwany; robot zatrzymany, pozostałe punkty pominięto")
                return
            code = self.process.poll()
            if code is None:
                return
            self.log.close()
            self.log = None
            self.process = None
            if code:
                self.store.update_operation(
                    job.id,
                    status=MissionStatus.FAILED,
                    message="Obchód zatrzymany z błędem. " + (" ".join(lines[-3:]))[-600:],
                )
            else:
                self.store.update_operation(
                    job.id,
                    status=MissionStatus.SUCCEEDED,
                    message="Obchód zakończony; robot zatrzymany. Zapisz mapę lub zakończ mapowanie.",
                )
            self.current = None
        if self.current:
            return
        jobs = self.store.operation_busy()
        job = next((j for j in jobs if j.status == MissionStatus.QUEUED), None)
        if job is None:
            return
        self.current = job
        if job.cancel_requested:
            self.canceled("Operacja anulowana przed uruchomieniem")
            return
        self.store.update_operation(
            job.id, status=MissionStatus.RUNNING, message="Rozpoczynanie operacji…"
        )
        try:
            if job.kind == MappingAction.START:
                self.progress("Ustawianie robota w BASE i uruchamianie świeżego SLAM…")
                self.manager.switch("mapping", None)
                if self.store.operation(job.id).cancel_requested:
                    self.canceled("Obchód anulowany przed rozpoczęciem jazdy")
                    return
                self.progress("Mapowanie w toku: obchód 8 punktów hali")
                self.log_path = self.manager.log_dir / f"survey-{job.id}.log"
                self.log = self.log_path.open("w")
                self.logged = 0
                self.process = subprocess.Popen(
                    [
                        str(self.manager.root / ".venv/bin/python"),
                        str(self.manager.root / "scripts/slam_tools.py"),
                        "survey",
                        "--operation-id",
                        job.id,
                    ],
                    cwd=self.manager.root,
                    stdout=self.log,
                    stderr=subprocess.STDOUT,
                    start_new_session=True,
                )
                return
            if job.kind in WAREHOUSE_KINDS:
                self.progress("Przygotowanie układu i sprawdzanie drogi do wszystkich celów…")
                selection = self.manager.change_warehouse(
                    job.kind.value.removeprefix("warehouse_"),
                    job.layout_seed,
                    lambda: self.store.operation(job.id).cancel_requested,
                )
                message = (
                    f"Magazyn gotowy. Robot w BASE; przeszkody: {selection['movable_count']}. "
                    "Wszystkie czerwone strefy i punkty P są dostępne."
                )
            elif job.kind == MappingAction.RESET:
                self.progress("Reset bieżącej mapy i powrót robota do BASE…")
                self.manager.switch("mapping", None)
                message = "Bieżąca mapa wyzerowana. Zapisane wersje i historia zostały zachowane."
            elif job.kind == MappingAction.SAVE:
                self.save()
                message = "Mapa i graf zapisane; można kontynuować mapowanie."
            else:
                path = self.save()
                if self.store.operation(job.id).cancel_requested:
                    raise MappingCanceled()
                self.progress("Mapa zapisana. Przełączanie na AMCL + Nav2; robot startuje w BASE…")
                self.manager.switch("navigation", path)
                selection = self.manager.root / "data/current-map.json"
                temporary = selection.with_suffix(".tmp")
                temporary.write_text(
                    json.dumps(
                        {
                            "scenario": self.manager.scenario,
                            "map": str(path),
                            "layout_id": getattr(self.manager, "warehouse", {}).get(
                                "layout_id", "standard"
                            ),
                        }
                    )
                    + "\n"
                )
                temporary.replace(selection)
                message = "Mapowanie zakończone. Nav2 gotowe na zapisanej mapie; robot w BASE."
            if self.store.operation(job.id).cancel_requested:
                raise MappingCanceled()
            self.store.update_operation(job.id, status=MissionStatus.SUCCEEDED, message=message)
        except MappingCanceled:
            self.store.update_operation(
                job.id, status=MissionStatus.CANCELED, message="Operacja zatrzymana poleceniem STOP"
            )
        except Exception as exc:
            self.store.update_operation(
                job.id, status=MissionStatus.FAILED, message=str(exc)[:1000]
            )
        self.current = None

    def close(self):
        if self.process:
            self.manager.stop(self.process)
        if self.log:
            self.log.close()
        self.store.interrupt_operations()
