# Hướng dẫn phát triển công cụ MCP

Tài liệu này hướng dẫn cách phát triển công cụ MCP **tích hợp sẵn (built-in)** cho py-xiaozhi. Để tích hợp các dịch vụ MCP bên ngoài, vui lòng xem [Hướng dẫn tích hợp MCP bên ngoài](xiaozhi-mcp.md).

## Nguyên lý hoạt động

1. `McpPlugin.setup` khởi tạo các đối tượng runtime như camera và gọi `register_camera_tools` / `register_screenshot_tools`
2. `McpServer.register_builtin_tools()` gọi **tường minh** hàm `register_*_tools(add_tool, …)` của từng gói tích hợp sẵn
3. Mỗi hàm `register_*` dùng closure để giữ các phụ thuộc (như `MediaPlayer`, `VolumeController`), khởi tạo `McpTool` và gọi `add_tool`
4. `McpServer.reload_external_plugins(media_player=...)` tải các plugin mở rộng, đồng thời đăng ký có điều kiện các công cụ điều khiển phát chung của host (`media.*`) khi `media_player` được cấp quyền và có plugin mở rộng đang hoạt động
5. Các công cụ được cung cấp ra bên ngoài thông qua JSON-RPC 2.0

**Công cụ tích hợp sẵn không sử dụng decorator toàn cục `@mcp_tool` và không tự động quét thư mục (auto-discovery).** Khi thêm một gói công cụ mới: hãy triển khai `register_*_tools`, rồi gắn một lần vào `add_common_tools` (hoặc `McpPlugin`).

Khi cần đối tượng runtime, hãy để container / `McpPlugin` khởi tạo rồi inject vào `register`, **không** viết singleton `get_instance` ở cấp module.

## Bắt đầu nhanh: Phát triển công cụ điều khiển đèn

### Bước 1: Tạo thư mục

```
src/mcp/tools/light/
├── __init__.py          # Xuất register_light_tools
├── register.py      # Triển khai register_light_tools
└── light_manager.py     # Logic nghiệp vụ (tùy chọn)
```

### Bước 2: Logic nghiệp vụ (`light_manager.py`)

```python
"""Logic nghiệp vụ điều khiển đèn."""

from src.logging import get_logger

logger = get_logger()


class LightManager:
    def __init__(self):
        self._on = False
        self._brightness = 100

    def turn_on(self) -> str:
        self._on = True
        logger.info("[Light] Đèn đã bật")
        return "Đèn đã bật"

    def turn_off(self) -> str:
        self._on = False
        logger.info("[Light] Đèn đã tắt")
        return "Đèn đã tắt"

    def set_brightness(self, level: int) -> str:
        self._brightness = max(0, min(100, level))
        logger.info(f"[Light] Đã đặt độ sáng thành {self._brightness}%")
        return f"Đã đặt độ sáng thành {self._brightness}%"

    def get_status(self) -> str:
        state = "bật" if self._on else "tắt"
        return f"Trạng thái đèn: {state}, độ sáng: {self._brightness}%"
```

### Bước 3: `register_light_tools` (`register.py`)

```python
"""Đăng ký công cụ MCP điều khiển đèn."""

from collections.abc import Callable
from typing import Any

from src.logging import get_logger
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

from .light_manager import LightManager

logger = get_logger()


def register_light_tools(
    add_tool: Callable[[McpTool], None],
    manager: LightManager | None = None,
) -> None:
    light = manager or LightManager()

    async def turn_on(args: dict[str, Any]) -> str:
        return light.turn_on()

    async def turn_off(args: dict[str, Any]) -> str:
        return light.turn_off()

    async def set_brightness(args: dict[str, Any]) -> str:
        brightness = int(args.get("brightness", 100))
        return light.set_brightness(brightness)

    async def get_status(args: dict[str, Any]) -> str:
        return light.get_status()

    tools = [
        McpTool(
            "self.light.turn_on",
            "Bật đèn. Gọi khi người dùng nói 'bật đèn', 'mở đèn'.",
            PropertyList(),
            turn_on,
        ),
        McpTool(
            "self.light.turn_off",
            "Tắt đèn. Gọi khi người dùng nói 'tắt đèn', 'tắt đèn đi'.",
            PropertyList(),
            turn_off,
        ),
        McpTool(
            "self.light.set_brightness",
            "Đặt độ sáng cho đèn. Tham số: brightness (0-100).",
            PropertyList(
                [
                    Property(
                        "brightness",
                        PropertyType.INTEGER,
                        min_value=0,
                        max_value=100,
                    )
                ]
            ),
            set_brightness,
        ),
        McpTool(
            "self.light.get_status",
            "Xem trạng thái hiện tại của đèn (bật/tắt, độ sáng).",
            PropertyList(),
            get_status,
        ),
    ]
    for tool in tools:
        add_tool(tool)
    logger.info("Đã đăng ký %d công cụ MCP điều khiển đèn", len(tools))
```

### Bước 4: `__init__.py`

```python
"""Công cụ điều khiển đèn."""

from .register import register_light_tools

__all__ = ["register_light_tools"]
```

### Bước 5: Gắn vào ứng dụng chủ (host)

Trong `add_common_tools` của `src/mcp/mcp_server.py`, thêm:

```python
from src.mcp.tools.light import register_light_tools

register_light_tools(self.add_tool)
```

Nếu công cụ phụ thuộc vào đối tượng từ container, hãy khởi tạo trong `McpPlugin.setup` rồi truyền vào `register_light_tools(server.add_tool, manager)`.

**Hoàn tất.** Sau khi khởi động lại ứng dụng, công cụ điều khiển đèn sẽ sẵn sàng sử dụng.

## Tham chiếu API

### `McpTool` / `Property`

```python
from src.mcp.tooling import McpTool, Property, PropertyList, PropertyType

McpTool(
    name="self.module.action",  # Duy nhất trên toàn hệ thống
    description="AI dựa vào mô tả này để quyết định khi nào gọi",
    properties=PropertyList(
        [
            Property("city", PropertyType.STRING),
            Property(
                "days",
                PropertyType.INTEGER,
                default_value=3,
                min_value=1,
                max_value=7,
            ),
            Property("verbose", PropertyType.BOOLEAN, default_value=False),
        ]
    ),
    callback=async_handler,  # async def handler(args: dict) -> str | int | bool
)
```

### Kiểu tham số

| Kiểu | Cách dùng | Mô tả |
|------|-----------|-------|
| `PropertyType.STRING` | `Property("name", PropertyType.STRING)` | Chuỗi ký tự |
| `PropertyType.INTEGER` | `Property("n", PropertyType.INTEGER, min_value=0, max_value=100)` | Số nguyên, có thể giới hạn khoảng giá trị |
| `PropertyType.BOOLEAN` | `Property("flag", PropertyType.BOOLEAN, default_value=False)` | Giá trị logic (Boolean) |

- Tham số không có `default_value` thường là **bắt buộc** (được kiểm tra ở phía giao thức)
- `min_value` / `max_value` chỉ có hiệu lực với `INTEGER`

### Giá trị trả về

Hàm callback nên trả về **`str`** (hoặc `bool`/`int`). Với dữ liệu có cấu trúc, hãy dùng `json.dumps(..., ensure_ascii=False)`.

**Không trả về trực tiếp `dict`** làm dạng chính của body giao thức; cần tuân theo quy ước đóng gói hiện có của `McpTool`.

## Quy ước đăng ký

| Quy tắc | Mô tả |
|---------|-------|
| Điểm vào (Entry) | Gói xuất hàm `register_*_tools(add_tool, ...)`, phần triển khai đặt trong **`register.py`** |
| Cấu trúc gói | `__init__.py` (re-export) + `register.py` (đăng ký) + module nghiệp vụ (ví dụ `service.py`) |
| Gắn kết | Gọi **tường minh** một lần trong `add_common_tools` hoặc `McpPlugin.setup` |
| Phụ thuộc | Đối tượng có trạng thái được inject vào closure qua tham số; cấm dùng `get_instance` toàn cục cấp module |
| Đặt tên | Tên công cụ theo dạng `self.module.action` hoặc quy ước nghiệp vụ, duy nhất toàn cục |
| Bất đồng bộ | `async def`; các tác vụ IO chặn (blocking IO) dùng `asyncio.to_thread` |
| Thời gian chờ | API bên ngoài bắt buộc phải đặt `timeout` |
| Ghi log | `get_logger()`, tiền tố `[ToolName]` |
| Xử lý lỗi | Dùng `try/except`, trả về thông báo dễ hiểu cho người dùng + `logger.error(..., exc_info=True)` |

## Các module công cụ hiện có

| Module | Đường dẫn | Tệp đăng ký | Cách đăng ký | Tài liệu chi tiết |
|--------|-----------|-------------|--------------|-------------------|
| Âm lượng | `volume/` | `register.py` | `register_volume_tools` | [system.md](system.md) |
| Ứng dụng | `app/` | `register.py` | `register_app_tools` | [system.md](system.md) |
| Camera | `camera/` | `register.py` | `register_camera_tools` (`McpPlugin`) | [camera.md](camera.md) |
| Chụp màn hình | `screenshot/` | `register.py` | `register_screenshot_tools` (`McpPlugin`) | — |
| Điều khiển phát media | `media/` | `register.py` | `register_media_tools` (đăng ký có điều kiện: bật khi cấp quyền phát cho plugin mở rộng và có plugin đang chạy) | [plugins.md](plugins.md) |
| Thời tiết | `weather/` | `register.py` + `service.py` | `register_weather_tools` (hiện đang là mock) | — |

Để tìm hiểu về **plugin mở rộng** trong thư mục dữ liệu người dùng (đóng gói sẵn thư viện phụ thuộc, cài đặt dùng ngay), hãy xem [Plugin mở rộng MCP](./plugins.md); cơ chế này hoạt động song song với `register_*` tích hợp sẵn và không khôi phục cơ chế quét decorator toàn cục.
