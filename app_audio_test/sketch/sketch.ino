// Sylva EchoLens: one microphone, adaptive gate, bounded event capture.
// The custom Zephyr loader supplies SAI1_A and word-wide STM32U5 DMA.
#include <Arduino_RouterBridge.h>
#include <Arduino_LED_Matrix.h>
#include "audio_capture.h"
#include "acoustic_gate.h"
#include "event_buffer.h"

using namespace sylva;
static AcousticGate gate;
static EventBuffer recorder;
static ArduinoLEDMatrix matrix;
static int16_t frame[kChunkSamples];
static char hex[kChunkSamples * 4 + 1];
static uint64_t samplePosition = 0;
static uint64_t triggerSample = 0;
static uint32_t eventId = 0;
static uint32_t skippedEvents = 0;
static float triggerRms = 0;
static float triggerNoise = 0;
static bool healthy = false;
static bool sending = false;
static size_t txChunk = 0;
static uint32_t lastTelemetryMs = 0;
static uint32_t lastDisplayMs = 0;
static uint32_t lastErrorMs = 0;
static uint32_t lastTxMs = 0;
static bool powerSaveArmed = false;
static bool wakeNotified = false;
static uint32_t wakeNotifiedMs = 0;
static uint8_t levels[13] = {};
static constexpr uint8_t kLedOn = 7;
static constexpr uint32_t kLinuxWakeLeadMs = 1500;

static bool setPowerSave(bool enabled) {
    if (!enabled) {
        powerSaveArmed = false;
        wakeNotified = false;
        return true;
    }
    // Suspend is safe only while the MCU owns no event that Linux must receive.
    if (!healthy || sending || recorder.state() != EventBuffer::State::Listening) return false;
    powerSaveArmed = true;
    wakeNotified = false;
    return true;
}

static void drawLevel() {
    // Approximately 6 dB per step, without requiring the loader's libm errno ABI.
    // This is DC-removed RMS, not calibrated sound pressure.
    static const float thresholds[] = {65, 130, 260, 519, 1036, 2068, 4125, 8231};
    int level = 0;
    while (level < 8 && gate.rms() >= thresholds[level]) ++level;
    memmove(levels + 1, levels, 12);
    levels[0] = static_cast<uint8_t>(level);
    uint8_t pixels[104] = {};
    for (int x = 0; x < 13; ++x) {
        for (int row = 7; row >= 8 - levels[x]; --row) pixels[row * 13 + x] = kLedOn;
    }
    matrix.draw(pixels);
}

void setup() {
    matrix.begin();
    // The loader boot animation uses 8-bit grayscale and leaves that global state
    // behind. Select the 3-bit depth expected by this sketch on every boot.
    matrix.setGrayscaleBits(3);
    Bridge.begin();
    healthy = audio_init();
    Bridge.provide("sylva_power_save", setPowerSave);
    Bridge.notify("sylva_boot", 1, healthy ? "ready" : "error", audio_last_error());
}

void loop() {
    if (!healthy) {
        if (millis() - lastErrorMs >= 2000) {
            lastErrorMs = millis();
            Bridge.notify("sylva_error", audio_last_error());
        }
        delay(20);
        return;
    }
    // Acquisition keeps running while a frozen event is transferred to Linux.
    if (!audio_capture_chunk(frame, kChunkSamples)) {
        healthy = false;
        Bridge.notify("sylva_error", audio_last_error());
        return;
    }
    if (gate.process(frame, kChunkSamples)) {
        if (recorder.begin()) {
            ++eventId;
            triggerSample = samplePosition;
            triggerRms = gate.rms();
            triggerNoise = gate.noiseRms();
        } else {
            ++skippedEvents;
        }
    }
    recorder.append(frame, kChunkSamples);
    samplePosition += kChunkSamples;

    // Pace the UART transfer while continuing to drain queued DMA samples.
    if (recorder.state() == EventBuffer::State::Ready && millis() - lastTxMs >= 100) {
        lastTxMs = millis();
        if (powerSaveArmed) {
            if (!wakeNotified) {
                // UART activity is the suspend-to-idle wake stimulus. The lead
                // time lets Linux and the Bridge resume before event framing.
                Bridge.notify("sylva_wake", eventId);
                wakeNotified = true;
                wakeNotifiedMs = millis();
                return;
            }
            if (millis() - wakeNotifiedMs < kLinuxWakeLeadMs) return;
            powerSaveArmed = false;
            wakeNotified = false;
        }
        if (!sending) {
            Bridge.notify("sylva_begin", eventId, kSampleRate, kEventSamples,
                          kPreSamples, triggerSample, triggerRms, triggerNoise);
            sending = true;
            txChunk = 0;
        } else if (txChunk < kEventSamples / kChunkSamples) {
            encodeSamples(recorder.data() + txChunk * kChunkSamples, kChunkSamples, hex);
            Bridge.notify("sylva_chunk", eventId, static_cast<int>(txChunk), hex);
            ++txChunk;
        } else {
            char crc[9];
            snprintf(crc, sizeof(crc), "%08lx",
                     static_cast<unsigned long>(pcmCrc32(recorder.data(), kEventSamples)));
            Bridge.notify("sylva_end", eventId, static_cast<int>(txChunk), crc);
            sending = false;
            recorder.release();
        }
    }

    const uint32_t now = millis();
    if (now - lastDisplayMs >= 64) {
        lastDisplayMs = now;
        drawLevel();
    }
    if (!powerSaveArmed && now - lastTelemetryMs >= 1000) {
        lastTelemetryMs = now;
        Bridge.notify("sylva_level", gate.stateName(), gate.rms(), gate.noiseRms(),
                      gate.openingThreshold(), gate.closingThreshold(), skippedEvents);
    }
}
