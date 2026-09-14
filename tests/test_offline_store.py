import hashlib
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_audio_test" / "python"))
from event_receiver import EventReceiver
from offline_store import ObservationStore, StoragePolicy, TimestampAuthority


PCM = struct.pack("<32768h", *([120, -120] * 16384))


def complete_event(event_id=1, timestamp=None):
    metadata = {
        "event_id": event_id,
        "session": "test-session",
        "sample_rate": 16000,
        "samples": 32768,
        "channels": 1,
        "pre_samples": 8192,
        "trigger_sample": 90000,
        "trigger_rms": 120.0,
        "noise_rms": 20.0,
        "received_at": "2026-09-13T10:00:00+00:00",
        "timestamp": timestamp or {
            "utc": "2026-09-13T10:00:00+00:00",
            "quality": "unverified",
            "source": "system_clock",
            "uncertainty_seconds": None,
            "boot_id": "test-boot",
            "monotonic_seconds": 42.0,
            "trigger_sample": 90000,
        },
        "protocol": 1,
        "pcm_format": "s16le",
        "crc32": f"{zlib.crc32(PCM):08x}",
        "transfer_seconds": 1.0,
    }
    return PCM, metadata


class OfflineStoreTests(unittest.TestCase):
    def policy(self, **overrides):
        values = {
            "audio_budget_bytes": 1024 * 1024,
            "record_reserve_bytes": 0,
            "system_reserve_bytes": 0,
            "retention": "delete_oldest",
        }
        values.update(overrides)
        return StoragePolicy(**values)

    def test_audio_is_retained_with_explicit_provenance(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = ObservationStore(temporary, self.policy(), temp_directory=temporary)
            path, metadata = store.persist(complete_event(), classify=lambda _: {"label": "owl"})
            self.assertTrue(path.exists())
            self.assertEqual(metadata["audio"]["status"], "retained")
            self.assertEqual(metadata["audio"]["bytes"], path.stat().st_size)
            self.assertEqual(metadata["classification"]["label"], "owl")
            self.assertEqual(metadata, json.loads(path.with_suffix(".json").read_text()))

    def test_inference_failure_keeps_audio_and_records_the_error(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = ObservationStore(temporary, self.policy(), temp_directory=temporary)

            def fail(_):
                raise RuntimeError("model unavailable")

            path, metadata = store.persist(complete_event(), classify=fail)
            self.assertTrue(path.exists())
            self.assertIsNone(metadata["classification"])
            self.assertEqual(metadata["classification_error"]["type"], "RuntimeError")

    def test_quota_switches_to_temporary_recognition_only_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            seen = []
            store = ObservationStore(
                temporary,
                self.policy(audio_budget_bytes=0, retention="recognition_only"),
                temp_directory=temporary,
            )
            path, metadata = store.persist(
                complete_event(), classify=lambda wav: seen.append(Path(wav).exists()) or {"label": "owl"}
            )
            self.assertIsNone(path)
            self.assertEqual(seen, [True])
            self.assertEqual(metadata["audio"]["status"], "never_retained")
            self.assertEqual(metadata["audio"]["reason"], "audio_budget_exhausted")
            self.assertFalse(list(Path(temporary).glob("event-*.wav")))
            self.assertFalse(list(Path(temporary).glob(".*.wav.tmp")))
            self.assertEqual(len(list(Path(temporary).glob("event-*.json"))), 1)

    def test_record_and_system_reserves_keep_audio_out(self):
        with tempfile.TemporaryDirectory() as temporary:
            free = len(PCM) + 44 + 150
            store = ObservationStore(
                temporary,
                self.policy(record_reserve_bytes=100, system_reserve_bytes=100),
                temp_directory=temporary,
                disk_usage=lambda _: SimpleNamespace(free=free),
            )
            path, metadata = store.persist(complete_event())
            self.assertIsNone(path)
            self.assertEqual(metadata["audio"]["reason"], "filesystem_reserve_reached")

    def test_audio_write_failure_falls_back_to_temporary_inference(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = ObservationStore(temporary, self.policy(), temp_directory=temporary)
            write_wav = store._write_wav
            calls = 0

            def fail_once(path, pcm):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise OSError("simulated permanent write failure")
                write_wav(path, pcm)

            store._write_wav = fail_once
            path, metadata = store.persist(
                complete_event(), classify=lambda _: {"label": "owl"}
            )
            self.assertIsNone(path)
            self.assertEqual(metadata["classification"]["label"], "owl")
            self.assertEqual(metadata["audio"]["reason"], "audio_write_failed:OSError")

    def test_delete_oldest_retains_records_and_honors_protection(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = ObservationStore(
                temporary,
                self.policy(audio_budget_bytes=66000),
                temp_directory=temporary,
            )
            first_path, first = store.persist(complete_event(1))
            first["audio"]["protected"] = True
            first_path.with_suffix(".json").write_text(json.dumps(first), encoding="utf-8")
            second_path, second = store.persist(complete_event(2))
            self.assertTrue(first_path.exists())
            self.assertIsNone(second_path)
            self.assertEqual(second["audio"]["status"], "never_retained")

            first["audio"]["protected"] = False
            first_path.with_suffix(".json").write_text(json.dumps(first), encoding="utf-8")
            third_path, _ = store.persist(complete_event(3))
            self.assertTrue(third_path.exists())
            self.assertFalse(first_path.exists())
            evicted = json.loads(first_path.with_suffix(".json").read_text())
            self.assertEqual(evicted["audio"]["status"], "removed_by_retention")
            self.assertEqual(evicted["audio"]["reason"], "audio_budget_exhausted")

    def test_recovery_finishes_json_and_marks_missing_audio(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            final = root / "event-a-000001.json"
            pending = root / ".event-a-000001.json.tmp"
            pending.write_text(json.dumps({"audio": {"status": "retained"}}), encoding="utf-8")
            store = ObservationStore(root, self.policy(), temp_directory=root)
            self.assertTrue(final.exists())
            recovered = json.loads(final.read_text())
            self.assertEqual(recovered["audio"]["status"], "missing_after_reboot")
            self.assertGreaterEqual(store.recovery_report["json_completed"], 1)

    def test_recovery_promotes_pending_state_before_loading_it(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            pending = root / ".sylva-state.json.tmp"
            pending.write_text(json.dumps({
                "schema": 1, "device_instance": "kept", "boot_count": 7,
            }), encoding="utf-8")
            store = ObservationStore(root, self.policy(), temp_directory=root)
            self.assertEqual(store.state["device_instance"], "kept")
            self.assertEqual(store.state["boot_count"], 8)

    def test_orphaned_valid_and_corrupt_wavs_are_inventory_records(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            valid = root / "event-old-000001.wav"
            corrupt = root / "event-old-000002.wav"
            import wave
            with wave.open(str(valid), "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(16000)
                wav.writeframes(PCM)
            corrupt.write_bytes(b"")
            ObservationStore(root, self.policy(), temp_directory=root)
            valid_record = json.loads(valid.with_suffix(".json").read_text())
            corrupt_record = json.loads(corrupt.with_suffix(".json").read_text())
            self.assertEqual(valid_record["audio"]["status"], "retained_recovered")
            self.assertEqual(corrupt_record["audio"]["status"], "corrupt_recovered")

    def test_recovery_detects_corrupt_audio_with_existing_record(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            wav_path = root / "event-old-000003.wav"
            wav_path.write_bytes(b"")
            wav_path.with_suffix(".json").write_text(json.dumps({
                "samples": 32768,
                "sha256": hashlib.sha256(b"expected").hexdigest(),
                "audio": {"status": "retained", "protected": False},
            }), encoding="utf-8")
            store = ObservationStore(root, self.policy(), temp_directory=root)
            record = json.loads(wav_path.with_suffix(".json").read_text())
            self.assertEqual(record["audio"]["status"], "corrupt_after_reboot")
            self.assertEqual(store.recovery_report["corrupt_audio_marked"], 1)

    def test_timestamp_quality_is_explicit_and_regression_is_detected(self):
        values = iter([1000.0, 900.0])
        authority = TimestampAuthority(
            wall_clock=lambda: next(values), monotonic_clock=lambda: 12.5,
            boot_id="boot", source="rtc", quality="rtc", uncertainty_seconds=2.0,
            last_utc_epoch=950.0,
        )
        first = authority.observe()
        second = authority.observe()
        self.assertEqual(first["quality"], "rtc")
        self.assertEqual(second["quality"], "regressed")
        self.assertIsNone(second["uncertainty_seconds"])

    def test_receiver_attaches_timestamp_evidence(self):
        receiver = EventReceiver(
            clock=lambda: 1.0,
            timestamp_factory=lambda: {"quality": "unverified", "boot_id": "boot"},
        )
        receiver.begin(1, 16000, 32768, 8192, 90000, 200, 20)
        self.assertEqual(receiver.current["timestamp"]["quality"], "unverified")

    def test_policy_environment_is_validated(self):
        with patch.dict(os.environ, {"SYLVA_RETENTION": "erase_everything"}, clear=True):
            with self.assertRaisesRegex(ValueError, "SYLVA_RETENTION"):
                StoragePolicy.from_environment()


if __name__ == "__main__":
    unittest.main()
