# Research: Wake Word Detection Regression (6cad765 vs HEAD)

- **Query**: Compare wake word detection code between commit 6cad765 (pre-merge main) and current HEAD; identify what changed that could prevent wake word from interrupting TTS playback on Windows.
- **Scope**: internal
- **Date**: 2026-05-15

## Summary of Commits Between 6cad765 and HEAD

Over 20 commits modified these files, including multiple fix/regression cycles:
- `288a4c3` fix: 回退检测循环为轮询模式，修复唤醒词无法检测的回归
- `8040b18` fix: 改为逐帧实时处理，去掉批量累积
- `442fdc4` fix: 修复批量处理导致唤醒词无法检测的回归
- `7210abb` fix: 修复唤醒词检测性能和 TTS 尾部截断问题
- `00cf6c3` feat: 添加线程锁以保护sherpa-onnx对象的访问

## Files Compared

| File | Old (6cad765) | Current (HEAD) |
|---|---|---|
| `src/audio_processing/wake_word_detect.py` | ~230 lines, synchronous init | ~464 lines, async `initialize()`, threading lock, sentinel stop |
| `src/plugins/wake_word.py` | ~70 lines, direct `self.app` access | ~130 lines, `PluginContext`/`PluginCommands` DI pattern |
| `src/audio_codecs/audio_codec.py` | Monolithic, inline `_input_callback` | Refactored; converter-based pipeline, thread-safe listener lock |

---

## Finding 1: Detection Loop Structure (Polling vs Event-Driven)

**Old (`6cad765`):**
```python
async def _detection_loop(self):
    while self.is_running_flag:
        if self.paused:
            await asyncio.sleep(0.1)
            continue
        await self._process_audio()
        await asyncio.sleep(0.005)
```

**Current (HEAD):**
```python
async def _detection_loop(self):
    while self._running and not self._stopping:
        if self._paused or self._stopping:
            await asyncio.sleep(0.1)
            continue
        await self._process_audio()
        await asyncio.sleep(0.005)
```

**Analysis:** Both use the same polling pattern with 5ms sleep. The detection loop structure is essentially identical. The current version adds a `self._stopping` guard, which only matters during shutdown -- not during normal speaking-state operation.

No regression here.

---

## Finding 2: Audio Data Flow to Detector

**Old (`6cad765`) -- `audio_codec.py` `_input_callback`:**
```python
# Step 4: convert to int16
audio_data_int16 = (audio_data * 32768.0).astype(np.int16)
# ...
# Step 7: notify listeners
for listener in self._audio_listeners:
    listener.on_audio_data(audio_data_int16.copy())
```
Listeners received **int16** data. No thread lock on listener list.

**Old (`6cad765`) -- `wake_word_detect.py` `_process_audio`:**
```python
if audio_data.dtype == np.int16:
    samples = audio_data.astype(np.float32) / 32768.0
else:
    samples = audio_data.astype(np.float32)
self.stream.accept_waveform(sample_rate=self.sample_rate, waveform=samples)
```
Old detector explicitly converted int16 -> float32 before feeding sherpa-onnx.

**Current (HEAD) -- `audio_codec.py` `_input_callback`:**
```python
audio_converted = self.converter.convert_input(indata, AudioConfig.INPUT_FRAME_SIZE)
# ...
with self._listeners_lock:
    for listener in self._audio_listeners:
        listener.on_audio_data(audio_converted.copy())
```
Listeners now receive **float32** data (output of `converter.convert_input`). Thread-safe via `_listeners_lock`.

**Current (HEAD) -- `wake_word_detect.py` `_process_audio`:**
```python
self._stream.accept_waveform(
    sample_rate=self._sample_rate, waveform=audio_data
)
```
The new detector passes audio_data directly to `accept_waveform` **without any dtype conversion**.

**CRITICAL DIFFERENCE:** The old detector had an explicit int16-to-float32 conversion. The new detector removed that conversion because the new audio_codec already sends float32. This is correct for the current pipeline. However, if any code path still sends int16, the new detector would feed raw int16 values to sherpa-onnx, causing detection failure.

---

## Finding 3: Pause/Resume During Speaking State

**Old (`6cad765`):**
- `WakeWordDetector` has `self.paused` flag.
- **Neither the old detector nor the old plugin ever set `self.paused = True` during speaking state.**
- The old `_on_detected` callback in `WakeWordPlugin`:
  ```python
  if self.app.is_speaking():
      await self.app.abort_speaking(AbortReason.WAKE_WORD_DETECTED)
      # clear audio queue
  else:
      await self.app.start_auto_conversation()
  ```
  No pause/resume logic. Detection continued running during TTS playback.

**Current (HEAD):**
- `WakeWordDetector` has `self._paused` flag.
- `_handle_detection` now **sets `self._paused = True`** after detection, then waits 0.3s and drains the queue before unpausing:
  ```python
  self._paused = True
  try:
      # invoke callback
  finally:
      await asyncio.sleep(0.3)
      # drain queue
      self._paused = False
  ```
- The plugin `_on_detected` callback does the same abort/clear logic through new DI interfaces.
- **Explicit `pause()` and `resume()` public methods were added** but are not called by any code in the plugin or elsewhere during speaking state.

**KEY OBSERVATION:** In both old and new code, detection is NOT paused during TTS speaking. The `_paused` flag is only briefly set (0.3s) after a detection fires. The detector keeps running and processing audio while TTS is playing. **There is no explicit pause during speaking state in either version.**

---

## Finding 4: Channel/Frame Handling Differences

**Old (`6cad765`):**
- `audio_codec._input_callback`: Manual downmix + resampling + frame validation inline.
- Frame size check: `if len(audio_data) != AudioConfig.INPUT_FRAME_SIZE: return`
- Converts to int16 before AEC and listener notification.

**Current (HEAD):**
- `audio_codec._input_callback`: Uses `self.converter.convert_input()` which encapsulates downmix + resampling + frame assembly.
- Returns `None` if data insufficient (same semantic).
- Stays float32 throughout; no int16 conversion before listener notification.

**No functional regression** in channel/frame handling. The converter is a refactored equivalent of the old inline logic.

---

## Finding 5: `_on_detected` Callback -- Speaking State Check

**Old (`6cad765`) -- `WakeWordPlugin._on_detected`:**
```python
async def _on_detected(self, wake_word, full_text):
    try:
        if hasattr(self.app, "device_state") and hasattr(self.app, "start_auto_conversation"):
            if self.app.is_speaking():
                await self.app.abort_speaking(AbortReason.WAKE_WORD_DETECTED)
                audio_plugin = self.app.plugins.get_plugin("audio")
                if audio_plugin and audio_plugin.codec:
                    await audio_plugin.codec.clear_audio_queue()
            else:
                await self.app.start_auto_conversation()
    except Exception as e:
        logger.error(...)
```
- Guarded by `hasattr` checks.
- If speaking: abort + clear queue.
- If not speaking: start auto conversation.

**Current (HEAD) -- `WakeWordPlugin._on_detected`:**
```python
async def _on_detected(self, wake_word, full_text):
    try:
        if self._ctx.is_speaking():
            await self._cmd.abort_speaking(AbortReason.WAKE_WORD_DETECTED)
            if self._audio_plugin and self._audio_plugin.codec:
                await self._audio_plugin.codec.clear_audio_queue()
        else:
            await self._cmd.connect_protocol()
            mode = (ListeningMode.REALTIME if ... else ListeningMode.AUTO_STOP)
            await self._cmd.start_listening(mode)
    except Exception as e:
        logger.error(...)
```
- Uses DI interfaces (`self._ctx`, `self._cmd`) instead of direct `self.app`.
- Same logic: if speaking -> abort + clear; else -> start listening.
- **Added `connect_protocol()` call before starting to listen** (new behavior for non-speaking case).
- No `hasattr` guards -- relies on DI contract.

**No functional change to the speaking-state interruption logic itself.** The abort mechanism is semantically identical.

---

## Finding 6: New Post-Detection Pause (Potential Issue)

The current `_handle_detection` introduces a **0.3-second pause + queue drain** that did not exist in the old version:

```python
# Current HEAD only:
self._paused = True
try:
    # invoke callback (which calls abort_speaking)
finally:
    await asyncio.sleep(0.3)
    # drain all queued audio
    self._paused = False
```

In the old code, `_handle_detection_result` simply fired the callback and continued immediately (no pause, no drain).

**Impact:** After a wake word is detected during TTS, the new code:
1. Pauses detection for 0.3s
2. Drains all queued audio

This is a post-detection cooldown. It should not affect the *initial* detection during speaking, but it does mean that if the first detection fails for another reason, the user has a longer window where re-detection is suppressed.

---

## Finding 7: Threading Lock Around sherpa-onnx

The current code wraps all `_keyword_spotter` and `_stream` access in `self._onnx_lock` (a `threading.Lock`):

```python
with self._onnx_lock:
    self._stream.accept_waveform(...)
    if self._keyword_spotter.is_ready(self._stream):
        self._keyword_spotter.decode_stream(self._stream)
        result = self._keyword_spotter.get_result(self._stream)
```

The old code had no such lock. Since `_process_audio` is called from the async detection loop (single-threaded event loop), and `on_audio_data` only enqueues data, the lock itself should not cause deadlocks. However, it does mean that if `_release_model` (called during `stop()/reload()`) is invoked from another thread while `_process_audio` is running, they will contend. This is a safety improvement, not a regression.

---

## Finding 8: Input Stream Continuity During Speaking

In both old and new code, the audio input stream (`sd.InputStream`) runs continuously. It is never stopped or paused during TTS playback. The `_input_callback` always fires and always notifies listeners.

The wake word detector receives audio data regardless of whether TTS is playing. The microphone picks up room audio (including TTS output played through speakers), which is what the wake word detector processes.

**No change here.** The input stream is always active in both versions.

---

## Root Cause Hypothesis

The reported regression ("wake word cannot interrupt TTS on Windows") is **unlikely to be caused by the wake word detection code itself**, since:

1. Detection loop is structurally identical (both polling at 5ms).
2. Audio data flows continuously to the detector in both versions.
3. No pause during speaking state in either version.
4. The `_on_detected` speaking-state check is semantically identical.

**Possible external causes to investigate:**

1. **Audio device behavior on Windows:** The refactored audio codec uses a `converter` abstraction instead of inline processing. If the converter has a bug on Windows (e.g., frame accumulation, dtype mismatch), audio data may not reach the detector.

2. **The `_onnx_lock` under contention:** If something else acquires `_onnx_lock` during TTS playback (e.g., a reload triggered by config change), the detection loop would block.

3. **The `_ctx.is_speaking()` / `_cmd.abort_speaking()` DI chain:** If these new DI interfaces behave differently from the old direct `self.app.is_speaking()` / `self.app.abort_speaking()` on Windows, the abort may silently fail.

4. **Audio input quality during TTS:** On Windows, the microphone might pick up TTS playback through speaker loopback, flooding the detector with TTS audio rather than the user's voice. This is not a code regression but an environmental issue that AEC should handle.

5. **`asyncio.Queue` behavior:** The new code creates the queue lazily in `start()` (`self._audio_queue = asyncio.Queue(maxsize=100)`). The old code created it in `__init__()` (`self._audio_queue = asyncio.Queue(maxsize=100)`). If `on_audio_data` is called before `start()` completes, the `if self._audio_queue is None: return` guard silently drops data.

## Caveats / Not Found

- Could not examine the `converter.convert_input()` implementation in detail (would need to trace `src/audio_codecs/` converter module).
- Could not test actual Windows audio device behavior.
- The `abort_speaking` and `is_speaking` implementations behind the DI interfaces were not compared.
- The `clear_audio_queue` implementation was not compared between versions.
