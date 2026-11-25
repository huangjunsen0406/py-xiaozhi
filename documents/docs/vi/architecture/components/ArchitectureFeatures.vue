<script setup lang="ts">
import {
  PuzzlePieceIcon,
  CubeIcon,
  ArrowsRightLeftIcon,
  BoltIcon,
  ShareIcon,
  ArrowPathIcon
} from '@heroicons/vue/24/solid';

// Đặc điểm kiến trúc
const architectureFeatures = [
  {
    title: 'Hướng sự kiện',
    description: 'Các mô-đun giao tiếp qua EventBus, giảm ghép nối trực tiếp',
    icon: ArrowPathIcon
  },
  {
    title: 'Kiến trúc bất đồng bộ',
    description: 'asyncio + qasync, phù hợp cho xử lý giọng nói thời gian thực',
    icon: BoltIcon
  },
  {
    title: 'Đa giao diện',
    description: 'GUI / TUI / GPIO dùng chung một lớp ViewPort',
    icon: ShareIcon
  },
  {
    title: 'Máy trạng thái',
    description: 'Chuyển đổi rõ ràng giữa các trạng thái chờ / đang nghe / đang nói',
    icon: ArrowsRightLeftIcon
  },
  {
    title: 'Hệ sinh thái plugin và tiện ích mở rộng',
    description: 'Plugin tích hợp tách rời mô-đun; hỗ trợ nhập nóng và chạy cô lập plugin MCP bên ngoài',
    icon: PuzzlePieceIcon
  },
  {
    title: 'Đa nền tảng',
    description: 'Windows / macOS / Linux (bao gồm cả Raspberry Pi)',
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
