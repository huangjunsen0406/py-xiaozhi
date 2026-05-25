import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vitepress";
// https://vitepress.dev/reference/site-config
export default defineConfig({
  title: "PY-XIAOZHI",
  description:
    "py-xiaozhi is a Python-based Xiaozhi voice client for learning and experiencing AI voice features without hardware.",
  base: "/py-xiaozhi/",
  locales: {
    root: {
      label: "English",
      lang: "en-US",
      link: "/",
      themeConfig: {
        langMenuLabel: "Languages",
        // https://vitepress.dev/reference/default-theme-config
        nav: [
          { text: "Home", link: "/" },
          {
            text: "Guide",
            items: [
              { text: "Documentation Directory", link: "/guide/文档目录" },
              { text: "System Dependencies", link: "/guide/系统依赖安装" },
              { text: "Configuration Guide", link: "/guide/配置说明" },
              { text: "Voice Interaction Modes", link: "/guide/语音交互模式说明" },
              { text: "Keyboard Shortcuts", link: "/guide/快捷键说明" },
              // { text: "Echo Cancellation", link: "/guide/回声消除" },
              { text: "Wake Word", link: "/guide/语音唤醒" },
              { text: "Device Activation", link: "/guide/设备激活流程" },
              { text: "Packaging Guide", link: "/guide/打包教程" },
              { text: "Development Guide", link: "/guide/开发指南" },
              { text: "Troubleshooting", link: "/guide/异常汇总" },
              { text: "Legacy Docs", link: "/guide/old_docs/使用文档" },
            ],
          },
          { text: "Architecture", link: "/architecture/" },
          { text: "Ecosystem", link: "/ecosystem/" },
          {
            text: "MCP",
            items: [
              { text: "MCP Guide", link: "/mcp/" },
              { text: "Camera", link: "/mcp/camera" },
              { text: "Home Assistant (HA)", link: "/mcp/ha" },
              { text: "Music", link: "/mcp/music" },
              { text: "System", link: "/mcp/system" },
            ],
          },
          { text: "Team", link: "/about/team" },
          { text: "Contributing", link: "/contributing" },
          { text: "Sponsors", link: "/sponsors/" },
        ],

        sidebar: {
          "/about/": [],
          "/mcp/": [],
          "/sponsors/": [],
          "/contributing": [],
          "/architecture/": [],
          "/about/team": [],
        },

        socialLinks: [
          {
            icon: "github",
            link: "https://github.com/huangjunsen0406/py-xiaozhi",
          },
        ],
      },
    },
    zh: {
      label: "简体中文",
      lang: "zh-CN",
      link: "/zh/",
      themeConfig: {
        langMenuLabel: "语言",
        nav: [
          { text: "主页", link: "/zh/" },
          {
            text: "指南",
            items: [
              { text: "文档目录（重要）", link: "/zh/guide/文档目录" },
              { text: "系统依赖安装", link: "/zh/guide/系统依赖安装" },
              { text: "配置说明", link: "/zh/guide/配置说明" },
              { text: "语音交互模式说明", link: "/zh/guide/语音交互模式说明" },
              { text: "快捷键说明", link: "/zh/guide/快捷键说明" },
              // { text: "回声消除", link: "/zh/guide/回声消除" },
              { text: "语音唤醒", link: "/zh/guide/语音唤醒" },
              { text: "设备激活流程", link: "/zh/guide/设备激活流程" },
              { text: "打包教程", link: "/zh/guide/打包教程" },
              { text: "开发指南", link: "/zh/guide/开发指南" },
              { text: "异常汇总", link: "/zh/guide/异常汇总" },
              { text: "旧版文档", link: "/zh/guide/old_docs/使用文档" },
            ],
          },
          { text: "系统架构", link: "/zh/architecture/" },
          { text: "相关生态", link: "/zh/ecosystem/" },
          {
            text: "MCP",
            items: [
              { text: "开发指南", link: "/zh/mcp/" },
              { text: "相机 (Camera)", link: "/zh/mcp/camera" },
              { text: "Home Assistant (HA)", link: "/zh/mcp/ha" },
              { text: "音乐 (Music)", link: "/zh/mcp/music" },
              { text: "系统 (System)", link: "/zh/mcp/system" },
            ],
          },
          { text: "团队", link: "/zh/about/team" },
          { text: "贡献指南", link: "/zh/contributing" },
          { text: "赞助", link: "/zh/sponsors/" },
        ],

        sidebar: {
          "/zh/about/": [],
          "/zh/mcp/": [],
          "/zh/sponsors/": [],
          "/zh/contributing": [],
          "/zh/architecture/": [],
          "/zh/about/team": [],
        },

        socialLinks: [
          {
            icon: "github",
            link: "https://github.com/huangjunsen0406/py-xiaozhi",
          },
        ],
      },
    },
  },
  vite: {
    plugins: [tailwindcss()],
  },
});
