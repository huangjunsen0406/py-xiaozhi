import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitepress";
// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "PY-XIAOZHI",
  description:
    "py-xiaozhi 是一个使用 Python 实现的小智语音客户端，旨在通过代码学习和在没有硬件条件下体验 AI 小智的语音功能。",
  base: "/py-xiaozhi/",
  themeConfig: {
    // https://vitepress.dev/reference/default-theme-config
    nav: [
      { text: "主页", link: "/" },
      {
        text: "指南",
        items: [
          { text: "文档目录（重要）", link: "/guide/文档目录" },
          { text: "系统依赖安装", link: "/guide/系统依赖安装" },
          { text: "配置说明", link: "/guide/配置说明" },
          { text: "语音交互模式说明", link: "/guide/语音交互模式说明" },
          { text: "快捷键说明", link: "/guide/快捷键说明" },
          // { text: "回声消除", link: "/guide/回声消除" },
          { text: "语音唤醒", link: "/guide/语音唤醒" },
          { text: "设备激活流程", link: "/guide/设备激活流程" },
          { text: "打包教程", link: "/guide/打包教程" },
          { text: "开发指南", link: "/guide/开发指南" },
          { text: "异常汇总", link: "/guide/异常汇总" },
          { text: "旧版文档", link: "/guide/old_docs/使用文档" },
        ],
      },
      { text: "系统架构", link: "/architecture/" },
      { text: "相关生态", link: "/ecosystem/" },
      {
        text: "MCP",
        items: [
          { text: "开发指南", link: "/mcp/" },
          { text: "相机 (Camera)", link: "/mcp/camera" },
          { text: "Home Assistant (HA)", link: "/mcp/ha" },
          { text: "音乐 (Music)", link: "/mcp/music" },
          { text: "系统 (System)", link: "/mcp/system" },
        ],
      },
      { text: "团队", link: "/about/team" },
      { text: "贡献指南", link: "/contributing" },
      { text: "赞助", link: "/sponsors/" },
    ],

    sidebar: {
      "/about/": [],
      // MCP 页面不显示侧边栏
      "/mcp/": [],
      // 赞助页面不显示侧边栏
      "/sponsors/": [],
      // 贡献指南页面不显示侧边栏
      "/contributing": [],
      // 系统架构页面不显示侧边栏
      "/architecture/": [],
      // 团队页面不显示侧边栏
      "/about/team": [],
    },

    socialLinks: [
      { icon: "github", link: "https://github.com/huangjunsen0406/py-xiaozhi" },
    ],
  },
  vite: {
    plugins: [tailwindcss()],
  },
});
