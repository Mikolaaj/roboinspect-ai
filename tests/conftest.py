from copy import deepcopy

import pytest

from roboinspect.missions import MissionService
from roboinspect.store import MissionStore


class FakeRobot:
    def __init__(self):
        self.state = dict(
            service="roboinspect",
            ready=True,
            busy=False,
            state="idle",
            velocity=dict(linear=0.0, angular=0.0),
            remote_active=False,
        )
        self.calls = []
        self.recoveries = 0

    def snapshot(self):
        return deepcopy(self.state)

    def start(self, target, execution_id):
        self.calls.append(target)
        self.state.update(
            busy=True,
            state="navigating",
            execution_id=execution_id,
            goal=target,
            velocity=dict(linear=0.2, angular=0.0),
        )

    def finish(self, status="succeeded"):
        self.state.update(busy=False, state=status, velocity=dict(linear=0.0, angular=0.0))

    def cancel(self):
        self.finish("canceled")

    def recover(self):
        self.recoveries += 1
        self.finish("canceled")
        self.state["recovery_state"] = "succeeded"


@pytest.fixture
def service(tmp_path):
    store = MissionStore(f"sqlite:///{tmp_path / 'missions.db'}")
    robot = FakeRobot()
    executor = MissionService(store, robot, "normal", tmp_path / "owner.lock")
    yield executor
    executor.close()
    store.close()
