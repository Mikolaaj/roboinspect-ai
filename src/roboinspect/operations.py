"""Accept durable mapping jobs; one supervisor executes them outside the API."""

from .contracts import ConflictError, MappingAction, MappingOperation

TITLES = {
    MappingAction.START: "Mapowanie hangaru",
    MappingAction.SAVE: "Zapis mapy SLAM",
    MappingAction.RESET: "Reset bieżącej mapy",
    MappingAction.FINISH: "Zakończenie mapowania i nawigacja",
}


def request_operation(service, action: MappingAction, key: str | None):
    # Shared lock with mission creation: an operation and a mission cannot race.
    with service.lock:
        store = service.store
        if key and (previous := store.operation_key(key)):
            if previous.kind != action:
                raise ConflictError("Klucz został użyty do innej operacji")
            return previous, False
        state = service.robot.snapshot()
        if not state.get("mapping_controls"):
            raise ConflictError("Uruchom kokpit z obsługą operacji mapowania")
        if state.get("scenario") != "normal":
            raise ConflictError("Obchód mapujący obsługuje obecnie halę standardową")
        if store.active() or state.get("busy") or state.get("remote_active"):
            raise ConflictError("Najpierw zakończ lub anuluj misję nawigacyjną")
        jobs = store.operation_busy()
        if jobs:
            # Reset/finish can interrupt a survey, but never another mode transition/save.
            if (
                action not in (MappingAction.RESET, MappingAction.FINISH)
                or len(jobs) != 1
                or jobs[0].kind != MappingAction.START
                or jobs[0].cancel_requested
            ):
                raise ConflictError("Inna operacja mapowania jest w toku")
        elif action in (MappingAction.SAVE, MappingAction.FINISH):
            if state.get("mode") != "mapping" or not state.get("mapping_ready"):
                raise ConflictError("Najpierw rozpocznij mapowanie")
        record = MappingOperation(kind=action, name=TITLES[action])
        store.create_operation(record, key, cancel_id=jobs[0].id if jobs else None)
        return record, True
