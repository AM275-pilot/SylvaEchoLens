# Architecture and code guide

Current architecture as of September 14, 2026. For the evidence level of each
component, see the [current status ledger](CURRENT_STATUS.md).

## Boundaries

The active source application is `app_audio_test/`; its directory name is retained
for repository continuity. The deployed App Lab application is named
`SylvaEchoLens` and lives at `/home/arduino/ArduinoApps/sylvaecholens`.

| Module | Responsibility |
|---|---|
| `sketch/audio_capture.cpp` | Zephyr SAI1_A, DMA slab ownership, native signed mono PCM |
| `sketch/audio_format.h` | Audio geometry, I2S extraction, numeric hex and PCM CRC |
| `sketch/acoustic_gate.h` | DC-removed energy, calibration, floor adaptation, event decision |
| `sketch/event_buffer.h` | Rolling history and one immutable captured event |
| `sketch/sketch.ino` | Scheduling, Bridge messages, telemetry, RMS LED display |
| `python/event_receiver.py` | Bounded assembly, format conversion and checksum validation |
| `python/offline_store.py` | Quotas, retention, temporary inference, recovery and time evidence |
| `python/power_manager.py` | Idle policy, MCU arm/disarm handshake and fail-safe suspend request lifecycle |
| `python/main.py` | Guarded primary-process entrypoint, App Lab callbacks and bounded offline persistence worker |
| `scripts/linux/sylva-linux-suspend` | Root-owned, narrowly scoped suspend-to-idle helper |

## Sample continuity

```mermaid
sequenceDiagram
    participant M as INMP441
    participant S as STM32
    participant R as Rolling history
    participant L as Linux receiver
    M->>S: Continuous I2S samples
    S->>R: Retain last 8192 mono samples
    S->>S: Confirm 2 of 3 frames above threshold
    R->>S: Copy history into event prefix
    S->>S: Append 24576 samples including trigger frame
    S->>L: begin + 128 chunks + end/CRC
    Note over M,S: Continue acquisition and gate while sending
    L->>L: Verify exact PCM; queue observation persistence
```

A trigger timestamp refers to the **start of the confirmation frame**, not the
first threshold crossing and not an absolute UTC clock. Its index in the WAV is
8192. UTC in metadata is Linux receive time. ADC/I2S latency is not measured.

## Gate

The detector processes 256 samples (16 ms). Energy is
`mean(x*x) - mean(x)^2`, with a nonnegative clamp for rounding. Its square root
is RMS in signed PCM16 units.

1. Settle for 2 seconds while discarding decisions.
2. Calibrate background power for 3 seconds. Keep this interval representative.
3. Open at `max(96, 2 * background_RMS)`, with two votes in three frames.
4. Freeze background adaptation during candidates and active events.
5. Close after 300 ms below `max(96 / sqrt(2), sqrt(2) * background_RMS)`.
6. Wait 1 second before rearming.

The quiet-background power estimate uses EMA alpha 0.0032 per frame (roughly a
5-second time constant). These values are engineering defaults, not a validated
wildlife operating point. Long-term noise jumps can keep the detector active;
restart calibration after a deliberate environment change in this milestone.
Wind rejection and per-band thresholds remain future work.

## Acquisition and memory

The loader provides six 2048-frame DMA slabs. Each stereo bus frame occupies
8 bytes: 98,304 bytes total. At 16 kHz a slab spans 128 ms. The gate processes
16 ms subframes once the DMA block is available, so 16 ms is **not** a promise of
end-to-end trigger latency.

The mono history uses 16,384 bytes; the frozen event uses 65,536 bytes.
Do not allocate a second event casually: the Arduino sketch SRAM budget is
262,144 bytes, and Bridge, stack and runtime need headroom. See the build result
in the validation record.

## Backpressure and errors

There is one event slot on the MCU. A new confirmed trigger while this slot is
occupied increments `skippedEvents`; it does not overwrite the event. Sustained
sound produces one event until the gate releases. This first version is not a
lossless recorder of continuous vocalization.

Linux holds one in-flight event and a persistence queue of two. Incomplete,
expired or corrupt events are rejected. Queue saturation and storage failures
are logged. There is no retransmission or delivery acknowledgement yet.

At most one notification is attempted per 100 ms, with no blocking sleep between
transmissions; intervening loops drain the DMA backlog. An event needs at least
13 seconds to transfer. Actual Bridge throughput and worst blocking time still
need measurement. Capture errors stop event production and
emit an error every two seconds; automatic I2S recovery is intentionally not
claimed.

## Energy and inference

The persistence worker has a host-tested BirdNET v2.4 adapter. It loads the official
FP32 TFLite model through LiteRT and analyzes only finalized, checksum-verified WAVs.
The evidence JSON records the decision, score, threshold, five ranked candidates,
model identity and input conversion facts. BirdNET runs at 48 kHz in three-second
windows; the current 16 kHz, 2.048-second event is resampled and zero-padded by the
runtime. Resampling cannot restore content above the capture Nyquist limit.

BirdNET has no human or generic background output. The adapter requests candidates
at zero internal threshold, then reports `unknown` unless the best score reaches the
configured 0.25 threshold. Geographic filtering is initially disabled and recorded
as null rather than inferred from an unstated location. Model loading is amortized
between events while the application is awake.

BirdNET uses spawned worker processes. Runtime construction in `main.py` is guarded
by the primary-process entrypoint so a worker importing `__mp_main__` cannot create
a second App Lab instance or write to the observation store during inference.

Inference failure is fail-open for evidence retention: the WAV remains and the JSON
records an explicit `classification_error`. The current development variant excludes
camera and servo hardware. Its very-low-power objective must be validated at board
level; gating a model does not by itself
establish very low idle power or deep MPU shutdown.

## Experimental Linux suspend-to-idle — disabled

The research implementation uses kernel `freeze` (suspend-to-idle), not `deep`
suspend and not a Linux reboot. It is split deliberately across trust domains:

1. The Python coordinator waits until there is no partial event, queued persistence
   work or active writer.
2. It calls the MCU `sylva_power_save` provider. The MCU accepts only while healthy,
   listening and not transferring an event, then suppresses periodic telemetry.
3. Python atomically creates one `suspend.request`. Without the root-installed
   `helper.ready` marker it never arms or requests suspend.
4. A systemd path unit starts the fixed root helper. The helper accepts only
   `freeze`, enables `ttyHS1` as a wake source, syncs storage and writes the kernel
   power state.
5. A confirmed acoustic event makes the MCU emit one `sylva_wake` UART notification,
   wait up to 1.5 seconds for Linux, then transfer the immutable buffered event.
6. After resume the helper publishes a result and Python disarms the MCU. Failure or
   timeout also disarms it so normal telemetry and transfer resume.

The device experiment confirmed entry into and exit from suspend-to-idle, but did not
produce a repeatable, attributable acoustic UART wake. Other enabled wake sources
caused resumes, and controlled recovery needed the power control or a power cycle.
The release therefore defaults to `disabled`, omits the helper readiness marker and
keeps Linux awake. This section documents research code and the failed acceptance
boundary; it is not the supported operating architecture.

## Offline observation and storage policy

`ObservationStore` accounts only final `event-*.wav` files in its configured audio
budget. Before admitting a new WAV it preserves both a record reserve and a system
reserve. In `delete_oldest` mode it may remove the oldest unprotected WAV only when
that WAV has a readable observation sidecar. The JSON is updated before and after
deletion; the record and original audio hash remain. Protected WAVs, sidecars,
unrelated files and invalid records are never retention candidates.

If room cannot be made, the worker creates a bounded temporary WAV, runs BirdNET,
deletes the temporary file and atomically publishes a `never_retained` JSON record.
Thus classification no longer depends on a successful permanent WAV write. If even
the system reserve would be crossed, publication fails loudly instead of silently
claiming persistence.

At startup, recovery completes valid pending JSON publication, removes incomplete
temporary WAVs, finishes already-authorized retention, marks missing/corrupt audio,
and inventories orphan WAVs without deleting them. A hidden state file preserves
boot count, counters and the last observed wall-clock anchor.

Every new event carries UTC, clock source, declared quality/uncertainty, Linux boot
ID, monotonic time and trigger sample. The default quality is deliberately
`unverified`; a backward wall-clock jump is marked `regressed`. This implementation
is host-tested and has passed an isolated device smoke test. Controlled write
interruption, physical reboot and endurance acceptance remain.
See [offline operation](OFFLINE_OPERATION.md) for configuration and evidence limits.
