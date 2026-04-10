# py-xiaozhi i18n: English/Russian Localization

## TL;DR

> **Quick Summary**: Add internationalization (i18n) system to py-xiaozhi using Qt Linguist (.ts/.qm files), enabling the GUI to display in English and Russian instead of Chinese.
>
> **Deliverables**:
> - Qt Linguist translation infrastructure (.ts files, .pro file, build scripts)
> - English translations for all UI strings
> - Russian translations for all UI strings
> - Language switcher in Settings
> - Fallback chain: target_lang → en_US → zh_CN
>
> **Estimated Effort**: Medium-Large (30+ files to modify, 500+ strings to translate)
> **Parallel Execution**: YES - 4 waves
> **Critical Path**: Wave 1 (setup) → Wave 2 (infrastructure) → Wave 3 (translation) → Wave 4 (integration)

---

## Context

### Original Request
User wants to run py-xiaozhi GUI in Russian (or English) because Chinese interface is not understandable.

### Metis Review Findings

**Identified Gaps (addressed in plan)**:
1. Missing default/fallback language chain definition
2. No language switcher UX specification
3. MCP/backend strings scope not defined
4. Log messages translation not considered
5. Translation quality standards for PR not set

**Guardrails Applied**:
- MUST NOT modify LLM/API prompt templates
- MUST NOT re-translate third-party dependencies
- MUST preserve UTF-8 encoding
- MUST provide fallback chain

---

## Work Objectives

### Core Objective
Enable py-xiaozhi to display all user-facing UI strings in English and Russian using Qt Linguist i18n system.

### Concrete Deliverables
- [ ] `i18n/` directory with translation infrastructure
- [ ] `i18n/translations/` - compiled .qm files
- [ ] `i18n/source/` - .ts source files for translators
- [ ] `i18n/xiaozhi.pro` - pylupdate5 configuration
- [ ] `i18n/generate_translations.sh` - build script
- [ ] Modified `main.py` with QTranslator loading
- [ ] Modified QML files using `qsTr()`
- [ ] Modified Python files using `QCoreApplication.translate()`
- [ ] English .ts/.qm (en_US)
- [ ] Russian .ts/.qm (ru_RU)
- [ ] Language switcher in Settings UI

### Definition of Done
- [ ] `python main.py --lang=en_US` → English UI
- [ ] `python main.py --lang=ru_RU` → Russian UI
- [ ] No Chinese strings visible in English/Russian mode
- [ ] `python main.py` (no lang arg) → respects system locale or defaults to zh_CN
- [ ] `lrelease i18n/*.ts` compiles without errors
- [ ] PR passes upstream code review

### Must Have
- Qt Linguist translation workflow
- All hardcoded Chinese strings externalized to .ts files
- English translations (minimum viable)
- Russian translations (minimum viable)
- Working language switcher

### Must NOT Have (Guardrails)
- Modified LLM prompt templates (response language unchanged)
- Translated third-party dependency strings
- Changed application logic (strings only)
- New dependencies without upstream approval
- Breaking changes for existing Chinese users
- Mixed language in logs (all logs translated per Q4)

---

## Verification Strategy

### Test Decision
- **Infrastructure exists**: NO - creating new
- **Automated tests**: NO (QA via agent-executed scenarios)
- **Translation validation**: Machine-translated + manual spot-check

### QA Policy
Every task includes agent-executed QA scenarios. Evidence saved to `.sisyphus/evidence/`.

---

## Execution Strategy

### Parallel Execution Waves

```
Wave 1 (Setup & Infrastructure - 5 tasks):
├── T1: Create i18n directory structure
├── T2: Create xiaozhi.pro for pylupdate5
├── T3: Create translation build script
├── T4: Add QTranslator loading to main.py
└── T5: Create base translation files (.ts)

Wave 2 (QML + Python string marking - MAX PARALLEL - 8 tasks):
├── T6: Mark strings in gui_display.qml (qsTr)
├── T7: Mark strings in activation_window.qml (qsTr)
├── T8: Mark strings in gui_display.py (translate)
├── T9: Mark strings in gui_display_model.py (translate)
├── T10: Mark strings in cli_display.py (translate)
├── T11: Mark strings in cli_activation.py (translate)
├── T12: Mark strings in system_tray.py (translate)
└── T13: Mark strings in settings_window.py + .ui

Wave 3 (Settings UI + Components - 6 tasks):
├── T14: Mark strings in settings components .py files
├── T15: Mark strings in settings .ui files
├── T16: Add language dropdown to System Options tab
├── T17: Wire language setting to translator
├── T18: Create en_US.ts translations
└── T19: Create ru_RU.ts translations

Wave 4 (Polish + CLI - 4 tasks):
├── T20: Add CLI --lang argument support
├── T21: Verify CLI mode translations work
├── T22: Create CONTRIBUTING.md for translators
└── T23: Final integration test

Critical Path: T1 → T5 → T4 → T6-T13 → T16-T17 → T23
Parallel Speedup: ~60% faster than sequential
Max Concurrent: 8 (Wave 2)
```

---

## TODOs

- [x] 1. **Create i18n directory structure**

  **What to do**:
  - Create `i18n/` directory in project root
  - Create `i18n/translations/` for compiled .qm files
  - Create `i18n/source/` for .ts source files
  - Create `i18n/build/` for temporary build artifacts
  - Add `i18n/README.md` explaining the structure

  **Must NOT do**:
  - Do NOT add translation files yet - only infrastructure

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple directory creation, no complex logic
  - **Skills**: []
    - No specific skills needed

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 2, 3, 4, 5)
  - **Blocks**: Task 2 (needs directory to exist)
  - **Blocked By**: None

  **References**:
  - Qt Linguist documentation: `https://doc.qt.io/qt-5/linguist.html`
  - Standard Qt i18n structure used in KDE, LXQt projects

  **Acceptance Criteria**:
  - [ ] `i18n/` directory exists at project root
  - [ ] `i18n/translations/` subdirectory exists
  - [ ] `i18n/source/` subdirectory exists
  - [ ] `ls i18n/` shows all three directories

  **QA Scenarios**:

  Scenario: Directory structure created correctly
    Tool: Bash
    Preconditions: Clean git state
    Steps:
      1. `mkdir -p i18n/translations i18n/source i18n/build`
      2. `ls -la i18n/`
    Expected Result: Three directories visible
    Evidence: .sisyphus/evidence/task-1-dir-structure.txt

- [x] 2. **Create xiaozhi.pro for pylupdate5**

  **What to do**:
  - Create `i18n/xiaozhi.pro` Qt project file for pylupdate5
  - Specify source files: `*.py`, `*.qml`, `*.ui`
  - Specify translation output: `i18n/source/xiaozhi_*.ts`
  - Set source language: zh_CN (Chinese)
  - Set target languages: en_US, ru_RU

  **Must NOT do**:
  - Do NOT include third-party libs/ in translation sources
  - Do NOT include models/ or cache/ directories

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Creating configuration file with standard Qt syntax
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 3, 4, 5)
  - **Blocks**: Task 5 (needs .pro to run pylupdate5)
  - **Blocked By**: Task 1

  **References**:
  - pylupdate5 documentation: `https://doc.qt.io/qt-5/pylupdate5.html`
  - Example .pro file syntax from PyQt5 examples

  **Acceptance Criteria**:
  - [ ] `i18n/xiaozhi.pro` exists and is valid
  - [ ] `pylupdate5 i18n/xiaozhi.pro` runs without errors
  - [ ] `ls i18n/source/` shows generated .ts files

  **QA Scenarios**:

  Scenario: pylupdate5 generates .ts files
    Tool: Bash
    Preconditions: Task 1 complete, .pro file created
    Steps:
      1. `cd /Users/alxy/Desktop/2AREA/VIBE/py-xiaozhi`
      2. `pylupdate5 i18n/xiaozhi.pro 2>&1`
      3. `ls -la i18n/source/`
    Expected Result: .ts files created in i18n/source/
    Evidence: .sisyphus/evidence/task-2-ts-generated.txt

- [x] 3. **Create translation build script**

  **What to do**:
  - Create `i18n/generate_translations.sh` (Unix) / `i18n/generate_translations.bat` (Windows)
  - Script should:
    1. Run `pylupdate5 i18n/xiaozhi.pro` to extract/update strings
    2. Run `lrelease i18n/*.pro` to compile .ts → .qm
    3. Copy .qm files to `i18n/translations/`
  - Add shebang and chmod +x for Unix script
  - Add error handling with exit codes

  **Must NOT do**:
  - Do NOT hardcode absolute paths
  - Do NOT modify any source files

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Shell script creation, straightforward
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 4, 5)
  - **Blocks**: Task 5
  - **Blocked By**: Task 2

  **References**:
  - lrelease documentation: `https://doc.qt.io/qt-5/lrelease.html`
  - Example build scripts from Qt projects

  **Acceptance Criteria**:
  - [ ] `i18n/generate_translations.sh` is executable
  - [ ] Script runs without errors on Unix
  - [ ] Script produces .qm files in i18n/translations/

  **QA Scenarios**:

  Scenario: Build script produces translation files
    Tool: Bash
    Preconditions: Tasks 1, 2, 3 complete
    Steps:
      1. `cd /Users/alxy/Desktop/2AREA/VIBE/py-xiaozhi/i18n`
      2. `./generate_translations.sh 2>&1`
      3. `ls -la translations/*.qm`
    Expected Result: en_US.qm and ru_RU.qm exist
    Evidence: .sisyphus/evidence/task-3-build-script.txt

- [x] 4. **Add QTranslator loading to main.py**

  **What to do**:
  - Modify `main.py` to load QTranslator on startup
  - Add `--lang` CLI argument (en_US, ru_RU, or empty for system locale)
  - Detect system locale via `QLocale.system().name()`
  - Implement fallback chain: target_lang → en_US → zh_CN
  - Install translator to QCoreApplication
  - Store language preference in config for persistence

  **Must NOT do**:
  - Do NOT break existing Chinese user experience (default to zh_CN)
  - Do NOT change application startup logic beyond translator loading

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Small modification to existing file
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `git-master`: Not needed for single file change

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 5)
  - **Blocks**: Wave 4 (CLI --lang support)
  - **Blocked By**: None

  **References**:
  - `main.py:1-159` - Current main.py structure
  - QTranslator documentation: `https://doc.qt.io/qt-5/qtranslator.html`
  - QLocale documentation: `https://doc.qt.io/qt-5/qlocale.html`

  **Acceptance Criteria**:
  - [ ] `--lang=en_US` argument works
  - [ ] `--lang=ru_RU` argument works
  - [ ] No `--lang` defaults to system locale or zh_CN
  - [ ] QTranslator loads correct .qm file
  - [ ] Chinese users unaffected (default behavior unchanged)

  **QA Scenarios**:

  Scenario: English translator loads via --lang argument
    Tool: Bash
    Preconditions: Tasks 1-3 complete, .qm files exist
    Steps:
      1. `cd /Users/alxy/Desktop/2AREA/VIBE/py-xiaozhi`
      2. `python main.py --skip-activation --lang=en_US 2>&1 | head -20`
    Expected Result: App starts, English translator loaded
    Evidence: .sisyphus/evidence/task-4-english-loader.txt

  Scenario: Russian translator loads via --lang argument
    Tool: Bash
    Preconditions: Tasks 1-3 complete, .qm files exist
    Steps:
      1. `cd /Users/alxy/Desktop/2AREA/VIBE/py-xiaozhi`
      2. `python main.py --skip-activation --lang=ru_RU 2>&1 | head -20`
    Expected Result: App starts, Russian translator loaded
    Evidence: .sisyphus/evidence/task-4-russian-loader.txt

- [x] 5. **Create base translation files (.ts)**

  **What to do**:
  - Run `pylupdate5 i18n/xiaozhi.pro` to extract all hardcoded strings
  - Create `i18n/source/xiaozhi_zh_CN.ts` (source, Chinese)
  - Create `i18n/source/xiaozhi_en_US.ts` (English target)
  - Create `i18n/source/xiaozhi_ru_RU.ts` (Russian target)
  - Use Qt Linguist XML format for .ts files
  - Verify all source strings are captured

  **Must NOT do**:
  - Do NOT manually edit .ts files - use pylupdate5
  - Do NOT include strings not visible in UI

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Running pylupdate5 to generate files
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 1 (with Tasks 1, 2, 3, 4)
  - **Blocks**: Wave 2 (string marking tasks need to reference strings)
  - **Blocked By**: Tasks 2, 3

  **References**:
  - `pylupdate5` man page
  - Example .ts files from Qt applications

  **Acceptance Criteria**:
  - [ ] `i18n/source/xiaozhi_zh_CN.ts` exists and has all source strings
  - [ ] `i18n/source/xiaozhi_en_US.ts` exists (empty/untranslated)
  - [ ] `i18n/source/xiaozhi_ru_RU.ts` exists (empty/untranslated)
  - [ ] String count in .ts files matches hardcoded string count

  **QA Scenarios**:

  Scenario: pylupdate5 extracts all strings
    Tool: Bash
    Preconditions: Tasks 2, 3, 6-13 complete (all strings marked)
    Steps:
      1. `cd /Users/alxy/Desktop/2AREA/VIBE/py-xiaozhi`
      2. `pylupdate5 i18n/xiaozhi.pro 2>&1`
      3. `grep -c "<name>" i18n/source/xiaozhi_zh_CN.ts`
    Expected Result: Count > 0, all strings extracted
    Evidence: .sisyphus/evidence/task-5-string-count.txt

---

- [x] 6. **Mark strings in gui_display.qml (qsTr)**

  **What to do**:
  - Open `src/display/gui_display.qml`
  - Replace all hardcoded Chinese strings with `qsTr("Chinese text")`
  - Strings to replace:
    - `"状态: 未连接"` → `qsTr("Status: Not Connected")` (for en_US)
    - `"待命"` → `qsTr("Standby")`
    - `"按住后说话"` → `qsTr("Press and Speak")`
    - `"松开以停止"` → `qsTr("Release to Stop")`
    - `"开始对话"` → `qsTr("Start")`
    - `"打断对话"` → `qsTr("Interrupt")`
    - `"输入文字..."` → `qsTr("Enter text...")`
    - `"发送"` → `qsTr("Send")`
    - `"手动对话"` → `qsTr("Manual")`
    - `"自动对话"` → `qsTr("Auto")`
    - `"参数配置"` → `qsTr("Settings")`
  - Verify QML syntax remains valid after changes

  **Must NOT do**:
  - Do NOT change any logic, only string wrapping
  - Do NOT remove or rename variables
  - Do NOT change string interpolation patterns

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Straight string replacement, QML syntax is simple
  - **Skills**: []
  - **Skills Evaluated but Omitted**:
    - `frontend-ui-ux`: Not needed, no visual changes

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 7, 8, 9, 10, 11, 12, 13)
  - **Blocks**: Task 5 (string extraction needs marked strings)
  - **Blocked By**: None

  **References**:
  - `src/display/gui_display.qml:1-417` - QML file with all strings
  - Qt qsTr documentation: `https://doc.qt.io/qt-5/qml-qtqml-qt.html#qsTr`

  **Acceptance Criteria**:
  - [ ] All Chinese strings wrapped in qsTr()
  - [ ] QML file parses without errors
  - [ ] Original Chinese strings preserved as source in ts files

  **QA Scenarios**:

  Scenario: QML parses without errors after marking
    Tool: Bash
    Preconditions: None
    Steps:
      1. `cd /Users/alxy/Desktop/2AREA/VIBE/py-xiaozhi`
      2. `python -c "from PyQt5.QtQuick import QQuickView; print('QML syntax OK')"`
    Expected Result: No syntax errors
    Evidence: .sisyphus/evidence/task-6-qml-syntax.txt

  Scenario: All Chinese strings replaced with qsTr
    Tool: Bash
    Preconditions: None
    Steps:
      1. `grep -n "qsTr" src/display/gui_display.qml | wc -l`
      2. `grep -P "[\x{4e00}-\x{9fff}]" src/display/gui_display.qml || echo "No Chinese found"`
    Expected Result: qsTr count > 0, no raw Chinese strings
    Evidence: .sisyphus/evidence/task-6-qstr-count.txt

- [x] 7. **Mark strings in activation_window.qml (qsTr)**

  **What to do**:
  - Open `src/views/activation/activation_window.qml`
  - Replace Chinese strings with qsTr():
    - `"设备激活"` → `qsTr("Device Activation")`
    - `"设备信息"` → `qsTr("Device Info")`
    - `"设备序列号"` → `qsTr("Serial Number")`
    - `"MAC地址"` → `qsTr("MAC Address")`
    - `"激活验证码"` → `qsTr("Activation Code")`
    - `"复制"` → `qsTr("Copy")`
    - `"跳转激活"` → `qsTr("Open Activation")`
    - `"已激活"` → `qsTr("Activated")`
    - `"未激活"` → `qsTr("Not Activated")`
    - `"激活中..."` → `qsTr("Activating...")`
  - Keep status color logic intact

  **Must NOT do**:
  - Do NOT modify the QML logic for status colors
  - Do NOT change the layout

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple string replacement
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 8, 9, 10, 11, 12, 13)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `src/views/activation/activation_window.qml:1-381`

  **Acceptance Criteria**:
  - [ ] All Chinese strings wrapped in qsTr()
  - [ ] Activation status logic works (is_activated check)

  **QA Scenarios**:

  Scenario: Activation window QML marks strings
    Tool: Bash
    Preconditions: None
    Steps:
      1. `grep -c "qsTr" src/views/activation/activation_window.qml`
      2. `grep -P "[\x{4e00}-\x{9fff}]" src/views/activation/activation_window.qml || echo "Clean"`
    Expected Result: qsTr count > 0, no raw Chinese
    Evidence: .sisyphus/evidence/task-7-activation-qstr.txt

- [x] 8. **Mark strings in gui_display.py (translate)**

  **What to do**:
  - Open `src/display/gui_display.py`
  - Add `QCoreApplication.translate()` wrapping for Chinese strings
  - Key locations:
    - Line 421: `mode_text = "自动对话" if self.auto_mode else "手动对话"`
      → `mode_text = QCoreApplication.translate("GuiDisplay", "Auto") if self.auto_mode else QCoreApplication.translate("GuiDisplay", "Manual")`
  - Import QCoreApplication if not already imported
  - Use context "GuiDisplay" for all strings in this file

  **Must NOT do**:
  - Do NOT change any logic flow
  - Do NOT modify variable types
  - Do NOT add new imports beyond QCoreApplication

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple string replacement
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 9, 10, 11, 12, 13)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `src/display/gui_display.py:421` - Main string to translate
  - Qt translate documentation: `https://doc.qt.io/qt-5/qcoreapplication.html#translate`

  **Acceptance Criteria**:
  - [ ] QCoreApplication imported
  - [ ] Chinese strings wrapped in translate()
  - [ ] Python syntax valid after changes

  **QA Scenarios**:

  Scenario: gui_display.py syntax valid
    Tool: Bash
    Preconditions: None
    Steps:
      1. `python -m py_compile src/display/gui_display.py 2>&1`
    Expected Result: No syntax errors
    Evidence: .sisyphus/evidence/task-8-python-syntax.txt

- [x] 9. **Mark strings in gui_display_model.py (translate)**

  **What to do**:
  - Open `src/display/gui_display_model.py`
  - Replace default Chinese strings with translate():
    - Line 35: `_status_text = "状态: 未连接"` → `QCoreApplication.translate("GuiDisplayModel", "Status: Not Connected")`
    - Line 37: `_tts_text = "待命"` → `translate("GuiDisplayModel", "Standby")`
    - Line 38: `_button_text = "开始对话"` → `translate("GuiDisplayModel", "Start")`
    - Line 39: `_mode_text = "手动对话"` → `translate("GuiDisplayModel", "Manual")`
  - Lines 147-149: Auto mode text updates
  - Import QCoreApplication at top

  **Must NOT do**:
  - Do NOT change the model logic
  - Do NOT modify property types

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple string replacement
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 10, 11, 12, 13)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `src/display/gui_display_model.py:35-149` - All strings to translate

  **Acceptance Criteria**:
  - [ ] All Chinese strings wrapped in translate()
  - [ ] File compiles without errors

  **QA Scenarios**:

  Scenario: gui_display_model.py compiles
    Tool: Bash
    Preconditions: None
    Steps:
      1. `python -m py_compile src/display/gui_display_model.py 2>&1`
    Expected Result: Success, no errors
    Evidence: .sisyphus/evidence/task-9-model-compile.txt

- [x] 10. **Mark strings in cli_display.py (translate)**

  **What to do**:
  - Open `src/display/cli_display.py`
  - Replace all Chinese display strings with translate():
    - Line 222: `"正在关闭应用..."` → `translate("CliDisplay", "Closing application...")`
    - Line 228: `"r: 开始/停止 | x: 打断 | q: 退出 | h: 帮助 | 其他: 发送文本"` → multi-part translation
    - Line 308: `"输入: "` → `translate("CliDisplay", "Input: ")`
    - Line 329: `"状态: {trunc(self._dash_status)}"` → `translate("CliDisplay", "Status: %1").arg(trunc(self._dash_status))`
    - Line 330: `"连接: {'已连接' if ... else '未连接'}"` → split and translate
    - Line 331: `"表情: {trunc(self._dash_emotion)}"` → `translate("CliDisplay", "Emoji: %1").arg(trunc(self._dash_emotion))`
    - Line 332: `"文本: {trunc(self._dash_text)}"` → `translate("CliDisplay", "Text: %1").arg(trunc(self._dash_text))`
  - Line 352: `title = style(" 小智 AI 终端 ", "bold", "cyan")` → `translate("CliDisplay", " Xiaozhi AI Terminal ")`

  **Must NOT do**:
  - Do NOT change terminal drawing logic
  - Do NOT modify ANSI escape sequences

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: String replacement, some concatenation pattern changes
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 9, 11, 12, 13)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `src/display/cli_display.py:222,228,308,329-332,352`

  **Acceptance Criteria**:
  - [ ] All Chinese strings wrapped in translate()
  - [ ] CLI still renders correctly
  - [ ] No syntax errors

  **QA Scenarios**:

  Scenario: CLI strings marked for translation
    Tool: Bash
    Preconditions: None
    Steps:
      1. `grep -c "translate" src/display/cli_display.py`
      2. `python -m py_compile src/display/cli_display.py`
    Expected Result: translate count > 0, compile succeeds
    Evidence: .sisyphus/evidence/task-10-cli-translate.txt

- [x] 11. **Mark strings in cli_activation.py (translate)**

  **What to do**:
  - Open `src/views/activation/cli_activation.py`
  - Replace Chinese strings with translate():
    - Line 89: `"小智AI客户端 - 设备激活流程"` → `translate("CLIActivation", "Xiaozhi AI - Device Activation")`
    - Line 91: `"正在初始化设备，请稍候..."` → `translate("CLIActivation", "Initializing device...")`
    - Line 120-133: Device info display strings
    - Line 186-202: Activation info display
    - Line 207-217: Success/failure messages
    - All print() statements with Chinese text

  **Must NOT do**:
  - Do NOT change activation flow logic
  - Do NOT modify error handling

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: String replacement in print statements
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 9, 10, 12, 13)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `src/views/activation/cli_activation.py:89-260` - All Chinese strings

  **Acceptance Criteria**:
  - [ ] All Chinese print statements wrapped
  - [ ] Activation logic unchanged
  - [ ] File compiles

  **QA Scenarios**:

  Scenario: CLI activation marks strings
    Tool: Bash
    Preconditions: None
    Steps:
      1. `grep -c "translate" src/views/activation/cli_activation.py`
      2. `python -m py_compile src/views/activation/cli_activation.py`
    Expected Result: Count > 0, compile OK
    Evidence: .sisyphus/evidence/task-11-activation-cli.txt

- [x] 12. **Mark strings in system_tray.py (translate)**

  **What to do**:
  - Open `src/views/components/system_tray.py`
  - Replace Chinese tray menu strings:
    - Line 98: `"显示主窗口"` → `translate("SystemTray", "Show Window")`
    - Line 106: `"参数配置"` → `translate("SystemTray", "Settings")`
    - Line 114: `"退出程序"` → `translate("SystemTray", "Exit")`
    - Line 174: `tooltip = f"小智AI助手 - {status}"` → `translate("SystemTray", "Xiaozhi AI - %1").arg(status)`
    - Line 193-200: Status color logic (no translation needed, these are conditional checks)
  - Tray tooltip/status text should translate based on status

  **Must NOT do**:
  - Do NOT change tray icon logic
  - Do NOT modify status color determination

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Simple string replacement
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 9, 10, 11, 13)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `src/views/components/system_tray.py:98,106,114,174`

  **Acceptance Criteria**:
  - [ ] Menu items use translate()
  - [ ] Tray tooltip uses translate()
  - [ ] File compiles

  **QA Scenarios**:

  Scenario: System tray strings marked
    Tool: Bash
    Preconditions: None
    Steps:
      1. `grep -c "translate" src/views/components/system_tray.py`
    Expected Result: Count > 0
    Evidence: .sisyphus/evidence/task-12-tray-translate.txt

- [x] 13. **Mark strings in settings_window.py + .ui**

  **What to do**:
  - Open `src/views/settings/settings_window.py`
  - Replace Chinese tab names:
    - `"系统选项"` → `translate("SettingsWindow", "System")`
    - `"唤醒词"` → `translate("SettingsWindow", "Wake Word")`
    - `"摄像头"` → `translate("SettingsWindow", "Camera")`
    - `"音频设备"` → `translate("SettingsWindow", "Audio")`
    - `"快捷键"` → `translate("SettingsWindow", "Shortcuts")`
  - Message boxes (Line 156-277): Chinese strings → translate()
  - Open `src/views/settings/settings_window.ui` - strings here are auto-extracted by pylupdate5, but ensure they use proper translate context

  **Must NOT do**:
  - Do NOT change settings tab logic
  - Do NOT modify dialog behavior

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: String replacement in multiple files
  - **Skills**: []

  **Parallelization**:
  - **Can Run In Parallel**: YES
  - **Parallel Group**: Wave 2 (with Tasks 6, 7, 8, 9, 10, 11, 12)
  - **Blocks**: Task 5
  - **Blocked By**: None

  **References**:
  - `src/views/settings/settings_window.py:80-101,156-277`
  - `src/views/settings/settings_window.ui` - Qt Designer UI file

  **Acceptance Criteria**:
  - [ ] Tab names use translate()
  - [ ] Message boxes use translate()
  - [ ] Both .py and .ui files parse correctly

  **QA Scenarios**:

  Scenario: Settings window strings marked
    Tool: Bash
    Preconditions: None
    Steps:
      1. `grep -c "translate" src/views/settings/settings_window.py`
      2. `python -m py_compile src/views/settings/settings_window.py`
    Expected Result: Count > 0, compile OK
    Evidence: .sisyphus/evidence/task-13-settings-translate.txt

---

- [x] 14. **Mark strings in settings components .py files**

  **What to do**:
  - Open each settings component file:
    - `src/views/settings/components/system_options/system_options_widget.py`
    - `src/views/settings/components/wake_word/wake_word_widget.py`
    - `src/views/settings/components/camera/camera_widget.py`
    - `src/views/settings/components/audio/audio_widget.py`
    - `src/views/settings/components/shortcuts_settings.py`
  - Replace Chinese strings in each with translate()
  - Common patterns: labels, tooltips, button text, placeholder text

  **Must NOT do**:
  - Do NOT modify widget logic
  - Do NOT change config key names

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Multiple files but simple string replacements
  - **Skills**: []
  - **Parallelization**: YES - Wave 3 with Tasks 15, 16, 17, 18, 19

  **References**:
  - Each component's .py file
  - Qt translate documentation

  **Acceptance Criteria**:
  - [ ] All Chinese strings wrapped in translate()
  - [ ] All files compile without errors

  **QA Scenarios**:

  Scenario: All settings components compile
    Tool: Bash
    Preconditions: None
    Steps:
      1. `for f in src/views/settings/components/*/*.py src/views/settings/components/shortcuts_settings.py; do python -m py_compile "$f" || echo "FAIL: $f"; done`
    Expected Result: All compile successfully
    Evidence: .sisyphus/evidence/task-14-components-compile.txt

- [x] 15. **Mark strings in settings .ui files**

  **What to do**:
  - Open each .ui file:
    - `src/views/settings/settings_window.ui`
    - `src/views/settings/components/system_options/system_options_widget.ui`
    - `src/views/settings/components/wake_word/wake_word_widget.ui`
    - `src/views/settings/components/camera/camera_widget.ui`
    - `src/views/settings/components/audio/audio_widget.ui`
  - Note: .ui strings are auto-extracted by pylupdate5, but verify they're properly marked
  - Some .ui files may need manual wrapping in translate() if they have dynamic strings

  **Must NOT do**:
  - Do NOT use Qt Designer to modify layouts
  - Do NOT change widget IDs

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: UI XML file string marking
  - **Skills**: []
  - **Parallelization**: YES - Wave 3 with Tasks 14, 16, 17, 18, 19

  **References**:
  - `.ui` files are Qt Designer XML format
  - Strings in `<string>` tags are auto-extracted

  **Acceptance Criteria**:
  - [ ] All .ui files have Chinese strings visible for extraction
  - [ ] pylupdate5 can extract from .ui files

  **QA Scenarios**:

  Scenario: UI files extract correctly
    Tool: Bash
    Preconditions: Task 2 complete
    Steps:
      1. `pylupdate5 i18n/xiaozhi.pro 2>&1 | grep -i "ui"`
      2. `grep -c "<string>" src/views/settings/settings_window.ui`
    Expected Result: .ui files processed, strings extracted
    Evidence: .sisyphus/evidence/task-15-ui-extract.txt

- [x] 16. **Add language dropdown to System Options tab**

  **What to do**:
  - Modify `system_options_widget.py` and `.ui`
  - Add QComboBox for language selection
  - Options: "简体中文" (default), "English", "Русский"
  - When changed, save to config and trigger translator reload
  - Add to settings_window.ui System Options tab

  **Must NOT do**:
  - Do NOT make language change require app restart (reload translator in-memory)
  - Do NOT add languages not supported by translations

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Adding dropdown widget
  - **Skills**: []
  - **Parallelization**: YES - Wave 3 with Tasks 14, 15, 17, 18, 19
  - **Blocks**: Task 17

  **References**:
  - `settings_window.py:78-81` - Example of adding tabs
  - Qt QComboBox documentation

  **Acceptance Criteria**:
  - [ ] Language dropdown appears in System Options
  - [ ] Dropdown shows zh_CN, en_US, ru_RU options
  - [ ] Selection saves to config

  **QA Scenarios**:

  Scenario: Language dropdown appears in settings
    Tool: Bash
    Preconditions: Tasks 14, 15 complete
    Steps:
      1. `grep -n "language\|Language\|combo" src/views/settings/components/system_options/system_options_widget.py | head -10`
    Expected Result: Combo box code exists
    Evidence: .sisyphus/evidence/task-16-lang-dropdown.txt

- [x] 17. **Wire language setting to translator**

  **What to do**:
  - Create `src/utils/language_manager.py` to handle:
    - Load .qm files based on config or CLI arg
    - Install translator to QCoreApplication
    - Change language at runtime without restart
    - Provide `set_language(lang_code)` function
  - Modify main.py to use LanguageManager instead of direct QTranslator
  - Settings window calls LanguageManager when dropdown changes

  **Must NOT do**:
  - Do NOT break existing startup flow
  - Do NOT require restart for language change

  **Recommended Agent Profile**:
  - **Category**: `deep`
    - Reason: New module with logic, needs careful implementation
  - **Skills**: []
  - **Parallelization**: YES - Wave 3 with Tasks 14, 15, 16, 18, 19
  - **Blocks**: Task 4 (connects to main.py)

  **References**:
  - `main.py` startup flow
  - QTranslator documentation
  - ConfigManager for storing preference

  **Acceptance Criteria**:
  - [ ] LanguageManager class exists
  - [ ] set_language() works at runtime
  - [ ] Preference persists across restarts

  **QA Scenarios**:

  Scenario: Language changes at runtime
    Tool: Bash
    Preconditions: Tasks 1-4, 16, 17 complete
    Steps:
      1. `python -c "from src.utils.language_manager import LanguageManager; lm = LanguageManager(); lm.set_language('en_US'); print('OK')"`
    Expected Result: No errors
    Evidence: .sisyphus/evidence/task-17-lang-manager.txt

- [x] 18. **Create en_US.ts translations**

  **What to do**:
  - Run `pylupdate5 i18n/xiaozhi.pro` to extract all marked strings
  - Open `i18n/source/xiaozhi_en_US.ts` in Qt Linguist or text editor
  - Fill in English translations for all `<source>` elements
  - Example: `<source>状态: 未连接</source>` → `<translation>Status: Not Connected</translation>`
  - Compile with `lrelease i18n/xiaozhi.pro`
  - Verify `i18n/translations/xiaozhi_en_US.qm` exists

  **Must NOT do**:
  - Do NOT use machine translation without checking
  - Do NOT leave any strings untranslated

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Translation work, creative but straightforward
  - **Skills**: []
  - **Parallelization**: YES - Wave 3 with Tasks 14, 15, 16, 17, 19

  **References**:
  - Qt Linguist documentation
  - Example .ts files from other Qt projects

  **Acceptance Criteria**:
  - [ ] en_US.ts has all source strings translated
  - [ ] en_US.qm compiles successfully
  - [ ] No untranslated <unfinished> tags

  **QA Scenarios**:

  Scenario: English translation complete
    Tool: Bash
    Preconditions: All string marking tasks complete
    Steps:
      1. `grep -c "<translation>" i18n/source/xiaozhi_en_US.ts`
      2. `grep -c "<unfinished>" i18n/source/xiaozhi_en_US.ts || echo "0"`
      3. `ls -la i18n/translations/xiaozhi_en_US.qm`
    Expected Result: All translated, no unfinished, .qm exists
    Evidence: .sisyphus/evidence/task-18-en-complete.txt

- [x] 19. **Create ru_RU.ts translations**

  **What to do**:
  - Run `pylupdate5 i18n/xiaozhi.pro` to ensure strings are current
  - Copy `i18n/source/xiaozhi_en_US.ts` as base (to preserve structure)
  - Fill in Russian translations for all strings
  - Key translations needed:
    - "状态: 未连接" → "Статус: Не подключено"
    - "待命" → "Ожидание"
    - "按住后说话" → "Зажмите и говорите"
    - "松开以停止" → "Отпустите для остановки"
    - "开始对话" → "Начать"
    - "打断对话" → "Прервать"
    - "输入文字..." → "Введите текст..."
    - "发送" → "Отправить"
    - "手动对话" → "Ручной"
    - "自动对话" → "Авто"
    - "参数配置" → "Настройки"
  - Compile with `lrelease i18n/xiaozhi.pro`
  - Verify `i18n/translations/xiaozhi_ru_RU.qm` exists

  **Must NOT do**:
  - Do NOT use only machine translation (may be poor quality for Russian)
  - Do NOT change string IDs

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Translation work
  - **Skills**: []
  - **Parallelization**: YES - Wave 3 with Tasks 14, 15, 16, 17, 18

  **References**:
  - Russian Qt translations as reference
  - Russian localization conventions

  **Acceptance Criteria**:
  - [ ] ru_RU.ts has all source strings translated
  - [ ] ru_RU.qm compiles successfully
  - [ ] Cyrillic renders correctly (no tofu □□)

  **QA Scenarios**:

  Scenario: Russian translation complete and compiles
    Tool: Bash
    Preconditions: Task 18 complete
    Steps:
      1. `grep -c "<translation>" i18n/source/xiaozhi_ru_RU.ts`
      2. `grep -c "<unfinished>" i18n/source/xiaozhi_ru_RU.ts || echo "0"`
      3. `ls -la i18n/translations/xiaozhi_ru_RU.qm`
      4. `file i18n/translations/xiaozhi_ru_RU.qm`
    Expected Result: All translated, no unfinished, .qm exists with correct encoding
    Evidence: .sisyphus/evidence/task-19-ru-complete.txt

---

- [x] 20. **Add CLI --lang argument support**

  **What to do**:
  - Ensure main.py properly handles `--lang` argument
  - If `--lang=en_US` or `--lang=ru_RU`, load that translator
  - If no `--lang` specified:
    - Check config for saved preference
    - Fall back to system locale (QLocale.system().name())
    - If system locale not supported, fall back to zh_CN (source)
  - ParseArgs already handles --lang in Task 4, verify it works

  **Must NOT do**:
  - Do NOT change default behavior for existing Chinese users

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Integration testing/verification
  - **Skills**: []
  - **Parallelization**: YES - Wave 4 with Tasks 21, 22, 23
  - **Blocked By**: Task 4

  **References**:
  - `main.py:12-34` - argument parsing
  - Task 4 implementation

  **Acceptance Criteria**:
  - [ ] `--lang=en_US` works from CLI
  - [ ] `--lang=ru_RU` works from CLI
  - [ ] No `--lang` uses system locale or default

  **QA Scenarios**:

  Scenario: CLI lang argument parsing
    Tool: Bash
    Preconditions: Tasks 4, 17, 18, 19 complete
    Steps:
      1. `cd /Users/alxy/Desktop/2AREA/VIBE/py-xiaozhi`
      2. `python main.py --help | grep -A1 "\-\-lang"`
    Expected Result: --lang argument documented
    Evidence: .sisyphus/evidence/task-20-cli-lang.txt

- [x] 21. **Verify CLI mode translations work**

  **What to do**:
  - Run app in CLI mode with different languages
  - Verify Chinese strings don't appear in CLI output
  - Verify translated strings appear correctly with Cyrillic/Latin characters

  **Must NOT do**:
  - Do NOT break CLI mode functionality

  **Recommended Agent Profile**:
  - **Category**: `quick`
    - Reason: Verification testing
  - **Skills**: []
  - **Parallelization**: YES - Wave 4 with Tasks 20, 22, 23

  **References**:
  - `src/display/cli_display.py` - CLI rendering

  **Acceptance Criteria**:
  - [ ] CLI mode displays English/Russian correctly
  - [ ] No Chinese visible when lang=en_US or ru_RU

  **QA Scenarios**:

  Scenario: CLI displays in selected language
    Tool: Bash
    Preconditions: Task 20 complete
    Steps:
      1. `cd /Users/alxy/Desktop/2AREA/VIBE/py-xiaozhi`
      2. `LANG=en_US timeout 2 python main.py --mode cli --skip-activation 2>&1 || true`
      3. `LANG=ru_RU timeout 2 python main.py --mode cli --skip-activation 2>&1 || true`
    Expected Result: No Chinese output visible
    Evidence: .sisyphus/evidence/task-21-cli-translation.txt

- [x] 22. **Create CONTRIBUTING.md for translators**

  **What to do**:
  - Create `CONTRIBUTING.md` in i18n/ directory
  - Document:
    1. How to add a new language
    2. How to update existing translations after code changes
    3. How to run pylupdate5 and lrelease
    4. Translation guidelines (context, plurals, etc.)
  - Add section in main CONTRIBUTING.md if exists

  **Must NOT do**:
  - Do NOT make instructions too complex for new contributors

  **Recommended Agent Profile**:
  - **Category**: `writing`
    - Reason: Documentation writing
  - **Skills**: []
  - **Parallelization**: YES - Wave 4 with Tasks 20, 21, 23

  **References**:
  - KDE i18n Contributing guide as reference
  - Qt Linguist manual

  **Acceptance Criteria**:
  - [ ] i18n/CONTRIBUTING.md exists
  - [ ] Instructions are clear and complete
  - [ ] Commands can be copy-pasted to run

  **QA Scenarios**:

  Scenario: Contributing guide exists and is clear
    Tool: Bash
    Preconditions: None
    Steps:
      1. `ls -la i18n/CONTRIBUTING.md`
      2. `head -50 i18n/CONTRIBUTING.md`
    Expected Result: File exists, content is helpful
    Evidence: .sisyphus/evidence/task-22-contrib-guide.txt

- [x] 23. **Final integration test**

  **What to do**:
  - Full end-to-end test:
    1. Run `python main.py --lang=en_US --skip-activation` in GUI mode
    2. Verify all UI elements show English
    3. Change language in Settings to Russian
    4. Verify UI updates to Russian without restart
    5. Restart app, verify preference persisted
  - Check for any remaining hardcoded Chinese strings
  - Verify no regression in Chinese mode

  **Must NOT do**:
  - Do NOT skip any verification step

  **Recommended Agent Profile**:
  - **Category**: `unspecified-high`
    - Reason: Comprehensive end-to-end testing
  - **Skills**: [`playwright`]
    - playwright: For GUI testing if available
  - **Parallelization**: YES - Wave 4 with Tasks 20, 21, 22

  **References**:
  - All previous task criteria
  - Full codebase

  **Acceptance Criteria**:
  - [ ] English GUI mode works completely
  - [ ] Russian GUI mode works completely
  - [ ] Language switcher persists preference
  - [ ] No Chinese strings visible in non-zh_CN mode
  - [ ] Chinese users unaffected

  **QA Scenarios**:

  Scenario: Full English mode verification
    Tool: Bash
    Preconditions: Tasks 1-22 complete
    Steps:
      1. `cd /Users/alxy/Desktop/2AREA/VIBE/py-xiaozhi`
      2. `# Check for remaining Chinese in English mode`
      3. `grep -r "[\x{4e00}-\x{9fff}]" src/**/*.qml src/**/*.py src/**/*.ui 2>/dev/null | grep -v ".pyc" | head -20 || echo "No Chinese found"`
    Expected Result: No hardcoded Chinese in translatable files
    Evidence: .sisyphus/evidence/task-23-no-chinese.txt

---

## Final Verification Wave

> 4 review agents run in PARALLEL. ALL must APPROVE. Present consolidated results to user and get explicit "okay" before completing.

- [x] F1. **Plan Compliance Audit** — `oracle` ✅ PASS (Must Have 15/15, Must NOT Have 4/4, Tasks 23/23)
  Read the plan end-to-end. For each "Must Have": verify implementation exists. For each "Must NOT Have": search codebase for forbidden patterns. Check evidence files exist in .sisyphus/evidence/.
  Output: `Must Have [N/N] | Must NOT Have [N/N] | Tasks [N/N] | VERDICT: APPROVE/REJECT`

- [x] F2. **Code Quality Review** — `unspecified-high` ✅ PASS (Build PASS, 14/14 clean)
  Run `python -m py_compile` on all modified .py files. Check for `as any`/`@ts-ignore`, empty catches, console.log in prod, commented-out code, unused imports. Check all translate() calls have proper context.
  Output: `Build [PASS/FAIL] | Files [N/N clean] | VERDICT`

- [x] F3. **Real Manual QA** — `unspecified-high` (+ `playwright` skill if UI) ✅ PASS
  Start from clean state. Execute EVERY QA scenario from EVERY task. Test GUI mode with both languages. Test CLI mode. Test language switcher. Save to `.sisyphus/evidence/final-qa/`.
  Output: `Scenarios [N/N pass] | Integration [N/N] | VERDICT`

- [x] F4. **Scope Fidelity Check** — `deep` ✅ PASS (23/23 compliant, CLEAN - no contamination)
  For each task: read "What to do", read actual diff. Verify 1:1. Check "Must NOT do" compliance. Detect cross-task contamination. Flag unaccounted changes.
  Output: `Tasks [N/N compliant] | Contamination [CLEAN/N issues] | VERDICT`

---

## Commit Strategy

- **1**: `i18n: add Qt Linguist translation infrastructure` - i18n/, xiaozhi.pro
- **2**: `i18n: mark QML strings for translation` - *.qml files
- **3**: `i18n: mark Python strings for translation` - *.py files
- **4**: `i18n: add English translations` - en_US.ts, en_US.qm
- **5**: `i18n: add Russian translations` - ru_RU.ts, ru_RU.qm
- **6**: `i18n: add language switcher to settings` - system_options
- **7**: `docs: add i18n contribution guide` - CONTRIBUTING.md

---

## Success Criteria

### Verification Commands
```bash
# Extract strings (should create/merge .ts files)
pylupdate5 i18n/xiaozhi.pro

# Compile translations
lrelease i18n/*.pro

# Run in English mode
python main.py --lang=en_US

# Run in Russian mode
python main.py --lang=ru_RU

# Verify no Chinese in UI (grep for unicode ranges)
grep -rP "[\x{4e00}-\x{9fff}]" src/**/*.qml src/**/*.py 2>/dev/null | wc -l
# Should be 0 after translation
```

### Final Checklist
- [x] All Chinese strings externalized to .ts files ✅
- [x] en_US.ts has all source strings translated ✅
- [x] ru_RU.ts has all source strings translated ✅
- [x] Language switcher works in Settings ✅
- [x] QTranslator loads .qm on startup ✅
- [x] No regression for existing Chinese users ✅
- [x] PR ready for upstream submission ✅

---

## Open Questions — RESOLVED

### ✅ Q1: Default Language Fallback → **A: Китайский**
Fallback chain: target_lang → en_US → zh_CN → Китайский для всех unsupported локалей

### ✅ Q2: Translation Quality → **A: Машинный перевод**
Использовать машинный перевод для скорости, можно улучшить позже

### ✅ Q3: Russian Scope → **A: English + Russian**
Полная локализация обоих языков в одном PR

### ✅ Q4: Log Messages → **A: Переводить все**
Все логи тоже переводятся (INFO, DEBUG, ERROR)

---

## Key Decisions Applied

- **Fallback Chain**: target_lang → en_US → zh_CN (Китайский для unsupported)
- **Language Switcher Location**: System Options tab in Settings
- **Language Change Timing**: Immediate (no restart required)
- **Chinese Users**: Unaffected (zh_CN remains default)
- **Translation Quality**: Machine-translated (acceptable for OSS PR)
- **Log Translation**: Yes, all levels

---

## Plan Generated: xiaozhi-i18n

**Key Decisions Made:**
- Using Qt Linguist (ts/qm files) - standard for PyQt5
- All strings wrapped in `qsTr()` (QML) and `translate()` (Python)
- Language switcher in Settings UI (System Options tab)
- Fallback chain: target → en_US → zh_CN

**Scope:**
- IN: All user-facing UI strings (GUI, CLI, Settings, Tray, Activation)
- OUT: LLM/API prompts, log messages (unless user decides otherwise), third-party libs

**Guardrails Applied**:
- MUST NOT modify LLM prompt templates
- MUST NOT change application logic
- MUST preserve UTF-8 encoding
- MUST provide fallback chain

**Auto-Resolved** (minor gaps fixed):
- Added LanguageManager module for cleaner translator handling
- Created build script for easy translation updates

**Defaults Applied**:
- Chinese remains default for existing users
- Logs kept in English for debugging

**Decisions Needed** (from Open Questions above):
- Q1: Default fallback language for unsupported locales
- Q2: Translation quality approach
- Q3: Russian scope
- Q4: Log message translation

Plan saved to: `.sisyphus/plans/xiaozhi-i18n.md`
Draft cleaned up: `.sisyphus/drafts/xiaozhi-i18n.md` (deleted)

- [x] F1. **Plan Compliance Audit** — `oracle` ✅ PASS (Must Have 15/15, Must NOT Have 4/4, Tasks 23/23) — .qm location fixed
- [x] F2. **Code Quality Review** — `unspecified-high` ✅ PASS (Build PASS, 14/14 clean)
- [x] F3. **Real Manual QA** — `unspecified-high` ✅ PASS (already complete)
- [x] F4. **Scope Fidelity Check** — `deep` ✅ PASS (23/23 compliant, contamination was false positive — git diff confirms only i18n files modified)

---

## Commit Strategy

- **1**: `i18n: add Qt Linguist translation infrastructure` - i18n/, xiaozhi.pro
- **2**: `i18n: mark QML strings for translation` - *.qml files
- **3**: `i18n: mark Python strings for translation` - *.py files
- **4**: `i18n: add English translations` - en_US.ts, en_US.qm
- **5**: `i18n: add Russian translations` - ru_RU.ts, ru_RU.qm
- **6**: `i18n: add language switcher to settings` - system_options
- **7**: `docs: add i18n contribution guide` - CONTRIBUTING.md

---

## Success Criteria

### Verification Commands
```bash
# Extract strings (should create/merge .ts files)
pylupdate5 i18n/xiaozhi.pro

# Compile translations
lrelease i18n/*.ts

# Run in English mode
LANG=en_US python main.py  # or --lang=en_US

# Verify no Chinese in UI (grep for unicode ranges)
grep -P "[\x{4e00}-\x{9fff}]" src/**/*.qml  # Should find 0 after translation
```

### Final Checklist
- [x] All Chinese strings externalized to .ts files ✅
- [x] en_US.ts has all source strings translated ✅
- [x] ru_RU.ts has all source strings translated ✅
- [x] Language switcher works in Settings ✅
- [x] QTranslator loads .qm on startup ✅
- [x] No regression for existing Chinese users ✅
