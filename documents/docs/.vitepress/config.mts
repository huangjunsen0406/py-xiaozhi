import { defineConfig } from 'vitepress'
import { getGuideSideBarItems } from './guide'

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
      { text: '贡献指南', link: '/contributing' },
      { text: '特殊贡献者', link: '/contributors' },
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
        // {
        //   text: '资源和支持',
        //   collapsed: true,
        //   items: [
        //     { text: '官方扩展和插件', link: '/ecosystem/resources/official-extensions/' },
        //     { text: '社区贡献', link: '/ecosystem/resources/community-contributions/' },
        //     { text: '兼容设备', link: '/ecosystem/resources/compatible-devices/' }
        //   ]
        // }
      ],
      // 赞助页面不显示侧边栏
      '/sponsors/': [],
      // 贡献指南页面不显示侧边栏
      '/contributing': [],
      // 贡献者名单页面不显示侧边栏
      '/contributors': [],
      // 系统架构页面不显示侧边栏
      '/architecture/': []
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/huangjunsen0406/py-xiaozhi' }
    ]
  }
})
