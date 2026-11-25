/*
 * windows_wasapi.cpp - Windows WASAPI Loopback system audio capture.
 *
 * Runs COM (MTA) + IAudioClient(AUDCLNT_STREAMFLAGS_LOOPBACK) on a dedicated
 * worker thread so it never conflicts with PySide6's STA apartment on the main
 * thread. Pads 10ms of silence on event timeout so the AEC far-end stays
 * clocked smoothly even when no application is actively rendering audio.
 *
 * Build with MSVC:
 *   cl /LD /O2 /EHsc /W3 /I. windows_wasapi.cpp /Fe:system_loopback.dll ^
 *      ole32.lib avrt.lib uuid.lib
 */

#ifndef WIN32_LEAN_AND_MEAN
  #define WIN32_LEAN_AND_MEAN
#endif
#ifndef NOMINMAX
  #define NOMINMAX
#endif

#include <windows.h>
#include <audioclient.h>
#include <avrt.h>
#include <functiondiscoverykeys_devpkey.h>
#include <ksmedia.h>
#include <mmdeviceapi.h>

#include <atomic>
#include <condition_variable>
#include <cstdarg>
#include <cstdio>
#include <cstring>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

#include "system_loopback.h"

struct SystemLoopback {
    std::string target_device_utf8;
    std::thread worker;
    std::mutex mu;
    std::condition_variable cv;

    bool init_done = false;
    slb_status_t init_status = SLB_ERR_INIT_FAILED;
    bool start_requested = false;
    std::atomic<bool> stop_requested{false};
    std::atomic<int> device_lost{0};
    HANDLE stop_event = nullptr;

    int sample_rate = 48000;
    slb_ring_t ring;
    char last_error[256] = {0};
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

static std::wstring utf8_to_wide(const std::string& s) {
    if (s.empty()) return std::wstring();
    int len = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), nullptr, 0);
    if (len <= 0) return std::wstring();
    std::wstring out((size_t)len, L'\0');
    MultiByteToWideChar(CP_UTF8, 0, s.c_str(), (int)s.size(), &out[0], len);
    return out;
}

static IMMDevice* select_render_device(IMMDeviceEnumerator* enumerator, const std::string& hint_utf8) {
    if (!hint_utf8.empty()) {
        std::wstring hint = utf8_to_wide(hint_utf8);
        IMMDeviceCollection* col = nullptr;
        if (SUCCEEDED(enumerator->EnumAudioEndpoints(eRender, DEVICE_STATE_ACTIVE, &col)) && col) {
            UINT count = 0;
            col->GetCount(&count);
            for (UINT i = 0; i < count; ++i) {
                IMMDevice* dev = nullptr;
                if (FAILED(col->Item(i, &dev)) || !dev) continue;
                IPropertyStore* props = nullptr;
                if (SUCCEEDED(dev->OpenPropertyStore(STGM_READ, &props)) && props) {
                    PROPVARIANT var;
                    PropVariantInit(&var);
                    if (SUCCEEDED(props->GetValue(PKEY_Device_FriendlyName, &var))
                        && var.vt == VT_LPWSTR && var.pwszVal) {
                        std::wstring name(var.pwszVal);
                        if (name == hint || name.find(hint) != std::wstring::npos) {
                            PropVariantClear(&var);
                            props->Release();
                            col->Release();
                            return dev;
                        }
                    }
                    PropVariantClear(&var);
                    props->Release();
                }
                dev->Release();
            }
            col->Release();
        }
    }

    IMMDevice* def_dev = nullptr;
    if (SUCCEEDED(enumerator->GetDefaultAudioEndpoint(eRender, eConsole, &def_dev))) {
        return def_dev;
    }
    return nullptr;
}

static bool is_ieee_float_format(const WAVEFORMATEX* wf) {
    if (!wf) return false;
    if (wf->wFormatTag == WAVE_FORMAT_IEEE_FLOAT && wf->wBitsPerSample == 32) {
        return true;
    }
    if (wf->wFormatTag == WAVE_FORMAT_EXTENSIBLE && wf->cbSize >= 22) {
        const auto* ext = reinterpret_cast<const WAVEFORMATEXTENSIBLE*>(wf);
        return IsEqualGUID(ext->SubFormat, KSDATAFORMAT_SUBTYPE_IEEE_FLOAT)
            && wf->wBitsPerSample == 32;
    }
    return false;
}

static bool is_pcm16_format(const WAVEFORMATEX* wf) {
    if (!wf) return false;
    if (wf->wFormatTag == WAVE_FORMAT_PCM && wf->wBitsPerSample == 16) {
        return true;
    }
    if (wf->wFormatTag == WAVE_FORMAT_EXTENSIBLE && wf->cbSize >= 22) {
        const auto* ext = reinterpret_cast<const WAVEFORMATEXTENSIBLE*>(wf);
        return IsEqualGUID(ext->SubFormat, KSDATAFORMAT_SUBTYPE_PCM)
            && wf->wBitsPerSample == 16;
    }
    return false;
}

static void push_packet_to_ring(
    slb_ring_t* ring,
    const BYTE* data,
    UINT32 frames,
    WORD channels,
    bool is_float,
    bool is_pcm16,
    DWORD flags
) {
    if (frames == 0) return;
    if ((flags & AUDCLNT_BUFFERFLAGS_SILENT) || !data) {
        slb_ring_write_zeros(ring, frames);
        return;
    }
    const UINT32 ch = channels > 0 ? channels : 1;
    const float inv_ch = 1.0f / (float)ch;
    float mono[512];

    if (is_float) {
        const auto* src = reinterpret_cast<const float*>(data);
        if (ch == 1) {
            slb_ring_write(ring, src, frames);
            return;
        }
        UINT32 off = 0;
        while (off < frames) {
            UINT32 chunk = (frames - off) < 512 ? (frames - off) : 512;
            for (UINT32 i = 0; i < chunk; ++i) {
                float sum = 0.0f;
                const float* p = src + (off + i) * ch;
                for (UINT32 c = 0; c < ch; ++c) sum += p[c];
                mono[i] = sum * inv_ch;
            }
            slb_ring_write(ring, mono, chunk);
            off += chunk;
        }
    } else if (is_pcm16) {
        const auto* src = reinterpret_cast<const int16_t*>(data);
        UINT32 off = 0;
        while (off < frames) {
            UINT32 chunk = (frames - off) < 512 ? (frames - off) : 512;
            for (UINT32 i = 0; i < chunk; ++i) {
                float sum = 0.0f;
                const int16_t* p = src + (off + i) * ch;
                for (UINT32 c = 0; c < ch; ++c) sum += (float)p[c] / 32768.0f;
                mono[i] = sum * inv_ch;
            }
            slb_ring_write(ring, mono, chunk);
            off += chunk;
        }
    } else {
        slb_ring_write_zeros(ring, frames);
    }
}

static void worker_thread_main(SystemLoopback* ctx) {
    HRESULT hr = CoInitializeEx(nullptr, COINIT_MULTITHREADED);
    const bool com_init = SUCCEEDED(hr);

    IMMDeviceEnumerator* enumerator = nullptr;
    IMMDevice* device = nullptr;
    IAudioClient* audio_client = nullptr;
    IAudioCaptureClient* capture_client = nullptr;
    WAVEFORMATEX* mix_fmt = nullptr;
    HANDLE h_mmcss = nullptr;
    DWORD task_idx = 0;

    auto signal_init = [&](slb_status_t status) {
        if (status != SLB_OK && ctx->last_error[0] != '\0') {
            set_create_error("%s", ctx->last_error);
        } else if (status == SLB_OK) {
            g_last_create_error[0] = '\0';
        }
        std::lock_guard<std::mutex> lk(ctx->mu);
        ctx->init_status = status;
        ctx->init_done = true;
        ctx->cv.notify_all();
    };

    if (!com_init && hr != RPC_E_CHANGED_MODE) {
        set_error(ctx, "CoInitializeEx failed (0x%08lx)", (unsigned long)hr);
        signal_init(SLB_ERR_INIT_FAILED);
        return;
    }

    hr = CoCreateInstance(
        __uuidof(MMDeviceEnumerator),
        nullptr,
        CLSCTX_ALL,
        __uuidof(IMMDeviceEnumerator),
        reinterpret_cast<void**>(&enumerator)
    );
    if (FAILED(hr) || !enumerator) {
        set_error(ctx, "CoCreateInstance(MMDeviceEnumerator) failed (0x%08lx)", (unsigned long)hr);
        signal_init(SLB_ERR_INIT_FAILED);
        goto cleanup;
    }

    device = select_render_device(enumerator, ctx->target_device_utf8);
    if (!device) {
        set_error(ctx, "No active WASAPI render endpoint found");
        signal_init(SLB_ERR_DEVICE_NOT_FOUND);
        goto cleanup;
    }

    hr = device->Activate(__uuidof(IAudioClient), CLSCTX_ALL, nullptr, reinterpret_cast<void**>(&audio_client));
    if (FAILED(hr) || !audio_client) {
        set_error(ctx, "IMMDevice::Activate(IAudioClient) failed (0x%08lx)", (unsigned long)hr);
        signal_init(SLB_ERR_INIT_FAILED);
        goto cleanup;
    }

    hr = audio_client->GetMixFormat(&mix_fmt);
    if (FAILED(hr) || !mix_fmt) {
        set_error(ctx, "IAudioClient::GetMixFormat failed (0x%08lx)", (unsigned long)hr);
        signal_init(SLB_ERR_INIT_FAILED);
        goto cleanup;
    }

    const bool fmt_float = is_ieee_float_format(mix_fmt);
    const bool fmt_pcm16 = is_pcm16_format(mix_fmt);
    if (!fmt_float && !fmt_pcm16) {
        set_error(ctx, "Unsupported WASAPI mix format (tag=%u, bits=%u)",
                  (unsigned)mix_fmt->wFormatTag, (unsigned)mix_fmt->wBitsPerSample);
        signal_init(SLB_ERR_UNSUPPORTED);
        goto cleanup;
    }

    /*
     * 30ms shared-mode WASAPI loopback buffer (polling mode without EVENTCALLBACK
     * for maximum compatibility across Windows 10/11 audio drivers).
     */
    hr = audio_client->Initialize(
        AUDCLNT_SHAREMODE_SHARED,
        AUDCLNT_STREAMFLAGS_LOOPBACK,
        300000, /* 30ms in 100ns units */
        0,
        mix_fmt,
        nullptr
    );
    if (FAILED(hr)) {
        set_error(ctx, "IAudioClient::Initialize(LOOPBACK) failed (0x%08lx)", (unsigned long)hr);
        signal_init(SLB_ERR_INIT_FAILED);
        goto cleanup;
    }

    hr = audio_client->GetService(__uuidof(IAudioCaptureClient), reinterpret_cast<void**>(&capture_client));
    if (FAILED(hr) || !capture_client) {
        set_error(ctx, "IAudioClient::GetService(IAudioCaptureClient) failed (0x%08lx)", (unsigned long)hr);
        signal_init(SLB_ERR_INIT_FAILED);
        goto cleanup;
    }

    ctx->sample_rate = (int)mix_fmt->nSamplesPerSec;
    signal_init(SLB_OK);

    /* Wait until slb_start() or slb_destroy(). */
    {
        std::unique_lock<std::mutex> lk(ctx->mu);
        ctx->cv.wait(lk, [&]() {
            return ctx->start_requested || ctx->stop_requested.load(std::memory_order_acquire);
        });
    }
    if (ctx->stop_requested.load(std::memory_order_acquire)) {
        goto cleanup;
    }

    h_mmcss = AvSetMmThreadCharacteristicsW(L"Pro Audio", &task_idx);

    hr = audio_client->Start();
    if (FAILED(hr)) {
        set_error(ctx, "IAudioClient::Start failed (0x%08lx)", (unsigned long)hr);
        ctx->device_lost.store(1, std::memory_order_release);
        goto cleanup;
    }

    {
        const UINT32 silence_10ms = (UINT32)(ctx->sample_rate / 100);
        const WORD channels = mix_fmt->nChannels;

        while (!ctx->stop_requested.load(std::memory_order_acquire)) {
            DWORD wait_rc = ctx->stop_event
                ? WaitForSingleObject(ctx->stop_event, 10)
                : (Sleep(10), WAIT_TIMEOUT);
            if (wait_rc == WAIT_OBJECT_0 || ctx->stop_requested.load(std::memory_order_acquire)) {
                break;
            }

            UINT32 packet_frames = 0;
            hr = capture_client->GetNextPacketSize(&packet_frames);
            if (hr == AUDCLNT_E_DEVICE_INVALIDATED || hr == AUDCLNT_E_SERVICE_NOT_RUNNING) {
                set_error(ctx, "WASAPI output device invalidated (0x%08lx)", (unsigned long)hr);
                ctx->device_lost.store(1, std::memory_order_release);
                break;
            }
            if (FAILED(hr)) {
                continue;
            }

            if (packet_frames == 0) {
                /* No audio packets arrived in 10ms (idle speaker); pad zeros for AEC cadence. */
                slb_ring_write_zeros(&ctx->ring, silence_10ms);
                continue;
            }

            while (packet_frames > 0 && !ctx->stop_requested.load(std::memory_order_acquire)) {
                BYTE* data = nullptr;
                UINT32 frames_avail = 0;
                DWORD flags = 0;
                hr = capture_client->GetBuffer(&data, &frames_avail, &flags, nullptr, nullptr);
                if (hr == AUDCLNT_E_DEVICE_INVALIDATED || hr == AUDCLNT_E_SERVICE_NOT_RUNNING) {
                    set_error(ctx, "WASAPI GetBuffer device lost (0x%08lx)", (unsigned long)hr);
                    ctx->device_lost.store(1, std::memory_order_release);
                    break;
                }
                if (FAILED(hr)) break;

                push_packet_to_ring(
                    &ctx->ring, data, frames_avail, channels, fmt_float, fmt_pcm16, flags
                );
                capture_client->ReleaseBuffer(frames_avail);

                hr = capture_client->GetNextPacketSize(&packet_frames);
                if (FAILED(hr)) break;
            }
        }
    }

    audio_client->Stop();

cleanup:
    if (h_mmcss) AvRevertMmThreadCharacteristics(h_mmcss);
    if (capture_client) capture_client->Release();
    if (audio_client) audio_client->Release();
    if (device) device->Release();
    if (enumerator) enumerator->Release();
    if (mix_fmt) CoTaskMemFree(mix_fmt);
    if (com_init) CoUninitialize();
}

extern "C" {

SLB_API slb_status_t slb_create(
    const char* target_device_name,
    int* out_sample_rate,
    int* out_channels,
    SystemLoopback** out_handle
) {
    if (!out_handle) return SLB_ERR_INVALID_ARG;
    *out_handle = nullptr;

    auto* ctx = new SystemLoopback();
    slb_ring_init(&ctx->ring);
    ctx->stop_event = CreateEventW(nullptr, TRUE, FALSE, nullptr);
    if (target_device_name && target_device_name[0] != '\0') {
        ctx->target_device_utf8 = target_device_name;
    }

    ctx->worker = std::thread(worker_thread_main, ctx);

    {
        std::unique_lock<std::mutex> lk(ctx->mu);
        ctx->cv.wait(lk, [&]() { return ctx->init_done; });
    }

    if (ctx->init_status != SLB_OK) {
        slb_status_t rc = ctx->init_status;
        ctx->stop_requested.store(true, std::memory_order_release);
        if (ctx->stop_event) SetEvent(ctx->stop_event);
        ctx->cv.notify_all();
        if (ctx->worker.joinable()) ctx->worker.join();
        if (ctx->stop_event) CloseHandle(ctx->stop_event);
        delete ctx;
        return rc;
    }

    if (out_sample_rate) *out_sample_rate = ctx->sample_rate;
    if (out_channels) *out_channels = 1;
    *out_handle = ctx;
    return SLB_OK;
}

SLB_API slb_status_t slb_start(SystemLoopback* handle) {
    if (!handle) return SLB_ERR_INVALID_ARG;
    {
        std::lock_guard<std::mutex> lk(handle->mu);
        handle->start_requested = true;
    }
    handle->cv.notify_all();
    return SLB_OK;
}

SLB_API int slb_read_f32(SystemLoopback* handle, float* out_buf, int max_frames) {
    if (!handle || !out_buf || max_frames <= 0) return SLB_ERR_INVALID_ARG;
    if (handle->device_lost.load(std::memory_order_acquire)) return SLB_ERR_DEVICE_LOST;
    return (int)slb_ring_read_latest(&handle->ring, out_buf, (uint32_t)max_frames);
}

SLB_API const char* slb_last_error(SystemLoopback* handle) {
    if (!handle) return g_last_create_error;
    return handle->last_error;
}

SLB_API void slb_stop(SystemLoopback* handle) {
    if (!handle) return;
    handle->stop_requested.store(true, std::memory_order_release);
    if (handle->stop_event) SetEvent(handle->stop_event);
    handle->cv.notify_all();
    if (handle->worker.joinable()) {
        handle->worker.join();
    }
}

SLB_API void slb_destroy(SystemLoopback* handle) {
    if (!handle) return;
    slb_stop(handle);
    if (handle->stop_event) {
        CloseHandle(handle->stop_event);
        handle->stop_event = nullptr;
    }
    delete handle;
}

} /* extern "C" */
