#pragma once

#include "audio_format.h"
#include <string.h>

namespace sylva {
class EventBuffer {
public:
    enum class State { Listening, Capturing, Ready };

    // Call before appending the trigger frame, so history ends immediately
    // before that frame. During transfer the frozen event is never overwritten.
    bool begin() {
        if (state_ != State::Listening || historyCount_ < kPreSamples) return false;
        for (size_t i = 0; i < kPreSamples; ++i) {
            event_[i] = history_[(historyHead_ + i) % kPreSamples];
        }
        eventCount_ = kPreSamples;
        state_ = State::Capturing;
        return true;
    }

    void append(const int16_t* samples, size_t count) {
        for (size_t i = 0; i < count; ++i) {
            if (state_ == State::Capturing) {
                event_[eventCount_++] = samples[i];
                if (eventCount_ == kEventSamples) state_ = State::Ready;
            }
            history_[historyHead_] = samples[i];
            historyHead_ = (historyHead_ + 1) % kPreSamples;
            if (historyCount_ < kPreSamples) ++historyCount_;
        }
    }

    const int16_t* data() const { return event_; }
    State state() const { return state_; }
    void release() { state_ = State::Listening; eventCount_ = 0; }

private:
    int16_t history_[kPreSamples] = {};
    int16_t event_[kEventSamples] = {};
    size_t historyHead_ = 0;
    size_t historyCount_ = 0;
    size_t eventCount_ = 0;
    State state_ = State::Listening;
};
}  // namespace sylva
