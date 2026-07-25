"""Linux 音量后端（pactl / wpctl / amixer）."""

from __future__ import annotations

import re
import shutil
import subprocess

from src.logging import get_logger

logger = get_logger()

DEFAULT_VOLUME = 70


def _run_command(
    cmd: list[str], *, check: bool = False
) -> subprocess.CompletedProcess | None:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, check=check)
    except Exception as e:
        logger.debug(f"执行命令失败 {' '.join(cmd)}: {e}")
        return None


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
            logger.error("未找到可用的Linux音量控制工具 (pactl/wpctl/amixer)")
            raise Exception("未找到可用的Linux音量控制工具")

        logger.debug(f"Linux音量控制初始化成功，使用: {self.linux_tool}")

    def get_volume(self) -> int:
        tool = self.linux_tool
        if tool == "pactl":
            return self._get_pactl()
        if tool == "wpctl":
            return self._get_wpctl()
        if tool == "amixer":
            return self._get_amixer()
        return DEFAULT_VOLUME

    def set_volume(self, volume: int) -> None:
        tool = self.linux_tool
        if tool == "pactl":
            self._set_pactl(volume)
        elif tool == "wpctl":
            self._set_wpctl(volume)
        elif tool == "amixer":
            self._set_amixer(volume)

    def _get_pactl(self) -> int:
        try:
            result = _run_command(["pactl", "list", "sinks"])
            if result and result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "Volume:" in line:
                        match = re.search(r"(\d+)%", line)
                        if match:
                            volume = int(match.group(1))
                            logger.debug(f"pactl获取音量成功: {volume}%")
                            return volume
                logger.warning("pactl输出中未找到音量信息")
            else:
                logger.warning(
                    f"pactl命令执行失败: {result.returncode if result else 'None'}"
                )
        except Exception as e:
            logger.warning(f"通过pactl获取音量失败: {e}", exc_info=True)
        return DEFAULT_VOLUME

    def _set_pactl(self, volume: int) -> None:
        try:
            result = _run_command(
                ["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{volume}%"]
            )
            if result and result.returncode == 0:
                logger.debug(f"pactl设置音量成功: {volume}%")
            else:
                logger.warning(
                    f"pactl设置音量失败: {result.returncode if result else 'None'}"
                )
        except Exception as e:
            logger.warning(f"通过pactl设置音量失败: {e}", exc_info=True)

    def _get_wpctl(self) -> int:
        try:
            result = _run_command(["wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@"])
            if result and result.returncode == 0:
                match = re.search(r"(\d+\.?\d*)", result.stdout)
                if match:
                    volume = int(float(match.group(1)) * 100)
                    logger.debug(f"wpctl获取音量成功: {volume}%")
                    return volume
                logger.warning(f"wpctl输出格式无法解析: {result.stdout}")
            else:
                logger.warning(
                    f"wpctl命令执行失败: {result.returncode if result else 'None'}"
                )
        except Exception as e:
            logger.warning(f"通过wpctl获取音量失败: {e}", exc_info=True)
        return DEFAULT_VOLUME

    def _set_wpctl(self, volume: int) -> None:
        try:
            result = _run_command(
                [
                    "wpctl",
                    "set-volume",
                    "@DEFAULT_AUDIO_SINK@",
                    f"{volume / 100.0:.2f}",
                ]
            )
            if result and result.returncode == 0:
                logger.debug(f"wpctl设置音量成功: {volume}%")
            else:
                logger.warning(
                    f"wpctl设置音量失败: {result.returncode if result else 'None'}"
                )
        except Exception as e:
            logger.warning(f"通过wpctl设置音量失败: {e}", exc_info=True)

    def _get_amixer(self) -> int:
        try:
            result = _run_command(["amixer", "get", "Master"])
            if result and result.returncode == 0:
                match = re.search(r"\[(\d+)%\]", result.stdout)
                if match:
                    volume = int(match.group(1))
                    logger.debug(f"amixer获取音量成功: {volume}%")
                    return volume
                logger.warning(f"amixer输出格式无法解析: {result.stdout}")
            else:
                logger.warning(
                    f"amixer命令执行失败: {result.returncode if result else 'None'}"
                )
        except Exception as e:
            logger.warning(f"通过amixer获取音量失败: {e}", exc_info=True)
        return DEFAULT_VOLUME

    def _set_amixer(self, volume: int) -> None:
        try:
            result = _run_command(["amixer", "sset", "Master", f"{volume}%"])
            if result and result.returncode == 0:
                logger.debug(f"amixer设置音量成功: {volume}%")
            else:
                logger.warning(
                    f"amixer设置音量失败: {result.returncode if result else 'None'}"
                )
        except Exception as e:
            logger.warning(f"通过amixer设置音量失败: {e}", exc_info=True)
