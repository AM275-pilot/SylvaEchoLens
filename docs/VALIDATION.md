# Validation and acceptance experiments

## Host checks

Python 3, no extra packages:

```powershell
python -m unittest discover -s tests -p "test_*.py" -v
```

Portable C++17 (Linux/WSL):

```sh
g++ -std=c++17 -Wall -Wextra -Werror -fsanitize=address,undefined \
  tests/test_acoustic_pipeline.cpp -o /tmp/sylva-gate-test
/tmp/sylva-gate-test
```

Tests cover signed sample order, BirdNET-result normalization and failure
retention, DC offset rejection, isolated spikes,
two-of-three confirmation, frozen background, sustained-event suppression,
release/cooldown, ring wrap, exact pre-event history, immutable event payload,
WAV byte equality, geometry, duplicate handling, missing chunks, checksums,
timeout, reboot session and evidence JSON.

Offline-store tests additionally cover quota fallback, temporary-file cleanup,
protected FIFO retention, atomic JSON recovery, missing/orphan/corrupt audio,
clock regression and autonomy arithmetic from supplied measurements. Power-manager
tests cover missing-helper refusal, idle/busy decisions, MCU arm-before-request,
resume cleanup, timeout fail-open behavior and environment validation.

## Device acceptance

1. Start the matching receiver, upload the sketch, and keep startup background
   representative for five seconds.
2. Observe `settling → calibrating → listening` and finite RMS/floor thresholds.
3. Keep quiet for 30 seconds. Record event count; do not interpret arbitrary
   ambient noise as an implementation fault without examining the signal.
4. Play a labeled test sound; verify a trigger and a 2.048 s mono WAV.
5. Check CRC, hash, no missing chunks, no unintended clipping, and waveform at
   the 0.512 s trigger boundary. Listen to the file.
6. Repeat at three levels/distances. Retain the settings and evidence cards.
7. Test a sustained sound: expect one fixed window until release/rearm.
8. Test close-spaced sounds: note skipped triggers while the MCU event slot is busy.
9. Run for ten minutes and inspect capture errors, receive rejections, timing,
   storage and free memory. Do not claim long-run stability from host tests.

## Archived suspend-to-idle experiment

This procedure records the experiment that failed device acceptance. It is not a
release acceptance path unless a future design supplies a verified wake source.

1. Confirm `/sys/power/state` includes `freeze`, `power/helper.ready` contains
   exactly `freeze`, and the systemd path unit is active.
2. Confirm the application is idle and that ordinary one-second MCU telemetry stops
   after it logs a suspend request.
3. Trigger a known acoustic event. Verify Linux resumes, `suspend.result` reports
   `status=resumed`, and the UART interrupt delta is recorded when available.
4. Verify the wake-causing event is transferred completely and passes geometry,
   CRC, SHA-256, WAV and JSON checks. Record time from trigger to first Bridge message
   and to completed persistence.
5. Repeat at least 30 acoustic wake cycles, plus quiet periods and wake by another
   enabled source. Count missing events, spurious resumes and timeouts separately.
6. Stop or remove the helper and verify that missing readiness leaves Linux awake;
   simulate a stale/failed result and verify the MCU is disarmed after timeout.
7. Compare whole-board energy over equivalent awake-idle and `freeze` intervals.
   Suspend correctness does not by itself establish useful energy savings.

The first implementation targets suspend-to-idle only. Do not substitute `deep`
without a new wake-source, bridge recovery and event-integrity acceptance record.

## Result record

### September 5, 2026 — first matched firmware/receiver run

- Python 3.13: all 9 unit tests passed.
- C++17 / GCC 13 in WSL: assertions passed with `-Wall -Wextra -Werror` and
  address/undefined-behavior sanitizers. Shared CRC vector: `170aea81`, independently
  matched by Python `zlib`.
- UNO Q build: 79,172 bytes flash; 211,180 bytes static RAM (80% of the sketch
  budget), leaving 50,964 bytes for dynamic use. The compiler's low-memory
  warning remains relevant; stack high-water marks have not been measured.
- Uploaded sketch BIN SHA-256:
  `33E6090545F7C7A16F1A792178842A05DB2B64F90DC7EB81390B6C96B8A12815`.
- MCU boot at `17:36:32 UTC`, protocol 1, capture error 0. Observed settling,
  calibration, listening, active and cooldown on the physical board.
- Seven events saved by `17:38:46 UTC`; no capture/rejection errors in this
  observed interval. Eighteen busy-slot triggers had been skipped by then.
  This is a short smoke test, **not** the ten-minute acceptance run.
- Independently pulled and audited the first three WAV/JSON pairs on Windows:
  mono PCM16, 16 kHz, 32,768 samples, 8,192 pre-event samples; CRC and SHA matched.
  The confirmation-frame RMS recomputed from each WAV matches the MCU RMS,
  verifying the numeric sample contract across both processors.

| Event | MCU confirmation RMS | WAV confirmation RMS | Transfer (s) | Clipped samples |
|---|---:|---:|---:|---:|
| 1 | 187.527374 | 187.527368 | 13.263 | 0 |
| 2 | 116.277733 | 116.277734 | 13.287 | 0 |
| 3 | 114.798340 | 114.798341 | 13.259 | 0 |

Session: `9ca0081d97a349d1b874e456e3600ca3`.
First WAV SHA-256:
`d309feca45afa99ae2bb1696e375e62fe792d7102475a535aa06e23144b72454`.
Local evidence: `artifacts/2026-09-05-gate/events/` (ignored by Git).
Stimulus was **unlabeled ambient sound**: neither a known replay nor a wildlife
observation. No listening/frequency-response validation was performed in this run.

Repeat the independent audit and generate SVG waveform evidence cards:

```powershell
python scripts/audit-events.py artifacts/2026-09-05-gate/events
```

The shaded prefix is the pre-event history, the dashed line starts the confirmation
frame, and the waveform is min/max downsampled with an explicitly labeled automatic
amplitude scale. These cards are visual aids, not calibrated acoustic plots.

Still required: labeled replay/listening, quiet-baseline false-trigger measurement,
distance/level sweep, long-run stability, throughput improvement and species-model
evaluation. CRC cannot identify dropped samples upstream of the MCU event buffer.

### September 8, 2026 — release-pipeline integration (host only)

- Added the optional App Lab local audio-classification adapter after checked WAV
  publication and before evidence JSON publication.
- All 15 Python tests pass, including normalized score metadata and preservation of
  a checked WAV when inference fails.
- The explicit LED grayscale correction compiles against the verified custom loader:
  79,232 bytes flash and 211,192 bytes static RAM, leaving 50,952 bytes. The existing
  low-memory warning remains relevant.
- Deployed the matching receiver and uploaded the sketch after reconstructing the
  previous deployed firmware. Its rollback `sketch.ino.elf-zsk.bin` matches the known
  SHA-256 `33E6090545F7C7A16F1A792178842A05DB2B64F90DC7EB81390B6C96B8A12815`.
  The new uploaded sketch SHA-256 is
  `D8F306F0660DE5D885445AF950D3BEEA96F466C8AB400FD728903A88480E3114`.
- After recreating one ephemeral app container to clear a corrupt Docker JSON log,
  fresh logs show the receiver running, classification explicitly disabled, and live
  `listening` telemetry with finite RMS/floor and skip count reset to zero. Bound app
  data and event files were preserved.
- No wildlife model was installed. Visible LED behavior still needs a human board
  check, and wildlife inference remains device-unverified.

### September 9, 2026 — BirdNET v2.4 board integration

- All 16 Python tests pass. They verify the exact BirdNET v2.4 FP32/LiteRT selection,
  stable candidate metadata, threshold-to-`unknown` behavior and source/model input
  geometry flags without requiring the runtime during host tests.
- Provisioned the locked Python environment on UNO Q and cached the official model.
  The model SHA-256 is
  `55f3e4055b1a13bfa9a2452731d0d34f6a02d6b775a334362665892794165e4c`;
  the English label list has 6,522 entries and includes `Otus scops`.
- Board inference on a prior unlabeled event completed successfully. Its best score
  was 0.0121617, so the 0.25 policy emitted `unknown` and retained five candidates.
- Repeated that inference in an ephemeral container with Docker networking disabled;
  it returned the same decision and score from local cached assets.
- These checks establish executable offline inference, not recognition quality. A
  labeled bird-call replay and speech/quiet negative controls remain outstanding.
- A new device event at `2026-09-09T05:27:30.867755Z` completed the entire live path:
  32,768 samples, CRC and SHA verified, 13.269 s transfer, no clipping and BirdNET
  metadata published without an inference error. The 0.0648866 best score produced
  `unknown`; stimulus identity is pending user annotation, so this is not yet a
  labeled recognition result. Local ignored evidence is under
  `.codex-build/evidence/20260909-birdnet-playback/`.

## Verification after repository correction

Re-ran all 9 Python tests, the sanitized C++ assertions and the three-file WAV
audit from the authoritative checkout: all passed. Compiled
the sketch from this checkout using the external custom toolchain: successful,
with the same 79,172-byte flash / 211,180-byte static RAM result and low-memory
warning. Active sketch and Python source hashes match the version already
deployed on the board. No additional flash was needed. `.gitattributes` and Git
metadata were preserved; changes remain local and uncommitted.

## Limits of these checks

### September 13, 2026 — offline storage implementation (host only)

- Added bounded audio, record and system reserves with protected FIFO retention.
- Added recognition-only classification through deleted temporary audio, with
  explicit audio provenance and preserved SHA-256 in the durable JSON record.
- Added startup reconciliation for pending writes, retention, missing/corrupt audio
  and orphan WAV inventory, plus persistent boot/counter state.
- Added declared clock quality, uncertainty, boot ID, monotonic time, trigger sample
  and backward-clock detection.
- Added per-event processing timing and an autonomy estimator requiring measured
  whole-board inputs. No power or autonomy value was measured.
- At this host-only checkpoint, all 30 Python tests passed. Device deployment,
  forced interruption, scratch-quota and endurance acceptance remained outstanding
  because the board was not connected.

These host checks do not establish long disconnected endurance, measured power,
device-safe retention or recognition quality. Execute the separate
[offline acceptance plan](OFFLINE_OPERATION.md#offline-readiness-and-evidence-plan)
before advancing those claims.

### September 13, 2026 — offline storage UNO Q smoke test

- Deployed the matching Python application to ADB device `2064497211`; no STM32
  flash was needed. The deployment helper preserved rollback snapshot
  `.codex-build/rollback/20260913-131627-before-app-deploy/`.
- Remote SHA-256 values matched the local sources: `main.py`
  `19b763df8ff77c70245df104a69dc33c3f1b191b9f878e580cd72ffbe6b495ce`,
  `event_receiver.py`
  `d0d11153bfe58b548d672a51676dee13a84b0c3ea119defe3137f3b1bf41f822`,
  and `offline_store.py`
  `a16e09dc132df993ecceafc53df6e84f3e14781442dad943bfea5e423c5a8d4e`.
- The device had 17,135,734,784 bytes free on the app filesystem and 1,922,637,824
  bytes free in `/tmp` before testing. Startup reported the documented 512 MiB
  audio budget, 16 MiB record reserve and 128 MiB system reserve.
- An isolated `/tmp/sylva-offline-smoke` test passed retained audio, protected-audio
  fallback, FIFO removal with sidecar preservation, recognition-only persistence,
  corrupt-orphan indexing and persistent state across store reconstruction.
- A separate container used `--network none`, the deployed virtual environment and
  cached BirdNET assets. With audio quota zero it classified a stored device WAV as
  `unknown` at score `0.046614330261945724`, recorded model
  `BirdNET_GLOBAL_6K_V2.4`, deleted temporary audio, and persisted only metadata.
  Inference took 8.9266 seconds; total store processing took 8.9854 seconds. This is
  execution evidence, not a labeled recognition-quality result.
- Restarting the app while a prior event was in flight caused expected `no matching
  event` chunk rejections. A WAV published before a subsequent app initialization
  lacked its JSON; startup recovery preserved it and created a
  `retained_recovered` sidecar with an unverified filesystem-mtime timestamp. This
  confirms honest orphan recovery but also records one incomplete live observation.
- A later clean app stop/start advanced persistent `boot_count` to 4 with the same
  Linux boot ID and a zero-count recovery report; the gate returned to `listening`.
- BirdNET shutdown emitted a Python resource-tracker warning for five shared-memory
  objects. The tracker removed them; the restarted container had no `bn_*` entries
  in `/dev/shm`. Treat the warning as an upstream/runtime lifecycle issue to watch.
- Two test-harness attempts failed before the successful offline inference: the
  image entrypoint initially started the normal app instead of the script, and a
  direct test lacked Python's multiprocessing main guard. The extra container was
  removed and the guarded test was rerun with the deployed virtual environment.

Local ignored evidence is under `.codex-build/evidence/20260913-offline-device/`.
No physical power cut, whole-board power measurement, autonomous runtime claim or
long-duration storage test was performed.

### September 13, 2026 — coherence verification and matched redeployment

- Removed the unused persistence helper from `event_receiver.py`; the receiver now
  owns only bounded assembly and integrity checks, while `ObservationStore` is the
  sole runtime persistence path.
- Current checks pass: 29 Python tests, Python bytecode compilation, PowerShell
  parsing, and the C++17 gate/buffer test with address and undefined-behavior
  sanitizers. The lower Python count reflects consolidation of duplicate persistence
  tests, not removed behavior coverage.
- The guarded firmware build succeeds with 79,232 bytes flash and 211,192 bytes
  static RAM, leaving 50,952 bytes. The known low-memory warning remains.
- The matching Python application was redeployed with rollback snapshot
  `.codex-build/rollback/20260913-144216-before-app-deploy/`; the STM32 was not
  reflashed. Board and local SHA-256 values match for `main.py`
  (`fb6b6b58f73484a1cb25c04b80a60819464e4daef4003b4b582d92c7d896104f`),
  `event_receiver.py`
  (`7b6019e6988a6f85f6cd456d18a268c1a0f4653f7f4e0d1a3a2d3629590138d8`), and
  `offline_store.py`
  (`f7ee981ff9cab0b353302c1bd2ec9e29cd39da82bb8b2f449d2649db45ae19d4`).
- Startup showed zero recovery actions, BirdNET enabled and the gate in `listening`.
  This cleanup did not add a labeled recognition result, power-cut test, physical
  reboot, endurance run or power measurement.

### September 13, 2026 — suspend-to-idle implementation checkpoint

- The connected UNO Q exposes `freeze`, `mem` and `disk`; `deep` is selected for
  `mem`. The implementation uses only the more recoverable `freeze` state.
- `/sys/class/tty/ttyHS1/power/wakeup` exists for the Bridge UART and was disabled
  before helper installation. The kernel exposes a `qcom_geni_serial_uart1`
  interrupt counter for supporting wake evidence.
- All 37 Python tests pass, including eight suspend-coordinator cases. Python bytecode
  compilation, PowerShell parsing and the portable sanitized C++ test pass.
- Matching firmware was built and uploaded: 84,956 bytes flash, 213,558 bytes static
  RAM and 48,586 bytes remaining. The low-memory warning still applies.
- The matching app was deployed and showed clean MCU boot, calibration and listening.
  With no helper marker it logged `helper_ready=False` and did not request suspend.
- Direct Bridge calls to the deployed `sylva_power_save` provider returned `true`
  for both arm and disarm, verifying the app-to-MCU control contract.
- The helper, installer, uninstaller and systemd units were staged on the board.
  Their shell syntax passes on the device. Root installation awaits interactive
  owner authentication; the app was deliberately stopped while waiting so helper
  activation cannot cause an unobserved first suspend.

This checkpoint preceded the physical experiment below and did not yet prove one
physical suspend/resume cycle, acoustic wake, wake-causing event integrity, repeated
reliability or reduced whole-board energy.

### September 14, 2026 — suspend-to-idle device rejection

- Installed and activated the restricted helper with owner authentication. The
  marker and systemd path unit were present, and the application restarted its full
  60-second idle window before the first request.
- Linux entered kernel `s2idle`; ADB disappeared as expected. The previous-boot
  journal later showed multiple `PM: suspend entry (s2idle)` and `PM: suspend exit`
  pairs, proving that the kernel power transition itself worked.
- Resumes occurred after varying intervals through enabled sources that were not
  attributable to an acoustic event. Repeated automatic cycles made ADB intermittent.
- A controlled one-shot test removed the readiness marker, armed the deployed MCU
  provider manually and submitted exactly one `freeze` request. Deliberate noise near
  the microphone did not return ADB within the observation window.
- The board required power-control or power-cycle recovery. After a full power cycle,
  the marker was absent, the application restarted, recovery counters were zero and
  listening telemetry resumed.
- The release default is now `SYLVA_LINUX_SUSPEND=disabled`. The helper may remain
  installed without effect, but no readiness marker is published.

Conclusion: kernel suspend/resume is real, but acoustic UART wake and preservation of
the wake-causing event were not demonstrated. Suspend-to-idle is rejected from the
release and no energy-saving claim is attached to it.

CRC proves transfer integrity, not acoustic fidelity. A plausible RMS does not
establish bandwidth, calibration or species accuracy. The 16 kHz rate is
configured; clock accuracy has not been independently measured. Gate recall
must be measured on representative weak/short calls, wind and other backgrounds.
