# Acoustic replay test — September 5, 2026

Status at the end of this trial: user confirmed playback and three event files were
audited. The acoustic stimulus identity was not established.

## Purpose and stimulus

Verify event triggering and WAV capture using a recording described by the user
as an Eurasian scops owl (Italian: assiolo). This is an acoustic replay test,
not an independently verified species identification or a field observation.
The local species model is not enabled.

Source file/link, actual playback time, speaker, volume and distance: pending.
Suggested first trial: speaker about 50 cm from the single INMP441, moderate
volume, a few seconds of playback, followed by 20 seconds without playback.

## Setup evidence

- Correct project: `AM275-pilot/SylvaEchoLens`.
- Started `/home/arduino/ArduinoApps/audio-test` with App Lab's native app CLI
  following the user's request, at approximately `2026-09-05 18:59:50 UTC`.
- No firmware upload, loader flash, wiring change or threshold change performed.
- Fresh telemetry confirmed `listening` from 18:59:59 through 19:00:14 UTC.
  RMS ranged approximately 1.9–2.6; the floor decreased from 2.8 to 2.2.
  Opening threshold: 96.0 PCM RMS; closing threshold: 67.9.
- Busy-slot skip counter was already 13 and stayed unchanged in that interval;
  this is a baseline counter, not 13 failures attributable to this replay trial.
- At 19:00:15 UTC, the event directory contained 11 WAVs from earlier activity.
  Do not count these as results of the upcoming user playback.
- The filesystem reported about 17 GiB available. No recordings were deleted.
- A fresh MCU boot/calibration sequence was not observed in this check; restarting
  the Linux receiver alone must not be described as recalibrating the MCU.

## Results and pending verification

### Results inspected after playback — approximately 19:08 UTC

- Three events from session `519c58a088254703b3672e9d8c78ad9a` were saved at
  19:05:53 (ID 12), 19:06:35 (ID 13), and 19:06:51 (ID 14) UTC.
- Pulled those WAV/JSON pairs into `artifacts/2026-09-05-replay/` and ran
  `scripts/audit-events.py`: all passed geometry, CRC, SHA and MCU/WAV RMS checks;
  each has zero saturated samples and transfer time approximately 13.26–13.29 s.
- The busy-trigger counter rose from 17 to 27 across the observed interval.
  The single frozen event slot can exclude later sounds while an earlier event
  transfers. Do not claim every replayed call was retained.
- Source audio identity has not been confirmed by listening. These are verified
  transport results, not a successful species-recognition or acoustic-fidelity test.


### LED diagnosis — subsequently corrected

The explanation that low RMS alone accounted for the blank display was insufficient:
telemetry during playback included RMS 163.2 and 116.9, above the first LED threshold
65. The sketch writes pixel values 0/1 using `matrix.draw()` but never specifies
the grayscale depth. The custom loader's `main.c` can set depth to 8 for its boot
animation; `matrixBegin()` does not reset it. In `loader/matrix.inc`, intensity is
computed as `pixel * 8 / (1 << grayscale_bits)`. At depth 8, a pixel value 1 becomes
zero: the matrix remains dark even with nonzero bars. At default depth 3, value 1
is only the dimmest level. This boot-state dependency plausibly explains why the
same sketch can appear different after a board restart.

The subsequent correction explicitly set grayscale depth and matching bright pixel
values in the sketch. It compiled on September 8 and the matching firmware was
uploaded; see [validation](VALIDATION.md#september-8-2026--release-pipeline-integration-host-only).
Actual runtime grayscale state was not read back and a human visual check is still
required. No firmware or threshold changes were made during the September 5
diagnosis itself. Existing tests of audio integrity do not validate the LED display.

### Receiver restart at user request — 19:04 UTC

There was no visible LED scrolling. The container was running; stopped
and started it at 19:04:45 UTC without a firmware upload. Fresh telemetry through
19:05:05 UTC confirmed `listening`, RMS approximately 1.7–4.0, opening threshold
96 and unchanged skip count 17. The first LED level requires RMS 65, so these
measured levels produce a blank matrix by design, not proof of stopped capture.
No user playback or acoustic-fidelity result is inferred from this check.

The three newly completed pairs were identified and their transport integrity was
verified as recorded above. The remaining action is to listen to and label the
recordings and connect any claimed replay event to a documented source, playback
time, level and distance. Do not retroactively treat these files as a labeled
BirdNET result: the model was not enabled during this trial.
