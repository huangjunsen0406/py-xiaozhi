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
      'ServiceContainer orchestrates start/shutdown',
      'Session, health, and plugin wiring split out',
      'Plugins load by dependency order'
    ]
  },
  {
    name: 'src/core/',
    icon: BoltIcon,
    features: [
      'EventBus for decoupled messaging',
      'Device state machine and protocol manager',
      'Tasks and resources cleaned up together'
    ]
  },
  {
    name: 'src/plugins/',
    icon: CpuChipIcon,
    features: [
      'Plugin lifecycle and failure isolation',
      'Audio, UI, shortcuts, wake word, MCP'
    ]
  },
  {
    name: 'src/protocols/',
    icon: ArrowsRightLeftIcon,
    features: [
      'WebSocket and MQTT',
      'Realtime audio and text'
    ]
  },
  {
    name: 'src/audio_codecs/',
    icon: DocumentIcon,
    features: [
      'Opus codec and resampling',
      'Hot refresh and reload of devices'
    ]
  },
  {
    name: 'src/audio_processing/',
    icon: SpeakerXMarkIcon,
    features: [
      'Offline wake-word detection',
      'Reuses microphone PCM'
    ]
  },
  {
    name: 'src/mcp/',
    icon: WrenchIcon,
    features: [
      'Music, camera, screenshot, volume, and more',
      'Container injection; optional external plugins',
      'Camera: USB and Raspberry Pi CSI'
    ]
  },
  {
    name: 'src/ui/',
    icon: ComputerDesktopIcon,
    features: [
      'GUI / CLI / GPIO via ViewPort',
      'PySide6 + QML main window and settings',
      'Cold start does not steal focus (macOS)'
    ]
  },
  {
    name: 'src/activation/',
    icon: LightBulbIcon,
    features: [
      'Device activation and OTA',
      'Standalone activation window'
    ]
  },
  {
    name: 'src/logging/',
    icon: DocumentIcon,
    features: [
      'Leveled logs and rotation',
      'Explicit initialization'
    ]
  },
  {
    name: 'src/utils/',
    icon: MapIcon,
    features: [
      'Config (audio devices matched by name)',
      'Resource paths and cross-platform helpers'
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
