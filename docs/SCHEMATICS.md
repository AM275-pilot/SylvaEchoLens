# Sylva EchoLens schematics

This document collects every current circuit and system diagram for the
single-microphone Sylva EchoLens prototype. It is the source set for publication
figures and build reference.

Current hardware boundary: one Arduino UNO Q and one INMP441 microphone. The first
milestone deliberately validates mono capture and evidence before expanding the
sensor geometry. A synchronized second microphone, direction estimation and later
visual orientation are planned development stages, not impossible additions. They
are not wired or claimed in the implemented variant. The repository does not yet
contain a Fritzing project, PCB design, enclosure CAD model or verified schematic
for those future additions.

## 1. System signal path

```mermaid
flowchart LR
    MIC["One INMP441<br/>mono I2S microphone"] --> DMA["STM32<br/>SAI1 + DMA"]
    DMA --> GATE["DC-removed energy<br/>adaptive acoustic gate"]
    DMA --> HISTORY["Rolling<br/>0.512 s history"]
    GATE --> EVENT["Frozen 2.048 s event"]
    HISTORY --> EVENT
    EVENT --> BRIDGE["Bridge transport<br/>geometry + CRC-32"]
    BRIDGE --> STORE["Linux observation store<br/>quota + integrity decision"]
    STORE --> PRESSURE{"Audio space<br/>available?"}
    PRESSURE -- Yes --> WAV["Retain indexed WAV"]
    PRESSURE -- No --> COMPACT["Use bounded<br/>temporary WAV"]
    WAV --> MODEL["BirdNET v2.4<br/>local LiteRT inference"]
    COMPACT --> MODEL
    MODEL --> RECORD["Observation JSON<br/>label or unknown"]
```

Publication caption: **One microphone feeds deterministic event selection on the
STM32; Linux verifies the event, runs BirdNET locally and retains an auditable
observation according to the storage policy.**

## 2. Current electrical wiring

Disconnect USB power before changing any connection. Power the INMP441 from 3.3 V,
not 5 V. Header labels describe the physical UNO Q pins; this application uses their
alternate SAI/I2S functions.

```mermaid
flowchart LR
    subgraph UNO["Arduino UNO Q"]
        U3["3.3 V"]
        UG["GND"]
        U21["D21 / SCL<br/>PB10 · SAI1_SCK_A"]
        U10["D10<br/>PB9 · SAI1_FS_A"]
        U4["A4<br/>PC1 · SAI1_SD_A"]
    end

    subgraph MIC["INMP441 breakout"]
        MV["VDD"]
        MG["GND"]
        MS["SCK / BCLK"]
        MW["WS / LRCLK"]
        MD["SD / DOUT"]
        ML["L/R"]
    end

    U3 -- "red" --> MV
    UG -- "black" --> MG
    UG -- "white · select left slot" --> ML
    U21 -- "purple · bit clock" --> MS
    U10 -- "green · word select" --> MW
    MD -- "blue · audio data" --> U4
```

### Wiring net list

| Net | INMP441 pin | UNO Q connection | Tested wire | Constraint |
|---|---|---|---|---|
| Microphone supply | VDD | 3.3 V | Red | Do not use 5 V |
| Electrical reference | GND | GND | Black | Common ground |
| I2S bit clock | SCK / BCLK | D21 / SCL · PB10 / SAI1_SCK_A | Purple | Alternate SAI function, not I2C |
| I2S word select | WS / LRCLK | D10 · PB9 / SAI1_FS_A | Green | One word-select signal |
| Microphone data | SD / DOUT | A4 · PC1 / SAI1_SD_A | Blue | Digital input, not analog audio |
| Slot selection | L/R | GND | White | Selects the left I2S slot |

I2S carries two 32-bit slots per frame, but only the selected left slot contains the
one microphone signal. The empty/right slot is not a second channel and cannot be
used for direction finding.

Publication caption: **The implemented prototype uses six connections between one
INMP441 and Arduino UNO Q. L/R is tied to ground, so the microphone occupies the
left I2S slot.**

## 3. Event-window timing

```mermaid
flowchart LR
    SETTLE["Startup settle<br/>2.0 s"] --> CAL["Background calibration<br/>3.0 s"]
    CAL --> LISTEN["Listening<br/>rolling history active"]
    LISTEN --> VOTE["2 of 3 frames<br/>above opening threshold"]
    VOTE --> PRE["Pre-event prefix<br/>8,192 samples · 0.512 s"]
    PRE --> POST["From confirmation frame<br/>24,576 samples · 1.536 s"]
    POST --> READY["Immutable event<br/>32,768 samples · 2.048 s"]
    READY --> SEND["128 chunks<br/>256 samples each"]
    SEND --> RELEASE["Release event slot<br/>continue rolling history"]
```

The trigger position stored in metadata is sample 8,192: the start of the
confirmation frame. It is not the first threshold crossing and is not an absolute
UTC timestamp. The gate works on 256-sample, 16 ms frames. DMA delivery and Bridge
transfer mean that frame size is not an end-to-end latency guarantee.

Publication caption: **Every retained event contains 0.512 seconds from before
trigger confirmation and 1.536 seconds from the confirmation frame onward.**

## 4. Cross-processor event sequence

```mermaid
sequenceDiagram
    participant M as INMP441
    participant S as STM32
    participant R as Rolling history
    participant B as Bridge
    participant L as Linux receiver
    participant O as Observation store
    participant N as BirdNET v2.4

    M->>S: Continuous I2S frames
    S->>R: Retain latest 8,192 mono samples
    S->>S: Confirm 2 of 3 frames above threshold
    R->>S: Copy pre-event history
    S->>S: Complete immutable 32,768-sample event
    S->>B: begin + 128 chunks + end / CRC-32
    Note over M,S: Acquisition and gating continue during transfer
    B->>L: Numeric PCM samples
    L->>L: Validate geometry, chunks and CRC-32
    L->>O: Queue checked event
    O->>N: Retained or bounded temporary WAV
    N-->>O: Five candidates and scores
    O->>O: Publish WAV when retained, then atomic JSON
```

There is one MCU event slot, one in-flight Linux receiver and a persistence queue of
two. A busy MCU slot increments the skipped-event counter; a full Linux queue logs
an explicit drop. There is no retransmission or delivery acknowledgement in the
current protocol.

Publication caption: **The STM32 owns acquisition and event selection. Linux accepts
only complete checked events, then serializes storage and local inference.**

## 5. Offline storage decision

```mermaid
flowchart TD
    E["Checked event received"] --> SAFE{"System and record<br/>reserves preserved?"}
    SAFE -- No --> FAIL["Log persistence failure<br/>do not claim a durable observation"]
    SAFE -- Yes --> AUDIO{"New WAV fits<br/>audio budget?"}
    AUDIO -- Yes --> KEEP["Write WAV atomically<br/>run BirdNET<br/>publish JSON"]
    AUDIO -- No --> POLICY{"Retention policy"}
    POLICY -- delete_oldest --> EVICT{"Indexed unprotected<br/>WAV available?"}
    EVICT -- Yes --> REMOVE["Journal removal<br/>delete WAV<br/>preserve JSON + hash"]
    REMOVE --> KEEP
    EVICT -- No --> TEMP["Bounded temporary WAV<br/>run BirdNET<br/>delete temporary"]
    POLICY -- recognition_only --> TEMP
    TEMP --> JSON["Publish compact JSON<br/>audio = never_retained"]
```

Only final app-owned `event-*.wav` files with readable sidecars are candidates for
automatic removal. Protected WAVs, JSON records, unrelated files, corrupt audio and
unindexed orphan files are never retention candidates.

Publication caption: **Storage pressure changes audio retention, not the truthfulness
of the record: missing audio and every removal reason remain explicit.**

## 6. Planned field power and enclosure — not yet implemented

```mermaid
flowchart LR
    SUN["Photovoltaic panel"] --> CHARGE["Charge controller<br/>battery protection"]
    BAT["Rechargeable battery"] <--> CHARGE
    CHARGE --> REG["Regulated power path<br/>sized from measurements"]
    REG --> SEALED["Weather-resistant enclosure<br/>UNO Q + storage"]
    SEALED --> PORT["Downward-facing<br/>microphone port"]
    PORT --> MEM["Hydrophobic<br/>acoustic membrane"]
    MEM --> FOAM["Replaceable open-cell<br/>foam windscreen"]
    FOAM --> MIC["INMP441 acoustic opening"]
```

This is a development intention, not a verified circuit or enclosure. The final
design still requires selection of battery chemistry and capacity, charge-controller
and protection ratings, regulator, connector sealing, panel size, ventilation and
condensation strategy. Foam alone is not a waterproof barrier; the hydrophobic
acoustic membrane, downward-facing geometry, drainage and complete enclosure must be
validated together.

Publication caption: **Planned autonomous field packaging separates the sealed
electronics from a protected acoustic path: solar charging and battery sizing follow
measured power, while the microphone remains audible through a hydrophobic membrane
and replaceable windscreen.**

## Publication and source notes

Mermaid source is kept here so every diagram remains editable. If the publication
editor does not render Mermaid, export each diagram to SVG or a high-resolution PNG
and insert the rendered image with its caption. Do not use a generic two-microphone,
camera or servo diagram for the current prototype.

The electrical diagram is a verified logical net diagram, not a PCB fabrication
schematic. A publication-quality physical record still requires:

1. an evenly lit top-down photograph showing both ends of all six wires;
2. a close-up where the INMP441 silkscreen and orientation are readable;
3. optional reproduction of the same six-net circuit in Fritzing, without adding
   unimplemented components;
4. a revision label tying exported figures to the repository state used for the
   final device demonstration.

Reference documents:

- [Arduino UNO Q full pinout](https://docs.arduino.cc/resources/pinouts/ABX00162-full-pinout.pdf)
- [INMP441 datasheet](https://invensense.tdk.com/wp-content/uploads/2015/02/INMP441.pdf)
- [STM32U585 datasheet](https://www.st.com/resource/en/datasheet/stm32u585zi.pdf)
