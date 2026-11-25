---
# https://vitepress.dev/reference/default-theme-home-page
layout: home

hero:
  name: "PY-XIAOZHI"
  tagline: Framework điều khiển tương tác AI đa phương thức gọn nhẹ, đa nền tảng. Hỗ trợ giọng nói thời gian thực, nhận diện thị giác và điều khiển thiết bị IoT trên máy tính lẫn nền tảng nhúng ARM.
  actions:
    - theme: brand
      text: Bắt đầu ngay
      link: /vi/guide/文档目录
    - theme: alt
      text: Xem mã nguồn
      link: https://github.com/huangjunsen0406/py-xiaozhi
    - theme: alt
      text: Hướng dẫn phát triển
      link: /vi/guide/开发指南

features:
  - title: Tương tác giọng nói AI
    details: Hỗ trợ thu âm và nhận diện giọng nói tự nhiên, mượt mà. Thiết kế bất đồng bộ (asyncio) giúp xử lý âm thanh thời gian thực với độ trễ thấp.
  - title: Thị giác đa phương thức
    details: Hỗ trợ nhận diện và phân tích hình ảnh, mang lại khả năng tương tác đa phương thức. Tích hợp camera OpenCV và Pi CSI cho phân tích trực tiếp.
  - title: Công cụ MCP & hệ sinh thái plugin
    details: Hệ thống công cụ mô-đun dựa trên JSON-RPC 2.0 với các công cụ âm lượng, ứng dụng, camera, chụp màn hình và thời tiết tích hợp sẵn; hỗ trợ cài plugin ZIP/thư mục ngoài ngay trong Cài đặt với tiến trình con cách ly.
  - title: Nền tảng phát đa phương tiện độc lập
    details: Tách bạch hoàn toàn lớp âm thanh (AudioMixer + AudioDecoder) với MediaPlayer không phụ thuộc nguồn nhạc, tự động quản lý Audio Focus khi phát TTS; plugin âm thanh chỉ cần trả URL trực tiếp hoặc tệp cục bộ.
  - title: Âm thanh độ trễ thấp & AEC tích hợp
    details: Chuỗi âm thanh thời gian thực dùng codec Opus và tái lấy mẫu SoXR, tích hợp sẵn khử tiếng vọng WebRTC APM trên cả 3 hệ điều hành, hỗ trợ hội thoại song công và ngắt lời tức thì.
  - title: Đa nền tảng, đa giao diện & đa ngôn ngữ
    details: Hỗ trợ Windows 10+, macOS 10.15+ và Linux (kể cả Raspberry Pi) với 3 chế độ GUI (PySide6/QML), TUI (Textual), GPIO và chuyển đổi nóng tiếng Trung / Anh / Việt không cần khởi động lại.
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
