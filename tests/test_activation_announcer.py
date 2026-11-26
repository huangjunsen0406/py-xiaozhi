"""激活验证码播报器单线程 OutputStream 与防掐断行为测试."""

from __future__ import annotations

import threading

import numpy as np

from src.utils.activation_announcer import ActivationAnnouncer


def test_announcer_retry_does_not_interrupt_and_stops_cleanly(monkeypatch):
    """轮询重试 (interrupt=False) 不得掐断正在播报的验证码，stop() 可快速安全终止."""
    started = threading.Event()
    release = threading.Event()
    writes: list[int] = []
    open_threads: list[int] = []

    class _FakeOutputStream:
        def __init__(self, **_kwargs):
            pass

        def __enter__(self):
            open_threads.append(threading.get_ident())
            started.set()
            return self

        def __exit__(self, *_exc):
            return False

        def write(self, chunk):
            writes.append(len(chunk))
            release.wait(timeout=0.05)

    monkeypatch.setattr("src.utils.activation_announcer.sd.OutputStream", _FakeOutputStream)
    monkeypatch.setattr(
        ActivationAnnouncer,
        "_build_sequence_audio",
        lambda self, names: (np.zeros(24000, dtype=np.float32), 24000),
    )

    announcer = ActivationAnnouncer()
    announcer.announce("708046", interrupt=True)
    assert started.wait(timeout=1.0)
    assert announcer.is_playing

    # 模拟 3 秒轮询重试：不得掐断重开新流
    announcer.announce("708046", interrupt=False)
    assert len(open_threads) == 1
    assert open_threads[0] != threading.get_ident()

    # 激活完成/取消：安全停止并退出线程
    release.set()
    announcer.stop()
    assert not announcer.is_playing
    assert len(writes) >= 1
