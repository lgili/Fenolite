# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library sources (kicad-library-resolution, "Library sources"); every input is injected."""

from __future__ import annotations

from pathlib import Path

import pytest
from _libs import make_install, verified_cache

from fenolite.backends.kicad import libs
from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver, LibrarySource, find_library_sources


def test_missing_install_path_means_no_install(tmp_path: Path) -> None:
    assert find_library_sources(LibraryConfig(env={}, install_dir=tmp_path / "absent")) == ()


def test_install_major_from_the_symbol_header(tmp_path: Path) -> None:
    ten = make_install(tmp_path / "ten", 20251024)
    nine = make_install(tmp_path / "nine", 20241209)
    eight = make_install(tmp_path / "eight", 20231120)
    assert find_library_sources(LibraryConfig(env={}, install_dir=ten)) == (
        LibrarySource("install", ten, 10),
    )
    assert find_library_sources(LibraryConfig(env={}, install_dir=nine))[0].major == 9
    assert find_library_sources(LibraryConfig(env={}, install_dir=eight))[0].major == 8


def test_header_is_read_from_the_first_4_kib(tmp_path: Path) -> None:
    root = make_install(tmp_path / "late")
    padding = "#" * 5000
    (root / "symbols" / "Fake.kicad_sym").write_text(f"{padding}\n(kicad_symbol_lib (version 20251024))\n")
    assert find_library_sources(LibraryConfig(env={}, install_dir=root)) == ()


def test_install_without_symbols_is_not_a_source(tmp_path: Path) -> None:
    (tmp_path / "bare").mkdir()
    assert find_library_sources(LibraryConfig(env={}, install_dir=tmp_path / "bare")) == ()


def test_symbol_folders_identify_an_install(tmp_path: Path) -> None:
    root = make_install(tmp_path / "dirs")
    (root / "symbols" / "Fake.kicad_sym").unlink()
    folder = root / "symbols" / "Device.kicad_symdir"
    folder.mkdir()
    (folder / "R.kicad_sym").write_text("(kicad_symbol_lib (version 20251024))\n", encoding="utf-8")
    assert find_library_sources(LibraryConfig(env={}, install_dir=root))[0].major == 10


def test_env_sources(tmp_path: Path) -> None:
    footprints, symbols = tmp_path / "fp", tmp_path / "sym"
    footprints.mkdir()
    symbols.mkdir()
    env = {
        "KICAD10_FOOTPRINT_DIR": str(footprints),
        "KICAD9_SYMBOL_DIR": str(symbols),
        "KICAD10_SYMBOL_DIR": str(tmp_path / "absent"),
    }
    found = find_library_sources(LibraryConfig(env=env, install_dir=tmp_path / "absent"))
    assert found == (LibrarySource("env", footprints, 10), LibrarySource("env", symbols, 9))


def test_env_sources_come_before_the_install(tmp_path: Path) -> None:
    install = make_install(tmp_path / "install")
    footprints = tmp_path / "fp"
    footprints.mkdir()
    found = find_library_sources(
        LibraryConfig(env={"KICAD10_FOOTPRINT_DIR": str(footprints)}, install_dir=install)
    )
    assert [s.kind for s in found] == ["env", "install"]


def test_default_install_folders_per_os(tmp_path: Path) -> None:
    candidates = libs._install_candidates  # pyright: ignore[reportPrivateUsage]
    assert candidates(LibraryConfig(system="linux"), {}) == [Path("/usr/share/kicad")]
    assert candidates(LibraryConfig(system="darwin"), {}) == [
        Path("/Applications/KiCad/KiCad.app/Contents/SharedSupport")
    ]
    windows = candidates(LibraryConfig(system="win32"), {"ProgramFiles": str(tmp_path)})
    assert windows == [
        tmp_path / "KiCad" / "10.0" / "share" / "kicad",
        tmp_path / "KiCad" / "9.0" / "share" / "kicad",
    ]
    assert candidates(LibraryConfig(install_dir=tmp_path), {}) == [tmp_path]


# -- the cache source (c0021)


def _config(tmp_path: Path, **overrides: object) -> LibraryConfig:
    settings: dict[str, object] = {"env": {}, "install_dir": tmp_path / "absent", "home": tmp_path / "home"}
    settings.update(overrides)
    return LibraryConfig(**settings)  # type: ignore[arg-type]


def test_verified_cache_source(tmp_path: Path) -> None:
    cache = verified_cache(tmp_path / "C", "9.0.9", "kicad-footprints")
    assert find_library_sources(_config(tmp_path, cache_dir=cache)) == (
        LibrarySource("cache", cache / "9.0.9", 9),
    )


def test_stale_stamp_is_ignored(tmp_path: Path) -> None:
    cache = verified_cache(tmp_path / "C", "9.0.9", "kicad-footprints", stale=True)
    assert find_library_sources(_config(tmp_path, cache_dir=cache)) == ()
    (cache / "9.0.9" / "kicad-footprints" / libs.libcache.STAMP).unlink()
    assert find_library_sources(_config(tmp_path, cache_dir=cache)) == ()


def test_one_cache_source_per_tag_in_pin_order(tmp_path: Path) -> None:
    cache = verified_cache(tmp_path / "C", "9.0.9", "kicad-footprints", "kicad-symbols")
    verified_cache(cache, "10.0.6", "kicad-symbols")
    assert find_library_sources(_config(tmp_path, cache_dir=cache)) == (
        LibrarySource("cache", cache / "10.0.6", 10),
        LibrarySource("cache", cache / "9.0.9", 9),
    )


def test_cache_from_the_environment_and_order(tmp_path: Path) -> None:
    cache = verified_cache(tmp_path / "C", "10.0.6", "kicad-footprints")
    install = make_install(tmp_path / "install")
    footprints = tmp_path / "fp"
    footprints.mkdir()
    env = {"FENOLITE_LIBS_CACHE": str(cache), "KICAD10_FOOTPRINT_DIR": str(footprints)}
    found = find_library_sources(_config(tmp_path, env=env, install_dir=install))
    assert [s.kind for s in found] == ["env", "cache", "install"]
    # cache_dir wins over the variable
    other = _config(tmp_path, env={"FENOLITE_LIBS_CACHE": str(cache)}, cache_dir=tmp_path / "empty")
    assert find_library_sources(other) == ()


def test_cache_before_install(tmp_path: Path) -> None:
    cache = verified_cache(tmp_path / "C", "10.0.6", "kicad-footprints")
    install = make_install(tmp_path / "install")
    resolver = LibraryResolver(_config(tmp_path, cache_dir=cache, install_dir=install))
    assert Path(resolver.expand("${KICAD10_FOOTPRINT_DIR}")) == cache / "10.0.6" / "kicad-footprints"
    with pytest.raises(libs.LibraryError) as caught:
        resolver.expand("${KICAD10_3DMODEL_DIR}")
    assert caught.value.issue.code == "kicad.lib.unresolved-variable"


def test_a_cache_of_another_major_is_not_used(tmp_path: Path) -> None:
    cache = verified_cache(tmp_path / "C", "9.0.9", "kicad-footprints")
    resolver = LibraryResolver(_config(tmp_path, cache_dir=cache, target_major=10))
    with pytest.raises(libs.LibraryError):
        resolver.expand("${KICAD10_FOOTPRINT_DIR}")
    nine = LibraryResolver(_config(tmp_path, cache_dir=cache, target_major=9))
    assert Path(nine.expand("${KICAD9_FOOTPRINT_DIR}")) == cache / "9.0.9" / "kicad-footprints"


def test_no_default_cache_location(tmp_path: Path) -> None:
    home = tmp_path / "home"
    verified_cache(home / ".cache" / "fenolite" / "libs", "10.0.6", "kicad-footprints")
    assert find_library_sources(_config(tmp_path, home=home)) == ()
    assert find_library_sources(_config(tmp_path, cache_dir=tmp_path / "does-not-exist")) == ()
