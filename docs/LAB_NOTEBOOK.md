# Lab notebook

## 2026-09-13 — Implement bounded offline persistence

- Added separate audio, record and system-space boundaries. The default retention
  policy removes only the oldest indexed, unprotected app WAV and keeps its JSON,
  hash and removal reason. A non-deleting recognition-only policy is configurable.
- Added temporary-audio BirdNET inference when a permanent WAV cannot be admitted.
  The resulting JSON explicitly states that audio was never retained.
- Added atomic sidecars and state, startup reconciliation for interrupted writes,
  missing/corrupt files and orphan audio, and persistent recovery counters.
- Added UTC source/quality/uncertainty, boot ID, monotonic time and MCU sample position.
  Time is unverified by default and backward movement is marked `regressed`.
- Added inference/processing durations and a host-tested autonomy calculator that
  accepts measured power inputs. No power value or battery duration was fabricated.
- At this host-only checkpoint, all 30 Python tests passed. The board was not
  connected, so deployment, real power interruption, scratch-quota, offline reboot
  and endurance checks remained pending.

### UNO Q deployment and smoke evidence

- The board later became available as ADB `2064497211`. Deployed the Python side
  with rollback snapshot `20260913-131627-before-app-deploy`; local and remote source
  hashes matched. The STM32 firmware was unchanged and was not reflashed.
- Scratch storage on the device passed quota, protection, FIFO removal,
  recognition-only fallback, state reconstruction and corrupt-orphan indexing.
- Cached BirdNET then ran in a separate `--network none` container with quota zero.
  It returned `unknown` at 0.0466143 in 8.9266 seconds and left no temporary WAV.
- A deployment-time restart crossed an in-flight transfer: continuation chunks were
  rejected and a final WAV without sidecar was later indexed as
  `retained_recovered`. This is a successful recovery test and a recorded lost
  observation, not a fully delivered event.
- A clean application restart subsequently produced an empty recovery report and
  returned to `listening`. This was not a Linux reboot or physical power cut.
- Initial offline test attempts exposed the image entrypoint and Python 3.13
  multiprocessing-main requirements; both failures were retained in this record.
  BirdNET shutdown also warned of five shared-memory objects, which the Python
  resource tracker removed; none remained after restart.
- Power and autonomy remain unmeasured because no inline power instrument was used.

### Coherence cleanup and matched redeployment

- Removed an unused duplicate WAV/JSON writer from `event_receiver.py`; runtime
  persistence, classification and failure provenance now have one owner in
  `offline_store.py`. Equivalent persistence coverage remains in the store tests.
- Removed unrelated legacy documentation and workstation-specific paths, serials,
  ports and schedule dates from current guidance. Historical experiment dates remain
  because they identify validation evidence.
- The current suite passes 29 Python tests plus the C++17 sanitizer test. The guarded
  firmware build still uses 79,232 bytes of flash and 211,192 bytes of static RAM,
  leaving 50,952 bytes and the existing low-memory warning.
- Redeployed the matching Python application without reflashing the STM32. Rollback
  snapshot: `.codex-build/rollback/20260913-144216-before-app-deploy/`.
- Local and board SHA-256 values match: `main.py`
  `fb6b6b58f73484a1cb25c04b80a60819464e4daef4003b4b582d92c7d896104f`,
  `event_receiver.py`
  `7b6019e6988a6f85f6cd456d18a268c1a0f4653f7f4e0d1a3a2d3629590138d8`,
  and `offline_store.py`
  `f7ee981ff9cab0b353302c1bd2ec9e29cd39da82bb8b2f449d2649db45ae19d4`.
- Startup reported zero recovery actions, enabled offline BirdNET and returned the
  gate to `listening`. No new acoustic event, physical reboot, power-cut, endurance
  run or power measurement was performed during this cleanup.

## 2026-09-11 — Reframe documentation for beginner reproduction and publication

- Added a single beginner-oriented project guide with the story, complete prototype
  and lab BOM, software/tool inventory, one-microphone wiring schematic, guarded
  recreation sequence, code-contribution map and known limitations.
- Mapped the documentation directly to the project-documentation, BOM, schematics,
  code/contribution and creativity criteria. Added an evidence shot list and a
  90-second demonstration storyboard without fabricating missing photos or results.
- Marked publishable wiring photographs, screenshots, labeled playback evidence and
  the demonstration video as pending. Raw audio and large video remain local-only.
- Corrected stale summary text: BirdNET v2.4 has executed on the board and repeated
  offline on an unlabeled event; recognition quality and labeled replay remain open.
- Documentation-only change. No firmware deployment, board change, commit or push
  was performed.

## 2026-09-08 — Closing the release loop

- Reconfirmed the correct repository root and GitHub origin. The UNO Q was reachable
  over ADB and through its discovered upload port; the `audio-test` app was stopped.
- Confirmed that unrelated model configurations already present on the board are
  not wildlife evidence for this project.
- Connected checked WAV persistence to an optional local App Lab classifier and made
  model failure preserve the recording with explicit error metadata. Fifteen host
  tests passed.
- Fixed the loader boot-animation dependency by selecting 3-bit matrix grayscale in
  the sketch and writing full 3-bit pixel values. The sketch compiled with the custom
  I2S loader and was uploaded after reconstructing the previous exact firmware binary.
  New `sketch.ino.elf-zsk.bin` SHA-256:
  `D8F306F0660DE5D885445AF950D3BEEA96F466C8AB400FD728903A88480E3114`.
  A human visual check of the matrix is still pending.
- Deployed and started the matching Linux receiver through the rollback-first helper.
  A stale/corrupt Docker JSON log blocked normal inspection, so the exact ephemeral
  `audio-test-main-1` container was stopped and recreated after verifying that app and
  events are bind-mounted. Fresh logs show live `listening` telemetry and the intended
  `Local classification disabled` state; stored app data was retained.
- A versioned wildlife model and representative labeled evaluation set remain the
  release blockers.

## 2026-08-30 — Establish the electrical path

- Hardware: one INMP441; purple SCK to D21/SCL, green WS to D10, blue SD to A4.
- Built ArduinoCore-zephyr 0.90.0 with I2S enabled and SAI1_A pin selection.
- Modified Zephyr 4.2 STM32U5 SAI DMA width from half-word to word for this
  dedicated 32-bit-slot configuration.
- Observed buffer overrun with delayed reads. Continuous draining and larger
  DMA buffers allowed four consecutive 32-chunk captures in the recorded test.
- The saved WAV had nonzero, nonsaturated values. At the time, a firmware byte
  swap was interpreted as a hardware alignment requirement.
- Archived loader and recordings in ignored local build storage.
- Important qualification: this was bring-up evidence, not wildlife/model or
  field-fidelity validation.

## 2026-09-05 — Define the mono milestone and audit the sample contract

- User requirement: documentation is fundamental; use English source and
  documentation, with natural comments and creative, professional evidence.
- Current scope remains **one microphone**.
- Kept unrelated example material outside the active implementation and evidence.
- Snapshot before edits: `.codex-build/rollback/2026-09-05-before-gate/`.
- Found that high-byte-first textual samples were written directly into a
  little-endian WAV. The firmware byte swap compensated at the file boundary,
  but MCU-side energy values were not the same signed samples.
- Corrected the boundary explicitly: native MCU PCM, numeric hex, Python s16le.
- Replaced periodic recording with an adaptive event gate and bounded history.
- Added CRC validation, strict rejection of incomplete events, immutable event
  storage during transfer, and WAV evidence cards.
- Moved reproducibility patches out of ignored build storage into
  `firmware/patches/`.
- Validation evidence and remaining hardware checks are in `VALIDATION.md`.

### Build and first live gate evidence

- First build failed at link time: `log10f` pulled an unavailable `__errno`
  symbol from this loader/toolchain combination. Replaced only the LED display
  logarithm with equivalent approximately 6 dB thresholds; detector math is unchanged.
- Removed unused peak-meter and old frame-ready APIs from the capture backend.
- Fixed a malformed hunk count in the archived DMA patch; both versioned patch
  files now parse with `git apply --numstat`. This is not a fresh-core apply test.
- Added non-sleeping 100 ms transmission pacing to let DMA draining catch up
  between Bridge notifications.
- Saved the previous board Python/app configuration under
  `/home/arduino/ArduinoApps/audio-test/.cache/pre-gate-20260905/`.
- Deployed the matched receiver and sketch using the existing custom loader.
  Nine Python tests and sanitized portable C++ assertions pass.
- First three live events passed an independent Windows audit: WAV confirmation
  frame RMS agrees with MCU measurement. This resolves the numeric byte-order
  inconsistency at the measurement/transport boundary.
- Measured transfer: 13.26–13.29 seconds per event. Busy-slot skips are visible,
  so throughput remains an explicit next engineering task.
- Added a reproducible audit script that also produces local SVG waveform cards.
  Raw ambient audio is kept outside version control; stimulus identity is unknown.

## Repository correction — September 5, 2026

The user identified `AM275-pilot/SylvaEchoLens` as the authoritative repository.
The implementation had mistakenly been written in a separate example checkout.
Copied the active source, documentation, tests and ignored local evidence into the
correct project without replacing existing files. Kept generated build tools and
rollback files outside version control. Updated the build helper to accept an
external toolchain root. No commit, push or additional board flash was performed as
part of this relocation.

## Offline-first rationale — September 5, 2026

The user clarified why local recognition is fundamental: the lightweight unit
should remain disconnected from the Internet for extended periods, with no camera
or servo and a very-low-power objective. Keep observations and their audio while
storage permits; prioritize compact recognition records when the audio budget is
exhausted, instead of depending on a cloud connection to interpret stored sounds.

Recorded the intent in `OFFLINE_OPERATION.md`, the project brief, README and
ADR-012 through ADR-014. The design proposes reserved record/system capacity,
explicit audio-retention status and a finite-storage failure policy. Audio removal
order and quota values still need decisions. Recognition-only records sacrifice
later audio verification; this limitation is part of the observation provenance.

This change is documentation-only: no firmware, runtime behavior, recording or
retention policy was changed. No power, endurance or storage-fallback test was
performed. Very low consumption remains a target; Linux still stays running.

## Evidence conventions

## 2026-09-09 — Select and integrate the first species model

- Selected the official BirdNET v2.4 FP32 acoustic model through LiteRT, pinned via
  `birdnet==1.1.1`. Model files remain in the ignored persistent app cache.
- The adapter stores five ranked species candidates and emits `unknown` below 0.25.
  Geographic filtering is deliberately unset until a deployment location is stated.
- The current 16 kHz, 2.048-second mono event is resampled to 48 kHz and padded to
  the model's three-second window. This is functional adaptation, not proof that the
  present capture geometry is optimal; frequencies above 8 kHz were never captured.
- Host tests cover model selection, thresholding, evidence shape and input-contract
  flags. Board provisioning and labeled acoustic replay remain to be recorded.
- BirdNET source code is MIT; the v2.4 model is CC BY-NC-SA 4.0, a release constraint
  for attribution, share-alike derivatives and non-commercial use.
- Provisioning on UNO Q completed with Python 3.13.14 and the locked dependency set.
  Cached model SHA-256 is
  `55f3e4055b1a13bfa9a2452731d0d34f6a02d6b775a334362665892794165e4c`.
- A prior unlabeled event produced a best score of 0.0121617 and therefore `unknown`.
  The same result ran with Docker networking disabled, confirming cached local
  execution. It is a runtime check, not an animal-recognition result.
- The first post-integration live event (`ceead83f.../000016`) passed independent WAV,
  CRC, SHA and trigger-frame checks and received BirdNET metadata end to end. Best
  score was 0.0648866 (`Psilopogon zeylanicus`); `Strix aluco` ranked third at
  0.0359597. The decision remained `unknown`. Do not label or score this replay until
  its playback source is supplied.
- The audit also exposed five zero-byte WAV names from September 5 and 8 sessions.
  They predate this BirdNET deployment and were excluded rather than repaired or
  deleted. Their origin remains an evidence-retention defect to investigate; the new
  event is a complete 65,580-byte WAV.

## Acoustic replay setup — September 5, 2026, 18:59 UTC

At the user's request, started the stopped receiver and confirmed fresh MCU
listening telemetry without reflashing. Recorded baseline counters and storage
availability in [the replay test record](2026-09-05-REPLAY-TEST.md). The user plans
to play an assiolo recording; playback and acoustic results are not yet confirmed.

## Evidence categories

- **Host synthetic:** generated signals with known amplitude and timing.
- **Device transport:** confirms firmware/Bridge/WAV agreement.
- **Acoustic replay:** known sound played through a loudspeaker into the mic.
- **Field recording:** uncontrolled real environment, annotated afterward.

Keep those categories separate. Record failure conditions, sample rate, software
revision, loader hash, parameters, stimulus, distance and hashes. Never label a
synthetic sound as a wildlife observation.

## Linux suspend-to-idle implementation — September 13, 2026

- Confirmed on the UNO Q that the running kernel exposes `freeze`, `mem` and `disk`;
  `deep` is the selected `mem_sleep`, but this first implementation deliberately uses
  only `freeze` for a recoverable suspend-to-idle acceptance path.
- Confirmed that the Bridge host UART is `ttyHS1`, exposes a wake control currently
  disabled by default, and has a visible `qcom_geni_serial_uart1` interrupt counter.
- Added an MCU `sylva_power_save` provider. It arms only from a healthy listening
  state, suppresses periodic telemetry, emits one `sylva_wake` notification after an
  acoustic event, preserves the immutable event and delays transfer by up to 1.5 s.
- Added a Python coordinator that waits for a truly idle receiver/writer, arms the
  MCU before atomically requesting suspend and disarms on resume, failure or timeout.
  Missing helper readiness is fail-safe and leaves Linux awake.
- Added a root-owned helper plus systemd path unit. The helper accepts only `freeze`,
  enables UART wake, syncs storage and records result and interrupt-delta evidence.
  The container receives no general privileged execution path.
- Added a scoped uninstaller that removes the units, helper and readiness marker so
  the application falls back to awake operation.
- All 37 Python tests pass, including eight power-manager cases. Portable C++ tests
  pass with address and undefined-behavior sanitizers.
- Built and uploaded the matching sketch: 84,956 bytes flash and 213,558 bytes static
  RAM, leaving 48,586 bytes. The compiler low-memory warning remains a release risk.
- Deployed the matching Linux application and observed clean MCU reboot, calibration
  and listening telemetry. The app reported `helper_ready=False` as designed.
- Exercised the deployed MCU power provider over Bridge; arm and disarm both returned
  `true`, confirming the deployed application-to-firmware handshake before suspend.
- Staged the privileged helper files on the board. Activation requires the board
  owner's interactive `sudo` authentication; no physical suspend/wake cycle or
  energy measurement is claimed until that step and the acceptance run complete.
- Added an activation-transition guard: when the helper first appears, the
  coordinator restarts the full idle window instead of suspending immediately from
  time accumulated while the helper was unavailable. Redeployed this version and
  observed `helper_ready=False` with normal listening telemetry.

## Suspend-to-idle device outcome — September 14, 2026

- Installed the helper and observed genuine kernel `s2idle` entry and exit in the
  previous-boot journal. Automatic operation produced repeated cycles with resumes
  from enabled but unattributed wake sources.
- Removed the readiness marker and ran a controlled one-shot cycle. The MCU was armed
  and deliberate nearby noise was produced, but ADB did not return within the test
  window. Acoustic UART wake was therefore not established.
- Recovery required the power control or a power cycle. The next boot used a new
  Linux boot ID, restarted the application with zero recovery actions and returned
  to normal listening with the helper marker absent.
- Closed this line of work for the current release. The application default is
  `disabled`; Linux remains awake. Research code and the failed experiment remain
  documented, but no wake reliability or energy-saving claim is made.
