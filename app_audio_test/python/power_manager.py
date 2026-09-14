"""Coordinate event-driven Linux suspend with a privileged host helper."""

from dataclasses import dataclass
import os
from pathlib import Path
from threading import Event, Lock
import time


def _positive_float(name, default):
    try:
        value = float(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be a number") from exc
    if value <= 0:
        raise ValueError(f"{name} must be positive")
    return value


@dataclass(frozen=True)
class PowerPolicy:
    """Suspend policy shared by the unprivileged app and host helper."""

    # Suspend-to-idle did not pass device wake acceptance. Keep the release-safe
    # default awake; a future experiment must opt in explicitly.
    mode: str = "disabled"
    idle_seconds: float = 60.0
    request_timeout_seconds: float = 120.0
    directory: Path = Path("/app/power")

    def __post_init__(self):
        if self.mode not in ("disabled", "freeze"):
            raise ValueError("SYLVA_LINUX_SUSPEND must be disabled or freeze")
        if self.idle_seconds <= 0:
            raise ValueError("SYLVA_SUSPEND_IDLE_SECONDS must be positive")
        if self.request_timeout_seconds <= 0:
            raise ValueError("SYLVA_SUSPEND_REQUEST_TIMEOUT_SECONDS must be positive")

    @classmethod
    def from_environment(cls):
        return cls(
            mode=os.getenv("SYLVA_LINUX_SUSPEND", cls.mode).strip().lower(),
            idle_seconds=_positive_float("SYLVA_SUSPEND_IDLE_SECONDS", cls.idle_seconds),
            request_timeout_seconds=_positive_float(
                "SYLVA_SUSPEND_REQUEST_TIMEOUT_SECONDS",
                cls.request_timeout_seconds,
            ),
            directory=Path(os.getenv("SYLVA_POWER_DIR", str(cls.directory))),
        )


class LinuxSuspendCoordinator:
    """Request suspend only after the MCU and application agree that it is safe."""

    def __init__(
        self,
        policy,
        arm_mcu,
        is_idle,
        logger,
        monotonic=time.monotonic,
        poll_seconds=1.0,
    ):
        self.policy = policy
        self.arm_mcu = arm_mcu
        self.is_idle = is_idle
        self.logger = logger
        self.monotonic = monotonic
        self.poll_seconds = poll_seconds
        self.ready_path = policy.directory / "helper.ready"
        self.request_path = policy.directory / "suspend.request"
        self.result_path = policy.directory / "suspend.result"
        self.last_activity = monotonic()
        self.requested_at = None
        self._waiting = False
        self._helper_warning_emitted = False
        self._helper_was_ready = self._helper_supports_mode()
        self._lock = Lock()

    def note_activity(self):
        """Delay suspend after a transfer, boot notification, or resume."""
        with self._lock:
            self.last_activity = self.monotonic()

    def _helper_supports_mode(self):
        try:
            modes = self.ready_path.read_text(encoding="ascii").split()
            return self.policy.mode in modes
        except OSError:
            return False

    @property
    def helper_ready(self):
        return self._helper_supports_mode()

    def _publish_request(self):
        self.policy.directory.mkdir(parents=True, exist_ok=True)
        temporary = self.request_path.with_name(f".{self.request_path.name}.tmp")
        with temporary.open("w", encoding="ascii") as stream:
            stream.write(f"{self.policy.mode}\n")
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.request_path)

    def _consume_result(self):
        try:
            lines = self.result_path.read_text(encoding="ascii").splitlines()
            result = dict(line.split("=", 1) for line in lines if "=" in line)
            self.result_path.unlink(missing_ok=True)
            return result
        except OSError:
            return None

    def _finish_request(self, result):
        self._waiting = False
        self.requested_at = None
        try:
            self.arm_mcu(False)
        finally:
            self.note_activity()
        status = result.get("status", "unknown")
        if status == "resumed":
            self.logger.info(
                "Linux resumed from suspend-to-idle; "
                f"wake_irq={result.get('wake_irq', 'unknown')}"
            )
        else:
            self.logger.warning(
                f"Linux suspend request ended with status={status}; "
                f"reason={result.get('reason', 'unspecified')}"
            )

    def step(self):
        """Advance the coordinator once; separated from the loop for host tests."""
        if self.policy.mode == "disabled":
            return

        result = self._consume_result()
        if result is not None:
            self._finish_request(result)

        now = self.monotonic()
        if self._waiting:
            if now - self.requested_at >= self.policy.request_timeout_seconds:
                self.request_path.unlink(missing_ok=True)
                self._finish_request({"status": "failed", "reason": "helper_timeout"})
            return

        helper_ready = self._helper_supports_mode()
        if not helper_ready:
            self._helper_was_ready = False
            if not self._helper_warning_emitted:
                self.logger.warning(
                    "Linux suspend is configured but the privileged helper is not ready"
                )
                self._helper_warning_emitted = True
            return

        # Installing or re-enabling the helper is an explicit state transition.
        # Restart the idle window so activation cannot suspend an unattended board
        # immediately because of time accumulated while the helper was absent.
        if not self._helper_was_ready:
            self._helper_was_ready = True
            self._helper_warning_emitted = False
            self.note_activity()
            self.logger.info("Linux suspend helper became ready; idle timer restarted")
            return

        with self._lock:
            idle_for = now - self.last_activity
        if idle_for < self.policy.idle_seconds or not self.is_idle():
            return

        # Arm the MCU first. Once armed it suppresses periodic telemetry and sends
        # one wake notification before transferring the next captured event.
        if not self.arm_mcu(True):
            self.note_activity()
            self.logger.warning("MCU rejected Linux suspend because capture is busy")
            return

        try:
            self._publish_request()
        except OSError:
            self.arm_mcu(False)
            self.note_activity()
            self.logger.exception("Could not publish Linux suspend request")
            return

        self._waiting = True
        self.requested_at = now
        self.logger.info("Linux suspend-to-idle requested; MCU event wake is armed")

    def run(self, stop_event=None):
        stop_event = stop_event or Event()
        while not stop_event.wait(self.poll_seconds):
            try:
                self.step()
            except Exception:
                self.logger.exception("Linux suspend coordinator failed")
