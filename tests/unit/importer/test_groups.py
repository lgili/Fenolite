# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Groups through ``fenolite import --to python`` (capability board-to-code, "Groups in an import"; change
c0277): a group whose members the code writes becomes a ``design.group()`` call, a group inside a group
after it; a group holding an item the code does not write is unexpressed."""

from __future__ import annotations

from pathlib import Path

from _importcode import BOARD, build, drawn_grouped, imported

from fenolite.backends.kicad.sexpr import Node, parse


def _uuid(node: Node) -> str:
    held = node.find("uuid")
    assert held is not None
    return held.atoms()[0].value


def _reference(node: Node) -> str:
    for prop in node.nodes("property"):
        atoms = prop.atoms()
        if len(atoms) >= 2 and atoms[0].value == "Reference":
            return atoms[1].value
    return ""


def test_groups_are_written(tmp_path: Path) -> None:
    reply = imported(tmp_path, drawn_grouped(tmp_path / "src"), "--allow-lossy", "--confirm")
    assert reply.exit_code == 0, reply.error
    kinds = {row["kind"]: row["examples"] for row in reply.result["unexpressed"]}
    assert kinds == {"dimension-style": ["aligned on Dwgs.User"], "group": ["lost"], "text": ["HIDDEN"]}
    code = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert code.count("design.group(") == 2
    assert 'design.group("logo", "Dwgs.User/dimension/1", "F.SilkS/text/1", j1, locked=True)\n' in code
    assert 'design.group("", "F.SilkS/text/2", "logo", key="group/1")\n' in code
    assert build(tmp_path / "out").exit_code == 0
    root = parse((tmp_path / "out" / "built" / "drawn.kicad_pcb").read_text(encoding="utf-8"))
    groups = {node.atoms()[0].value: node for node in root.nodes("group")}
    assert set(groups) == {"logo", ""}
    assert [child.name for child in root.nodes()][-2:] == ["group", "group"]
    ids = {_reference(fp): _uuid(fp) for fp in root.nodes("footprint")}
    texts = {node.atoms()[0].value: _uuid(node) for node in root.nodes("gr_text")}
    (dimension,) = root.nodes("dimension")

    def members(node: Node) -> list[str]:
        held = node.find("members")
        assert held is not None
        return [a.value for a in held.atoms()]

    logo = groups["logo"]
    assert logo.find("locked") == parse("(locked yes)")
    assert members(logo) == sorted([ids["J1"], texts["KNOCK"], _uuid(dimension)])
    assert members(groups[""]) == sorted([_uuid(logo), texts["TWO\nLINES"]])
    assert groups[""].find("locked") is None


def test_group_of_a_shared_key_is_unexpressed(tmp_path: Path) -> None:
    """A rule area named as the zone ``GND`` makes ``"GND"`` name two items: a group of the zone is left
    out."""
    text = BOARD.read_text(encoding="utf-8").rstrip()
    area = (
        '\t(zone (layers "F.Cu") (uuid "0e0e0e0e-0000-4000-8000-000000000041") (name "GND")'
        " (keepout (tracks not_allowed) (vias allowed) (pads allowed) (copperpour allowed)"
        " (footprints allowed))"
        " (polygon (pts (xy 140 114) (xy 144 114) (xy 144 118) (xy 140 118))))\n"
        '\t(group "pour" (uuid "0e0e0e0e-0000-4000-8000-000000000042")'
        ' (members "acdd6d99-1aad-5cbe-8b11-0bec91326628"))\n'
    )
    folder = tmp_path / "shared"
    folder.mkdir()
    source = folder / "shared.kicad_pcb"
    source.write_text(text[:-1] + area + ")\n", encoding="utf-8")
    reply = imported(tmp_path, source, "--allow-lossy")
    assert reply.exit_code == 0, reply.error
    kinds = {row["kind"]: row["examples"] for row in reply.result["unexpressed"]}
    assert kinds.get("group") == ["pour"]
