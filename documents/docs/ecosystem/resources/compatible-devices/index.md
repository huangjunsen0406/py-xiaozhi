---
title: 兼容设备
description: 与py-xiaozhi项目兼容的硬件设备和开发板列表
---

# 兼容设备

<div class="project-header">
  <div class="project-logo">
    <!-- <img src="/py-xiaozhi/images/hardware.png" alt="兼容设备" onerror="this.src='/py-xiaozhi/images/logo.png'; this.onerror=null;"> -->
  </div>
  <div class="project-badges">
    <span class="badge category">硬件</span>
    <span class="badge status">持续更新</span>
  </div>
</div>

## 设备兼容性

py-xiaozhi支持多种硬件设备和平台，从低成本的开发板到高性能的边缘计算设备。本页面列出了经过测试和验证的兼容设备，为您的项目选择合适的硬件提供参考。

## 开发板

<div class="devices-container">
  <div class="device-card">
    <!-- <img src="/py-xiaozhi/images/devices/raspberry-pi.jpg" alt="树莓派" onerror="this.src='/py-xiaozhi/images/logo.png'; this.onerror=null;"> -->
    <div class="device-info">
      <h3>树莓派 4B/5</h3>
      <div class="compatibility high">兼容性: 优秀</div>
      <p>树莓派是运行py-xiaozhi最理想的平台之一，提供良好的性能和丰富的接口。</p>
      <div class="specs">
        <div class="spec"><span>处理器:</span> Broadcom BCM2711/BCM2712</div>
        <div class="spec"><span>RAM:</span> 2GB/4GB/8GB</div>
        <div class="spec"><span>接口:</span> USB, GPIO, I2S, I2C</div>
      </div>
      <div class="notes">
        <strong>注意:</strong> 推荐使用4GB或以上内存版本，搭配USB麦克风阵列效果最佳。
      </div>
    </div>
  </div>

  <div class="device-card">
    <!-- <img src="/py-xiaozhi/images/devices/jetson-nano.jpg" alt="Jetson Nano" onerror="this.src='/py-xiaozhi/images/logo.png'; this.onerror=null;"> -->
    <div class="device-info">
      <h3>NVIDIA Jetson Nano</h3>
      <div class="compatibility high">兼容性: 优秀</div>
      <p>GPU加速使Jetson Nano成为需要更强大语音和图像处理能力的场景的理想选择。</p>
      <div class="specs">
        <div class="spec"><span>处理器:</span> Quad-core ARM A57</div>
        <div class="spec"><span>GPU:</span> 128-core NVIDIA Maxwell</div>
        <div class="spec"><span>RAM:</span> 4GB</div>
      </div>
      <div class="notes">
        <strong>注意:</strong> 完全支持本地唤醒词训练和离线语音识别。
      </div>
    </div>
  </div>

  <div class="device-card">
    <!-- <img src="/py-xiaozhi/images/devices/esp32.jpg" alt="ESP32" onerror="this.src='/py-xiaozhi/images/logo.png'; this.onerror=null;"> -->
    <div class="device-info">
      <h3>ESP32/ESP32-S3</h3>
      <div class="compatibility medium">兼容性: 良好</div>
      <p>ESP32系列是构建低功耗xiaozhi节点的理想选择，通过xiaozhi-esp32-server项目支持。</p>
      <div class="specs">
        <div class="spec"><span>处理器:</span> Tensilica Xtensa LX6/LX7</div>
        <div class="spec"><span>RAM:</span> 520KB-8MB</div>
        <div class="spec"><span>连接:</span> WiFi, Bluetooth</div>
      </div>
      <div class="notes">
        <strong>注意:</strong> 只支持基本功能，需要连接到主py-xiaozhi服务器。推荐使用ESP32-S3以获得更好的性能。
      </div>
    </div>
  </div>

  <div class="device-card">
    <!-- <img src="/py-xiaozhi/images/devices/rockpi.jpg" alt="Rock Pi" onerror="this.src='/py-xiaozhi/images/logo.png'; this.onerror=null;"> -->
    <div class="device-info">
      <h3>Rock Pi 4</h3>
      <div class="compatibility high">兼容性: 优秀</div>
      <p>Rock Pi 4提供了与树莓派相似的性能，但具有更强大的多媒体处理能力和更多接口。</p>
      <div class="specs">
        <div class="spec"><span>处理器:</span> Rockchip RK3399</div>
        <div class="spec"><span>RAM:</span> 1GB/2GB/4GB</div>
        <div class="spec"><span>存储:</span> eMMC模块/MicroSD</div>
      </div>
      <div class="notes">
        <strong>注意:</strong> 适合需要高性能多媒体处理的应用场景。
      </div>
    </div>
  </div>

  <div class="device-card">
    <!-- <img src="/py-xiaozhi/images/devices/orange-pi.jpg" alt="Orange Pi" onerror="this.src='/py-xiaozhi/images/logo.png'; this.onerror=null;"> -->
    <div class="device-info">
      <h3>Orange Pi 4/5</h3>
      <div class="compatibility medium">兼容性: 良好</div>
      <p>Orange Pi系列提供了经济实惠的选择，适合成本敏感的项目。</p>
      <div class="specs">
        <div class="spec"><span>处理器:</span> Rockchip RK3399/RK3588S</div>
        <div class="spec"><span>RAM:</span> 4GB/16GB</div>
        <div class="spec"><span>接口:</span> GPIO, I2S, HDMI</div>
      </div>
      <div class="notes">
        <strong>注意:</strong> 需要一些额外配置工作，但性价比高。
      </div>
    </div>
  </div>

  <div class="device-card">
    <!-- <img src="/py-xiaozhi/images/devices/arduino.jpg" alt="Arduino" onerror="this.src='/py-xiaozhi/images/logo.png'; this.onerror=null;"> -->
    <div class="device-info">
      <h3>Arduino系列</h3>
      <div class="compatibility low">兼容性: 有限</div>
      <p>Arduino可以作为外设控制器与py-xiaozhi系统集成，但不能运行完整的py-xiaozhi程序。</p>
      <div class="specs">
        <div class="spec"><span>处理器:</span> 取决于型号</div>
        <div class="spec"><span>RAM:</span> 2KB-8KB</div>
        <div class="spec"><span>接口:</span> GPIO, I2C, SPI</div>
      </div>
      <div class="notes">
        <strong>注意:</strong> 仅适合作为执行器或传感器节点，需与主控设备配合使用。
      </div>
    </div>
  </div>
</div>

## 外设设备

除了开发板外，以下外设设备经过测试，可与py-xiaozhi项目配合使用：

### 音频输入设备

<div class="peripherals">
  <div class="peripheral">
    <h4>ReSpeaker 4麦克风阵列</h4>
    <div class="rating excellent">推荐度: ★★★★★</div>
    <p>提供360°拾音和DOA（声源方向）检测，适合多人交互场景。</p>
  </div>
  
  <div class="peripheral">
    <h4>USB会议麦克风</h4>
    <div class="rating good">推荐度: ★★★★☆</div>
    <p>经济实惠的选择，在安静环境中效果良好，大多数品牌兼容性良好。</p>
  </div>
  
  <div class="peripheral">
    <h4>INMP441 I2S麦克风</h4>
    <div class="rating good">推荐度: ★★★★☆</div>
    <p>ESP32项目的理想选择，提供高质量数字音频输入。</p>
  </div>
  
  <div class="peripheral">
    <h4>普通USB麦克风</h4>
    <div class="rating fair">推荐度: ★★★☆☆</div>
    <p>可用于测试和开发，但拾音范围和质量有限。</p>
  </div>
</div>

### 音频输出设备

<div class="peripherals">
  <div class="peripheral">
    <h4>USB音箱</h4>
    <div class="rating excellent">推荐度: ★★★★★</div>
    <p>即插即用，大多数设备兼容性良好，推荐用于开发和测试。</p>
  </div>
  
  <div class="peripheral">
    <h4>MAX98357A I2S放大器 + 扬声器</h4>
    <div class="rating good">推荐度: ★★★★☆</div>
    <p>ESP32和树莓派项目的理想选择，提供高质量数字音频输出。</p>
  </div>
  
  <div class="peripheral">
    <h4>蓝牙音箱</h4>
    <div class="rating fair">推荐度: ★★★☆☆</div>
    <p>提供无线连接，但可能存在延迟问题，不推荐语音交互场景。</p>
  </div>
</div>

## 兼容性测试

如果您使用了本页面未列出的硬件设备，并成功运行了py-xiaozhi，欢迎提交您的兼容性报告。请包含以下信息：

1. 设备型号和规格
2. 安装的py-xiaozhi版本
3. 任何必要的配置或修改
4. 性能和稳定性评估
5. 使用场景和建议

## 硬件配置指南

我们为一些常用设备提供了详细的配置指南：

- [树莓派配置指南](/py-xiaozhi/guide/hardware/raspberry-pi-setup)
- [ESP32/ESP32-S3配置指南](/py-xiaozhi/guide/hardware/esp32-setup)
- [Jetson Nano配置指南](/py-xiaozhi/guide/hardware/jetson-nano-setup)
- [麦克风和扬声器配置](/py-xiaozhi/guide/hardware/audio-setup)

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

.badge.category {
  background-color: rgba(59, 130, 246, 0.2);
  color: rgb(59, 130, 246);
}

.badge.status {
  background-color: rgba(5, 150, 105, 0.2);
  color: rgb(5, 150, 105);
}

.devices-container {
  display: flex;
  flex-direction: column;
  gap: 2rem;
  margin: 2rem 0;
}

.device-card {
  display: flex;
  background-color: var(--vp-c-bg-soft);
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--vp-c-divider);
}

.device-card img {
  width: 200px;
  height: 200px;
  object-fit: cover;
}

.device-info {
  padding: 1.5rem;
  flex: 1;
}

.device-info h3 {
  margin-top: 0;
  margin-bottom: 0.5rem;
  color: var(--vp-c-brand);
}

.compatibility {
  display: inline-block;
  padding: 0.25rem 0.75rem;
  border-radius: 1rem;
  font-size: 0.85rem;
  font-weight: 500;
  margin-bottom: 1rem;
}

.compatibility.high {
  background-color: rgba(16, 185, 129, 0.2);
  color: rgb(16, 185, 129);
}

.compatibility.medium {
  background-color: rgba(245, 158, 11, 0.2);
  color: rgb(245, 158, 11);
}

.compatibility.low {
  background-color: rgba(239, 68, 68, 0.2);
  color: rgb(239, 68, 68);
}

.specs {
  margin: 1rem 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 0.5rem;
}

.spec {
  font-size: 0.9rem;
}

.spec span {
  font-weight: 500;
  margin-right: 0.25rem;
}

.notes {
  background-color: rgba(var(--vp-c-brand-rgb), 0.1);
  padding: 0.75rem;
  border-radius: 4px;
  font-size: 0.9rem;
  margin-top: 1rem;
}

.peripherals {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
  gap: 1.5rem;
  margin: 1.5rem 0;
}

.peripheral {
  background-color: var(--vp-c-bg-soft);
  border-radius: 8px;
  padding: 1.5rem;
  border: 1px solid var(--vp-c-divider);
}

.peripheral h4 {
  margin-top: 0;
  margin-bottom: 0.5rem;
  color: var(--vp-c-brand);
}

.rating {
  font-size: 0.9rem;
  margin-bottom: 1rem;
  font-weight: 500;
}

.rating.excellent {
  color: rgb(16, 185, 129);
}

.rating.good {
  color: rgb(59, 130, 246);
}

.rating.fair {
  color: rgb(245, 158, 11);
}

@media (max-width: 768px) {
  .device-card {
    flex-direction: column;
  }
  
  .device-card img {
    width: 100%;
    height: 200px;
  }
}
</style> 