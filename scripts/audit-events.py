"""Verify local event evidence and draw a dependency-free SVG waveform card."""

import argparse
import hashlib
import html
import json
import math
from pathlib import Path
import struct
import wave
import zlib


def rms(values):
    mean = sum(values) / len(values)
    return math.sqrt(sum((value - mean) ** 2 for value in values) / len(values))


def audit(path):
    metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8"))
    with wave.open(str(path)) as wav:
        geometry = (wav.getnchannels(), wav.getsampwidth(), wav.getframerate(), wav.getnframes())
        if geometry != (1, 2, 16000, 32768):
            raise ValueError(f"unsupported WAV geometry: {geometry}")
        pcm = wav.readframes(wav.getnframes())
    if hashlib.sha256(path.read_bytes()).hexdigest() != metadata["sha256"]:
        raise ValueError("WAV SHA-256 mismatch")
    if f"{zlib.crc32(pcm):08x}" != metadata["crc32"]:
        raise ValueError("PCM CRC mismatch")
    values = struct.unpack("<32768h", pcm)
    boundary = metadata["pre_samples"]
    if boundary != 8192:
        raise ValueError("unexpected pre-event boundary")
    trigger_rms = rms(values[boundary:boundary + 256])
    if not math.isclose(trigger_rms, metadata["trigger_rms"], rel_tol=1e-5, abs_tol=1e-3):
        raise ValueError("WAV confirmation-frame RMS differs from MCU measurement")
    if not math.isclose(rms(values), metadata["rms"], rel_tol=1e-8):
        raise ValueError("whole-event RMS mismatch")

    # Min/max envelopes preserve short transients at this display resolution.
    width, left, center, height = 768, 76, 218, 100
    scale = max(1, max(abs(value) for value in values))
    bars = []
    for column in range(width):
        segment = values[column * len(values) // width:(column + 1) * len(values) // width]
        x = left + column
        bars.append(f'<path d="M{x},{center - max(segment) / scale * height:.2f} '
                    f'V{center - min(segment) / scale * height:.2f}"/>')
    trigger_x = left + width * boundary / len(values)
    label = html.escape(f"Event {metadata['event_id']:06d} · {metadata['received_at']}")
    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="920" height="410" viewBox="0 0 920 410">
<rect width="920" height="410" rx="18" fill="#102823"/>
<g font-family="sans-serif" fill="#e9f4ee">
<text x="40" y="42" font-size="24">Sylva EchoLens / acoustic evidence</text>
<text x="40" y="72" font-size="14">{label}</text>
<rect x="76" y="106" width="192" height="224" fill="#25483e"/>
<path d="M76,218 H844" stroke="#56756b"/>
<g stroke="#7fdeb0" stroke-width="1">{''.join(bars)}</g>
<path d="M{trigger_x},104 V332" stroke="#ffc876" stroke-dasharray="5 4"/>
<text x="80" y="351" font-size="13">0 s / pre-event</text>
<text x="274" y="351" font-size="13">0.512 s / confirmation frame</text>
<text x="780" y="351" font-size="13">2.048 s</text>
<text x="40" y="380" font-size="13">Mono · 16 kHz · PCM16 · CRC + SHA verified · amplitude auto-scaled (peak {scale})</text>
</g></svg>'''
    path.with_suffix(".svg").write_text(svg, encoding="utf-8")
    return {"file": path.name, "verified": True, "trigger_rms_from_wav": trigger_rms,
            "transfer_seconds": metadata["transfer_seconds"], "clipped_samples": metadata["clipped_samples"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    args = parser.parse_args()
    paths = sorted(args.directory.glob("*.wav"))
    if not paths:
        parser.error("no WAV files found")
    for path in paths:
        print(json.dumps(audit(path)))
