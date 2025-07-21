<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 relative mb-10">
    <div class="grid grid-cols-1 md:grid-cols-2 gap-x-8 gap-y-6">
      <div v-for="(module, index) in modules" :key="index" class="module-card">
        <div class="flex items-start">
          <div class="w-12 h-12 rounded-lg flex items-center justify-center"
            :class="moduleColors[index % moduleColors.length]">
            <component :is="module.icon" class="w-6 h-6 text-white" />
          </div>
          <div class="ml-4 flex-1">
            <h3 class="text-lg font-semibold text-gray-900 dark:text-white mb-2">{{ module.name }}</h3>
            <ul class="space-y-2">
              <li v-for="(feature, featureIndex) in module.features" :key="featureIndex" class="flex items-start">
                <CheckCircleIcon class="w-5 h-5 text-green-500 mt-1 mr-2" />
                <span class="text-gray-700 dark:text-gray-300">{{ feature }}</span>
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
  CheckCircleIcon,
  CpuChipIcon,
  MapIcon
} from '@heroicons/vue/24/solid';
import { useData } from 'vitepress';

const { isDark } = useData();

// 模块详情
const modules = [
  {
    name: 'src/application.py',
    icon: CogIcon,
    features: [
      '应用主类，采用单例模式管理全局状态',
      '使用asyncio.Task池进行任务管理',
      '实现设备状态机(IDLE/CONNECTING/LISTENING/SPEAKING)',
      '通过命令队列实现线程安全的异步操作'
    ]
  },
  {
    name: 'src/core/resource_manager.py',
    icon: ServerIcon,
    features: [
      '中央化资源生命周期管理',
      '依赖关系跟踪和优先级清理',
      '资源健康监控和统计',
      '自动清理和错误恢复'
    ]
  },
  {
    name: 'src/mcp/mcp_server.py',
    icon: WrenchIcon,
    features: [
      '基于JSON-RPC 2.0的MCP服务器',
      '可扩展的工具插件系统',
      '类型安全的参数验证',
      '支持丰富的MCP工具生态系统'
    ]
  },
  {
    name: 'src/mcp/tools/',
    icon: CpuChipIcon,
    features: [
      '系统工具：应用管理、设备状态监控',
      '日历工具：事件管理、提醒服务',
      '地图工具：位置查询、路线规划',
      '八字工具：命理分析、婚配计算',
      '铁路工具：车次查询、票务信息',
      '音乐工具：播放控制、播放列表管理',
      '定时器工具：任务调度、提醒功能',
      '搜索工具：信息检索、内容查找',
      '食谱工具：菜谱推荐、营养分析',
      '摄像头工具：图像采集、视觉处理'
    ]
  },
  {
    name: 'src/protocols/',
    icon: ArrowsRightLeftIcon,
    features: [
      '抽象协议接口设计',
      'WebSocket协议：实时双向通信',
      'MQTT协议：IoT设备通信',
      'TLS加密和自动重连机制'
    ]
  },
  {
    name: 'src/audio_codecs/',
    icon: DocumentIcon,
    features: [
      '基于Opus的实时音频编解码',
      'SoXR高质量音频重采样',
      '异步音频流处理',
      '低延迟音频缓冲管理'
    ]
  },
  {
    name: 'src/audio_processing/',
    icon: SpeakerXMarkIcon,
    features: [
      'AEC声学回声消除处理器(基于pyaec)',
      '基于Vosk的语音活动检测(VAD)',
      '多语言唤醒词检测',
      '相似度算法和拼音匹配',
      '实时音频处理回调'
    ]
  },
  {
    name: 'src/display/',
    icon: ComputerDesktopIcon,
    features: [
      '策略模式的UI系统架构',
      'PyQt5 + qasync的GUI实现',
      '异步CLI界面支持',
      '情感表情和状态显示'
    ]
  },
  {
    name: 'src/iot/',
    icon: LightBulbIcon,
    features: [
      '基于Thing抽象的IoT设备框架',
      '统一设备管理器和状态同步',
      '属性和方法的动态发现',
      '支持智能家居设备控制'
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
}

.module-card {
  @apply hover:shadow-xl;
}
</style> 