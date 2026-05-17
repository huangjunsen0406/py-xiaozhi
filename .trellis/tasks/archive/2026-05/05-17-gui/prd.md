# GUI 切换自动对话按钮文案不同步修复

## Goal

QML 主窗口中"自动对话/手动对话"模式切换后，操作按钮文案没有跟着变化（切到自动模式后仍显示"按住说话"，应显示"开始对话"）。修复该 bug，并顺手消除按钮文案在三处常量之间的不一致（"按住说话" vs "按住后说话"）。

## What I already know

- `src/ui/gui/qml/windows/MainWindow.qml:128-177` 中有两个互斥按钮：
  - `manualBtn`（visible: `!autoMode`），fallback 文本 `"按住后说话"`
  - `autoBtn`（visible: `autoMode`），fallback 文本 `"开始对话"`
  - 两者实际显示的都是 `mainModel.buttonText`
- `src/ui/shared/models/main_model.py:28` 初始化 `_button_text = "按住说话"`，所以 QML 的 fallback **永远走不到**
- `MainModel.set_auto_mode()` (`main_model.py:84-89`) 切换模式时只更新 `_auto_mode` 和 `_mode_text`，**没有同步刷新 `_button_text`**，这是根因
- `src/plugins/ui.py:125,212` 在录音结束/状态重置时把按钮文本设回 `"按住后说话"`（多了"后"字，与 model 初始值不一致）
- GUI 手动按钮是 `onClicked → onManualToggle`（点击切换），不是真正的"按住"，所以"按住后说话"作为提示也不准确，但本任务不修文案语义，只修一致性

## Requirements

1. 切换自动对话模式后，按钮文案立刻刷新：
   - 自动模式 → `"开始对话"`
   - 手动模式 → `"按住后说话"`
2. 统一 `MainModel._button_text` 初始值为 `"按住后说话"`，与 `plugins/ui.py` 中重置逻辑一致
3. 不改动 `plugins/ui.py` 中"发送"态（录音中）的文本切换语义

## Acceptance Criteria

- [ ] 启动 GUI，默认在手动模式，按钮显示 `"按住后说话"`
- [ ] 点击"切换到自动"后，按钮立刻变为 `"开始对话"`
- [ ] 点击"切换回手动"后，按钮立刻变回 `"按住后说话"`
- [ ] 手动模式下点击按钮开始录音，文本变为 `"发送"`；再次点击停止录音，文本回到 `"按住后说话"`（既有逻辑不破坏）

## Definition of Done

- 改动通过本地 lint / typecheck
- GUI 启动后人工 QA 三种切换路径（启动 → 自动 → 手动 → 录音 → 停止）

## Out of Scope

- 不改 QML 两个按钮的 fallback 文本本身（保持现状）
- 不重命名"按住后说话"为更准确的"点击说话"（涉及 UX 语义，超出本次范围）
- 不重构两按钮共享 `buttonText` 的结构

## Technical Approach

修改 `src/ui/shared/models/main_model.py`：

1. 第 28 行 `self._button_text = "按住说话"` → `self._button_text = "按住后说话"`
2. `set_auto_mode` 方法体内，模式实际变化时同步设置 `_button_text` 并 emit `buttonTextChanged`：
   ```python
   def set_auto_mode(self, auto: bool):
       if self._auto_mode != auto:
           self._auto_mode = auto
           self._mode_text = "自动对话" if auto else "手动对话"
           self._button_text = "开始对话" if auto else "按住后说话"
           self.autoModeChanged.emit()
           self.modeTextChanged.emit()
           self.buttonTextChanged.emit()
   ```

## Technical Notes

- `MainWindow.qml:134,160` 两按钮都绑定到同一个 `mainModel.buttonText`，所以只需在 model 侧保证 buttonText 跟着 autoMode 走
- `_auto_toggle` (`plugins/ui.py:216-234`) 只调 `set_auto_mode`，不会重复 emit
- 录音态文本（`"发送"`）由 `_manual_toggle` 显式 set，不受 `set_auto_mode` 影响
