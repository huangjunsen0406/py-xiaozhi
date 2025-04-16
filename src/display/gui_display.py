import threading
import tkinter as tk
from tkinter import ttk, messagebox
import queue
import time
from typing import Optional, Callable
from pynput import keyboard as pynput_keyboard

from src.display.base_display import BaseDisplay
from src.utils.logging_config import get_logger
from src.utils.config_manager import ConfigManager


class GuiDisplay(BaseDisplay):
    def __init__(self):
        super().__init__()  # 调用父类初始化
        """创建 GUI 界面"""
        # 初始化日志
        self.logger = get_logger(__name__)

        # 初始化配置管理器
        self.config_manager = ConfigManager.get_instance()

        # 创建主窗口
        self.root = tk.Tk()
        self.root.title("小智Ai语音控制")
        self.root.geometry("350x400")  # 增大默认窗口尺寸
        self.root.minsize(350, 400)  # 设置最小窗口尺寸

        # 创建标签页控件
        self.notebook = ttk.Notebook(self.root)
        self.notebook.pack(expand=True, fill='both')

        # 创建主页面
        self.main_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.main_frame, text="主界面")

        # 创建配置页面
        self.config_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.config_frame, text="配置")
        
        # 初始化主页面内容
        self._init_main_page()
        
        # 初始化配置页面内容
        self._init_config_page()

        # 回调函数
        self.button_press_callback = None
        self.button_release_callback = None
        self.status_update_callback = None
        self.text_update_callback = None
        self.emotion_update_callback = None
        self.mode_callback = None
        self.auto_callback = None
        self.abort_callback = None

        # 更新队列
        self.update_queue = queue.Queue()

        # 运行标志
        self._running = True

        # 设置窗口关闭处理
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

        # 启动更新处理
        self.root.after(100, self._process_updates)

        # 键盘监听器
        self.keyboard_listener = None

    def _init_main_page(self):
        """初始化主页面内容"""
        # 状态显示
        self.status_frame = ttk.Frame(self.main_frame)
        self.status_frame.pack(pady=10)
        self.status_label = ttk.Label(self.status_frame, text="状态: 未连接")
        self.status_label.pack(side=tk.LEFT)

        # 表情显示
        self.emotion_label = tk.Label(
            self.main_frame, 
            text="😊", 
            font=("Segoe UI Emoji", 16)
        )
        self.emotion_label.pack(padx=20, pady=20)

        # TTS文本显示
        self.tts_text_label = ttk.Label(self.main_frame, text="待命", wraplength=250)
        self.tts_text_label.pack(padx=20, pady=10)

        # 音量控制
        self.volume_frame = ttk.Frame(self.main_frame)
        self.volume_frame.pack(pady=10)
        ttk.Label(self.volume_frame, text="音量:").pack(side=tk.LEFT)
        
        # 添加音量更新节流
        self.volume_update_timer = None
        self.volume_scale = ttk.Scale(
            self.volume_frame,
            from_=0,
            to=100,
            command=self._on_volume_change
        )
        self.volume_scale.set(self.current_volume)
        self.volume_scale.pack(side=tk.LEFT, padx=10)

        # 控制按钮
        self.btn_frame = ttk.Frame(self.main_frame)
        self.btn_frame.pack(pady=20)
        
        # 手动模式按钮 - 默认显示
        self.manual_btn = ttk.Button(self.btn_frame, text="按住说话")
        self.manual_btn.bind("<ButtonPress-1>", self._on_manual_button_press)
        self.manual_btn.bind("<ButtonRelease-1>", self._on_manual_button_release)
        self.manual_btn.pack(side=tk.LEFT, padx=10)
        
        # 打断按钮 - 放在中间
        self.abort_btn = ttk.Button(
            self.btn_frame, 
            text="打断", 
            command=self._on_abort_button_click
        )
        self.abort_btn.pack(side=tk.LEFT, padx=10)
        
        # 自动模式按钮 - 默认隐藏
        self.auto_btn = ttk.Button(
            self.btn_frame, 
            text="开始对话", 
            command=self._on_auto_button_click
        )
        # 不立即pack，等切换到自动模式时再显示
        
        # 模式切换按钮
        self.mode_btn = ttk.Button(
            self.btn_frame, 
            text="手动对话", 
            command=self._on_mode_button_click
        )
        self.mode_btn.pack(side=tk.LEFT, padx=10)
        
        # 对话模式标志
        self.auto_mode = False

    def _init_config_page(self):
        """初始化配置页面内容"""
        # 创建外部框架来包含Canvas和滚动条
        outer_frame = ttk.Frame(self.config_frame)
        outer_frame.pack(fill='both', expand=True)
        
        # 创建一个带滚动条的框架
        self.config_canvas = tk.Canvas(outer_frame, highlightthickness=0)
        scrollbar = ttk.Scrollbar(
            outer_frame, 
            orient="vertical", 
            command=self.config_canvas.yview
        )
        self.scrollable_frame = ttk.Frame(self.config_canvas)
        
        # 设置框架的ID，用于绑定事件
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self._configure_scroll_region()
        )
        
        # 创建窗口并配置滚动区域
        self.config_canvas.create_window(
            (0, 0),
            window=self.scrollable_frame,
            anchor="nw",
            tags="self.scrollable_frame"
        )
        self.config_canvas.configure(yscrollcommand=scrollbar.set)
        
        # 确保canvas填充整个区域并随窗口调整大小
        self.config_canvas.pack(side="left", fill="both", expand=True)
        scrollbar.pack(side="right", fill="y")
        
        # 添加主要配置组件
        self._add_config_sections()
        
        # 添加保存按钮
        save_btn = ttk.Button(
            self.scrollable_frame, 
            text="保存配置", 
            command=self._save_config
        )
        save_btn.pack(pady=20)
        
        # 绑定调整大小事件
        self.config_frame.bind("<Configure>", self._on_frame_configure)
        
        # 绑定鼠标滚轮事件到canvas
        self.config_canvas.bind("<MouseWheel>", self._on_mousewheel)  # Windows
        self.config_canvas.bind("<Button-4>", self._on_mousewheel)    # Linux上滚
        self.config_canvas.bind("<Button-5>", self._on_mousewheel)    # Linux下滚
        
        # 初始设置Canvas高度，避免自动调整
        self.config_canvas.configure(height=500)
        self._height_configured = False
        
        # 绑定标签页切换事件，处理切换到配置页面时的初始化
        self.notebook.bind("<<NotebookTabChanged>>", self._on_tab_changed)
    
    def _on_frame_configure(self, event):
        """当frame大小改变时，调整canvas的大小和滚动区域"""
        try:
            # 使用定时器防止频繁更新
            if hasattr(self, '_frame_timer') and self._frame_timer:
                self.root.after_cancel(self._frame_timer)
            
            # 延迟200ms执行更新，减少界面闪烁
            self._frame_timer = self.root.after(200, lambda: self._update_canvas_size(event.width))
        except Exception as e:
            self.logger.error(f"Frame配置错误: {e}")
    
    def _update_canvas_size(self, width):
        """更新canvas大小，减少频繁刷新"""
        try:
            # 清除计时器标记
            self._frame_timer = None
            
            # 更新canvas宽度
            canvas_width = width - 20  # 减去滚动条宽度的估计值
            
            # 仅当宽度变化超过阈值时才更新
            if not hasattr(self, '_last_canvas_width') or abs(self._last_canvas_width - canvas_width) > 5:
                self._last_canvas_width = canvas_width
                self.config_canvas.configure(width=canvas_width)
                
                # 重新配置滚动区域，但不调整子控件大小
                self._configure_scroll_region(False)
        except Exception as e:
            self.logger.error(f"更新Canvas大小错误: {e}")
    
    def _configure_scroll_region(self, update_height=True):
        """配置滚动区域以包含整个框架"""
        try:
            # 确保滚动区域包含所有内容
            self.config_canvas.configure(
                scrollregion=self.config_canvas.bbox("all")
            )
            
            # 如果需要更新高度，则更新
            if update_height and not hasattr(self, '_height_configured'):
                # 配置最小canvas高度
                content_height = self.scrollable_frame.winfo_reqheight()
                if content_height > 100:  # 只有当内容高度合理时才更新
                    # 固定高度，避免反复调整
                    self.config_canvas.configure(height=500)
                    self._height_configured = True
        except Exception as e:
            self.logger.error(f"滚动区域配置错误: {e}")
    
    def _on_mousewheel(self, event):
        """处理鼠标滚轮事件"""
        # 这里使用简化的处理逻辑，避免复杂判断导致的可能问题
        try:
            # Windows - event.delta: 正值表示向上滚动，负值表示向下滚动
            if hasattr(event, 'delta'):
                delta = -1 if event.delta < 0 else 1
                self.config_canvas.yview_scroll(-delta, "units")
            # Linux - event.num: 4表示向上滚动，5表示向下滚动
            elif hasattr(event, 'num'):
                delta = 1 if event.num == 4 else -1
                self.config_canvas.yview_scroll(delta, "units")
            return "break"  # 阻止事件继续传播
        except Exception as e:
            self.logger.error(f"鼠标滚轮事件处理错误: {e}")
            return "break"
            
    def _add_config_sections(self):
        """添加配置部分"""
        # 加载当前配置
        config = self.config_manager._config
        
        # 创建配置控件字典，用于保存和更新
        self.config_widgets = {}
        
        # SYSTEM_OPTIONS 部分
        self._add_section_title("系统设置")
        
        # CLIENT_ID
        client_id = config.get("SYSTEM_OPTIONS", {}).get("CLIENT_ID", "")
        self._add_config_entry("客户端ID", client_id, "SYSTEM_OPTIONS.CLIENT_ID")
        
        # DEVICE_ID
        device_id = config.get("SYSTEM_OPTIONS", {}).get("DEVICE_ID", "")
        self._add_config_entry("设备ID", device_id, "SYSTEM_OPTIONS.DEVICE_ID")
        
        # OTA版本URL
        ota_url = config.get("SYSTEM_OPTIONS", {}).get("NETWORK", {}).get("OTA_VERSION_URL", "")
        self._add_config_entry("OTA版本URL", ota_url, "SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL")
        
        # 网络设置
        self._add_subsection_title("网络设置")
        
        # WebSocket URL
        ws_url = config.get("SYSTEM_OPTIONS", {}).get("NETWORK", {}).get("WEBSOCKET_URL", "")
        self._add_config_entry("WebSocket URL", ws_url, "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_URL")
        
        # WebSocket Token
        ws_token = config.get("SYSTEM_OPTIONS", {}).get("NETWORK", {}).get("WEBSOCKET_ACCESS_TOKEN", "")
        self._add_config_entry("WebSocket Token", ws_token, "SYSTEM_OPTIONS.NETWORK.WEBSOCKET_ACCESS_TOKEN")
        
        # MQTT 设置
        if config.get("SYSTEM_OPTIONS", {}).get("NETWORK", {}).get("MQTT_INFO"):
            self._add_subsection_title("MQTT 设置")
            mqtt_info = config.get("SYSTEM_OPTIONS", {}).get("NETWORK", {}).get("MQTT_INFO", {})
            self._add_config_entry("Endpoint", mqtt_info.get("endpoint", ""), 
                                  "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.endpoint")
            self._add_config_entry("Client ID", mqtt_info.get("client_id", ""), 
                                  "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.client_id")
            self._add_config_entry("用户名", mqtt_info.get("username", ""), 
                                  "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.username")
            self._add_config_entry("密码", mqtt_info.get("password", ""), 
                                  "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.password")
            self._add_config_entry("发布主题", mqtt_info.get("publish_topic", ""), 
                                  "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.publish_topic")
            self._add_config_entry("订阅主题", mqtt_info.get("subscribe_topic", ""), 
                                  "SYSTEM_OPTIONS.NETWORK.MQTT_INFO.subscribe_topic")
        
        # 唤醒词设置
        self._add_section_title("唤醒词设置")
        
        # 是否使用唤醒词
        use_wake_word = config.get("WAKE_WORD_OPTIONS", {}).get("USE_WAKE_WORD", False)
        self._add_config_checkbox("使用唤醒词", use_wake_word, "WAKE_WORD_OPTIONS.USE_WAKE_WORD")
        
        # 唤醒词列表
        wake_words = config.get("WAKE_WORD_OPTIONS", {}).get("WAKE_WORDS", [])
        wake_words_str = ", ".join(wake_words)
        self._add_config_entry(
            "唤醒词列表(逗号分隔)", 
            wake_words_str, 
            "WAKE_WORD_OPTIONS.WAKE_WORDS", 
            is_list=True
        )

        # 摄像头设置
        self._add_section_title("摄像头设置")
        
        camera_config = config.get("CAMERA", {})
        self._add_config_entry("摄像头索引", camera_config.get("camera_index", 0), 
                              "CAMERA.camera_index", is_int=True)
        self._add_config_entry("宽度", camera_config.get("frame_width", 640), 
                              "CAMERA.frame_width", is_int=True)
        self._add_config_entry("高度", camera_config.get("frame_height", 480), 
                              "CAMERA.frame_height", is_int=True)
        self._add_config_entry("帧率", camera_config.get("fps", 30), 
                              "CAMERA.fps", is_int=True)
        self._add_config_entry("视觉服务URL", camera_config.get("Loacl_VL_url", ""), 
                              "CAMERA.Loacl_VL_url")
        self._add_config_entry("视觉API密钥", camera_config.get("VLapi_key", ""), 
                              "CAMERA.VLapi_key")
        self._add_config_entry("视觉模型", camera_config.get("models", ""), 
                              "CAMERA.models")
    
    def _add_section_title(self, title):
        """添加配置部分标题"""
        label = ttk.Label(self.scrollable_frame, text=title, font=("TkDefaultFont", 12, "bold"))
        label.pack(anchor="w", padx=10, pady=(15, 5))
        ttk.Separator(self.scrollable_frame, orient='horizontal').pack(fill='x', padx=5, pady=5)
    
    def _add_subsection_title(self, title):
        """添加配置子部分标题"""
        label = ttk.Label(self.scrollable_frame, text=title, font=("TkDefaultFont", 10, "bold"))
        label.pack(anchor="w", padx=20, pady=(10, 5))
    
    def _add_readonly_entry(self, label_text, value, config_path):
        """添加只读配置项（为兼容性保留，但实际上使其可编辑）"""
        # 调用可编辑的版本，保持向后兼容
        self._add_config_entry(label_text, value, config_path)
    
    def _add_config_entry(self, label_text, value, config_path, is_int=False, is_list=False):
        """添加配置输入项"""
        frame = ttk.Frame(self.scrollable_frame)
        frame.pack(fill='x', padx=20, pady=5)
        
        label = ttk.Label(frame, text=label_text, width=15)
        label.pack(side=tk.LEFT, padx=(0, 10))
        
        entry = ttk.Entry(frame, width=30)
        entry.insert(0, str(value))
        entry.pack(side=tk.LEFT, fill='x', expand=True)
        
        # 保存控件和元数据
        self.config_widgets[config_path] = {
            'widget': entry,
            'type': 'entry',
            'is_int': is_int,
            'is_list': is_list
        }
    
    def _add_config_checkbox(self, label_text, value, config_path):
        """添加配置复选框"""
        frame = ttk.Frame(self.scrollable_frame)
        frame.pack(fill='x', padx=20, pady=5)
        
        var = tk.BooleanVar(value=bool(value))
        checkbox = ttk.Checkbutton(frame, text=label_text, variable=var)
        checkbox.pack(anchor="w")
        
        # 保存控件和元数据
        self.config_widgets[config_path] = {
            'widget': var,
            'type': 'checkbox'
        }
    
    def _add_config_slider(self, label_text, value, config_path, min_val, max_val, step):
        """添加配置滑块"""
        frame = ttk.Frame(self.scrollable_frame)
        frame.pack(fill='x', padx=20, pady=5)
        
        label = ttk.Label(frame, text=label_text)
        label.pack(anchor="w")
        
        # 创建包含滑块和值显示的框架
        slider_frame = ttk.Frame(frame)
        slider_frame.pack(fill='x', pady=5)
        
        # 创建值显示标签
        value_var = tk.StringVar(value=str(value))
        value_label = ttk.Label(slider_frame, textvariable=value_var, width=5)
        value_label.pack(side=tk.RIGHT)
        
        # 创建滑块
        slider = ttk.Scale(
            slider_frame,
            from_=min_val,
            to=max_val,
            command=lambda v: value_var.set(f"{float(v):.1f}")
        )
        slider.set(float(value))
        slider.pack(side=tk.LEFT, fill='x', expand=True, padx=(0, 10))
        
        # 保存控件和元数据
        self.config_widgets[config_path] = {
            'widget': slider,
            'type': 'slider',
            'value_var': value_var
        }
    
    def _save_config(self):
        """保存配置到文件"""
        try:
            # 遍历所有配置控件，更新配置
            for config_path, widget_info in self.config_widgets.items():
                widget_type = widget_info['type']
                widget = widget_info['widget']
                
                if widget_type == 'entry':
                    value = widget.get()
                    
                    # 处理整数类型
                    if widget_info.get('is_int', False):
                        try:
                            value = int(value)
                        except ValueError:
                            messagebox.showerror("错误", f"{config_path} 必须是一个整数")
                            return
                    
                    # 处理列表类型
                    if widget_info.get('is_list', False):
                        value = [item.strip() for item in value.split(',') if item.strip()]
                    
                elif widget_type == 'checkbox':
                    value = widget.get()
                
                elif widget_type == 'slider':
                    value = float(widget.get())
                
                # 更新配置
                self.config_manager.update_config(config_path, value)
            
            # 显示成功消息
            messagebox.showinfo("成功", "配置已保存")
            
            # 记录日志
            self.logger.info("配置已成功保存")
            
        except Exception as e:
            messagebox.showerror("错误", f"保存配置时发生错误: {e}")
            self.logger.error(f"保存配置失败: {e}")

    def set_callbacks(self,
                      press_callback: Optional[Callable] = None,
                      release_callback: Optional[Callable] = None,
                      status_callback: Optional[Callable] = None,
                      text_callback: Optional[Callable] = None,
                      emotion_callback: Optional[Callable] = None,
                      mode_callback: Optional[Callable] = None,
                      auto_callback: Optional[Callable] = None,
                      abort_callback: Optional[Callable] = None):
        """设置回调函数"""
        self.button_press_callback = press_callback
        self.button_release_callback = release_callback
        self.status_update_callback = status_callback
        self.text_update_callback = text_callback
        self.emotion_update_callback = emotion_callback
        self.mode_callback = mode_callback
        self.auto_callback = auto_callback
        self.abort_callback = abort_callback


    def _process_updates(self):
        """处理更新队列"""
        try:
            while True:
                try:
                    # 非阻塞方式获取更新
                    update_func = self.update_queue.get_nowait()
                    update_func()
                    self.update_queue.task_done()
                except queue.Empty:
                    break
        finally:
            if self._running:
                self.root.after(100, self._process_updates)

    def _on_manual_button_press(self, event):
        """手动模式按钮按下事件处理"""
        try:
            # 更新按钮文本为"松开以停止"
            self.manual_btn.config(text="松开以停止")
            
            # 调用回调函数
            if self.button_press_callback:
                self.button_press_callback()
        except Exception as e:
            self.logger.error(f"按钮按下回调执行失败: {e}")

    def _on_manual_button_release(self, event):
        """手动模式按钮释放事件处理"""
        try:
            # 更新按钮文本为"按住说话"
            self.manual_btn.config(text="按住说话")
            
            # 调用回调函数
            if self.button_release_callback:
                self.button_release_callback()
        except Exception as e:
            self.logger.error(f"按钮释放回调执行失败: {e}")
            
    def _on_auto_button_click(self):
        """自动模式按钮点击事件处理"""
        try:
            if self.auto_callback:
                self.auto_callback()
        except Exception as e:
            self.logger.error(f"自动模式按钮回调执行失败: {e}")

    def _on_abort_button_click(self):
        """打断按钮点击事件处理"""
        try:
            if self.abort_callback:
                self.abort_callback()
        except Exception as e:
            self.logger.error(f"打断按钮回调执行失败: {e}")

    def _on_mode_button_click(self):
        """对话模式切换按钮点击事件"""
        try:
            # 检查是否可以切换模式（通过回调函数询问应用程序当前状态）
            if self.mode_callback:
                # 如果回调函数返回False，表示当前不能切换模式
                if not self.mode_callback(not self.auto_mode):
                    return
                    
            # 切换模式
            self.auto_mode = not self.auto_mode
            
            # 更新按钮显示
            if self.auto_mode:
                # 切换到自动模式
                self.update_mode_button_status("自动对话")
                
                # 隐藏手动按钮，显示自动按钮
                self.update_queue.put(lambda: self._switch_to_auto_mode())
            else:
                # 切换到手动模式
                self.update_mode_button_status("手动对话")
                
                # 隐藏自动按钮，显示手动按钮
                self.update_queue.put(lambda: self._switch_to_manual_mode())
                
        except Exception as e:
            self.logger.error(f"模式切换按钮回调执行失败: {e}")
            
    def _switch_to_auto_mode(self):
        """切换到自动模式的UI更新"""
        self.manual_btn.pack_forget()  # 移除手动按钮
        self.auto_btn.pack(side=tk.LEFT, padx=10, before=self.abort_btn)  # 显示自动按钮
        
    def _switch_to_manual_mode(self):
        """切换到手动模式的UI更新"""
        self.auto_btn.pack_forget()  # 移除自动按钮
        self.manual_btn.pack(side=tk.LEFT, padx=10, before=self.abort_btn)  # 显示手动按钮

    def update_status(self, status: str):
        """更新状态文本"""
        self.update_queue.put(lambda: self.status_label.config(text=f"状态: {status}"))

    def update_text(self, text: str):
        """更新TTS文本"""
        self.update_queue.put(lambda: self.tts_text_label.config(text=text))

    def update_emotion(self, emotion: str):
        """更新表情"""
        self.update_queue.put(lambda: self.emotion_label.config(text=emotion))

    def start_update_threads(self):
        """启动更新线程"""

        def update_loop():
            while self._running:
                try:
                    # 更新状态
                    if self.status_update_callback:
                        status = self.status_update_callback()
                        if status:
                            self.update_status(status)

                    # 更新文本
                    if self.text_update_callback:
                        text = self.text_update_callback()
                        if text:
                            self.update_text(text)

                    # 更新表情
                    if self.emotion_update_callback:
                        emotion = self.emotion_update_callback()
                        if emotion:
                            self.update_emotion(emotion)

                except Exception as e:
                    self.logger.error(f"更新失败: {e}")
                time.sleep(0.1)

        threading.Thread(target=update_loop, daemon=True).start()

    def on_close(self):
        """关闭窗口处理"""
        self._running = False
        self.root.destroy()
        self.stop_keyboard_listener()

    def start(self):
        """启动GUI"""
        try:
            # 启动键盘监听
            self.start_keyboard_listener()
            # 启动更新线程
            self.start_update_threads()
            # 在主线程中运行主循环
            self.logger.info("开始启动GUI主循环")
            self.root.mainloop()
        except Exception as e:
            self.logger.error(f"GUI启动失败: {e}", exc_info=True)
            # 尝试回退到CLI模式
            print(f"GUI启动失败: {e}，请尝试使用CLI模式")

    def update_mode_button_status(self, text: str):
        """更新模式按钮状态"""
        self.update_queue.put(lambda: self.mode_btn.config(text=text))

    def update_button_status(self, text: str):
        """更新按钮状态 - 保留此方法以满足抽象基类要求"""
        # 根据当前模式更新相应的按钮
        if self.auto_mode:
            self.update_queue.put(lambda: self.auto_btn.config(text=text))
        else:
            # 在手动模式下，不通过此方法更新按钮文本
            # 因为按钮文本由按下/释放事件直接控制
            pass

    def _on_volume_change(self, value):
        """处理音量滑块变化，使用节流"""
        # 取消之前的定时器
        if self.volume_update_timer is not None:
            self.root.after_cancel(self.volume_update_timer)
        
        # 设置新的定时器，300ms 后更新音量
        self.volume_update_timer = self.root.after(
            300, 
            lambda: self.update_volume(int(float(value)))
        )

    def start_keyboard_listener(self):
        """启动键盘监听"""
        try:
            def on_press(key):
                try:
                    # F2 按键处理 - 在手动模式下处理
                    if key == pynput_keyboard.Key.f2 and not self.auto_mode:
                        if self.button_press_callback:
                            self.button_press_callback()
                            self.update_button_status("松开以停止")
                    # F3 按键处理 - 打断
                    elif key == pynput_keyboard.Key.f3:
                        if self.abort_callback:
                            self.abort_callback()
                except Exception as e:
                    self.logger.error(f"键盘事件处理错误: {e}")

            def on_release(key):
                try:
                    # F2 释放处理 - 在手动模式下处理
                    if key == pynput_keyboard.Key.f2 and not self.auto_mode:
                        if self.button_release_callback:
                            self.button_release_callback()
                            self.update_button_status("按住说话")
                except Exception as e:
                    self.logger.error(f"键盘事件处理错误: {e}")

            # 创建并启动监听器
            self.keyboard_listener = pynput_keyboard.Listener(
                on_press=on_press,
                on_release=on_release
            )
            self.keyboard_listener.start()
            self.logger.info("键盘监听器初始化成功")
        except Exception as e:
            self.logger.error(f"键盘监听器初始化失败: {e}")

    def stop_keyboard_listener(self):
        """停止键盘监听"""
        if self.keyboard_listener:
            try:
                self.keyboard_listener.stop()
                self.keyboard_listener = None
                self.logger.info("键盘监听器已停止")
            except Exception as e:
                self.logger.error(f"停止键盘监听器失败: {e}")

    def _on_tab_changed(self, event):
        """处理标签页切换事件"""
        try:
            # 获取当前选中的标签页
            current_tab = self.notebook.index(self.notebook.select())
            
            # 如果切换到配置页面，确保滚动区域正确配置
            if current_tab == 1:  # 配置页面的索引
                # 延迟执行以确保切换完成
                self.root.after(100, self._configure_scroll_region)
        except Exception as e:
            self.logger.error(f"标签页切换事件处理错误: {e}")