import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_audio_test" / "python"))
from power_manager import LinuxSuspendCoordinator, PowerPolicy


class FakeLogger:
    def __init__(self):
        self.messages = []

    def info(self, message):
        self.messages.append(("info", message))

    def warning(self, message):
        self.messages.append(("warning", message))

    def exception(self, message):
        self.messages.append(("exception", message))


class SuspendCoordinatorTests(unittest.TestCase):
    def make_coordinator(self, directory, clock, armed, idle=lambda: True, **policy):
        values = {
            "mode": "freeze",
            "idle_seconds": 10,
            "request_timeout_seconds": 20,
            "directory": Path(directory),
        }
        values.update(policy)
        logger = FakeLogger()
        coordinator = LinuxSuspendCoordinator(
            PowerPolicy(**values),
            arm_mcu=lambda enabled: armed.append(enabled) or True,
            is_idle=idle,
            logger=logger,
            monotonic=lambda: clock[0],
            poll_seconds=0.01,
        )
        return coordinator, logger

    def test_default_policy_keeps_linux_awake(self):
        self.assertEqual(PowerPolicy().mode, "disabled")

    def test_missing_helper_never_arms_or_requests_suspend(self):
        with tempfile.TemporaryDirectory() as temporary:
            clock = [30]
            armed = []
            coordinator, logger = self.make_coordinator(temporary, clock, armed)
            coordinator.step()
            self.assertEqual(armed, [])
            self.assertFalse((Path(temporary) / "suspend.request").exists())
            self.assertIn("not ready", logger.messages[0][1])

    def test_new_helper_restarts_idle_window_before_first_suspend(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            clock = [30]
            armed = []
            coordinator, logger = self.make_coordinator(root, clock, armed)
            coordinator.step()
            (root / "helper.ready").write_text("freeze\n", encoding="ascii")
            coordinator.step()
            self.assertEqual(armed, [])
            self.assertEqual(coordinator.last_activity, 30)
            self.assertIn("idle timer restarted", logger.messages[-1][1])
            clock[0] = 41
            coordinator.step()
            self.assertEqual(armed, [True])

    def test_idle_handshake_arms_mcu_before_atomic_request(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "helper.ready").write_text("freeze\n", encoding="ascii")
            clock = [0]
            armed = []
            coordinator, _ = self.make_coordinator(root, clock, armed)
            clock[0] = 11
            coordinator.step()
            self.assertEqual(armed, [True])
            self.assertEqual((root / "suspend.request").read_text(), "freeze\n")
            self.assertTrue(coordinator._waiting)

    def test_busy_pipeline_delays_suspend(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "helper.ready").write_text("freeze\n", encoding="ascii")
            clock = [11]
            armed = []
            coordinator, _ = self.make_coordinator(root, clock, armed, idle=lambda: False)
            coordinator.last_activity = 0
            coordinator.step()
            self.assertEqual(armed, [])

    def test_resume_result_disarms_mcu_and_restarts_idle_window(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "helper.ready").write_text("freeze\n", encoding="ascii")
            clock = [0]
            armed = []
            coordinator, logger = self.make_coordinator(root, clock, armed)
            clock[0] = 11
            coordinator.step()
            (root / "suspend.request").unlink()
            (root / "suspend.result").write_text(
                "status=resumed\nwake_irq=1\n", encoding="ascii"
            )
            clock[0] = 12
            coordinator.step()
            self.assertEqual(armed, [True, False])
            self.assertEqual(coordinator.last_activity, 12)
            self.assertIn("wake_irq=1", logger.messages[-1][1])

    def test_helper_timeout_fails_open_and_disarms_mcu(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "helper.ready").write_text("freeze\n", encoding="ascii")
            clock = [0]
            armed = []
            coordinator, logger = self.make_coordinator(root, clock, armed)
            clock[0] = 11
            coordinator.step()
            clock[0] = 32
            coordinator.step()
            self.assertEqual(armed, [True, False])
            self.assertFalse((root / "suspend.request").exists())
            self.assertIn("helper_timeout", logger.messages[-1][1])

    def test_environment_policy_is_validated(self):
        with patch.dict(os.environ, {"SYLVA_LINUX_SUSPEND": "hibernate"}, clear=True):
            with self.assertRaisesRegex(ValueError, "SYLVA_LINUX_SUSPEND"):
                PowerPolicy.from_environment()


if __name__ == "__main__":
    unittest.main()
