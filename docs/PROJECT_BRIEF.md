# Project brief

Current scope reviewed on September 14, 2026. The concise implementation and
verification ledger is maintained in [current status](CURRENT_STATUS.md).

## Purpose

Sylva EchoLens aims to detect, classify and document wildlife vocalizations
without continuous human presence. Arduino UNO Q combines a real-time STM32
microcontroller with a Qualcomm Linux processor; App Lab integrates the
application, local model and observation storage. A wildlife observation interface
is planned but not yet implemented.

## Current implementation boundary

One INMP441 microphone supplies mono audio at a configured 16 kHz. The STM32
selects candidate acoustic events using lightweight energy measurements.
A Linux receiver writes verified audio and provenance, then runs the official
BirdNET v2.4 FP32 model locally. Board inference, a network-disconnected rerun and
two audited events from an announced assiolo replay have succeeded. BirdNET returned
`Otus scops` at 0.996 and 0.997. Complete replay provenance and negative controls are
still required before making a representative species-recognition claim.
See the exact [assiolo field-test record](2026-09-14-FIELD-TEST-ASSIOLO.md).

The variant being developed is the lightweight acoustic-only unit: no camera and
no servo mechanism. Very low power is its engineering objective, not yet a measured
result. A guarded suspend-to-idle prototype reached the Linux power state, but its
acoustic UART wake did not pass device acceptance. It is disabled and excluded from
the release; richer imaging/motion variants remain separate future extensions.

## Why local recognition is essential

The unit should remain useful through extended periods without Internet access.
Recognizing events on board means observations can be created and retained in the
field, rather than waiting for connectivity to interpret a backlog of recordings.
While persistent storage permits, keep the observations together with their audio.
When the audio budget runs out, continue prioritizing compact recognition records
so that acoustic evidence takes less space without immediately ending observation.

This storage behavior is implemented and host-tested: audio, record and system
reserves, protected FIFO WAV retention, recognition-only fallback, restart
reconciliation and explicit clock quality. These also passed an isolated UNO Q
smoke test. Audio loss still limits later verification, and records remain finite.
Physical power-cut, device endurance and power acceptance are specified in
[offline operation](OFFLINE_OPERATION.md).

## Observation record

Each current observation contains species label, model score and version, timestamp
evidence and source-audio retention status. Image and environmental context remain
optional future extensions.
Unknown or low-confidence results should stay explicitly unknown. A model score
is not automatically a calibrated probability.

## Longer-term concept

The broader platform concept includes a second synchronized microphone, direction
estimation, camera pan/tilt, environmental sensors, a local dashboard, export,
notifications and a multi-node view. These are desired extensions, not current
features. Two microphones alone also impose geometric ambiguities on direction
estimation; camera aiming needs a separately validated design.

The planned outdoor variant adds solar charging, a protected rechargeable battery
and a weather-resistant enclosure. Electronics remain in the sealed compartment;
the downward-facing microphone port uses a hydrophobic acoustic membrane and
replaceable open-cell foam windscreen. Power sizing, ingress protection,
condensation behavior and the acoustic effect of the protective materials all
require measurement before deployment claims are made.

The supported energy design removes unnecessary inference while Linux remains
awake. A future power-state design requires a separately verified wake path. Any
battery-life or solar-assisted autonomy target requires actual measurements and
component sizing.
Passive listening
avoids active acoustic probing; later servos or illumination may still disturb
wildlife and must be evaluated.

## Near-term acceptance story

A quiet background does not create a stream of WAV files. A new sound raises the
gate, which preserves its beginning and captures a complete window. The receiver
checks the audio and records the reason it was selected. The local model attaches
ranked candidates and keeps a weak result as `unknown`. A first announced assiolo
replay passed; the next milestone completes its provenance and adds negative
controls. The dashboard remains future work.

## Publication discipline

Use a video of a repeatable experiment, an annotated wiring photo, an architecture
diagram, event evidence cards and a candid limitations table. Keep synthetic,
replayed and actual field recordings clearly labeled. Do not reuse assets or
results from unrelated example applications as wildlife evidence.
