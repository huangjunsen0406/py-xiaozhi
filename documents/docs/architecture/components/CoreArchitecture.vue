<template>
  <div class="bg-white rounded-lg relative mb-10">
    <div ref="architectureChart" class="w-full h-[500px]"></div>
    <p class="text-gray-600 mt-4 text-center">核心架构图：展示了应用核心、资源管理器、MCP服务器、通信协议层、音频处理系统、用户界面系统、IoT设备管理等模块的关系</p>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue';
import * as echarts from 'echarts';

const architectureChart = ref(null);

onMounted(() => {
  if (architectureChart.value) {
    const chart = echarts.init(architectureChart.value);
    chart.setOption({
      animation: false,
      tooltip: {
        trigger: 'item',
        formatter: '{b}: {c}'
      },
      legend: {
        orient: 'vertical',
        right: 10,
        top: 'center',
        data: ['核心', '主要模块', '子模块']
      },
      series: [
        {
          name: '架构图',
          type: 'graph',
          layout: 'force',
          data: [
            { name: '应用核心', value: 'Application', category: 0, symbolSize: 70 },
            { name: '资源管理器', value: 'Resource Manager', category: 1, symbolSize: 50 },
            { name: 'MCP服务器', value: 'MCP Server', category: 1, symbolSize: 50 },
            { name: '通信协议层', value: 'Protocols', category: 1, symbolSize: 50 },
            { name: '音频处理系统', value: 'Audio Processing', category: 1, symbolSize: 50 },
            { name: '用户界面系统', value: 'UI System', category: 1, symbolSize: 50 },
            { name: 'IoT设备管理', value: 'IoT Management', category: 1, symbolSize: 50 },
            { name: 'WebSocket', value: 'WebSocket', category: 2, symbolSize: 30 },
            { name: 'MQTT', value: 'MQTT', category: 2, symbolSize: 30 },
            { name: 'MCP工具', value: 'MCP Tools', category: 2, symbolSize: 30 },
            { name: '音频编解码', value: 'Audio Codecs', category: 2, symbolSize: 30 },
            { name: 'VAD检测', value: 'VAD', category: 2, symbolSize: 30 },
            { name: '唤醒词检测', value: 'Wakeword', category: 2, symbolSize: 30 },
            { name: 'GUI界面', value: 'GUI', category: 2, symbolSize: 30 },
            { name: 'CLI界面', value: 'CLI', category: 2, symbolSize: 30 },
            { name: 'Thing抽象', value: 'Thing Abstract', category: 2, symbolSize: 30 },
            { name: '智能家居', value: 'Smart Home', category: 2, symbolSize: 30 }
          ],
          links: [
            { source: '应用核心', target: '资源管理器' },
            { source: '应用核心', target: 'MCP服务器' },
            { source: '应用核心', target: '通信协议层' },
            { source: '应用核心', target: '音频处理系统' },
            { source: '应用核心', target: '用户界面系统' },
            { source: '应用核心', target: 'IoT设备管理' },
            { source: '通信协议层', target: 'WebSocket' },
            { source: '通信协议层', target: 'MQTT' },
            { source: 'MCP服务器', target: 'MCP工具' },
            { source: '音频处理系统', target: '音频编解码' },
            { source: '音频处理系统', target: 'VAD检测' },
            { source: '音频处理系统', target: '唤醒词检测' },
            { source: '用户界面系统', target: 'GUI界面' },
            { source: '用户界面系统', target: 'CLI界面' },
            { source: 'IoT设备管理', target: 'Thing抽象' },
            { source: 'IoT设备管理', target: '智能家居' }
          ],
          categories: [
            { name: '核心' },
            { name: '主要模块' },
            { name: '子模块' }
          ],
          roam: true,
          label: {
            show: true,
            position: 'right',
            formatter: '{b}'
          },
          lineStyle: {
            color: 'source',
            curveness: 0.3
          },
          emphasis: {
            focus: 'adjacency',
            lineStyle: {
              width: 3
            }
          },
          force: {
            repulsion: 300,
            edgeLength: 120
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