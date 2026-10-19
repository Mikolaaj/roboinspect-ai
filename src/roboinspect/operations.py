"""Accept durable mapping jobs; one supervisor executes them outside the API."""

from .contracts import ConflictError, MappingAction, MappingOperation

TITLES = {
    MappingAction.START: "Mapowanie hangaru",
    MappingAction.SAVE: "Zapis mapy SLAM",
    MappingAction.RESET: "Reset bieżącej mapy",
    MappingAction.FINISH: "Zakończenie mapowania i nawigacja",
}


def request_operation(service, action: MappingAction, key: str | None):
    if action.value.startswith("warehouse_"):
        raise ConflictError("Użyj panelu ustawień magazynu")
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


WAREHOUSE_KINDS = {
    MappingAction.WAREHOUSE_STANDARD,
    MappingAction.WAREHOUSE_CLEAR,
    MappingAction.WAREHOUSE_RANDOM,
    MappingAction.WAREHOUSE_PICTURES,
}
WAREHOUSE_TITLES = {
    MappingAction.WAREHOUSE_STANDARD: "Standardowe ustawienie magazynu",
    MappingAction.WAREHOUSE_CLEAR: "Usunięcie wszystkich przeszkód",
    MappingAction.WAREHOUSE_RANDOM: "Losowanie przeszkód w magazynie",
    MappingAction.WAREHOUSE_PICTURES: "Zmiana zdjęć na banerach",
}


def request_warehouse(service, action, key):
    import secrets

    from .missions import stationary

    kind = MappingAction("warehouse_" + action.value)
    with service.lock:
        if key and (previous := service.store.operation_key(key)):
            if previous.kind != kind:
                raise ConflictError("Klucz został użyty do innej operacji")
            return previous, False
        state = service.robot.snapshot()
        if not state.get("mapping_controls") or state.get("scenario") != "normal":
            raise ConflictError("Zmiana magazynu wymaga kokpitu standardowego hangaru")
        if (
            not service.healthy
            or not state.get("ready")
            or state.get("mode") != "navigation"
            or not stationary(state)
            or service.store.active()
            or service.store.operation_busy()
            or state.get("busy")
            or state.get("remote_active")
        ):
            raise ConflictError("Zakończ mapowanie lub przejazd i poczekaj na gotowość robota")
        record = MappingOperation(
            kind=kind,
            name=WAREHOUSE_TITLES[kind],
            layout_seed=secrets.randbits(32) if action.value in ("random", "pictures") else None,
        )
        service.store.create_operation(record, key)
        return record, True
