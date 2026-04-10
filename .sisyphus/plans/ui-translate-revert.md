# Исправление: revert .ui файлов — translate() в XML не работает

## TL;DR

**Проблема**: Qt `.ui` XML формат НЕ выполняет `QCoreApplication.translate()` внутри `<string>` элементов — только plain text. Текущий подход (`<string>QCoreApplication.translate(...)</string>`) отображает код как текст.

**Решение**: Revert `.ui` файлов — вернуть plain Chinese текст обратно. Переводы применять в Python коде через `self.retranslateUi(self)` вызов после `uic.loadUi()`.

## Техническое объяснение

```xml
<!-- ❌ НЕПРАВИЛЬНО — Qt показывает как текст: -->
<string>QCoreApplication.translate("SettingsWindow", "参数配置")</string>

<!-- ✅ ПРАВИЛЬНО — plain text, Qt отображает китайский: -->
<string>参数配置</string>
```

Qt uic компилятор НЕ выполняет Python код из `<string>` элементов. Это просто текстовые метки для UI.

## TODOs

- [x] 1. **Revert settings_window.ui** — заменить все `<string>QCoreApplication.translate(...)` на plain Chinese текст ✅

- [x] 2. **Revert system_options_widget.ui** — аналогично ✅

- [x] 3. **Revert wake_word_widget.ui** — аналогично ✅

- [x] 4. **Revert audio_widget.ui** — аналогично ✅

- [x] 5. **Revert camera_widget.ui** — аналогично ✅

- [x] 6. **Добавить retranslateUi() вызовы** во все 5 компонентов после uic.loadUi() ✅

- [x] 7. **Переизвлечь строки pylupdate5** из reverted .ui файлов ✅

- [x] 8. **Перекомпилировать .qm файлы** ✅

- [ ] 9. **Проверить что Settings открывается и показывает русский**

## Файлы для revert

### settings_window.ui
Вернуть plain Chinese для всех строк:
- `<string>参数配置</string>`
- `<string>系统选项</string>`
- `<string>客户端ID:</string>`
- и т.д.

### system_options_widget.ui
- `<string>客户端ID:</string>`
- `<string>设备ID:</string>`
- и т.д.

### wake_word_widget.ui
### audio_widget.ui
### camera_widget.ui

## После revert — добавить retranslateUi() в Python

Каждый компонент должен вызывать `self.retranslateUi(self)` ПОСЛЕ `uic.loadUi()`.

```python
def _setup_ui(self):
    from PyQt5 import uic
    ui_path = Path(__file__).parent / "xxx.ui"
    uic.loadUi(str(ui_path), self)
    self.retranslateUi(self)  # ← добавить обратно
```

## Success Criteria
- [ ] .ui файлы содержат plain Chinese текст (без translate() внутри <string>)
- [ ] Python код вызывает self.retranslateUi(self) после uic.loadUi()
- [ ] Settings открывается и показывает русский текст (не код)
- [ ] Нет Chinese fallback в не-zh_CN режимах
