#pragma once

#include <stddef.h>
#include <stdint.h>

namespace sylva {
constexpr uint32_t kSampleRate = 16000;
constexpr size_t kChunkSamples = 256;
constexpr size_t kPreSamples = 8192;
constexpr size_t kEventSamples = 32768;

// INMP441: signed 24-bit audio, MSB-aligned in a 32-bit left I2S slot.
inline int16_t pcmFromSlot(uint32_t slot) {
    return static_cast<int16_t>(slot >> 16);
}

// The wire carries four hexadecimal digits per signed sample, high byte first.
// This is a textual number, not a byte stream ready to write to a WAV file.
inline void encodeSamples(const int16_t* samples, size_t count, char* output) {
    constexpr char digits[] = "0123456789abcdef";
    for (size_t i = 0; i < count; ++i) {
        const uint16_t value = static_cast<uint16_t>(samples[i]);
        for (int shift = 12; shift >= 0; shift -= 4) {
            *output++ = digits[(value >> shift) & 15];
        }
    }
    *output = '\0';
}

// CRC-32/ISO-HDLC over the canonical little-endian PCM bytes.
inline uint32_t pcmCrc32(const int16_t* samples, size_t count) {
    uint32_t crc = 0xffffffffu;
    for (size_t i = 0; i < count; ++i) {
        const uint16_t value = static_cast<uint16_t>(samples[i]);
        for (int shift = 0; shift <= 8; shift += 8) {
            crc ^= (value >> shift) & 255u;
            for (int bit = 0; bit < 8; ++bit) {
                crc = (crc >> 1) ^ (0xedb88320u & (0u - (crc & 1u)));
            }
        }
    }
    return crc ^ 0xffffffffu;
}
}  // namespace sylva
