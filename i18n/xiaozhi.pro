# Qt Linguist project file for py-xiaozhi i18n
# Generated for pylupdate5

SOURCES = ../src/application.py \
          ../src/audio_codecs/aec_processor.py \
          ../src/audio_codecs/audio_codec.py \
          ../src/audio_codecs/music_decoder.py \
          ../src/audio_processing/wake_word_detect.py \
          ../src/constants/constants.py \
          ../src/constants/system.py \
          ../src/core/ota.py \
          ../src/core/system_initializer.py \
          ../src/display/base_display.py \
          ../src/display/cli_display.py \
          ../src/display/gui_display.py \
          ../src/display/gui_display_model.py \
          ../src/iot/thing.py \
          ../src/iot/thing_manager.py \
          ../src/iot/things/lamp.py \
          ../src/mcp/mcp_server.py \
          ../src/mcp/tools/bazi/bazi_calculator.py \
          ../src/mcp/tools/bazi/engine.py \
          ../src/mcp/tools/bazi/marriage_analyzer.py \
          ../src/mcp/tools/bazi/marriage_tools.py \
          ../src/mcp/tools/bazi/models.py \
          ../src/mcp/tools/bazi/professional_analyzer.py \
          ../src/mcp/tools/bazi/professional_data.py \
          ../src/mcp/tools/bazi/tools.py \
          ../src/mcp/tools/calendar/database.py \
          ../src/mcp/tools/calendar/manager.py \
          ../src/mcp/tools/calendar/models.py \
          ../src/mcp/tools/calendar/reminder_service.py \
          ../src/mcp/tools/calendar/tools.py \
          ../src/mcp/tools/camera/base_camera.py \
          ../src/mcp/tools/camera/camera.py \
          ../src/mcp/tools/camera/normal_camera.py \
          ../src/mcp/tools/camera/vl_camera.py \
          ../src/mcp/tools/music/manager.py \
          ../src/mcp/tools/music/music_player.py \
          ../src/mcp/tools/screenshot/screenshot_camera.py \
          ../src/mcp/tools/system/app_management/killer.py \
          ../src/mcp/tools/system/app_management/launcher.py \
          ../src/mcp/tools/system/app_management/scanner.py \
          ../src/mcp/tools/system/app_management/utils.py \
          ../src/mcp/tools/system/manager.py \
          ../src/mcp/tools/system/tools.py \
          ../src/mcp/tools/timer/manager.py \
          ../src/mcp/tools/timer/timer_service.py \
          ../src/mcp/tools/timer/tools.py \
          ../src/network/mqtt_client.py \
          ../src/plugins/audio.py \
          ../src/plugins/base.py \
          ../src/plugins/calendar.py \
          ../src/plugins/iot.py \
          ../src/plugins/manager.py \
          ../src/plugins/mcp.py \
          ../src/plugins/shortcuts.py \
          ../src/plugins/ui.py \
          ../src/plugins/wake_word.py \
          ../src/protocols/mqtt_protocol.py \
          ../src/protocols/protocol.py \
          ../src/protocols/websocket_protocol.py \
          ../src/utils/audio_utils.py \
          ../src/utils/common_utils.py \
          ../src/utils/config_manager.py \
          ../src/utils/device_activator.py \
          ../src/utils/device_fingerprint.py \
          ../src/utils/logging_config.py \
          ../src/utils/opus_loader.py \
          ../src/utils/resource_finder.py \
          ../src/utils/volume_controller.py \
          ../src/views/activation/activation_model.py \
          ../src/views/activation/activation_window.py \
          ../src/views/activation/cli_activation.py \
          ../src/views/base/async_mixins.py \
          ../src/views/base/base_window.py \
          ../src/views/components/system_tray.py \
          ../src/views/settings/settings_window.py \
          ../src/views/settings/components/audio/audio_widget.py \
          ../src/views/settings/components/camera/camera_widget.py \
          ../src/views/settings/components/shortcuts_settings.py \
          ../src/views/settings/components/system_options/system_options_widget.py \
          ../src/views/settings/components/wake_word/wake_word_widget.py \
          ../src/display/gui_display.qml \
          ../src/views/activation/activation_window.qml

CODECFORTR = UTF-8
SOURCELANGUAGE = zh_CN

TRANSLATIONS = source/xiaozhi_zh_CN.ts \
               source/xiaozhi_en_US.ts \
               source/xiaozhi_ru_RU.ts

# Exclude third-party and generated content
EXCLUDE = ../libs/ \
         ../models/ \
         ../cache/ \
         ../.venv/ \
         ../__pycache__/ \
         *.pyc