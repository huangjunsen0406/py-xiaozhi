/*
 * macos_tap.m - macOS 14.2+ Core Audio Process Tap system loopback capture.
 *
 * Captures a global mono mixdown of all system audio output via a private
 * CATapDescription + private Core Audio Aggregate Device, requiring no
 * third-party virtual audio driver (e.g. BlackHole) and leaving system
 * volume keys completely unaffected.
 *
 * Compiled with -mmacosx-version-min=11.0 so the dylib loads safely on older
 * macOS releases and cleanly returns SLB_ERR_UNSUPPORTED at runtime.
 */

#import <AudioToolbox/AudioToolbox.h>
#import <CoreAudio/AudioHardwareTapping.h>
#import <CoreAudio/CATapDescription.h>
#import <CoreAudio/CoreAudio.h>
#import <Foundation/Foundation.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "system_loopback.h"

struct SystemLoopback {
    AudioObjectID tap_id;
    AudioObjectID agg_device_id;
    AudioDeviceIOProcID io_proc_id;
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

static void set_error(SystemLoopback* ctx, const char* fmt, ...) {
    if (!ctx) return;
    va_list args;
    va_start(args, fmt);
    vsnprintf(ctx->last_error, sizeof(ctx->last_error), fmt, args);
    va_end(args);
}

static OSStatus tap_io_proc(
    AudioObjectID inDevice,
    const AudioTimeStamp* inNow,
    const AudioBufferList* inInputData,
    const AudioTimeStamp* inInputTime,
    AudioBufferList* outOutputData,
    const AudioTimeStamp* inOutputTime,
    void* inClientData
) {
    (void)inDevice;
    (void)inNow;
    (void)inInputTime;
    (void)outOutputData;
    (void)inOutputTime;

    SystemLoopback* ctx = (SystemLoopback*)inClientData;
    if (!ctx || !inInputData || inInputData->mNumberBuffers == 0) {
        return noErr;
    }

    const UInt32 n_bufs = inInputData->mNumberBuffers;

    if (n_bufs == 1) {
        const AudioBuffer buf = inInputData->mBuffers[0];
        if (!buf.mData || buf.mDataByteSize == 0) return noErr;
        const UInt32 ch = buf.mNumberChannels > 0 ? buf.mNumberChannels : 1;
        const UInt32 total_floats = buf.mDataByteSize / (UInt32)sizeof(float);
        const UInt32 frames = total_floats / ch;
        const float* src = (const float*)buf.mData;

        if (ch == 1) {
            slb_ring_write(&ctx->ring, src, frames);
        } else {
            float mono[512];
            const float inv_ch = 1.0f / (float)ch;
            UInt32 offset = 0;
            while (offset < frames) {
                UInt32 chunk = frames - offset;
                if (chunk > 512) chunk = 512;
                for (UInt32 i = 0; i < chunk; ++i) {
                    float sum = 0.0f;
                    const float* frame_ptr = src + (offset + i) * ch;
                    for (UInt32 c = 0; c < ch; ++c) {
                        sum += frame_ptr[c];
                    }
                    mono[i] = sum * inv_ch;
                }
                slb_ring_write(&ctx->ring, mono, chunk);
                offset += chunk;
            }
        }
    } else {
        /* Non-interleaved multi-channel buffers: average across buffers. */
        const AudioBuffer first = inInputData->mBuffers[0];
        if (!first.mData || first.mDataByteSize == 0) return noErr;
        const UInt32 frames = first.mDataByteSize / (UInt32)sizeof(float);
        float mono[512];
        const float inv_bufs = 1.0f / (float)n_bufs;
        UInt32 offset = 0;
        while (offset < frames) {
            UInt32 chunk = frames - offset;
            if (chunk > 512) chunk = 512;
            for (UInt32 i = 0; i < chunk; ++i) {
                float sum = 0.0f;
                for (UInt32 b = 0; b < n_bufs; ++b) {
                    const float* bptr = (const float*)inInputData->mBuffers[b].mData;
                    if (bptr) sum += bptr[offset + i];
                }
                mono[i] = sum * inv_bufs;
            }
            slb_ring_write(&ctx->ring, mono, chunk);
            offset += chunk;
        }
    }

    return noErr;
}

static NSString* get_default_output_device_uid(void) {
    AudioObjectPropertyAddress addr = {
        kAudioHardwarePropertyDefaultSystemOutputDevice,
        kAudioObjectPropertyScopeGlobal,
        kAudioObjectPropertyElementMain
    };
    AudioObjectID dev_id = kAudioObjectUnknown;
    UInt32 size = sizeof(dev_id);
    OSStatus status = AudioObjectGetPropertyData(
        kAudioObjectSystemObject, &addr, 0, NULL, &size, &dev_id
    );
    if (status != noErr || dev_id == kAudioObjectUnknown) {
        addr.mSelector = kAudioHardwarePropertyDefaultOutputDevice;
        status = AudioObjectGetPropertyData(
            kAudioObjectSystemObject, &addr, 0, NULL, &size, &dev_id
        );
        if (status != noErr || dev_id == kAudioObjectUnknown) {
            return nil;
        }
    }

    CFStringRef uid_cf = NULL;
    UInt32 uid_size = sizeof(uid_cf);
    AudioObjectPropertyAddress uid_addr = {
        kAudioDevicePropertyDeviceUID,
        kAudioObjectPropertyScopeGlobal,
        kAudioObjectPropertyElementMain
    };
    status = AudioObjectGetPropertyData(dev_id, &uid_addr, 0, NULL, &uid_size, &uid_cf);
    if (status != noErr || !uid_cf) {
        return nil;
    }
    return CFBridgingRelease(uid_cf);
}

static int query_tap_sample_rate(AudioObjectID tap_id, AudioObjectID agg_device_id) {
    AudioStreamBasicDescription asbd;
    memset(&asbd, 0, sizeof(asbd));
    UInt32 size = sizeof(asbd);

    /* Prefer querying the tap's actual format property first. */
    AudioObjectPropertyAddress tap_fmt_addr = {
        kAudioTapPropertyFormat,
        kAudioObjectPropertyScopeGlobal,
        kAudioObjectPropertyElementMain
    };
    if (AudioObjectGetPropertyData(tap_id, &tap_fmt_addr, 0, NULL, &size, &asbd) == noErr
        && asbd.mSampleRate >= 8000.0) {
        return (int)(asbd.mSampleRate + 0.5);
    }

    /* Fallback: nominal sample rate on aggregate device. */
    Float64 nominal = 0.0;
    size = sizeof(nominal);
    AudioObjectPropertyAddress rate_addr = {
        kAudioDevicePropertyNominalSampleRate,
        kAudioObjectPropertyScopeGlobal,
        kAudioObjectPropertyElementMain
    };
    if (AudioObjectGetPropertyData(agg_device_id, &rate_addr, 0, NULL, &size, &nominal) == noErr
        && nominal >= 8000.0) {
        return (int)(nominal + 0.5);
    }

    return 48000;
}

static void cleanup_context(SystemLoopback* ctx) {
    if (!ctx) return;
    if (ctx->started && ctx->agg_device_id != kAudioObjectUnknown && ctx->io_proc_id != NULL) {
        AudioDeviceStop(ctx->agg_device_id, ctx->io_proc_id);
        ctx->started = 0;
    }
    if (ctx->agg_device_id != kAudioObjectUnknown && ctx->io_proc_id != NULL) {
        AudioDeviceDestroyIOProcID(ctx->agg_device_id, ctx->io_proc_id);
        ctx->io_proc_id = NULL;
    }
    if (ctx->agg_device_id != kAudioObjectUnknown) {
        AudioHardwareDestroyAggregateDevice(ctx->agg_device_id);
        ctx->agg_device_id = kAudioObjectUnknown;
    }
    if (@available(macOS 14.2, *)) {
        if (ctx->tap_id != kAudioObjectUnknown) {
            AudioHardwareDestroyProcessTap(ctx->tap_id);
            ctx->tap_id = kAudioObjectUnknown;
        }
    }
}

SLB_API slb_status_t slb_create(
    const char* target_device_name,
    int* out_sample_rate,
    int* out_channels,
    SystemLoopback** out_handle
) {
    (void)target_device_name;
    if (!out_handle) return SLB_ERR_INVALID_ARG;
    *out_handle = NULL;

    @autoreleasepool {
        if (@available(macOS 14.2, *)) {
            SystemLoopback* ctx = (SystemLoopback*)calloc(1, sizeof(SystemLoopback));
            if (!ctx) return SLB_ERR_INIT_FAILED;
            ctx->tap_id = kAudioObjectUnknown;
            ctx->agg_device_id = kAudioObjectUnknown;
            ctx->io_proc_id = NULL;
            SLB_STORE_RELX(ctx->device_lost, 0);
            slb_ring_init(&ctx->ring);

            CATapDescription* tap_desc =
                [[CATapDescription alloc] initMonoGlobalTapButExcludeProcesses:@[]];
            if (!tap_desc) {
                set_error(ctx, "Failed to allocate CATapDescription");
                free(ctx);
                return SLB_ERR_INIT_FAILED;
            }
            tap_desc.name = @"py-xiaozhi-aec-tap";
            tap_desc.UUID = [NSUUID UUID];
            tap_desc.muteBehavior = CATapUnmuted;
            tap_desc.privateTap = YES;

            OSStatus status = AudioHardwareCreateProcessTap(tap_desc, &ctx->tap_id);
            if (status != noErr || ctx->tap_id == kAudioObjectUnknown) {
                set_create_error("AudioHardwareCreateProcessTap failed (OSStatus=%d)", (int)status);
                slb_status_t rc = (status == kAudioHardwareIllegalOperationError)
                    ? SLB_ERR_PERMISSION_DENIED
                    : SLB_ERR_INIT_FAILED;
                free(ctx);
                return rc;
            }

            NSString* tap_uid = tap_desc.UUID.UUIDString;
            NSString* agg_uid = [NSString stringWithFormat:@"com.py-xiaozhi.aec.agg.%@",
                                                           [NSUUID UUID].UUIDString];

            NSMutableDictionary* agg_dict = [NSMutableDictionary dictionaryWithDictionary:@{
                @kAudioAggregateDeviceNameKey: @"py-xiaozhi-aec-agg",
                @kAudioAggregateDeviceUIDKey: agg_uid,
                @kAudioAggregateDeviceIsPrivateKey: @YES,
                @kAudioAggregateDeviceIsStackedKey: @NO,
                /* Start IOProc immediately instead of waiting for first audio packet. */
                @kAudioAggregateDeviceTapAutoStartKey: @NO,
                @kAudioAggregateDeviceTapListKey: @[
                    @{
                        @kAudioSubTapUIDKey: tap_uid,
                        @kAudioSubTapDriftCompensationKey: @NO,
                    }
                ],
            }];

            /* Anchor clock to default output device when available for minimal drift. */
            NSString* output_uid = get_default_output_device_uid();
            if (output_uid.length > 0) {
                agg_dict[@kAudioAggregateDeviceMainSubDeviceKey] = output_uid;
                agg_dict[@kAudioAggregateDeviceSubDeviceListKey] = @[
                    @{
                        @kAudioSubDeviceUIDKey: output_uid,
                    }
                ];
            }

            status = AudioHardwareCreateAggregateDevice(
                (__bridge CFDictionaryRef)agg_dict, &ctx->agg_device_id
            );
            if (status != noErr || ctx->agg_device_id == kAudioObjectUnknown) {
                /* Retry tap-only aggregate device without sub-device anchor. */
                [agg_dict removeObjectForKey:@kAudioAggregateDeviceMainSubDeviceKey];
                [agg_dict removeObjectForKey:@kAudioAggregateDeviceSubDeviceListKey];
                status = AudioHardwareCreateAggregateDevice(
                    (__bridge CFDictionaryRef)agg_dict, &ctx->agg_device_id
                );
                if (status != noErr || ctx->agg_device_id == kAudioObjectUnknown) {
                    set_create_error("AudioHardwareCreateAggregateDevice failed (OSStatus=%d)", (int)status);
                    cleanup_context(ctx);
                    free(ctx);
                    return SLB_ERR_INIT_FAILED;
                }
            }

            ctx->sample_rate = query_tap_sample_rate(ctx->tap_id, ctx->agg_device_id);

            status = AudioDeviceCreateIOProcID(
                ctx->agg_device_id, tap_io_proc, ctx, &ctx->io_proc_id
            );
            if (status != noErr || !ctx->io_proc_id) {
                set_create_error("AudioDeviceCreateIOProcID failed (OSStatus=%d)", (int)status);
                cleanup_context(ctx);
                free(ctx);
                return SLB_ERR_INIT_FAILED;
            }

            g_last_create_error[0] = '\0';
            if (out_sample_rate) *out_sample_rate = ctx->sample_rate;
            if (out_channels) *out_channels = 1;
            *out_handle = ctx;
            return SLB_OK;
        } else {
            set_create_error("Core Audio Process Tap requires macOS 14.2+");
            return SLB_ERR_UNSUPPORTED;
        }
    }
}

SLB_API slb_status_t slb_start(SystemLoopback* handle) {
    if (!handle) return SLB_ERR_INVALID_ARG;
    if (handle->started) return SLB_OK;
    OSStatus status = AudioDeviceStart(handle->agg_device_id, handle->io_proc_id);
    if (status != noErr) {
        set_error(handle, "AudioDeviceStart failed (OSStatus=%d)", (int)status);
        return (status == kAudioHardwareIllegalOperationError)
            ? SLB_ERR_PERMISSION_DENIED
            : SLB_ERR_INIT_FAILED;
    }
    handle->started = 1;
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
    if (handle->started && handle->agg_device_id != kAudioObjectUnknown && handle->io_proc_id) {
        AudioDeviceStop(handle->agg_device_id, handle->io_proc_id);
        handle->started = 0;
    }
}

SLB_API void slb_destroy(SystemLoopback* handle) {
    if (!handle) return;
    cleanup_context(handle);
    free(handle);
}
