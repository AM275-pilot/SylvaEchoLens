#ifndef AUDIO_CAPTURE_H
#define AUDIO_CAPTURE_H

#include <Arduino.h>

// Initializes SAI1_A + DMA at 16 kHz for the INMP441.
bool audio_init();

// Last negative Zephyr errno returned by the I2S backend (0 when healthy).
int audio_last_error();

// Capture exactly n mono samples from the left I2S slot.
bool audio_capture_chunk(int16_t* buf, int n);

#endif
