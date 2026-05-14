<template>
  <div class="module-container">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
      <div v-for="(module, index) in modules" :key="index" class="module-card">
        <div class="flex items-start">
          <div class="w-12 h-12 rounded-lg flex items-center justify-center"
            :class="moduleColors[index % moduleColors.length]">
            <component :is="module.icon" class="w-6 h-6 text-white" />
          </div>
          <div class="ml-4 flex-1">
            <h3 class="module-title">{{ module.name }}</h3>
            <ul class="space-y-2">
              <li v-for="(feature, featureIndex) in module.features" :key="featureIndex" class="flex items-start">
                <CheckCircleIcon class="w-5 h-5 text-green-500 mt-1 mr-2" />
                <span class="feature-text">{{ feature }}</span>
              </li>
            </ul>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import {
  CogIcon,
  ArrowsRightLeftIcon,
  DocumentIcon,
  SpeakerXMarkIcon,
  ComputerDesktopIcon,
  LightBulbIcon,
  WrenchIcon,
  CheckCircleIcon,
  CpuChipIcon,
  MapIcon,
  BoltIcon
} from '@heroicons/vue/24/solid';
import { useData } from 'vitepress';

const { isDark } = useData();

// 模块详情
const modules = [
  {
    name: 'src/bootstrap/',
    icon: CogIcon,
    features: [
      'ServiceContainer 聚合核心服务，统一管理生命周期',
      'PluginContext/PluginCommands 适配器暴露受控 API',
      '按依赖拓扑排序加载 Audio/WakeWord/UI/Shortcuts/MCP 插件'
    ]
  },
  {
    name: 'src/core/',
    icon: BoltIcon,
    features: [
      'EventBus 实现组件间解耦通信，支持异步事件处理',
      'StateManager 维护 DeviceState/ListeningMode 状态机',
      'ProtocolManager 封装协议连接与消息发送',
      'TaskManager 异步任务生命周期管理',
      'ResourcePool 统一资源注册与逆序释放'
    ]
  },
  {
    name: 'src/plugins/',
    icon: CpuChipIcon,
    features: [
      'PluginManager 拓扑排序依赖，统一 setup/start/stop/shutdown',
      'AudioPlugin 管理音频编解码与音乐播放控制',
      'UIPlugin 支持 GUI/CLI 双模式，ShortcutsPlugin 处理快捷键'
    ]
  },
  {
    name: 'src/protocols/',
    icon: ArrowsRightLeftIcon,
    features: [
      'Protocol 抽象定义音频/文本/控制消息接口',
      'WebSocket/MQTT 双实现，支持实时音频通道',
      '广播 AUDIO_CHANNEL_* 事件驱动状态变更'
    ]
  },
  {
    name: 'src/audio_codecs/',
    icon: DocumentIcon,
    features: [
      'AudioCodec 组合设备管理、Opus编解码、重采样模块',
      '输入流重采样到 16kHz 单声道 Opus 编码',
      '支持热重载音频设备与低延迟播放缓冲'
    ]
  },
  {
    name: 'src/audio_processing/',
    icon: SpeakerXMarkIcon,
    features: [
      'WakeWordDetector 基于 sherpa-onnx 关键词检测',
      '重用 AudioCodec PCM 流，异步队列检测循环',
      '检测结果触发 start_listening/abort_speaking'
    ]
  },
  {
    name: 'src/mcp/',
    icon: WrenchIcon,
    features: [
      'McpServer 实现 MCP 规范与 JSON-RPC 2.0',
      '@mcp_tool 装饰器自动发现并注册工具函数',
      '内置工具：音乐/摄像头/截图/应用管理/天气/音量'
    ]
  },
  {
    name: 'src/ui/',
    icon: ComputerDesktopIcon,
    features: [
      'PySide6/QML 实现 GUI，CLIViewManager 实现命令行界面',
      'EventBridge 连接 Python 与 QML 的双向通信',
      '系统托盘、情绪表情、设置窗口均由 EventBus 驱动'
    ]
  },
  {
    name: 'src/activation/',
    icon: LightBulbIcon,
    features: [
      'ActivationService 处理设备激活与 OTA 信息',
      'efuse.json 缓存序列号/HMAC 等设备指纹',
      '提供激活状态 API 给 UI 显示'
    ]
  },
  {
    name: 'src/logging/',
    icon: DocumentIcon,
    features: [
      '独立日志子系统，支持分级过滤和格式化',
      '自定义 Handler 支持文件轮转和控制台输出',
      '日志过滤器按模块/级别精细控制'
    ]
  },
  {
    name: 'src/utils/',
    icon: MapIcon,
    features: [
      'ConfigManager 管理配置文件，支持点记法访问和动态更新',
      'ResourceFinder 解析资源路径，AudioDeviceManager 探测设备',
      'OpusLoader 跨平台 Opus 库加载，优先内置库'
    ]
  }
];

const moduleColors = [
  'bg-blue-600',
  'bg-indigo-600',
  'bg-purple-600',
  'bg-pink-600',
  'bg-red-600',
  'bg-orange-600',
  'bg-yellow-600',
  'bg-green-600'
];
</script>

<style scoped>
.module-container {
  background-color: var(--vp-c-bg);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 40px;
}

.module-card {
  transition: all 0.3s ease;
  padding: 1.5rem;
}

.module-card:hover {
  background-color: var(--vp-c-bg-soft);
}

.module-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--vp-c-text-1);
  margin-bottom: 0.5rem;
}

.feature-text {
  color: var(--vp-c-text-2);
}
</style>
