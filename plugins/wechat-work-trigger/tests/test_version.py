from pathlib import Path

import pytest

from scripts import version


def test_check_versions_keeps_manifest_schema_version_separate(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    manifest = tmp_path / "manifest.yaml"
    pyproject.write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")
    manifest.write_text("version: 1.2.3\nmeta:\n  version: 0.0.2\n", encoding="utf-8")
    monkeypatch.setattr(version, "PYPROJECT_PATH", pyproject)
    monkeypatch.setattr(version, "MANIFEST_PATH", manifest)

    assert version.check_versions() == "1.2.3"


def test_set_version_does_not_change_manifest_schema_version(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    pyproject = tmp_path / "pyproject.toml"
    manifest = tmp_path / "manifest.yaml"
    pyproject.write_text('[project]\nversion = "1.2.3"\n', encoding="utf-8")
    manifest.write_text("version: 1.2.3\nmeta:\n  version: 0.0.2\n", encoding="utf-8")
    monkeypatch.setattr(version, "PYPROJECT_PATH", pyproject)
    monkeypatch.setattr(version, "MANIFEST_PATH", manifest)

    version.set_version("1.2.4")

    assert "version: 1.2.4" in manifest.read_text(encoding="utf-8")
    assert "  version: 0.0.2" in manifest.read_text(encoding="utf-8")
