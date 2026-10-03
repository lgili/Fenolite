# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``tools/kicad_libs_fetch.py`` on local ``file://`` tarballs (capability kicad-library-resolution,
"Library cache fetch"; change c0021). No test touches the network, and the files are authored here."""

from __future__ import annotations

import importlib.util
import io
import sys
import tarfile
import types
from pathlib import Path
from types import ModuleType

import pytest

from fenolite.backends.kicad import libcache

ROOT = Path(__file__).resolve().parents[2]
TAG, REPO = "10.0.6", "kicad-footprints"
COMMIT = "c" * 40
FILES = {"Mini.pretty/R.kicad_mod": b"(footprint R)", "LICENSE.md": b"authored for the test"}


def _load_tool() -> ModuleType:
    spec = importlib.util.spec_from_file_location("kicad_libs_fetch", ROOT / "tools" / "kicad_libs_fetch.py")
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _tarball(tmp_path: Path, members: dict[str, bytes], *, top: str = "kicad-footprints-abc/",
             link: str = "") -> Path:  # fmt: skip
    """The archive that the ``file://`` template of ``_pins`` names for ``COMMIT``."""
    path = tmp_path / "srv" / "kicad" / "libraries" / f"{REPO}-{COMMIT}.tar.gz"
    path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members.items():
            info = tarfile.TarInfo(name if name.startswith("..") else top + name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
        if link:
            info = tarfile.TarInfo(top + link)
            info.type = tarfile.SYMTYPE
            info.linkname = "LICENSE.md"
            tar.addfile(info)
    return path


def _tree(tmp_path: Path, members: dict[str, bytes]) -> tuple[str, int]:
    folder = tmp_path / "expected"
    for name, data in members.items():
        (folder / name).parent.mkdir(parents=True, exist_ok=True)
        (folder / name).write_bytes(data)
    return libcache.tree_hash(folder)


def _pins(tmp_path: Path, tree: str, files: int) -> Path:
    template = (tmp_path / "srv").as_uri() + "/{project}-{commit}.tar.gz"
    path = tmp_path / "libraries.toml"
    path.write_text(
        f'schema = 1\narchive = "{template}"\n\n[[pin]]\ntag = "{TAG}"\nmajor = 10\nrepo = "{REPO}"\n'
        f'project = "kicad/libraries/{REPO}"\ncommit = "{COMMIT}"\ntree = "{tree}"\nfiles = {files}\n',
        encoding="utf-8",
    )
    return path


@pytest.fixture
def tool() -> ModuleType:
    return _load_tool()


def _setup(tmp_path: Path, members: dict[str, bytes] = FILES) -> tuple[Path, Path, Path]:
    tree, files = _tree(tmp_path, FILES)
    return _pins(tmp_path, tree, files), tmp_path / "cache", _tarball(tmp_path, members)


def _leftovers(cache: Path) -> list[str]:
    return sorted(p.name for p in (cache / TAG).iterdir()) if (cache / TAG).is_dir() else []


def test_python_without_the_data_filter(tool: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
                                        capsys: pytest.CaptureFixture[str]) -> None:  # fmt: skip
    pins, cache, _ = _setup(tmp_path)
    monkeypatch.setattr(tool, "tarfile", types.SimpleNamespace(open=tarfile.open))
    assert tool.main(["--cache", str(cache), "--pins", str(pins)]) == 2
    assert "3.11.4" in capsys.readouterr().err and not cache.exists()


def test_fetch_stamp_and_move(tool: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pins, cache, _ = _setup(tmp_path)
    assert tool.main(["--cache", str(cache), "--pins", str(pins)]) == 0
    assert capsys.readouterr().out.strip() == f"{TAG}/{REPO}: fetched"
    (pin,) = libcache.load_pins(pins)
    assert libcache.stamp_matches(cache / TAG / REPO, pin)
    assert (cache / TAG / REPO / "Mini.pretty" / "R.kicad_mod").read_bytes() == b"(footprint R)"
    assert _leftovers(cache) == [REPO]


def test_cached_folders_are_not_downloaded_again(tool: ModuleType, tmp_path: Path,
                                                 capsys: pytest.CaptureFixture[str]) -> None:  # fmt: skip
    pins, cache, tarball = _setup(tmp_path)
    assert tool.main(["--cache", str(cache), "--pins", str(pins)]) == 0
    tarball.unlink()
    capsys.readouterr()
    assert tool.main(["--cache", str(cache), "--pins", str(pins)]) == 0
    assert capsys.readouterr().out.strip() == f"{TAG}/{REPO}: cached"
    assert tool.main(["--cache", str(cache), "--pins", str(pins), "--verify"]) == 0
    assert capsys.readouterr().out.strip() == f"{TAG}/{REPO}: verified"


def test_tree_mismatch(tool: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    _, cache, _ = _setup(tmp_path)
    pins = _pins(tmp_path, "0" * 64, 2)
    assert tool.main(["--cache", str(cache), "--pins", str(pins)]) == 5
    assert "failed" in capsys.readouterr().out
    assert not (cache / TAG / REPO).exists() and _leftovers(cache) == []


def test_unsafe_member(tool: ModuleType, tmp_path: Path) -> None:
    pins, cache, _ = _setup(tmp_path, FILES | {"../outside.txt": b"x"})
    assert tool.main(["--cache", str(cache), "--pins", str(pins)]) == 3
    assert not (cache / "outside.txt").exists() and not (cache.parent / "outside.txt").exists()
    assert not (cache / TAG / "outside.txt").exists()
    assert not (cache / TAG / REPO).exists() and _leftovers(cache) == []


def test_link_member_and_two_top_folders(tool: ModuleType, tmp_path: Path) -> None:
    pins, cache, _ = _setup(tmp_path)
    _tarball(tmp_path, FILES, link="alias")
    assert tool.main(["--cache", str(cache), "--pins", str(pins)]) == 3
    path = _tarball(tmp_path, FILES)
    with tarfile.open(path, "w:gz") as tar:
        for top in ("one/", "two/"):
            info = tarfile.TarInfo(top + "a.txt")
            info.size = 1
            tar.addfile(info, io.BytesIO(b"x"))
    assert tool.main(["--cache", str(cache), "--pins", str(pins)]) == 3
    assert _leftovers(cache) == []


def test_download_error(tool: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pins, cache, tarball = _setup(tmp_path)
    tarball.unlink()
    assert tool.main(["--cache", str(cache), "--pins", str(pins)]) == 3
    assert "download failed" in capsys.readouterr().out and _leftovers(cache) == []


def test_verify_finds_a_change(tool: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pins, cache, _ = _setup(tmp_path)
    assert tool.main(["--cache", str(cache), "--pins", str(pins)]) == 0
    (cache / TAG / REPO / "LICENSE.md").write_bytes(b"edited")
    capsys.readouterr()
    assert tool.main(["--cache", str(cache), "--pins", str(pins), "--verify"]) == 5
    assert str(cache / TAG / REPO) in capsys.readouterr().out


def test_older_folder_is_replaced(tool: ModuleType, tmp_path: Path) -> None:
    pins, cache, _ = _setup(tmp_path)
    old = cache / TAG / REPO
    old.mkdir(parents=True)
    (old / "stale.txt").write_text("old", encoding="utf-8")
    assert tool.main(["--cache", str(cache), "--pins", str(pins)]) == 0
    assert not (old / "stale.txt").exists() and (old / "LICENSE.md").is_file()
    assert _leftovers(cache) == [REPO]


def test_pin_printed(tool: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    pins, cache, _ = _setup(tmp_path)
    tree, files = _tree(tmp_path / "again", FILES)
    args = ["--cache", str(cache), "--pins", str(pins), "--print-pin", "--tag", TAG, "--repo", REPO]
    assert tool.main([*args, "--commit", COMMIT]) == 0
    out = capsys.readouterr().out
    assert f'commit = "{COMMIT}"' in out and f'tree = "{tree}"' in out and f"files = {files}" in out
    assert out.startswith("[[pin]]") and 'project = "kicad/libraries/kicad-footprints"' in out
    assert not (cache / TAG / REPO).exists()
    assert tool.main(args) == 2  # --commit is missing


def test_selection_and_usage(tool: ModuleType, tmp_path: Path) -> None:
    pins, cache, _ = _setup(tmp_path)
    assert tool.main(["--cache", str(cache), "--pins", str(pins), "--tag", "9.0.9"]) == 2
    assert tool.main(["--cache", str(cache), "--pins", str(tmp_path / "missing.toml")]) == 2
    assert tool.main(["--cache", str(cache), "--pins", str(pins), "--repo", REPO, "--tag", TAG]) == 0
