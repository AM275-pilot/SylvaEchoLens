"""App Lab entry point: receive and persist bounded offline observations."""

import os
from pathlib import Path
from queue import Full, Queue
from threading import Event, Thread
from arduino.app_utils import App, Bridge, Logger
from classification import classifier_from_environment
from event_receiver import EventReceiver
from offline_store import ObservationStore
from power_manager import LinuxSuspendCoordinator, PowerPolicy


def run_app():
    """Build and run the application only in the primary App Lab process.

    BirdNET uses Python multiprocessing. Spawned inference workers import this file
    as ``__mp_main__``; keeping runtime setup inside this function prevents them
    from creating a second store, Bridge, or application instance.
    """
    logger = Logger("SylvaEchoLens")
    # Bound memory while inference or flash writes lag behind the MCU event stream.
    # Overflow is explicit in logs instead of allowing unbounded Linux allocation.
    pending = Queue(maxsize=2)
    writer_busy = Event()
    output = Path(os.getenv("SYLVA_EVENT_DIR", "/app/events"))
    store = ObservationStore(output)
    clock = store.clock()
    receiver = EventReceiver(timestamp_factory=clock.observe)
    classifier = classifier_from_environment()

    def set_mcu_power_save(enabled):
        try:
            return bool(Bridge.call("sylva_power_save", bool(enabled), timeout=3))
        except Exception:
            logger.exception("Could not change the MCU power-save state")
            return False

    def power_idle():
        return receiver.current is None and pending.empty() and not writer_busy.is_set()

    power = LinuxSuspendCoordinator(
        PowerPolicy.from_environment(),
        arm_mcu=set_mcu_power_save,
        is_idle=power_idle,
        logger=logger,
    )

    def save_loop():
        # A single writer serializes quota decisions, retention, state, and sidecars.
        while True:
            event = pending.get()
            writer_busy.set()
            try:
                path, metadata = store.persist(
                    event, classifier.classify if classifier else None
                )
                artifact = path.name if path else "recognition-only"
                classification = metadata.get("classification")
                decision = (
                    f"; birdnet={classification['label']} "
                    f"score={classification['score']:.3f} "
                    f"accepted={classification['accepted']}"
                    if classification else ""
                )
                logger.info(
                    f"Event saved: {artifact}; "
                    f"audio={metadata['audio']['status']}; RMS={metadata['rms']:.2f}; "
                    f"peak={metadata['peak']}; sha256={metadata['sha256']}{decision}"
                )
                if "classification_error" in metadata:
                    logger.warning(
                        f"Inference failed for {artifact}: "
                        f"{metadata['classification_error']['message']}"
                    )
            except Exception:
                logger.exception("Event persistence failed")
            finally:
                writer_busy.clear()
                power.note_activity()
                pending.task_done()

    def guarded(operation, *args):
        try:
            return operation(*args)
        except (ValueError, TypeError) as exc:
            logger.warning(f"Event rejected: {exc}")
            return None

    def on_boot(version, state, error):
        # Discard any partial transfer because the MCU cannot resume it after reboot.
        receiver.reset()
        power.note_activity()
        logger.info(f"MCU boot: protocol={version}, state={state}, error={error}")

    def on_begin(*args):
        power.note_activity()
        guarded(receiver.begin, *args)

    def on_chunk(*args):
        guarded(receiver.chunk, *args)

    def on_end(*args):
        event = guarded(receiver.end, *args)
        if event is None:
            return
        try:
            pending.put_nowait(event)
        except Full:
            logger.warning("Event dropped: persistence queue is full")

    def on_wake(event_id):
        power.note_activity()
        logger.info(f"MCU event {event_id} requested Linux wake")

    def on_level(state, rms, floor, opening, closing, skipped):
        logger.info(
            f"Gate {state}: RMS={float(rms):.1f}, floor={float(floor):.1f}, "
            f"open={float(opening):.1f}, close={float(closing):.1f}, skipped={skipped}"
        )

    Bridge.provide("sylva_boot", on_boot)
    Bridge.provide("sylva_begin", on_begin)
    Bridge.provide("sylva_chunk", on_chunk)
    Bridge.provide("sylva_end", on_end)
    Bridge.provide("sylva_wake", on_wake)
    Bridge.provide("sylva_level", on_level)
    Bridge.provide("sylva_error", lambda error: logger.error(f"MCU capture error: {error}"))
    Thread(target=save_loop, daemon=True, name="event-writer").start()
    Thread(target=power.run, daemon=True, name="linux-suspend").start()
    logger.info("Ready for mono events; startup calibration takes about five seconds")
    logger.info(
        f"Offline storage ready: audio_budget={store.policy.audio_budget_bytes}; "
        f"record_reserve={store.policy.record_reserve_bytes}; "
        f"system_reserve={store.policy.system_reserve_bytes}; "
        f"retention={store.policy.retention}; recovery={store.recovery_report}"
    )
    logger.info(
        f"Clock evidence: source={clock.source}; quality={clock.quality}; "
        f"uncertainty_seconds={clock.uncertainty_seconds}"
    )
    logger.info(
        "Offline BirdNET v2.4 classification enabled"
        if classifier else "Local classification disabled"
    )
    logger.info(
        f"Linux suspend policy: mode={power.policy.mode}; "
        f"idle_seconds={power.policy.idle_seconds}; "
        f"helper_ready={power.helper_ready}"
    )
    App.run()


if __name__ == "__main__":
    run_app()
