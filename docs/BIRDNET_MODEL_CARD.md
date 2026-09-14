# BirdNET v2.4 integration card

## Identity and license

- Python package: `birdnet==1.1.1`, with transitive versions locked in
  `app_audio_test/python/requirements.txt`.
- Acoustic model: `BirdNET_GLOBAL_6K_V2.4`, official FP32 TFLite distribution.
- Runtime: LiteRT (`ai-edge-litert==2.2.0`) on the UNO Q Linux MPU, CPU only.
- Model SHA-256 on the verified board:
  `55f3e4055b1a13bfa9a2452731d0d34f6a02d6b775a334362665892794165e4c`.
- English label count: 6,522. `Otus scops_Eurasian Scops-Owl` is entry 4,155.
- BirdNET code is MIT licensed. BirdNET model weights are licensed
  [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/); attribution,
  non-commercial use and share-alike obligations constrain redistribution and use.
- Upstream package: [birdnet-team/birdnet](https://github.com/birdnet-team/birdnet).
  Model archive: [BirdNET v2.4 on Zenodo](https://zenodo.org/records/15050749).

The model and generated environments are deliberately not committed. A deployment
downloads the official archive once and persists it below the app's ignored
`.cache/birdnet` directory.

## Input and decision contract

BirdNET v2.4 expects a mono 48 kHz, three-second window. The current instrument
produces mono 16 kHz, 2.048-second checked WAVs. Upstream BirdNET resamples each
event to 48 kHz and appends silence to three seconds. The JSON records both source
and model geometry plus `resampled` and `zero_padded`. This adaptation does not
recover frequencies above 8 kHz and is a known recall limitation.

The adapter requests five candidates at BirdNET threshold zero. It accepts the best
candidate only at or above 0.25; otherwise the public decision is `unknown` while
the ranked candidates remain available for audit. BirdNET includes some non-bird
classes, including human non-vocal sounds, engines and power tools. Geographic and
seasonal filtering is not active because a deployment location has not been fixed.

## Verification status

On 2026-09-09 the UNO Q ran the model against a previously stored, unlabeled event.
The best candidate scored 0.0121617 and the adapter correctly emitted `unknown`.
The same inference succeeded in an ephemeral Docker container with networking set
to `none`, using only the persisted environment, model and event. This verifies
local execution, not species accuracy.

A defensible recognition result still requires a newly captured, labeled playback
with source URL/title, expected species, playback distance and volume noted. Follow
with speech and quiet controls. Do not treat the old unlabeled event as wildlife
evidence or tune the threshold from a single playback.
