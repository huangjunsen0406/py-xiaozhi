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
    description: '应用核心采用线程安全的单例模式，保证全局唯一实例',
    icon: CubeIcon
  },
  {
    title: '异步架构',
    description: '全面采用asyncio异步编程，支持高并发和高性能',
    icon: BoltIcon
  },
  {
    title: '资源管理',
    description: '中央化资源管理器，依赖跟踪和优雅清理',
    icon: ShareIcon
  },
  {
    title: '状态机模式',
    description: '设备状态管理采用状态机模式，清晰的状态转换逻辑',
    icon: ArrowsRightLeftIcon
  },
  {
    title: '插件化设计',
    description: 'MCP工具和IoT设备采用插件化设计，支持动态扩展',
    icon: PuzzlePieceIcon
  },
  {
    title: '跨平台兼容',
    description: '支持Windows、macOS、Linux多平台，优雅降级处理',
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
  <div class="bg-white rounded-lg relative mb-10">
      <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div v-for="(feature, index) in architectureFeatures" :key="index"
          class="bg-white rounded-lg p-6 hover:shadow-xl transition-shadow">
          <div class="w-12 h-12 rounded-full flex items-center justify-center mb-4"
            :class="featureColors[index % featureColors.length]">
            <component :is="feature.icon" class="w-6 h-6 text-white" />
          </div>
          <h3 class="text-xl font-semibold mb-2">{{ feature.title }}</h3>
          <p class="text-gray-700">{{ feature.description }}</p>
        </div>
      </div>
    </div>
</template>

<style scoped>
/* 架构特点卡片样式优化 */
.grid-cols-1.md\:grid-cols-2.lg\:grid-cols-3 > div {
  transition: all 0.3s ease;
  height: 100%;
}

.grid-cols-1.md\:grid-cols-2.lg\:grid-cols-3 > div:hover {
  transform: translateY(-5px);
}
</style>