<template>
  <div class="tech-container">
      <div class="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
        <div v-for="(tech, index) in techStack" :key="index"
          class="tech-item">
          <div class="w-16 h-16 rounded-full flex items-center justify-center mb-3"
            :class="techColors[index % techColors.length]">
            <component :is="tech.icon" class="w-8 h-8 text-white" />
          </div>
          <h4 class="tech-name">{{ tech.name }}</h4>
          <p class="tech-description">{{ tech.description }}</p>
        </div>
      </div>
    </div>
</template>

<script setup>
import {
  CodeBracketIcon,
  WindowIcon,
  DocumentIcon,
  SpeakerWaveIcon as AudioIcon,
  PuzzlePieceIcon,
  SignalIcon,
  ArrowPathIcon,
  ArrowsUpDownIcon,
  CommandLineIcon
} from '@heroicons/vue/24/solid';

// 技术栈
const techStack = [
  {
    name: 'Python',
    description: '>= 3.10',
    icon: CodeBracketIcon
  },
  {
    name: 'AsyncIO',
    description: '异步编程框架',
    icon: ArrowPathIcon
  },
  {
    name: 'PySide6 / QML',
    description: 'Qt6 声明式 GUI',
    icon: WindowIcon
  },
  {
    name: 'Textual',
    description: '全屏终端 TUI',
    icon: CommandLineIcon
  },
  {
    name: 'qasync',
    description: 'Qt 异步集成',
    icon: ArrowsUpDownIcon
  },
  {
    name: 'uv',
    description: '包管理器',
    icon: CommandLineIcon
  },
  {
    name: 'WebRTC APM',
    description: '三端内置回声消除',
    icon: AudioIcon
  },
  {
    name: 'Sherpa-ONNX',
    description: '离线唤醒词检测',
    icon: DocumentIcon
  },
  {
    name: 'OpusLib',
    description: '语音编解码',
    icon: AudioIcon
  },
  {
    name: 'FFmpeg',
    description: '通用媒体流解码',
    icon: SignalIcon
  },
  {
    name: 'SoXR',
    description: '高质量重采样',
    icon: SignalIcon
  },
  {
    name: 'SoundDevice',
    description: '音频设备 I/O',
    icon: AudioIcon
  },
  {
    name: 'WebSockets',
    description: '实时通信协议',
    icon: PuzzlePieceIcon
  },
  {
    name: 'MQTT',
    description: '轻量消息传输',
    icon: SignalIcon
  },
  {
    name: 'MCP Protocol',
    description: '模型上下文协议',
    icon: PuzzlePieceIcon
  },
  {
    name: 'EventBus',
    description: '事件驱动架构',
    icon: ArrowPathIcon
  }
];

const techColors = [
  'bg-blue-500',
  'bg-indigo-500',
  'bg-purple-500',
  'bg-pink-500',
  'bg-red-500',
  'bg-orange-500',
  'bg-yellow-500',
  'bg-green-500',
  'bg-teal-500'
];
</script>

<style scoped>
.tech-container {
  background-color: var(--vp-c-bg);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 40px;
}

.tech-item {
  display: flex;
  flex-direction: column;
  align-items: center;
  padding: 16px;
  border-radius: 8px;
  transition: all 0.2s ease;
}

.tech-item:hover {
  background-color: var(--vp-c-bg-soft);
}

.tech-name {
  font-weight: 600;
  text-align: center;
  color: var(--vp-c-text-1);
  margin-top: 12px;
}

.tech-description {
  font-size: 0.875rem;
  color: var(--vp-c-text-2);
  text-align: center;
  margin-top: 4px;
}
</style>
