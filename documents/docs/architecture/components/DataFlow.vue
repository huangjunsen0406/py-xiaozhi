<template>
  <div class="bg-white rounded-lg  relative mb-10">
    <div class="grid grid-cols-1 lg:grid-cols-3 gap-8">
      <div v-for="(flow, index) in dataFlows" :key="index"
        class="data-flow-card bg-white rounded-xl shadow-xl overflow-hidden transform hover:scale-[1.02] transition-all duration-300">
        <div class="p-5 text-white font-semibold bg-gradient-to-r" :class="[
          index === 0 ? 'from-blue-500 to-blue-600' :
            index === 1 ? 'from-green-500 to-green-600' :
              'from-purple-500 to-purple-600'
        ]">
          <div class="flex items-center">
            <div class="w-10 h-10 rounded-full bg-white/20 backdrop-blur-sm flex items-center justify-center">
              <component :is="flow.icon" class="w-5 h-5 text-white" />
            </div>
            <div class="ml-4">
              <h3 class="text-xl font-bold">{{ flow.title }}</h3>
              <p class="text-white/80 text-sm mt-1">{{ flow.subtitle }}</p>
            </div>
          </div>
        </div>
        <div class="p-5 flex-grow">
          <div class="relative py-3 h-full" >
            <div v-for="(step, stepIndex) in flow.steps" :key="stepIndex"
                 class="flow-step flex items-center mb-5 last:mb-0">
              <div
                class="flow-step-number w-10 h-10 rounded-full bg-gradient-to-br flex items-center justify-center text-white font-bold shadow-md"
                :class="[
                  index === 0 ? 'from-blue-400 to-blue-500' :
                    index === 1 ? 'from-green-400 to-green-500' :
                      'from-purple-400 to-purple-500'
                ]">
                {{ stepIndex + 1 }}
              </div>
              <div class="flow-step-content ml-3 flex-1 bg-gradient-to-br from-gray-50 to-white rounded-lg p-3 shadow-sm">
                <p class="text-gray-700">{{ step }}</p>
              </div>
            </div>
            <div class="absolute left-5 top-8 bottom-5 w-0.5" :class="[
              index === 0 ? 'bg-blue-200' :
                index === 1 ? 'bg-green-200' :
                  'bg-purple-200'
            ]">
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { 
  AcademicCapIcon, 
  SpeakerWaveIcon, 
  CommandLineIcon
} from '@heroicons/vue/24/solid';

// 数据流
const dataFlows = [
  {
    title: '音频输入流程',
    subtitle: '从用户到服务器',
    icon: AcademicCapIcon,
    steps: [
      '麦克风捕获音频并进行采样率转换',
      'VAD检测语音活动判断是否有语音',
      '使用Opus编码器压缩音频数据',
      '通过WebSocket/MQTT协议发送到服务器'
    ]
  },
  {
    title: '音频输出流程',
    subtitle: '从服务器到用户',
    icon: SpeakerWaveIcon,
    steps: [
      '服务器返回经过Opus编码的音频数据',
      '使用Opus解码器解码音频数据',
      '通过SoXR进行高质量重采样',
      '输出到音频设备进行播放'
    ]
  },
  {
    title: 'MCP工具执行流程',
    subtitle: '命令处理与执行',
    icon: CommandLineIcon,
    steps: [
      '用户发送语音或文本命令',
      'MCP服务器解析命令和参数',
      '路由到相应的工具执行器',
      '执行结果返回给用户界面'
    ]
  }
];
</script>

<style scoped>
.data-flow-card {
  display: flex;
  flex-direction: column;
  height: 100%;
}

.data-flow-card > div:last-child {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.flow-chart {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.flow-step {
  position: relative;
  z-index: 1;
}

.flow-chart .flow-step {
  margin-bottom: 1.25rem;
  min-height: 3rem;
}

.flow-chart .flow-step:last-child {
  margin-bottom: 0;
}

.flow-step-content {
  padding: 0.75rem 1rem;
  display: flex;
  align-items: center;
  min-height: 3rem;
}

.flow-chart .absolute {
  z-index: 0;
}

@media (min-width: 1024px) {
  .grid-cols-1.lg\:grid-cols-3 {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .grid-cols-1.lg\:grid-cols-3 > div {
    display: flex;
    flex-direction: column;
  }

  .grid-cols-1.lg\:grid-cols-3 > div > div:last-child {
    flex: 1;
    display: flex;
    flex-direction: column;
  }

  .flow-chart {
    flex: 1;
    display: flex;
    flex-direction: column;
    justify-content: space-between;
  }
}

@media (max-width: 1023px) {
  .grid-cols-1.lg\:grid-cols-3 > div {
    margin-bottom: 2rem;
  }
}
</style> 