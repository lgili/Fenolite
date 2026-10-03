# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pins, tree hash and stamps of the library cache (capability kicad-library-resolution, "Library pins";
change c0021). Hermetic: temporary pins files and folders, no network and no fetched library."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from fenolite.backends.kicad import libcache
from fenolite.backends.kicad.libcache import (
    LibraryPin,
    archive_template,
    default_cache_dir,
    load_pins,
    read_stamp,
    stamp_matches,
    tree_hash,
    verified_folders,
    write_stamp,
)

ARCHIVE = "https://example.org/{project}/archive.tar.gz?sha={commit}"
PIN = {
    "tag": "10.0.6",
    "major": 10,
    "repo": "kicad-footprints",
    "project": "kicad/libraries/kicad-footprints",
    "commit": "a" * 40,
    "tree": "b" * 64,
    "files": 3,
}


def _toml(value: object) -> str:
    return str(value) if isinstance(value, int) and not isinstance(value, bool) else json.dumps(value)


def pins_file(tmp_path: Path, *pins: dict[str, object], head: str | None = None) -> Path:
    lines = [head if head is not None else f'schema = 1\narchive = "{ARCHIVE}"\n']
    for pin in pins:
        lines.append("[[pin]]\n" + "".join(f"{key} = {_toml(value)}\n" for key, value in pin.items()))
    path = tmp_path / "libraries.toml"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def test_pins_in_file_order(tmp_path: Path) -> None:
    symbols = PIN | {"repo": "kicad-symbols", "project": "kicad/libraries/kicad-symbols"}
    nine = PIN | {"tag": "9.0.9", "major": 9}
    path = pins_file(tmp_path, symbols, PIN, nine)
    pins = load_pins(path)
    assert [(p.tag, p.repo) for p in pins] == [
        ("10.0.6", "kicad-symbols"),
        ("10.0.6", "kicad-footprints"),
        ("9.0.9", "kicad-footprints"),
    ]
    assert pins[1] == LibraryPin("10.0.6", 10, "kicad-footprints", PIN["project"], "a" * 40, "b" * 64, 3)  # type: ignore[arg-type]
    assert archive_template(path) == ARCHIVE


@pytest.mark.parametrize(
    ("change", "key"),
    [
        ({"commit": "a" * 39}, "commit"),
        ({"commit": "A" * 40}, "commit"),
        ({"tree": "b" * 63}, "tree"),
        ({"files": 0}, "files"),
        ({"files": "3"}, "files"),
        ({"major": 0}, "major"),
        ({"repo": "kicad-packages3D"}, "repo"),
        ({"project": "other/kicad-footprints"}, "project"),
        ({"tag": ""}, "tag"),
        ({"extra": 1}, "extra"),
    ],
)
def test_malformed_pin(tmp_path: Path, change: dict[str, object], key: str) -> None:
    path = pins_file(tmp_path, PIN | change)
    with pytest.raises(ValueError, match=key) as error:
        load_pins(path)
    assert str(path) in str(error.value)


def test_missing_key_and_bad_head(tmp_path: Path) -> None:
    short = {k: v for k, v in PIN.items() if k != "tree"}
    with pytest.raises(ValueError, match="tree"):
        load_pins(pins_file(tmp_path, short))
    with pytest.raises(ValueError, match="schema"):
        load_pins(pins_file(tmp_path, PIN, head=f'schema = 2\narchive = "{ARCHIVE}"\n'))
    with pytest.raises(ValueError, match="archive"):
        load_pins(pins_file(tmp_path, PIN, head='schema = 1\narchive = "https://example.org/x"\n'))
    with pytest.raises(ValueError, match="pin"):
        load_pins(pins_file(tmp_path))
    (tmp_path / "broken.toml").write_text("schema = [", encoding="utf-8")
    with pytest.raises(ValueError, match="broken.toml"):
        load_pins(tmp_path / "broken.toml")


def test_one_pin_per_tag_and_repo_and_one_tag_per_major(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="pinned twice"):
        load_pins(pins_file(tmp_path, PIN, PIN))
    other_tag = PIN | {"tag": "10.0.5", "repo": "kicad-symbols", "project": "kicad/libraries/kicad-symbols"}
    with pytest.raises(ValueError, match="two tags"):
        load_pins(pins_file(tmp_path, PIN, other_tag))


def _tree(folder: Path, files: dict[str, bytes], *, reverse: bool = False, mtime: int = 0) -> Path:
    for name in sorted(files, reverse=reverse):
        path = folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(files[name])
        if mtime:
            os.utime(path, (mtime, mtime))
    return folder


FILES = {"b/x.kicad_mod": b"(footprint x)", "a.txt": b"hello", "b/é.kicad_mod": b"(footprint e)"}


def test_tree_hash_ignores_order_and_times(tmp_path: Path) -> None:
    one = _tree(tmp_path / "one", FILES, mtime=1_000_000)
    two = _tree(tmp_path / "two", FILES, reverse=True, mtime=2_000_000)
    (two / "empty").mkdir()  # empty folders do not count
    assert tree_hash(one) == tree_hash(two) and tree_hash(one)[1] == 3
    (two / "a.txt").write_bytes(b"hellp")
    assert tree_hash(one)[0] != tree_hash(two)[0] and tree_hash(two)[1] == 3
    os.chmod(one / "a.txt", 0o600)
    assert tree_hash(one) == tree_hash(_tree(tmp_path / "three", FILES))


def test_tree_hash_is_the_documented_scheme(tmp_path: Path) -> None:
    import hashlib

    folder = _tree(tmp_path / "t", {"b.txt": b"B", "a/c.txt": b"C"})
    lines = b"".join(
        f"{hashlib.sha256(data).hexdigest()} {len(data)} {name}\n".encode()
        for name, data in (("a/c.txt", b"C"), ("b.txt", b"B"))
    )
    assert tree_hash(folder) == (hashlib.sha256(lines).hexdigest(), 2)


def test_stamp_is_not_hashed(tmp_path: Path) -> None:
    folder = _tree(tmp_path / "t", FILES)
    before = tree_hash(folder)
    (folder / libcache.STAMP).write_text("{}", encoding="utf-8")
    assert tree_hash(folder) == before


def test_symlink_refused(tmp_path: Path) -> None:
    folder = _tree(tmp_path / "t", {"b": b"x"})
    (folder / "a").symlink_to(folder / "b")
    with pytest.raises(ValueError, match="a: a symlink"):
        tree_hash(folder)


def test_stamps(tmp_path: Path) -> None:
    (pin,) = load_pins(pins_file(tmp_path, PIN))
    folder = tmp_path / "cache" / pin.tag / pin.repo
    folder.mkdir(parents=True)
    assert read_stamp(folder) is None and not stamp_matches(folder, pin)
    write_stamp(folder, pin)
    stamp = read_stamp(folder)
    assert stamp == {
        "scheme": "fenolite-tree-1",
        "tag": "10.0.6",
        "repo": "kicad-footprints",
        "commit": "a" * 40,
        "tree": "b" * 64,
        "files": 3,
    }
    assert stamp_matches(folder, pin)
    assert verified_folders(tmp_path / "cache", (pin,)) == ((pin, folder),)
    for key, value in (("commit", "c" * 40), ("scheme", "fenolite-tree-0"), ("files", 4)):
        (folder / libcache.STAMP).write_text(json.dumps(stamp | {key: value}), encoding="utf-8")
        assert not stamp_matches(folder, pin)
    (folder / libcache.STAMP).write_text(json.dumps(stamp | {"more": 1}), encoding="utf-8")
    assert not stamp_matches(folder, pin)
    (folder / libcache.STAMP).write_text("[1]", encoding="utf-8")
    assert read_stamp(folder) is None and verified_folders(tmp_path / "cache", (pin,)) == ()


def test_default_cache_dir(tmp_path: Path) -> None:
    assert default_cache_dir({"FENOLITE_LIBS_CACHE": "/x/libs"}, tmp_path) == Path("/x/libs")
    assert default_cache_dir({}, tmp_path) == tmp_path / ".cache" / "fenolite" / "libs"


def test_pins_of_both_tags() -> None:
    pins = load_pins()
    assert [(p.tag, p.major, p.repo) for p in pins] == [
        ("10.0.6", 10, "kicad-footprints"),
        ("10.0.6", 10, "kicad-symbols"),
        ("9.0.9", 9, "kicad-footprints"),
        ("9.0.9", 9, "kicad-symbols"),
    ]
    for pin in pins:
        assert len(pin.commit) == 40 and len(pin.tree) == 64 and pin.files > 0
        assert pin.project == f"kicad/libraries/{pin.repo}"
    # the short ids that the sources register records for the four tags (S-0042, S-0043)
    assert [p.commit[:12] for p in pins] == ["819223b66f96", "7800d91437ce", "2b941bf1d978", "ad36cd14bcd1"]
    assert "{project}" in archive_template() and "{commit}" in archive_template()
