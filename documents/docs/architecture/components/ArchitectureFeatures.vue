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
    title: '模块化设计',
    description: '各功能模块高度解耦，便于维护和扩展',
    icon: CubeIcon
  },
  {
    title: '协议抽象',
    description: '通过抽象接口支持多种通信协议',
    icon: ArrowsRightLeftIcon
  },
  {
    title: '事件驱动',
    description: '基于事件的异步处理机制',
    icon: BoltIcon
  },
  {
    title: '状态机模式',
    description: '清晰的状态转换逻辑',
    icon: ShareIcon
  },
  {
    title: '插件式IoT设备',
    description: '统一设备接口，支持动态加载设备',
    icon: PuzzlePieceIcon
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