<template>
  <div class="chart-container">
    <div ref="architectureChart" class="w-full h-[500px]"></div>
    <p class="chart-description">Core: container → plugins / protocol / audio / UI</p>
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
    ['#818cf8', '#34d399', '#fbbf24', '#fb7185', '#a78bfa', '#60a5fa', '#4ade80', '#fcd34d'] :
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
    data: ['核心基础设施', '主要模块', '子模块'],
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
        { name: 'ServiceContainer', value: 'lifecycle', category: 0, symbolSize: 70 },
        { name: 'EventBus', value: 'events', category: 0, symbolSize: 55 },
        { name: 'PluginManager', value: 'plugins', category: 1, symbolSize: 50 },
        { name: 'ProtocolManager', value: 'protocol', category: 1, symbolSize: 50 },
        { name: 'AudioCodec', value: 'audio', category: 1, symbolSize: 50 },
        { name: 'MCP Server', value: 'MCP', category: 1, symbolSize: 50 },
        { name: 'ViewPort', value: 'UI', category: 1, symbolSize: 50 },
        { name: 'WebSocket', value: 'WS', category: 2, symbolSize: 32 },
        { name: 'MQTT', value: 'MQTT', category: 2, symbolSize: 32 },
        { name: 'AudioPlugin', value: 'audio plugin', category: 2, symbolSize: 32 },
        { name: 'UIPlugin', value: 'UI plugin', category: 2, symbolSize: 32 },
        { name: 'MCP tools', value: 'tools', category: 2, symbolSize: 32 },
        { name: 'Gui/Cli/Gpio', value: 'views', category: 2, symbolSize: 32 }
      ],
      links: [
        { source: 'ServiceContainer', target: 'EventBus' },
        { source: 'ServiceContainer', target: 'PluginManager' },
        { source: 'ServiceContainer', target: 'ProtocolManager' },
        { source: 'PluginManager', target: 'AudioPlugin' },
        { source: 'PluginManager', target: 'UIPlugin' },
        { source: 'PluginManager', target: 'MCP Server' },
        { source: 'AudioPlugin', target: 'AudioCodec' },
        { source: 'UIPlugin', target: 'ViewPort' },
        { source: 'ViewPort', target: 'Gui/Cli/Gpio' },
        { source: 'ProtocolManager', target: 'WebSocket' },
        { source: 'ProtocolManager', target: 'MQTT' },
        { source: 'MCP Server', target: 'MCP tools' },
        { source: 'EventBus', target: 'PluginManager' }
      ],
      categories: [
        {
          name: '核心基础设施',
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
