# Offline by design: preserve observations, not dependence on a connection

Implementation status reviewed on September 14, 2026; see the
[current status ledger](CURRENT_STATUS.md) for the cross-project evidence boundary.

## Design intent

Sylva EchoLens should keep observing even when there is no network to report to.
In the lightweight configuration now being developed, a single microphone replaces
the need for a camera or moving mechanisms. On-device recognition is therefore not
just a latency feature: it lets the unit turn sound into a useful observation at
the place and time it happens, without waiting for a cloud service.

The goal is extended unattended operation without Internet access and with very
low energy consumption. While storage allows, the unit should retain both the
observation and its acoustic evidence. As space becomes scarce, priority shifts
from retaining recordings to retaining compact recognition records. The field
notebook can continue growing after the audio archive reaches its allocated budget.

This does not imply unlimited autonomy: energy, storage, component reliability and
clock drift still bound deployment duration. Records themselves also consume space.

## Current variant and implementation status

- Current development variant: one INMP441, no camera and no servo/pan-tilt.
- Implemented and host-tested: BirdNET v2.4 inference, audio quota, separate record
  and system reserves, protected FIFO retention, recognition-only persistence,
  startup reconciliation and explicit time-quality metadata.
- Device status: deployed and smoke-tested with isolated scratch storage, a clean
  application restart and cached BirdNET inference in a networkless container.
  Physical power-cut and endurance acceptance remain outstanding.
- An experimental Linux suspend-to-idle path reached the kernel power state, but
  acoustic UART wake did not pass device acceptance. It is disabled by default and
  excluded from the release; Linux remains awake in the supported configuration.

## Implemented storage behavior

Here, storage means persistent flash or disk, not the MCU's working RAM.
The writer reserves capacity for the operating system and observation records before
the audio area fills. Default audio, record and system boundaries are 512 MiB,
16 MiB and 128 MiB and are configurable through the environment.

| Condition | Implemented behavior | Evidence consequence |
|---|---|---|
| Audio budget available | Run local inference and retain observation plus event WAV | The prediction can be reviewed against its source recording |
| Audio budget exhausted; record reserve available | Infer through a bounded temporary WAV, delete it, persist compact JSON | Mark audio `never_retained` |
| Room can be reclaimed | Delete the oldest unprotected, indexed WAV only | Preserve JSON, original hash and removal reason/date |
| No safe record space remains | Raise and log persistence failure | Do not claim a durable observation |

`SYLVA_RETENTION=delete_oldest` enables protected FIFO retention;
`SYLVA_RETENTION=recognition_only` preserves existing WAVs and sends only new events
to the compact path. Only app-owned `event-*.wav` files with readable JSON are
candidates. JSON, unrelated, protected, corrupt and orphan files are not deleted.

Recognition-only mode still requires audio acquisition and model processing.
It saves persistent storage; it does not eliminate inference energy. Its temporary
path is independent of a successful permanent WAV write.

## Minimum recognition record

The compact record retains:

- Event ID and device/session identity.
- Observation time, time source/uncertainty and monotonic/sample position. Do not
  assume network time remains available or that an offline reboot preserves UTC.
- Predicted species/class, model score, model version and decision threshold.
- Explicit unknown/uncertain status when no supported identification can be made.
- Relevant acoustic context such as trigger RMS, background estimate and duration.
- Audio availability: retained, never retained, or removed by retention policy;
  keep a hash/reference when one was actually computed.

A model prediction remains a prediction, not a verified species observation.
Without retained audio, later re-listening or reclassification may be impossible.
This trade-off must remain visible in exported observations and published claims.

## Restart and time behavior

At startup the store removes incomplete hidden WAV temporaries, completes valid
pending JSON publication and already-journaled retention, marks missing/corrupt
audio, and creates minimal inventory sidecars for orphan WAVs. It never fabricates
samples, repairs audio silently or deletes an unindexed final WAV. Recovery counters,
boot count and the last wall-clock anchor live in `.sylva-state.json`.

Every new event contains UTC, declared clock source, quality and uncertainty, Linux
boot ID, monotonic seconds and MCU trigger sample. Time defaults to `unverified`.
Configure `SYLVA_TIME_QUALITY=synchronized` or `rtc` and an uncertainty only after a
real clock procedure. A time earlier than the saved anchor is marked `regressed`.
Monotonic time orders records within one boot but does not establish UTC across boots.

## Power evidence

Records include inference and total processing durations. Whole-board baseline and
incremental inference/write watts still require a physical instrument. Feed measured
values to `scripts/estimate-autonomy.py`; it reports energy per day and estimated
days from usable battery Wh. Incremental watts are interpreted above baseline.
This calculation does not turn assumed inputs into measured autonomy.

The disabled experiment used Linux `freeze` after an idle period. Its application
guards and MCU handshake remain host-tested research code, not a supported operating
mode. The device test did not establish acoustic UART wake, event preservation across
wake or an energy benefit. Any future power-state design needs an independently
verified wake source before integration with the observation pipeline.

## Offline readiness and evidence plan

Preinstall model weights, preprocessing assets and runtime dependencies. Observation
must not require a cloud API, online authentication refresh or network download
during normal operation. Export by local retrieval or later connectivity is a
separate workflow, not a prerequisite for recognizing and storing an event.

Before calling this capability fully device-accepted, test in an isolated scratch
storage area with synthetic/replayed data, never by filling the board root filesystem:

1. Boot and run with Internet unavailable; verify acquisition, inference and records.
2. Exhaust a small test audio quota; verify transition to recognition-only storage.
3. Verify prediction provenance and explicit missing-audio status in both modes.
4. Exercise configured eviction, record-reserve exhaustion and interrupted writes.
5. Restart offline and verify record recovery, IDs and honest timestamp quality.
6. Measure whole-board power in each mode and estimate deployment duration using
   measured event rates and storage growth, with assumptions stated.
7. If low-power research resumes, validate the wake source independently before
   reconnecting suspend to acoustic events or claiming preserved post-wake evidence.

Deployment, isolated quota transitions and networkless cached inference now have UNO
Q smoke evidence. A clean application restart also passed. Controlled interruption of
every write phase, Linux/board reboot, reserve exhaustion, power measurement and
endurance remain acceptance work.
