from pathlib import Path
import struct
import sys
import unittest
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_audio_test" / "python"))
from event_receiver import EventReceiver, decode_chunk

VECTOR = [0, 1, -1, 0x1234, -32768, 32767]
SAMPLES = (VECTOR * 43)[:256]
HEX = struct.pack(">256h", *SAMPLES).hex()
PCM = struct.pack("<256h", *SAMPLES)


class ReceiverTests(unittest.TestCase):
    def setUp(self):
        self.clock = 0.0
        self.receiver = EventReceiver(clock=lambda: self.clock)
        self.receiver.begin(1, 16000, 32768, 8192, 90000, 200, 20)

    def fill(self):
        for index in reversed(range(128)):
            self.receiver.chunk(1, index, HEX)

    def test_numeric_hex_to_wav_bytes(self):
        self.assertEqual(decode_chunk(HEX), PCM)
        self.assertEqual(decode_chunk(HEX)[6:8], b"\x34\x12")

    def test_complete_out_of_order_with_identical_duplicate(self):
        self.fill()
        self.receiver.chunk(1, 0, HEX)
        crc = zlib.crc32(PCM * 128)
        pcm, metadata = self.receiver.end(1, 128, f"{crc:08x}")
        self.assertEqual(pcm, PCM * 128)
        self.assertEqual(metadata["samples"], 32768)
        self.assertEqual(metadata["crc32"], f"{crc:08x}")

    def test_missing_chunk_rejected(self):
        self.receiver.chunk(1, 0, HEX)
        with self.assertRaisesRegex(ValueError, "incomplete"):
            self.receiver.end(1, 128, "0")

    def test_checksum_rejected(self):
        self.fill()
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.receiver.end(1, 128, "0")

    def test_conflicting_duplicate_aborts_event(self):
        self.receiver.chunk(1, 0, HEX)
        with self.assertRaisesRegex(ValueError, "conflicting"):
            self.receiver.chunk(1, 0, "0000" * 256)
        self.assertIsNone(self.receiver.current)

    def test_timeout(self):
        self.clock = 61
        with self.assertRaisesRegex(ValueError, "timeout"):
            self.receiver.chunk(1, 0, HEX)

    def test_invalid_length_index_and_id(self):
        for args in [(1, 128, HEX), (2, 0, HEX), (1, 0, "0000"), (1, 0, "z" * 1024)]:
            with self.assertRaises(ValueError):
                self.receiver.chunk(*args)

    def test_replay_rejected_and_reboot_changes_session(self):
        with self.assertRaisesRegex(ValueError, "stale"):
            self.receiver.begin(1, 16000, 32768, 8192, 90000, 200, 20)
        old_session = self.receiver.session
        self.receiver.reset()
        self.receiver.begin(1, 16000, 32768, 8192, 90000, 200, 20)
        self.assertNotEqual(old_session, self.receiver.session)

    def test_unsupported_geometry(self):
        with self.assertRaisesRegex(ValueError, "geometry"):
            self.receiver.begin(2, 48000, 32768, 8192, 90000, 200, 20)


if __name__ == "__main__":
    unittest.main()
