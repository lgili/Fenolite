# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Built project files (capability design-dsl, "Built project files"; change c0011)."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
from _buildhelp import LIBS, blink, build, codes, project, resolver

from fenolite.backends.kicad.libs import read_lib_table
from fenolite.backends.kicad.versions import LossyWriteError
from fenolite.dsl import Net, connect
from fenolite.lens.build import RECORD_FILE, RECORD_SCHEMA

TRIAD = {"blink.kicad_pcb", "blink.kicad_pro", "blink.kicad_dru"}
VENDORED = {
    f"lib/Mini.pretty/{n}.kicad_mod" for n in ("Mini_R_0603", "Mini_LED_THT_3mm", "Mini_QFP-32_7x7mm_P0.8mm")
}
CACHE = {
    f".fenolite/{n}.json" for n in ("meta", "circuit", "board", "rules", "manufacturing", "findings", "build")
}


def test_files_of_a_target_9_build() -> None:
    out = build(blink(), 9)
    assert set(out.files) == TRIAD | VENDORED | CACHE | {"fp-lib-table"}
    assert b"version" not in out.files["fp-lib-table"]
    for rel in VENDORED:
        assert out.files[rel] == (LIBS / "Mini_v9.pretty" / Path(rel).name).read_bytes()
    assert out.files["blink.kicad_dru"] == b"(version 1)\n"
    assert (
        out.files[".fenolite/findings.json"] == b"{}\n" or b"issues" in out.files[".fenolite/findings.json"]
    )


def test_build_record() -> None:
    out = build(blink())
    record = json.loads(out.files[RECORD_FILE])
    assert record["schema"] == RECORD_SCHEMA and record["design"] == "blink" and record["target"] == 10
    assert set(record) == {"design", "files", "schema", "target"}
    outside = {k for k in out.files if not k.startswith(".fenolite/")}
    assert set(record["files"]) == outside and len(outside) == 7
    assert all(record["files"][k] == hashlib.sha256(out.files[k]).hexdigest() for k in outside)
    assert out.files[RECORD_FILE].endswith(b"\n")


def test_errors_produce_no_files() -> None:
    d = blink()
    connect(Net("LED2"), d.parts["R1"]["X"])
    out = build(d)
    assert out.files == {} and "build.unknown-pin" in codes(out)


def test_unsafe_class_pattern_refused() -> None:
    d = blink()
    d.rules.netclass("HV", clearance="1mm", nets=(Net("D[0]"),))
    d.add(Net("D0"))
    with pytest.raises(LossyWriteError) as caught:
        build(d)
    assert any(i.code == "kicad.project.pattern-unsafe" for i in caught.value.issues)


def test_vendored_file_newer_than_the_target(tmp_path: Path) -> None:
    lib = tmp_path / "p" / "New.pretty"
    shutil.copytree(LIBS / "Mini_v9.pretty", lib)
    text = (
        (lib / "Mini_R_0603.kicad_mod")
        .read_text(encoding="utf-8")
        .replace("(version 20241229)", "(version 20260206)")
    )
    (lib / "Mini_R_0603.kicad_mod").write_text(text, encoding="utf-8")
    folder = project(
        tmp_path / "p", {"Mini": "${KIPRJMOD}/New.pretty"}, {"Mini": str(LIBS / "Mini_v9.kicad_sym")}
    )
    out = build(blink(), 9, project_dir=folder)
    found = [i for i in out.issues if i.code == "build.library-too-new"]
    assert len(found) == 1 and "Mini_R_0603" in found[0].message
    assert out.files["lib/Mini.pretty/Mini_R_0603.kicad_mod"] == text.encode("utf-8")


def test_the_built_folder_moves_whole(tmp_path: Path) -> None:
    out = build(blink())
    copy = tmp_path / "moved"
    for rel, data in out.files.items():
        (copy / rel).parent.mkdir(parents=True, exist_ok=True)
        (copy / rel).write_bytes(data)
    location = resolver(10, copy).locate("Mini:Mini_R_0603", "footprint")
    assert location.item_path == copy / "lib" / "Mini.pretty" / "Mini_R_0603.kicad_mod"
    assert read_lib_table(copy / "fp-lib-table").version == 7


def test_no_absolute_path_in_outputs() -> None:
    out = build(blink())
    root = str(Path(__file__).resolve().parents[3])
    assert not any(root.encode() in data for rel, data in out.files.items() if not rel.startswith("lib/"))
