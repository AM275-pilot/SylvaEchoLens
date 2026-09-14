# Sylva EchoLens: Listen First, Keep the Evidence, Understand It Locally

Sylva EchoLens is an offline acoustic wildlife observer built around Arduino UNO Q.
It listens through one digital microphone, selects relevant sound events on the
real-time microcontroller, checks that every sample reaches Linux intact and runs
BirdNET locally. Each result becomes a traceable observation instead of a label with
no evidence behind it.

The goal is simple: keep observing where an Internet connection cannot be assumed.

## Why I decided to build it

Wildlife monitoring often happens in exactly the places where cloud-dependent
systems are least comfortable. Connectivity can be slow, intermittent or absent,
yet an animal call lasts only a moment. If the device cannot decide what to keep at
the edge, that moment may disappear before anyone can inspect it.

I wanted to explore a different kind of observer: small enough to remain focused,
honest about uncertainty and useful even while disconnected. The device should not
just output a species name. It should preserve how that result was produced: the
audio geometry, the trigger position, transport checks, model identity, score,
threshold, time quality and whether the original recording is still available.

The project began with a broader idea that included sound localization, a camera,
pan-and-tilt movement, environmental sensors and a dashboard. Planning the first
prototype established a deliberate development order: the hardware on my bench had
one INMP441 microphone, so the first milestone would prove the complete mono evidence
path. The two slots in an Inter-IC Sound (I2S) frame are not two microphones, and one
microphone alone cannot yet provide an honest direction estimate.

This is a prioritization decision, not a statement that expansion is impossible.
The architecture is intended to progress. Once capture fidelity, event selection,
local inference, storage resilience and power are validated, the planned path is to
add synchronized microphone channels, measure their geometry and timing, validate a
direction estimator and only then use that result for optional visual orientation.
Focusing first on trustworthy mono audio gives those later stages a tested input
rather than building localization on uncertain samples.

## What I built

The current prototype uses:

- one Arduino UNO Q;
- one INMP441 digital I2S microphone;
- six jumper wires for power, ground, clock, word select, data and channel select;
- a USB-C data connection for development and evidence collection;
- a separate speaker only when running controlled acoustic replay tests.

The INMP441 runs at 3.3 V and sends a mono stream to the STM32 side of the UNO Q.
The STM32 performs continuous acquisition and lightweight event detection. The
Qualcomm Linux processor receives only selected windows, validates them, stores the
observation and runs BirdNET v2.4 through LiteRT.

The complete wiring net list and every current logical diagram are collected in the
[Sylva EchoLens schematics](https://github.com/AM275-pilot/SylvaEchoLens/blob/develop/docs/SCHEMATICS.md).
The full source is available in the
[project repository](https://github.com/AM275-pilot/SylvaEchoLens).

## How it works

### 1. Listen continuously on the real-time processor

The STM32 receives the microphone stream through a custom SAI1/I2S and Direct Memory
Access (DMA) path. DMA keeps acquisition moving while the firmware evaluates the
signal and communicates with Linux.

The verified format is mono, signed 16-bit pulse-code modulation at a configured
16 kHz. That means the current capture cannot represent frequencies above the 8 kHz
Nyquist limit. This is an important boundary for bird calls and is recorded rather
than hidden.

### 2. Learn the background and detect acoustic contrast

At startup the detector settles for two seconds and measures the background for
three seconds. It removes direct-current offset, estimates background energy and
opens only when two of three consecutive 16 ms frames rise above an adaptive
threshold. Hysteresis and a cooldown period reduce repeated triggers around the
same boundary.

This stage detects a sound that differs from the recent background. It does not
recognize a species. Wind, speech, machinery and other sounds can also open the
gate, which is why classification and negative controls are separate validation
steps.

### 3. Keep the beginning of the sound

A rolling memory always retains the most recent samples. When a trigger is confirmed,
the firmware freezes a 2.048-second event containing 0.512 seconds from before the
confirmation frame. This pre-event history helps preserve the beginning of a short
call instead of starting the recording after detection.

Only one immutable event is held at a time. A new trigger never overwrites an event
being transferred. Closely spaced sounds can therefore be counted as skipped. That
is a known throughput limit, but it is preferable to silently corrupting evidence.

### 4. Verify the event across both processors

The Bridge transports numeric sample values from the STM32 to Linux. A CRC-32 covers
the exact little-endian PCM bytes, and the Linux receiver rejects invalid geometry,
missing chunks, conflicting duplicates, timeouts or checksum failures. It never
inserts invented silence to make an incomplete event look valid.

After a valid transfer, Linux produces an evidence record and, while the audio
budget permits, a WAV file. SHA-256 identifies the stored audio. The record also
contains the trigger and background levels, duration, peak, clipped-sample count,
session identity and timing provenance.

This verification step came from an early failure. The first recordings contained
nonzero data, but investigation found a byte-order mismatch between the two
processors. Fixing the sample contract and checking it across languages was more
important than rushing to a classifier. A model can only be as trustworthy as its
input.

### 5. Run wildlife inference locally

The checked WAV is analyzed by the official BirdNET v2.4 FP32 model on the UNO Q
Linux processor. The application pins the BirdNET package and LiteRT runtime and
keeps the downloaded model in persistent local storage.

BirdNET expects a three-second mono window at 48 kHz. Sylva EchoLens currently
produces 2.048 seconds at 16 kHz, so the adapter resamples and zero-pads the event.
Those transformations are written into the observation record. Resampling makes the
file compatible with the model, but it cannot reconstruct frequencies absent from
the original capture.

BirdNET always ranks candidates, even for unfamiliar or non-wildlife sounds. To
avoid presenting every ranking as a detection, Sylva EchoLens retains the five best
candidates and publishes `unknown` when the highest score is below the configured
0.25 threshold. Every prediction includes the model name, version, backend, score
and threshold.

The model has completed inference on the physical UNO Q and in a container with
networking disabled, using only cached assets. This proves local execution. It does
not yet prove recognition accuracy for this microphone and deployment context; that
requires a versioned labeled replay set plus quiet, speech and background controls.

A first positive replay is now recorded. After the operator announced an assiolo
playback, two retained and independently audited events were classified as
`Otus scops_Eurasian Scops-Owl` at 0.996 and 0.997. Both passed the 0.25 acceptance
threshold with no clipped samples. This is precise evidence of the device response
to that replay, not a claim that a wild owl was present or that accuracy is already
known. The source, license, speaker distance and playback setting still need to be
attached, together with negative controls and repeated levels.

### 6. Degrade gracefully when storage becomes scarce

Offline operation is more than disconnecting the network. A field device must also
handle finite storage, interrupted writes, restarts and an uncertain clock.

Sylva EchoLens separates storage into an audio budget, a reserve for compact
observation records and a system-space reserve. While space is available, an
observation retains both its JSON record and WAV evidence. Under pressure, the
retention policy may remove only the application's own indexed, unprotected WAVs.
Their records, original hashes and removal reasons remain.

If permanent audio cannot be admitted, BirdNET uses a bounded temporary WAV. The
temporary file is deleted after inference and the durable record is explicitly
marked `never_retained`. This recognition-only mode keeps producing compact
observations, but it also states the cost: without the audio, later listening or
reclassification is impossible.

Writes use temporary files and atomic publication. On startup the application
reconciles pending records, incomplete temporary audio, missing or corrupt WAVs and
orphan recordings. Each observation records wall-clock source and declared quality,
Linux boot identity, monotonic time and MCU trigger position. Time is `unverified`
by default, and backward movement is marked `regressed`.

## The power-saving approach—and the experiment that failed

The compact variant saves work by design. The STM32 performs continuous lightweight
acquisition, while BirdNET runs only after a complete event is worth analyzing. The
node carries no camera, illumination or servo load. Bounded retention also prevents
the audio archive from growing without control.

This is an architectural power-saving approach, not a measured battery-life claim.
Linux remains awake in the supported release configuration, and whole-board power
has not yet been measured.

I also prototyped Linux suspend-to-idle to test whether the STM32 could keep listening
and wake Linux after an acoustic event. The software used a restricted host helper,
an MCU arm/disarm handshake and a buffered wake-causing event. The board genuinely
entered and exited kernel `s2idle`, but deliberate nearby sound did not produce a
repeatable, attributable UART wake. Other enabled sources caused some resumes, and
controlled recovery required power control or a power cycle.

That result failed the acceptance criterion for an unattended observer. Suspend is
therefore disabled by default and excluded from the release. The failed experiment
is documented because it changed the design direction: future low-power work must
begin with actual measurements and an independently verified wake source, not with
an assumption that a writable UART setting guarantees wake.

## What has been demonstrated

The current evidence supports these claims:

- continuous mono acquisition works through the verified custom I2S loader;
- the adaptive gate and pre-event buffer run on the physical board;
- device WAV events have passed geometry, CRC-32 and SHA-256 audits;
- BirdNET v2.4 inference runs locally from cached assets without network access;
- two audited events from an announced assiolo replay returned accepted `Otus scops`
  results at 0.996 and 0.997;
- isolated UNO Q smoke tests exercised audio quota transitions, protected retention,
  recognition-only inference, orphan recovery and a clean application restart;
- 38 Python host tests pass, including a multiprocessing entrypoint regression test;
- the portable C++ acoustic-pipeline test passes with address and undefined-behavior
  sanitizers, including a shared cross-language CRC vector.

These results demonstrate an end-to-end edge pipeline and its evidence handling.
They do not demonstrate calibrated microphone sensitivity, representative species
accuracy, long-term unattended operation, physical power-cut recovery or battery
autonomy.

## Reproducing the build

The active source is in `app_audio_test/`; that historical directory name remains
for repository continuity. The application displayed and started on Arduino UNO Q is
named `SylvaEchoLens`.

1. Wire the single INMP441 exactly as shown in the schematics: 3.3 V, ground, I2S
   clock, word select, data and L/R tied to ground for the left slot.
2. Run the Python unit tests and the portable C++ gate/buffer test.
3. Read the deployment runbook before uploading. The project depends on a verified
   custom I2S loader, and a stock-core workflow can replace it.
4. Use the guarded build and deployment scripts. The Linux deployment creates a
   rollback snapshot before replacing the current board application.
5. Leave the startup environment representative for the five-second settling and
   calibration interval.
6. Trigger a documented sound, retain the matching WAV/JSON pair and audit it with
   `scripts/audit-events.py`.
7. Repeat with a licensed labeled bird call, quiet, speech and representative
   background controls at recorded playback levels and distances.

The repository contains the complete source, pinned Python dependencies, firmware
patches, tests, runbook, validation records, decisions and laboratory notebook.
Generated toolchains, credentials and raw field recordings are deliberately kept
out of Git.

## Planned field hardware

The current USB-powered bench prototype is the acoustic and inference foundation.
The planned field version adds an autonomous energy chain: a photovoltaic panel,
a rechargeable battery, a charge controller with battery protection and a regulated
power path sized for the complete UNO Q workload. Panel area and battery capacity
will be selected only after measuring awake baseline, audio transfer, BirdNET
inference and storage energy under realistic event rates. Until those measurements
exist, the project does not claim a specific number of autonomous days.

The electronics are also intended to move into a weather-resistant enclosure. The
UNO Q, battery, charger and connectors will remain inside a sealed volume with cable
strain relief. The microphone needs an acoustic path to the outside, so it will sit
behind a downward-facing opening protected by an acoustically transparent,
hydrophobic membrane and a replaceable open-cell foam windscreen. These protective
foam elements reduce direct droplets, wind and debris while leaving the microphone
acoustically exposed.

The enclosure must be tested rather than assumed waterproof. Planned acceptance
includes spray and driven-rain tests without powered electronics, drainage and
condensation inspection, before/after frequency-response comparison, wind-noise
trials and long outdoor temperature cycles. The microphone port must never become a
path that channels water toward the board or battery.

This mechanical design also leaves room for the planned sensing progression. A
later enclosure revision can establish a known baseline between synchronized
microphones for direction estimation. Only after that geometry is calibrated would
a camera or pan-and-tilt mechanism be added to a larger variant.

## Current limits and next steps

The next milestone is a repeatable labeled evaluation. It will combine licensed
target bird calls with quiet, speech, machinery and representative outdoor
backgrounds. Every accepted result, `unknown`, false trigger and missed event should
remain in the record. The 0.25 threshold must be evaluated on that set rather than
tuned from one successful playback.

The persistence path still needs controlled interruption during each write phase,
followed by application, Linux and whole-board restarts and a longer endurance run.
Power work must measure the awake baseline, acquisition, transfer, inference and
storage activity before choosing the battery, charge controller and solar-panel
area. Enclosure work must verify water protection, condensation behavior and the
acoustic effect of the membrane and foam rather than relying on appearance alone.

A local observation timeline is a natural next software feature. It can expose
candidates, audio-retention status, timestamp quality and storage health without
changing the evidence pipeline.

The hardware roadmap is also explicit. A second synchronized microphone is the next
localization step, followed by channel-alignment tests, known-angle replay trials and
an error map across distance and frequency. If that evidence supports reliable
direction estimates, a later variant can add camera confirmation and pan-and-tilt.
Each stage has its own acceptance test and power budget. None is claimed for the
current one-microphone device, but the progression is planned and technically open.

## What Sylva EchoLens is becoming

Sylva EchoLens started as a broad wildlife-monitoring idea and became a focused,
auditable acoustic instrument. It listens continuously, keeps the beginning of a
sound, refuses corrupt events, classifies locally and preserves useful records when
the network or audio-storage budget is unavailable.

Its most important result is not a single species label. It is the evidence chain
from microphone sample to MCU decision, checked event, local model output and honest
observation record. That foundation makes the current acoustic-only prototype useful
today while leaving the design open: the next versions can add localization, visual
confirmation, environmental context and multiple collaborating nodes without
abandoning the verified evidence path built first.
