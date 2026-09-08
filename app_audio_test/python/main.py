"""App Lab entry point: receive mono acoustic events and persist checked WAVs."""

import os
from pathlib import Path
from queue import Full, Queue
from threading import Thread
from arduino.app_utils import App, Bridge, Logger
from event_receiver import EventReceiver, write_event

logger = Logger("SylvaEchoLens")
receiver = EventReceiver()
pending = Queue(maxsize=2)
output = Path(os.getenv("SYLVA_EVENT_DIR", "/app/events"))


def save_loop():
    while True:
        event = pending.get()
        try:
            path, metadata = write_event(output, event)
            logger.info(
                f"Event saved: {path.name}; RMS={metadata['rms']:.2f}; "
                f"peak={metadata['peak']}; sha256={metadata['sha256']}"
            )
            # Attach inference here in the next milestone, outside Bridge callbacks.
        except Exception:
            logger.exception("Event persistence failed")
        finally:
            pending.task_done()


def guarded(operation, *args):
    try:
        return operation(*args)
    except (ValueError, TypeError) as exc:
        logger.warning(f"Event rejected: {exc}")
        return None


def on_boot(version, state, error):
    receiver.reset()
    logger.info(f"MCU boot: protocol={version}, state={state}, error={error}")


def on_begin(*args):
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


def on_level(state, rms, floor, opening, closing, skipped):
    logger.info(
        f"Gate {state}: RMS={float(rms):.1f}, floor={float(floor):.1f}, "
        f"open={float(opening):.1f}, close={float(closing):.1f}, skipped={skipped}"
    )


Bridge.provide("sylva_boot", on_boot)
Bridge.provide("sylva_begin", on_begin)
Bridge.provide("sylva_chunk", on_chunk)
Bridge.provide("sylva_end", on_end)
Bridge.provide("sylva_level", on_level)
Bridge.provide("sylva_error", lambda error: logger.error(f"MCU capture error: {error}"))
Thread(target=save_loop, daemon=True, name="event-writer").start()
logger.info("Ready for mono events; startup calibration takes about five seconds")
App.run()
