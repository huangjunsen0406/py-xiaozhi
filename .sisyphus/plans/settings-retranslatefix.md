# Исправление retranslateUi crash в settings_window.py

## TL;DR
> Удалить ошибочный вызов `self.retranslateUi(self)` в `settings_window.py` — uic.loadUi() уже применяет translate() из .ui файла при загрузке.

## Контекст
- **Файл**: `src/views/settings/settings_window.py`
- **Строка**: 54
- **Ошибка**: `AttributeError: 'SettingsWindow' object has no attribute 'retranslateUi'`
- **Причина**: `retranslateUi` — это метод сгенерированного Ui-класса, а не экземпляра виджета. При использовании `uic.loadUi(baseInstance=self)` метод не создаётся на экземпляре.
- **Решение**: Удалить строку `self.retranslateUi(self)` — Qt uic автоматически выполняет `QCoreApplication.translate()` из `<string>` элементов .ui файла при загрузке.

## TODOs

- [ ] 1. **Удалить self.retranslateUi(self) из settings_window.py**
   
   **Файл**: `src/views/settings/settings_window.py`
   
   **Что сделать**: Удалить строку 54 `self.retranslateUi(self)` — она вызывает crash.
   
   **Почему работает без неё**: `.ui` файл содержит `<string>QCoreApplication.translate("SettingsWindow", "текст")</string>`. Qt uic.evaluateThese при загрузке .ui файла уже вызывает translate() для всех строк. Дополнительный вызов retranslateUi не нужен.
   
   **Проверка**: `uv run python -c "from src.views.settings.settings_window import SettingsWindow; print('OK')"`

- [ ] 2. **Проверить что Settings открывается без crash**
   
   **Что сделать**: Запустить приложение и открыть окно настроек (кнопка ⚙️)
   
   **Ожидаемый результат**: Settings открывается без ошибок

## Технические детали

### Почему self.retranslateUi(self) не работает
```python
# Генерируется pyuic5 в Ui_settings_window:
class Ui_settings_window:
    def retranslateUi(self, SettingsWindow):
        SettingsWindow.some_label.setText(
            QCoreApplication.translate("SettingsWindow", "中文"))
# retranslateUi — метод класса Ui_settings_window, НЕ виджета SettingsWindow

# При uic.loadUi(ui_path, self) — self это SettingsWindow (QDialog)
# Метод retranslateUi НЕ добавляется к экземпляру SettingsWindow
```

### Почему удаление строки безопасно
`.ui` файл содержит:
```xml
<string>QCoreApplication.translate("SettingsWindow", "参数配置")</string>
```
`uic.loadUi()` вызывает `QCoreApplication.translate()` для каждого `<string>` элемента в процессе загрузки. Перевод уже применён.

### Если позже нужно будет поддерживать смену языка
Потребуется более сложный подход:
```python
def retranslateUi(self):
    for widget in self.findChildren(QtWidgets.QWidget):
        if hasattr(widget, 'setText'):
            # Перезагрузить перевод для виджета
```
Но для текущей задачи это не нужно.

## Success Criteria
- [ ] Settings открывается без AttributeError
- [ ] Все строки в Settings показывают русский/английский текст (в зависимости от --lang)
- [ ] Главное окно не затронуто
