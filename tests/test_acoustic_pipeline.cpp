#include "../app_audio_test/sketch/acoustic_gate.h"
#include "../app_audio_test/sketch/event_buffer.h"
#include <cassert>
#include <cstring>
#include <iostream>
using namespace sylva;

static int16_t block[kChunkSamples];
static void fill(int amplitude, int dc = 0) {
    for (size_t i = 0; i < kChunkSamples; ++i) block[i] = dc + ((i & 1) ? amplitude : -amplitude);
}
static void feed(AcousticGate& gate, int amplitude, int frames, int dc = 0) {
    fill(amplitude, dc);
    while (frames--) assert(!gate.process(block, kChunkSamples));
}
static AcousticGate calibrated() {
    AcousticGate gate;
    feed(gate, 20, 125);  // Settling.
    feed(gate, 20, 188);  // Calibration.
    assert(gate.state() == GateState::Listening);
    return gate;
}
int main() {
    assert(pcmFromSlot(0x12345600) == 0x1234);
    assert(pcmFromSlot(0xffffab00) == -1);
    assert(pcmFromSlot(0x80000000) == -32768);
    int16_t vector[] = {0, 1, -1, 0x1234, -32768, 32767};
    char encoded[25];
    encodeSamples(vector, 6, encoded);
    assert(std::strcmp(encoded, "00000001ffff123480007fff") == 0);
    assert(pcmCrc32(vector, 6) == 0x170aea81);  // Also checked with Python zlib.

    auto gate = calibrated();
    feed(gate, 20, 100, 2000);  // DC offset must not trigger the gate.
    assert(gate.rms() == 20);
    const float floor = gate.noiseRms();
    feed(gate, 200, 1);        // A single outlier is not enough.
    feed(gate, 20, 3);
    feed(gate, 200, 1);
    fill(200);
    assert(gate.process(block, kChunkSamples));
    assert(gate.noiseRms() == floor);
    feed(gate, 200, 100);      // Sustained sound produces a single trigger.
    feed(gate, 20, 19);        // Release after at least 300 ms.
    assert(gate.state() == GateState::Cooldown);
    feed(gate, 20, 63);
    assert(gate.state() == GateState::Listening);
    feed(gate, 200, 1);
    fill(200);
    assert(gate.process(block, kChunkSamples));

    static EventBuffer buffer;
    assert(!buffer.begin());  // Do not publish an incomplete pre-roll.
    for (size_t i = 0; i < kPreSamples + 1024; ++i) {
        int16_t sample = static_cast<int16_t>(i);
        buffer.append(&sample, 1);
    }
    assert(buffer.begin());
    assert(!buffer.begin());
    for (size_t i = 0; i < kPreSamples; ++i) assert(buffer.data()[i] == static_cast<int16_t>(i + 1024));
    fill(-123);
    for (size_t i = kPreSamples; i < kEventSamples; i += kChunkSamples) buffer.append(block, kChunkSamples);
    assert(buffer.state() == EventBuffer::State::Ready);
    const uint32_t before = pcmCrc32(buffer.data(), kEventSamples);
    fill(456);
    buffer.append(block, kChunkSamples);
    assert(pcmCrc32(buffer.data(), kEventSamples) == before);
    buffer.release();
    assert(buffer.begin());   // Fresh history was retained during transfer.

    std::cout << "PASS: PCM format, DC rejection, confirmation, hysteresis, cooldown, pre-roll, immutable event\n";
    std::cout << "cross_language_crc=" << std::hex << pcmCrc32(vector, 6) << "\n";
}
