import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vitepress'
// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "PY-XIAOZHI",
  description: "py-xiaozhi 是一个使用 Python 实现的小智语音客户端，旨在通过代码学习和在没有硬件条件下体验 AI 小智的语音功能。",
  base: '/py-xiaozhi/',
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: '主页', link: '/' },
      {
        text: '指南',
        items: [
          { text: '文档目录（重要）', link: '/guide/文档目录' },
          { text: '系统依赖安装', link: '/guide/系统依赖安装' },
          { text: '配置说明', link: '/guide/配置说明' },
          { text: '语音交互模式说明', link: '/guide/语音交互模式说明' },
          { text: '快捷键说明', link: '/guide/快捷键说明.md'},
          { text: '语音唤醒', link: '/guide/语音唤醒' },
          { text: '设备激活流程', link: '/guide/设备激活流程' },
          { text: '打包教程', link: '/guide/打包教程' },
          { text: '异常汇总', link: '/guide/异常汇总' },
          { text: '旧版文档', link: '/guide/old_docs/使用文档' },
        ]
      },
      { text: '系统架构', link: '/architecture/' },
      { text: '相关生态', link: '/ecosystem/' },
      {
        text: 'IoT',
        items: [
          { text: '开发指南', link: '/iot/' },
        ]
      },
      {
        text: 'MCP',
        items: [
          { text: '开发指南', link: '/mcp/' },
          { text: '高德地图 (Amap)', link: '/mcp/amap' },
          { text: '八字 (Bazi)', link: '/mcp/bazi' },
          { text: '日历 (Calendar)', link: '/mcp/calendar' },
          { text: '相机 (Camera)', link: '/mcp/camera' },
          { text: '音乐 (Music)', link: '/mcp/music' },
          { text: '火车票 (Railway)', link: '/mcp/railway' },
          { text: '菜谱 (Recipe)', link: '/mcp/recipe' },
          { text: '搜索 (Search)', link: '/mcp/search' },
          { text: '系统 (System)', link: '/mcp/system' },
          { text: '计时器 (Timer)', link: '/mcp/timer' }
        ]
      },
      { text: '团队', link: '/about/team' },
      { text: '贡献指南', link: '/contributing' },
      { text: '赞助', link: '/sponsors/' }
    ],

    sidebar: {
      '/ecosystem/': [
        {
          text: '生态系统概览',
          link: '/ecosystem/'
        },
        {
          text: '相关项目',
          collapsed: false,
          items: [
            { text: '小智手机端', link: '/ecosystem/projects/xiaozhi-android-client/' },
            { text: 'xiaozhi-esp32-server', link: '/ecosystem/projects/xiaozhi-esp32-server/' },
            { text: 'XiaoZhiAI_server32_Unity', link: '/ecosystem/projects/xiaozhi-unity/' },
            { text: 'IntelliConnect', link: '/ecosystem/projects/intelliconnect/' },
            { text: 'open-xiaoai', link: '/ecosystem/projects/open-xiaoai/' }
          ]
        },
      ],
      '/about/': [],
      // MCP 页面不显示侧边栏
      '/mcp/': [],
      // IoT 页面不显示侧边栏
      '/iot/': [],
      // 赞助页面不显示侧边栏
      '/sponsors/': [],
      // 贡献指南页面不显示侧边栏
      '/contributing': [],
      // 系统架构页面不显示侧边栏
      '/architecture/': [],
      // 团队页面不显示侧边栏
      '/about/team': []
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/huangjunsen0406/py-xiaozhi' }
    ]
  },
  vite: {
    plugins: [
        tailwindcss()
    ]
  }
})
