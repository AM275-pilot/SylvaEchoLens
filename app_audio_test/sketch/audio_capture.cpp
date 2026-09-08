// audio_capture.cpp — STM32U585 SAI1 + DMA receiver for an INMP441.
//
// Wiring on the Arduino UNO Q R3 headers:
//   D21 / SCL -> SCK  (PB10 / SAI1_SCK_A)
//   D10       -> WS   (PB9  / SAI1_FS_A)
//   A4        -> SD   (PC1  / SAI1_SD_A)
//   GND       -> L/R  (left-channel selection)
//
// The custom Zephyr loader exposes SAI1_A as the i2s-rx devicetree alias.
// It receives standard Philips I2S at 16 kHz, two 32-bit slots per frame.

#include "audio_capture.h"
#include "audio_format.h"

#include <zephyr/device.h>
#include <zephyr/devicetree.h>
#include <zephyr/drivers/i2s.h>
#include <zephyr/kernel.h>

#include <stddef.h>
#include <stdint.h>

#define I2S_RX_NODE        DT_ALIAS(i2s_rx)
#define I2S_SAMPLE_RATE    16000
#define I2S_CHANNELS       2
#define I2S_SLOT_BYTES     4
#define I2S_BLOCK_FRAMES   2048
#define I2S_BLOCK_BYTES    (I2S_BLOCK_FRAMES * I2S_CHANNELS * I2S_SLOT_BYTES)
#define I2S_BLOCK_COUNT    6

static struct k_mem_slab s_rx_slab;
alignas(4) static uint8_t s_rx_slab_buffer[I2S_BLOCK_BYTES * I2S_BLOCK_COUNT];

static const struct device* s_i2s = nullptr;
static void* s_dma_block = nullptr;
static const int32_t* s_dma_words = nullptr;
static size_t s_dma_frames = 0;
static size_t s_dma_frame_index = 0;

static bool s_initialized = false;
static bool s_started = false;
static int s_last_error = 0;

static void release_dma_block() {
    if (s_dma_block != nullptr) {
        k_mem_slab_free(&s_rx_slab, s_dma_block);
        s_dma_block = nullptr;
        s_dma_words = nullptr;
        s_dma_frames = 0;
        s_dma_frame_index = 0;
    }
}

static bool acquire_dma_block() {
    release_dma_block();

    size_t bytes = 0;
    void* block = nullptr;
    const int rc = i2s_read(s_i2s, &block, &bytes);
    if (rc < 0) {
        s_last_error = rc;
        return false;
    }
    if (block == nullptr || bytes < (I2S_CHANNELS * I2S_SLOT_BYTES)) {
        if (block != nullptr) {
            k_mem_slab_free(&s_rx_slab, block);
        }
        s_last_error = -90;  // EMSGSIZE, kept numeric for the Bridge diagnostic.
        return false;
    }

    s_dma_block = block;
    s_dma_words = static_cast<const int32_t*>(block);
    s_dma_frames = bytes / (I2S_CHANNELS * I2S_SLOT_BYTES);
    s_dma_frame_index = 0;
    return true;
}

static bool ensure_started() {
    if (s_started) return true;

    int rc = i2s_trigger(s_i2s, I2S_DIR_RX, I2S_TRIGGER_START);
    if (rc == -EIO) {
        // Recover if a previous reader was interrupted after DMA overran.
        rc = i2s_trigger(s_i2s, I2S_DIR_RX, I2S_TRIGGER_PREPARE);
        if (rc == 0) {
            rc = i2s_trigger(s_i2s, I2S_DIR_RX, I2S_TRIGGER_START);
        }
    }
    if (rc < 0) {
        s_last_error = rc;
        return false;
    }

    s_started = true;
    return true;
}

static bool read_sample(int16_t* sample) {
    if (s_dma_block == nullptr || s_dma_frame_index >= s_dma_frames) {
        if (!acquire_dma_block()) {
            *sample = 0;
            return false;
        }
    }

    const uint32_t word = static_cast<uint32_t>(
        s_dma_words[s_dma_frame_index * I2S_CHANNELS]);
    // Keep native signed PCM on the MCU. The WAV writer owns byte serialization.
    *sample = sylva::pcmFromSlot(word);
    ++s_dma_frame_index;
    return true;
}

bool audio_init() {
    s_initialized = false;
    s_last_error = 0;
    s_started = false;
    release_dma_block();

    k_mem_slab_init(&s_rx_slab, s_rx_slab_buffer, I2S_BLOCK_BYTES, I2S_BLOCK_COUNT);

    s_i2s = device_get_binding(DEVICE_DT_NAME(I2S_RX_NODE));
    if (s_i2s == nullptr || !device_is_ready(s_i2s)) {
        s_last_error = -19;  // ENODEV
        return false;
    }

    struct i2s_config config = {};
    config.word_size = 32;
    config.channels = I2S_CHANNELS;
    config.format = I2S_FMT_DATA_FORMAT_I2S | I2S_FMT_DATA_ORDER_MSB |
                    I2S_FMT_CLK_NF_NB;
    config.options = I2S_OPT_BIT_CLK_MASTER | I2S_OPT_FRAME_CLK_MASTER;
    config.frame_clk_freq = I2S_SAMPLE_RATE;
    config.mem_slab = &s_rx_slab;
    config.block_size = I2S_BLOCK_BYTES;
    config.timeout = 1000;

    int rc = i2s_configure(s_i2s, I2S_DIR_RX, &config);
    if (rc < 0) {
        s_last_error = rc;
        return false;
    }

    s_initialized = true;
    return true;
}

int audio_last_error() {
    return s_last_error;
}

bool audio_capture_chunk(int16_t* buf, int n) {
    if (!s_initialized || buf == nullptr || n < 0) {
        s_last_error = -22;  // EINVAL
        return false;
    }
    if (!ensure_started()) return false;

    for (int i = 0; i < n; ++i) {
        if (!read_sample(&buf[i])) {
            for (int j = i + 1; j < n; ++j) {
                buf[j] = 0;
            }
            return false;
        }
    }
    return true;
}
