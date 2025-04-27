import { defineConfig } from 'vitepress'
import { getGuideSideBarItems } from './guide'
import tailwindcss from '@tailwindcss/vite'
// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "PY-XIAOZHI",
  description: "py-xiaozhi 是一个使用 Python 实现的小智语音客户端，旨在通过代码学习和在没有硬件条件下体验 AI 小智的语音功能。",
  base: '/py-xiaozhi/',
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: '主页', link: '/' },
      { text: '指南', link: '/guide/00_文档目录' },
      { text: '系统架构', link: '/architecture/' },
      { text: '相关生态', link: '/ecosystem/' },
      { text: '团队', link: '/about/team' },
      { text: '贡献指南', link: '/contributing' },
      { text: '赞助', link: '/sponsors/' }
    ],

    sidebar: {
      '/guide/': [
        {
          text: '指南',
          // 默认展开
          collapsed: false,
          items: getGuideSideBarItems(),
        },
        {
          text: '旧版文档',
          collapsed: true,
          items: [
            { text: '使用文档', link: '/guide/old_docs/使用文档' }
          ]
        }
      ],
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
