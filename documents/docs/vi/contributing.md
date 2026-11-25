---
title: Hướng dẫn đóng góp
description: Cách đóng góp mã nguồn và tài liệu cho dự án py-xiaozhi
sidebar: false
outline: deep
---

<div class="contributing-page">

# Hướng dẫn đóng góp

<div class="header-content">
  <h2>Cách đóng góp mã nguồn cho dự án py-xiaozhi 🚀</h2>
</div>

## Lời mở đầu

Cảm ơn bạn đã quan tâm đến dự án **py-xiaozhi**! Chúng tôi rất hoan nghênh mọi đóng góp từ cộng đồng, dù là sửa lỗi, cải thiện tài liệu hay phát triển tính năng mới. Hướng dẫn này trình bày quy trình chuẩn để gửi đóng góp cho dự án.

## Chuẩn bị môi trường phát triển

### Yêu cầu cơ bản

- Python 3.10 trở lên
- Hệ thống quản lý phiên bản Git
- Trình soạn thảo Python cơ bản (khuyến nghị Visual Studio Code)

### Lấy mã nguồn

1. Trước tiên, Fork dự án trên GitHub về tài khoản của bạn:
   - Truy cập [trang dự án py-xiaozhi](https://github.com/huangjunsen0406/py-xiaozhi)
   - Nhấn nút **Fork** ở góc trên bên phải
   - Chờ quá trình Fork hoàn tất, bạn sẽ được chuyển sang bản sao kho mã nguồn của mình

2. Clone kho mã nguồn đã fork về máy cục bộ:

```bash
git clone https://github.com/YOUR_USERNAME/py-xiaozhi.git
cd py-xiaozhi
```

3. Thêm kho mã nguồn gốc (`upstream`):

```bash
git remote add upstream https://github.com/huangjunsen0406/py-xiaozhi.git
```

Bạn có thể kiểm tra cấu hình remote bằng lệnh `git remote -v`:

```bash
git remote -v
# Kết quả mong đợi:
# origin    https://github.com/YOUR_USERNAME/py-xiaozhi.git (fetch)
# origin    https://github.com/YOUR_USERNAME/py-xiaozhi.git (push)
# upstream  https://github.com/huangjunsen0406/py-xiaozhi.git (fetch)
# upstream  https://github.com/huangjunsen0406/py-xiaozhi.git (push)
```

### Cài đặt phụ thuộc phát triển

- Các phụ thuộc hệ thống khác vui lòng xem thêm trong mục **Hướng dẫn**.

```bash
# Tạo và kích hoạt môi trường ảo (khuyến nghị)
python -m venv .venv
source .venv/bin/activate  # Trên Windows dùng: .venv\Scripts\activate

# Cài đặt GUI, TUI và bộ công cụ phát triển (khuyến nghị dùng uv)
uv sync --extra gui --extra tui --group dev

# Hoặc dùng pip trong môi trường ảo vừa tạo
# pip install -e '.[gui,tui]'
# pip install pytest pytest-asyncio ruff pyinstaller
```

## Quy trình phát triển

### Đồng bộ với kho gốc

Trước khi bắt đầu công việc mới, hãy luôn đồng bộ nhánh cục bộ với kho gốc:

1. Chuyển sang nhánh chính (`main`):

```bash
git checkout main
```

2. Lấy các thay đổi mới nhất từ `upstream`:

```bash
git fetch upstream
```

3. Gộp nhánh `upstream/main` vào nhánh `main` cục bộ:

```bash
git merge upstream/main
```

4. Đẩy nhánh `main` đã cập nhật lên GitHub của bạn:

```bash
git push origin main
```

### Tạo nhánh làm việc

Hãy tạo nhánh mới từ `upstream/main` mới nhất trước khi chỉnh sửa:

```bash
# Cập nhật mã nguồn gốc
git fetch upstream
git checkout -b feature/your-feature-name upstream/main
```

Quy ước đặt tên nhánh:

- `feature/xxx`: phát triển tính năng mới
- `fix/xxx`: sửa lỗi
- `docs/xxx`: cập nhật tài liệu
- `test/xxx`: bổ sung hoặc chỉnh sửa kiểm thử
- `refactor/xxx`: tái cấu trúc mã nguồn

### Quy chuẩn mã nguồn

Dự án tuân theo [PEP 8](https://www.python.org/dev/peps/pep-0008/) cho mã Python. Trước khi gửi PR, hãy đảm bảo:

- Dùng 4 dấu cách để thụt lề
- Độ dài dòng hợp lý (khuyến nghị kiểm tra bằng `ruff`)
- Đặt tên biến và hàm rõ ràng, có ý nghĩa
- Viết docstring cho các API công khai
- Sử dụng gợi ý kiểu (`Type Hints`)

Khuyến nghị chạy công cụ kiểm tra tĩnh trước khi commit:

```bash
# Kiểm tra phong cách và lỗi cú pháp bằng ruff
ruff check main.py src scripts tests

# Chạy bộ kiểm thử tự động
pytest -q -W error::RuntimeWarning
```

### Kiểm thử

Đảm bảo tất cả các bài kiểm thử hiện có đều vượt qua và bổ sung kiểm thử mới cho thay đổi của bạn.

## Gửi thay đổi

### Danh sách kiểm tra trước khi commit

1. Mã nguồn tuân thủ PEP 8 và vượt qua `ruff check`
2. Đã bổ sung kiểm thử cần thiết
3. Toàn bộ bộ kiểm thử đều vượt qua
4. Đã cập nhật tài liệu liên quan (nếu thay đổi hành vi, cấu hình hoặc API)
5. Đã giải quyết đúng vấn đề đặt ra
6. Đã đồng bộ với mã nguồn `upstream/main` mới nhất

### Commit thay đổi

Nên chia thành các commit nhỏ, gọn và rõ mục đích:

```bash
# Xem trạng thái tệp đã sửa
git status

# Thêm tệp vào staging
git add file1.py file2.py

# Tạo commit
git commit -m "feat: add new feature X"
```

### Xử lý xung đột (Conflict)

Nếu gặp xung đột khi đồng bộ từ kho gốc:

1. Kiểm tra các tệp bị xung đột:

```bash
git status
```

2. Mở tệp xung đột, bạn sẽ thấy các đánh dấu như sau:

```
<<<<<<< HEAD
Mã nguồn của bạn
=======
Mã nguồn từ upstream
>>>>>>> upstream/main
```

3. Chỉnh sửa lại nội dung hợp lệ và xóa toàn bộ dấu xung đột
4. Thêm lại tệp đã xử lý và commit:

```bash
git add .
git commit -m "fix: resolve merge conflicts"
```

### Quy ước thông điệp Commit

Chúng tôi áp dụng chuẩn [Conventional Commits](https://www.conventionalcommits.org/) theo định dạng:

```
<loại>[phạm vi tùy chọn]: <mô tả>

[nội dung chi tiết tùy chọn]

[chú thích cuối tùy chọn]
```

Các loại commit phổ biến:

- `feat`: tính năng mới
- `fix`: sửa lỗi
- `docs`: cập nhật tài liệu
- `style`: định dạng mã (không đổi logic)
- `refactor`: tái cấu trúc mã nguồn (không thêm tính năng hay sửa lỗi)
- `perf`: tối ưu hiệu năng
- `test`: thêm hoặc sửa kiểm thử
- `chore`: cập nhật quy trình build, công cụ phụ trợ hoặc phụ thuộc

Ví dụ:

```
feat(tts): add new speech synthesis engine support

Add support for Baidu TTS API, including:
- Multiple voice presets
- Speed and volume adjustment
- Mixed Chinese-English synthesis

Fixes #123
```

### Đẩy nhánh lên GitHub

```bash
git push origin feature/your-feature-name
```

Nếu bạn đã mở Pull Request và cần bổ sung chỉnh sửa, chỉ cần commit và đẩy tiếp lên cùng nhánh:

```bash
git add .
git commit -m "refactor: improve code based on feedback"
git push origin feature/your-feature-name
```

### Đồng bộ mới nhất trước khi tạo Pull Request

```bash
# Lấy mã nguồn mới nhất từ upstream
git fetch upstream

# Rebase nhánh tính năng lên upstream/main
git rebase upstream/main

# Nếu có xung đột, sửa xong rồi chạy:
git add .
git rebase --continue

# Đẩy lại nhánh đã rebase một cách an toàn
git push --force-with-lease origin feature/your-feature-name
```

Lưu ý: `--force-with-lease` an toàn hơn `--force` vì tránh ghi đè nhầm thay đổi của người khác.

### Tạo Pull Request

1. Đẩy nhánh của bạn lên GitHub:

```bash
git push origin feature/your-feature-name
```

2. Mở trang kho fork của bạn trên GitHub và nhấn **Compare & pull request**
3. Điền đầy đủ biểu mẫu Pull Request:
   - Tiêu đề rõ ràng theo quy ước commit
   - Mô tả chi tiết mục đích thay đổi và cách kiểm thử
   - Liên kết issue liên quan (ví dụ `#123`)
   - Nếu đang phát triển dở, thêm tiền tố `[WIP]` vào tiêu đề
4. Gửi Pull Request và chờ nhóm duy trì xem xét

### Vòng đời của Pull Request

1. **Tạo PR**: gửi yêu cầu gộp mã
2. **Kiểm tra CI**: tự động chạy lint, pytest và kiểm tra đóng gói wheel
3. **Review mã nguồn**: người duy trì xem xét và để lại nhận xét
4. **Chỉnh sửa**: cập nhật mã nguồn theo góp ý
5. **Phê duyệt**: PR đạt yêu cầu và được duyệt
6. **Gộp nhánh (Merge)**: PR được gộp vào nhánh chính

## Đóng góp tài liệu

Nếu bạn muốn cải thiện hoặc bổ sung tài liệu dự án:

1. Fork và clone dự án như hướng dẫn ở trên
2. Tài liệu nằm trong thư mục `documents/docs` ở định dạng Markdown (`/` cho tiếng Anh, `/zh/` cho tiếng Trung, `/vi/` cho tiếng Việt)
3. Cài đặt phụ thuộc của trang tài liệu:

```bash
cd documents
pnpm install
```

4. Khởi chạy máy chủ xem trước cục bộ:

```bash
pnpm docs:dev
```

5. Mở trình duyệt tại `http://localhost:5173/py-xiaozhi/vi/` để xem trước thay đổi
6. Commit thay đổi và tạo Pull Request

### Nguyên tắc viết tài liệu

- Ngôn ngữ rõ ràng, súc tích, dễ hiểu
- Đính kèm ví dụ lệnh hoặc cấu hình thực tế
- Giải thích rõ các khái niệm phức tạp
- Bổ sung ảnh chụp màn hình hoặc sơ đồ khi cần thiết
- Giữ cấu trúc tiêu đề nhất quán giữa các ngôn ngữ

## Báo cáo sự cố

Nếu phát hiện lỗi nhưng chưa thể tự sửa, vui lòng [tạo Issue trên GitHub](https://github.com/huangjunsen0406/py-xiaozhi/issues/new) kèm các thông tin sau:

- Mô tả chi tiết sự cố
- Các bước tái hiện lỗi
- Hành vi mong đợi và hành vi thực tế
- Hệ điều hành và phiên bản Python đang dùng
- Nhật ký (log) hoặc thông báo lỗi liên quan

## Xem xét mã nguồn (Code Review)

Trong quá trình xem xét Pull Request:

- Kiên nhẫn chờ phản hồi từ người duy trì
- Phản hồi kịp thời các bình luận và gợi ý
- Thực hiện chỉnh sửa và cập nhật PR khi cần
- Duy trì trao đổi lịch sự, mang tính xây dựng

### Cách phản hồi nhận xét Review

1. Đọc kỹ từng nhận xét và đề xuất
2. Phản hồi hoặc cập nhật mã cho từng điểm
3. Nếu không đồng ý với một góp ý, hãy trình bày lý do rõ ràng và lịch sự
4. Sau khi hoàn tất chỉnh sửa, bình luận trong PR để thông báo cho người duyệt

## Trở thành người duy trì dự án

Nếu bạn đóng góp bền bỉ và có giá trị cho dự án, bạn có thể được mời trở thành người duy trì (Maintainer) với quyền review và gộp Pull Request.

### Trách nhiệm của người duy trì

- Review Pull Request
- Quản lý và phân loại Issue
- Tham gia định hướng phát triển dự án
- Giải đáp thắc mắc của cộng đồng
- Hướng dẫn người đóng góp mới

## Quy tắc ứng xử

Hãy tôn trọng mọi thành viên cộng đồng và tuân thủ các nguyên tắc sau:

- Sử dụng ngôn ngữ cởi mở, thân thiện
- Tôn trọng quan điểm và kinh nghiệm khác nhau
- Tiếp nhận góp ý xây dựng với thái độ cầu thị
- Đặt lợi ích chung của cộng đồng lên hàng đầu
- Cảm thông và hỗ trợ các thành viên khác

## Câu hỏi thường gặp

### Tôi nên bắt đầu đóng góp từ đâu?

1. Xem các Issue gắn nhãn `good first issue`
2. Sửa lỗi chính tả, bổ sung ví dụ hoặc dịch tài liệu
3. Bổ sung thêm các bài kiểm thử đơn vị
4. Khắc phục những vấn đề bạn gặp trong quá trình sử dụng thực tế

### PR của tôi đã mở khá lâu chưa có phản hồi thì sao?

Hãy bình luận nhẹ nhàng trong PR để hỏi xem cần bổ sung hay làm rõ thêm thông tin gì không. Người duy trì có thể đang bận và cần thêm thời gian xem xét.

### Tôi có thể đóng góp những loại thay đổi nào?

- Sửa lỗi (`fix`)
- Tính năng mới (`feat`)
- Cải thiện hiệu năng (`perf`)
- Cập nhật tài liệu (`docs`)
- Kiểm thử (`test`)
- Tái cấu trúc mã nguồn (`refactor`)

## Lời cảm ơn

Một lần nữa cảm ơn bạn đã đồng hành và đóng góp cho **py-xiaozhi**! Sự tham gia của bạn giúp dự án ngày càng hoàn thiện hơn!

</div>

<style>
.contributing-page {
  max-width: 900px;
  margin: 0 auto;
  padding: 2rem 1.5rem;
}

.contributing-page h1 {
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

.contributing-page h2 {
  margin-top: 3rem;
  padding-top: 1rem;
  border-top: 1px solid var(--vp-c-divider);
}

.contributing-page h3 {
  margin-top: 2rem;
}

.contributing-page code {
  background-color: var(--vp-c-bg-soft);
  padding: 0.2em 0.4em;
  border-radius: 3px;
}

.contributing-page pre {
  margin: 1rem 0;
  border-radius: 8px;
  overflow: auto;
}
</style>
