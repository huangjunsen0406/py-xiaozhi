"""Shared GUI/TUI keyword transactions keep config and complete file contents paired."""

import json
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import Mock

import pytest

from src.ui.tui import settings_data
from src.utils import keyword_writer
from src.utils.config_manager import ConfigManager


@pytest.fixture(params=["gui", "tui"])
def save_word(request, monkeypatch, tmp_path):
    monkeypatch.setattr(
        "src.utils.resource_finder.get_keywords_dir", lambda: tmp_path / "keywords"
    )
    if request.param == "gui":
        pytest.importorskip("PySide6.QtCore")
        from src.ui.gui.models.settings_model import SettingsModel

        monkeypatch.setattr(
            "src.ui.gui.models.settings.wake_word.convert_wake_word",
            lambda word: ("TEST @test", "en", "models/en"),
        )

        def save(config):
            model = SettingsModel(config_manager=config)
            try:
                model._wake_word = "test"
                result = model.saveWakeWord()
                return result, model._error
            finally:
                model.close()
    else:
        monkeypatch.setattr(
            settings_data,
            "preview_wake_word",
            lambda word: ("TEST @test", "en", "models/en"),
        )

        def save(config):
            return settings_data.save_settings(
                {"WAKE_WORD_OPTIONS.WAKE_WORD": "test"}, config
            )

    return save


def test_rejected_config_restores_previous_keyword_bytes(
    save_word, tmp_path, monkeypatch
):
    config = ConfigManager(tmp_path / "config.json")
    target = tmp_path / "keywords/en_keywords.txt"
    target.parent.mkdir()
    target.write_bytes(b"previous\r\nbytes\n")
    before, disk = config.get_config(""), config.config_file.read_bytes()
    original = keyword_writer.os.replace

    def replace(source, destination):
        if Path(destination) == config.config_file:
            raise OSError("injected config replace failure")
        return original(source, destination)

    monkeypatch.setattr(keyword_writer.os, "replace", replace)
    ok, error = save_word(config)
    assert not ok and "保存配置失败" in error
    assert target.read_bytes() == b"previous\r\nbytes\n"
    assert config.get_config("") == before
    assert config.config_file.read_bytes() == disk
    assert list(target.parent.iterdir()) == [target]


def test_failed_keyword_replace_prevents_config_commit(
    save_word, tmp_path, monkeypatch
):
    config = ConfigManager.from_dict()
    target = tmp_path / "keywords/en_keywords.txt"
    target.parent.mkdir()
    target.write_text("old\n")
    commit = Mock(wraps=config.commit_draft)
    monkeypatch.setattr(config, "commit_draft", commit)
    monkeypatch.setattr(
        keyword_writer.os, "replace", Mock(side_effect=OSError("keyword denied"))
    )
    ok, error = save_word(config)
    assert not ok and "keyword denied" in error
    assert target.read_text() == "old\n"
    assert list(target.parent.iterdir()) == [target]
    commit.assert_not_called()


def test_post_write_reload_failure_preserves_matching_disk_pair(
    save_word, tmp_path, monkeypatch
):
    config = ConfigManager(tmp_path / "config.json")
    before = config.get_config("")
    monkeypatch.setattr(config, "reload_config", lambda **kwargs: False)
    ok, error = save_word(config)
    assert not ok and "已写入" in error
    assert config.get_config("") == before
    assert (
        json.loads(config.config_file.read_text())["WAKE_WORD_OPTIONS"]["WAKE_WORD"]
        == "test"
    )
    assert (tmp_path / "keywords/en_keywords.txt").read_text() == "TEST @test\n"


def test_rollback_failure_is_explicit(save_word, tmp_path, monkeypatch):
    config = ConfigManager.from_dict()
    target = tmp_path / "keywords/en_keywords.txt"
    target.parent.mkdir()
    target.write_text("old\n")
    monkeypatch.setattr(config, "commit_draft", lambda draft: "rejected")
    original = keyword_writer.os.replace
    writes = 0

    def replace(source, destination):
        nonlocal writes
        writes += 1
        if writes > 1:
            raise OSError("cannot restore")
        return original(source, destination)

    monkeypatch.setattr(keyword_writer.os, "replace", replace)
    ok, error = save_word(config)
    assert not ok and "恢复旧关键词失败" in error
    assert target.read_text() == "TEST @test\n"
    assert list(target.parent.iterdir()) == [target]


def test_concurrent_keyword_commits_leave_final_config_and_file_paired(
    tmp_path, monkeypatch
):
    config = ConfigManager(tmp_path / "config.json")
    monkeypatch.setattr(
        "src.utils.resource_finder.get_keywords_dir", lambda: tmp_path / "keywords"
    )
    barrier = threading.Barrier(4)

    def save(index):
        draft = config.get_config("")
        draft["WAKE_WORD_OPTIONS"].update(
            WAKE_WORD=f"word-{index}", WAKE_WORD_LANG="en", MODEL_PATH="models/en"
        )
        barrier.wait(timeout=3)
        return keyword_writer.commit_with_keywords(config, draft, "en", f"word-{index}")

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(save, range(4))) == [None] * 4
    final_word = config.get_config("WAKE_WORD_OPTIONS.WAKE_WORD")
    assert (tmp_path / "keywords/en_keywords.txt").read_text() == final_word + "\n"
    assert (
        json.loads(config.config_file.read_text())["WAKE_WORD_OPTIONS"]["WAKE_WORD"]
        == final_word
    )
