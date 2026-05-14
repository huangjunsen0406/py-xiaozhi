# 迁移 volume_controller 到 system 工具模块

## Goal

将 `src/utils/volume_controller.py` 迁移到 `src/mcp/tools/system/volume_controller.py`，因为它只被 system 工具的 `tools.py` 调用，逻辑上属于 system 模块而非通用工具。同时简化 `tools.py` 中每次调用都重复的 lazy import + check_dependencies + 重新实例化的冗余逻辑。

## Requirements

- 将 `src/utils/volume_controller.py` 移动到 `src/mcp/tools/system/volume_controller.py`
- 更新 `src/mcp/tools/system/tools.py` 中的 import 路径
- 确认无其他文件 import 旧路径（grep 已确认只有 tools.py）
- 删除 `src/utils/volume_controller.py`
- 简化 tools.py：VolumeController 改为模块级单例，不再每次调用都重新实例化
- 清理 typing imports（接触到的文件迁移到现代语法）

## Acceptance Criteria

- [ ] `src/utils/volume_controller.py` 已删除
- [ ] `src/mcp/tools/system/volume_controller.py` 存在且内容正确
- [ ] `tools.py` import 路径指向新位置
- [ ] 零残留的旧路径 import
- [ ] py_compile 通过
- [ ] 3 个音量 MCP 工具的名称、参数、返回格式不变

## Out of Scope

- VolumeController 内部逻辑重构
- 新增测试
