<script setup lang="ts">
import {
  PuzzlePieceIcon,
  CubeIcon,
  ArrowsRightLeftIcon,
  BoltIcon,
  ShareIcon,
  ArrowPathIcon
} from '@heroicons/vue/24/solid';

// 架构特点
const architectureFeatures = [
  {
    title: '事件驱动',
    description: '模块之间用 EventBus 通信，少直接耦合',
    icon: ArrowPathIcon
  },
  {
    title: '异步架构',
    description: 'asyncio + qasync，适合实时语音',
    icon: BoltIcon
  },
  {
    title: '多界面',
    description: 'GUI / CLI / GPIO 同一套 ViewPort',
    icon: ShareIcon
  },
  {
    title: '状态机',
    description: '待命 / 聆听 / 说话 状态清晰切换',
    icon: ArrowsRightLeftIcon
  },
  {
    title: '插件化',
    description: '音频、MCP、UI、快捷键、唤醒词可插拔',
    icon: PuzzlePieceIcon
  },
  {
    title: '跨平台',
    description: 'Windows / macOS / Linux（含树莓派）',
    icon: CubeIcon
  }
];

const featureColors = [
  'bg-blue-500',
  'bg-indigo-500',
  'bg-purple-500',
  'bg-pink-500',
  'bg-red-500',
  'bg-orange-500'
];
</script>

<template>
  <div class="features-container">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div v-for="(feature, index) in architectureFeatures" :key="index"
          class="feature-card">
          <div class="w-12 h-12 rounded-full flex items-center justify-center mb-4"
            :class="featureColors[index % featureColors.length]">
            <component :is="feature.icon" class="w-6 h-6 text-white" />
          </div>
          <h3 class="feature-title">{{ feature.title }}</h3>
          <p class="feature-description">{{ feature.description }}</p>
        </div>
      </div>
    </div>
</template>

<style scoped>
.features-container {
  background-color: var(--vp-c-bg);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 40px;
}

.feature-card {
  border-radius: 8px;
  padding: 24px;
  transition: all 0.3s ease;
  height: 100%;
}

.feature-card:hover {
  background-color: var(--vp-c-bg-soft);
}

.feature-title {
  font-size: 1.25rem;
  font-weight: 600;
  color: var(--vp-c-text-1);
  margin-bottom: 8px;
}

.feature-description {
  color: var(--vp-c-text-2);
  line-height: 1.6;
}
</style>
