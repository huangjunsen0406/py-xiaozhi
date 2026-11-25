# Công cụ Camera (Camera Tools)

Công cụ Camera là một công cụ MCP nhận diện thị giác thông minh, cung cấp các khả năng chụp ảnh, phân tích thị giác và hiểu nội dung hình ảnh.

### Các tình huống sử dụng phổ biến

**Nhận diện và phân tích hình ảnh:**
- "Chụp giúp tôi một tấm ảnh xem đây là cái gì"
- "Chụp ảnh nhận diện vật thể này giúp tôi"
- "Dùng camera xem trước mặt tôi là thứ gì"
- "Xem thử món đồ này là gì"
- "Nhận diện giúp tôi cái này là gì"
- "Xem giúp tôi cái này"
- "Chụp ảnh phân tích đồ vật này"

**Hiểu bối cảnh:**
- "Chụp ảnh mô tả khung cảnh hiện tại"
- "Dùng camera xem trong phòng có gì"
- "Chụp ảnh phân tích môi trường xung quanh đây"
- "Xem tình hình xung quanh"
- "Mô tả khung cảnh này"
- "Phân tích môi trường ở đây"

**Nhận diện văn bản (OCR):**
- "Chụp ảnh nhận diện chữ trên tài liệu này"
- "Dùng camera đọc thông tin trên nhãn này"
- "Chụp ảnh dịch đoạn tiếng Anh này"
- "Đọc đoạn chữ này"
- "Nhận diện nội dung văn bản"
- "Đọc giúp tôi đoạn này"
- "Dịch đoạn văn bản này"
- "Trích xuất thông tin chữ viết"

**Giải đáp câu hỏi:**
- "Chụp ảnh xem giúp tôi bài tập này làm thế nào"
- "Dùng camera phân tích biểu đồ này"
- "Chụp ảnh giải thích biển báo này nghĩa là gì"
- "Bài này giải thế nào"
- "Phân tích biểu đồ này"
- "Giải thích biển báo này"
- "Giúp tôi giải đáp câu hỏi này"

**Trợ lý đời sống:**
- "Chụp ảnh nhận diện giống cây này"
- "Dùng camera xem công thức nấu ăn này"
- "Chụp ảnh nhận diện giúp tôi sản phẩm này"
- "Đây là cây gì"
- "Nhận diện loài hoa này"
- "Xem công thức món ăn này"
- "Sản phẩm này là gì"
- "Xem giúp tôi mặt hàng này"

### Mẹo sử dụng

1. **Đảm bảo đủ ánh sáng**: Điều kiện ánh sáng tốt giúp nâng cao độ chính xác khi nhận diện
2. **Giữ thiết bị ổn định**: Cố gắng giữ camera cố định khi chụp để tránh ảnh bị mờ
3. **Đặt câu hỏi rõ ràng**: Mô tả cụ thể điều bạn muốn biết, ví dụ "Nhận diện loài cây này" thay vì chỉ hỏi "Đây là gì"
4. **Khoảng cách phù hợp**: Giữ khoảng cách chụp hợp lý để vật thể mục tiêu hiển thị rõ nét

Trợ lý AI sẽ tự động gọi công cụ Camera theo nhu cầu của bạn, chụp ảnh và thực hiện phân tích thông minh.

## Tổng quan tính năng

### Chức năng chụp ảnh
- **Chụp ảnh thông minh**: Tự động điều chỉnh thông số camera để chụp ảnh rõ nét
- **Tối ưu kích thước**: Tự động điều chỉnh kích thước ảnh nhằm tăng hiệu quả xử lý
- **Chuyển đổi định dạng**: Chuyển ảnh sang định dạng JPEG tiêu chuẩn

### Chức năng phân tích thị giác
- **Nhận diện vật thể**: Nhận diện các đối tượng và khung cảnh trong ảnh
- **Nhận diện văn bản**: Trích xuất nội dung chữ viết trong ảnh
- **Hiểu bối cảnh**: Phân tích nội dung ảnh và đưa ra mô tả
- **Giải đáp câu hỏi**: Trả lời câu hỏi của người dùng dựa trên nội dung ảnh

### Chức năng quản lý thiết bị
- **Cấu hình camera**: Tự động phát hiện và cấu hình thiết bị camera
- **Điều chỉnh thông số**: Hỗ trợ thiết lập độ phân giải, tốc độ khung hình (FPS), v.v.
- **Xử lý lỗi**: Cơ chế xử lý lỗi và khôi phục hoàn chỉnh

## Danh sách công cụ

### 1. Công cụ chụp và phân tích ảnh

#### take_photo - Chụp ảnh và phân tích
Chụp ảnh và tiến hành phân tích thông minh.

**Tham số:**
- `question` (tùy chọn): Câu hỏi cụ thể hoặc yêu cầu phân tích đối với bức ảnh

**Tình huống sử dụng:**
- Nhận diện vật thể
- Phân tích khung cảnh
- Nhận diện văn bản
- Giải đáp câu hỏi
- Trợ lý đời sống

## Ví dụ sử dụng

### Ví dụ chụp ảnh và phân tích cơ bản

```python
# Chụp ảnh và phân tích đơn giản
result = await mcp_server.call_tool("take_photo", {
    "question": "Đây là vật thể gì?"
})

# Mô tả khung cảnh
result = await mcp_server.call_tool("take_photo", {
    "question": "Hãy mô tả khung cảnh này"
})

# Nhận diện văn bản
result = await mcp_server.call_tool("take_photo", {
    "question": "Nhận diện nội dung văn bản trong ảnh"
})

# Giải đáp câu hỏi
result = await mcp_server.call_tool("take_photo", {
    "question": "Bài toán này giải như thế nào?"
})
```

## Kiến trúc kỹ thuật

### Quản lý camera
- **Container injection**: `McpPlugin` khởi tạo thực thể camera và gọi `register_camera_tools`, không dùng singleton toàn cục
- **Backend thu ảnh có thể cắm rút** (`src/mcp/tools/camera/capture_backend.py`):
  - **OpenCV / V4L2**: USB trên máy tính để bàn, USB trên Linux (Linux ưu tiên `CAP_V4L2`)
  - **picamera2**: Camera CSI chính thức của Raspberry Pi (ngăn xếp libcamera trên Bookworm)
  - **`backend=auto`**: Thử OpenCV trước, nếu thất bại sẽ tự lùi về `picamera2`
- **Khung hình làm nóng (warm-up frames)**: Bỏ qua một vài khung hình đầu sau khi mở thiết bị trước khi lấy ảnh (vài khung hình đầu của USB / Pi thường không hợp lệ)
- **Bảo vệ timeout**: Việc thu ảnh chạy trong thread pool để tránh driver bị treo làm đứng luồng chính
- **Quản lý tài nguyên**: Mỗi lần chụp theo chu trình open → đọc khung hình → release / stop, không chiếm giữ thiết bị lâu dài

### Xử lý ảnh
- **Mã hóa OpenCV**: Thu nhỏ sau khi chụp (mặc định cạnh dài nhất 320 px) và mã hóa sang JPEG
- **Tối ưu định dạng**: JPEG giúp giảm dung lượng tải lên

### Dịch vụ thị giác
- **Phân tích từ xa**: Hỗ trợ kết nối dịch vụ phân tích thị giác từ xa (`NormalCamera`)
- **Zhipu VL**: Khi cấu hình đủ `VLapi_key` + `Local_VL_url` sẽ sử dụng `VLCamera`
- **Xác thực danh tính**: Token và ID thiết bị
- **Xử lý lỗi**: Trả về thông báo lỗi dạng JSON khi lỗi mạng hoặc thu ảnh thất bại

## Hướng dẫn cấu hình

### Cấu hình camera
Các mục cấu hình liên quan đến camera nằm trong tệp cấu hình:

```json
{
  "CAMERA": {
    "backend": "auto",
    "device": "",
    "camera_index": 0,
    "frame_width": 640,
    "frame_height": 480,
    "fps": 30,
    "warm_up_frames": 5,
    "Local_VL_url": "https://open.bigmodel.cn/api/paas/v4/",
    "VLapi_key": "",
    "models": "glm-4v-plus"
  }
}
```

**Giải thích các mục cấu hình:**

| Mục cấu hình | Kiểu | Mặc định | Mô tả |
|--------------|------|----------|-------|
| `backend` | String | `"auto"` | `auto` / `opencv` / `picamera2` |
| `device` | String | `""` | Đường dẫn thiết bị, ví dụ `"/dev/video0"`; khi không rỗng sẽ ưu tiên hơn `camera_index` |
| `camera_index` | Integer | `0` | Chỉ số thiết bị OpenCV (thường dùng trên máy tính để bàn) |
| `frame_width` / `frame_height` | Integer | 640 / 480 | Độ phân giải mong muốn (driver có thể lùi về mức khác) |
| `warm_up_frames` | Integer | `5` | Số khung hình làm nóng bị loại bỏ sau khi mở camera |
| `Local_VL_url` / `VLapi_key` / `models` | — | — | Mô hình đa phương thức VL như Zhipu; khi cấu hình đủ cả hai sẽ phân tích qua VL |

### Chọn nền tảng và backend

| Tình huống | Khuyến nghị |
|------------|-------------|
| Camera USB hoặc tích hợp trên macOS / Windows | `backend=auto` hoặc `opencv`, dùng `camera_index` |
| Camera **USB UVC** trên Linux / Raspberry Pi | `backend=opencv`, ưu tiên cấu hình `device` là `/dev/videoX` |
| Camera **CSI chính thức** trên Raspberry Pi | Cài gói hệ thống `python3-picamera2`, đặt `backend=auto` hoặc `picamera2` |
| Trên macOS **không** cài `picamera2` bằng pip | Sẽ kéo theo `python-prctl` gây lỗi biên dịch |

### Quét thiết bị và chụp thử

```bash
# Liệt kê thiết bị; có thể ghi vào cấu hình và chụp thử
python scripts/camera_scanner.py
python scripts/camera_scanner.py --test
python scripts/camera_scanner.py --select 0 --test
python scripts/camera_scanner.py --device /dev/video0 --test
python scripts/camera_scanner.py --backend picamera2 --test
```

GUI: Cài đặt → Camera → Làm mới → Chọn **Camera N / V4L2 /dev/videoX / Raspberry Pi CSI** → Kiểm tra.

### Cấu hình dịch vụ thị giác
Dịch vụ phân tích thị giác cần cấu hình:
- **URL dịch vụ**: Địa chỉ API của dịch vụ phân tích thị giác (do máy chủ cấp hoặc VL URL)
- **Xác thực danh tính**: Token hoặc khóa API
- **Thông tin thiết bị**: ID thiết bị và ID máy khách (Client ID)

## Cấu trúc dữ liệu

### Định dạng dữ liệu ảnh
```python
{
    "buf": bytes,      # Dữ liệu byte ảnh JPEG
    "len": int         # Độ dài dữ liệu
}
```

### Định dạng kết quả phân tích
```python
{
    "success": bool,           # Có thành công hay không
    "message": str,            # Thông báo kết quả hoặc thông báo lỗi
    "analysis": {              # Kết quả phân tích (khi thành công)
        "objects": [...],      # Các vật thể được nhận diện
        "text": str,           # Văn bản trích xuất được
        "description": str,    # Mô tả khung cảnh
        "answer": str          # Câu trả lời cho câu hỏi
    }
}
```

## Quy trình xử lý ảnh

### 1. Chụp ảnh
1. Chọn backend dựa trên `CAMERA.backend` / `device` / `camera_index`
2. OpenCV: mở thiết bị (Linux ưu tiên V4L2) → thử đặt độ phân giải → bỏ qua khung hình làm nóng → đọc khung hình hợp lệ
3. Hoặc picamera2: cấu hình still → start → làm nóng → `capture_array` → chuyển sang BGR
4. Thu phóng và mã hóa JPEG, sau đó giải phóng thiết bị

### 2. Tiền xử lý ảnh
1. Lấy thông tin kích thước ảnh
2. Tính tỷ lệ thu phóng (cạnh dài nhất không vượt quá 320 pixel)
3. Thu phóng ảnh theo đúng tỷ lệ
4. Chuyển sang định dạng JPEG

### 3. Phân tích thị giác
1. Chuẩn bị thông tin header yêu cầu
2. Tạo yêu cầu đa phương tiện
3. Gửi đến dịch vụ phân tích thị giác
4. Phân tích cú pháp kết quả trả về

## Thực hành tốt nhất

### 1. Tối ưu chất lượng ảnh
- Đảm bảo điều kiện ánh sáng đầy đủ
- Giữ ống kính camera sạch sẽ
- Tránh phơi sáng quá mức hoặc quá tối
- Giữ đối tượng chụp rõ nét

### 2. Kỹ năng mô tả câu hỏi
- Sử dụng câu hỏi cụ thể, rõ ràng
- Tránh diễn đạt mơ hồ
- Cung cấp thông tin ngữ cảnh
- Nêu rõ trọng tâm cần phân tích

### 3. Tối ưu hiệu năng
- Thiết lập độ phân giải ảnh hợp lý
- Tránh chụp ảnh liên tục quá dày
- Giải phóng tài nguyên kịp thời
- Xử lý tình huống hết thời gian chờ mạng (timeout)

### 4. Xử lý lỗi
- Kiểm tra tính sẵn sàng của camera
- Xử lý lỗi kết nối mạng
- Xác thực kết quả phân tích
- Cung cấp thông báo lỗi thân thiện với người dùng

## Các loại phân tích được hỗ trợ

### Nhận diện vật thể
- Nhận diện đồ dùng hằng ngày
- Nhận diện động thực vật
- Nhận diện món ăn
- Nhận diện hàng hóa, sản phẩm

### Nhận diện văn bản
- Nhận diện chữ in
- Nhận diện chữ viết tay
- Nhận diện văn bản đa ngôn ngữ
- Trích xuất nội dung tài liệu

### Hiểu bối cảnh
- Phân tích khung cảnh trong nhà
- Mô tả môi trường ngoài trời
- Nhận diện hành động con người
- Hiểu bối cảnh hoạt động

### Giải đáp câu hỏi
- Giải bài tập toán
- Phân tích biểu đồ
- Giải thích biển báo, ký hiệu
- Câu hỏi kỹ thuật

## Lưu ý

1. **Bảo vệ quyền riêng tư**: Chức năng chụp ảnh liên quan đến quyền riêng tư, vui lòng sử dụng thận trọng
2. **Phụ thuộc mạng**: Phân tích thị giác yêu cầu kết nối Internet
3. **Quyền truy cập thiết bị**: Cần cấp quyền truy cập camera
4. **Thời gian xử lý**: Phân tích hình ảnh có thể mất một khoảng thời gian nhất định

## Khắc phục sự cố

### Các lỗi thường gặp
1. **Không mở được camera**: Kiểm tra kết nối, quyền truy cập (nhóm `video` trên Linux), `camera_index` / `device`
2. **Máy tính bình thường nhưng Raspberry Pi CSI không chạy**: CSI cần `libcamera` + `python3-picamera2`, đừng chỉ dựa vào `VideoCapture(0)`
3. **Trên Pi không mở được index 0**: Kiểm tra `ls /dev/video*`, dùng `--device /dev/videoX` hoặc đổi index
4. **Mở thành công nhưng ảnh đen / lỗi**: Tăng `warm_up_frames` hoặc hạ yêu cầu độ phân giải
5. **Phân tích thất bại**: Kiểm tra mạng, explain URL / VL Key
6. **Trên macOS `uv` lỗi vì `picamera2` / `python-prctl`**: Không cài `picamera2` trên Mac, chỉ cài trên Pi bằng `apt`

### Cách gỡ lỗi
```bash
# Linux / Pi
ls -l /dev/video*
groups   # Phải có nhóm video
# Ngăn xếp hệ thống CSI
rpicam-hello -t 1000   # hoặc libcamera-hello

python scripts/camera_scanner.py --test
```

Với công cụ Camera, bạn có thể dễ dàng khai thác khả năng nhận diện thị giác thông minh và phân tích hình ảnh, mang lại sự tiện lợi cho cuộc sống hằng ngày và công việc.
