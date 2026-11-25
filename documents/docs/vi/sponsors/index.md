---
title: Tài trợ & Ủng hộ
description: Cảm ơn tất cả các nhà tài trợ đã ủng hộ dự án
sidebar: false
outline: deep
---

<script setup>
import SponsorsList from './SponsorsList.vue'
</script>

<div class="sponsors-page">

# Tài trợ & Ủng hộ

<div class="header-content">
  <h2>Cảm ơn tất cả các nhà tài trợ đã ủng hộ ❤️</h2>
</div>

<div class="sponsors-section">


<SponsorsList />

## Trở thành nhà tài trợ

Vui lòng tài trợ thông qua các phương thức sau:
Khoản tài trợ của bạn sẽ được sử dụng cho:
- Hỗ trợ kiểm thử tương thích thiết bị
- Phát triển tính năng mới và bảo trì dự án


<div class="payment-container">
  <div class="payment-method">
    <h4>WeChat Pay</h4>
    <div class="qr-code">
      <img src="https://tuchuang.junsen.online/i/2025/03/28/43rpw7.jpg" alt="Mã QR thanh toán WeChat Pay">
    </div>
  </div>
  <div class="payment-method">
    <h4>Alipay</h4>
    <div class="qr-code">
      <img src="https://tuchuang.junsen.online/i/2025/03/28/43u3eo.jpg" alt="Mã QR thanh toán Alipay">
    </div>
  </div>
</div>

### Hỗ trợ tương thích thiết bị

Bạn có thể hỗ trợ kiểm thử tương thích thiết bị theo các cách sau:
- Ghi rõ mẫu thiết bị của bạn trong phần ghi chú khi tài trợ, tôi sẽ ưu tiên hỗ trợ các thiết bị này
- Trực tiếp tài trợ/quyên góp thiết bị phần cứng để hỗ trợ việc phát triển và kiểm thử tương thích
- Cung cấp thông số chi tiết và kịch bản sử dụng của thiết bị để việc phát triển đạt hiệu quả tốt hơn

::: tip Thông tin liên hệ
Đối với tài trợ phần cứng, vui lòng liên hệ với tôi qua email trên trang GitHub cá nhân để trao đổi về phương thức và địa chỉ gửi hàng.
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
