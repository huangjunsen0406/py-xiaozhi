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
  MusicalNoteIcon as MusicIcon
} from '@heroicons/vue/24/solid';

// 技术栈
const techStack = [
  {
    name: 'Python',
    description: '3.9-3.12',
    icon: CodeBracketIcon
  },
  {
    name: 'AsyncIO',
    description: '异步编程框架',
    icon: ArrowPathIcon
  },
  {
    name: 'PyQt5',
    description: 'GUI框架',
    icon: WindowIcon
  },
  {
    name: 'qasync',
    description: 'Qt异步集成',
    icon: ArrowsUpDownIcon
  },
  {
    name: 'Sherpa-ONNX',
    description: '语音识别引擎',
    icon: DocumentIcon
  },
  {
    name: 'WebRTC AEC',
    description: 'WebRTC音频处理模块',
    icon: MusicIcon
  },
  {
    name: 'OpusLib',
    description: '音频编解码',
    icon: AudioIcon
  },
  {
    name: 'SoXR',
    description: '高质量重采样',
    icon: SignalIcon
  },
  {
    name: 'SoundDevice',
    description: '音频设备管理',
    icon: AudioIcon
  },
  {
    name: 'WebSockets',
    description: '实时通信协议',
    icon: PuzzlePieceIcon
  },
  {
    name: 'MQTT',
    description: 'IoT消息传输',
    icon: SignalIcon
  },
  {
    name: 'MCP Protocol',
    description: '模型上下文协议',
    icon: PuzzlePieceIcon
  },
  {
    name: 'Cryptography',
    description: '加密安全库',
    icon: DocumentIcon
  },
  {
    name: 'Thing抽象',
    description: 'IoT设备抽象',
    icon: SignalIcon
  },
  {
    name: 'JSON-RPC',
    description: '远程过程调用',
    icon: DocumentIcon
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