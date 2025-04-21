<template>
  <div class="bg-white rounded-lg relative mb-10">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
      <div v-for="(module, index) in modules" :key="index" class="module-card">
        <div class="flex items-start">
          <div class="w-12 h-12 rounded-lg flex items-center justify-center"
            :class="moduleColors[index % moduleColors.length]">
            <component :is="module.icon" class="w-6 h-6 text-white" />
          </div>
          <div class="ml-4 flex-1">
            <h3 class="text-lg font-semibold mb-2">{{ module.name }}</h3>
            <ul class="space-y-2">
              <li v-for="(feature, featureIndex) in module.features" :key="featureIndex" class="flex items-start">
                <CheckCircleIcon class="w-5 h-5 text-green-500 mt-1 mr-2" />
                <span>{{ feature }}</span>
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
  ServerIcon,
  LightBulbIcon,
  WrenchIcon,
  CheckCircleIcon
} from '@heroicons/vue/24/solid';

// 模块详情
const modules = [
  {
    name: 'src/application.py',
    icon: CogIcon,
    features: [
      '应用主类，负责协调所有子系统',
      '实现了单例模式，管理全局状态',
      '处理事件调度和状态转换'
    ]
  },
  {
    name: 'src/protocols/',
    icon: ArrowsRightLeftIcon,
    features: [
      '通信协议的抽象接口和具体实现',
      'WebSocket协议：用于实时双向通信',
      'MQTT协议：用于物联网设备通信'
    ]
  },
  {
    name: 'src/audio_codecs/',
    icon: DocumentIcon,
    features: [
      '音频编解码器，处理音频数据压缩/解压缩',
      '支持Opus编码格式'
    ]
  },
  {
    name: 'src/audio_processing/',
    icon: SpeakerXMarkIcon,
    features: [
      '语音活动检测：判断用户是否在说话',
      '唤醒词检测：识别指定的唤醒词'
    ]
  },
  {
    name: 'src/display/',
    icon: ComputerDesktopIcon,
    features: [
      '用户界面抽象和实现',
      'GUI界面：基于PyQt5的图形界面',
      'CLI界面：命令行交互界面'
    ]
  },
  {
    name: 'src/iot/',
    icon: ServerIcon,
    features: [
      'IoT设备管理框架',
      '设备抽象类和具体实现',
      '支持智能家居设备控制'
    ]
  },
  {
    name: 'src/iot/things/',
    icon: LightBulbIcon,
    features: [
      '具体IoT设备的实现',
      '音乐播放器、温度传感器',
      '灯光控制、摄像头等'
    ]
  },
  {
    name: 'src/utils/',
    icon: WrenchIcon,
    features: [
      '各类工具函数和辅助类',
      '日志管理、配置管理等'
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
  'bg-yellow-600',
  'bg-green-600'
];
</script>

<style scoped>
.module-card {
  transition: all 0.3s ease;
}

.module-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 10px 15px -3px rgba(0, 0, 0, 0.1);
}
</style> 