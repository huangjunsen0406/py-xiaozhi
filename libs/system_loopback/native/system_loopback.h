/*
 * system_loopback.h - Cross-platform system audio loopback capture C ABI.
 *
 * Platforms:
 *   - macOS 14.2+: Core Audio Process Tap (macos_tap.m)
 *   - Windows:     WASAPI Loopback (windows_wasapi.cpp)
 *   - Linux:       PulseAudio / PipeWire-Pulse async monitor via dlopen (linux_pulse.c)
 *
 * All implementations expose the same minimal C ABI and deliver mono float32
 * samples in [-1.0, 1.0] via a lock-free single-producer single-consumer (SPSC)
 * ring buffer so the Python AEC consumer can drain without blocking.
 */

#ifndef PY_XIAOZHI_SYSTEM_LOOPBACK_H
#define PY_XIAOZHI_SYSTEM_LOOPBACK_H

#include <stddef.h>
#include <stdint.h>
#include <string.h>

#ifdef _WIN32
  #define SLB_API __declspec(dllexport)
#else
  #define SLB_API __attribute__((visibility("default")))
#endif

#ifdef __cplusplus
  #include <atomic>
  #define SLB_ATOMIC_UINT64 std::atomic<uint64_t>
  #define SLB_ATOMIC_INT std::atomic<int>
  #define SLB_LOAD_ACQ(x) ((x).load(std::memory_order_acquire))
  #define SLB_LOAD_RELX(x) ((x).load(std::memory_order_relaxed))
  #define SLB_STORE_REL(x, v) ((x).store((v), std::memory_order_release))
  #define SLB_STORE_RELX(x, v) ((x).store((v), std::memory_order_relaxed))
  extern "C" {
#else
  #include <stdatomic.h>
  #define SLB_ATOMIC_UINT64 _Atomic uint64_t
  #define SLB_ATOMIC_INT _Atomic int
  #define SLB_LOAD_ACQ(x) atomic_load_explicit(&(x), memory_order_acquire)
  #define SLB_LOAD_RELX(x) atomic_load_explicit(&(x), memory_order_relaxed)
  #define SLB_STORE_REL(x, v) atomic_store_explicit(&(x), (v), memory_order_release)
  #define SLB_STORE_RELX(x, v) atomic_store_explicit(&(x), (v), memory_order_relaxed)
#endif

typedef struct SystemLoopback SystemLoopback;

typedef enum slb_status {
    SLB_OK = 0,
    SLB_ERR_UNSUPPORTED = -1,       /* OS/runtime does not support system loopback */
    SLB_ERR_PERMISSION_DENIED = -2, /* OS privacy permission denied */
    SLB_ERR_DEVICE_NOT_FOUND = -3,  /* No output/monitor device available */
    SLB_ERR_INIT_FAILED = -4,       /* Backend initialization error */
    SLB_ERR_DEVICE_LOST = -5,       /* Output device invalidated/disconnected */
    SLB_ERR_INVALID_ARG = -6        /* Invalid argument */
} slb_status_t;

/*
 * Create a system loopback capture handle.
 *
 * target_device_name: optional UTF-8 output device hint (NULL/empty = system default).
 * out_sample_rate:    receives native loopback capture sample rate (Hz).
 * out_channels:       receives output channel count (always 1, mono float32).
 * out_handle:         receives opaque handle on SLB_OK; caller must slb_destroy().
 */
SLB_API slb_status_t slb_create(
    const char* target_device_name,
    int* out_sample_rate,
    int* out_channels,
    SystemLoopback** out_handle
);

/* Start streaming system loopback audio into the internal ring buffer. */
SLB_API slb_status_t slb_start(SystemLoopback* handle);

/*
 * Non-blocking read of up to max_frames mono float32 samples.
 * If more than max_frames are buffered, oldest stale frames are skipped so
 * the caller always receives the freshest time-aligned far-end reference.
 *
 * Returns >= 0 frames read, or a negative slb_status_t (e.g. SLB_ERR_DEVICE_LOST).
 */
SLB_API int slb_read_f32(SystemLoopback* handle, float* out_buf, int max_frames);

/* Returns the last diagnostic error string (never NULL; "" when none). */
SLB_API const char* slb_last_error(SystemLoopback* handle);

/* Stop capture (idempotent). */
SLB_API void slb_stop(SystemLoopback* handle);

/* Stop and free all resources (NULL-safe). */
SLB_API void slb_destroy(SystemLoopback* handle);

#ifdef __cplusplus
} /* extern "C" */
#endif

/* -------------------------------------------------------------------------
 * Lock-free SPSC float32 ring buffer (power-of-2 capacity).
 * 32768 samples = ~682ms @ 48kHz, ~2048ms @ 16kHz.
 * ------------------------------------------------------------------------- */
#define SLB_RING_CAPACITY 32768u
#define SLB_RING_MASK (SLB_RING_CAPACITY - 1u)

typedef struct slb_ring_t {
    float data[SLB_RING_CAPACITY];
    SLB_ATOMIC_UINT64 write_pos;
    SLB_ATOMIC_UINT64 read_pos;
} slb_ring_t;

static inline void slb_ring_init(slb_ring_t* r) {
    SLB_STORE_RELX(r->write_pos, 0u);
    SLB_STORE_RELX(r->read_pos, 0u);
}

static inline uint32_t slb_ring_write(slb_ring_t* r, const float* src, uint32_t count) {
    if (!count || !src) return 0u;
    uint64_t w = SLB_LOAD_RELX(r->write_pos);
    uint64_t rd = SLB_LOAD_ACQ(r->read_pos);
    uint64_t used = w - rd;
    if (used >= SLB_RING_CAPACITY) return 0u;
    uint32_t free_space = (uint32_t)(SLB_RING_CAPACITY - used);
    uint32_t n = count < free_space ? count : free_space;
    uint32_t idx = (uint32_t)(w & SLB_RING_MASK);
    uint32_t first = SLB_RING_CAPACITY - idx;
    if (first >= n) {
        memcpy(&r->data[idx], src, (size_t)n * sizeof(float));
    } else {
        memcpy(&r->data[idx], src, (size_t)first * sizeof(float));
        memcpy(&r->data[0], src + first, (size_t)(n - first) * sizeof(float));
    }
    SLB_STORE_REL(r->write_pos, w + n);
    return n;
}

static inline uint32_t slb_ring_write_zeros(slb_ring_t* r, uint32_t count) {
    if (!count) return 0u;
    uint64_t w = SLB_LOAD_RELX(r->write_pos);
    uint64_t rd = SLB_LOAD_ACQ(r->read_pos);
    uint64_t used = w - rd;
    if (used >= SLB_RING_CAPACITY) return 0u;
    uint32_t free_space = (uint32_t)(SLB_RING_CAPACITY - used);
    uint32_t n = count < free_space ? count : free_space;
    uint32_t idx = (uint32_t)(w & SLB_RING_MASK);
    uint32_t first = SLB_RING_CAPACITY - idx;
    if (first >= n) {
        memset(&r->data[idx], 0, (size_t)n * sizeof(float));
    } else {
        memset(&r->data[idx], 0, (size_t)first * sizeof(float));
        memset(&r->data[0], 0, (size_t)(n - first) * sizeof(float));
    }
    SLB_STORE_REL(r->write_pos, w + n);
    return n;
}

/*
 * Read the freshest samples up to max_frames; if more are queued, skip oldest
 * frames so far-end latency never accumulates unboundedly.
 */
static inline uint32_t slb_ring_read_latest(slb_ring_t* r, float* dst, uint32_t max_frames) {
    if (!max_frames || !dst) return 0u;
    uint64_t rd = SLB_LOAD_RELX(r->read_pos);
    uint64_t w = SLB_LOAD_ACQ(r->write_pos);
    uint64_t avail = w - rd;
    if (avail == 0u) return 0u;
    uint64_t start = rd;
    uint32_t n;
    if (avail > (uint64_t)max_frames) {
        start = w - (uint64_t)max_frames;
        n = max_frames;
    } else {
        n = (uint32_t)avail;
    }
    uint32_t idx = (uint32_t)(start & SLB_RING_MASK);
    uint32_t first = SLB_RING_CAPACITY - idx;
    if (first >= n) {
        memcpy(dst, &r->data[idx], (size_t)n * sizeof(float));
    } else {
        memcpy(dst, &r->data[idx], (size_t)first * sizeof(float));
        memcpy(dst + first, &r->data[0], (size_t)(n - first) * sizeof(float));
    }
    SLB_STORE_REL(r->read_pos, w);
    return n;
}

#endif /* PY_XIAOZHI_SYSTEM_LOOPBACK_H */
