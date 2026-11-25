# Tích hợp Home Assistant MCP

Nhằm nâng cao tính linh hoạt và ổn định về kiến trúc, py-xiaozhi đã loại bỏ tích hợp Home Assistant (HA) gắn sẵn. Hiện tại, bạn có thể kết nối HA thông qua plugin mở rộng Home Assistant MCP dựa trên WSS, kết nối trực tiếp tới máy chủ XiaoZhi AI bằng giao thức MCP mà không cần bất kỳ máy chủ trung gian nào. Plugin này được c1pher-cn duy trì mã nguồn mở, hỗ trợ đầy đủ truy vấn trạng thái thiết bị, điều khiển thực thể (entity) và quản lý tự động hóa.

Địa chỉ dự án: [ha-mcp-for-xiaozhi](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi)

## Tính năng của plugin

### Năng lực cốt lõi

1. **Kết nối trực tiếp máy chủ XiaoZhi**: Home Assistant đóng vai trò MCP server, kết nối trực tiếp tới máy chủ XiaoZhi qua giao thức WebSocket mà không cần trung chuyển
2. **Ủy quyền nhiều nhóm API**: Chọn đồng thời nhiều nhóm API trên cùng một thực thể (API điều khiển tích hợp của Home Assistant, MCP Server do người dùng tự định nghĩa)
3. **Hỗ trợ nhiều thực thể**: Hỗ trợ cấu hình đồng thời nhiều phiên bản thực thể
4. **Tích hợp HACS**: Cài đặt một chạm qua kho HACS, dễ dàng quản lý và cập nhật

### Ưu điểm kỹ thuật

- **Độ trễ thấp**: Kiến trúc kết nối trực tiếp giúp giảm độ trễ truyền qua trung gian
- **Độ tin cậy cao**: Dựa trên kết nối WebSocket duy trì dài hạn, ổn định hơn
- **Dễ mở rộng**: Hỗ trợ proxy cho các MCP Server khác, khả năng mở rộng mạnh mẽ
- **Dễ bảo trì**: Quản lý qua HACS và tự động cập nhật

## Các tình huống sử dụng phổ biến

**Truy vấn trạng thái thiết bị:**

- "Đèn phòng khách hiện đang ở trạng thái nào"
- "Xem trạng thái tất cả các đèn"
- "Cảm biến nhiệt độ đang báo bao nhiêu độ"
- "Điều hòa hiện có đang bật không"

**Điều khiển thiết bị:**

- "Bật đèn phòng khách"
- "Tắt tất cả đèn"
- "Đặt nhiệt độ điều hòa lên 25 độ"
- "Chỉnh độ sáng đèn phòng khách lên 80%"

**Điều khiển ngữ cảnh (Scene):**

- "Bật chế độ ngủ"
- "Kích hoạt ngữ cảnh về nhà"
- "Chạy ngữ cảnh chúc ngủ ngon"
- "Bật chế độ tiệc tùng"

**Điều khiển nâng cao:**

- "Điều khiển TV thông qua script"
- "Chạy tự động hóa tùy chỉnh"
- "Điều khiển thiết bị đa phương tiện"
- "Quản lý hệ thống an ninh"

## Hướng dẫn cài đặt

### Yêu cầu trước khi cài đặt

- Home Assistant đã được cài đặt và đang chạy
- Đã cài đặt HACS (Home Assistant Community Store)
- Có tài khoản XiaoZhi AI và địa chỉ điểm truy cập MCP (MCP endpoint)

### Các bước cài đặt

#### 1. Cài đặt qua HACS

1. Mở HACS, tìm kiếm `xiaozhi` hoặc `ha-mcp-for-xiaozhi`

<img width="700" alt="Giao diện tìm kiếm HACS" src="https://github.com/user-attachments/assets/fa49ee7c-b503-49fa-ad63-512499fa3885" />

2. Nhấp tải xuống và cài đặt plugin

<img width="500" alt="Giao diện tải xuống plugin" src="https://github.com/user-attachments/assets/1ee75d6f-e1b0-4073-a2c7-ee0d72d002ca" />

3. Khởi động lại Home Assistant

#### 2. Cài đặt thủ công

Nếu không thể cài đặt qua HACS, bạn có thể tải thủ công:

1. Tải phiên bản mới nhất từ [GitHub Releases](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi/releases)
2. Giải nén vào thư mục `custom_components`
3. Khởi động lại Home Assistant

### Các bước cấu hình

#### 1. Thêm tích hợp

1. Vào **Cài đặt > Thiết bị & Dịch vụ > Thêm tích hợp** (**Settings > Devices & Services > Add Integration**)
2. Tìm kiếm "Mcp" hoặc "MCP Server for Xiaozhi"

<img width="600" alt="Giao diện thêm tích hợp" src="https://github.com/user-attachments/assets/07a70fe1-8c6e-4679-84df-1ea05114b271" />

3. Chọn và nhấp thêm

#### 2. Cấu hình tham số

Giao diện cấu hình yêu cầu điền các thông tin sau:

**Cấu hình cơ bản:**

- **Địa chỉ điểm truy cập XiaoZhi MCP**: Địa chỉ MCP lấy từ trang quản trị XiaoZhi AI
- **Tên thiết bị**: Đặt tên nhận diện cho phiên bản Home Assistant này

**Chọn nhóm API:**

- **Assist**: Tính năng điều khiển tích hợp sẵn của Home Assistant
- **MCP Server khác**: Nếu bạn đã cấu hình các máy chủ MCP khác trong Home Assistant, có thể chọn để ủy quyền chung cho XiaoZhi

<img width="600" alt="Giao diện cấu hình" src="https://github.com/user-attachments/assets/38e98fde-8a6c-4434-932c-840c25dc6e28" />

#### 3. Cấu hình công khai thực thể (Expose)

Để XiaoZhi có thể điều khiển thiết bị, cần công khai các thực thể tương ứng:

1. Vào **Cài đặt > Trợ lý giọng nói > Công khai** (**Settings > Voice assistants > Expose**)
2. Chọn các thiết bị và thực thể cần cho phép XiaoZhi điều khiển
3. Lưu cài đặt

#### 4. Xác minh kết nối

1. Sau khi hoàn tất cấu hình, chờ khoảng 1 phút
2. Đăng nhập vào trang quản trị XiaoZhi AI, mở trang điểm truy cập MCP
3. Nhấp làm mới và kiểm tra xem trạng thái kết nối đã bình thường chưa

<img width="600" alt="Kiểm tra trạng thái kết nối" src="https://github.com/user-attachments/assets/ace79a44-6197-4e94-8c49-ab9048ed4502" />

## Ví dụ sử dụng

### Điều khiển thiết bị cơ bản

```
Người dùng: "Bật đèn phòng khách"
XiaoZhi: "Vâng, tôi đã bật đèn phòng khách cho bạn"

Người dùng: "Chỉnh nhiệt độ điều hòa lên 26 độ"
XiaoZhi: "Đã đặt nhiệt độ điều hòa thành 26 độ"

Người dùng: "Tắt tất cả đèn"
XiaoZhi: "Tôi đã tắt toàn bộ đèn cho bạn"
```

### Truy vấn trạng thái

```
Người dùng: "Nhiệt độ phòng khách hiện tại là bao nhiêu"
XiaoZhi: "Cảm biến nhiệt độ phòng khách báo nhiệt độ hiện tại là 23.5 độ"

Người dùng: "Những đèn nào hiện đang bật"
XiaoZhi: "Các đèn đang bật hiện tại gồm: đèn phòng khách, đèn ngủ đầu giường"
```

### Điều khiển ngữ cảnh

```
Người dùng: "Chạy chế độ ngủ"
XiaoZhi: "Đã kích hoạt ngữ cảnh chế độ ngủ cho bạn, toàn bộ đèn đã tắt và rèm cửa đã kéo lại"

Người dùng: "Bật ngữ cảnh về nhà"
XiaoZhi: "Chào mừng về nhà! Đã bật đèn phòng khách và đèn sảnh, điều hòa đã được chỉnh về mức nhiệt thoải mái"
```

## Hướng dẫn gỡ lỗi

### 1. Kiểm tra thực thể đã công khai

Số lượng công cụ được hiển thị phụ thuộc vào loại thực thể bạn đã công khai cho trợ lý giọng nói Home Assistant:

- Vào **Cài đặt > Trợ lý giọng nói > Công khai** (**Settings > Voice assistants > Expose**)
- Đảm bảo các thiết bị cần điều khiển đã được thêm vào danh sách công khai

### 2. Yêu cầu phiên bản

Khuyến nghị sử dụng phiên bản Home Assistant mới nhất:

- Các phiên bản mới cung cấp bộ công cụ và API đầy đủ hơn
- Phiên bản tháng 5 có cải tiến rõ rệt về hỗ trợ công cụ so với phiên bản tháng 3

### 3. Phương pháp gỡ lỗi

Khi kết quả điều khiển không như mong đợi:

**Xem lịch sử trò chuyện XiaoZhi:**

1. Kiểm tra xem XiaoZhi hiểu và xử lý câu lệnh như thế nào
2. Xác nhận xem công cụ Home Assistant có được gọi không
3. Phân tích xem tham số truyền vào có chính xác không

**Vấn đề đã biết:**

- Điều khiển đèn có thể xung đột với điều khiển màn hình tích hợp sẵn

### 4. Nhật ký gỡ lỗi (Debug logs)

Nếu lời gọi function của Home Assistant chính xác nhưng thực thi bất thường:

1. Bật nhật ký gỡ lỗi (debug logging) cho plugin này trong Home Assistant
2. Tái hiện lại thao tác gây lỗi
3. Xem chi tiết quá trình thực thi trong nhật ký

## Video minh họa

Để hiểu rõ hơn các tính năng của plugin, bạn có thể xem các video minh họa sau:

- [Video hướng dẫn tích hợp](https://www.bilibili.com/video/BV1XdjJzeEwe) - Quy trình cài đặt và cấu hình cơ bản
- [Minh họa điều khiển TV](https://www.bilibili.com/video/BV18DM8zuEYV) - Điều khiển TV thông qua script tùy chỉnh
- [Hướng dẫn nâng cao](https://www.bilibili.com/video/BV1SruXzqEW5) - Hướng dẫn chi tiết về Home Assistant, LLM, MCP và XiaoZhi

## Khắc phục sự cố

### Các vấn đề thường gặp

**1. Kết nối thất bại**

- Kiểm tra xem địa chỉ điểm truy cập XiaoZhi MCP có chính xác không
- Xác nhận kết nối mạng của Home Assistant hoạt động bình thường
- Kiểm tra cấu hình tường lửa

**2. Không thể điều khiển thiết bị**

- Xác nhận thiết bị đã được công khai trong trợ lý giọng nói
- Kiểm tra trạng thái thực thể của thiết bị có bình thường không
- Xác minh xem thiết bị có hỗ trợ thao tác tương ứng hay không

**3. Xung đột một số tính năng**

- Tạm thời tắt tính năng tích hợp sẵn
- Điều chỉnh tên thiết bị để tránh trùng lặp
- Chờ bản cập nhật tính năng chọn công cụ của máy chủ XiaoZhi

**4. Phản hồi chậm**

- Kiểm tra chất lượng kết nối mạng
- Tối ưu hiệu năng Home Assistant
- Giảm bớt các thực thể công khai không cần thiết

### Mẹo gỡ lỗi

1. Bật ghi log chi tiết
2. Kiểm tra lần lượt các chức năng cơ bản
3. So sánh với cấu hình thiết bị đang hoạt động bình thường
4. Tham khảo thảo luận và issues từ cộng đồng

## Hỗ trợ cộng đồng

### Liên kết dự án

- **Kho GitHub**: [ha-mcp-for-xiaozhi](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi)
- **Báo lỗi**: [GitHub Issues](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi/issues)
- **Đề xuất tính năng**: [GitHub Discussions](https://github.com/c1pher-cn/ha-mcp-for-xiaozhi/discussions)
