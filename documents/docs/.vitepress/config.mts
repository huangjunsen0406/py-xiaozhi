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
      { text: '相关生态', link: '/ecosystem' },
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
      // 赞助页面不显示侧边栏
      '/sponsors/': [],
      // 贡献指南页面不显示侧边栏
      '/contributing': [],
      // 贡献者名单页面不显示侧边栏
      '/contributors': [],
      // 相关生态页面不显示侧边栏
      '/ecosystem': []
    },

    socialLinks: [
      { icon: 'github', link: 'https://github.com/huangjunsen0406/py-xiaozhi' }
    ]
  }
})
