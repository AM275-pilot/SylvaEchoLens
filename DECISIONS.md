# Architecture decisions

| ID | Date | Decision | Reason and consequence |
|---|---|---|---|
| ADR-001 | 2026-09-05 | One microphone for the current milestone | Direction finding is excluded. Two I2S slots are framing, not two sensors. |
| ADR-002 | 2026-09-05 | STM32 selects events; Linux will classify | Keeps acquisition deterministic and gives the local model more resources. |
| ADR-003 | 2026-09-05 | Native PCM16 on MCU, explicit little-endian WAV conversion | The previous firmware byte swap compensated a receiver bug and corrupted MCU-side amplitude interpretation. |
| ADR-004 | 2026-09-05 | DC-removed RMS with adaptive background floor | A constant offset must not trigger. Values are relative PCM units, not dB SPL. |
| ADR-005 | 2026-09-05 | Two-of-three confirmation, hysteresis and rearm delay | Suppresses isolated spikes and repeated triggers around a boundary. It can miss very short calls; evaluate recall. |
| ADR-006 | 2026-09-05 | Fixed 2.048 s mono events with 0.512 s history | Bounded SRAM and a reproducible first input format; model input length may require revision. |
| ADR-007 | 2026-09-05 | One frozen event at a time; count busy triggers | Never overwrite an event in flight. Some dense activity is intentionally not retained. |
| ADR-008 | 2026-09-05 | Reject incomplete or corrupt events | Never manufacture silence that might bias a model or hide transport faults. |
| ADR-009 | 2026-09-05 | Linux remains running in the first gate implementation | Superseded by ADR-023 after workload gating was established. No autonomy claim was made. |
| ADR-010 | 2026-09-05 | Preserve custom core and driver patches | A normal stock-core upload may remove required I2S support. Build helper checks the known loader hash. |
| ADR-011 | 2026-09-05 | English documentation and evidence with every change | The repository is both an engineering instrument and a reproducible project deliverable. |
| ADR-015 | 2026-09-08 | Classification failure preserves checked audio | Model/runtime faults are recorded in metadata and do not discard independently useful acoustic evidence. |
| ADR-016 | 2026-09-08 | Model identity is part of every prediction | A label without model, version, threshold and normalized score is not release evidence. |
| ADR-017 | 2026-09-09 | Use official BirdNET v2.4 FP32 through LiteRT for the first species MVP | It provides an identifiable offline model and broad taxonomy with a small integration surface. Keep the CC BY-NC-SA model license visible. |
| ADR-018 | 2026-09-09 | Preserve the top five candidates and call sub-threshold output `unknown` | BirdNET has no human/background class and will still rank species; thresholding prevents weak guesses from becoming asserted observations. |
| ADR-019 | 2026-09-13 | Separate audio, record and system-space budgets | Audio must stop consuming space before observation records or the OS are endangered. |
| ADR-020 | 2026-09-13 | Retention may remove only indexed, unprotected app WAVs | Preserve every JSON and audio hash; never select unrelated, orphan, corrupt or protected files. |
| ADR-021 | 2026-09-13 | Recognition-only mode uses bounded temporary audio | Local inference continues without requiring permanent WAV publication, while provenance makes the evidence loss explicit. |
| ADR-022 | 2026-09-13 | Treat wall-clock quality as evidence, not an assumption | Default to unverified, retain boot/monotonic/sample ordering and mark backward time across persisted anchors. |
| ADR-023 | 2026-09-13 | Prototype guarded Linux `freeze` with STM32 UART event wake | The design kept privilege narrow and reached device testing, but is superseded by ADR-024 after wake acceptance failed. |
| ADR-024 | 2026-09-14 | Disable suspend-to-idle and exclude it from the release | Linux entered and exited `freeze`, but acoustic UART wake was not repeatable or attributable. The supported configuration keeps Linux awake; future sleep work requires a verified wake path. |

## Offline-first design direction — September 5, 2026

- **ADR-012 — Recognize at the point of observation.** Local inference is intended
  to allow extended disconnected deployment, not merely faster online responses.
  Install model/runtime assets before deployment; network access must not be a
  normal prerequisite. Inference and storage behavior are implemented; offline
  device endurance remains unverified.
- **ADR-013 — Develop the lightweight acoustic-only variant first.** One microphone,
  no camera and no servo. Very low power is a target; quantify whole-board energy
  before making consumption or autonomy claims.
- **ADR-014 — Prioritize observation records over audio under storage pressure.**
  The writer now uses configurable audio, record and system boundaries, protected
  FIFO WAV retention, and recognition-only persistence. Missing audio is explicit;
  record-full handling fails loudly. Default sizes still require device acceptance.

See [offline operation](docs/OFFLINE_OPERATION.md) for the rationale and acceptance plan.

## Open decisions

- Target species and representative background classes.
- Model input frequency/duration and MFCC versus MFE/spectrogram features.
- Transport throughput and buffering required for repeated/overlapping calls.
- Wind filtering and recovery from a persistent change in the ambient floor.
- Calibrated sensitivity, audio bandwidth and acoustic fidelity.
- Whether a separately verified hardware wake path justifies reopening Linux sleep
  research; the current UART experiment is closed and disabled.
- Battery and solar sizing from measured whole-board consumption.
