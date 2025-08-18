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
      '异步任务管理和状态机控制',
      '设备状态(IDLE/CONNECTING/LISTENING/SPEAKING)',
      '线程安全的命令队列处理'
    ]
  },
  {
    name: 'src/mcp/',
    icon: WrenchIcon,
    features: [
      '基于JSON-RPC 2.0的MCP服务器',
      '丰富的工具生态系统(系统、日历、地图等)',
      '可扩展的插件架构',
      '类型安全的参数验证'
    ]
  },
  {
    name: 'src/protocols/',
    icon: ArrowsRightLeftIcon,
    features: [
      '抽象协议接口设计',
      'WebSocket和MQTT协议实现',
      'TLS加密和自动重连机制',
      '统一的通信抽象层'
    ]
  },
  {
    name: 'src/audio_codecs/',
    icon: DocumentIcon,
    features: [
      '基于Opus的实时音频编解码',
      'WebRTC音频回声消除(AEC)处理器',
      'SoXR高质量音频重采样',
      '系统音频录制与环回处理',
      '异步音频流处理',
      '低延迟音频缓冲管理'
    ]
  },
  {
    name: 'src/audio_processing/',
    icon: SpeakerXMarkIcon,
    features: [
      'AEC声学回声消除处理器',
      '基于Sherpa-ONNX的语音活动检测(VAD)',
      '多语言唤醒词检测',
      '实时音频处理和回调机制'
    ]
  },
  {
    name: 'src/display/',
    icon: ComputerDesktopIcon,
    features: [
      '策略模式的UI系统架构',
      'PyQt5 GUI和CLI界面实现',
      '异步界面更新',
      '状态显示和用户交互'
    ]
  },
  {
    name: 'src/iot/',
    icon: LightBulbIcon,
    features: [
      '基于Thing抽象的IoT设备框架',
      '统一设备管理和状态同步',
      '动态设备发现',
      '智能家居设备控制'
    ]
  },
  {
    name: 'src/utils/',
    icon: MapIcon,
    features: [
      '配置管理和设备指纹',
      '日志系统和资源查找',
      '音量控制和通用工具',
      '跨平台兼容性处理'
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