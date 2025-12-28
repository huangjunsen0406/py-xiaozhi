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
  ServerIcon,
  LightBulbIcon,
  WrenchIcon,
  CheckCircleIcon,
  CpuChipIcon,
  MapIcon,
  CommandLineIcon,
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
      'ServiceContainer 服务容器，管理全局状态',
      '异步事件驱动架构，基于 asyncio + qasync',
      '设备状态机 (IDLE/LISTENING/SPEAKING)',
      '统一生命周期管理 (start/stop/shutdown)',
      '协议工厂，动态创建 WebSocket/MQTT 连接'
    ]
  },
  {
    name: 'src/core/',
    icon: BoltIcon,
    features: [
      'EventBus 事件总线，解耦模块通信',
      'TaskManager 异步任务池管理',
      'ProtocolManager 协议管理器',
      'StateManager 设备状态管理',
      '支持热重载配置变更'
    ]
  },
  {
    name: 'src/plugins/',
    icon: CpuChipIcon,
    features: [
      'PluginManager 按优先级注册插件',
      '统一生命周期 (setup/start/stop/shutdown)',
      '事件广播机制 (协议、音频、UI)',
      'Audio/MCP/UI/WakeWord/Shortcuts 核心插件',
      '插件隔离，错误不传播'
    ]
  },
  {
    name: 'src/plugins/shortcuts/',
    icon: CommandLineIcon,
    features: [
      'macOS: Quartz Event Tap (系统级热键)',
      'Linux/Windows: pynput 后端',
      '平台自动检测，工厂模式创建',
      '健康检查与自动重启机制',
      '支持 Ctrl/Alt/Cmd + 任意键组合'
    ]
  },
  {
    name: 'src/mcp/',
    icon: WrenchIcon,
    features: [
      '基于 MCP 协议的工具服务器',
      '丰富工具生态 (系统/音乐/相机/八字)',
      'Property/Method 抽象，支持异步调用',
      '类型安全参数验证',
      '工具分类管理 (camera/music/bazi 等)'
    ]
  },
  {
    name: 'src/protocols/',
    icon: ArrowsRightLeftIcon,
    features: [
      '抽象 Protocol 基类，统一接口',
      'WebSocket 和 MQTT 双协议实现',
      'WSS/TLS 加密传输，自动重连',
      '支持文本/音频/IoT/MCP 消息类型',
      '连接状态管理和错误回调'
    ]
  },
  {
    name: 'src/audio_codecs/',
    icon: DocumentIcon,
    features: [
      'Opus 编解码 (16kHz 编码 / 24kHz 解码)',
      'SoXR 实时重采样 (任意采样率)',
      '智能声道转换 (下混/上混)',
      '低延迟流式缓冲 (5ms 处理)',
      '观察者模式解耦音频监听'
    ]
  },
  {
    name: 'src/audio_processing/',
    icon: SpeakerXMarkIcon,
    features: [
      'Sherpa-ONNX 唤醒词检测',
      '支持多唤醒词和拼音匹配',
      '实时音频流处理',
      '异步事件通知机制',
      '热重载模型支持'
    ]
  },
  {
    name: 'src/views/',
    icon: ComputerDesktopIcon,
    features: [
      'PySide6 + QML 声明式 UI',
      'MVVM 架构 (Model/Bridge/QML)',
      '系统托盘和全局快捷键',
      '设置/激活/主窗口组件',
      'EventBridge 连接 Python 与 QML'
    ]
  },
  {
    name: 'src/utils/',
    icon: MapIcon,
    features: [
      'ConfigManager 分层配置管理',
      '点记法访问 (AUDIO_DEVICES.input_device_id)',
      '音频设备枚举和选择',
      'Opus 动态库加载器',
      '跨平台音量控制'
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
