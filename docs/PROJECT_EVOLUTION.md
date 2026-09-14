# Sylva EchoLens: Listen First, Keep the Evidence, Understand It Locally

Sylva EchoLens is a compact edge AI acoustic observer built around Arduino UNO Q.
It listens continuously through one digital microphone, selects meaningful sound
events on the real-time microcontroller, verifies them across the processor boundary
and runs wildlife classification locally. The result is an observation that remains
useful even when the device has no Internet connection.

The current model is the power-saving member of a broader monitoring platform. Its
purpose is not to carry every possible sensor. It concentrates hardware, storage and
computation on the part that must never stop: listening for an event and preserving
enough evidence to understand it later.

## From a broad idea to a focused instrument

The project began as a larger wildlife-monitoring concept. Acoustic localization,
visual confirmation, environmental sensors, pan-and-tilt movement and a dashboard
were all considered. That direction was attractive, but building everything at once
would have hidden the most important question: could the system acquire trustworthy
audio and turn it into a traceable local observation?

The physical prototype also established a firm constraint. It has one INMP441
microphone. The two slots visible in its Inter-IC Sound (I2S) stream are framing, not
two independent sensors. A single microphone cannot provide honest direction
finding, so localization and camera aiming moved out of the first product variant.

That decision made the project smaller, but stronger. Sylva EchoLens became an
acoustic-first instrument: one microphone, no camera, no servos and no continuous
visual workload.

*[Suggested visual: the complete compact prototype, photographed from above with the
UNO Q and microphone clearly visible.]*

## Building a trustworthy audio path

The first recordings appeared to contain data, but a nonzero waveform was not enough
to prove that the samples meant the same thing on both processors. Investigation
revealed a byte-order inconsistency between the microcontroller and Linux sides.

The contract was corrected at its source. The STM32 now keeps native signed pulse-code
modulation samples. The Bridge transports numeric sample values, and Linux alone
serializes the little-endian WAV representation. A cyclic redundancy check verifies
the complete event in transit, while SHA-256 identifies the final stored audio.

This change is central to the project. A classifier result is only as trustworthy as
the signal that produced it. Sylva EchoLens therefore rejects incomplete or corrupt
events instead of filling missing data with invented silence.

The verified capture is mono, 16 kHz and 16-bit. Each event contains 32,768 samples,
or 2.048 seconds of sound. The first 8,192 samples preserve 0.512 seconds from before
the trigger confirmation, so the saved recording includes the beginning of a call
rather than starting after it has already been detected.

*[Suggested visual: a waveform evidence card with the pre-event region shaded and
the confirmation boundary marked.]*

## Turning continuous audio into bounded events

Periodic recording was useful during bring-up, but it was not the right behavior for
an unattended observer. The firmware therefore evolved into an adaptive acoustic
gate running on the STM32.

The gate removes direct-current offset, estimates recent background energy and opens
only after repeated evidence above its threshold. Hysteresis prevents rapid switching
near the boundary, while cooldown avoids immediately retriggering on the same sound.
A rolling buffer is always maintained so pre-event audio is available when a trigger
is confirmed.

This detector identifies acoustic contrast, not a species. Wind, speech, machinery
and other sounds can trigger it. That distinction is deliberate: the STM32 performs
the deterministic, low-complexity task of deciding what is worth keeping; wildlife
interpretation happens later on Linux.

The microcontroller has one immutable event slot. It never overwrites an event being
transferred. Closely spaced triggers may therefore be counted as skipped, making
throughput limits visible rather than silently corrupting evidence.

*[Suggested visual: App Lab logs showing settling, calibration, listening and a
confirmed event.]*

## Local wildlife inference

Once the audio path was coherent, the project added local classification. The current
model is the official BirdNET v2.4 FP32 model executed on the UNO Q Linux processor
through LiteRT.

The recorded event is shorter and uses a lower sample rate than BirdNET's native
input. The adapter resamples it from 16 kHz to 48 kHz and pads it to three seconds.
This makes the geometry compatible, but does not recreate frequencies above the
original 8 kHz Nyquist limit. That capture boundary remains part of the evidence.

BirdNET always ranks species, including for speech, machinery or unfamiliar
backgrounds. Sylva EchoLens does not present every ranking as a detection. It keeps
the five best candidates and records `unknown` when the highest score is below the
configured acceptance threshold. Every result includes the model identity, version,
score, threshold, backend and input-conversion facts.

The model has run successfully on the physical UNO Q and inside its container with
networking disabled, using pre-provisioned dependencies and cached model assets.
This proves local offline execution. It does not yet establish species-recognition
accuracy, which requires a versioned labeled replay set and negative controls.

*[Suggested visual: one observation record showing BirdNET candidates, score,
threshold and an honest `unknown` decision.]*

## Offline means more than “no network”

An offline field unit must also handle finite storage, interrupted writes, restarts
and an uncertain clock. These conditions are now explicit parts of the application
rather than assumptions left to the operator.

Storage is divided into three boundaries:

- an audio budget for retained event WAV files;
- a reserve for compact observation records;
- a system reserve that the application must not consume.

While the audio budget permits, an observation retains both its JSON record and its
WAV evidence. Under pressure, the configured retention policy may remove only the
application's own indexed, unprotected and valid WAV files. Their JSON records,
original hashes and removal reasons remain.

If permanent audio cannot be admitted, BirdNET processes a bounded temporary WAV
that is deleted after inference. The durable observation is then marked
`never_retained`. This recognition-only mode extends useful storage life, but the
trade-off is visible: without audio, the observation cannot later be listened to or
reclassified.

Writes use temporary files and atomic publication. At startup, the application
reconciles interrupted JSON publication, incomplete temporary audio, previously
authorized retention, missing or corrupt WAVs and orphan recordings. Questionable
evidence is described and preserved where possible; it is not silently repaired.

Every new observation also records the wall-clock source and declared quality,
Linux boot identity, monotonic time and the trigger position from the MCU. Time is
`unverified` by default, and a backward clock movement relative to the persisted
anchor is marked `regressed`. The software does not assume that a disconnected
device always knows accurate UTC.

*[Suggested visual: two compact records side by side—one with retained audio and one
in recognition-only mode.]*

## Why this is the power-saving variant

The current saving is architectural and already active.

The STM32 performs continuous capture and the lightweight gate. The heavier BirdNET
workload runs only for a complete event worth analyzing. The compact node carries no
camera, lighting, servo or environmental-sensor load, and bounded retention prevents
the audio archive from growing without control.

This is a clear power-saving position within the wider Sylva EchoLens family: keep
the continuous task small, activate expensive computation only on demand and avoid
peripherals that are not required by the acoustic mission.

Linux remains awake in the release configuration. Whole-board consumption and
battery autonomy have not yet been measured, so no runtime claim is derived from
software behavior alone.

## A power experiment that changed the direction

A suspend-to-idle prototype was developed to test whether Linux could sleep while
the STM32 continued listening. The implementation included a restricted host helper,
an explicit MCU arm/disarm handshake, suppressed routine telemetry and a buffered
event intended to wake Linux over the Bridge UART before transfer.

The test produced useful evidence. The kernel entered and exited suspend-to-idle,
and the application and MCU handshake worked while awake. On the physical board,
however, an acoustic event did not provide a repeatable, observable UART wake. Some
resumes were caused by other enabled sources, and controlled recovery required the
power control or a power cycle.

That behavior is not acceptable for an unattended observer, so automatic Linux
suspend is disabled and excluded from the release boundary. The failed acceptance
test is still valuable: it shows that a writable UART wake setting does not by itself
prove end-to-end wake capability.

Future low-power work should begin with measured board consumption and a verified
hardware wake path. A dedicated wake line, a different Linux power state or a power
controller may be more appropriate than relying on the current Bridge UART.

## What is working now

The current physical prototype and matched software provide:

- continuous mono acquisition through the verified custom I2S loader;
- adaptive event detection with pre-trigger audio;
- fixed event geometry and explicit busy-event counting;
- cross-processor geometry and checksum validation;
- local BirdNET v2.4 inference with ranked candidates and an `unknown` policy;
- offline audio quotas, protected retention and recognition-only fallback;
- atomic observation records and startup reconciliation;
- explicit timestamp quality and ordering evidence;
- guarded build, deployment and rollback procedures.

Board events have passed geometry, cyclic redundancy check and file-hash audits.
BirdNET has completed inference without network access. Isolated device tests have
exercised audio quota transitions, retention, recognition-only persistence, orphan
reconciliation and a clean application restart.

Automated host verification currently contains 37 passing Python tests, together
with portable C++ checks for the acoustic gate, event buffer and sample contract.
These tests support the implementation but do not replace field evidence.

## Current limits

The project keeps its release claims deliberately bounded:

- the detector selects acoustic contrast and may react to non-wildlife sound;
- capture at 16 kHz cannot represent frequencies above 8 kHz;
- one event transfer takes roughly thirteen seconds and dense activity can produce
  visible skipped-event counts;
- thresholds are engineering defaults, not calibrated sound-pressure values;
- BirdNET accuracy and the acceptance threshold are not yet validated on a
  representative dataset for this exact device;
- recognition-only records cannot be re-audited without their original audio;
- full power-cut recovery and long-duration endurance still need controlled trials;
- automatic Linux suspend is disabled because acoustic wake did not pass device
  acceptance;
- battery duration and solar sizing require measured whole-board energy.

These boundaries do not weaken the prototype. They define exactly what the current
evidence proves and prevent an experimental result from becoming a product claim.

## Where the project can go next

The strongest next step is a repeatable labeled evaluation. A versioned set should
combine target bird calls, quiet, speech, machinery and representative outdoor
backgrounds. Source, license, playback level, speaker distance and expected outcome
must accompany every run, including false triggers, missed events and `unknown`
results.

Resilience testing should then interrupt each persistence phase in isolated scratch
storage and exercise application, Linux and whole-board restarts. A sustained event
and storage-pressure run will show whether the current bounded design behaves well
over time.

Power work begins with measurement: awake baseline, continuous acquisition, event
transfer, BirdNET inference and storage writes. Those values, combined with a measured
event rate, can drive battery and photovoltaic sizing. A future sleep design should
return only after its wake source is demonstrated independently.

The existing observation schema is also ready to support a user-facing wildlife
timeline. A dashboard can present candidates, retained-audio status, timestamp
quality, storage health and export without changing the core evidence pipeline.

Richer platform variants may later add synchronized microphones, direction
estimation, camera confirmation, calibrated environmental sensing or multiple nodes.
Each addition changes power, privacy, storage and validation requirements; none is
presented as a hidden capability of the current single-microphone unit.

## The current release position

Sylva EchoLens has evolved from a feature-rich wildlife-monitoring proposal into a
focused and auditable acoustic edge instrument. The compact prototype listens,
selects bounded events, preserves what happened before the trigger, verifies samples
across processors, classifies locally and retains useful observation records under
offline storage pressure.

Its most important result is not a single species label. It is the evidence chain:
from microphone sample, to MCU decision, to checked event, to local model output, to
an observation that states both what is known and what remains uncertain.

That makes the current acoustic-only model a coherent power-saving release candidate
and a reliable foundation for the larger Sylva EchoLens platform.

---

## Publication media checklist — not part of the Story body

Use real captures from the matched prototype. Detailed component lists, purchasing
links, schematics, source files and application inventories belong in Hackster's
dedicated fields rather than being duplicated in the Story.

1. Use a centered 4:3 cover photograph of the actual compact node under clean,
   diffuse lighting.
2. Add an annotated top-down wiring photograph after the project focus section.
3. Add a close-up where the microphone labels and orientation are readable.
4. Add a log capture showing calibration, listening, trigger and local inference.
5. Add a waveform evidence card with the pre-trigger boundary highlighted.
6. Add one retained-audio JSON example and one recognition-only JSON example.
7. Add a concise limitations table or diagram near the release position.
8. Identify every replay as a replay and retain its source, license, distance and
   playback setting.
9. Do not use stock wildlife imagery as implementation evidence.
10. Proofread the pasted Story after the editor applies its own formatting.
