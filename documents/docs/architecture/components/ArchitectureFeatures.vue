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
    title: 'Event-driven',
    description: 'Modules talk via EventBus with less direct coupling',
    icon: ArrowPathIcon
  },
  {
    title: 'Async',
    description: 'asyncio + qasync for realtime voice',
    icon: BoltIcon
  },
  {
    title: 'Multi UI',
    description: 'GUI / CLI / GPIO share one ViewPort',
    icon: ShareIcon
  },
  {
    title: 'State machine',
    description: 'Idle / listening / speaking transitions',
    icon: ArrowsRightLeftIcon
  },
  {
    title: 'Plugins',
    description: 'Audio, MCP, UI, shortcuts, wake word',
    icon: PuzzlePieceIcon
  },
  {
    title: 'Cross-platform',
    description: 'Windows / macOS / Linux (incl. Raspberry Pi)',
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
