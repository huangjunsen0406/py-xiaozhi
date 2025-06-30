from src.iot.thing import Thing


class Lamp(Thing):
    def __init__(self):
        super().__init__("Lamp", "一个测试用的灯")
        self.power = False

        # 定义属性 - 使用异步 getter
        self.add_property("power", "灯是否打开", self.get_power)

        # 定义方法 - 使用异步方法处理器
        self.add_method("TurnOn", "打开灯", [], self._turn_on)

        self.add_method("TurnOff", "关闭灯", [], self._turn_off)

    async def get_power(self):
        return self.power

    async def _turn_on(self, params):
        self.power = True
        return {"status": "success", "message": "灯已打开"}

    async def _turn_off(self, params):
        self.power = False
        return {"status": "success", "message": "灯已关闭"}
