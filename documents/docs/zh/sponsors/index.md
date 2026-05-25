---
title: 赞助支持
description: 感谢所有赞助者的支持
sidebar: false
outline: deep
---

<script setup>
import SponsorsList from './SponsorsList.vue'
</script>

<div class="sponsors-page">

# 赞助支持

<div class="header-content">
  <h2>感谢所有赞助者的支持 ❤️</h2>
</div>

<div class="sponsors-section">


<SponsorsList />

## 成为赞助者

请通过以下方式进行赞助：
您的赞助将用于：
- 支持设备兼容性测试
- 新功能开发和维护


<div class="payment-container">
  <div class="payment-method">
    <h4>微信支付</h4>
    <div class="qr-code">
      <img src="https://tuchuang.junsen.online/i/2025/03/28/43rpw7.jpg" alt="微信收款码">
    </div>
  </div>
  <div class="payment-method">
    <h4>支付宝支付</h4>
    <div class="qr-code">
      <img src="https://tuchuang.junsen.online/i/2025/03/28/43u3eo.jpg" alt="支付宝收款码">
    </div>
  </div>
</div>

### 设备兼容性支持

您可以通过以下方式支持设备兼容性：
- 在赞助备注中说明您的设备型号，我会优先支持这些设备
- 直接赞助/捐赠硬件设备，帮助我进行开发和适配测试
- 提供设备的详细参数和使用场景，便于我更好地进行开发

::: tip 联系方式
硬件赞助请通过GitHub主页的邮箱联系我，以便协商寄送方式和地址
:::

</div>

</div>

<style>
.sponsors-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
}

.sponsors-page h1 {
  text-align: center;
  margin-bottom: 1rem;
}

.header-content {
  text-align: center;
}

.header-content h2 {
  color: var(--vp-c-brand);
  margin-bottom: 1rem;
}

.sponsors-section h2, .sponsors-section h3 {
  margin-top: 3rem;
  padding-top: 1rem;
  border-top: 1px solid var(--vp-c-divider);
}

.payment-container {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 2.5rem;
  margin: 2rem 0;
}

.payment-method {
  text-align: center;
  border: 1px solid var(--vp-c-divider);
  border-radius: 8px;
  padding: 1.5rem;
  transition: all 0.3s ease;
}

.payment-method:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.08);
  transform: translateY(-5px);
}

.payment-method h4 {
  margin-top: 0;
  margin-bottom: 1rem;
}

.qr-code {
  width: 200px;
  height: 200px;
  margin: 0 auto;
  overflow: hidden;
}

.qr-code img {
  width: 100%;
  height: 100%;
  object-fit: contain;
}

@media (max-width: 768px) {
  .payment-container {
    grid-template-columns: 1fr;
  }
  
  .qr-code {
    width: 180px;
    height: 180px;
  }
}
</style> 