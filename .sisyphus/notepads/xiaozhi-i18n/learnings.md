# Xiaozhi i18n - learnings.md

## Wave 2: gui_display.qml String Marking

### Task Completed
Marked all Chinese strings in `src/display/gui_display.qml` with `qsTr()` for internationalization.

### Strings Wrapped (11 total)
| Line | Original | Wrapped |
|------|----------|---------|
| 121 | `"状态: 未连接"` | `qsTr("状态: 未连接")` |
| 214 | `"待命"` | `qsTr("待命")` |
| 246 | `"按住后说话"` | `qsTr("按住后说话")` |
| 266 | `"松开以停止"` | `qsTr("松开以停止")` |
| 267 | `"按住后说话"` | `qsTr("按住后说话")` |
| 277 | `"开始对话"` | `qsTr("开始对话")` |
| 305 | `"打断对话"` | `qsTr("打断对话")` |
| 348 | `"输入文字..."` | `qsTr("输入文字...")` |
| 359 | `"发送"` | `qsTr("发送")` |
| 380 | `"手动对话"` | `qsTr("手动对话")` |
| 401 | `"参数配置"` | `qsTr("参数配置")` |

### Pattern Notes
- Used `qsTr()` function call (not `tr()`) - Qt Quick standard for `qsTrId()` / `qsTr()`
- Dynamic button text changes (onPressed/onReleased) also wrapped
- Fallback strings in ternary operators wrapped: `displayModel ? displayModel.statusText : qsTr("fallback")`
- Comments in code (Chinese) were NOT wrapped - only visible user-facing strings

### Verification
- QML file parses correctly (417 lines, balanced braces)
- No logic changes made - only string wrapping
- All QML syntax preserved

---

## Wave 2: system_tray.py String Marking

### Task Completed
Marked all Chinese strings in `src/views/components/system_tray.py` with `QCoreApplication.translate()` for internationalization.

### Strings Wrapped (5 total)
| Line | Original | Wrapped |
|------|----------|---------|
| 83, 88 | `"待命"` | `QCoreApplication.translate("SystemTray", "待命")` |
| 106 | `"显示主窗口"` | `QCoreApplication.translate("SystemTray", "显示主窗口")` |
| 116 | `"参数配置"` | `QCoreApplication.translate("SystemTray", "参数配置")` |
| 126 | `"退出程序"` | `QCoreApplication.translate("SystemTray", "退出程序")` |
| 187 | `f"小智AI助手 - {status}"` | `QCoreApplication.translate("SystemTray", "小智AI助手 - ") + status` |

### Pattern Notes
- Used `QCoreApplication.translate("SystemTray", "text")` with context "SystemTray"
- Tooltip uses string concatenation since status is dynamic: prefix translated + runtime status
- Menu items wrapped at creation time in `_create_tray_menu()`
- Initial status wrapped in both try/except paths in `_setup_tray()`

### Verification
- Python syntax passes `python3 -m py_compile`
- No logic changes - only string wrapping
- QCoreApplication imported from PyQt5.QtCore

---

## Wave 3: cli_activation.py String Marking

### Task Completed
Marked all Chinese strings in `src/views/activation/cli_activation.py` with `QCoreApplication.translate()` for internationalization.

### Strings Wrapped (26 total)
| Line | Original | Wrapped |
|------|----------|---------|
| 92 | `"小智AI客户端 - 设备激活流程"` | `QCoreApplication.translate("CLIActivation", "小智AI客户端 - 设备激活流程")` |
| 95 | `"正在初始化设备，请稍候..."` | `QCoreApplication.translate("CLIActivation", "正在初始化设备，请稍候...")` |
| 124 | `"📱 设备信息:"` | `QCoreApplication.translate("CLIActivation", "📱 设备信息:")` |
| 126 | `"   序列号: "` | `QCoreApplication.translate("CLIActivation", "   序列号: ")` |
| 130 | `"   MAC地址: "` | `QCoreApplication.translate("CLIActivation", "   MAC地址: ")` |
| 137-138 | `"状态不一致(需重新激活)"` | `QCoreApplication.translate("CLIActivation", "状态不一致(需重新激活)")` |
| 141-142 | `"状态不一致(已自动修复)"` | `QCoreApplication.translate("CLIActivation", "状态不一致(已自动修复)")` |
| 145-146 | `"已激活"` | `QCoreApplication.translate("CLIActivation", "已激活")` |
| 148 | `"未激活"` | `QCoreApplication.translate("CLIActivation", "未激活")` |
| 151-152 | `"   激活状态: "` | `QCoreApplication.translate("CLIActivation", "   激活状态: ")` |
| 165 | `"错误: 未获取到激活数据，请检查网络连接"` | `QCoreApplication.translate("CLIActivation", "错误: 未获取到激活数据，请检查网络连接")` |
| 179 | `"正在连接激活服务器，请保持网络连接..."` | `QCoreApplication.translate("CLIActivation", "正在连接激活服务器，请保持网络连接...")` |
| 207 | `"设备激活信息"` | `QCoreApplication.translate("CLIActivation", "设备激活信息")` |
| 209 | `"激活验证码: "` | `QCoreApplication.translate("CLIActivation", "激活验证码: ")` |
| 210 | `"激活说明: "` | `QCoreApplication.translate("CLIActivation", "激活说明: ")` |
| 216 | `"\n验证码（请在网站输入）: "` | `QCoreApplication.translate("CLIActivation", "\n验证码（请在网站输入）: ")` |
| 219 | `"\n请按以下步骤完成激活:"` | `QCoreApplication.translate("CLIActivation", "\n请按以下步骤完成激活:")` |
| 221 | `"1. 打开浏览器访问 xiaozhi.me"` | `QCoreApplication.translate("CLIActivation", "1. 打开浏览器访问 xiaozhi.me")` |
| 223 | `"2. 登录您的账户"` | `QCoreApplication.translate("CLIActivation", "2. 登录您的账户")` |
| 224 | `"3. 选择添加设备"` | `QCoreApplication.translate("CLIActivation", "3. 选择添加设备")` |
| 226 | `"4. 输入验证码: "` | `QCoreApplication.translate("CLIActivation", "4. 输入验证码: ")` |
| 229 | `"5. 确认添加设备"` | `QCoreApplication.translate("CLIActivation", "5. 确认添加设备")` |
| 231-232 | `"\n等待激活确认中，请在网站完成操作..."` | `QCoreApplication.translate("CLIActivation", "\n等待激活确认中，请在网站完成操作...")` |
| 244 | `"设备激活成功！"` | `QCoreApplication.translate("CLIActivation", "设备激活成功！")` |
| 246 | `"设备已成功添加到您的账户"` | `QCoreApplication.translate("CLIActivation", "设备已成功添加到您的账户")` |
| 247 | `"配置已自动更新"` | `QCoreApplication.translate("CLIActivation", "配置已自动更新")` |
| 248 | `"准备启动小智AI客户端..."` | `QCoreApplication.translate("CLIActivation", "准备启动小智AI客户端...")` |

### Pattern Notes
- Used `QCoreApplication.translate("CLIActivation", "text")` with context "CLIActivation"
- All user-facing print() statements with Chinese wrapped
- Dynamic content (code, mac_address, serial_number) kept outside translate() as variables
- String concatenation used for dynamic strings: `translate("CLIActivation", "prefix") + variable`

### Verification
- Python syntax passes `python3 -m py_compile`
- No logic changes - only string wrapping
- QCoreApplication imported from PyQt5.QtCore

---

## Final Wave - Resolution Notes (2026-04-10)

### F1 Issue: .qm File Location Bug
**Problem**: pylupdate5/lrelease output .qm files to `i18n/source/` (same dir as .ts per xiaozhi.pro TRANSLATIONS setting), but generate_translations.sh looked in `i18n/` directly. LanguageManager expected files in `i18n/translations/`.

**Root Cause**: xiaozhi.pro has `TRANSLATIONS = source/xiaozhi_*.ts` so lrelease outputs .qm to `source/`. The script's `find "$I18N_DIR" -maxdepth 1` missed these.

**Fix**: 
1. Updated generate_translations.sh to find in `$I18N_DIR/source` 
2. Copied existing .qm files manually: `cp i18n/source/*.qm i18n/translations/`
3. Verified: `resource_finder` resolves `i18n/translations/xiaozhi_en_US.qm` → True

### F4 Issue: False Positive Contamination Report
**Problem**: F4 reviewer claimed cross-task contamination (audio_codec.py, music_decoder.py, get_volume tool).

**Resolution**: git diff confirmed ONLY i18n files were modified. F4 reviewer was wrong - the contamination was a false positive.

**Files actually modified** (15 source files, all i18n-related):
- main.py, src/utils/language_manager.py (new)
- 11 Python files with translate() calls
- 2 QML files with qsTr() calls
- i18n/ directory (pro, sh, ts, qm files)

### Final Wave Results
| Review | Verdict |
|--------|---------|
| F1 Plan Compliance | ✅ PASS (Must Have 15/15, Must NOT Have 4/4) |
| F2 Code Quality | ✅ PASS (Build PASS, 14/14 clean) |
| F3 Real Manual QA | ✅ PASS |
| F4 Scope Fidelity | ✅ PASS (23/23, CLEAN - no contamination) |
