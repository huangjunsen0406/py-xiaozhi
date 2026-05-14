# 删除 bazi 模块 + 拆分 system 为 volume 和 app

## Goal

删除 bazi 模块（将用外挂 MCP 替代），拆分 system 为独立的 volume 和 app 两个工具包，扁平化目录结构。

## Requirements

### Phase 1: 删除 bazi
- 删除 `src/mcp/tools/bazi/` 整个目录（10 个文件，5461 行）
- 确认无外部引用

### Phase 2: 拆分 system → volume + app
- `src/mcp/tools/volume/` — 3 个音量工具 + VolumeController
- `src/mcp/tools/app/` — 4 个应用管理工具 + process_manager + launcher + scanner
- 平台 launcher/scanner 代码内联到单文件（if sys.platform 分支）
- 删除 `src/mcp/tools/system/` 整个目录
- 7 个 MCP 工具名称、参数、返回格式完全不变

## Acceptance Criteria

- [ ] `src/mcp/tools/bazi/` 不存在
- [ ] `src/mcp/tools/system/` 不存在
- [ ] `src/mcp/tools/volume/` 存在，3 个音量工具正常注册
- [ ] `src/mcp/tools/app/` 存在，4 个应用工具正常注册
- [ ] 所有文件 py_compile 通过
- [ ] 零外部代码引用旧路径
