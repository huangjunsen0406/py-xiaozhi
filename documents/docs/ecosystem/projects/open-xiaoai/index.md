---
title: open-xiaoai
description: 让小爱音箱「听见你的声音」，解锁无限可能的开源项目
---

# open-xiaoai

<div class="project-header">
  <div class="project-logo">
    <img src="https://avatars.githubusercontent.com/u/35302658?s=48&v=4" alt="open-xiaoai Logo">
  </div>
  <div class="project-badges">
    <span class="badge platform">跨平台</span>
    <span class="badge language">Rust/Python/Node.js</span>
    <span class="badge status">实验性</span>
  </div>
</div>

<div class="project-banner">
  <img src="./images/logo.png" alt="Open-XiaoAI 项目封面">
</div>

## 项目简介

Open-XiaoAI 是一个让小爱音箱"听见你的声音"的开源项目，将小爱音箱与小智AI生态系统无缝集成。该项目直接接管小爱音箱的"耳朵"和"嘴巴"，通过多模态大模型和AI Agent技术，将小爱音箱的潜力完全释放，解锁无限可能。

2017年，当全球首款千万级销量的智能音箱诞生时，我们以为触摸到了未来。但很快发现，这些设备被困在「指令-响应」的牢笼里：

- 它听得见分贝，却听不懂情感
- 它能执行命令，却不会主动思考
- 它有千万用户，却只有一套思维

我们曾幻想中的"贾维斯"级人工智能，在现实场景中沦为"闹钟+音乐播放器"。

**真正的智能不应被预设的代码逻辑所束缚，而应像生命体般在交互中进化。**

在上一个 [MiGPT](https://github.com/idootop/mi-gpt) 项目的基础上，Open-XiaoAI再次进化，为小智生态系统提供了与小爱音箱交互的新方式。

## 核心功能

<div class="features-grid">
  <div class="feature-card">
    <div class="feature-icon">🎤</div>
    <h3>语音输入接管</h3>
    <p>直接捕获小爱音箱的麦克风输入，绕过原有语音识别限制</p>
  </div>
  
  <div class="feature-card">
    <div class="feature-icon">🔊</div>
    <h3>声音输出控制</h3>
    <p>完全接管小爱音箱的扬声器，可以播放自定义音频和TTS内容</p>
  </div>
  
  <div class="feature-card">
    <div class="feature-icon">🧠</div>
    <h3>AI模型整合</h3>
    <p>支持接入小智AI、ChatGPT等多种大模型，实现自然对话体验</p>
  </div>
  
  <div class="feature-card">
    <div class="feature-icon">🌐</div>
    <h3>跨平台支持</h3>
    <p>Client端使用Rust开发，Server端支持Python和Node.js实现</p>
  </div>
  
  <div class="feature-card">
    <div class="feature-icon">🛠️</div>
    <h3>可扩展架构</h3>
    <p>模块化设计，方便开发者添加自定义功能和集成其他服务</p>
  </div>
  
  <div class="feature-card">
    <div class="feature-icon">🎮</div>
    <h3>开发者友好</h3>
    <p>详细的文档和教程，帮助开发者快速上手并定制自己的功能</p>
  </div>
</div>

## 演示视频

<div class="demo-videos">
  <div class="video-item">
    <a href="https://www.bilibili.com/video/BV1NBXWYSEvX" target="_blank" class="video-link">
      <div class="video-thumbnail">
        <img src="https://raw.githubusercontent.com/idootop/open-xiaoai/main/docs/images/xiaozhi.jpg" alt="小爱音箱接入小智AI">
      </div>
      <div class="video-title">
        <span class="video-icon">▶️</span>
        <span>小爱音箱接入小智AI演示</span>
      </div>
    </a>
  </div>
  
  <div class="video-item">
    <a href="https://www.bilibili.com/video/BV1N1421y7qn" target="_blank" class="video-link">
      <div class="video-thumbnail">
        <img src="https://github.com/idootop/open-xiaoai/raw/main/docs/images/migpt.jpg" alt="小爱音箱接入MiGPT">
      </div>
      <div class="video-title">
        <span class="video-icon">▶️</span>
        <span>小爱音箱接入MiGPT演示</span>
      </div>
    </a>
  </div>
</div>

## 快速开始

<div class="important-notice">
  <div class="notice-icon">⚠️</div>
  <div class="notice-content">
    <strong>重要提示</strong>
    <p>本教程仅适用于 <strong>小爱音箱 Pro（LX06）</strong> 和 <strong>Xiaomi 智能音箱 Pro（OH2P）</strong> 这两款机型，<strong>其他型号</strong>的小爱音箱请勿直接使用！</p>
  </div>
</div>

Open-XiaoAI项目由Client端和Server端两部分组成，您可以按照以下步骤快速开始：

### 安装步骤

<div class="steps">
  <div class="step">
    <div class="step-number">1</div>
    <div class="step-content">
      <h4>小爱音箱固件更新</h4>
      <p>刷机更新小爱音箱补丁固件，开启并SSH连接到小爱音箱</p>
      <a href="https://github.com/idootop/open-xiaoai/blob/main/docs/flash.md" target="_blank" class="step-link">查看详细教程</a>
    </div>
  </div>
  
  <div class="step">
    <div class="step-number">2</div>
    <div class="step-content">
      <h4>客户端部署</h4>
      <p>在电脑上编译Client端补丁程序，然后复制到小爱音箱上运行</p>
      <a href="https://github.com/idootop/open-xiaoai/blob/main/packages/client-rust/README.md" target="_blank" class="step-link">查看详细教程</a>
    </div>
  </div>
  
  <div class="step">
    <div class="step-number">3</div>
    <div class="step-content">
      <h4>服务端部署</h4>
      <p>在电脑上运行Server端演示程序，体验小爱音箱的全新能力</p>
      <ul class="step-options">
        <li><a href="https://github.com/idootop/open-xiaoai/blob/main/packages/server-python/README.md" target="_blank">Python Server - 小爱音箱接入小智AI</a></li>
        <li><a href="https://github.com/idootop/open-xiaoai/blob/main/packages/server-node/README.md" target="_blank">Node.js Server - 小爱音箱接入MiGPT-Next</a></li>
      </ul>
    </div>
  </div>
</div>

## 工作原理

Open-XiaoAI通过以下方式工作：

1. **固件补丁**: 修改小爱音箱的固件，允许SSH访问和底层系统控制
2. **音频流劫持**: 客户端程序直接捕获麦克风输入和控制扬声器输出
3. **网络通信**: 客户端与服务端之间建立WebSocket连接进行实时通信
4. **AI处理**: 服务端接收语音输入，交由AI模型处理后返回响应
5. **自定义功能**: 开发者可以在服务端实现各种自定义功能和集成

## 相关项目

如果您不想刷机，或者不是小爱音箱Pro，以下项目可能对您有用：

- [MiGPT](https://github.com/idootop/mi-gpt) - 将ChatGPT接入小爱音箱的原始项目
- [MiGPT-Next](https://github.com/idootop/migpt-next) - MiGPT的下一代版本
- [XiaoGPT](https://github.com/yihong0618/xiaogpt) - 另一个小爱音箱ChatGPT接入方案
- [XiaoMusic](https://github.com/hanxi/xiaomusic) - 小爱音箱音乐播放增强

## 技术参考

如果您想了解更多技术细节，以下链接可能对您有帮助：

- [xiaoai-patch](https://github.com/duhow/xiaoai-patch) - 小爱音箱固件补丁
- [open-lx01](https://github.com/jialeicui/open-lx01) - 小爱音箱LX01开源项目
- [小爱FM研究](https://javabin.cn/2021/xiaoai_fm.html) - 小爱音箱FM功能研究
- [小米设备安全研究](https://github.com/yihong0618/gitblog/issues/258) - 小米IoT设备安全分析
- [小爱音箱探索](https://xuanxuanblingbling.github.io/iot/2022/09/16/mi/) - 小爱音箱技术探索

## 免责声明

<div class="disclaimer">
  <h4>适用范围</h4>
  <p>本项目为非盈利开源项目，仅限于技术原理研究、安全漏洞验证及非营利性个人使用。严禁用于商业服务、网络攻击、数据窃取、系统破坏等违反《网络安全法》及使用者所在地司法管辖区的法律规定的场景。</p>
  
  <h4>非官方声明</h4>
  <p>本项目由第三方开发者独立开发，与小米集团及其关联方（下称"权利方"）无任何隶属/合作关系，未获其官方授权/认可或技术支持。项目中涉及的商标、固件、云服务的所有权利归属小米集团。若权利方主张权益，使用者应立即主动停止使用并删除本项目。</p>
  
  <p>继续使用本项目，即表示您已完整阅读并同意<a href="https://github.com/idootop/open-xiaoai/blob/main/agreement.md" target="_blank">用户协议</a>，否则请立即终止使用并彻底删除本项目。</p>
</div>

## 许可证

本项目使用 [MIT](https://github.com/idootop/open-xiaoai/blob/main/LICENSE) 许可证 © 2024-PRESENT Del Wang

<style>
.project-header {
  display: flex;
  align-items: center;
  margin-bottom: 2rem;
}

.project-logo {
  width: 100px;
  height: 100px;
  margin-right: 1.5rem;
}

.project-logo img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

.project-badges {
  display: flex;
  flex-wrap: wrap;
  gap: 0.5rem;
}

.badge {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 1rem;
  font-size: 0.85rem;
  font-weight: 500;
}

.badge.platform {
  background-color: var(--vp-c-brand-soft);
  color: var(--vp-c-brand-dark);
}

.badge.language {
  background-color: rgba(59, 130, 246, 0.2);
  color: rgb(59, 130, 246);
}

.badge.status {
  background-color: rgba(139, 92, 246, 0.2);
  color: rgb(139, 92, 246);
}

.project-banner {
  width: 100%;
  margin: 2rem 0;
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--vp-c-divider);
}

.project-banner img {
  width: 100%;
  height: auto;
  display: block;
}

.features-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 1.5rem;
  margin: 2rem 0;
}

.feature-card {
  background-color: var(--vp-c-bg-soft);
  border-radius: 8px;
  padding: 1.5rem;
  transition: transform 0.3s ease, box-shadow 0.3s ease;
  border: 1px solid var(--vp-c-divider);
  height: 100%;
}

.feature-card:hover {
  transform: translateY(-5px);
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
}

.feature-icon {
  font-size: 2rem;
  margin-bottom: 1rem;
}

.feature-card h3 {
  color: var(--vp-c-brand);
  margin-top: 0;
  margin-bottom: 0.5rem;
}

.demo-videos {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 1.5rem;
  margin: 2rem 0;
}

.video-item {
  background-color: var(--vp-c-bg-soft);
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--vp-c-divider);
  transition: transform 0.3s ease, box-shadow 0.3s ease;
}

.video-item:hover {
  transform: translateY(-5px);
  box-shadow: 0 5px 15px rgba(0, 0, 0, 0.1);
}

.video-link {
  text-decoration: none;
  color: inherit;
  display: block;
}

.video-thumbnail {
  width: 100%;
  height: 180px;
  overflow: hidden;
}

.video-thumbnail img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.3s ease;
}

.video-item:hover .video-thumbnail img {
  transform: scale(1.05);
}

.video-title {
  padding: 1rem;
  display: flex;
  align-items: center;
  gap: 0.5rem;
}

.video-icon {
  color: var(--vp-c-brand);
}

.important-notice {
  background-color: rgba(234, 179, 8, 0.1);
  border-left: 4px solid rgba(234, 179, 8, 0.8);
  border-radius: 0 8px 8px 0;
  padding: 1rem 1.5rem;
  margin: 2rem 0;
  display: flex;
  gap: 1rem;
}

.notice-icon {
  font-size: 1.5rem;
}

.notice-content strong {
  display: block;
  margin-bottom: 0.5rem;
}

.steps {
  margin: 2rem 0;
}

.step {
  display: flex;
  margin-bottom: 1.5rem;
  gap: 1rem;
}

.step-number {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 32px;
  height: 32px;
  background-color: var(--vp-c-brand);
  color: white;
  border-radius: 50%;
  font-weight: bold;
  flex-shrink: 0;
}

.step-content {
  flex: 1;
}

.step-content h4 {
  margin-top: 0;
  margin-bottom: 0.5rem;
  color: var(--vp-c-brand);
}

.step-link {
  display: inline-block;
  margin-top: 0.5rem;
  color: var(--vp-c-brand);
  text-decoration: none;
  font-weight: 500;
}

.step-link:hover {
  text-decoration: underline;
}

.step-options {
  list-style-type: disc;
  padding-left: 1.5rem;
  margin-top: 0.5rem;
}

.architecture-diagram {
  text-align: center;
  margin: 2rem 0;
}

.architecture-diagram img {
  max-width: 100%;
  border-radius: 8px;
  border: 1px solid var(--vp-c-divider);
}

.disclaimer {
  background-color: rgba(239, 68, 68, 0.1);
  border-left: 4px solid rgba(239, 68, 68, 0.8);
  border-radius: 0 8px 8px 0;
  padding: 1.5rem;
  margin: 2rem 0;
}

.disclaimer h4 {
  margin-top: 0;
  color: rgba(239, 68, 68, 0.8);
  margin-bottom: 0.5rem;
}

.disclaimer p {
  margin: 0.5rem 0;
}

@media (max-width: 768px) {
  .project-header {
    flex-direction: column;
    align-items: flex-start;
  }
  
  .project-logo {
    margin-bottom: 1rem;
  }
  
  .demo-videos {
    grid-template-columns: 1fr;
  }
}
</style> 