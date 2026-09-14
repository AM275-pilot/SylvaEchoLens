import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "estimate-autonomy.py"
SPEC = importlib.util.spec_from_file_location("estimate_autonomy", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class PowerBudgetTests(unittest.TestCase):
    def test_autonomy_uses_measured_power_and_activity(self):
        result = MODULE.estimate(
            battery_wh=20.0,
            usable_fraction=0.8,
            baseline_watts=1.0,
            inference_watts=2.0,
            inference_seconds=3.0,
            events_per_day=100,
            write_watts=1.5,
            write_seconds=1.0,
        )
        self.assertAlmostEqual(result["daily_wh"], 24.2083333333)
        self.assertAlmostEqual(result["autonomy_days"], 16.0 / result["daily_wh"])

    def test_invalid_measurement_is_rejected(self):
        with self.assertRaises(ValueError):
            MODULE.estimate(20, 1.2, 1, 2, 3, 100, 1.5, 1)


if __name__ == "__main__":
    unittest.main()
