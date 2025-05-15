---
# https://vitepress.dev/reference/default-theme-home-page
layout: home

hero:
  name: "PY-XIAOZHI"
  tagline: py-xiaozhi 是一个使用 Python 实现的小智语音客户端，旨在通过代码学习和在没有硬件条件下体验 AI 小智的语音功能。
  actions:
    - theme: brand
      text: 开始使用
      link: /guide/00_文档目录
    - theme: alt
      text: 查看源码
      link: https://github.com/huangjunsen0406/py-xiaozhi

features:
  - title: AI语音交互
    details: 支持语音输入与识别，实现智能人机交互，提供自然流畅的对话体验。
  - title: 视觉多模态
    details: 支持图像识别和处理，提供多模态交互能力，理解图像内容。
  - title: IoT 设备集成
    details: 支持智能家居设备控制，包括灯光、音量、温度传感器等，集成Home Assistant智能家居平台，提供倒计时器功能，内置多种虚拟设备和物理设备驱动，可轻松扩展。
  - title: 联网音乐播放
    details: 基于pygame实现的高性能音乐播放器，支持播放／暂停／停止、进度控制、歌词显示和本地缓存，提供更稳定的音乐播放体验。
  - title: 语音唤醒
    details: 支持唤醒词激活交互，免去手动操作的烦恼（默认关闭需要手动开启）。
  - title: 自动对话模式
    details: 实现连续对话体验，提升用户交互流畅度。
  - title: 图形化界面
    details: 提供直观易用的 GUI，支持小智表情与文本显示，增强视觉体验。
  - title: 命令行模式
    details: 支持 CLI 运行，适用于嵌入式设备或无 GUI 环境。
  - title: 跨平台支持
    details: 兼容 Windows 10+、macOS 10.15+ 和 Linux 系统，随时随地使用。
  - title: 音量控制
    details: 支持音量调节，适应不同环境需求，统一声音控制接口。
  - title: 加密音频传输
    details: 支持 WSS 协议，保障音频数据的安全性，防止信息泄露。
  - title: 自动验证码处理
    details: 首次使用时，程序自动复制验证码并打开浏览器，简化用户操作。
---

<div class="developers-section">
  <p>感谢以下开发者对 py-xiaozhi 作出的贡献</p>
  
  <div class="contributors-wrapper">
    <a href="https://github.com/huangjunsen0406/py-xiaozhi/graphs/contributors" class="contributors-link">
      <img src="https://contrib.rocks/image?repo=huangjunsen0406/py-xiaozhi&max=1000" alt="contributors" class="contributors-image"/>
    </a>
  </div>
  
  <div class="developers-actions">
    <a href="/py-xiaozhi/contributors" class="dev-button">查看特别贡献者</a>
    <a href="/py-xiaozhi/contributing" class="dev-button outline">如何参与贡献</a>
  </div>

</div>

<style>
.developers-section {
  text-align: center;
  max-width: 960px;
  margin: 4rem auto 0;
  padding: 2rem;
  border-top: 1px solid var(--vp-c-divider);
}

.developers-section h2 {
  margin-bottom: 0.5rem;
  color: var(--vp-c-brand);
}

.contributors-wrapper {
  margin: 2rem auto;
  max-width: 800px;
  position: relative;
  overflow: hidden;
  border-radius: 10px;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
  transition: all 0.3s ease;
}

.contributors-wrapper:hover {
  transform: translateY(-5px);
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.15);
}

.contributors-link {
  display: block;
  text-decoration: none;
  background-color: var(--vp-c-bg-soft);
}

.contributors-image {
  width: 100%;
  height: auto;
  display: block;
  transition: all 0.3s ease;
}


.developers-actions {
  display: flex;
  gap: 1rem;
  justify-content: center;
  margin-top: 1.5rem;
}

.developers-actions a {
  text-decoration: none;
}

.dev-button {
  display: inline-block;
  border-radius: 20px;
  padding: 0.5rem 1.5rem;
  font-weight: 500;
  transition: all 0.2s ease;
  text-decoration: none;
}

.dev-button:not(.outline) {
  background-color: var(--vp-c-brand);
  color: white;
}

.dev-button.outline {
  border: 1px solid var(--vp-c-brand);
  color: var(--vp-c-brand);
}

.dev-button:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
}

@media (max-width: 640px) {
  .developers-actions {
    flex-direction: column;
  }
  
  .contributors-wrapper {
    margin: 1.5rem auto;
  }
}

.join-message {
  text-align: center;
  margin-top: 2rem;
  padding: 2rem;
  border-top: 1px solid var(--vp-c-divider);
}

.join-message h3 {
  margin-bottom: 1rem;
}
</style>

