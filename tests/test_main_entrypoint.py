from pathlib import Path
import runpy
import sys
from types import ModuleType
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
APP_PYTHON = ROOT / "app_audio_test" / "python"
MAIN = APP_PYTHON / "main.py"


class MainEntrypointTests(unittest.TestCase):
    def test_multiprocessing_child_import_has_no_app_side_effects(self):
        """BirdNET spawn workers must not initialize another App Lab runtime."""
        calls = []

        class MustNotRun:
            def __init__(self, *args, **kwargs):
                calls.append((args, kwargs))
                raise AssertionError("App runtime initialized in a spawn worker")

        arduino = ModuleType("arduino")
        app_utils = ModuleType("arduino.app_utils")
        app_utils.App = MustNotRun
        app_utils.Bridge = MustNotRun
        app_utils.Logger = MustNotRun
        arduino.app_utils = app_utils

        with patch.dict(
            sys.modules,
            {"arduino": arduino, "arduino.app_utils": app_utils},
        ), patch.object(sys, "path", [str(APP_PYTHON), *sys.path]):
            namespace = runpy.run_path(str(MAIN), run_name="__mp_main__")

        self.assertIn("run_app", namespace)
        self.assertEqual(calls, [])


if __name__ == "__main__":
    unittest.main()
