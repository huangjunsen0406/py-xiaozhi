"""Configuration draft transactions independent of Qt and user directories."""

import json
from unittest.mock import Mock

import pytest

import src.utils.config_manager as config_module
import src.utils.resource_finder as resource_finder
from src.utils.config_manager import ConfigManager


@pytest.fixture(autouse=True)
def forbid_user_paths(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("draft commit accessed user paths or applied PATHS")

    monkeypatch.setattr(config_module, "get_user_data_dir", forbidden)
    monkeypatch.setattr(config_module, "get_config_dir", forbidden)
    monkeypatch.setattr(resource_finder, "apply_path_overrides_from_config", forbidden)


@pytest.fixture(params=["memory", "file"])
def config(request, tmp_path):
    if request.param == "memory":
        return ConfigManager.from_dict()
    return ConfigManager(config_file=tmp_path / "config.json")


class Uncopyable:
    def __deepcopy__(self, memo):
        raise RuntimeError("injected copy failure")


def test_memory_commit_is_independent_and_does_not_use_file_operations(monkeypatch):
    config = ConfigManager.from_dict()
    save = Mock(side_effect=AssertionError("memory commit wrote a file"))
    reload = Mock(side_effect=AssertionError("memory commit reloaded a file"))
    monkeypatch.setattr(config, "_save_config", save)
    monkeypatch.setattr(config, "reload_config", reload)
    draft = config.get_config("")
    draft["SYSTEM_OPTIONS"]["DEVICE_ID"] = "committed"
    draft["MCP_TOOLS"]["DISABLED"] = ["music_player.stop"]

    assert config.commit_draft(draft) is None
    assert config.get_config("") == draft
    draft["MCP_TOOLS"]["DISABLED"].append("draft-only")
    assert config.get_config("MCP_TOOLS.DISABLED") == ["music_player.stop"]
    config.get_config("MCP_TOOLS.DISABLED").append("runtime-only")
    assert draft["MCP_TOOLS"]["DISABLED"] == ["music_player.stop", "draft-only"]
    save.assert_not_called()
    reload.assert_not_called()


def test_file_commit_writes_then_reloads_without_applying_paths(monkeypatch, tmp_path):
    config = ConfigManager(config_file=tmp_path / "config.json")
    draft = config.get_config("")
    draft["SYSTEM_OPTIONS"]["DEVICE_ID"] = "磁盘草稿"
    draft["PATHS"]["CACHE_DIR"] = str(tmp_path / "unused-cache")
    draft["MCP_TOOLS"]["DISABLED"] = ["music_player.stop"]
    original_reload = config.reload_config

    def reload_after_write(*, apply_paths, strict):
        assert apply_paths is False
        assert strict is True
        assert json.loads(config.config_file.read_text(encoding="utf-8")) == draft
        assert config.get_config("SYSTEM_OPTIONS.DEVICE_ID") != "磁盘草稿"
        return original_reload(apply_paths=apply_paths, strict=strict)

    reload = Mock(side_effect=reload_after_write)
    save = Mock(wraps=config._save_config)
    monkeypatch.setattr(config, "reload_config", reload)
    monkeypatch.setattr(config, "_save_config", save)

    assert config.commit_draft(draft) is None
    assert config.get_config("") == draft
    reload.assert_called_once_with(apply_paths=False, strict=True)
    save.assert_called_once()
    assert save.call_args.args[0] is not draft
    assert not config.config_file.with_suffix(".tmp").exists()
    assert not (tmp_path / "unused-cache").exists()
    draft["MCP_TOOLS"]["DISABLED"].append("draft-only")
    assert config.get_config("MCP_TOOLS.DISABLED") == ["music_player.stop"]
    config.get_config("MCP_TOOLS.DISABLED").append("runtime-only")
    assert draft["MCP_TOOLS"]["DISABLED"] == ["music_player.stop", "draft-only"]


def test_copy_failure_keeps_runtime_and_disk(config):
    before = config.get_config("")
    disk_before = config.config_file.read_bytes() if config.config_file else None
    draft = config.get_config("")
    draft["UNCOPYABLE"] = Uncopyable()

    error = config.commit_draft(draft)

    assert isinstance(error, str) and "复制失败" in error
    assert config.get_config("") == before
    assert isinstance(draft["UNCOPYABLE"], Uncopyable)
    if config.config_file:
        assert config.config_file.read_bytes() == disk_before


def test_runtime_snapshot_copy_failure_does_not_write(monkeypatch, tmp_path):
    config = ConfigManager(config_file=tmp_path / "config.json")
    draft = config.get_config("")
    uncopyable = Uncopyable()
    config.update_config("UNCOPYABLE", uncopyable, save=False)
    save = Mock(wraps=config._save_config)
    monkeypatch.setattr(config, "_save_config", save)
    before = config.config_file.read_bytes()

    error = config.commit_draft(draft)

    assert isinstance(error, str) and "复制失败" in error
    assert config.get_config("UNCOPYABLE") is uncopyable
    assert config.config_file.read_bytes() == before
    save.assert_not_called()


def test_replace_failure_keeps_previous_disk_and_runtime(monkeypatch, tmp_path):
    config = ConfigManager(config_file=tmp_path / "config.json")
    before = config.get_config("")
    disk_before = config.config_file.read_bytes()
    draft = config.get_config("")
    draft["SYSTEM_OPTIONS"]["DEVICE_ID"] = "uncommitted"
    reload = Mock(wraps=config.reload_config)
    monkeypatch.setattr(config, "reload_config", reload)
    monkeypatch.setattr(
        config_module.os,
        "replace",
        Mock(side_effect=PermissionError("injected replace failure")),
    )

    error = config.commit_draft(draft)

    assert isinstance(error, str) and "保存配置失败" in error
    assert "已写入" not in error
    assert config.config_file.read_bytes() == disk_before
    assert config.get_config("") == before
    assert draft["SYSTEM_OPTIONS"]["DEVICE_ID"] == "uncommitted"
    reload.assert_not_called()


@pytest.mark.parametrize("save_error", [False, RuntimeError("injected save failure")])
def test_save_failure_does_not_reload(monkeypatch, tmp_path, save_error):
    config = ConfigManager(config_file=tmp_path / "config.json")
    before = config.get_config("")
    disk_before = config.config_file.read_bytes()
    draft = config.get_config("")
    draft["SYSTEM_OPTIONS"]["DEVICE_ID"] = "uncommitted"
    save = Mock()
    if isinstance(save_error, Exception):
        save.side_effect = save_error
    else:
        save.return_value = save_error
    reload = Mock(wraps=config.reload_config)
    monkeypatch.setattr(config, "_save_config", save)
    monkeypatch.setattr(config, "reload_config", reload)

    error = config.commit_draft(draft)

    assert isinstance(error, str) and "保存配置失败" in error
    assert "已写入" not in error
    assert config.get_config("") == before
    assert config.config_file.read_bytes() == disk_before
    reload.assert_not_called()


@pytest.mark.parametrize("raises", [False, True])
def test_reload_failure_restores_runtime_but_preserves_written_draft(
    monkeypatch, tmp_path, raises
):
    config = ConfigManager(config_file=tmp_path / "config.json")
    config.update_config("SYSTEM_OPTIONS.DEVICE_ID", "runtime-only", save=False)
    before = config.get_config("")
    draft = config.get_config("")
    draft["SYSTEM_OPTIONS"]["DEVICE_ID"] = "disk-only"
    original_reload = config.reload_config

    def failed_reload(*, apply_paths, strict):
        assert apply_paths is False
        assert strict is True
        config.update_config(
            "SYSTEM_OPTIONS.DEVICE_ID", "partially-applied", save=False
        )
        config.get_config("MCP_TOOLS.DISABLED").append("partially-applied")
        if raises:
            raise RuntimeError("injected reload failure")
        return False

    monkeypatch.setattr(config, "reload_config", failed_reload)

    error = config.commit_draft(draft)

    assert isinstance(error, str) and "已写入" in error and "运行时" in error
    assert config.get_config("") == before
    assert json.loads(config.config_file.read_text(encoding="utf-8")) == draft
    assert draft["SYSTEM_OPTIONS"]["DEVICE_ID"] == "disk-only"
    assert draft["MCP_TOOLS"]["DISABLED"] == []

    monkeypatch.setattr(config, "reload_config", original_reload)
    assert config.commit_draft(draft) is None
    assert config.get_config("") == draft


@pytest.mark.parametrize("read_result", [OSError("injected read failure"), "{", "[]"])
def test_real_loader_failure_preserves_written_draft_and_runtime(
    monkeypatch, tmp_path, read_result
):
    from pathlib import Path

    config = ConfigManager(config_file=tmp_path / "config.json")
    config.update_config("SYSTEM_OPTIONS.DEVICE_ID", "runtime", save=False)
    before = config.get_config("")
    draft = config.get_config("")
    draft["SYSTEM_OPTIONS"]["DEVICE_ID"] = "draft"
    original_read = Path.read_text
    save = Mock(wraps=config._save_config)
    monkeypatch.setattr(config, "_save_config", save)
    backup = Mock(side_effect=AssertionError("commit attempted startup recovery"))
    monkeypatch.setattr(config, "_backup_corrupt_config", backup)

    def failed_read(path, *args, **kwargs):
        if path == config.config_file:
            if isinstance(read_result, Exception):
                raise read_result
            return read_result
        return original_read(path, *args, **kwargs)

    with monkeypatch.context() as read_patch:
        read_patch.setattr(Path, "read_text", failed_read)
        error = config.commit_draft(draft)

    assert error is not None and "已写入" in error and "运行时" in error
    assert config.get_config("") == before
    assert json.loads(config.config_file.read_text(encoding="utf-8")) == draft
    save.assert_called_once()
    backup.assert_not_called()
    assert config.commit_draft(draft) is None
    assert config.get_config("") == draft
