# Hướng dẫn tích hợp MCP bên ngoài cho XiaoZhi

Tài liệu này hướng dẫn cách kết nối các dịch vụ MCP bên ngoài vào hệ thống XiaoZhi nhằm mở rộng tính năng và tích hợp công cụ từ bên thứ ba.

## Tổng quan

Bên cạnh các công cụ MCP tích hợp sẵn, hệ thống XiaoZhi còn hỗ trợ kết nối tới các máy chủ MCP bên ngoài để thực hiện:
- Tích hợp công cụ bên thứ ba
- Gọi dịch vụ từ xa
- Triển khai công cụ phân tán
- Chia sẻ công cụ trong cộng đồng

## Mô tả kiến trúc

### Kiến trúc MCP kết nối ngoài
```
Nền tảng XiaoZhi AI   xiaozhi-mcphub        Máy chủ MCP ngoài     Công cụ bên thứ ba
┌─────────────────┐   ┌─────────────────┐   ┌─────────────────┐   ┌────────────────┐
│                 │   │                 │   │                 │   │                │
│   MCP Client    │◄──┤ MCP Server/Proxy│◄──┤   MCP Server    │◄──┤ Công cụ thực tế│
│                 │   │                 │   │                 │   │                │
└─────────────────┘   └─────────────────┘   └─────────────────┘   └────────────────┘
```

### Các phương thức kết nối
1. **Nhập/xuất chuẩn (stdio)**: Khởi chạy tiến trình con và giao tiếp liên tiến trình qua đường ống stdin/stdout, phù hợp với các công cụ CLI cục bộ như Playwright, Amap (Gaode Maps), v.v.
2. **Sự kiện đẩy từ máy chủ (SSE)**: Giao tiếp luồng sự kiện dựa trên kết nối HTTP dài hạn, cung cấp khả năng trao đổi hai chiều thời gian thực tương tự WebSocket
3. **HTTP truyền phát (streamable-http)**: Đóng gói giao thức HTTP trên nền TCP, hỗ trợ truyền dữ liệu dạng luồng (streaming), phù hợp cho các dịch vụ API từ xa và microservice
4. **OpenAPI**: Phương thức kết nối theo đặc tả REST API tiêu chuẩn, tự động phân tích đặc tả OpenAPI và sinh giao diện công cụ, phù hợp với các dịch vụ API bên thứ ba chuẩn hóa

## Các dự án mã nguồn mở liên quan
Các dự án máy khách XiaoZhi do cộng đồng phát triển, cung cấp nhiều cách tích hợp trên các nền tảng khác nhau:

### xiaozhi-mcphub (Đi kèm dự án này)

**XiaoZhi MCP Hub** là hệ thống cầu nối công cụ MCP thông minh được tối ưu riêng cho nền tảng XiaoZhi AI, phát triển dựa trên dự án MCPHub xuất sắc và bổ sung khả năng tích hợp nền tảng XiaoZhi cùng đồng bộ công cụ thông minh.

- **Trang dự án**: [xiaozhi-mcphub](https://huangjunsen0406.github.io/xiaozhi-mcphub/)
- **GitHub**: [xiaozhi-mcphub](https://github.com/huangjunsen0406/xiaozhi-mcphub)
- **Tính năng cốt lõi**:
  - **Tích hợp nền tảng XiaoZhi AI**: Tự động đồng bộ công cụ qua WebSocket, cập nhật trạng thái thời gian thực, cầu nối giao thức
  - **Quản lý MCP nâng cao**: Hỗ trợ giao thức stdio, SSE, HTTP, cấu hình cắm nóng (hot-plug), bảng điều khiển tập trung
  - **Định tuyến công cụ thông minh**: Tìm kiếm công cụ thông minh dựa trên vector và quản lý theo nhóm
  - **Cơ chế xác thực bảo mật**: Quản lý người dùng bằng JWT + bcrypt, kiểm soát quyền theo vai trò (RBAC)
  - **Kho MCP tích hợp sẵn**: Cài đặt trực tuyến nhiều công cụ MCP mà không cần khởi động lại, hỗ trợ cập nhật nóng

### xiaozhi-client
- **Địa chỉ dự án**: [xiaozhi-client](https://github.com/shenjingnan/xiaozhi-client)
- **Chức năng**: Máy khách XiaoZhi AI chuyên dùng để kết nối và tổng hợp MCP
- **Đặc điểm nổi bật**:
  - **Hỗ trợ nhiều điểm truy cập**: Cấu hình nhiều điểm truy cập XiaoZhi, cho phép nhiều thiết bị dùng chung một cấu hình MCP
  - **Tổng hợp MCP Server**: Tổng hợp nhiều MCP Server theo chuẩn chung để quản lý tập trung
  - **Kiểm soát công cụ động**: Kiểm soát mức độ hiển thị công cụ của MCP Server, tránh lỗi khi số lượng công cụ quá nhiều
  - **Nhiều cách tích hợp**: Hỗ trợ tích hợp như một MCP Server thông thường vào các máy khách như Cursor/Cherry Studio
  - **Cấu hình trực quan trên Web**: Giao diện Web UI hiện đại, hỗ trợ cấu hình và quản lý từ xa
  - **Tích hợp ModelScope**: Hỗ trợ các dịch vụ MCP từ xa được lưu trữ trên ModelScope

### HyperChat
- **Địa chỉ dự án**: [HyperChat](https://github.com/BigSweetPotatoStudio/HyperChat)
- **Chức năng**: Không gian làm việc AI thế hệ mới, nền tảng cộng tác thông minh đa nền tảng tiên phong ý tưởng "AI as Code"
- **Đặc điểm nổi bật**:
  - **AI as Code**: Quản lý năng lực AI theo cấu hình, hỗ trợ quản lý phiên bản và cộng tác nhóm
  - **Lấy không gian làm việc làm trung tâm**: Cách ly và quản lý môi trường AI theo từng dự án
  - **Tích hợp sâu hệ sinh thái MCP**: Hỗ trợ đầy đủ giao thức MCP, bộ công cụ tích hợp phong phú và tải động
  - **Thống nhất đa nền tảng**: Ứng dụng Web, ứng dụng desktop Electron, dòng lệnh CLI, tiện ích mở rộng VSCode
- **Điểm nhấn kỹ thuật**:
  - Hệ thống tác tử AI cấu hình hóa, hỗ trợ tùy biến Agent chuyên sâu
  - So sánh song song nhiều mô hình (Claude, OpenAI, Gemini, v.v.)
  - Hiển thị nội dung thông minh (Artifacts, Mermaid, công thức toán học)
  - Tác vụ định kỳ và tự động hóa quy trình làm việc (workflow)
