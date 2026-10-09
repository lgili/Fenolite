# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The tools folder (capability routing, "Tools folder"; change c0078)."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from fenolite.core import tools
from fenolite.core.tools import TOOLS_ENV, tool_path, tools_dir

JAR = "freerouting-2.4.1.jar"


@pytest.fixture
def bare(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """No variable that names a folder, and a home folder of the test."""
    for name in (TOOLS_ENV, "XDG_CACHE_HOME", "LOCALAPPDATA"):
        monkeypatch.delenv(name, raising=False)
    home = tmp_path / "home"
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    return home


def test_explicit_folder(bare: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    folder = tmp_path / "kept" / "tools"
    monkeypatch.setenv(TOOLS_ENV, str(folder))
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))  # the explicit folder wins
    assert tools_dir() == folder
    assert tool_path("freerouting", JAR) == folder / "freerouting" / JAR
    assert not folder.exists() and not (tmp_path / "kept").exists()


def test_explicit_folder_is_read_at_each_call(
    bare: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv(TOOLS_ENV, str(tmp_path / "one"))
    assert tools_dir() == tmp_path / "one"
    monkeypatch.setenv(TOOLS_ENV, str(tmp_path / "two"))
    assert tools_dir() == tmp_path / "two"


def test_platform_defaults_cache_variable(
    bare: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    for platform in ("darwin", "win32", "linux"):
        monkeypatch.setattr(sys, "platform", platform)
        assert tools_dir() == tmp_path / "cache" / "fenolite" / "tools"


def test_platform_defaults_macos(bare: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "platform", "darwin")
    assert tools_dir() == bare / "Library" / "Caches" / "fenolite" / "tools"


def test_platform_defaults_windows(bare: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "win32")
    assert tools_dir() == bare / ".cache" / "fenolite" / "tools"  # without the variable: the last rule
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))
    assert tools_dir() == tmp_path / "local" / "fenolite" / "tools"


def test_platform_defaults_elsewhere(bare: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "local"))  # read on Windows only
    assert tools_dir() == bare / ".cache" / "fenolite" / "tools"
    assert not bare.exists()


def test_relative_folder_is_refused(bare: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(TOOLS_ENV, "tools")
    with pytest.raises(ValueError, match=TOOLS_ENV):
        tools_dir()
    with pytest.raises(ValueError, match=TOOLS_ENV):
        tool_path("freerouting", JAR)


def test_module_is_standard_library_only() -> None:
    source = Path(tools.__file__).read_text(encoding="utf-8")
    imports = [line.split()[1] for line in source.splitlines() if line.startswith(("import ", "from "))]
    assert sorted(imports) == ["__future__", "os", "pathlib", "sys"]
