# Audio protocol v1

Protocol and persisted-evidence contract reviewed on September 14, 2026.

Mono, configured 16,000 samples/second, signed PCM16. Event length: 32,768 samples
(2.048 seconds). Pre-event history: 8,192 samples (0.512 seconds). Each chunk:
256 samples; 128 chunks per event.

## One value, three representations

| Layer | Example +4660 | Example -1 |
|---|---|---|
| Native MCU int16 | `0x1234` | `0xffff` |
| Bridge textual hex | `1234` | `ffff` |
| WAV data bytes | `34 12` | `ff ff` |

The MCU extracts the upper 16 bits of the MSB-aligned left I2S slot without a byte
swap. Python decodes numeric big-endian hex and packs little-endian PCM. This
fixes the prior receiver's direct `bytes.fromhex` write and removes the firmware
workaround. This is a representation change, not an audio filter.

## Messages

| Callback | Positional arguments |
|---|---|
| `sylva_boot` | protocol version, ready/error, capture errno |
| `sylva_begin` | event ID, sample rate, sample count, pre-count, trigger sample position, trigger RMS, noise RMS |
| `sylva_chunk` | event ID, zero-based chunk index, 1024 hexadecimal characters |
| `sylva_end` | event ID, chunk count, eight-character CRC32 hex |
| `sylva_level` | gate state, RMS, floor RMS, open threshold, close threshold, skipped triggers |
| `sylva_error` | negative capture errno |

CRC-32/ISO-HDLC covers the **little-endian PCM bytes**, not the ASCII hex or WAV
header. It must agree between MCU and Python. SHA-256 subsequently identifies the
complete WAV artifact.

## Receiver contract

Accept only the documented geometry. Chunks may arrive out of order. Identical
duplicates are harmless; conflicting duplicates abort assembly. Reject unknown
IDs, out-of-range indices, invalid encodings, missing chunks, checksum mismatch
and receive timeouts exceeding 60 seconds. A later valid begin supersedes an
unfinished older event. Never insert fabricated silence.

A receiver-generated session UUID separates files across app starts and received
MCU boot notifications. An MCU restart whose boot notification is lost requires
restarting the receiver if the event IDs move backwards.

## Evidence JSON

Each event has a same-basename JSON sidecar with protocol version, session,
event ID, rate, channels, pre-event count, sample-relative trigger position,
trigger/floor RMS, UTC receive time, transfer duration, CRC32, WAV SHA-256,
DC mean, DC-removed RMS, peak and clipped-sample count. It also records a device
instance, boot counter, Linux boot ID, monotonic receive time, wall-clock source,
declared clock quality/uncertainty and per-event processing durations.

The `audio` object makes evidence availability explicit: retained audio includes
its protected state; recognition-only output is `never_retained`; quota eviction is
`removed_by_retention`; restart reconciliation can mark missing, corrupt or recovered
audio. Records retain the original hash and a reason where available.

`classification` is null
until a model actually runs. A completed inference records `label`, normalized
`score` in 0..1, `accepted`, decision `threshold`, model identity and version,
backend, ranked candidates, input/model geometry, resampling/padding flags and the
geographic-filter state. An inference exception preserves the checked WAV, leaves `classification`
null and adds `classification_error`; a model failure must not erase the observation.

The WAV is atomically renamed before the JSON is published. They are not a
filesystem-wide atomic pair; consumers should discover finalized JSON files,
then inspect `audio.status` and verify the referenced same-basename WAV only when
the record says it is present. Recognition-only records intentionally have no WAV.
