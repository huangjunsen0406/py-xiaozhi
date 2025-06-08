import asyncio
from typing import Any, Dict, List

from src.iot.async_thing import AsyncThing
from src.iot.thing import Parameter, ValueType
from src.utils.logging_config import get_logger

logger = get_logger(__name__)


class RobotArm(AsyncThing):
    """模拟机械臂控制器
    
    模拟机械臂操作，包括移动、抓取等耗时操作，用于演示异步IoT架构
    """
    
    def __init__(self):
        super().__init__(
            "RobotArm", 
            "模拟六轴机械臂控制器，支持位置控制、抓取等操作"
        )
        
        # 模拟连接状态（默认连接以便测试）
        self.connected = True
        
        # 状态属性
        self.current_position = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]  # [x, y, z, rx, ry, rz]
        self.is_moving = False
        self.gripper_open = True
        self.is_busy = False
        
        # 模拟参数
        self.move_speed_multiplier = 0.1  # 移动速度倍数（秒/单位距离）
        self.gripper_delay = 1.0  # 夹爪操作延时（秒）
        
        # 注册属性和方法
        self._register_properties()
        self._register_methods()
        
        logger.info("模拟机械臂控制器初始化完成")
    
    def _register_properties(self):
        """注册机械臂属性"""
        self.add_property("connected", "连接状态", lambda: self.connected)
        self.add_property("is_moving", "是否正在移动", lambda: self.is_moving)
        self.add_property("is_busy", "是否繁忙", lambda: self.is_busy)
        self.add_property("gripper_open", "夹爪状态", lambda: self.gripper_open)
        self.add_property(
            "current_position", 
            "当前位置 [x,y,z,rx,ry,rz]", 
            lambda: self.current_position
        )
    
    def _register_methods(self):
        """注册机械臂方法"""
        # 连接控制
        self.add_async_method(
            "Connect", "连接机械臂，启动机器人", [], 
            lambda params: self._connect()
        )
        
        self.add_async_method(
            "Disconnect", "断开机械臂连接", [], 
            lambda params: self._disconnect()
        )
        
        # 移动控制
        self.add_async_method(
            "MoveToPosition", "移动到指定位置",
            [
                Parameter("x", "X坐标", ValueType.FLOAT, True),
                Parameter("y", "Y坐标", ValueType.FLOAT, True),
                Parameter("z", "Z坐标", ValueType.FLOAT, True),
                Parameter("rx", "X轴旋转", ValueType.FLOAT, False),
                Parameter("ry", "Y轴旋转", ValueType.FLOAT, False),
                Parameter("rz", "Z轴旋转", ValueType.FLOAT, False),
                Parameter("speed", "移动速度 (0-100)", ValueType.NUMBER, False)
            ],
            lambda params: self._move_to_position(params)
        )
        
        # 夹爪控制
        self.add_async_method(
            "OpenGripper", "打开夹爪", [], 
            lambda params: self._control_gripper(True)
        )
        
        self.add_async_method(
            "CloseGripper", "关闭夹爪", [], 
            lambda params: self._control_gripper(False)
        )
        
        # 复合操作
        self.add_async_method(
            "PickAndPlace", "抓取并放置",
            [
                Parameter("pick_x", "抓取X坐标", ValueType.FLOAT, True),
                Parameter("pick_y", "抓取Y坐标", ValueType.FLOAT, True),
                Parameter("pick_z", "抓取Z坐标", ValueType.FLOAT, True),
                Parameter("place_x", "放置X坐标", ValueType.FLOAT, True),
                Parameter("place_y", "放置Y坐标", ValueType.FLOAT, True),
                Parameter("place_z", "放置Z坐标", ValueType.FLOAT, True),
            ],
            lambda params: self._pick_and_place(params)
        )
        
        # 任务状态查询
        self.add_sync_method(
            "GetTaskStatus", "获取任务状态",
            [Parameter("task_name", "任务名称", ValueType.STRING, True)],
            lambda params: self.get_task_status(params["task_name"].get_value())
        )
        
        self.add_sync_method(
            "CancelTask", "取消任务",
            [Parameter("task_name", "任务名称", ValueType.STRING, True)],
            lambda params: self.cancel_task(params["task_name"].get_value())
        )
        
        # 测试方法
        self.add_async_method(
            "Test", "测试机械臂响应", [],
            lambda params: self._test()
        )
    
    async def _connect(self) -> Dict[str, Any]:
        """模拟连接机械臂"""
        if self.connected:
            return {"success": True, "message": "已经连接"}
        
        try:
            logger.info("正在模拟连接机械臂...")
            
            # 模拟连接延时
            await asyncio.sleep(1.0)
            
            # 模拟初始化
            await asyncio.sleep(0.5)
            
            self.connected = True
            logger.info("模拟机械臂连接成功")
            return {"success": True, "message": "连接成功"}
                
        except Exception as e:
            logger.error(f"模拟连接失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _disconnect(self) -> Dict[str, Any]:
        """模拟断开连接"""
        if not self.connected:
            return {"success": True, "message": "未连接"}
        
        try:
            # 模拟断开延时
            await asyncio.sleep(0.5)
            self.connected = False
            logger.info("模拟机械臂断开连接")
            return {"success": True, "message": "断开连接成功"}
        except Exception as e:
            logger.error(f"模拟断开连接失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _move_to_position(self, params: Dict) -> Dict[str, Any]:
        """移动到指定位置"""
        if not self.connected:
            return {"success": False, "error": "未连接"}
        
        if self.is_busy:
            return {"success": False, "error": "机械臂正忙"}
        
        try:
            # 提取参数
            target_pos = [
                params["x"].get_value(),
                params["y"].get_value(), 
                params["z"].get_value(),
                params.get("rx", Parameter("", "", "", False)).get_value() or 0,
                params.get("ry", Parameter("", "", "", False)).get_value() or 0,
                params.get("rz", Parameter("", "", "", False)).get_value() or 0,
            ]
            speed = params.get("speed", Parameter("", "", "", False)).get_value() or 50
            
            # 启动后台移动任务
            task_name = f"move_{int(asyncio.get_event_loop().time())}"
            self.start_background_task(
                task_name, 
                self._execute_movement(target_pos, speed)
            )
            
            return {
                "success": True, 
                "message": "开始移动", 
                "task_id": task_name,
                "target_position": target_pos
            }
            
        except Exception as e:
            logger.error(f"移动命令失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _execute_movement(self, target_pos: List[float], speed: int):
        """执行移动操作（后台任务）"""
        self.is_moving = True
        self.is_busy = True
        
        try:
            # 计算移动距离和时间
            current = self.current_position
            distance = sum((target_pos[i] - current[i]) ** 2 for i in range(3)) ** 0.5
            move_time = max(0.5, distance * self.move_speed_multiplier * (100 / speed))
            
            logger.info(f"开始移动到 {target_pos}，预计用时 {move_time:.1f}秒")
            
            # 模拟移动过程（分步更新位置）
            steps = max(10, int(move_time * 10))  # 每100ms更新一次位置
            for step in range(steps + 1):
                progress = step / steps
                # 线性插值计算当前位置
                for i in range(6):
                    self.current_position[i] = (
                        current[i] + (target_pos[i] - current[i]) * progress
                    )
                await asyncio.sleep(move_time / steps)
            
            # 确保最终位置准确
            self.current_position = target_pos.copy()
            logger.info(f"移动完成: {target_pos}")
            return {"success": True, "final_position": target_pos}
            
        except Exception as e:
            logger.error(f"移动执行失败: {e}")
            raise
        finally:
            self.is_moving = False
            self.is_busy = False
    
    async def _control_gripper(self, open_gripper: bool) -> Dict[str, Any]:
        """模拟控制夹爪"""
        if not self.connected:
            return {"success": False, "error": "未连接"}
        
        try:
            action = "打开" if open_gripper else "关闭"
            logger.info(f"开始{action}夹爪...")
            
            # 模拟夹爪操作延时
            await asyncio.sleep(self.gripper_delay)
            
            self.gripper_open = open_gripper
            logger.info(f"夹爪{action}成功")
            return {"success": True, "message": f"夹爪{action}成功"}
                
        except Exception as e:
            logger.error(f"夹爪控制失败: {e}")
            return {"success": False, "error": str(e)}
    
    async def _pick_and_place(self, params: Dict) -> Dict[str, Any]:
        """抓取并放置（复合操作）"""
        if not self.connected:
            return {"success": False, "error": "未连接"}
        
        if self.is_busy:
            return {"success": False, "error": "机械臂正忙"}
        
        # 启动后台任务
        task_name = f"pick_place_{int(asyncio.get_event_loop().time())}"
        pick_pos = [
            params["pick_x"].get_value(),
            params["pick_y"].get_value(),
            params["pick_z"].get_value(),
            0, 0, 0
        ]
        place_pos = [
            params["place_x"].get_value(),
            params["place_y"].get_value(),
            params["place_z"].get_value(),
            0, 0, 0
        ]
        
        self.start_background_task(
            task_name,
            self._execute_pick_and_place(pick_pos, place_pos)
        )
        
        return {
            "success": True,
            "message": "开始抓取放置操作",
            "task_id": task_name
        }
    
    async def _execute_pick_and_place(self, pick_pos: List[float], place_pos: List[float]):
        """执行抓取放置操作"""
        self.is_busy = True
        
        try:
            logger.info("开始执行抓取放置操作...")
            
            # 1. 移动到抓取位置上方
            hover_pick = pick_pos.copy()
            hover_pick[2] += 50  # 高50mm
            await self._execute_movement(hover_pick, 50)
            
            # 2. 下降到抓取位置
            await self._execute_movement(pick_pos, 20)
            
            # 3. 关闭夹爪
            await self._control_gripper(False)
            await asyncio.sleep(0.5)
            
            # 4. 提升
            await self._execute_movement(hover_pick, 30)
            
            # 5. 移动到放置位置上方
            hover_place = place_pos.copy()
            hover_place[2] += 50
            await self._execute_movement(hover_place, 50)
            
            # 6. 下降到放置位置
            await self._execute_movement(place_pos, 20)
            
            # 7. 打开夹爪
            await self._control_gripper(True)
            await asyncio.sleep(0.5)
            
            # 8. 提升
            await self._execute_movement(hover_place, 30)
            
            logger.info("抓取放置操作完成")
            return {"success": True, "message": "抓取放置完成"}
            
        except Exception as e:
            logger.error(f"抓取放置操作失败: {e}")
            raise
        finally:
            self.is_busy = False
    
    async def _test(self) -> Dict[str, Any]:
        """测试机械臂响应"""
        await asyncio.sleep(1.0)
        return {
            "success": True, 
            "message": f"机械臂测试成功！状态：{'已连接' if self.connected else '未连接'}",
            "position": self.current_position,
            "gripper": "打开" if self.gripper_open else "关闭"
        }

    async def cleanup(self):
        """清理资源"""
        await super().cleanup()
        self.connected = False 