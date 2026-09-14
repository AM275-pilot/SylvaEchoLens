"""Bounded offline persistence, reboot recovery, and timestamp evidence."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import struct
import tempfile
import time
import uuid
import wave

from event_receiver import SAMPLE_RATE


STATE_NAME = ".sylva-state.json"
WAV_HEADER_BYTES = 44


def _utc(epoch):
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat()


def _integer_environment(name, default):
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer number of bytes") from exc
    if value < 0:
        raise ValueError(f"{name} must not be negative")
    return value


def _pending_path(path):
    path = Path(path)
    name = f"{path.name}.tmp" if path.name.startswith(".") else f".{path.name}.tmp"
    return path.with_name(name)


def _atomic_json(path, value):
    # fsync the complete temporary record before the atomic rename so recovery
    # never has to treat a partially encoded JSON file as authoritative.
    path = Path(path)
    temporary = _pending_path(path)
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(value, stream, indent=2)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


@dataclass(frozen=True)
class StoragePolicy:
    """Space reserved for owned audio, observation records, and the OS."""

    audio_budget_bytes: int = 512 * 1024 * 1024
    record_reserve_bytes: int = 16 * 1024 * 1024
    system_reserve_bytes: int = 128 * 1024 * 1024
    retention: str = "delete_oldest"

    def __post_init__(self):
        for name in ("audio_budget_bytes", "record_reserve_bytes", "system_reserve_bytes"):
            if getattr(self, name) < 0:
                raise ValueError(f"{name} must not be negative")
        if self.retention not in ("delete_oldest", "recognition_only"):
            raise ValueError("SYLVA_RETENTION must be delete_oldest or recognition_only")

    @classmethod
    def from_environment(cls):
        return cls(
            audio_budget_bytes=_integer_environment(
                "SYLVA_AUDIO_BUDGET_BYTES", cls.audio_budget_bytes
            ),
            record_reserve_bytes=_integer_environment(
                "SYLVA_RECORD_RESERVE_BYTES", cls.record_reserve_bytes
            ),
            system_reserve_bytes=_integer_environment(
                "SYLVA_SYSTEM_RESERVE_BYTES", cls.system_reserve_bytes
            ),
            retention=os.getenv("SYLVA_RETENTION", cls.retention).strip().lower(),
        )


class TimestampAuthority:
    """Describe clock evidence without assuming that an offline wall clock is true."""

    VALID_QUALITIES = {"synchronized", "rtc", "unverified"}

    def __init__(
        self,
        wall_clock=time.time,
        monotonic_clock=time.monotonic,
        boot_id=None,
        source="system_clock",
        quality="unverified",
        uncertainty_seconds=None,
        last_utc_epoch=None,
    ):
        if quality not in self.VALID_QUALITIES:
            raise ValueError("SYLVA_TIME_QUALITY must be synchronized, rtc, or unverified")
        if uncertainty_seconds is not None:
            uncertainty_seconds = float(uncertainty_seconds)
            if not math.isfinite(uncertainty_seconds) or uncertainty_seconds < 0:
                raise ValueError("SYLVA_TIME_UNCERTAINTY_SECONDS must be nonnegative")
        self.wall_clock = wall_clock
        self.monotonic_clock = monotonic_clock
        self.boot_id = boot_id or self._system_boot_id()
        self.source = source
        self.quality = quality
        self.uncertainty_seconds = uncertainty_seconds
        self.last_utc_epoch = last_utc_epoch

    @staticmethod
    def _system_boot_id():
        try:
            value = Path("/proc/sys/kernel/random/boot_id").read_text(encoding="ascii").strip()
            return value or uuid.uuid4().hex
        except OSError:
            return uuid.uuid4().hex

    @classmethod
    def from_environment(cls, last_utc_epoch=None):
        uncertainty = os.getenv("SYLVA_TIME_UNCERTAINTY_SECONDS")
        return cls(
            source=os.getenv("SYLVA_TIME_SOURCE", "system_clock").strip() or "system_clock",
            quality=os.getenv("SYLVA_TIME_QUALITY", "unverified").strip().lower(),
            uncertainty_seconds=None if uncertainty in (None, "") else uncertainty,
            last_utc_epoch=last_utc_epoch,
        )

    def observe(self):
        epoch = float(self.wall_clock())
        quality = self.quality
        uncertainty = self.uncertainty_seconds
        if self.last_utc_epoch is not None and epoch < self.last_utc_epoch:
            # Preserve the observed value, but never present a regressed wall
            # clock as trustworthy evidence after a disconnected reboot.
            quality = "regressed"
            uncertainty = None
        self.last_utc_epoch = max(epoch, self.last_utc_epoch or epoch)
        return {
            "utc": _utc(epoch),
            "quality": quality,
            "source": self.source,
            "uncertainty_seconds": uncertainty,
            "boot_id": self.boot_id,
            "monotonic_seconds": float(self.monotonic_clock()),
        }


class ObservationStore:
    """Persist observations while maintaining explicit audio-retention provenance."""

    def __init__(self, directory, policy=None, temp_directory=None, disk_usage=shutil.disk_usage):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.policy = policy or StoragePolicy.from_environment()
        self.temp_directory = Path(temp_directory or os.getenv("SYLVA_TEMP_DIR", "/tmp/sylva-audio"))
        self.disk_usage = disk_usage
        self.state_path = self.directory / STATE_NAME
        self._recover_pending_state()
        self.state = self._load_state()
        self.recovery_report = self.recover()
        self._clock = TimestampAuthority.from_environment(self.state.get("last_utc_epoch"))
        self.state["boot_count"] = int(self.state.get("boot_count", 0)) + 1
        self.state["last_boot_id"] = self._clock.boot_id
        self.state["last_recovery"] = self.recovery_report
        self._save_state()

    def _recover_pending_state(self):
        pending = _pending_path(self.state_path)
        if not pending.exists():
            return
        try:
            candidate = json.loads(pending.read_text(encoding="utf-8"))
            if not isinstance(candidate, dict):
                raise ValueError("state must be an object")
            pending.replace(self.state_path)
        except (OSError, ValueError):
            pending.unlink(missing_ok=True)

    def _load_state(self):
        try:
            state = json.loads(self.state_path.read_text(encoding="utf-8"))
            return state if isinstance(state, dict) else {}
        except (OSError, ValueError):
            return {"schema": 1, "device_instance": uuid.uuid4().hex, "boot_count": 0}

    def _save_state(self):
        _atomic_json(self.state_path, self.state)

    def clock(self):
        return self._clock

    def _free(self):
        return self.disk_usage(self.directory).free

    def _audio_usage(self):
        return sum(path.stat().st_size for path in self.directory.glob("event-*.wav"))

    def _load_record(self, path):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            return record if isinstance(record, dict) else None
        except (OSError, ValueError):
            return None

    def _retention_candidates(self):
        # Only this application's indexed, valid, unprotected audio is eligible.
        # Unknown files and observation JSON are deliberately never deleted.
        candidates = []
        for wav_path in self.directory.glob("event-*.wav"):
            record_path = wav_path.with_suffix(".json")
            record = self._load_record(record_path)
            if record is None:
                continue
            audio = record.get("audio", {})
            if audio.get("protected", False):
                continue
            if audio.get("status", "retained") not in ("retained", "retained_recovered"):
                continue
            sequence = record.get("storage", {}).get("sequence")
            order = (1, int(sequence)) if sequence is not None else (0, wav_path.stat().st_mtime)
            candidates.append((order, wav_path, record_path, record))
        return sorted(candidates, key=lambda item: item[0])

    def _audio_allowed(self, required_bytes):
        within_budget = self._audio_usage() + required_bytes <= self.policy.audio_budget_bytes
        reserved = self.policy.system_reserve_bytes + self.policy.record_reserve_bytes
        return within_budget and self._free() - required_bytes >= reserved

    def _space_reason(self, required_bytes):
        if self._audio_usage() + required_bytes > self.policy.audio_budget_bytes:
            return "audio_budget_exhausted"
        return "filesystem_reserve_reached"

    def _remove_audio(self, wav_path, record_path, record, reason):
        audio = dict(record.get("audio", {}))
        audio.update({
            "status": "removal_pending",
            "reason": reason,
            "protected": False,
            "bytes": audio.get("bytes", wav_path.stat().st_size),
            "sha256": audio.get("sha256", record.get("sha256")),
        })
        record["audio"] = audio
        # The sidecar is a small retention journal: a reboot between these writes
        # completes the pending removal instead of losing why audio disappeared.
        _atomic_json(record_path, record)
        wav_path.unlink()
        audio["status"] = "removed_by_retention"
        audio["removed_at"] = datetime.now(timezone.utc).isoformat()
        _atomic_json(record_path, record)
        counters = self.state.setdefault("counters", {})
        counters["audio_removed"] = int(counters.get("audio_removed", 0)) + 1

    def _make_audio_room(self, required_bytes):
        if self._audio_allowed(required_bytes):
            return True, None
        reason = self._space_reason(required_bytes)
        if self.policy.retention != "delete_oldest":
            return False, reason
        for _, wav_path, record_path, record in self._retention_candidates():
            self._remove_audio(wav_path, record_path, record, reason)
            if self._audio_allowed(required_bytes):
                return True, None
        return False, reason

    @staticmethod
    def _write_wav(path, pcm):
        with wave.open(str(path), "wb") as wav:
            wav.setnchannels(1)
            wav.setsampwidth(2)
            wav.setframerate(SAMPLE_RATE)
            wav.writeframes(pcm)

    @staticmethod
    def _wav_is_valid(path, expected_samples=None):
        try:
            with wave.open(str(path), "rb") as wav:
                frames = wav.getnframes()
                return (
                    wav.getnchannels() == 1
                    and wav.getsampwidth() == 2
                    and wav.getframerate() == SAMPLE_RATE
                    and frames > 0
                    and (expected_samples is None or frames == int(expected_samples))
                )
        except (OSError, EOFError, wave.Error, ValueError):
            return False

    @staticmethod
    def _statistics(pcm):
        values = struct.unpack(f"<{len(pcm) // 2}h", pcm)
        mean = sum(values) / len(values)
        return {
            "duration_seconds": len(values) / SAMPLE_RATE,
            "mean": mean,
            "rms": math.sqrt(sum((value - mean) ** 2 for value in values) / len(values)),
            "peak": max(abs(value) for value in values),
            "clipped_samples": sum(value in (-32768, 32767) for value in values),
        }

    def _classify(self, path, classify, metadata):
        metadata["classification"] = None
        if classify is None:
            return
        started = time.monotonic()
        try:
            metadata["classification"] = classify(path)
        except Exception as exc:
            metadata["classification_error"] = {
                "type": type(exc).__name__, "message": str(exc),
            }
        finally:
            metadata["processing"]["inference_seconds"] = time.monotonic() - started

    def _temporary_inference(self, pcm, classify, metadata, reason):
        # BirdNET requires a real WAV path. Recognition-only mode therefore uses
        # an ephemeral file and retains only the durable observation record.
        self.temp_directory.mkdir(parents=True, exist_ok=True)
        handle, name = tempfile.mkstemp(prefix="sylva-", suffix=".wav", dir=self.temp_directory)
        os.close(handle)
        path = Path(name)
        try:
            self._write_wav(path, pcm)
            metadata["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
            metadata["audio"] = {
                "status": "never_retained",
                "reason": reason,
                "bytes": path.stat().st_size,
                "sha256": metadata["sha256"],
                "protected": False,
            }
            self._classify(path, classify, metadata)
        finally:
            path.unlink(missing_ok=True)

    def persist(self, event, classify=None):
        started = time.monotonic()
        pcm, source_metadata = event
        metadata = dict(source_metadata)
        metadata.update(self._statistics(pcm))
        metadata["pre_seconds"] = metadata["pre_samples"] / SAMPLE_RATE
        metadata["processing"] = {"inference_seconds": 0.0}
        metadata["storage"] = {
            "sequence": int(self.state.get("next_sequence", 1)),
            "audio_budget_bytes": self.policy.audio_budget_bytes,
            "record_reserve_bytes": self.policy.record_reserve_bytes,
            "system_reserve_bytes": self.policy.system_reserve_bytes,
            "retention": self.policy.retention,
        }
        name = f"event-{metadata['session']}-{metadata['event_id']:06d}"
        path = self.directory / f"{name}.wav"
        required = len(pcm) + WAV_HEADER_BYTES
        retain, reason = self._make_audio_room(required)

        if retain:
            temporary = self.directory / f".{name}.wav.tmp"
            try:
                self._write_wav(temporary, pcm)
                temporary.replace(path)
                metadata["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
                metadata["audio"] = {
                    "status": "retained",
                    "reason": None,
                    "bytes": path.stat().st_size,
                    "sha256": metadata["sha256"],
                    "protected": False,
                }
                self._classify(path, classify, metadata)
            except OSError as exc:
                temporary.unlink(missing_ok=True)
                path.unlink(missing_ok=True)
                reason = f"audio_write_failed:{type(exc).__name__}"
                self._temporary_inference(pcm, classify, metadata, reason)
                path = None
        else:
            self._temporary_inference(pcm, classify, metadata, reason)
            path = None

        metadata["processing"]["total_seconds"] = time.monotonic() - started
        record_path = self.directory / f"{name}.json"
        encoded_size = len(json.dumps(metadata).encode("utf-8")) + 1024
        # Observation metadata has priority over audio, but never consumes the
        # system reserve when even the compact record cannot be written safely.
        if self._free() - encoded_size < self.policy.system_reserve_bytes:
            if path is not None:
                path.unlink(missing_ok=True)
            raise OSError("system reserve reached; observation record cannot be persisted safely")
        _atomic_json(record_path, metadata)
        self.state["next_sequence"] = metadata["storage"]["sequence"] + 1
        self.state["last_utc_epoch"] = max(
            float(self.state.get("last_utc_epoch", 0)),
            float(self._clock.last_utc_epoch or 0),
        )
        counters = self.state.setdefault("counters", {})
        key = "audio_retained" if path is not None else "recognition_only"
        counters[key] = int(counters.get(key, 0)) + 1
        self._save_state()
        return path, metadata

    def recover(self):
        # Recovery is conservative: it completes journaled operations and indexes
        # unknown audio; it does not silently discard evidence it cannot explain.
        report = {
            "json_completed": 0,
            "temporary_audio_removed": 0,
            "retention_completed": 0,
            "missing_audio_marked": 0,
            "corrupt_audio_marked": 0,
            "orphan_audio_indexed": 0,
        }
        for temporary in self.directory.glob(".*.wav.tmp"):
            temporary.unlink(missing_ok=True)
            report["temporary_audio_removed"] += 1
        for temporary in self.directory.glob(".event-*.json.tmp"):
            final = temporary.with_name(temporary.name[1:-4])
            if not final.exists():
                try:
                    json.loads(temporary.read_text(encoding="utf-8"))
                    temporary.replace(final)
                    report["json_completed"] += 1
                except (OSError, ValueError):
                    temporary.unlink(missing_ok=True)
            else:
                temporary.unlink(missing_ok=True)

        for record_path in self.directory.glob("event-*.json"):
            record = self._load_record(record_path)
            if record is None:
                continue
            wav_path = record_path.with_suffix(".wav")
            audio = dict(record.get("audio", {}))
            status = audio.get("status", "retained")
            if status == "removal_pending":
                wav_path.unlink(missing_ok=True)
                audio["status"] = "removed_by_retention"
                audio["removed_at"] = datetime.now(timezone.utc).isoformat()
                record["audio"] = audio
                _atomic_json(record_path, record)
                report["retention_completed"] += 1
            elif status in ("retained", "retained_recovered") and not wav_path.exists():
                audio.update({"status": "missing_after_reboot", "reason": "audio_file_missing"})
                record["audio"] = audio
                _atomic_json(record_path, record)
                report["missing_audio_marked"] += 1
            elif status in ("retained", "retained_recovered"):
                expected_hash = audio.get("sha256", record.get("sha256"))
                actual_hash = hashlib.sha256(wav_path.read_bytes()).hexdigest()
                if not self._wav_is_valid(wav_path, record.get("samples")):
                    audio.update({
                        "status": "corrupt_after_reboot",
                        "reason": "invalid_audio_file",
                        "bytes": wav_path.stat().st_size,
                        "sha256": actual_hash,
                    })
                elif expected_hash and expected_hash != actual_hash:
                    audio.update({
                        "status": "corrupt_after_reboot",
                        "reason": "sha256_mismatch",
                        "bytes": wav_path.stat().st_size,
                        "sha256": actual_hash,
                    })
                else:
                    continue
                record["audio"] = audio
                _atomic_json(record_path, record)
                report["corrupt_audio_marked"] += 1

        for wav_path in self.directory.glob("event-*.wav"):
            record_path = wav_path.with_suffix(".json")
            if record_path.exists():
                continue
            valid = self._wav_is_valid(wav_path)
            digest = hashlib.sha256(wav_path.read_bytes()).hexdigest()
            record = {
                "recovered_after_reboot": True,
                "timestamp": {
                    "utc": _utc(wav_path.stat().st_mtime),
                    "quality": "unverified",
                    "source": "filesystem_mtime",
                    "uncertainty_seconds": None,
                    "boot_id": None,
                    "monotonic_seconds": None,
                },
                "sha256": digest,
                "classification": None,
                "audio": {
                    "status": "retained_recovered" if valid else "corrupt_recovered",
                    "reason": "orphan_after_interrupted_write",
                    "bytes": wav_path.stat().st_size,
                    "sha256": digest,
                    "protected": False,
                },
            }
            _atomic_json(record_path, record)
            report["orphan_audio_indexed"] += 1
        return report
