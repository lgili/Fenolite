# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``tools/release.py``, the steps of the release workflow (change c0221)."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
_spec = importlib.util.spec_from_file_location("release_tool", ROOT / "tools" / "release.py")
assert _spec and _spec.loader
release = importlib.util.module_from_spec(_spec)
sys.modules["release_tool"] = release
_spec.loader.exec_module(release)

CHANGELOG = """# Changelog

## [Unreleased]

## [1.2.0] - 2026-11-01

### Added

- a thing

### Fixed

- a bug

## [1.1.0] - 2026-10-01

### Added

- older
"""


def source(tmp_path: Path, version: str = "1.2.0", pin: str | None = None) -> Path:
    (tmp_path / "src" / "fenolite").mkdir(parents=True)
    (tmp_path / "src" / "fenolite" / "__init__.py").write_text(f'__version__ = "{version}"\n')
    (tmp_path / "packaging" / "phenolite").mkdir(parents=True)
    (tmp_path / "packaging" / "phenolite" / "pyproject.toml").write_text(
        f'[project]\nname = "phenolite"\nversion = "{version}"\n'
        f'dependencies = ["fenolite=={pin or version}"]\n'
    )
    (tmp_path / "CHANGELOG.md").write_text(CHANGELOG)
    return tmp_path


def test_check_agrees(tmp_path: Path) -> None:
    assert release.check(source(tmp_path), "v1.2.0") == []


def test_check_names_each_disagreement(tmp_path: Path) -> None:
    problems = release.check(source(tmp_path, version="1.3.0", pin="1.2.0"), "v1.3.0")
    assert any("alias does not pin fenolite==1.3.0" in p for p in problems)
    assert any("no section ## [1.3.0]" in p for p in problems)
    assert any("__version__" in p for p in release.check(source(tmp_path / "b"), "v1.1.0"))


def test_bad_tag_refused() -> None:
    with pytest.raises(release.ReleaseError):
        release.version_of("1.2.0")
    assert release.version_of("v1.2.0rc1") == "1.2.0rc1"


def test_changelog_section() -> None:
    date, body = release.changelog_section(CHANGELOG, "1.2.0")
    assert date == "2026-11-01" and "- a bug" in body and "older" not in body
    with pytest.raises(release.ReleaseError, match="empty"):
        release.changelog_section("## [2.0.0]\n\n## [1.0.0]\n- x\n", "2.0.0")


def test_notes(tmp_path: Path) -> None:
    wheel = tmp_path / "fenolite-1.2.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    text = release.notes(
        tag="v1.2.0", changelog=CHANGELOG, files=[wheel], previous="v1.1.0", run_url="https://run",
        record=True, on_pypi=True,
    )  # fmt: skip
    assert text.startswith("# Fenolite 1.2.0\n")
    assert "pip install fenolite==1.2.0" in text and "pypi.org/project/phenolite/1.2.0/" in text
    assert "compare/v1.1.0...v1.2.0" in text and "docs/release/v1.2.md" in text
    assert f"| `{wheel.name}` | `{hashlib.sha256(b'wheel').hexdigest()}` |" in text
    assert "### Fixed\n\n- a bug" in text and "older" not in text


def test_notes_stay_below_the_limit(tmp_path: Path) -> None:
    long = CHANGELOG.replace("- a thing", "\n".join(f"- entry {i} " + "x" * 200 for i in range(800)))
    text = release.notes(tag="v1.2.0", changelog=long, files=[], previous=None, run_url=None, record=False,
                         on_pypi=False)  # fmt: skip
    assert len(text) <= release.BODY_LIMIT and text.rstrip().endswith("CHANGELOG.md).")


def test_latest() -> None:
    tags = ["v0.4.0", "v0.5.0", "v0.0.1.dev0", "junk"]
    assert release.latest("v0.5.0", tags)
    assert not release.latest("v0.4.1", tags)
    assert release.latest("v0.6.0", tags)
    assert not release.latest("v0.6.0rc1", tags)


def test_pypi_files(tmp_path: Path) -> None:
    files = {"fenolite-1.2.0.tar.gz": b"core", "phenolite-1.2.0.tar.gz": b"alias"}

    def fetch(url: str) -> bytes:
        for name in ("fenolite", "phenolite"):
            if url == f"https://pypi.org/pypi/{name}/1.2.0/json":
                filename = f"{name}-1.2.0.tar.gz"
                digest = hashlib.sha256(files[filename]).hexdigest()
                return json.dumps({"urls": [{"filename": filename, "url": "f/" + filename,
                                             "digests": {"sha256": digest}}]}).encode()  # fmt: skip
        return files[url.removeprefix("f/")]

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "fenolite-1.2.0.tar.gz").write_bytes(b"rebuilt")
    written = release.pypi_files("v1.2.0", dist, fetch)
    assert sorted(p.name for p in written) == sorted(files)
    assert (dist / "fenolite-1.2.0.tar.gz").read_bytes() == b"core"
    files["phenolite-1.2.0.tar.gz"] = b"tampered"
    with pytest.raises(release.ReleaseError, match="SHA-256"):
        release.pypi_files("v1.2.0", dist, lambda url: fetch(url) if "json" in url else b"other")


def test_pypi_files_before_publication(tmp_path: Path) -> None:
    def missing(url: str) -> bytes:
        raise OSError("404")

    dist = tmp_path / "dist"
    dist.mkdir()
    (dist / "fenolite-1.2.0.tar.gz").write_bytes(b"built")
    assert release.pypi_files("v1.2.0", dist, missing) == []
    assert (dist / "fenolite-1.2.0.tar.gz").read_bytes() == b"built"
