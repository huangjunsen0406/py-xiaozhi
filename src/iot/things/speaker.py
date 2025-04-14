from src.application import Application
from src.iot.thing import Thing, Parameter, ValueType


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
        self.add_property("volume", "当前音量值", lambda: self.volume)

        # 定义方法
        self.add_method(
            "SetVolume", 
            "设置音量",
            [Parameter("volume", "0到100之间的整数", ValueType.NUMBER, True)],
            lambda params: self._set_volume(params["volume"].get_value())
        )

    def _set_volume(self, volume):
        if 0 <= volume <= 100:
            self.volume = volume
            try:
                app = Application.get_instance()
                app.display.update_volume(volume)
                return {"success": True, "message": f"音量已设置为: {volume}"}
            except Exception as e:
                print(f"设置音量失败: {e}")
                return {"success": False, "message": f"设置音量失败: {e}"}
        else:
            raise ValueError("音量必须在0-100之间")