"""Keep runtime, distribution and release-lock versions in agreement."""

import re
import subprocess
from pathlib import Path

import pytest
from packaging.version import Version

try:
    import tomllib
except ModuleNotFoundError:
    import tomli as tomllib

import release

ROOT = Path(__file__).resolve().parents[1]


def test_package_version_comes_from_runtime_constant():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert "version" not in project["project"]
    assert "version" in project["project"]["dynamic"]
    config = project["tool"]["hatch"]["version"]
    assert config["path"] == "src/constants/system.py"
    source = (ROOT / config["path"]).read_text(encoding="utf-8")
    version = re.search(config["pattern"], source).group("version")
    assert version == release.read_system_constants()["APP_VERSION"]
    assert Version(version).release
    lock = tomllib.loads((ROOT / "uv.lock").read_text(encoding="utf-8"))
    (package,) = [item for item in lock["package"] if item["name"] == "py-xiaozhi"]
    assert "version" not in package
    assert package["source"] == {"editable": "."}


@pytest.fixture
def release_files(tmp_path, monkeypatch):
    constants = tmp_path / "constants.py"
    constants.write_text(
        "class SystemConstants:\n"
        '    APP_NAME = "py-xiaozhi"\n'
        '    APP_DISPLAY_NAME = "小智"\n'
        '    APP_VERSION = "1.2.3"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr(release, "SYSTEM_PY", constants)
    monkeypatch.setattr(release, "BUILD_JSON", tmp_path / "build-config.json")
    monkeypatch.setattr(release.sys, "argv", ["release.py"])
    monkeypatch.setattr("builtins.input", lambda _: "1")
    return constants


@pytest.mark.parametrize(
    ("choice", "expected"), [("1", "1.2.4"), ("4", "1.2.4-beta.0")]
)
def test_release_updates_lock_before_git(release_files, monkeypatch, choice, expected):
    calls = []
    monkeypatch.setattr("builtins.input", lambda _: choice)

    def run(command, **kwargs):
        assert kwargs["check"] is True
        assert release.read_system_constants()["APP_VERSION"] == expected
        calls.append(command)

    monkeypatch.setattr(release.subprocess, "run", run)
    release.main()
    assert calls[0] == ["uv", "lock"]
    assert calls[1] == [
        "git",
        "add",
        str(release_files),
        str(release.BUILD_JSON),
        "uv.lock",
    ]
    assert calls[-1] == ["git", "push", "--follow-tags"]


def test_release_stops_before_git_when_lock_fails(release_files, monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(release.subprocess, "run", run)
    with pytest.raises(subprocess.CalledProcessError):
        release.main()
    assert calls == [["uv", "lock"]]
