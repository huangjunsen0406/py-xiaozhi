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
                <CheckCircleIcon class="w-5 h-5 text-green-500 mt-1 mr-2 shrink-0" />
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

const modules = [
  {
    name: 'src/bootstrap/',
    icon: CogIcon,
    features: [
      'ServiceContainer 编排启动与关闭',
      '会话、健康检查、插件装配拆分',
      '按依赖加载各插件'
    ]
  },
  {
    name: 'src/core/',
    icon: BoltIcon,
    features: [
      'EventBus 事件通信',
      '设备状态机与协议管理',
      '任务与资源统一回收'
    ]
  },
  {
    name: 'src/plugins/',
    icon: CpuChipIcon,
    features: [
      '插件生命周期与依赖隔离',
      '音频、UI、快捷键、唤醒词、MCP'
    ]
  },
  {
    name: 'src/protocols/',
    icon: ArrowsRightLeftIcon,
    features: [
      'WebSocket / MQTT 双协议',
      '实时音频与文本消息'
    ]
  },
  {
    name: 'src/audio_codecs/',
    icon: DocumentIcon,
    features: [
      'Opus 编解码与重采样',
      '设备热刷新与热重载'
    ]
  },
  {
    name: 'src/audio_processing/',
    icon: SpeakerXMarkIcon,
    features: [
      '离线唤醒词检测',
      '复用麦克风 PCM 流'
    ]
  },
  {
    name: 'src/mcp/',
    icon: WrenchIcon,
    features: [
      '音乐、摄像头、截图、音量等工具',
      '容器注入注册；支持外挂插件',
      '摄像头支持 USB 与树莓派 CSI'
    ]
  },
  {
    name: 'src/ui/',
    icon: ComputerDesktopIcon,
    features: [
      'GUI / CLI / GPIO 统一 ViewPort',
      'PySide6 + QML 主界面与设置',
      '冷启动不抢前台（macOS）'
    ]
  },
  {
    name: 'src/activation/',
    icon: LightBulbIcon,
    features: [
      '设备激活与 OTA',
      '独立激活窗口'
    ]
  },
  {
    name: 'src/logging/',
    icon: DocumentIcon,
    features: [
      '分级日志与文件轮转',
      '显式初始化'
    ]
  },
  {
    name: 'src/utils/',
    icon: MapIcon,
    features: [
      '配置管理（按名匹配音频设备）',
      '资源路径与跨平台工具'
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
  'bg-amber-600',
  'bg-green-600',
  'bg-teal-600',
  'bg-cyan-600',
  'bg-sky-600'
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
  border-radius: 8px;
  padding: 16px;
  transition: background-color 0.2s ease;
}

.module-card:hover {
  background-color: var(--vp-c-bg-soft);
}

.module-title {
  font-size: 1.125rem;
  font-weight: 600;
  color: var(--vp-c-text-1);
  margin-bottom: 8px;
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
}

.feature-text {
  color: var(--vp-c-text-2);
  line-height: 1.5;
  font-size: 0.95rem;
}
</style>
