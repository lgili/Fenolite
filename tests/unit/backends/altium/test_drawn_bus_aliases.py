# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Exact-member drawn bus lowering, independent of the native acceptance gate."""

from __future__ import annotations

import dataclasses
import shutil
from pathlib import Path

import _drawn
import pytest
from _buildhelp import LIBS

from fenolite.api import run
from fenolite.backends.altium.drawn import _native_buses
from fenolite.backends.altium.read import sch
from fenolite.core.coords import Point
from fenolite.core.errors import Issue
from fenolite.lens.drawn import write_drawn
from fenolite.model.drawn import DrawnBusAlias


@pytest.fixture(autouse=True)
def isolated(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    monkeypatch.setenv("FENOLITE_STATE_DIR", str(tmp_path / "state"))
    for key in ("KICAD9_SYMBOL_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD10_FOOTPRINT_DIR"):
        monkeypatch.delenv(key, raising=False)


def copy_source(root: Path, name: str) -> Path:
    shutil.copytree(_drawn.folder(name), root)
    for table, head, uri in (
        ("fp-lib-table", "fp_lib_table", LIBS / "Mini_v9.pretty"),
        ("sym-lib-table", "sym_lib_table", LIBS / "Mini_v9.kicad_sym"),
    ):
        (root / table).write_text(
            f'({head}\n(version 7)\n(lib (name "Mini") (type "KiCad") '
            f'(uri "{uri.as_posix()}") (options "") (descr "")))\n',
            encoding="utf-8",
        )
    return root / "design.py"


def build(script: Path, tmp_path: Path, *args: str):
    return run(
        "build",
        str(script),
        "--out",
        "out",
        "--target",
        "altium",
        *args,
        cwd=tmp_path,
        timestamp="2026-11-01T00:00:00Z",
    )


@pytest.mark.parametrize("form", ["binary", "ascii"])
def test_full_alias_is_written_as_exact_native_vector(tmp_path: Path, form: str) -> None:
    script = copy_source(tmp_path / "source", "full")
    reply = build(script, tmp_path, "--altium-format", form, "--confirm")
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    labels = [
        label.text
        for path in (tmp_path / "out").glob("*.SchDoc")
        for label in sch.read_schematic(path.read_bytes()).of_type(sch.NetLabel)
    ]
    assert "B[0..1]" in labels and "{BUSA}" not in labels
    assert {"B0", "B1"} <= set(labels)
    changed = [i for i in reply.envelope["issues"] if "native bus vector" in i["message"]]
    assert len(changed) == 1 and changed[0]["severity"] == "info"
    assert changed[0]["where"] == "root.label[5]"


@pytest.mark.parametrize("form", ["binary", "ascii"])
def test_alias_preserves_connected_sheet_bus(tmp_path: Path, form: str) -> None:
    script = copy_source(tmp_path / "source", "bus")
    value = _drawn.drawn("bus")
    sheets = []
    for sheet in value.sheets:
        sheets.append(
            dataclasses.replace(
                sheet,
                labels=tuple(
                    dataclasses.replace(label, text="{DATA}") if label.text == "D[0..3]" else label
                    for label in sheet.labels
                ),
                sheet_refs=tuple(
                    dataclasses.replace(
                        ref, pins=tuple(dataclasses.replace(pin, name="{DATA}") for pin in ref.pins)
                    )
                    for ref in sheet.sheet_refs
                ),
                bus_aliases=(DrawnBusAlias("DATA", ("D0", "D1", "D2", "D3")),) if sheet.key == "root" else (),
            )
        )
    source = script.parent / "schematic.toml"
    source.write_text(write_drawn(dataclasses.replace(value, sheets=tuple(sheets))), encoding="utf-8")
    before = source.read_bytes()
    reply = build(script, tmp_path, "--altium-format", form, "--confirm")
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    assert source.read_bytes() == before
    documents = [sch.read_schematic(p.read_bytes()) for p in (tmp_path / "out").glob("*.SchDoc")]
    assert [entry.name for doc in documents for entry in doc.of_type(sch.SheetEntry)] == ["D[0..3]"]
    assert [port.name for doc in documents for port in doc.of_type(sch.Port)] == ["D[0..3]"]
    labels = [label.text for doc in documents for label in doc.of_type(sch.NetLabel)]
    assert sorted(labels) == sorted(["D[0..3]", *[f"D{k}" for k in range(4)] * 2])
    changes = [i for i in reply.envelope["issues"] if "native bus vector" in i["message"]]
    assert len(changes) == 3 and all(i["severity"] == "info" for i in changes)


@pytest.mark.parametrize("members", ['"B0", "B2"', '"B00", "B01"', '"B0", "ENABLE"', ""])
@pytest.mark.parametrize("lossy", [False, True])
def test_unrepresentable_alias_refuses_without_output(tmp_path: Path, members: str, lossy: bool) -> None:
    script = copy_source(tmp_path / "source", "full")
    source = script.parent / "schematic.toml"
    source.write_text(
        source.read_text(encoding="utf-8").replace('members = ["B0", "B1"]', f"members = [{members}]"),
        encoding="utf-8",
    )
    reply = build(script, tmp_path, "--dry-run", *(["--allow-lossy"] if lossy else []))
    assert reply.exit_code == 3 and reply.error["code"] == "FEN-3004", reply.error
    assert "native bus vector" in reply.error["message"]
    assert "root.label[5]" in str(reply.error)
    assert not (tmp_path / "out").exists()


@pytest.mark.parametrize("text", ["{DATA}", "DATA", "{D3 D2 D1 D0}"])
def test_sheet_alias_precedence_and_descending_members(text: str) -> None:
    value = _drawn.drawn("bus")
    root, child = value.sheets
    root = dataclasses.replace(root, bus_aliases=(DrawnBusAlias("DATA", ("OTHER0", "OTHER1")),))
    child = dataclasses.replace(
        child,
        labels=tuple(
            dataclasses.replace(label, text=text) if label.kind == "hierarchical" else label
            for label in child.labels
        ),
        bus_aliases=(DrawnBusAlias("DATA", ("D3", "D2", "D1", "D0")),),
    )
    value = dataclasses.replace(value, sheets=(root, child))
    issues: list[Issue] = []
    lowered = _native_buses(value, child, "child", issues)
    assert lowered.labels[0].text == "D[3..0]"
    assert len(issues) == 1 and issues[0].where == "child.label[0]"


def test_scalar_group_looking_text_and_vector_bytes_stay_literal() -> None:
    value = _drawn.drawn("bus")
    root = value.sheets[0]
    labels = tuple(
        dataclasses.replace(label, text="{D0 D1}") if label.text == "D0" else label for label in root.labels
    )
    root = dataclasses.replace(root, labels=labels)
    issues: list[Issue] = []
    assert _native_buses(value, root, "root", issues) == root
    assert not issues


def test_identifier_outside_actual_bus_segment_stays_literal() -> None:
    value = _drawn.drawn("bus")
    root = value.sheets[0]
    root = dataclasses.replace(
        root,
        buses=((Point(0, 0), Point(10, 10)),),
        labels=(dataclasses.replace(root.labels[-1], text="{D0 D1}", at=Point(5, 6)),),
        sheet_refs=(),
    )
    issues: list[Issue] = []
    assert _native_buses(value, root, "root", issues) == root
    assert not issues
