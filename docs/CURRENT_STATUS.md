# Current implementation status

Documentation snapshot: September 14, 2026, reconciled against `develop` at
`92dd668` and the source tree described below. This page is the shortest current
status; dated validation and laboratory records remain the evidence of record.

## Latest integrated developments

- BirdNET v2.4 FP32 runs locally on the UNO Q Linux processor through LiteRT. The
  adapter retains five ranked candidates and publishes `unknown` below the 0.25
  threshold. A cached, network-disabled rerun succeeded. An announced assiolo
  replay then produced two audited `Otus scops` results at 0.996 and 0.997.
- The observation store now has separate audio, record and system-space boundaries.
  It can retain audio, remove only indexed and unprotected app WAVs, or classify
  through bounded temporary audio and publish a recognition-only record.
- Atomic JSON/state publication, startup reconciliation, orphan/corrupt/missing
  audio inventory and explicit clock quality make restart behavior auditable.
- Deployment snapshots the existing board application before replacement. Firmware
  builds remain guarded by the verified custom-loader SHA-256.
- A Linux suspend-to-idle experiment reached kernel `s2idle`, but acoustic UART wake
  failed device acceptance. The release default is `disabled`; Linux stays awake.

## Capability ledger

| Capability | Implemented | Host-tested | Device-tested | Remaining acceptance |
|---|:---:|:---:|:---:|---|
| One-INMP441 SAI1/DMA capture | Yes | Partial algorithm coverage | Yes | Calibrated bandwidth/sensitivity |
| Adaptive event gate and 0.512 s pre-event history | Yes | Yes | State transitions and audited events | Weak/short-call recall and wind backgrounds |
| Checked 2.048 s PCM transfer and WAV/JSON evidence | Yes | Yes | Yes | Ten-minute and dense-event acceptance |
| BirdNET v2.4 offline inference | Yes | Yes | Yes, including networkless inference and two audited assiolo-replay results | Complete replay provenance, negative controls and representative set |
| Bounded retention and recognition-only fallback | Yes | Yes | Isolated smoke test | Controlled write interruption, real reboot and endurance |
| Timestamp quality and restart reconciliation | Yes | Yes | Clean app restart and orphan recovery | Offline clock procedure and power-cut matrix |
| Guarded deploy and rollback snapshot | Yes | PowerShell parsed | Used on device | Repeat for final candidate |
| LED level display grayscale correction | Yes | Compiles | Firmware uploaded | Human visual confirmation |
| Linux suspend-to-idle acoustic wake | Research code only | Guards tested | Rejected | New independently verified wake path |
| Measured autonomy | No | Calculator only | No | Whole-board power and event-rate measurements |
| Solar/battery field supply and weather-resistant enclosure | Planned | No | No | Power sizing, protected charging, ingress/condensation and acoustic-port tests |
| Dashboard, remote threshold control, direction finding | No | No | No | Future implementation and hardware where applicable |

## Current verification baseline

- 38 Python unit tests pass on the host, including the BirdNET multiprocessing
  entrypoint regression test.
- The portable C++17 test passes with address and undefined-behavior sanitizers;
  the shared cross-language CRC remains `170aea81`.
- The latest documented firmware build used 84,956 bytes of flash and 213,558 bytes
  of static RAM, leaving 48,586 bytes. This is a recorded September 13 device-build
  result, not a fresh build from this documentation update.
- Board capture, checked transfer and BirdNET execution are demonstrated. Species
  accuracy is not established by the two positive replay events alone. Calibrated
  acoustic fidelity, physical power-cut recovery, endurance and battery autonomy
  are also not demonstrated.

## Next release gates

1. Complete source/license/distance/level provenance for the assiolo replay or
   repeat it from a fully versioned source, plus quiet, speech and representative
   background controls.
2. Audit every corresponding WAV/JSON pair and record accepted, unknown, missed and
   false-positive outcomes without tuning from one sample.
3. Exercise every persistence interruption point in isolated storage, followed by
   application, Linux and whole-board restarts and an endurance run.
4. Measure the supported awake configuration before selecting a battery or making
   any energy/autonomy claim.
5. Complete the physical wiring photographs, visual LED check and demonstration
   video. Then prototype the measured solar/battery power path and protected
   microphone enclosure. The dashboard remains a later software milestone.

See [validation](VALIDATION.md), [release candidate path](RELEASE_CANDIDATE.md),
[offline operation](OFFLINE_OPERATION.md) and the [lab notebook](LAB_NOTEBOOK.md)
for procedures, detailed evidence and failures.
