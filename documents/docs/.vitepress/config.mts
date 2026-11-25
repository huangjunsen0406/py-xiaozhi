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
              { text: "Echo Cancellation", link: "/guide/回声消除" },
              { text: "Wake Word", link: "/guide/语音唤醒" },
              { text: "Device Activation", link: "/guide/设备激活流程" },
              { text: "Packaging Guide", link: "/guide/打包教程" },
              { text: "Development Guide", link: "/guide/开发指南" },
              { text: "Troubleshooting", link: "/guide/异常汇总" },
            ],
          },
          { text: "Architecture", link: "/architecture/" },
          { text: "Ecosystem", link: "/ecosystem/" },
          {
            text: "MCP",
            items: [
              { text: "MCP Guide", link: "/mcp/" },
              { text: "External Plugins", link: "/mcp/plugins" },
              { text: "Camera", link: "/mcp/camera" },
              { text: "Home Assistant (HA)", link: "/mcp/ha" },
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
              { text: "回声消除", link: "/zh/guide/回声消除" },
              { text: "语音唤醒", link: "/zh/guide/语音唤醒" },
              { text: "设备激活流程", link: "/zh/guide/设备激活流程" },
              { text: "打包教程", link: "/zh/guide/打包教程" },
              { text: "开发指南", link: "/zh/guide/开发指南" },
              { text: "异常汇总", link: "/zh/guide/异常汇总" },
            ],
          },
          { text: "系统架构", link: "/zh/architecture/" },
          { text: "相关生态", link: "/zh/ecosystem/" },
          {
            text: "MCP",
            items: [
              { text: "开发指南", link: "/zh/mcp/" },
              { text: "外挂扩展", link: "/zh/mcp/plugins" },
              { text: "相机 (Camera)", link: "/zh/mcp/camera" },
              { text: "Home Assistant (HA)", link: "/zh/mcp/ha" },
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
    vi: {
      label: "Tiếng Việt",
      lang: "vi-VN",
      link: "/vi/",
      description:
        "py-xiaozhi là client trợ lý giọng nói AI đa phương thức dựa trên Python, gọn nhẹ, đa nền tảng và dễ mở rộng.",
      themeConfig: {
        langMenuLabel: "Ngôn ngữ",
        returnToTopLabel: "Lên đầu trang",
        sidebarMenuLabel: "Mục lục",
        darkModeSwitchLabel: "Giao diện",
        lightModeSwitchTitle: "Chuyển sang chế độ sáng",
        darkModeSwitchTitle: "Chuyển sang chế độ tối",
        outline: {
          label: "Trên trang này",
        },
        docFooter: {
          prev: "Trang trước",
          next: "Trang sau",
        },
        nav: [
          { text: "Trang chủ", link: "/vi/" },
          {
            text: "Hướng dẫn",
            items: [
              { text: "Danh mục tài liệu", link: "/vi/guide/文档目录" },
              { text: "Cài đặt phụ thuộc hệ thống", link: "/vi/guide/系统依赖安装" },
              { text: "Hướng dẫn cấu hình", link: "/vi/guide/配置说明" },
              { text: "Chế độ tương tác giọng nói", link: "/vi/guide/语音交互模式说明" },
              { text: "Phím tắt", link: "/vi/guide/快捷键说明" },
              { text: "Khử tiếng vọng (AEC)", link: "/vi/guide/回声消除" },
              { text: "Đánh thức bằng giọng nói", link: "/vi/guide/语音唤醒" },
              { text: "Quy trình kích hoạt thiết bị", link: "/vi/guide/设备激活流程" },
              { text: "Hướng dẫn đóng gói", link: "/vi/guide/打包教程" },
              { text: "Hướng dẫn phát triển", link: "/vi/guide/开发指南" },
              { text: "Khắc phục sự cố", link: "/vi/guide/异常汇总" },
            ],
          },
          { text: "Kiến trúc", link: "/vi/architecture/" },
          { text: "Hệ sinh thái", link: "/vi/ecosystem/" },
          {
            text: "MCP",
            items: [
              { text: "Hướng dẫn MCP", link: "/vi/mcp/" },
              { text: "Plugin mở rộng", link: "/vi/mcp/plugins" },
              { text: "Camera", link: "/vi/mcp/camera" },
              { text: "Home Assistant (HA)", link: "/vi/mcp/ha" },
              { text: "Hệ thống (System)", link: "/vi/mcp/system" },
            ],
          },
          { text: "Đội ngũ", link: "/vi/about/team" },
          { text: "Đóng góp", link: "/vi/contributing" },
          { text: "Tài trợ", link: "/vi/sponsors/" },
        ],

        sidebar: {
          "/vi/about/": [],
          "/vi/mcp/": [],
          "/vi/sponsors/": [],
          "/vi/contributing": [],
          "/vi/architecture/": [],
          "/vi/about/team": [],
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
