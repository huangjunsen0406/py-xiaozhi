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
  MapIcon
} from '@heroicons/vue/24/solid';
import { useData } from 'vitepress';

const { isDark } = useData();

// 模块详情
const modules = [
  {
    name: 'src/application.py',
    icon: CogIcon,
    features: [
      '应用主类，单例模式管理全局状态',
      '异步事件驱动架构，基于asyncio',
      '设备状态机(IDLE/LISTENING/SPEAKING)',
      '统一任务池管理和生命周期控制',
      '插件化架构，通过PluginManager协调各模块'
    ]
  },
  {
    name: 'src/plugins/',
    icon: CpuChipIcon,
    features: [
      '插件管理器，按优先级排序注册插件',
      '统一生命周期管理(setup/start/stop/shutdown)',
      '事件广播机制(协议连接、JSON消息、音频数据)',
      '插件隔离，错误不传播',
      '包含Audio、MCP、IoT、UI、WakeWord等核心插件'
    ]
  },
  {
    name: 'src/mcp/',
    icon: WrenchIcon,
    features: [
      '基于MCP协议的工具服务器',
      '丰富的工具生态(系统、日历、音乐、地图、八字等)',
      'Property/Method抽象，支持异步调用',
      '类型安全的参数验证和默认值处理',
      '工具分类管理(camera/calendar/timer/music等)'
    ]
  },
  {
    name: 'src/protocols/',
    icon: ArrowsRightLeftIcon,
    features: [
      '抽象Protocol基类，定义统一接口',
      'WebSocket和MQTT双协议实现',
      'WSS/TLS加密传输，自动重连机制',
      '支持文本/音频/IoT/MCP消息类型',
      '连接状态管理和错误回调'
    ]
  },
  {
    name: 'src/audio_codecs/',
    icon: DocumentIcon,
    features: [
      'Opus编解码器(16kHz编码/24kHz解码)',
      'WebRTC AEC回声消除处理器',
      'SoXR实时音频重采样(支持任意采样率)',
      '智能声道转换(下混/上混)',
      '设备原生格式自适应',
      '低延迟流式缓冲(5ms处理)',
      '观察者模式解耦音频监听器'
    ]
  },
  {
    name: 'src/audio_processing/',
    icon: SpeakerXMarkIcon,
    features: [
      '基于Sherpa-ONNX的唤醒词检测',
      '支持多唤醒词和拼音匹配',
      'VAD语音活动检测',
      '实时音频流处理',
      '异步事件通知机制'
    ]
  },
  {
    name: 'src/views/',
    icon: ComputerDesktopIcon,
    features: [
      'PyQt5 GUI界面(设置窗口/激活窗口)',
      '系统托盘和全局快捷键支持',
      '音频设备/摄像头/唤醒词配置界面',
      '异步UI更新和线程安全',
      '基础窗口组件和混入类'
    ]
  },
  {
    name: 'src/iot/',
    icon: LightBulbIcon,
    features: [
      'Thing基类定义设备抽象',
      'Property/Method异步属性和方法',
      'ThingManager统一设备管理',
      '状态增量更新和并发获取',
      '支持灯光/音量/定时器等设备类型'
    ]
  },
  {
    name: 'src/utils/',
    icon: MapIcon,
    features: [
      'ConfigManager分层配置管理',
      '点记法访问配置(如AUDIO_DEVICES.input_device_id)',
      '设备指纹生成和激活管理',
      '统一日志系统和资源查找',
      '音量控制和跨平台工具函数'
    ]
  },
  {
    name: 'src/core/',
    icon: ServerIcon,
    features: [
      'OTA在线更新模块',
      '系统初始化器',
      '版本检查和升级管理'
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