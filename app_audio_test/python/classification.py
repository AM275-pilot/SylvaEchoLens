"""Offline BirdNET v2.4 inference for finalized acoustic events."""

import math
import os
from pathlib import Path

MODEL_NAME = "BirdNET_GLOBAL_6K_V2.4"
MODEL_VERSION = "2.4"
MODEL_SAMPLE_RATE = 48000
MODEL_WINDOW_SECONDS = 3.0


def _threshold_from_environment():
    threshold = float(os.getenv("SYLVA_CLASSIFIER_THRESHOLD", "0.25"))
    if not math.isfinite(threshold) or not 0.0 <= threshold <= 1.0:
        raise ValueError("SYLVA_CLASSIFIER_THRESHOLD must be inside 0..1")
    return threshold


def _candidate(record):
    return {
        "label": str(record["species_name"]),
        "score": float(record["confidence"]),
        "start_seconds": float(record["start_time"]),
        "end_seconds": float(record["end_time"]),
    }


def normalize_birdnet_result(result, threshold, source_sample_rate, source_duration):
    """Convert BirdNET records into stable, JSON-safe evidence metadata."""
    records = [_candidate(record) for record in result.to_structured_array()]
    records.sort(key=lambda item: item["score"], reverse=True)
    best = records[0] if records else None
    accepted = best is not None and best["score"] >= threshold
    return {
        "label": best["label"] if accepted else "unknown",
        "score": best["score"] if best else 0.0,
        "accepted": accepted,
        "candidates": records,
        "model": MODEL_NAME,
        "version": MODEL_VERSION,
        "backend": "birdnet_litert",
        "precision": "fp32",
        "threshold": threshold,
        "geographic_filter": None,
        "source_sample_rate": int(source_sample_rate),
        "source_duration_seconds": float(source_duration),
        "model_sample_rate": MODEL_SAMPLE_RATE,
        "model_window_seconds": MODEL_WINDOW_SECONDS,
        "resampled": int(source_sample_rate) != MODEL_SAMPLE_RATE,
        "zero_padded": float(source_duration) < MODEL_WINDOW_SECONDS,
    }


class BirdNetV24Classifier:
    """Load the official BirdNET v2.4 FP32 model once and run it locally."""

    def __init__(self, threshold=None, birdnet_module=None):
        # Persist downloaded weights in the bind-mounted app, not the container.
        os.environ.setdefault("BIRDNET_APP_DATA", "/app/.cache/birdnet")
        if birdnet_module is None:
            import birdnet as birdnet_module

        self.threshold = _threshold_from_environment() if threshold is None else float(threshold)
        if not math.isfinite(self.threshold) or not 0.0 <= self.threshold <= 1.0:
            raise ValueError("classifier threshold must be inside 0..1")
        self.model = birdnet_module.load(
            "acoustic", "2.4", "tf", precision="fp32", lang="en_us", library="litert"
        )

    def classify(self, wav_path):
        import wave

        wav_path = Path(wav_path)
        with wave.open(str(wav_path), "rb") as wav:
            source_rate = wav.getframerate()
            source_duration = wav.getnframes() / source_rate
        result = self.model.predict(
            wav_path, top_k=5, n_producers=1, n_workers=1, batch_size=1,
            prefetch_ratio=0, default_confidence_threshold=0.0, show_stats=None,
        )
        return normalize_birdnet_result(
            result, self.threshold, source_rate, source_duration
        )


def classifier_from_environment():
    """Create the release classifier; explicit opt-out supports recovery."""
    backend = os.getenv("SYLVA_CLASSIFIER_BACKEND", "birdnet").strip().lower()
    if backend in ("", "disabled", "none"):
        return None
    if backend != "birdnet":
        raise ValueError(f"unsupported classifier backend: {backend}")
    return BirdNetV24Classifier()
