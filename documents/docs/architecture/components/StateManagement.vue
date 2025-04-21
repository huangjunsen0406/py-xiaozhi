<template>
  <div class="bg-white rounded-lg relative mb-10">
    <div ref="stateChart" class="w-full h-[300px]"></div>
    <div class="grid grid-cols-1 md:grid-cols-2 gap-6 mt-6">
      <div v-for="(state, index) in states" :key="index" class="bg-gray-50 p-4 rounded-lg border-l-4"
        :class="stateBorderColors[index]">
        <h4 class="font-bold mb-2">{{ state.name }}</h4>
        <p class="text-gray-700">{{ state.description }}</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import * as echarts from 'echarts';

// 状态管理数据
const states = [
  { name: 'IDLE', description: '空闲状态，等待用户交互或唤醒词' },
  { name: 'CONNECTING', description: '正在建立连接' },
  { name: 'LISTENING', description: '正在监听用户输入' },
  { name: 'SPEAKING', description: '正在播放语音回复' }
];

const stateBorderColors = [
  'border-blue-500',
  'border-yellow-500',
  'border-green-500',
  'border-purple-500'
];

const stateChart = ref(null);

onMounted(() => {
  if (stateChart.value) {
    const chart = echarts.init(stateChart.value);
    chart.setOption({
      animation: false,
      tooltip: {
        trigger: 'item',
        formatter: '{b}'
      },
      series: [
        {
          type: 'graph',
          layout: 'circular',
          symbolSize: 60,
          roam: false,
          label: {
            show: true
          },
          edgeSymbol: ['circle', 'arrow'],
          edgeSymbolSize: [4, 10],
          edgeLabel: {
            fontSize: 12
          },
          data: [
            { name: 'IDLE', itemStyle: { color: '#3b82f6' } },
            { name: 'CONNECTING', itemStyle: { color: '#eab308' } },
            { name: 'LISTENING', itemStyle: { color: '#22c55e' } },
            { name: 'SPEAKING', itemStyle: { color: '#a855f7' } }
          ],
          links: [
            { source: 'IDLE', target: 'CONNECTING', label: { show: true, formatter: '唤醒' } },
            { source: 'CONNECTING', target: 'LISTENING', label: { show: true, formatter: '连接成功' } },
            { source: 'LISTENING', target: 'SPEAKING', label: { show: true, formatter: '收到响应' } },
            { source: 'SPEAKING', target: 'IDLE', label: { show: true, formatter: '播放完成' } },
            { source: 'LISTENING', target: 'IDLE', label: { show: true, formatter: '超时' } },
            { source: 'CONNECTING', target: 'IDLE', label: { show: true, formatter: '连接失败' } }
          ],
          lineStyle: {
            opacity: 0.9,
            width: 2,
            curveness: 0.2
          }
        }
      ]
    });
    window.addEventListener('resize', () => {
      chart.resize();
    });
  }
});
</script> 