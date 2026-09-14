#!/usr/bin/env python3
"""Estimate autonomy from measured whole-board power; never invent measurements."""

import argparse
import json
import math


def estimate(
    battery_wh,
    usable_fraction,
    baseline_watts,
    inference_watts,
    inference_seconds,
    events_per_day,
    write_watts,
    write_seconds,
):
    values = (
        battery_wh, baseline_watts, inference_watts, inference_seconds,
        events_per_day, write_watts, write_seconds,
    )
    if any(not math.isfinite(value) or value < 0 for value in values):
        raise ValueError("power, duration and event values must be finite and nonnegative")
    if not math.isfinite(usable_fraction) or not 0 < usable_fraction <= 1:
        raise ValueError("power, duration and event values must be nonnegative; usable fraction is 0..1")
    daily_wh = baseline_watts * 24
    daily_wh += inference_watts * inference_seconds * events_per_day / 3600
    daily_wh += write_watts * write_seconds * events_per_day / 3600
    usable_wh = battery_wh * usable_fraction
    return {
        "battery_usable_wh": usable_wh,
        "daily_wh": daily_wh,
        "autonomy_days": usable_wh / daily_wh if daily_wh else None,
        "assumption": (
            "inference_watts and write_watts are incremental above the measured "
            "whole-board baseline"
        ),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--battery-wh", type=float, required=True)
    parser.add_argument("--usable-fraction", type=float, default=0.8)
    parser.add_argument("--baseline-watts", type=float, required=True)
    parser.add_argument("--inference-watts", type=float, required=True)
    parser.add_argument("--inference-seconds", type=float, required=True)
    parser.add_argument("--events-per-day", type=float, required=True)
    parser.add_argument("--write-watts", type=float, required=True)
    parser.add_argument("--write-seconds", type=float, required=True)
    args = parser.parse_args()
    print(json.dumps(estimate(**vars(args)), indent=2))


if __name__ == "__main__":
    main()
