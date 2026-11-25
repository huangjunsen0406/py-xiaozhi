# Công cụ hệ thống (System Tools)

Công cụ hệ thống hướng đến các tác vụ điều khiển âm lượng và quản lý ứng dụng trên máy tính để bàn, đóng gói các khả năng thiết lập/truy vấn âm lượng có thể gọi qua MCP, cùng quy trình quét, khởi chạy, liệt kê và đóng ứng dụng đa nền tảng.

### Các tình huống sử dụng phổ biến

**Điều chỉnh và truy vấn âm lượng:**

- "Chỉnh âm lượng về 40"
- "Tắt tiếng giúp tôi"
- "Âm lượng hiện tại là bao nhiêu"
- "Loa có đang hoạt động không"

**Khởi chạy ứng dụng:**

- "Mở WeChat"
- "Mở Notepad"
- "Mở trình duyệt giúp tôi"
- "Chạy VS Code"

**Khám phá và liệt kê ứng dụng:**

- "Trong máy có những ứng dụng nào"
- "Liệt kê các chương trình đang chạy"
- "Có những trình phát nào dùng được"
- "Kiểm tra xem QQ có đang chạy không"

**Đóng ứng dụng:**

- "Thoát QQ Music"
- "Buộc đóng Chrome"
- "Tắt trình phát đi"
- "Kết thúc tất cả tiến trình tên là XXX"

### Mẹo sử dụng

1. **Phạm vi giá trị âm lượng**: Mọi thao tác chỉnh âm lượng sử dụng số nguyên từ 0-100, trong đó 0 là tắt tiếng (mute)
2. **Khả năng đa nền tảng**: Công cụ quản lý ứng dụng tự động nhận diện Windows/macOS/Linux và gọi phần triển khai tương ứng
3. **Khớp tên ứng dụng**: Nên dùng trường `name` do `self.application.scan_installed` trả về để khởi chạy hoặc đóng ứng dụng nhằm giảm sai số khi khớp mờ
4. **Phân tích kết quả**: `get_volume_status`, `scan_installed`, `list_running` đều trả về chuỗi JSON; bên gọi cần tự dùng `json.loads`

Trợ lý AI sẽ tự chọn công cụ hệ thống phù hợp theo nhu cầu để hoàn tất các thao tác liên quan đến âm lượng và ứng dụng trong phiên thoại / văn bản.

## Tổng quan tính năng

### Điều khiển âm lượng và âm thanh

- **Đặt âm lượng tuyệt đối**: Đặt trực tiếp âm lượng loa về mức mục tiêu
- **Truy vấn âm lượng**: Lấy phần trăm âm lượng hiện tại
- **Chẩn đoán trạng thái**: Truy vấn cờ tắt tiếng, tính sẵn sàng của thư viện phụ thuộc... để kiểm tra khả năng âm thanh

### Quản lý ứng dụng

- **Khởi chạy ứng dụng**: Mở ứng dụng desktop, công cụ hoặc trò chơi qua một điểm vào thống nhất
- **Quét ứng dụng**: Lấy danh sách ứng dụng có thể khởi chạy, hỗ trợ cả tên tiếng Trung và tiếng Anh
- **Liệt kê ứng dụng đang chạy**: Xem các tiến trình đang chạy theo thời gian thực, hỗ trợ lọc theo tên
- **Đóng ứng dụng**: Thoát bình thường hoặc buộc chấm dứt ứng dụng chỉ định

### Minh bạch trạng thái

- **Phản hồi có cấu trúc**: Mọi công cụ truy vấn đều trả về JSON có cấu trúc gồm các trường như `success`, `message`
- **Cách ly luồng**: Thao tác thực tế (quét/khởi chạy/đóng) chạy trên luồng nền hoặc tiến trình con, không làm chặn vòng lặp chính của MCP

## Danh sách công cụ

### 1. Công cụ âm lượng và âm thanh

#### self.audio_speaker.set_volume - Đặt âm lượng hệ thống

Đặt âm lượng loa hệ thống về giá trị tuyệt đối, bên trong gọi trực tiếp `VolumeController`.

**Tham số:**

- `volume` (bắt buộc): Số nguyên từ 0-100, 0 biểu thị tắt tiếng

**Tình huống sử dụng:**

- Điều chỉnh âm lượng chính xác
- Bật tắt tiếng / bỏ tắt tiếng
- Người dùng yêu cầu “tăng/giảm đến một mức cụ thể”

**Giá trị trả về:**

- Giá trị boolean `True/False` cho biết thao tác có thành công hay không

#### self.audio_speaker.get_volume - Truy vấn âm lượng hiện tại

Trả về âm lượng loa hiện tại (0-100). Trả về giá trị mặc định nếu thiếu thư viện phụ thuộc.

**Tham số:**
Không có

**Tình huống sử dụng:**

- Trả lời câu hỏi “Âm lượng hiện tại là bao nhiêu”
- Đọc giá trị cũ trước khi điều chỉnh
- Kiểm tra xem máy có đang tắt tiếng không

**Giá trị trả về:**

- Giá trị âm lượng dạng số nguyên; trả về `VolumeController.DEFAULT_VOLUME` nếu phụ thuộc không khả dụng

#### self.audio_speaker.get_volume_status - Lấy trạng thái âm lượng

Cung cấp chuỗi JSON chi tiết gồm âm lượng, cờ tắt tiếng và tính sẵn sàng của phụ thuộc.

**Tham số:**
Không có

**Tình huống sử dụng:**

- Kiểm tra xem các thư viện phụ thuộc điều khiển âm lượng đã đầy đủ chưa
- Xác định xem âm thanh có đang bị tắt tiếng hay không
- Hiển thị trạng thái phong phú hơn trên giao diện UI

**Giá trị trả về:**

- Chuỗi JSON gồm các trường `volume`, `muted`, `available`, `reason/error`

### 2. Công cụ vòng đời ứng dụng

#### self.application.launch - Khởi chạy ứng dụng

Khởi chạy ứng dụng đa nền tảng: hỗ trợ phần mềm máy tính, công cụ hệ thống, trình duyệt, trò chơi, v.v.

**Tham số:**

- `app_name` (bắt buộc): Tên hoặc đường dẫn ứng dụng, có thể pha trộn tiếng Trung và tiếng Anh

**Tình huống sử dụng:**

- Mở QQ, WeChat, trình duyệt, VS Code, v.v.
- Gọi ứng dụng tích hợp sẵn của hệ thống (Calculator, Notepad, v.v.)
- Khởi chạy chương trình có trong PATH hoặc đã được quét thấy

#### self.application.scan_installed - Quét ứng dụng đã cài đặt

Liệt kê danh sách ứng dụng có thể khởi chạy kèm các trường cần cho việc đối khớp như `name`, `display_name`, `path`, `type`.

**Tham số:**

- `force_refresh` (tùy chọn): Có buộc quét lại hay không, mặc định `false`

**Tình huống sử dụng:**

- Tra cứu trước khi không chắc chắn tên ứng dụng
- Cho người dùng biết các phần mềm khả dụng trên hệ thống hiện tại
- Kiểm tra lại tên khi gọi `self.application.launch` thất bại

**Giá trị trả về:**

- Chuỗi JSON chứa `success`, `total_count`, `applications[]`

#### self.application.list_running - Liệt kê ứng dụng đang chạy

Liệt kê theo thời gian thực các tiến trình ứng dụng đang chạy, hỗ trợ lọc theo tên.

**Tham số:**

- `filter_name` (tùy chọn): Khớp chuỗi con theo tên, mặc định rỗng

**Tình huống sử dụng:**

- Trả lời câu hỏi “Những chương trình nào đang chạy”
- Xác nhận ứng dụng có đang chạy hay không trước khi đóng
- Kiểm tra các tiến trình đang chiếm tài nguyên

**Giá trị trả về:**

- Chuỗi JSON gồm các trường `success`, `total_count`, `applications[]`

#### self.application.kill - Đóng / buộc kết thúc ứng dụng

Đóng một hoặc nhiều chương trình đang chạy khớp theo tên; trên Windows hỗ trợ đóng theo nhóm và buộc kết thúc (force kill).

**Tham số:**

- `app_name` (bắt buộc): Tên ứng dụng cần đóng
- `force` (tùy chọn): Đặt `true` để bật buộc kết thúc (force kill), mặc định `false`

**Tình huống sử dụng:**

- Người dùng yêu cầu thoát / đóng một ứng dụng
- Chương trình bị treo cần buộc kết thúc
- Dọn hàng loạt các phiên bản cùng tên của chương trình

**Giá trị trả về:**

- Giá trị boolean `True/False` cho biết có đóng thành công ít nhất một tiến trình khớp hay không

> Khuyến nghị kết hợp với `self.application.list_running` để lấy PID/tên trước khi gọi `self.application.kill` nhằm tránh đóng nhầm.

## Ví dụ sử dụng

### Ví dụ điều khiển âm lượng

```python
# Đặt âm lượng thành 50
await mcp_server.call_tool("self.audio_speaker.set_volume", {"volume": 50})

# Truy vấn âm lượng hiện tại
current_volume = await mcp_server.call_tool("self.audio_speaker.get_volume", {})

# Lấy trạng thái âm lượng chi tiết (cần tự parse chuỗi JSON)
import json
status_json = await mcp_server.call_tool("self.audio_speaker.get_volume_status", {})
status = json.loads(status_json)
```

### Ví dụ quản lý ứng dụng

```python
import json

# Quét các ứng dụng đã cài đặt
scan_raw = await mcp_server.call_tool("self.application.scan_installed", {"force_refresh": False})
scan_result = json.loads(scan_raw)

# Khởi chạy ứng dụng đầu tiên trong kết quả quét
first_app = scan_result["applications"][0]["name"]
await mcp_server.call_tool("self.application.launch", {"app_name": first_app})

# Liệt kê các ứng dụng đang chạy
running_raw = await mcp_server.call_tool("self.application.list_running", {"filter_name": "QQ"})
running = json.loads(running_raw)

# Đóng tất cả ứng dụng có tên chứa QQ
await mcp_server.call_tool("self.application.kill", {
    "app_name": "QQ",
    "force": False
})
```

## Kiến trúc kỹ thuật

### Điều khiển âm lượng (`src/mcp/tools/volume/`)

- **VolumeController**: Điều khiển âm lượng đa nền tảng (Windows: `pycaw`, macOS: `applescript`, Linux: `pactl`/`wpctl`/`amixer`)
- **Đóng gói bất đồng bộ**: Đưa các lời gọi chặn (blocking) sang thread pool thông qua `asyncio.to_thread`
- **Chiến lược chịu lỗi**: Khi thiếu phụ thuộc sẽ trả về âm lượng mặc định và đánh dấu `available=False` trong API trạng thái

### Quản lý ứng dụng (`src/mcp/tools/app/`)

- **Quản lý tiến trình**: `process_manager.py` dựa trên `psutil`, thống nhất việc liệt kê và chấm dứt tiến trình trên cả 3 nền tảng
- **Quét ứng dụng**: `scanner.py` + tệp theo từng nền tảng (`scanner_mac.py` / `scanner_windows.py` / `scanner_linux.py`)
- **Khởi chạy ứng dụng**: `launcher.py` + tệp theo từng nền tảng (`launcher_mac.py` / `launcher_windows.py` / `launcher_linux.py`)
- **Khớp thống nhất**: `AppMatcher` trong `utils.py` phụ trách khớp mờ (tiếng Trung, tiếng Anh, không phân biệt hoa thường, bí danh)

## Cấu trúc dữ liệu

### Trạng thái âm lượng

```python
{
    "volume": 42,
    "muted": false,
    "available": true
}
```

### Kết quả quét ứng dụng đã cài đặt

```python
{
    "success": true,
    "total_count": 128,
    "applications": [
        {
            "name": "QQ",
            "display_name": "QQ 音乐",
            "path": "C:/Program Files/QQMusic/QQMusic.exe",
            "type": "exe"
        },
        {
            "name": "WeChat",
            "display_name": "微信",
            "path": "/Applications/WeChat.app",
            "type": "app"
        }
    ],
    "message": "Đã quét thành công 128 ứng dụng đã cài đặt"
}
```

### Danh sách ứng dụng đang chạy

```python
{
    "success": true,
    "total_count": 2,
    "applications": [
        {
            "pid": 1234,
            "name": "WeChat",
            "display_name": "微信",
            "command": "/Applications/WeChat.app/Contents/MacOS/WeChat"
        },
        {
            "pid": 4321,
            "name": "QQMusic",
            "display_name": "QQ 音乐",
            "command": "C:/Program Files/QQMusic/QQMusic.exe"
        }
    ],
    "message": "Tìm thấy 2 ứng dụng đang chạy"
}
```

## Thực hành tốt nhất

### Quản lý âm lượng

- Gọi `get_volume` trước để lấy mức cũ, từ đó phản hồi rõ ràng dạng “đã chỉnh từ X sang Y”
- Khi tắt tiếng có thể đặt trực tiếp về 0; khi bỏ tắt tiếng hãy khôi phục về mức đã ghi nhận trước đó
- Khi thiếu thư viện phụ thuộc, hãy nhắc người dùng cài đặt hoặc cấp quyền điều khiển âm thanh

### Quản lý ứng dụng

- Trước khi khởi chạy/đóng, hãy dùng `scan_installed` hoặc `list_running` để xác minh tên nhằm hạn chế thao tác nhầm
- Trước khi buộc đóng (`force=true`), hãy thử đóng bình thường trước để tránh hỏng dữ liệu
- Với chương trình chạy nhiều phiên bản, có thể liệt kê danh sách đang chạy và báo cho người dùng theo PID

## Khắc phục sự cố

1. **Đặt âm lượng thất bại**: Kiểm tra trường `available`/`reason` trong `get_volume_status`
2. **Khởi chạy ứng dụng thất bại**: Xác nhận ứng dụng có trong kết quả quét hoặc cung cấp đường dẫn đầy đủ
3. **Đóng ứng dụng thất bại**: Dùng `list_running` xác minh ứng dụng có thực sự đang chạy không, bật `force` nếu cần
4. **Quét quá thời gian chờ**: Khi có nhiều ứng dụng sẽ mất thời gian hơn; có thể nhắc người dùng chờ hoặc thu hẹp phạm vi quét

## Cân nhắc bảo mật

### Quyền hạn và kiểm soát truy cập

- Điều khiển âm lượng phụ thuộc quyền cấp hệ thống, lần gọi đầu có thể cần người dùng cấp phép
- Các thao tác khởi chạy, đóng ứng dụng chỉ nên thực hiện sau khi có chỉ thị rõ ràng từ người dùng để tránh ảnh hưởng nhầm các chương trình nhạy cảm
- Đóng bằng `force` sẽ kết thúc tiến trình ngay lập tức; cần thông báo cho người dùng trước về nguy cơ mất dữ liệu

### Bảo vệ dữ liệu

- Danh sách quét / đang chạy có thể chứa tên phần mềm mà người dùng đã cài, cần thận trọng khi hiển thị ra bên ngoài
- Khi cần lưu log lâu dài, nên ẩn thông tin nhạy cảm và chỉ giữ lại các trường cần thiết
- Không ghi log hoặc gửi lên các tham số dòng lệnh cụ thể để bảo vệ quyền riêng tư

Thông qua các công cụ hệ thống này, trợ lý AI có thể điều chỉnh âm lượng, khởi chạy và quản lý ứng dụng desktop một cách an toàn trên nhiều nền tảng, mang đến trải nghiệm điều khiển hệ thống bằng ngôn ngữ tự nhiên cho người dùng cuối.
