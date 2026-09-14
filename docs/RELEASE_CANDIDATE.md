# Release candidate path

Gate status reviewed on September 14, 2026. This checklist should be read together
with the [current capability ledger](CURRENT_STATUS.md).

This is the shortest honest path from the current prototype to a published or field
release candidate. It keeps technical plumbing distinct from wildlife-model claims.

## Current gate

| Segment | Status | Evidence needed to advance |
|---|---|---|
| Microphone → event gate → checked WAV/JSON | Device-tested | Repeat after final deployment |
| Checked WAV → BirdNET v2.4 metadata | Device-tested; two audited assiolo replay events accepted at 0.996/0.997 | Complete replay provenance and negative controls |
| Prediction quality | Not established | Versioned labeled set, confusion matrix and unknown policy |
| LED level display | Fix uploaded | Human visual board check |
| Offline persistence | Deployed; isolated quota/retention/restart and networkless compact inference smoke-tested | Power-cut and endurance acceptance |
| Linux suspend-to-idle and STM32 event wake | Excluded from release; acoustic UART wake failed device acceptance | Revisit only with a separately verified hardware wake path |
| Publication package | Documentation structure assembled | Final photos, screenshots, demo video and labeled evidence |

Latest host recheck: 38 Python tests and the sanitized C++17 acoustic pipeline test
pass. This does not advance the device-only or field-evidence gates in the table.

The first release model is BirdNET v2.4 FP32 via LiteRT. Remaining product decisions
are the deployment location/date filter, representative evaluation recordings and
the operating threshold after validation. Unrelated or non-wildlife model output
must not be presented as wildlife results.

## Candidate sequence

1. Confirm the pinned `birdnet==1.1.1` environment and cached official v2.4 FP32
   model still match the hashes recorded in the model card.
2. Repeat the documented 16 kHz/2.048 s to 48 kHz/3 s resample-and-pad path after
   the final deployment.
3. Run a labeled single-species replay plus speech/quiet negative controls; preserve
   all five candidates even when the accepted decision is `unknown`.
4. Run host tests and the custom-loader sketch build. Preserve rollback sources.
5. Deploy the Linux receiver with `scripts/deploy-audio-app.ps1`; it snapshots the
   current board app before stopping or replacing it. Upload the sketch separately
   through `scripts/build-audio-gate.ps1 -Upload` only after verifying the loader hash.
6. Replay held-out labeled samples at several levels/distances. Audit each WAV/JSON,
   verify accepted/unknown decisions and record false positives in quiet/background.
7. Repeat the isolated storage smoke test with controlled interruption during each
   write phase and a real Linux/board reboot. Do not claim power-cut recovery or
   autonomy until the separate acceptance tests pass.
8. Measure the supported awake configuration before selecting a battery or making an
   autonomy claim. Keep the failed suspend experiment outside the release path.
9. Complete the [project documentation evidence plan](PROJECT_DOCUMENTATION.md#publication-evidence-plan):
   reproducible demo, model card, evaluation table, wiring images, architecture,
   exact hashes, known failures and limitations.

## Release stop conditions

Stop rather than publish a wildlife claim if model identity is `unversioned`, the
evaluation audio overlaps training data, only a replay used for training succeeds,
unknown/background behavior is absent, inference needs a cloud connection, or the
final board run has missing/corrupt event evidence.
