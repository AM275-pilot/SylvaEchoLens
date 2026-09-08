#pragma once

#include "audio_format.h"
#include <cmath>
#include <stdint.h>

namespace sylva {
struct GateConfig {
    float minimumRms = 96.0f;       // PCM units, not calibrated sound pressure.
    float openRatio = 2.0f;         // Approximately +6 dB in amplitude.
    float closeRatio = 1.414214f;   // Approximately +3 dB.
    float floorAlpha = 0.0032f;     // About five seconds at 256 samples/frame.
    uint32_t settleSamples = 2 * kSampleRate;
    uint32_t calibrationSamples = 3 * kSampleRate;
    uint32_t releaseSamples = 4800; // 300 ms below the closing threshold.
    uint32_t cooldownSamples = kSampleRate;
};

enum class GateState { Settling, Calibrating, Listening, Active, Cooldown };

class AcousticGate {
public:
    explicit AcousticGate(GateConfig config = {}) : config_(config) {}

    // Returns true only on the transition into an acoustic event.
    bool process(const int16_t* samples, size_t count) {
        double sum = 0.0;
        double squares = 0.0;
        for (size_t i = 0; i < count; ++i) {
            const double value = samples[i];
            sum += value;
            squares += value * value;
        }
        if (count == 0) return false;
        const double mean = sum / count;
        const double variance = squares / count - mean * mean;
        const float power = static_cast<float>(variance > 0.0 ? variance : 0.0);
        rms_ = std::sqrt(power);
        elapsed_ += count;

        if (state_ == GateState::Settling) {
            if (elapsed_ >= config_.settleSamples) {
                state_ = GateState::Calibrating;
                elapsed_ = 0;
            }
            return false;
        }
        if (state_ == GateState::Calibrating) {
            ++calibrationFrames_;
            floorPower_ += (power - floorPower_) / calibrationFrames_;
            if (elapsed_ >= config_.calibrationSamples) {
                state_ = GateState::Listening;
                elapsed_ = 0;
            }
            return false;
        }

        const float close = closingThreshold();
        if (state_ == GateState::Active) {
            quietSamples_ = rms_ < close ? quietSamples_ + count : 0;
            if (quietSamples_ >= config_.releaseSamples) {
                state_ = GateState::Cooldown;
                elapsed_ = 0;
                votes_ = 0;
            }
            return false;
        }
        if (state_ == GateState::Cooldown) {
            if (elapsed_ >= config_.cooldownSamples) state_ = GateState::Listening;
            return false;
        }

        const bool above = rms_ >= openingThreshold();
        votes_ = ((votes_ << 1) | (above ? 1u : 0u)) & 7u;
        const unsigned votes = (votes_ & 1u) + ((votes_ >> 1) & 1u) + ((votes_ >> 2) & 1u);
        if (votes >= 2) {
            state_ = GateState::Active;
            quietSamples_ = 0;
            votes_ = 0;
            return true;
        }
        // Freeze the floor around candidate events, including the vote history.
        if (votes_ == 0 && rms_ < close) {
            floorPower_ += config_.floorAlpha * (power - floorPower_);
        }
        return false;
    }

    float rms() const { return rms_; }
    float noiseRms() const { return std::sqrt(floorPower_); }
    float openingThreshold() const {
        const float adaptive = noiseRms() * config_.openRatio;
        return adaptive > config_.minimumRms ? adaptive : config_.minimumRms;
    }
    float closingThreshold() const {
        const float adaptive = noiseRms() * config_.closeRatio;
        const float minimum = config_.minimumRms / config_.closeRatio;
        return adaptive > minimum ? adaptive : minimum;
    }
    GateState state() const { return state_; }
    const char* stateName() const {
        switch (state_) {
            case GateState::Settling: return "settling";
            case GateState::Calibrating: return "calibrating";
            case GateState::Listening: return "listening";
            case GateState::Active: return "active";
            case GateState::Cooldown: return "cooldown";
        }
        return "unknown";
    }

private:
    GateConfig config_;
    GateState state_ = GateState::Settling;
    uint64_t elapsed_ = 0;
    uint32_t quietSamples_ = 0;
    uint32_t calibrationFrames_ = 0;
    unsigned votes_ = 0;
    float floorPower_ = 0;
    float rms_ = 0;
};
}  // namespace sylva
