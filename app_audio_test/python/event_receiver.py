"""Strict event assembly, independent of App Lab and suitable for host tests."""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import struct
import time
import uuid
import wave
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
    """One in-flight event, bounded to 64 KiB and a 60-second receive deadline."""

    def __init__(self, clock=time.monotonic):
        self.clock = clock
        self.reset()

    def reset(self):
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
        self.current = {
            "event_id": event_id, "session": self.session,
            "sample_rate": SAMPLE_RATE, "samples": EVENT_SAMPLES,
            "channels": 1, "pre_samples": PRE_SAMPLES,
            "trigger_sample": int(trigger_sample),
            "trigger_rms": float(rms), "noise_rms": float(floor),
            "received_at": datetime.now(timezone.utc).isoformat(),
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


def write_event(directory, event):
    """Write WAV atomically, then its provenance sidecar. Never erase old events."""
    pcm, source_metadata = event
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    metadata = dict(source_metadata)
    name = f"event-{metadata['session']}-{metadata['event_id']:06d}"
    path = directory / f"{name}.wav"
    temporary = directory / f".{name}.wav.tmp"
    with wave.open(str(temporary), "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(pcm)
    temporary.replace(path)
    values = struct.unpack(f"<{len(pcm) // 2}h", pcm)
    mean = sum(values) / len(values)
    metadata.update({
        "duration_seconds": len(values) / SAMPLE_RATE,
        "pre_seconds": metadata["pre_samples"] / SAMPLE_RATE,
        "mean": mean,
        "rms": math.sqrt(sum((value - mean) ** 2 for value in values) / len(values)),
        "peak": max(abs(value) for value in values),
        "clipped_samples": sum(value in (-32768, 32767) for value in values),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "classification": None,
    })
    sidecar_tmp = directory / f".{name}.json.tmp"
    sidecar_tmp.write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    sidecar_tmp.replace(directory / f"{name}.json")
    return path, metadata
