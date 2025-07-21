<script setup lang="ts">
import {
  PuzzlePieceIcon,
  CubeIcon,
  ArrowsRightLeftIcon,
  BoltIcon,
  ShareIcon
} from '@heroicons/vue/24/solid';
// 架构特点
const architectureFeatures = [
  {
    title: '单例模式',
    description: '应用核心采用线程安全的单例模式，保证全局唯一实例和状态一致性',
    icon: CubeIcon
  },
  {
    title: '异步架构',
    description: '全面采用asyncio异步编程，支持高并发处理和实时音频流',
    icon: BoltIcon
  },
  {
    title: '资源管理',
    description: '中央化资源管理器，智能依赖跟踪和优雅清理机制',
    icon: ShareIcon
  },
  {
    title: '状态机模式',
    description: '设备状态管理采用状态机模式，清晰的状态转换和错误恢复',
    icon: ArrowsRightLeftIcon
  },
  {
    title: '插件化生态',
    description: 'MCP工具和IoT设备采用插件化设计，支持热插拔和动态扩展',
    icon: PuzzlePieceIcon
  },
  {
    title: '跨平台兼容',
    description: '支持Windows、macOS、Linux多平台，智能特性检测和优雅降级',
    icon: CubeIcon
  }
];

const featureColors = [
  'bg-blue-500',
  'bg-indigo-500',
  'bg-purple-500',
  'bg-pink-500',
  'bg-red-500'
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