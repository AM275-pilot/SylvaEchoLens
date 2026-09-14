# Build, deploy and recover

## Required baseline

The active sketch needs the custom ArduinoCore-zephyr **0.90.0** / Zephyr **4.2**
loader created during bring-up. It enables I2S, SAI1_A on PB9/PB10/PC1, PLL2 and
word-width GPDMA. Patches are versioned under `firmware/patches/`.

Known loader SHA-256 (BIN):
`43C4DA2D3F3E6329EB603EBE6922D2DFE8331C9AA50CCC2FC3D7654CA23B39DB`.

This loader is specialized for 24/32-bit SAI slots. Its DMA patch is not a general
replacement for 16-bit SAI support. Rebuilding with another core/version requires
revalidating the driver and recording a new hash.

## Local toolchain layout

Paths are resolved from the repository root unless an explicit toolchain directory
is supplied. See [repository identity](REPOSITORY.md).

- CLI: `%LOCALAPPDATA%/AppLab/resources/arduino/arduino-cli/arduino-cli.exe`
- Config: `.codex-build/arduino-cli-custom.yaml`
- Custom core: `.codex-build/arduino-user/hardware/arduino-git/zephyr`
- Libraries: `.codex-build/arduino-user/libraries`
- Upload port: discover it for the connected board and pass it explicitly.

Generated dependencies are not included in Git. A clean checkout requires
reconstructing the custom toolchain before a device build. This is a documented
reproducibility dependency, not a one-click stock-App-Lab installation.

## Build

```powershell
$toolchain = 'C:/path/to/verified-custom-toolchain'
./scripts/build-audio-gate.ps1 -ToolchainRoot $toolchain
./scripts/build-audio-gate.ps1 -ToolchainRoot $toolchain -Upload -Port <current-port>
```

The helper checks the known loader hash, stages only source files (excluding the
stock `sketch.yaml` profile), and compiles against `arduino-git:zephyr:unoq`.
Output goes to this project's `.codex-build/event-gate-build/`. The unsafe stock
profile was not copied into this project. On a workstation where the custom
toolchain is installed in this project's `.codex-build/`, omit `-ToolchainRoot`.
An explicit `-Config` must select the same custom core as `-ToolchainRoot`.

## Linux deployment

Use ADB from the Arduino installation. Target app:
`/home/arduino/ArduinoApps/audio-test`.

1. Preserve the existing app Python folder and known sketch build.
2. Stop the app with `arduino-app-cli app stop /home/arduino/ArduinoApps/audio-test`.
3. Push `main.py`, `event_receiver.py`, `classification.py`, `offline_store.py`,
   `power_manager.py` and `requirements.txt` into its `python/` directory, plus the
   matching `app.yaml`.
4. Start with `arduino-app-cli app start /home/arduino/ArduinoApps/audio-test`.
5. Upload the matching sketch after the receiver is listening.
6. Inspect `arduino-app-cli app logs /home/arduino/ArduinoApps/audio-test --tail 40`.

Inside the container, events default to `/app/events/`, backed by the app
directory. A complete event produces a JSON record and either a retained WAV or an
explicit `never_retained` audio status. This version does not update the old
`test.wav`: it remains historical and must not be mistaken for a fresh event.

Offline storage configuration uses integer byte counts:

| Environment variable | Default | Meaning |
|---|---:|---|
| `SYLVA_AUDIO_BUDGET_BYTES` | 536870912 | Maximum bytes in final owned event WAVs |
| `SYLVA_RECORD_RESERVE_BYTES` | 16777216 | Space kept away from audio for JSON records |
| `SYLVA_SYSTEM_RESERVE_BYTES` | 134217728 | Space not consumed by this application |
| `SYLVA_RETENTION` | `delete_oldest` | `delete_oldest` or `recognition_only` |
| `SYLVA_TEMP_DIR` | `/tmp/sylva-audio` | Bounded temporary inference-audio directory |
| `SYLVA_LINUX_SUSPEND` | `disabled` | Release default; `freeze` is an unsupported experiment |
| `SYLVA_SUSPEND_IDLE_SECONDS` | `60` | Continuous idle time before requesting suspend |
| `SYLVA_SUSPEND_REQUEST_TIMEOUT_SECONDS` | `120` | Maximum wait for a helper result before disarming |
| `SYLVA_POWER_DIR` | `/app/power` | Request/result directory shared with the host helper |

Retention considers only `event-*.wav` under the event directory with a readable
sidecar. Set `audio.protected` to `true` in a record to exclude its WAV. Never point
`SYLVA_EVENT_DIR` at a directory containing unrelated event-named data.

Time provenance defaults to `SYLVA_TIME_QUALITY=unverified`. Set
`SYLVA_TIME_SOURCE`, `SYLVA_TIME_QUALITY` (`synchronized`, `rtc`, or `unverified`)
and `SYLVA_TIME_UNCERTAINTY_SECONDS` only from an established clock procedure.
A backward jump is always downgraded to `regressed`.

## Experimental suspend-to-idle — not for release deployment

Acoustic UART wake did not pass physical-device acceptance. The release keeps
`SYLVA_LINUX_SUSPEND=disabled` and no `helper.ready` marker. The commands below are
retained only to reproduce or remove the recorded experiment; do not activate them
for unattended operation.

Deploy the matching Python application and MCU sketch first. Then stage the fixed
root helper from the repository:

```powershell
./scripts/install-linux-suspend.ps1
```

The script uses passwordless `sudo` when configured. Otherwise it prints the exact
interactive ADB command; enter the board password directly in that terminal. It
installs one helper and two systemd units, then creates `power/helper.ready`. The
application will not request suspend without this marker.

The helper accepts only `freeze`, enables wake on the Bridge UART `ttyHS1`, calls
`sync`, enters suspend-to-idle and publishes `suspend.result` after resume. It does
not grant the container `sudo`, shell access or arbitrary command execution.

Before unattended use, perform the suspend acceptance sequence in
[validation](VALIDATION.md). Keep a power key or controlled power cycle available
during the first wake experiment. Remove the feature with:

```text
adb shell -t 'sudo /home/arduino/sylva-power-install/uninstall-sylva-linux-suspend.sh'
```

Removal disables the path unit and deletes the readiness marker, so the application
continues in awake mode. To disable suspend without uninstalling the helper, set
`SYLVA_LINUX_SUSPEND=disabled` and redeploy the application.

## Recovery

On each application start the store reconciles pending writes and records a summary
in `.sylva-state.json` and the application log. It removes only incomplete hidden
temporary WAVs, completes valid pending JSON publication and previously authorized
retention, marks missing or corrupt audio, and creates sidecars for orphan WAVs.
Inspect `recovery={...}` in the startup log after an unexpected reboot.

Deployment snapshots are created under `.codex-build/rollback/` before board files
are replaced. Restore one complete matching snapshot rather than mixing receiver
files from different revisions.

The official loader backup is
`.codex-build/rollback/official-zephyr-0.90.0/`; its BIN hash is
`5C10F9BDEBDD2F9A825C1115BB9D493EB2F777DC84B4C9B79F5D5C99CFE421CF`.
A full official-loader restore also requires a compatible stock-core sketch;
the new I2S sketch cannot run with I2S removed.

Use only the guarded scripts in this repository. No new loader flash is required
for the event gate if the documented word-DMA loader remains installed.

## Tuning

Defaults live in `GateConfig` in `acoustic_gate.h`; remote tuning is not
implemented. Log a baseline before adjusting minimum RMS, ratios or confirmation.
A restart recalibrates after two seconds of settling and three seconds of
background measurement. Persistent wind/noise changes require a new calibration
in this first version.
