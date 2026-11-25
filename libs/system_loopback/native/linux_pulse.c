/*
 * linux_pulse.c - Linux PipeWire / PulseAudio system monitor loopback capture.
 *
 * Uses dlopen("libpulse.so.0") at runtime (zero hard link-time dependency so
 * headless ALSA-only systems load cleanly and return SLB_ERR_UNSUPPORTED) and
 * captures "@DEFAULT_MONITOR@" asynchronously via pa_threaded_mainloop at
 * 16kHz mono float32 so slb_stop() never blocks on a suspended sink.
 *
 * Build with gcc:
 *   gcc -shared -fPIC -O2 -Wall -I. linux_pulse.c -o libsystem_loopback.so -ldl -lpthread
 */

#include <dlfcn.h>
#include <stdarg.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "system_loopback.h"

/* Minimal PulseAudio ABI declarations (stable since PulseAudio 0.9.x & PipeWire). */
#define PA_SAMPLE_FLOAT32LE 5
#define PA_CONTEXT_READY 4
#define PA_CONTEXT_FAILED 5
#define PA_CONTEXT_TERMINATED 6
#define PA_STREAM_READY 2
#define PA_STREAM_FAILED 3
#define PA_STREAM_TERMINATED 4
#define PA_STREAM_ADJUST_LATENCY 0x2000

typedef struct pa_threaded_mainloop pa_threaded_mainloop;
typedef struct pa_mainloop_api pa_mainloop_api;
typedef struct pa_context pa_context;
typedef struct pa_stream pa_stream;

typedef struct pa_sample_spec {
    int format;
    uint32_t rate;
    uint8_t channels;
} pa_sample_spec;

typedef struct pa_buffer_attr {
    uint32_t maxlength;
    uint32_t tlength;
    uint32_t prebuf;
    uint32_t minreq;
    uint32_t fragsize;
} pa_buffer_attr;

typedef void (*pa_context_notify_cb_t)(pa_context* c, void* userdata);
typedef void (*pa_stream_notify_cb_t)(pa_stream* p, void* userdata);
typedef void (*pa_stream_request_cb_t)(pa_stream* p, size_t nbytes, void* userdata);

typedef struct pulse_api_t {
    void* so;
    pa_threaded_mainloop* (*ml_new)(void);
    void (*ml_free)(pa_threaded_mainloop*);
    int (*ml_start)(pa_threaded_mainloop*);
    void (*ml_stop)(pa_threaded_mainloop*);
    void (*ml_lock)(pa_threaded_mainloop*);
    void (*ml_unlock)(pa_threaded_mainloop*);
    void (*ml_wait)(pa_threaded_mainloop*);
    void (*ml_signal)(pa_threaded_mainloop*, int);
    pa_mainloop_api* (*ml_get_api)(pa_threaded_mainloop*);

    pa_context* (*ctx_new)(pa_mainloop_api*, const char*);
    void (*ctx_unref)(pa_context*);
    int (*ctx_connect)(pa_context*, const char*, int, const void*);
    void (*ctx_disconnect)(pa_context*);
    int (*ctx_get_state)(const pa_context*);
    void (*ctx_set_state_callback)(pa_context*, pa_context_notify_cb_t, void*);

    pa_stream* (*stream_new)(pa_context*, const char*, const pa_sample_spec*, const void*);
    void (*stream_unref)(pa_stream*);
    int (*stream_connect_record)(pa_stream*, const char*, const pa_buffer_attr*, int);
    int (*stream_disconnect)(pa_stream*);
    int (*stream_get_state)(const pa_stream*);
    void (*stream_set_state_callback)(pa_stream*, pa_stream_notify_cb_t, void*);
    void (*stream_set_read_callback)(pa_stream*, pa_stream_request_cb_t, void*);
    int (*stream_peek)(pa_stream*, const void**, size_t*);
    int (*stream_drop)(pa_stream*);
} pulse_api_t;

struct SystemLoopback {
    pulse_api_t pa;
    pa_threaded_mainloop* ml;
    pa_context* ctx;
    pa_stream* stream;
    int sample_rate;
    int started;
    SLB_ATOMIC_INT device_lost;
    slb_ring_t ring;
    char last_error[256];
};

static char g_last_create_error[256] = {0};

static void set_create_error(const char* fmt, ...) {
    va_list args;
    va_start(args, fmt);
    vsnprintf(g_last_create_error, sizeof(g_last_create_error), fmt, args);
    va_end(args);
}

static int is_valid_pulse_monitor_hint(const char* name) {
    if (!name || name[0] == '\0') return 0;
    if (name[0] == '@') return 1;
    size_t len = strlen(name);
    const char* suffix = ".monitor";
    size_t slen = strlen(suffix);
    return len > slen && strcmp(name + (len - slen), suffix) == 0;
}

#define LOAD_SYM(api, field, name)                          \
    do {                                                    \
        *(void**)(&(api)->field) = dlsym((api)->so, name);  \
        if (!(api)->field) return -1;                       \
    } while (0)

static int load_pulse_api(pulse_api_t* api) {
    memset(api, 0, sizeof(*api));
    api->so = dlopen("libpulse.so.0", RTLD_LAZY | RTLD_LOCAL);
    if (!api->so) {
        api->so = dlopen("libpulse.so", RTLD_LAZY | RTLD_LOCAL);
    }
    if (!api->so) return -1;

    LOAD_SYM(api, ml_new, "pa_threaded_mainloop_new");
    LOAD_SYM(api, ml_free, "pa_threaded_mainloop_free");
    LOAD_SYM(api, ml_start, "pa_threaded_mainloop_start");
    LOAD_SYM(api, ml_stop, "pa_threaded_mainloop_stop");
    LOAD_SYM(api, ml_lock, "pa_threaded_mainloop_lock");
    LOAD_SYM(api, ml_unlock, "pa_threaded_mainloop_unlock");
    LOAD_SYM(api, ml_wait, "pa_threaded_mainloop_wait");
    LOAD_SYM(api, ml_signal, "pa_threaded_mainloop_signal");
    LOAD_SYM(api, ml_get_api, "pa_threaded_mainloop_get_api");

    LOAD_SYM(api, ctx_new, "pa_context_new");
    LOAD_SYM(api, ctx_unref, "pa_context_unref");
    LOAD_SYM(api, ctx_connect, "pa_context_connect");
    LOAD_SYM(api, ctx_disconnect, "pa_context_disconnect");
    LOAD_SYM(api, ctx_get_state, "pa_context_get_state");
    LOAD_SYM(api, ctx_set_state_callback, "pa_context_set_state_callback");

    LOAD_SYM(api, stream_new, "pa_stream_new");
    LOAD_SYM(api, stream_unref, "pa_stream_unref");
    LOAD_SYM(api, stream_connect_record, "pa_stream_connect_record");
    LOAD_SYM(api, stream_disconnect, "pa_stream_disconnect");
    LOAD_SYM(api, stream_get_state, "pa_stream_get_state");
    LOAD_SYM(api, stream_set_state_callback, "pa_stream_set_state_callback");
    LOAD_SYM(api, stream_set_read_callback, "pa_stream_set_read_callback");
    LOAD_SYM(api, stream_peek, "pa_stream_peek");
    LOAD_SYM(api, stream_drop, "pa_stream_drop");
    return 0;
}

static void on_context_state(pa_context* c, void* userdata) {
    SystemLoopback* s = (SystemLoopback*)userdata;
    int st = s->pa.ctx_get_state(c);
    if (st == PA_CONTEXT_FAILED || st == PA_CONTEXT_TERMINATED) {
        SLB_STORE_REL(s->device_lost, 1);
    }
    s->pa.ml_signal(s->ml, 0);
}

static void on_stream_state(pa_stream* p, void* userdata) {
    SystemLoopback* s = (SystemLoopback*)userdata;
    int st = s->pa.stream_get_state(p);
    if (st == PA_STREAM_FAILED || st == PA_STREAM_TERMINATED) {
        SLB_STORE_REL(s->device_lost, 1);
    }
    s->pa.ml_signal(s->ml, 0);
}

static void on_stream_read(pa_stream* p, size_t nbytes, void* userdata) {
    (void)nbytes;
    SystemLoopback* s = (SystemLoopback*)userdata;
    for (;;) {
        const void* data = NULL;
        size_t len = 0;
        if (s->pa.stream_peek(p, &data, &len) < 0) break;
        if (len == 0) break;
        uint32_t frames = (uint32_t)(len / sizeof(float));
        if (data != NULL) {
            slb_ring_write(&s->ring, (const float*)data, frames);
        } else {
            /* Hole in stream -> pad zeros */
            slb_ring_write_zeros(&s->ring, frames);
        }
        s->pa.stream_drop(p);
    }
}

static void cleanup_pulse(SystemLoopback* s) {
    if (!s) return;
    if (s->ml) {
        s->pa.ml_lock(s->ml);
        if (s->stream) {
            s->pa.stream_set_read_callback(s->stream, NULL, NULL);
            s->pa.stream_set_state_callback(s->stream, NULL, NULL);
            s->pa.stream_disconnect(s->stream);
            s->pa.stream_unref(s->stream);
            s->stream = NULL;
        }
        if (s->ctx) {
            s->pa.ctx_set_state_callback(s->ctx, NULL, NULL);
            s->pa.ctx_disconnect(s->ctx);
            s->pa.ctx_unref(s->ctx);
            s->ctx = NULL;
        }
        s->pa.ml_unlock(s->ml);
        s->pa.ml_stop(s->ml);
        s->pa.ml_free(s->ml);
        s->ml = NULL;
    }
    if (s->pa.so) {
        dlclose(s->pa.so);
        s->pa.so = NULL;
    }
}

SLB_API slb_status_t slb_create(
    const char* target_device_name,
    int* out_sample_rate,
    int* out_channels,
    SystemLoopback** out_handle
) {
    if (!out_handle) return SLB_ERR_INVALID_ARG;
    *out_handle = NULL;

    SystemLoopback* s = (SystemLoopback*)calloc(1, sizeof(SystemLoopback));
    if (!s) return SLB_ERR_INIT_FAILED;
    slb_ring_init(&s->ring);
    SLB_STORE_RELX(s->device_lost, 0);
    s->sample_rate = 16000;

    if (load_pulse_api(&s->pa) != 0) {
        set_create_error("libpulse.so.0 not available on this system");
        cleanup_pulse(s);
        free(s);
        return SLB_ERR_UNSUPPORTED;
    }

    s->ml = s->pa.ml_new();
    if (!s->ml) {
        set_create_error("pa_threaded_mainloop_new failed");
        cleanup_pulse(s);
        free(s);
        return SLB_ERR_INIT_FAILED;
    }

    s->ctx = s->pa.ctx_new(s->pa.ml_get_api(s->ml), "py-xiaozhi-aec");
    if (!s->ctx) {
        set_create_error("pa_context_new failed");
        cleanup_pulse(s);
        free(s);
        return SLB_ERR_INIT_FAILED;
    }

    s->pa.ctx_set_state_callback(s->ctx, on_context_state, s);

    if (s->pa.ml_start(s->ml) < 0) {
        set_create_error("pa_threaded_mainloop_start failed");
        cleanup_pulse(s);
        free(s);
        return SLB_ERR_INIT_FAILED;
    }

    s->pa.ml_lock(s->ml);
    if (s->pa.ctx_connect(s->ctx, NULL, 0, NULL) < 0) {
        set_create_error("pa_context_connect failed (PulseAudio/PipeWire daemon not running)");
        s->pa.ml_unlock(s->ml);
        cleanup_pulse(s);
        free(s);
        return SLB_ERR_DEVICE_NOT_FOUND;
    }

    for (;;) {
        int st = s->pa.ctx_get_state(s->ctx);
        if (st == PA_CONTEXT_READY) break;
        if (st == PA_CONTEXT_FAILED || st == PA_CONTEXT_TERMINATED) {
            set_create_error("PulseAudio context failed to reach READY (state=%d)", st);
            s->pa.ml_unlock(s->ml);
            cleanup_pulse(s);
            free(s);
            return SLB_ERR_DEVICE_NOT_FOUND;
        }
        s->pa.ml_wait(s->ml);
    }

    pa_sample_spec spec;
    spec.format = PA_SAMPLE_FLOAT32LE;
    spec.rate = (uint32_t)s->sample_rate;
    spec.channels = 1;

    s->stream = s->pa.stream_new(s->ctx, "system-loopback", &spec, NULL);
    if (!s->stream) {
        set_create_error("pa_stream_new failed");
        s->pa.ml_unlock(s->ml);
        cleanup_pulse(s);
        free(s);
        return SLB_ERR_INIT_FAILED;
    }

    s->pa.stream_set_state_callback(s->stream, on_stream_state, s);
    s->pa.stream_set_read_callback(s->stream, on_stream_read, s);

    pa_buffer_attr attr;
    attr.maxlength = (uint32_t)-1;
    attr.tlength = (uint32_t)-1;
    attr.prebuf = (uint32_t)-1;
    attr.minreq = (uint32_t)-1;
    attr.fragsize = 160u * (uint32_t)sizeof(float); /* 10ms @ 16kHz */

    /* Only honor explicit PulseAudio monitor names; ignore PortAudio friendly names. */
    const char* source_name = is_valid_pulse_monitor_hint(target_device_name)
        ? target_device_name
        : "@DEFAULT_MONITOR@";

    if (s->pa.stream_connect_record(s->stream, source_name, &attr, PA_STREAM_ADJUST_LATENCY) < 0) {
        set_create_error("pa_stream_connect_record(%s) failed", source_name);
        s->pa.ml_unlock(s->ml);
        cleanup_pulse(s);
        free(s);
        return SLB_ERR_DEVICE_NOT_FOUND;
    }

    for (;;) {
        int st = s->pa.stream_get_state(s->stream);
        if (st == PA_STREAM_READY) break;
        if (st == PA_STREAM_FAILED || st == PA_STREAM_TERMINATED) {
            set_create_error("PulseAudio monitor stream(%s) failed (state=%d)", source_name, st);
            s->pa.ml_unlock(s->ml);
            cleanup_pulse(s);
            free(s);
            return SLB_ERR_DEVICE_NOT_FOUND;
        }
        s->pa.ml_wait(s->ml);
    }

    g_last_create_error[0] = '\0';
    s->started = 1;
    SLB_STORE_REL(s->device_lost, 0);
    s->pa.ml_unlock(s->ml);

    if (out_sample_rate) *out_sample_rate = s->sample_rate;
    if (out_channels) *out_channels = 1;
    *out_handle = s;
    return SLB_OK;
}

SLB_API slb_status_t slb_start(SystemLoopback* handle) {
    if (!handle) return SLB_ERR_INVALID_ARG;
    /* PulseAudio record stream starts immediately on READY. */
    return SLB_OK;
}

SLB_API int slb_read_f32(SystemLoopback* handle, float* out_buf, int max_frames) {
    if (!handle || !out_buf || max_frames <= 0) return SLB_ERR_INVALID_ARG;
    if (SLB_LOAD_ACQ(handle->device_lost)) return SLB_ERR_DEVICE_LOST;
    return (int)slb_ring_read_latest(&handle->ring, out_buf, (uint32_t)max_frames);
}

SLB_API const char* slb_last_error(SystemLoopback* handle) {
    if (!handle) return g_last_create_error;
    return handle->last_error;
}

SLB_API void slb_stop(SystemLoopback* handle) {
    if (!handle) return;
    handle->started = 0;
    cleanup_pulse(handle);
}

SLB_API void slb_destroy(SystemLoopback* handle) {
    if (!handle) return;
    cleanup_pulse(handle);
    free(handle);
}
