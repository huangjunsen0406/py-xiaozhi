<template>
  <div class="chart-container">
    <div ref="architectureChart" class="w-full h-[500px]"></div>
    <p class="chart-description">核心架构图：展示了应用核心、资源管理器、MCP服务器、通信协议层、音频处理系统、用户界面系统、IoT设备管理等模块的关系</p>
  </div>
</template>

<script setup>
import { ref, onMounted, watch } from 'vue';
import * as echarts from 'echarts';
import { useData } from 'vitepress';

const { isDark } = useData();
const architectureChart = ref(null);
let chart = null;

const createChartOption = (darkMode) => ({
  animation: false,
  backgroundColor: 'transparent',
  color: darkMode ?
    // 暗色模式：现代科技感配色 - 蓝紫系为主，辅以自然色彩
    ['#818cf8', '#34d399', '#fbbf24', '#fb7185', '#a78bfa', '#60a5fa', '#4ade80', '#fcd34d'] :
    // 亮色模式：商务专业配色 - 深沉稳重，层次分明
    ['#4338ca', '#059669', '#d97706', '#e11d48', '#7c3aed', '#0369a1', '#16a34a', '#ca8a04'],
  tooltip: {
    trigger: 'item',
    formatter: '{b}: {c}',
    backgroundColor: darkMode ? '#374151' : '#ffffff',
    borderColor: darkMode ? '#4b5563' : '#e5e7eb',
    borderWidth: 1,
    textStyle: {
      color: darkMode ? '#f3f4f6' : '#374151'
    }
  },
  legend: {
    orient: 'vertical',
    right: 10,
    top: 'center',
    data: ['核心', '主要模块', '子模块'],
    textStyle: {
      color: darkMode ? '#f3f4f6' : '#374151'
    },
    backgroundColor: darkMode ? 'rgba(55, 65, 81, 0.8)' : 'rgba(255, 255, 255, 0.8)',
    borderRadius: 4,
    padding: 10
  },
  series: [
    {
      name: '架构图',
      type: 'graph',
      layout: 'force',
      data: [
        { name: '应用核心', value: 'Application', category: 0, symbolSize: 70 },
        { name: 'MCP服务器', value: 'MCP Server', category: 1, symbolSize: 50 },
        { name: '通信协议层', value: 'Protocols', category: 1, symbolSize: 50 },
        { name: '音频处理系统', value: 'Audio Processing', category: 1, symbolSize: 50 },
        { name: '用户界面系统', value: 'UI System', category: 1, symbolSize: 50 },
        { name: 'IoT设备管理', value: 'IoT Management', category: 1, symbolSize: 50 },
        { name: 'WebSocket', value: 'WebSocket', category: 2, symbolSize: 30 },
        { name: 'MQTT', value: 'MQTT', category: 2, symbolSize: 30 },
        { name: 'MCP工具生态', value: 'MCP Tools Ecosystem', category: 2, symbolSize: 30 },
        { name: 'AEC处理', value: 'AEC Processing', category: 2, symbolSize: 30 },
        { name: 'VAD检测', value: 'VAD Detection', category: 2, symbolSize: 30 },
        { name: '唤醒词检测', value: 'Wakeword Detection', category: 2, symbolSize: 30 },
        { name: 'PyQt5 GUI', value: 'PyQt5 GUI', category: 2, symbolSize: 30 },
        { name: 'CLI界面', value: 'CLI Interface', category: 2, symbolSize: 30 },
        { name: 'Thing抽象', value: 'Thing Abstract', category: 2, symbolSize: 30 },
        { name: '智能家居', value: 'Smart Home', category: 2, symbolSize: 30 }
      ],
      links: [
        { source: '应用核心', target: 'MCP服务器' },
        { source: '应用核心', target: '通信协议层' },
        { source: '应用核心', target: '音频处理系统' },
        { source: '应用核心', target: '用户界面系统' },
        { source: '应用核心', target: 'IoT设备管理' },
        { source: '通信协议层', target: 'WebSocket' },
        { source: '通信协议层', target: 'MQTT' },
        { source: 'MCP服务器', target: 'MCP工具生态' },
        { source: '音频处理系统', target: 'AEC处理' },
        { source: '音频处理系统', target: 'VAD检测' },
        { source: '音频处理系统', target: '唤醒词检测' },
        { source: '用户界面系统', target: 'PyQt5 GUI' },
        { source: '用户界面系统', target: 'CLI界面' },
        { source: 'IoT设备管理', target: 'Thing抽象' },
        { source: 'IoT设备管理', target: '智能家居' }
      ],
      categories: [
        { 
          name: '核心',
          itemStyle: {
            color: '#5470c6',
            borderColor: '#5470c6',
            borderWidth: 2
          }
        },
        { 
          name: '主要模块',
          itemStyle: {
            color: '#93cc76',
            borderColor: '#93cc76',
            borderWidth: 2
          }
        },
        { 
          name: '子模块',
          itemStyle: {
            color: '#fac858',
            borderColor: '#fac858',
            borderWidth: 1
          }
        }
      ],
      roam: true,
      label: {
        show: true,
        position: 'right',
        formatter: '{b}',
        color: darkMode ? '#f3f4f6' : '#374151'
      },
      lineStyle: {
        color: darkMode ? '#64748b' : '#94a3b8',
        width: 2,
        curveness: 0.2,
        opacity: 0.6
      },
      emphasis: {
        focus: 'adjacency',
        lineStyle: {
          width: 4,
          opacity: 1,
          color: darkMode ? '#3b82f6' : '#2563eb'
        },
        itemStyle: {
          shadowBlur: 10,
          shadowColor: darkMode ? 'rgba(59, 130, 246, 0.5)' : 'rgba(37, 99, 235, 0.3)'
        }
      },
      force: {
        repulsion: 400,
        edgeLength: 150,
        gravity: 0.1
      },
      itemStyle: {
        shadowBlur: 8,
        shadowColor: darkMode ? 'rgba(0, 0, 0, 0.3)' : 'rgba(0, 0, 0, 0.1)'
      }
    }
  ]
});

const initChart = () => {
  if (architectureChart.value) {
    chart = echarts.init(architectureChart.value);
    chart.setOption(createChartOption(isDark.value));
    window.addEventListener('resize', () => {
      chart.resize();
    });
  }
};

onMounted(() => {
  initChart();
});

// 监听主题切换
watch(isDark, (newValue) => {
  if (chart) {
    chart.setOption(createChartOption(newValue));
  }
});
</script>

<style scoped>
.chart-container {
  background-color: var(--vp-c-bg);
  border-radius: 12px;
  padding: 24px;
  margin-bottom: 40px;
}

.chart-description {
  color: var(--vp-c-text-2);
  text-align: center;
  margin-top: 16px;
  font-size: 14px;
}
</style> 