# 参与贡献

英文版本请查看 [CONTRIBUTING.md](./CONTRIBUTING.md)。

感谢你为 `py-xiaozhi` 做出贡献。我们欢迎 Bug 反馈、文档修复、测试补充、工具链改进，以及范围清晰的新功能。

## 开始之前

- 提交前先搜索现有的 Issue 和 Pull Request，避免重复。
- 对于较大的新功能、架构调整或行为变更，建议先开 Issue 讨论。
- 文档修复、小型 Bug 修复和聚焦明确的改进，一般可以直接提交 Pull Request。

## 开发环境

### 基本要求

- Python `>=3.10`
- Git
- 如果需要验证音频能力，请准备可用的麦克风和扬声器

### 安装依赖

```bash
git clone https://github.com/huangjunsen0406/py-xiaozhi.git
cd py-xiaozhi

# 基础安装
uv sync

# GUI + 开发工具
uv sync --extra gui --group dev
```

如果你不使用 `uv`，可以使用以下兼容方案：

```bash
pip install -e .
pip install -e '.[gui]'
pip install pytest pytest-asyncio ruff pyinstaller
```

## 开发流程

1. Fork 仓库，并从 `main` 创建功能分支。
2. 尽量让每次修改只聚焦一个问题、一个功能或一类文档更新。
3. 提交信息遵循 Conventional Commits，例如 `fix(audio): handle empty frame`。
4. 如果修改影响行为、配置或公共接口，请同步更新文档。
5. 如果修改涉及正确性或回归风险，请补充或更新测试。

推荐分支命名：

- `feature/xxx`
- `fix/xxx`
- `docs/xxx`
- `refactor/xxx`
- `test/xxx`

## 质量要求

提交 Pull Request 前，请根据改动类型运行相应检查：

```bash
ruff check .
ruff format .
pytest
```

如有必要，也请验证对应运行路径，例如：

- GUI 改动：运行 `python main.py`
- CLI 改动：运行 `python main.py --mode cli`
- 协议改动：验证 `websocket` 或 `mqtt`
- 文档改动：在 `documents/` 下本地预览

## Pull Request 要求

每个 Pull Request 都应尽量满足以下要求：

- 清楚说明问题背景和解决方案。
- 如有相关 Issue，请附上关联链接。
- 提供必要的验证步骤、截图或日志，方便审核。
- 保持改动范围合理，避免混入无关重构。
- 遵循现有代码风格和项目结构。

## Maintainer Workflow

维护者通常会按以下流程审核贡献：

1. 先将改动归类为 `bug`、`feature`、`docs`、`refactor` 或 `maintenance`。
2. 确认改动范围是否清晰、问题是否可复现、方向是否符合项目规划。
3. 检查测试、文档和验证证据，再决定是否提出修改意见或批准。
4. 在 CI 通过且反馈处理完成后合并。
5. 合并后按正常发布流程进入后续版本，合并不等于立即发布。

## 详细文档

- 项目文档：<https://huangjunsen0406.github.io/py-xiaozhi/>
- 详细贡献指南（英文）：<https://huangjunsen0406.github.io/py-xiaozhi/en/contributing>
- 详细贡献指南（中文）：<https://huangjunsen0406.github.io/py-xiaozhi/contributing>

再次感谢你的贡献。
