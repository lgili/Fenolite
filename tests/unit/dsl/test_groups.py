# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Groups in the DSL (capability design-dsl, "Groups in the DSL"; change c0277): ``design.group()`` in the
model, written for KiCad 9 and 10, replaced on a rebuild and reported by an Altium build."""

from __future__ import annotations

from pathlib import Path

import pytest
from _buildhelp import blink_variant

from fenolite.api import run
from fenolite.backends.kicad.sexpr import Node, parse
from fenolite.dsl import Design, DslError, Net, Part, mm, to_model

STAMP = "2026-10-30T00:00:00Z"
LINES = (
    'design.text("silk/logo", "LOGO", (mm(5), mm(5)))\n'
    'design.group("logo", r1, "silk/logo", locked=True)\n'
    'design.group("", "logo", d1, key="outer")\n'
)


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def _design() -> tuple[Design, Part]:
    design = Design("groups")
    design.board(mm(40), mm(30))
    r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603")
    design.add(r1)
    design.text("silk/a", "A", (mm(5), mm(5)))
    design.text("silk/b", "B", (mm(5), mm(10)))
    gnd = Net("GND")
    design.add(gnd)
    design.zone(gnd, layers=("B.Cu",), outline=((mm(0), mm(0)), (mm(10), mm(0)), (mm(10), mm(10))))
    return design, r1


def test_groups_in_the_model() -> None:
    design, r1 = _design()
    design.group("inner", r1, "silk/a", "GND", locked=True)
    design.group("", "inner", "silk/b", key="outer")
    board = to_model(design).board
    assert board is not None
    groups = {g.name: g for g in board.groups}
    assert set(groups) == {"inner", ""}
    inner, outer = groups["inner"], groups[""]
    assert inner.locked and not outer.locked
    assert len(inner.member_ids) == 3 and inner.member_ids == tuple(sorted(inner.member_ids))
    assert inner.id in outer.member_ids
    component = next(c for c in to_model(design).circuit.components if c.ref == "R1")
    assert component.id in inner.member_ids


@pytest.mark.parametrize(
    ("call", "match"),
    [
        (lambda d, r: d.group("g"), "at least one member"),
        (lambda d, r: d.group("g", "nowhere"), "neither a part nor the key"),
        (lambda d, r: d.group("g", Part("R9", "Mini:Mini_R")), "not added"),
        (lambda d, r: d.group("g", r, locked="yes"), "locked must be a bool"),
        (lambda d, r: d.group("a b", r), "must match"),
        (lambda d, r: d.group("", r), "must match"),
        (lambda d, r: (d.group("g", r), d.group("h", r)), "already a member"),
        (lambda d, r: (d.group("g", "silk/a"), d.group("g", "silk/b")), "already used"),
        (lambda d, r: d.group("g", r, r), "already a member"),
    ],
)
def test_refusals(call, match: str) -> None:  # noqa: ANN001
    design, r1 = _design()
    with pytest.raises(DslError, match=match):
        call(design, r1)


def _build(script: Path, out: Path, target: int) -> Node:
    reply = run(
        "build", str(script), "--out", str(out), "--kicad-version", str(target), "--confirm",
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip
    assert reply.exit_code == 0, reply.error
    return parse((out / "blink.kicad_pcb").read_text(encoding="utf-8"))


def _uuid(node: Node) -> str:
    held = node.find("uuid")
    assert held is not None
    return held.atoms()[0].value


def _members(node: Node) -> list[str]:
    held = node.find("members")
    assert held is not None
    return [a.value for a in held.atoms()]


def _footprints(root: Node) -> dict[str, str]:
    found: dict[str, str] = {}
    for node in root.nodes("footprint"):
        for prop in node.nodes("property"):
            atoms = prop.atoms()
            if atoms[0].value == "Reference":
                found[atoms[1].value] = _uuid(node)
    return found


@pytest.mark.parametrize("target", [9, 10])
def test_groups_written(tmp_path: Path, target: int) -> None:
    root = _build(blink_variant(tmp_path / "src", append=LINES), tmp_path / "out", target)
    assert [child.name for child in root.nodes()][-2:] == ["group", "group"]
    groups = {node.atoms()[0].value: node for node in root.nodes("group")}
    logo, outer = groups["logo"], groups[""]
    assert [child.name for child in logo.nodes()] == ["uuid", "locked", "members"]
    assert [child.name for child in outer.nodes()] == ["uuid", "members"]
    parts = _footprints(root)
    (text,) = [_uuid(t) for t in root.nodes("gr_text") if t.atoms()[0].value == "LOGO"]
    assert _members(logo) == sorted([parts["R1"], text])
    assert _members(outer) == sorted([_uuid(logo), parts["D1"]])


def test_rebuild_replaces_the_group(tmp_path: Path) -> None:
    script = blink_variant(tmp_path / "src", append=LINES)
    out = tmp_path / "out"
    first = _build(script, out, 10)
    again = _build(script, out, 10)
    assert again == first
    script.write_text(script.read_text(encoding="utf-8").replace(", locked=True", ""), "utf-8")
    groups = [node for node in _build(script, out, 10).nodes("group") if node.atoms()[0].value == "logo"]
    assert len(groups) == 1 and groups[0].find("locked") is None


def test_altium_reports_groups(tmp_path: Path) -> None:
    script = blink_variant(tmp_path / "src", append=LINES)
    reply = run(
        "build", str(script), "--out", str(tmp_path / "out"), "--target", "altium", "--dry-run",
        cwd=script.parent, timestamp=STAMP,
    )  # fmt: skip
    assert reply.exit_code == 0, reply.error
    found = [i for i in reply.envelope["issues"] if i["where"].startswith("group/")]  # type: ignore[index]
    assert len(found) == 2 and {i["code"] for i in found} == {"altium.not-lowered"}
    assert any("'logo'" in i["message"] for i in found)
