"""Bridge from application threads to the single ROS executor."""

import threading
import time
from queue import Full

from .contracts import RobotState


class RosRobot:
    def __init__(self, operator):
        self.operator = operator

    def snapshot(self):
        return RobotState.model_validate(self.operator.snapshot()).model_dump(mode="json")

    def _command(self, kind, data=None):
        reply, done = {}, threading.Event()
        try:
            self.operator.commands.put_nowait((kind, data, reply, done, time.monotonic() + 4))
        except Full as exc:
            raise RuntimeError("Kolejka robota jest pełna") from exc
        if not done.wait(5):
            raise RuntimeError("Niepotwierdzone wykonanie polecenia ROS")
        if reply.get("code", 500) >= 400:
            raise RuntimeError(reply.get("error", "Polecenie odrzucone"))
        return reply

    def start(self, target, execution_id):
        return self._command("goal", {"target": target, "execution_id": execution_id})

    def cancel(self):
        return self._command("cancel")

    def recover(self):
        return self._command("recover")
