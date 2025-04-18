import { defineConfig } from 'vitepress'
import { getGuideSideBarItems } from './guide'

console.log('getGuideSideBarItems()', getGuideSideBarItems());


// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "PY-XIAOZHI",
  description: "py-xiaozhi 是一个使用 Python 实现的小智语音客户端，旨在通过代码学习和在没有硬件条件下体验 AI 小智的语音功能。",
  base: '/',
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: '主页', link: '/' },
      { text: '指南', link: '/guide/00_文档目录' },
    ],

    sidebar: [
      {
        text: '指南',
        // 默认展开
        collapsed: false,
        base: '/guide/',
        items: getGuideSideBarItems(),
      },
    ],

    socialLinks: [
      { icon: 'github', link: 'https://github.com/huangjunsen0406/py-xiaozhi' }
    ]
  }
})
