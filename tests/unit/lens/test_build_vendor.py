# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Footprints of every row origin are vendored (capability design-dsl, "Footprints of every row origin are
vendored" and the vendoring rows of "Build evidence"; change c0027)."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from _buildhelp import LIBS, blink, build
from _libs import make_install

from fenolite.backends.kicad.libs import LibraryConfig, LibraryResolver, LibRow, LibTable, write_lib_table
from fenolite.dsl import Design, Part, placements, to_model
from fenolite.lens.build import RECORD_FILE, VENDOR_EVIDENCE, BuildOutput, build_design

USED = ("Mini_LED_THT_3mm", "Mini_QFP-32_7x7mm_P0.8mm", "Mini_R_0603")


def library(root: Path) -> tuple[Path, Path]:
    """Copies of the CC0 ``Mini_v9`` library under ``root``."""
    pretty, symbols = root / "Mini.pretty", root / "Mini.kicad_sym"
    shutil.copytree(LIBS / "Mini_v9.pretty", pretty)
    shutil.copyfile(LIBS / "Mini_v9.kicad_sym", symbols)
    return pretty, symbols


def config_home(root: Path, rows: dict[str, Path], symbols: Path) -> Path:
    """A configuration folder whose global tables (both majors) hold ``rows`` and the row ``Mini`` of
    ``symbols``."""
    for major in (9, 10):
        sub = root / f"{major}.0"
        sub.mkdir(parents=True)
        fp = LibTable("footprint", tuple(LibRow(n, "KiCad", str(p)) for n, p in rows.items()))
        sy = LibTable("symbol", (LibRow("Mini", "KiCad", str(symbols)),))
        (sub / "fp-lib-table").write_text(write_lib_table(fp, target=major), encoding="utf-8")
        (sub / "sym-lib-table").write_text(write_lib_table(sy, target=major), encoding="utf-8")
    return root


def global_setup(tmp_path: Path) -> tuple[Path, Path, Path]:
    """``(config folder, footprint copy, empty project folder)`` of the global setup."""
    pretty, symbols = library(tmp_path / "global")
    empty = tmp_path / "project"
    empty.mkdir()
    return config_home(tmp_path / "config", {"Mini": pretty}, symbols), pretty, empty


def global_build(
    tmp_path: Path, design: Design | None = None, target: int = 10, **kwargs: object
) -> BuildOutput:
    config, _, empty = global_setup(tmp_path)
    return build(design or blink(), target, project_dir=empty, config_home=config, **kwargs)


@pytest.mark.parametrize("target", [9, 10])
def test_global_footprints_vendored(tmp_path: Path, target: int) -> None:
    out = global_build(tmp_path, target=target)
    pretty = tmp_path / "global" / "Mini.pretty"
    for name in USED:
        assert out.files[f"lib/Mini.pretty/{name}.kicad_mod"] == (pretty / f"{name}.kicad_mod").read_bytes()
    table = out.files["fp-lib-table"].decode("utf-8")
    assert table.count("(lib ") == 1 and "${KIPRJMOD}/lib/Mini.pretty" in table
    assert not [i for i in out.issues if i.code == "build.global-library"]
    assert out.summary["libraries"]["Mini:Mini_R_0603"] == "global"  # type: ignore[index]
    assert b'(footprint "Mini:Mini_R_0603"' in out.files["blink.kicad_pcb"]
    assert VENDOR_EVIDENCE.hypotheses[0] in out.evidence.hypotheses


def test_template_footprints_vendored(tmp_path: Path) -> None:
    template = '(fp_lib_table (version 7) (lib (name "Mini") (type "KiCad") (uri "${KICAD10_FOOTPRINT_DIR}/Mini.pretty") (options "") (descr "")))'  # noqa: E501
    sym_template = '(sym_lib_table (version 7) (lib (name "Mini") (type "KiCad") (uri "${KICAD10_SYMBOL_DIR}/Mini.kicad_sym") (options "") (descr "")))'  # noqa: E501
    install = make_install(
        tmp_path / "install", template={"fp-lib-table": template, "sym-lib-table": sym_template}
    )
    shutil.copytree(LIBS / "Mini_v9.pretty", install / "footprints" / "Mini.pretty")
    shutil.copyfile(LIBS / "Mini_v9.kicad_sym", install / "symbols" / "Mini.kicad_sym")
    (tmp_path / "project").mkdir()
    (tmp_path / "config").mkdir()
    resolver = LibraryResolver(
        LibraryConfig(
            target_major=10,
            project_dir=tmp_path / "project",
            env={},
            config_home=tmp_path / "config",
            install_dir=install,
        )
    )
    d = blink()
    out = build_design(to_model(d), placements(d), name=d.name, copper=2, resolver=resolver, target=10)
    assert out.summary["libraries"]["Mini:Mini_R_0603"] == "template"  # type: ignore[index]
    reference = global_build(tmp_path / "g")
    assert {k: v for k, v in out.files.items() if k.startswith("lib/") or k == "fp-lib-table"} == {
        k: v for k, v in reference.files.items() if k.startswith("lib/") or k == "fp-lib-table"
    }


def test_vendoring_kept_to_project_rows_on_request(tmp_path: Path) -> None:
    out = global_build(tmp_path, vendor="project")
    assert not any(k.startswith("lib/") for k in out.files)
    assert b"(lib " not in out.files["fp-lib-table"]
    found = [i for i in out.issues if i.code == "build.global-library"]
    assert len(found) == 3 and all(i.severity == "info" for i in found)
    assert VENDOR_EVIDENCE.hypotheses[0] not in out.evidence.hypotheses


def test_unsafe_nickname(tmp_path: Path) -> None:
    pretty, symbols = library(tmp_path / "global")
    config = config_home(tmp_path / "config", {"Mini": pretty, "a/b": pretty}, symbols)
    (tmp_path / "project").mkdir()
    d = blink()
    d.parts["R1"].footprint = "a/b:Mini_R_0603"
    out = build(d, 10, project_dir=tmp_path / "project", config_home=config)
    assert out.files == {}
    (found,) = [i for i in out.issues if i.code == "build.vendor-unsafe-name"]
    assert "a/b" in found.message


def test_paths_equal_after_casefold(tmp_path: Path) -> None:
    pretty, symbols = library(tmp_path / "global")
    config = config_home(tmp_path / "config", {"Mini": pretty, "MINI": pretty}, symbols)
    (tmp_path / "project").mkdir()
    d = blink()
    d.add(Part("R2", "Mini:Mini_R", footprint="MINI:Mini_R_0603", value="1k"))
    out = build(d, 10, project_dir=tmp_path / "project", config_home=config)
    assert out.files == {}
    (found,) = [i for i in out.issues if i.code == "build.vendor-unsafe-name"]
    assert "lib/MINI.pretty" in found.message and "lib/Mini.pretty" in found.message


def _hashes(out: BuildOutput) -> dict[str, str]:
    return json.loads(out.files[RECORD_FILE])["files"]


def test_library_changed_since_the_last_build(tmp_path: Path) -> None:
    config, pretty, empty = global_setup(tmp_path)
    first = build(blink(), 10, project_dir=empty, config_home=config)
    record = _hashes(first)
    again = build(blink(), 10, project_dir=empty, config_home=config, record=record)
    assert not [i for i in again.issues if i.code == "build.library-changed"]
    path = pretty / "Mini_R_0603.kicad_mod"
    path.write_text(
        path.read_text(encoding="utf-8").replace("(at -0.8 0)", "(at -0.75 0)", 1), encoding="utf-8"
    )
    changed = build(blink(), 10, project_dir=empty, config_home=config, record=record)
    (found,) = [i for i in changed.issues if i.code == "build.library-changed"]
    assert found.where == "lib/Mini.pretty/Mini_R_0603.kicad_mod" and found.severity == "warning"
    assert changed.files["lib/Mini.pretty/Mini_R_0603.kicad_mod"] == path.read_bytes()
    assert hashlib.sha256(path.read_bytes()).hexdigest() != record["lib/Mini.pretty/Mini_R_0603.kicad_mod"]


def test_built_folder_resolves_alone(tmp_path: Path) -> None:
    out = global_build(tmp_path)
    folder = tmp_path / "out"
    for rel, data in out.files.items():
        (folder / rel).parent.mkdir(parents=True, exist_ok=True)
        (folder / rel).write_bytes(data)
    copy = tmp_path / "moved"
    shutil.copytree(folder, copy)
    (tmp_path / "empty-config").mkdir()
    resolver = LibraryResolver(
        LibraryConfig(
            target_major=10,
            project_dir=copy,
            env={},
            config_home=tmp_path / "empty-config",
            install_dir=tmp_path / "no-install",
        )
    )
    location = resolver.locate("Mini:Mini_R_0603", "footprint")
    assert location.origin == "project"
    assert location.item_path == copy / "lib" / "Mini.pretty" / "Mini_R_0603.kicad_mod"


def test_byte_identical_rebuilds(tmp_path: Path) -> None:
    config, _, empty = global_setup(tmp_path)
    first = build(blink(), 9, project_dir=empty, config_home=config)
    second = build(blink(), 9, project_dir=empty, config_home=config)
    assert first.files == second.files and any(k.startswith("lib/") for k in first.files)
