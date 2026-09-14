# Field test record — Assiolo acoustic replay — September 14, 2026

## Observation statement

The operator announced and played an assiolo recording near the running
`SylvaEchoLens` prototype. Two complete device events were classified locally as
`Otus scops_Eurasian Scops-Owl` with scores 0.996271 and 0.997038. Both exceeded the
configured 0.25 acceptance threshold, retained their WAV evidence and passed the
independent event audit.

This is a precise observation of the device response to an announced acoustic
replay. It is **not** a spontaneous wildlife observation, proof that a living owl was
present or a complete accuracy evaluation. Source title/URL, license, loudspeaker
distance and playback-volume setting still need operator annotation.

## Test configuration

| Item | Recorded value |
|---|---|
| Application identity | `user:sylvaecholens` / `SylvaEchoLens` |
| Board application path | `/home/arduino/ArduinoApps/sylvaecholens` |
| Hardware | Arduino UNO Q with one INMP441 microphone |
| Capture geometry | Mono PCM16, configured 16 kHz |
| Event geometry | 32,768 samples / 2.048 s |
| Pre-event history | 8,192 samples / 0.512 s |
| Model | `BirdNET_GLOBAL_6K_V2.4`, FP32 through LiteRT |
| Decision threshold | 0.25 |
| Geographic filter | Disabled / null |
| Linux suspend | Disabled |
| Clock evidence | `system_clock`, quality `unverified` |
| Session | `d826aae0c4af492da71b26900f8cad56` |

## Audited results

| Event | Receive time UTC | Trigger RMS | Overall RMS | Peak | Transfer | Inference | BirdNET result | Score | CRC32 | WAV SHA-256 |
|---:|---|---:|---:|---:|---:|---:|---|---:|---|---|
| 17 | 2026-09-14 05:04:36.229 | 115.404 | 34.570 | 214 | 13.269 s | 7.752 s | `Otus scops_Eurasian Scops-Owl` | 0.996271 | `4da4bc1e` | `574b4fe64536e3cf0f1379082b2516f9fad339da2b28afc219a0a2cd20fda73f` |
| 18 | 2026-09-14 05:04:53.144 | 218.242 | 51.322 | 460 | 13.260 s | 8.297 s | `Otus scops_Eurasian Scops-Owl` | 0.997038 | `ec77cefa` | `aa2a2628a96658b0e640c613a0c3201bcf0a7f283447adb32c6cec4ab995cf08` |

For both events:

- `scripts/audit-events.py` returned `verified: true`;
- WAV geometry, CRC32 and SHA-256 matched the JSON evidence;
- the recomputed confirmation-frame RMS matched the MCU value;
- clipped-sample count was zero;
- audio status was `retained`;
- resampling from 16 kHz to 48 kHz and zero-padding to the three-second BirdNET
  window were explicitly recorded;
- no multiprocessing re-import, application restart or atomic-file collision
  occurred after the entrypoint correction.

The second-ranked candidate was `Otus cyprius_Cyprus Scops-Owl`, at 0.094463 for
event 17 and 0.021398 for event 18. The complete top-five lists remain in the JSON
records.

## Evidence location

Local ignored evidence:
`.codex-build/evidence/20260914-assiolo-replay/`.

Files:

- `event-d826aae0c4af492da71b26900f8cad56-000017.wav`
- `event-d826aae0c4af492da71b26900f8cad56-000017.json`
- `event-d826aae0c4af492da71b26900f8cad56-000018.wav`
- `event-d826aae0c4af492da71b26900f8cad56-000018.json`
- generated SVG waveform audit cards in the same ignored directory.

The WAV/JSON pairs also remain in the board event store. Local copies preserve this
test even if the board retention policy later removes an unprotected WAV.

## Interpretation and remaining controls

This run establishes a strong positive demonstration for the announced assiolo
replay and verifies the repaired end-to-end runtime under real BirdNET inference.
It does not yet measure precision, recall or the suitability of the 0.25 threshold.

To promote the result into a reproducible labeled evaluation set, add:

1. source recording title, URL and license;
2. loudspeaker model, microphone distance and playback-volume setting;
3. a quiet control and human-speech/background controls in the same setup;
4. repeated playback at three documented levels or distances;
5. every miss, false trigger and `unknown`, not only accepted results;
6. an explicit statement that the files are replays when used in the contest Story
   or demonstration video.
