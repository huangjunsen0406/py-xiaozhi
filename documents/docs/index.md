---
# https://vitepress.dev/reference/default-theme-home-page
layout: home

hero:
  name: "PY-XIAOZHI"
  tagline: Lightweight, cross-platform multimodal AI interaction framework. Supports real-time voice, vision recognition, and IoT device control, deployable on desktop and ARM embedded platforms.
  actions:
    - theme: brand
      text: Get Started
      link: /guide/文档目录
    - theme: alt
      text: View Source
      link: https://github.com/huangjunsen0406/py-xiaozhi
    - theme: alt
      text: Dev Guide
      link: /guide/开发指南

features:
  - title: AI Voice Interaction
    details: Supports voice input and recognition for intelligent human-computer interaction with natural conversation flow. Built with async architecture for real-time audio processing and low-latency responses.
  - title: Vision Multimodal
    details: Supports image recognition and processing for multimodal interaction, understanding image content. Integrates OpenCV camera processing for real-time visual analysis.
  - title: MCP Tool Server
    details: Modular tool system based on JSON-RPC 2.0 protocol, with built-in music playback, Bazi fortune-telling, and more. Dynamically extensible tool plugins.
  - title: IoT Device Integration
    details: Designed with Thing abstraction pattern, supports smart home device control including lights, volume, temperature sensors. Integrates Home Assistant platform for easy expansion.
  - title: High-Performance Audio
    details: Real-time audio transmission based on Opus codec, intelligent resampling, 5ms audio frame interval processing for low-latency, high-quality audio experience.
  - title: Cross-Platform
    details: Compatible with Windows 10+, macOS 10.15+, and Linux. Supports GUI and CLI dual modes, adapts to platform-specific audio devices and system interfaces.
---

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
