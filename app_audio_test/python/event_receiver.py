"""Strict event assembly, independent of App Lab and suitable for host tests."""

from datetime import datetime, timezone
import math
import struct
import time
import uuid
import zlib

SAMPLE_RATE = 16000
CHUNK_SAMPLES = 256
EVENT_SAMPLES = 32768
PRE_SAMPLES = 8192


def decode_chunk(encoded):
    """Decode numeric high-byte-first hex into signed PCM16 little-endian bytes."""
    if not isinstance(encoded, str) or len(encoded) != CHUNK_SAMPLES * 4:
        raise ValueError("invalid chunk length")
    raw = bytes.fromhex(encoded)
    if len(raw) != CHUNK_SAMPLES * 2:
        raise ValueError("invalid PCM payload")
    values = struct.unpack(f">{CHUNK_SAMPLES}h", raw)
    return struct.pack(f"<{CHUNK_SAMPLES}h", *values)


class EventReceiver:
    """One in-flight event, bounded to 64 KiB and a 60-second receive timeout."""

    def __init__(self, clock=time.monotonic, timestamp_factory=None):
        self.clock = clock
        self.timestamp_factory = timestamp_factory or self._default_timestamp
        self.reset()

    @staticmethod
    def _default_timestamp():
        return {
            "utc": datetime.now(timezone.utc).isoformat(),
            "quality": "unverified",
            "source": "system_clock",
            "uncertainty_seconds": None,
            "boot_id": None,
            "monotonic_seconds": time.monotonic(),
        }

    def reset(self):
        # A fresh session rejects delayed chunks from an earlier app process even
        # when firmware event IDs restart from one after a board reset.
        self.session = uuid.uuid4().hex
        self.last_id = 0
        self.current = None

    def begin(self, event_id, rate, samples, pre_samples, trigger_sample, rms, floor):
        event_id = int(event_id)
        if event_id <= self.last_id:
            raise ValueError("duplicate or stale event ID")
        if (int(rate), int(samples), int(pre_samples)) != (SAMPLE_RATE, EVENT_SAMPLES, PRE_SAMPLES):
            raise ValueError("unsupported audio geometry")
        if int(trigger_sample) < PRE_SAMPLES:
            raise ValueError("insufficient pre-event history")
        if not all(math.isfinite(float(v)) and float(v) >= 0 for v in (rms, floor)):
            raise ValueError("invalid trigger metrics")
        self.last_id = event_id
        timestamp = self.timestamp_factory()
        timestamp["trigger_sample"] = int(trigger_sample)
        self.current = {
            "event_id": event_id, "session": self.session,
            "sample_rate": SAMPLE_RATE, "samples": EVENT_SAMPLES,
            "channels": 1, "pre_samples": PRE_SAMPLES,
            "trigger_sample": int(trigger_sample),
            "trigger_rms": float(rms), "noise_rms": float(floor),
            "received_at": timestamp.get("utc", datetime.now(timezone.utc).isoformat()),
            "timestamp": timestamp,
            "started": self.clock(), "chunks": {},
        }

    def _active(self, event_id):
        if self.current is None or int(event_id) != self.current["event_id"]:
            raise ValueError("no matching event")
        if self.clock() - self.current["started"] > 60:
            self.current = None
            raise ValueError("event receive timeout")
        return self.current

    def chunk(self, event_id, index, encoded):
        event = self._active(event_id)
        index = int(index)
        if not 0 <= index < EVENT_SAMPLES // CHUNK_SAMPLES:
            raise ValueError("chunk index out of range")
        data = decode_chunk(encoded)
        previous = event["chunks"].get(index)
        if previous is not None and previous != data:
            self.current = None
            raise ValueError("conflicting duplicate chunk")
        event["chunks"][index] = data

    def end(self, event_id, chunk_count, crc_hex):
        event = self._active(event_id)
        self.current = None
        expected = EVENT_SAMPLES // CHUNK_SAMPLES
        if int(chunk_count) != expected or len(event["chunks"]) != expected:
            raise ValueError("incomplete event; missing audio is never replaced by silence")
        pcm = b"".join(event["chunks"][i] for i in range(expected))
        crc = zlib.crc32(pcm)
        if crc != int(str(crc_hex), 16):
            raise ValueError("PCM checksum mismatch")
        metadata = {k: v for k, v in event.items() if k not in ("started", "chunks")}
        metadata.update({"protocol": 1, "pcm_format": "s16le", "crc32": f"{crc:08x}",
                         "transfer_seconds": self.clock() - event["started"]})
        return pcm, metadata
