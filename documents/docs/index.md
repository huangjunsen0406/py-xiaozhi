---
# https://vitepress.dev/reference/default-theme-home-page
layout: home

hero:
  name: "PY-XIAOZHI"
  tagline: py-xiaozhi 是一个使用 Python 实现的小智语音客户端，旨在通过代码学习和在没有硬件条件下体验 AI 小智的语音功能。
  actions:
    - theme: brand
      text: 开始使用
      link: /guide/文档目录
    - theme: alt
      text: 查看源码
      link: https://github.com/huangjunsen0406/py-xiaozhi

features:
  - title: AI语音交互
    details: 支持语音输入与识别，实现智能人机交互，提供自然流畅的对话体验。采用异步架构设计，支持实时音频处理和低延迟响应。
  - title: 视觉多模态
    details: 支持图像识别和处理，提供多模态交互能力，理解图像内容。集成OpenCV摄像头处理，支持实时视觉分析。
  - title: MCP工具服务器
    details: 基于JSON-RPC 2.0协议的模块化工具系统，支持日程管理、音乐播放、12306查询、地图服务、菜谱搜索、八字命理等丰富功能，可动态扩展工具插件。
  - title: IoT 设备集成
    details: 采用Thing抽象模式设计，支持智能家居设备控制，包括灯光、音量、温度传感器等，集成Home Assistant智能家居平台，可轻松扩展。
  - title: 高性能音频处理
    details: 基于Opus编解码的实时音频传输，支持智能重采样技术，5ms音频帧间隔处理，确保低延迟高质量的音频体验。
  - title: 跨平台支持
    details: 兼容Windows 10+、macOS 10.15+和Linux系统，支持GUI和CLI双模式运行，自适应不同平台的音频设备和系统接口。
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
