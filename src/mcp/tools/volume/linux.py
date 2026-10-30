"""Linux 音量后端（pactl / wpctl / amixer）; failed measurements raise."""

from __future__ import annotations

import re
import shutil
import subprocess

from src.logging import get_logger

logger = get_logger()


def _run_command(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True, timeout=5)


def _checked_output(cmd: list[str]) -> str:
    result = _run_command(cmd)
    if result.returncode != 0:
        raise RuntimeError(
            f"{cmd[0]} failed ({result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout


class LinuxVolumeBackend:
    def __init__(self) -> None:
        self.linux_tool: str | None = None
        self._init()

    def _init(self) -> None:
        for tool in ("pactl", "wpctl", "amixer"):
            if shutil.which(tool):
                self.linux_tool = tool
                break
        if not self.linux_tool:
            raise RuntimeError("未找到可用的Linux音量控制工具 (pactl/wpctl/amixer)")
        logger.debug(f"Linux音量控制初始化成功，使用: {self.linux_tool}")

    def get_volume(self) -> int:
        tool = self.linux_tool
        if tool == "pactl":
            return self._get_pactl()
        if tool == "wpctl":
            return self._get_wpctl()
        if tool == "amixer":
            return self._get_amixer()
        raise RuntimeError("Linux volume controller is unavailable")

    def set_volume(self, volume: int) -> None:
        tool = self.linux_tool
        if tool == "pactl":
            self._set_pactl(volume)
        elif tool == "wpctl":
            self._set_wpctl(volume)
        elif tool == "amixer":
            self._set_amixer(volume)
        else:
            raise RuntimeError("Linux volume controller is unavailable")

    def _get_pactl(self) -> int:
        output = _checked_output(["pactl", "get-sink-volume", "@DEFAULT_SINK@"])
        match = re.search(r"(\d+)%", output)
        if not match:
            raise RuntimeError("pactl returned no volume measurement")
        return int(match.group(1))

    def _set_pactl(self, volume: int) -> None:
        _checked_output(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"])

    def _get_wpctl(self) -> int:
        output = _checked_output(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
        match = re.search(r"Volume:\s*(\d+(?:\.\d+)?)", output)
        if not match:
            raise RuntimeError("wpctl returned no volume measurement")
        return int(float(match.group(1)) * 100)

    def _set_wpctl(self, volume: int) -> None:
        _checked_output(
            ["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{volume / 100.0:.2f}"]
        )

    def _get_amixer(self) -> int:
        output = _checked_output(["amixer", "get", "Master"])
        match = re.search(r"\[(\d+)%\]", output)
        if not match:
            raise RuntimeError("amixer returned no volume measurement")
        return int(match.group(1))

    def _set_amixer(self, volume: int) -> None:
        _checked_output(["amixer", "sset", "Master", f"{volume}%"])
