import asyncio

from src.application import Application
from src.iot.thing import Parameter, Thing, ValueType


class Speaker(Thing):
    def __init__(self):
        super().__init__("Speaker", "当前 AI 机器人的扬声器")

        # 获取当前显示实例的音量作为初始值
        try:
            app = Application.get_instance()
            self.volume = app.display.current_volume
        except Exception:
            # 如果获取失败，使用默认值
            self.volume = 100  # 默认音量

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
        return self.volume

    async def _set_volume(self, params):
        volume = params["volume"].get_value()
        if 0 <= volume <= 100:
            self.volume = volume
            try:
                app = Application.get_instance()
                # 在单独的线程中运行同步的 update_volume 函数
                await asyncio.to_thread(app.display.update_volume, volume)
                return {"success": True, "message": f"音量已设置为: {volume}"}
            except Exception as e:
                print(f"设置音量失败: {e}")
                return {"success": False, "message": f"设置音量失败: {e}"}
        else:
            raise ValueError("音量必须在0-100之间")
