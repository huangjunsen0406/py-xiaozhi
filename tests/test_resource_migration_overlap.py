"""Migration overlap must be rejected without creating/activating its destination."""

import pytest

from src.utils import resource_finder as rf
from src.utils.config_manager import ConfigManager


@pytest.fixture(autouse=True)
def isolated_paths(tmp_path, monkeypatch):
    monkeypatch.setenv(rf.ENV_DATA_DIR, str(tmp_path / "data"))
    for name in (
        rf.ENV_CACHE_DIR,
        rf.ENV_LOG_DIR,
        rf.ENV_MUSIC_CACHE_DIR,
        rf.ENV_KEYWORDS_DIR,
    ):
        monkeypatch.delenv(name, raising=False)
    for name in (
        "_override_cache",
        "_override_log",
        "_override_music",
        "_override_keywords",
    ):
        monkeypatch.setattr(rf, name, None)
    monkeypatch.setattr(rf, "_log_migration", lambda *args: None)
    rf.clear_path_caches()
    yield
    rf.clear_path_caches()


@pytest.mark.parametrize("copy", [True, False])
@pytest.mark.parametrize("existing_destination", [False, True])
def test_nested_destination_rejected_without_copying_or_deleting(
    tmp_path, copy, existing_destination
):
    source = tmp_path / "cache"
    source.mkdir()
    seed = source / "seed.bin"
    seed.write_bytes(b"original")
    destination = source / "nested"
    if existing_destination:
        destination.mkdir()
        (destination / "user.bin").write_bytes(b"user")
    before = sorted(p.relative_to(source) for p in source.rglob("*"))
    for _ in range(3):
        result = rf.migrate_directory(source, destination, copy=copy)
        assert not result["ok"]
        assert "overlap" in result["error"]
        assert result["files_copied"] == 0
        assert sorted(p.relative_to(source) for p in source.rglob("*")) == before
        assert seed.read_bytes() == b"original"
    assert destination.exists() == existing_destination
    if existing_destination:
        assert (destination / "user.bin").read_bytes() == b"user"


def test_parent_destination_rejected_without_touching_files(tmp_path):
    source = tmp_path / "parent" / "child"
    source.mkdir(parents=True)
    (source / "seed.bin").write_bytes(b"seed")
    (source.parent / "seed.bin").write_bytes(b"user")
    result = rf.migrate_directory(source, source.parent)
    assert not result["ok"]
    assert (source / "seed.bin").read_bytes() == b"seed"
    assert (source.parent / "seed.bin").read_bytes() == b"user"
    assert sorted(p.name for p in source.iterdir()) == ["seed.bin"]


def test_resolved_symlink_overlap_is_rejected(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    alias = tmp_path / "alias"
    alias.symlink_to(source, target_is_directory=True)
    (source / "seed.bin").write_bytes(b"seed")
    result = rf.migrate_directory(source, alias / "nested")
    assert not result["ok"]
    assert not (source / "nested").exists()
    assert rf.migrate_directory(source, alias)["skipped"] == "same_path"
    assert (source / "seed.bin").read_bytes() == b"seed"


def test_missing_source_overlap_does_not_create_directories(tmp_path):
    source = tmp_path / "missing"
    assert not rf.migrate_directory(source, source / "nested")["ok"]
    assert not source.exists()


@pytest.mark.parametrize(
    ("key", "getter", "kind"),
    [
        ("CACHE_DIR", rf.get_user_cache_dir, "cache"),
        ("LOG_DIR", rf.get_user_log_dir, "logs"),
        ("MUSIC_CACHE_DIR", rf.get_music_cache_dir, "music"),
        ("KEYWORDS_DIR", rf.get_keywords_dir, "keywords"),
    ],
)
def test_startup_rejects_nested_override_before_activation(key, getter, kind):
    source = getter().resolve()
    seed = source / "seed.bin"
    seed.write_bytes(b"seed")
    destination = source / "nested"
    config = ConfigManager.from_dict({"PATHS": {key: str(destination)}})
    for _ in range(3):
        rf.clear_path_overrides(all=True)
        results = rf.apply_path_overrides_from_config(config, migrate=True)
        failure = next(r for r in results if r["kind"] == kind)
        assert not failure["ok"]
        assert "overlap" in failure["error"]
        assert getter().resolve() == source
        assert not destination.exists()
        assert list(source.rglob("seed.bin")) == [seed]
        assert seed.read_bytes() == b"seed"


def test_rejected_override_does_not_activate_unrelated_destinations(tmp_path):
    source = rf.get_user_cache_dir()
    unrelated = tmp_path / "new-logs"
    config = ConfigManager.from_dict(
        {"PATHS": {"CACHE_DIR": str(source / "nested"), "LOG_DIR": str(unrelated)}}
    )
    results = rf.apply_path_overrides_from_config(config, migrate=True)
    assert any(not r["ok"] for r in results)
    assert rf.get_user_cache_dir() == source
    assert rf.get_user_log_dir() != unrelated
    assert not unrelated.exists()


def test_startup_rejects_symlink_alias_before_creating_target(tmp_path):
    source = rf.get_user_cache_dir()
    alias = tmp_path / "alias"
    alias.symlink_to(source, target_is_directory=True)
    config = ConfigManager.from_dict({"PATHS": {"CACHE_DIR": str(alias / "nested")}})
    results = rf.apply_path_overrides_from_config(config, migrate=True)
    assert any(not r["ok"] for r in results)
    assert not (source / "nested").exists()
    assert rf.get_user_cache_dir() == source


def test_disjoint_migration_preserves_source_and_existing_destination(tmp_path):
    source = rf.get_user_cache_dir()
    (source / "seed.bin").write_bytes(b"seed")
    (source / "existing.bin").write_bytes(b"source")
    (source / "music").mkdir()
    (source / "music" / "song.bin").write_bytes(b"music")
    destination = tmp_path / "relocated"
    destination.mkdir()
    (destination / "existing.bin").write_bytes(b"user")
    config = ConfigManager.from_dict({"PATHS": {"CACHE_DIR": str(destination)}})
    for _ in range(3):
        rf.clear_path_overrides(all=True)
        assert all(r["ok"] for r in rf.apply_path_overrides_from_config(config))
        assert rf.get_user_cache_dir() == destination
        assert (destination / "seed.bin").read_bytes() == b"seed"
        assert (destination / "existing.bin").read_bytes() == b"user"
        assert (destination / "music" / "song.bin").read_bytes() == b"music"
        assert (source / "existing.bin").read_bytes() == b"source"
        assert len(list(destination.rglob("seed.bin"))) == 1


def test_environment_override_still_precedes_invalid_config(tmp_path, monkeypatch):
    destination = tmp_path / "env-cache"
    monkeypatch.setenv(rf.ENV_CACHE_DIR, str(destination))
    config = ConfigManager.from_dict(
        {"PATHS": {"CACHE_DIR": str(destination / "nested")}}
    )
    assert rf.apply_path_overrides_from_config(config) == []
    assert rf.get_user_cache_dir() == destination
    assert not (destination / "nested").exists()


def test_existing_target_remains_active_when_new_nested_override_is_rejected(tmp_path):
    current = tmp_path / "current"
    rf.set_path_overrides(cache=current)
    rf.get_user_cache_dir()
    config = ConfigManager.from_dict({"PATHS": {"CACHE_DIR": str(current / "nested")}})
    assert any(not r["ok"] for r in rf.apply_path_overrides_from_config(config))
    assert rf.get_user_cache_dir() == current
    assert not (current / "nested").exists()
