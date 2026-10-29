"""Resource layouts for source checkouts, wheels and frozen applications."""

import sys
from pathlib import Path

import pytest

from src.utils import resource_finder as resources


@pytest.mark.parametrize("layout", ["source", "wheel", "frozen"])
def test_resource_layout_preserves_python_import_root(tmp_path, monkeypatch, layout):
    app_root = tmp_path / "application"
    package = app_root / "src"
    embedded = package / "_resources"
    if layout == "wheel":
        embedded.mkdir(parents=True)
    monkeypatch.setattr(
        resources, "__file__", str(package / "utils" / "resource_finder.py")
    )
    monkeypatch.setattr(resources, "get_app_root", lambda: app_root)
    monkeypatch.setattr(sys, "frozen", layout == "frozen", raising=False)
    expected = embedded if layout == "wheel" else app_root
    assert resources.get_resource_root() == expected
    assert resources.get_assets_dir() == expected / "assets"
    assert resources.get_models_dir() == expected / "models"
    assert resources.get_config_dir() == expected / "config"
    assert resources.get_app_root() == app_root
    assert not (expected / "config").exists()


def test_english_converter_uses_resolved_model_directory(monkeypatch, tmp_path):
    from src.audio_processing.keyword_converters.bpe_converter import BpeConverter

    monkeypatch.setattr(resources, "get_models_dir", lambda: tmp_path / "models")
    assert (
        BpeConverter()._get_tokens_path() == tmp_path / "models" / "en" / "tokens.txt"
    )
    custom = Path("/custom/tokens.txt")
    assert BpeConverter(str(custom))._get_tokens_path() == custom
