"""Windows 音量后端（pycaw 新旧 API 兼容）单元测试."""

from __future__ import annotations

import sys
import types

import pytest

from src.mcp.tools.volume.windows import WindowsVolumeBackend


class _FakeEndpointVolume:
    def __init__(self, scalar: float = 0.5) -> None:
        self.scalar = scalar

    def GetMasterVolumeLevelScalar(self) -> float:
        return self.scalar

    def SetMasterVolumeLevelScalar(self, value: float, _ctx) -> None:
        self.scalar = value


def _install_fake_pycaw(monkeypatch, speaker_obj, *, activate_result=None):
    fake_pycaw_mod = types.ModuleType("pycaw.pycaw")

    class _FakeAudioUtilities:
        @staticmethod
        def GetSpeakers():
            return speaker_obj

    class _FakeIAudioEndpointVolume:
        _iid_ = "fake-iid"

    fake_pycaw_mod.AudioUtilities = _FakeAudioUtilities
    fake_pycaw_mod.IAudioEndpointVolume = _FakeIAudioEndpointVolume

    fake_pycaw_pkg = types.ModuleType("pycaw")
    fake_pycaw_pkg.pycaw = fake_pycaw_mod

    fake_comtypes = types.ModuleType("comtypes")
    fake_comtypes.CLSCTX_ALL = 23

    monkeypatch.setitem(sys.modules, "pycaw", fake_pycaw_pkg)
    monkeypatch.setitem(sys.modules, "pycaw.pycaw", fake_pycaw_mod)
    monkeypatch.setitem(sys.modules, "comtypes", fake_comtypes)

    if activate_result is not None:
        monkeypatch.setattr(
            WindowsVolumeBackend,
            "_activate_endpoint_volume",
            staticmethod(lambda raw_dev: activate_result),
        )


def test_windows_volume_new_pycaw_endpoint_volume(monkeypatch):
    """新版 pycaw: AudioDevice 暴露 EndpointVolume（无 Activate）."""
    vol = _FakeEndpointVolume(0.42)

    class _AudioDevice:
        EndpointVolume = vol

    _install_fake_pycaw(monkeypatch, _AudioDevice())

    backend = WindowsVolumeBackend()
    assert backend.get_volume() == 42
    backend.set_volume(75)
    assert vol.scalar == pytest.approx(0.75)


def test_windows_volume_legacy_pycaw_activate(monkeypatch):
    """旧版 pycaw: GetSpeakers() 返回原始 IMMDevice（带 Activate）."""
    vol = _FakeEndpointVolume(0.3)

    class _LegacyIMMDevice:
        def Activate(self, *_args):
            return vol

    _install_fake_pycaw(monkeypatch, _LegacyIMMDevice(), activate_result=vol)

    backend = WindowsVolumeBackend()
    assert backend.get_volume() == 30
    backend.set_volume(60)
    assert vol.scalar == pytest.approx(0.6)


def test_windows_volume_wrapper_dev_fallback(monkeypatch):
    """兜底分支: 包装对象仅通过 _dev 暴露底层 IMMDevice."""
    vol = _FakeEndpointVolume(0.8)

    class _WrappedDevice:
        _dev = object()

    _install_fake_pycaw(monkeypatch, _WrappedDevice(), activate_result=vol)

    backend = WindowsVolumeBackend()
    assert backend.get_volume() == 80


def test_windows_volume_no_default_device_raises(monkeypatch):
    """无默认输出设备时给出明确 RuntimeError."""
    _install_fake_pycaw(monkeypatch, None)
    with pytest.raises(RuntimeError, match="未找到默认 Windows 音频输出设备"):
        WindowsVolumeBackend()
