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

// Công nghệ sử dụng
const techStack = [
  {
    name: 'Python',
    description: '>= 3.10',
    icon: CodeBracketIcon
  },
  {
    name: 'AsyncIO',
    description: 'Framework lập trình bất đồng bộ',
    icon: ArrowPathIcon
  },
  {
    name: 'PySide6 / QML',
    description: 'GUI khai báo trên Qt6',
    icon: WindowIcon
  },
  {
    name: 'Textual',
    description: 'TUI toàn màn hình trên terminal',
    icon: CommandLineIcon
  },
  {
    name: 'qasync',
    description: 'Tích hợp bất đồng bộ cho Qt',
    icon: ArrowsUpDownIcon
  },
  {
    name: 'uv',
    description: 'Trình quản lý gói',
    icon: CommandLineIcon
  },
  {
    name: 'WebRTC APM',
    description: 'Khử tiếng vọng tích hợp đa HĐH',
    icon: AudioIcon
  },
  {
    name: 'Sherpa-ONNX',
    description: 'Phát hiện từ đánh thức ngoại tuyến',
    icon: DocumentIcon
  },
  {
    name: 'OpusLib',
    description: 'Mã hóa/giải mã giọng nói',
    icon: AudioIcon
  },
  {
    name: 'FFmpeg',
    description: 'Giải mã luồng đa phương tiện chung',
    icon: SignalIcon
  },
  {
    name: 'SoXR',
    description: 'Tái lấy mẫu chất lượng cao',
    icon: SignalIcon
  },
  {
    name: 'SoundDevice',
    description: 'Xuất/nhập thiết bị âm thanh',
    icon: AudioIcon
  },
  {
    name: 'WebSockets',
    description: 'Giao thức thời gian thực',
    icon: PuzzlePieceIcon
  },
  {
    name: 'MQTT',
    description: 'Truyền tải tin nhắn gọn nhẹ',
    icon: SignalIcon
  },
  {
    name: 'MCP Protocol',
    description: 'Giao thức ngữ cảnh mô hình',
    icon: PuzzlePieceIcon
  },
  {
    name: 'EventBus',
    description: 'Kiến trúc hướng sự kiện',
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
