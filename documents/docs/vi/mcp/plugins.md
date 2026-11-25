# Plugin mở rộng MCP

Hướng đến **bản cài đặt đã đóng gói (exe / dmg)** lẫn môi trường phát triển: nhà phát triển plugin đóng gói sẵn **gói plugin Python kèm đầy đủ thư viện phụ thuộc**, người dùng phổ thông chỉ cần nhập tệp ZIP / thư mục bằng một cú nhấp chuột trong trang cài đặt để mở rộng công cụ MCP — **không cần** `pip install` và cũng không cần sửa mã nguồn dự án chính.

Để phát triển công cụ tích hợp sẵn, vui lòng xem [Hướng dẫn phát triển công cụ MCP](./index.md). Plugin mở rộng và công cụ tích hợp sẵn **tồn tại song song hai luồng**.

## Tóm tắt trong một câu

**Nhà phát triển xây dựng gói plugin (`plugin.py` + `manifest.json` + `lib/`) → Người dùng nhập ZIP / thư mục trong 「Cài đặt tham số → Công cụ MCP」 → Tải nóng (hot reload) và có hiệu lực ngay lập tức.**

## Điểm khác biệt so với công cụ tích hợp sẵn

| | Tích hợp sẵn | Plugin mở rộng |
|--|--------------|----------------|
| Vị trí | `src/mcp/tools/<name>/` | `{dữ_liệu_người_dùng}/mcp_plugins/<id>/` |
| Điểm vào | `register.py` → `register_*_tools` | `plugin.py` → `register(host)` |
| Thư viện phụ thuộc | Phụ thuộc của ứng dụng chính | Tự đóng gói trong thư mục `lib/` của plugin (vendored) |
| Thư mục dữ liệu | Thư mục dữ liệu dùng chung của host | Thư mục cách ly riêng `{dữ_liệu_người_dùng}/mcp_plugins_data/<id>/` |
| Phát hành | Đi kèm bản phát hành ứng dụng chính | Phiên bản độc lập của từng plugin |
| Thao tác người dùng | Nâng cấp ứng dụng | Nhập / gỡ cài đặt bằng một cú nhấp trong trang cài đặt |

## Thư mục cài đặt và cấu hình

| Nền tảng | Thư mục mã nguồn plugin mặc định |
|----------|----------------------------------|
| macOS | `~/Library/Application Support/py-xiaozhi/mcp_plugins/` |
| Windows | `%LOCALAPPDATA%\py-xiaozhi\mcp_plugins\` |
| Linux | `~/.local/share/py-xiaozhi/mcp_plugins/` |

Nếu cần di chuyển toàn bộ thư mục dữ liệu người dùng (bao gồm cấu hình, log, plugin và dữ liệu plugin), hãy đặt biến môi trường `XIAOZHI_DATA_DIR` trước khi khởi động.

Mục cấu hình (`config.json`):

```json
"MCP_PLUGINS": {
  "ENABLED": true,
  "DIR": null,
  "ENABLED_IDS": [],
  "DISABLED_IDS": [],
  "ALLOW_HOST_GET": ["config_readonly", "logger", "data_dir"]
}
```

- Khi `DIR` là `null`, ứng dụng dùng đường dẫn mặc định ở bảng trên.
- Nếu `DISABLED_IDS` chứa `id` của plugin → **không tải plugin đó**.
- `ALLOW_HOST_GET` kiểm soát danh sách cho phép (whitelist) của `host.get`; quyền phát âm thanh/media `media_player` mặc định bị tắt, có thể bật công tắc 「**Cho phép plugin sử dụng trình phát trong ứng dụng**」 trong 「Cài đặt tham số → Công cụ MCP」.

## Cấu trúc gói plugin

```text
demo_media_plugin/
  manifest.json     # Định danh, runtime và điểm vào (entry)
  plugin.py         # def register(host)
  lib/              # Tùy chọn: các thư viện phụ thuộc cài bằng pip install --target lib/
  native/           # Tùy chọn: thư viện mở rộng nhị phân chia theo thư mục con nền tảng
  README.md         # Tùy chọn
```

### Ví dụ `manifest.json`

```json
{
  "id": "demo_media_plugin",
  "name": "Plugin phát media mẫu",
  "version": "1.0.0",
  "description": "Phát luồng âm thanh hoặc tệp cục bộ thông qua media_player của host",
  "api_version": 1,
  "entry": "plugin:register",
  "runtime": "python-subprocess",
  "tool_name_prefix": "demo_media.",
  "enabled_by_default": true,
  "tools": [
    { "name": "demo_media.play_url", "title": "Phát liên kết âm thanh" }
  ]
}
```

| Trường | Mô tả |
|--------|-------|
| `id` | Duy nhất toàn cục (`^[a-zA-Z0-9][a-zA-Z0-9._-]{0,63}$`), dùng cho cài đặt, cách ly dữ liệu và bật/tắt |
| `name` / `version` / `description` | Tùy chọn; hiển thị trên thẻ plugin đã cài trong 「Cài đặt tham số → Công cụ MCP」 |
| `api_version` | Không được cao hơn phiên bản API plugin mà host hỗ trợ (hiện tại là 1) |
| `min_host_version` | Tùy chọn; bỏ qua nếu phiên bản host thấp hơn mức này |
| `platforms` | Tùy chọn; khi khai báo sẽ bỏ qua nếu không khớp với OS/ARCH hiện tại |
| `python_abi` | Tùy chọn; ví dụ `cp310`, bỏ qua nếu không khớp với host |
| `entry` | Dạng `module:thuộc_tính`, mặc định là `plugin:register` |
| `runtime` | **`python-inprocess` (mặc định, cùng tiến trình)** hoặc **`python-subprocess` (khuyến nghị, tiến trình con độc lập)** |
| `call_timeout` | Tùy chọn; chỉ áp dụng cho `python-subprocess`, thời gian chờ tối đa (giây) cho một lần gọi công cụ (mặc định 60) |
| `tool_name_prefix` | Nên khai báo; tên công cụ nên bắt đầu bằng tiền tố này |
| `tools` | Tùy chọn; khai báo danh sách công cụ để trang cài đặt hiển thị ngoại tuyến tên công cụ và tiêu đề |

Các tùy chọn kiểm tra nghiêm ngặt (mặc định tắt): `ENFORCE_PREFIX`, `REQUIRE_PYTHON_ABI`, `REQUIRE_PLATFORMS`.

### Ví dụ `plugin.py` tối giản

```python
def register(host):
    @host.tool(
        name="example.hello",
        description="Chào hỏi. Tham số name là tùy chọn.",
        props=[{"name": "name", "type": "string", "default": "thế giới"}],
    )
    async def hello(args):
        name = (args or {}).get("name") or "thế giới"
        return f"Xin chào, {name}!"
```

Bạn cũng có thể dùng `host.add_tool(McpTool(...))` (cùng kiểu trong `src.mcp.tooling` như công cụ tích hợp sẵn).

## API của ứng dụng chủ (`host`)

| Phương thức | Mô tả |
|-------------|-------|
| `host.add_tool(tool)` | Đăng ký `McpTool` |
| `host.tool(name, description, props=None)` | Cú pháp decorator tiện lợi, **không ghi** vào registry toàn cục |
| `host.get(name)` | Lấy năng lực từ host theo danh sách cho phép; trả về `None` nếu chưa được cấp quyền |

### Danh sách năng lực khả dụng

| Tên năng lực | Cho phép mặc định | Mô tả |
|--------------|-------------------|-------|
| `logger` | Có | Bộ ghi log (trong chế độ subprocess sẽ xuất ra kênh log của host) |
| `config_readonly` | Có | Bản chụp cấu hình chỉ đọc đệ quy đã ẩn thông tin nhạy cảm (chỉ gồm các trường công khai, không có phương thức ghi) |
| `data_dir` | Có | Thư mục `Path` cách ly có thể ghi dành riêng cho plugin (`{dữ_liệu_người_dùng}/mcp_plugins_data/<id>/`), được tạo lười (lazy) ở lần đầu gọi `host.get("data_dir")`; cập nhật hoặc ghi đè mã plugin không làm mất dữ liệu |
| `media_player` | Không (cần người dùng cấp quyền) | Handle `MediaPlayerFacade` có kiểm soát, hỗ trợ cả hai chế độ `inprocess` và `subprocess` |

> Đặt tường minh `MCP_PLUGINS.ALLOW_HOST_GET` thành `[]` sẽ vô hiệu hóa toàn bộ năng lực từ host.

`config_readonly` chỉ công khai các trường sau (URL đã bị loại bỏ thông tin người dùng, chuỗi truy vấn và fragment; mọi thông tin xác thực / API Key khác đều ẩn hoàn toàn):

- `CONFIG_VERSION`
- `SYSTEM_OPTIONS.WINDOW_SIZE_MODE`
- `SYSTEM_OPTIONS.NETWORK.OTA_VERSION_URL`
- `SYSTEM_OPTIONS.NETWORK.AUTHORIZATION_URL`
- `SYSTEM_OPTIONS.NETWORK.ACTIVATION_VERSION`

**Cấm** phụ thuộc vào decorator toàn cục `@mcp_tool` hoặc singleton `get_instance` đã bị gỡ bỏ.

## Phát triển plugin âm thanh / media (`media_player`)

Ứng dụng chính đã loại bỏ các nguồn nhạc tích hợp dễ hỏng và chuyển sang cung cấp **nền tảng âm thanh dùng chung không phụ thuộc nguồn phát** (dựa trên `AudioMixer` + `AudioDecoder` + `MediaPlayer`). Các plugin âm nhạc, radio, podcast, sách nói, tiếng ồn trắng... chỉ cần đảm nhận việc “tìm nguồn / lấy liên kết trực tiếp hoặc tệp cục bộ”, còn phần phát lại giao hoàn toàn cho `host.get("media_player")`:

- **Tự động hưởng hạ tầng âm thanh của host**: triệt vọng AEC, tự động giảm âm lượng (ducking) khi TTS nói (chế độ song song) hoặc tạm dừng rồi phát tiếp sau khi nói xong (chế độ bán song công), bộ giải mã FFmpeg tích hợp, chuyển nóng thiết bị Bluetooth/card âm thanh ngoài, hiển thị thanh `mediaLine` ở đáy giao diện chính.
- **Không cần đăng ký lặp lại các công cụ điều khiển phát chung**: khi người dùng bật 「Cho phép plugin sử dụng trình phát trong ứng dụng」 và có ít nhất 1 plugin mở rộng được tải thành công, host sẽ tự động đăng ký bộ công cụ duy nhất toàn cục gồm `media.pause`, `media.resume`, `media.stop`, `media.seek`, `media.get_status`, tránh xung đột giữa nhiều plugin âm thanh. Plugin chỉ cần đăng ký các công cụ đặc thù của riêng mình (như “tìm và phát”, “bài tiếp theo”, “quản lý danh sách phát”).
- **Bảo vệ vòng đời và an toàn**: mỗi plugin giữ một handle `MediaPlayerFacade` độc lập; khi plugin bị gỡ cài đặt, handle mất hiệu lực ngay lập tức và luồng âm thanh thuộc plugin đó sẽ tự động dừng phát.

### Tham chiếu phương thức `media_player`

| Phương thức | Mô tả |
|-------------|-------|
| `await player.play_url(url, *, title="", start_position=0.0, headers=None)` | Phát luồng âm thanh `http/https` hoặc **đường dẫn tuyệt đối** đến tệp cục bộ |
| `await player.pause()` | Tạm dừng phát hiện tại theo thao tác thủ công |
| `await player.resume()` | Tiếp tục phát |
| `await player.stop()` | Dừng phát |
| `await player.seek(*, position=None, percent=None)` | Tua theo số giây hoặc phần trăm (`0~100`) |
| `await player.get_status()` | Trả về từ điển có cấu trúc (`status` / `state` / `title` / `position` / `duration` / `progress` / `owner_id` / `message`) |
| `await player.set_subtitle(text)` | Cập nhật dòng phụ đề hoặc lời bài hát trên `mediaLine` của giao diện chính |

**Ràng buộc an toàn đầu vào:**

- `url` chỉ chấp nhận địa chỉ `http://` / `https://` hợp lệ hoặc **đường dẫn tuyệt đối đến tệp cục bộ đã tồn tại** (ví dụ: sau khi giải mã/lưu đệm âm thanh vào `data_dir`, truyền `str(data_dir / "track.mp3")`); từ chối đường dẫn tương đối và các giao thức không hợp lệ như `file:` / `pipe:` / `concat:`.
- `headers` chỉ cho phép theo danh sách whitelist gồm `User-Agent`, `Referer`, `Origin`, `Cookie`, `Authorization`, `Accept`, `Accept-Language`, `Range`, đồng thời chặn tấn công chèn CRLF.

### Ví dụ hoàn chỉnh cho plugin âm thanh

Mẫu hoàn chỉnh có sẵn trong kho mã nguồn tại `examples/mcp_plugins/demo_media_plugin/`:

```python
import json
from pathlib import Path

def register(host):
    player = host.get("media_player")
    data_dir = host.get("data_dir")

    @host.tool(
        "demo_media.play_url",
        "Phát liên kết trực tiếp HTTP(S) hoặc đường dẫn tuyệt đối tệp âm thanh cục bộ qua trình phát trong ứng dụng của host.",
        [
            {"name": "url", "type": "string"},
            {"name": "title", "type": "string", "default": ""},
        ],
    )
    async def play_url(args):
        if player is None:
            return json.dumps(
                {
                    "status": "error",
                    "message": "Vui lòng bật 「Cho phép plugin sử dụng trình phát trong ứng dụng」 trong 「Cài đặt tham số → Công cụ MCP」.",
                },
                ensure_ascii=False,
            )
        res = await player.play_url(
            str(args.get("url") or "").strip(),
            title=str(args.get("title") or "").strip(),
            headers={"User-Agent": "py-xiaozhi-plugin/1.0"},
        )
        return json.dumps(res, ensure_ascii=False)
```

## Đóng gói sẵn phụ thuộc và phát hành theo nền tảng

### Nguyên tắc

| Loại phụ thuộc | Dùng chung 1 gói cho cả 3 nền tảng? | Cách làm |
|----------------|-------------------------------------|----------|
| Thuần Python (như `httpx`, `markdown`) | Thường có thể | Chỉ cần một thư mục `lib/` + một tệp zip |
| Có phần mở rộng native (`.so` / `.pyd` / `.dylib`) | **Không** | **Xây dựng riêng và phát hành riêng theo từng OS + kiến trúc** |
| SDK môi trường hệ thống / robot (ROS2, `rclpy`, SDK của hãng) | **Thường không thể nhét vào `lib/`** | Xem mục 「Phụ thuộc môi trường」 bên dưới |

### Quy ước đặt tên phát hành khuyến nghị (phù hợp nhất khi có thư viện native)

```text
com.example.foo-1.0.0-macos-arm64.zip
com.example.foo-1.0.0-windows-amd64.zip
com.example.foo-1.0.0-linux-x86_64.zip
```

Mỗi tệp zip chứa đầy đủ thư mục plugin; `manifest.platforms` nên chỉ ghi nền tảng tương ứng, và `python_abi` khớp với Python của host dùng khi build (ví dụ `cp310`).

### Lệnh xây dựng (dành cho nhà phát triển)

Trên **nền tảng đích**, với **cùng phiên bản nhỏ (minor version) Python** của host:

```bash
# Bên trong thư mục plugin
uv pip install -r requirements.txt --target lib/ --python /path/to/host/python
# Hoặc: python -m pip install -r requirements.txt -t lib/
```

- Sử dụng `--target lib/` / `-t lib/`, **không** `pip install` vào môi trường của ứng dụng chính.
- Các gói chứa thành phần nhị phân bắt buộc phải chạy lệnh trên tại máy hoặc CI có đúng OS/ARCH đích.
- Khi nén zip hãy đóng gói cả thư mục (bao gồm `lib/`); trình nhập sẽ tự động bóc lớp thư mục gốc đơn lẻ, đồng thời kiểm tra chống path traversal và symlink.

### Phụ thuộc môi trường (ROS2 / Unitree Python SDK, v.v.)

Các phụ thuộc dạng này thường được cài sẵn trong môi trường hệ thống của robot (ví dụ `source /opt/ros/humble/setup.bash`) và rất khó vendor trọn vẹn vào `lib/`. Khuyến nghị:

- Nêu rõ yêu cầu môi trường hệ thống và nền tảng đích trong `README` (như `linux-aarch64`);
- `lib/` chỉ đóng gói các thư viện thuần Python có thể di chuyển được;
- Đưa ra hướng dẫn rõ ràng khi `import` SDK hệ thống thất bại.

## Runtime: `python-inprocess` và `python-subprocess`

Khi không khai báo `runtime`, mặc định là `python-inprocess`; **các plugin có thư viện bên thứ ba hoặc tác vụ mạng IO (đặc biệt là âm thanh / crawler) được khuyến nghị khai báo tường minh `python-subprocess`**.

| | `python-inprocess` (mặc định) | `python-subprocess` (khuyến nghị) |
|--|-------------------------------|-----------------------------------|
| Tiến trình | Cùng tiến trình với host | Tiến trình worker độc lập (giao thức JSON từng dòng hai chiều qua stdin/stdout) |
| Cách ly sự cố / treo | Kém (có thể làm sập cả host) | Tốt hơn (có thể chấm dứt tiến trình con khi một lần gọi vượt quá timeout) |
| `host.get("logger")` | Logger của host | Logger cục bộ trong subprocess (`stderr` được gom vào log của host) |
| `host.get("config_readonly")` | Bản chụp chỉ đọc đã ẩn thông tin nhạy cảm | Giao diện chỉ đọc tương tự (dựng từ bản chụp JSON đã ẩn thông tin nhạy cảm) |
| `host.get("data_dir")` | `Path` tạo lười (lazy) | **Hỗ trợ đầy đủ** (lấy `Path` theo kiểu lazy qua RPC `host_call`) |
| `host.get("media_player")` | `MediaPlayerFacade` có kiểm soát | **Hỗ trợ đầy đủ** (ủy quyền qua RPC `host_call` hai chiều, API giống 100%) |
| Phù hợp với | Plugin cực nhẹ, hoàn toàn đáng tin cậy | Thư viện bên thứ ba, âm thanh / trình thu thập mạng, plugin cần cách ly rủi ro |

Ví dụ trong kho mã nguồn:

```text
examples/mcp_plugins/com.example.hello/          # inprocess
examples/mcp_plugins/com.example.hello_sub/      # subprocess
examples/mcp_plugins/demo_media_plugin/          # subprocess + media_player + data_dir
```

Lưu ý: cách ly bằng tiến trình con **không phải** sandbox cấp hệ điều hành, tiến trình vẫn chạy với cùng quyền người dùng trên máy cục bộ; cơ chế này chỉ cách ly trình thông dịch, đường dẫn thư viện phụ thuộc và không gian bộ nhớ.

## Cài đặt và quản lý cho người dùng (Trang cài đặt)

Mục **Cài đặt tham số → Công cụ MCP** trong ứng dụng đã tích hợp đầy đủ khả năng quản lý plugin:

1. **Nhập ZIP / Nhập thư mục**: nhấp vào 「Nhập ZIP」 hoặc 「Nhập thư mục」 ở phía trên; host sẽ giải nén/sao chép an toàn, kiểm tra `manifest.json` (tự động sao lưu khi ghi đè cùng ID và hoàn tác nếu lỗi) rồi tải nóng ngay lập tức.
2. **Bật quyền phát trong ứng dụng**: nếu dùng plugin âm thanh, bật công tắc 「**Cho phép plugin sử dụng trình phát trong ứng dụng**」 và lưu lại.
3. **Xem và gỡ cài đặt**: thẻ hiển thị tên, phiên bản, `runtime` và lỗi tải (nếu có) của các plugin đã cài; nhấp 「Gỡ cài đặt」 sẽ tự động dừng media thuộc plugin đó, gỡ bỏ công cụ, kết thúc tiến trình con và xóa thư mục mã plugin (thư mục dữ liệu cách ly `mcp_plugins_data/<id>/` được giữ lại theo mặc định).
4. **Mở thư mục / Làm mới**: mở nhanh thư mục `mcp_plugins` hoặc kích hoạt quét lại thủ công.

## Bật/tắt theo từng công cụ (`MCP_TOOLS`)

Bên dưới mục **Cài đặt tham số → Công cụ MCP**, bạn có thể bật/tắt trạng thái công khai theo nhóm hoặc từng công cụ riêng lẻ:

- Khóa cấu hình: `MCP_TOOLS.DISABLED` (danh sách chặn theo tên đầy đủ của công cụ; mặc định `[]` là bật tất cả).
- Danh mục công cụ tích hợp sẵn được quét từ `src/mcp/tools/*/register.py` (nhóm = tên thư mục, ví dụ `media` / `app` / `camera`).
- **Sau khi tắt**: công cụ sẽ không xuất hiện trong `tools/list` của MCP và lệnh `tools/call` cũng bị từ chối.
- **Sau khi lưu**: nếu đang kết nối máy chủ, ứng dụng sẽ tự động ngắt và kết nối lại để làm mới danh sách công cụ (giữ trạng thái nhàn rỗi sau khi kết nối lại).

Khác biệt với `MCP_PLUGINS.DISABLED_IDS`: khóa này là **không tải cả gói plugin**; còn `MCP_TOOLS.DISABLED` là **thu gọn bề mặt công khai** của các công cụ đã đăng ký.

## Kiểm tra dành cho nhà phát triển

```bash
python scripts/check_mcp_plugin.py /path/to/demo_media_plugin
python scripts/check_mcp_plugin.py /path/to/plugin --strict
```

Tùy chọn `--strict` yêu cầu khai báo đủ `api_version`, `python_abi`, `platforms`, `tool_name_prefix`.

## Đặt tên, xung đột và vòng đời

- Tên công cụ nên sử dụng tiền tố `manifest.tool_name_prefix` (ví dụ `demo_media.`).
- Khi **trùng tên với công cụ đã tồn tại**, host sẽ từ chối toàn bộ lô đăng ký của plugin đó và giữ nguyên quyền sở hữu của công cụ ban đầu; sau khi cửa sổ đăng ký đóng lại, không thể dùng đối tượng `host` đã lưu đệm để đăng ký thêm công cụ mới.
- Khi gỡ cài đặt, tải lại hoặc thoát ứng dụng, host sẽ gọi `revoke` token vòng đời của plugin trước (làm mất hiệu lực toàn bộ handle năng lực được cấp và tự động dừng luồng media thuộc sở hữu của plugin), sau đó mới gỡ công cụ và kết thúc tiến trình worker.
- Giao thức JSON của tiến trình con sử dụng UTF-8; lệnh `print`/stdout của plugin được chuyển hướng sang kênh log để không làm hỏng luồng giao thức.

## API runtime (phía chương trình)

| API | Mô tả |
|-----|-------|
| Tải khi khởi động | `McpPlugin.setup` gọi `server.register_builtin_tools()` và `server.reload_external_plugins(media_player=...)` |
| `server.unload_plugin(plugin_id)` | Thu hồi vòng đời plugin, dừng media thuộc plugin, gỡ công cụ, kết thúc tiến trình con và đồng bộ lại các công cụ `media.*` có điều kiện |
| `server.reload_external_plugins(media_player=...)` | Gỡ toàn bộ plugin mở rộng, quét lại theo cấu hình và đồng bộ các công cụ điều khiển phát chung của host theo điều kiện cấp quyền |

## Lưu ý bảo mật

- **`python-inprocess`**: chạy cùng tiến trình ứng dụng chính, quyền hạn tương đương mã tùy ý trên máy cục bộ.
- **`python-subprocess`**: logic công cụ chạy trong tiến trình con độc lập, cách ly lỗi và thư viện phụ thuộc tốt hơn, nhưng vẫn có quyền của cùng người dùng cục bộ và **không phải** sandbox bảo mật.
- Chỉ cài đặt plugin từ **nguồn đáng tin cậy**; `media_player` mặc định tắt và chỉ bật khi cần; có thể đặt `MCP_PLUGINS.ENABLED=false` để tắt toàn bộ plugin mở rộng cùng lúc.

## Tài liệu liên quan

- [Hướng dẫn phát triển công cụ MCP tích hợp sẵn](./index.md)
- Thư mục ví dụ: `examples/mcp_plugins/` (gồm `demo_media_plugin`)
- Triển khai: `src/mcp/plugins/` (`host.py`, `media_facade.py`, `installer.py`, `loader.py`, `registry.py`, `subprocess_runtime.py`, `subprocess_worker.py`) và `src/media/`
