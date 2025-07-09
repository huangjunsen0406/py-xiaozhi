import asyncio

from src.iot.thing import Parameter, Thing, ValueType
from src.utils.volume_controller import VolumeController


class Speaker(Thing):
    def __init__(self):
        super().__init__("Speaker", "当前 AI 机器人的扬声器")

        # 初始化音量控制器
        self.volume_controller = None
        try:
            if VolumeController.check_dependencies():
                self.volume_controller = VolumeController()
                self.volume = self.volume_controller.get_volume()
            else:
                self.volume = 70  # 默认音量
        except Exception:
            self.volume = 70  # 默认音量

        # 定义属性
        self.add_property("volume", "当前音量值", self.get_volume)

        # 定义方法
        self.add_method(
            "SetVolume",
            "设置音量",
            [Parameter("volume", "0到100之间的整数", ValueType.NUMBER, True)],
            self._set_volume,
        )

    async def get_volume(self):
        # 尝试从音量控制器获取实时音量
        if self.volume_controller:
            try:
                self.volume = self.volume_controller.get_volume()
            except Exception:
                pass
        return self.volume

    async def _set_volume(self, params):
        volume = params["volume"].get_value()
        if 0 <= volume <= 100:
            self.volume = volume
            try:
                # 直接使用VolumeController设置系统音量
                if self.volume_controller:
                    await asyncio.to_thread(self.volume_controller.set_volume, volume)
                else:
                    raise Exception("音量控制器未初始化")

                return {"success": True, "message": f"音量已设置为: {volume}"}
            except Exception as e:
                print(f"设置音量失败: {e}")
                return {"success": False, "message": f"设置音量失败: {e}"}
        else:
            raise ValueError("音量必须在0-100之间")
