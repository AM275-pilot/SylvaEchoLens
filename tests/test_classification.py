import os
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app_audio_test" / "python"))
from classification import (
    BirdNetV24Classifier,
    classifier_from_environment,
    normalize_birdnet_result,
)


class FakeResult:
    def __init__(self, records):
        self.records = records

    def to_structured_array(self):
        return [
            {
                "species_name": record[0], "confidence": record[1],
                "start_time": record[2], "end_time": record[3],
            }
            for record in self.records
        ]


class FakeModel:
    def predict(self, path, **kwargs):
        self.call = (path, kwargs)
        return FakeResult([
            ("Otus scops_Eurasian Scops-Owl", 0.81, 0.0, 2.048),
            ("Athene noctua_Little Owl", 0.19, 0.0, 2.048),
        ])


class FakeBirdnet:
    def __init__(self):
        self.model = FakeModel()

    def load(self, *args, **kwargs):
        self.load_call = (args, kwargs)
        return self.model


class ClassificationTests(unittest.TestCase):
    def test_explicit_disable_does_not_import_runtime(self):
        with patch.dict(os.environ, {"SYLVA_CLASSIFIER_BACKEND": "disabled"}, clear=True):
            self.assertIsNone(classifier_from_environment())

    def test_normalizes_top_candidates_and_input_contract(self):
        result = normalize_birdnet_result(
            FakeResult([
                ("low", 0.12, 0.0, 2.048),
                ("target", 0.82, 0.0, 2.048),
            ]), 0.25, 16000, 2.048,
        )
        self.assertEqual(result["label"], "target")
        self.assertAlmostEqual(result["score"], 0.82, places=5)
        self.assertTrue(result["accepted"])
        self.assertEqual(result["candidates"][0]["label"], "target")
        self.assertTrue(result["resampled"])
        self.assertTrue(result["zero_padded"])
        self.assertIsNone(result["geographic_filter"])

    def test_below_threshold_is_unknown_but_keeps_candidates(self):
        result = normalize_birdnet_result(
            FakeResult([("candidate", 0.2, 0.0, 2.0)]), 0.25, 48000, 3.0
        )
        self.assertEqual(result["label"], "unknown")
        self.assertFalse(result["accepted"])
        self.assertEqual(result["candidates"][0]["label"], "candidate")

    def test_loads_exact_release_model(self):
        fake = FakeBirdnet()
        classifier = BirdNetV24Classifier(threshold=0.25, birdnet_module=fake)
        self.assertEqual(fake.load_call, (
            ("acoustic", "2.4", "tf"),
            {"precision": "fp32", "lang": "en_us", "library": "litert"},
        ))
        self.assertIs(classifier.model, fake.model)

    def test_rejects_invalid_threshold(self):
        with self.assertRaisesRegex(ValueError, "inside"):
            BirdNetV24Classifier(threshold=1.1, birdnet_module=FakeBirdnet())


if __name__ == "__main__":
    unittest.main()
