<template>
  <div class="bg-white dark:bg-gray-800 rounded-lg border border-gray-200 dark:border-gray-700 relative mb-10">
    <div ref="stateChart" class="w-full h-[300px]"></div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
      <div v-for="(state, index) in states" :key="index" class="bg-gray-50 dark:bg-gray-700 p-4 rounded-lg border-l-4"
        :class="stateBorderColors[index]">
        <h4 class="font-bold text-gray-900 dark:text-white mb-2">{{ state.name }}</h4>
        <p class="text-gray-700 dark:text-gray-300">{{ state.description }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, computed, watch } from 'vue';
import { useData } from 'vitepress';
import * as echarts from 'echarts';

const { isDark } = useData();

// 状态管理数据
const states = [
  { name: 'IDLE', description: '空闲状态，等待用户交互或唤醒词，系统处于低功耗模式' },
  { name: 'CONNECTING', description: '正在建立与AI服务的连接，初始化语音会话' },
  { name: 'LISTENING', description: '正在监听用户输入，启用VAD检测和AEC处理' },
  { name: 'SPEAKING', description: '正在播放语音回复，配置参考音频信号' }
];

const stateBorderColors = [
  'border-blue-500',
  'border-yellow-500',
  'border-green-500',
  'border-purple-500'
];

const stateChart = ref(null);
let chart = null;

const getThemeOptions = computed(() => {
  const backgroundColor = 'transparent';
  const textColor = isDark.value ? '#e5e7eb' : '#374151';
  const lineColor = isDark.value ? '#6b7280' : '#9ca3af';
  
  return {
    backgroundColor,
    textStyle: {
      color: textColor
    },
    tooltip: {
      backgroundColor: isDark.value ? '#374151' : '#ffffff',
      borderColor: isDark.value ? '#6b7280' : '#e5e7eb',
      textStyle: {
        color: textColor
      }
    },
    lineColor
  };
});

const updateChart = () => {
  if (!chart) return;
  
  const theme = getThemeOptions.value;
  chart.setOption({
    backgroundColor: theme.backgroundColor,
    textStyle: theme.textStyle,
    animation: false,
    tooltip: {
      trigger: 'item',
      formatter: '{b}',
      ...theme.tooltip
    },
    series: [
      {
        type: 'graph',
        layout: 'circular',
        symbolSize: 60,
        roam: false,
        label: {
          show: true,
          color: theme.textStyle.color
        },
        edgeSymbol: ['circle', 'arrow'],
        edgeSymbolSize: [4, 10],
        edgeLabel: {
          fontSize: 12,
          color: theme.textStyle.color
        },
        data: [
          { name: 'IDLE', itemStyle: { color: isDark.value ? '#3b82f6' : '#2563eb' } },
          { name: 'CONNECTING', itemStyle: { color: isDark.value ? '#eab308' : '#ca8a04' } },
          { name: 'LISTENING', itemStyle: { color: isDark.value ? '#22c55e' : '#16a34a' } },
          { name: 'SPEAKING', itemStyle: { color: isDark.value ? '#a855f7' : '#9333ea' } }
        ],
        links: [
          { source: 'IDLE', target: 'CONNECTING', label: { show: true, formatter: '唤醒', color: theme.textColor } },
          { source: 'CONNECTING', target: 'LISTENING', label: { show: true, formatter: '连接成功', color: theme.textColor } },
          { source: 'LISTENING', target: 'SPEAKING', label: { show: true, formatter: '收到响应', color: theme.textColor } },
          { source: 'SPEAKING', target: 'IDLE', label: { show: true, formatter: '播放完成', color: theme.textColor } },
          { source: 'LISTENING', target: 'IDLE', label: { show: true, formatter: '超时', color: theme.textColor } },
          { source: 'CONNECTING', target: 'IDLE', label: { show: true, formatter: '连接失败', color: theme.textColor } }
        ],
        lineStyle: {
          opacity: 0.9,
          width: 2,
          curveness: 0.2,
          color: theme.lineColor
        }
      }
    ]
  });
};

onMounted(() => {
  if (stateChart.value) {
    chart = echarts.init(stateChart.value);
    updateChart();
    
    // 监听主题变化
    const observer = new MutationObserver(() => {
      setTimeout(updateChart, 100);
    });
    
    observer.observe(document.documentElement, {
      attributes: true,
      attributeFilter: ['class']
    });
    
    window.addEventListener('resize', () => {
      chart.resize();
    });
  }
});

// 监听主题变化
watch(isDark, () => {
  updateChart();
});
</script> 