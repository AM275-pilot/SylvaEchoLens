# Repository identity and provenance

## Authoritative project

- Remote: <https://github.com/AM275-pilot/SylvaEchoLens.git>
- Active application: `app_audio_test/`
- Board application: `/home/arduino/ArduinoApps/audio-test`

Before making changes or deploying, verify the checkout instead of relying on a
workstation-specific path:

```powershell
git rev-parse --show-toplevel
git remote get-url origin
git status --short
```

The deployment helper independently checks that it is inside this repository and
that the origin matches the authoritative remote. Local edits are not a commit or
a GitHub push.

## Local build assets and evidence

Generated toolchains, build output, rollback snapshots and device-test evidence are
not committed. Keep them under the ignored `.codex-build/` directory. The guarded
build helper accepts `-ToolchainRoot` when the verified custom toolchain is stored
elsewhere; that location is an operator input, not part of the project identity.

Raw WAV recordings, JSON sidecars and generated waveform cards also remain local.
Record their SHA-256 and acquisition metadata in the lab notebook when they support
a validation claim.

## Portability rules

Do not encode a local checkout path, ADB serial or upload port in source or
documentation. Discover the connected device and pass the current upload port
explicitly. The fixed board application path is intentional because it is the
deployed App Lab application identity.

The custom loader hash and recovery procedure are documented in the
[runbook](RUNBOOK.md). A clean checkout still needs that verified generated
toolchain before a device firmware build; the stock App Lab core is not a substitute.
