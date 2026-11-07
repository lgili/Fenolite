# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Parts not populated and net ties through ``fenolite import --to python`` (change c0277): a ``dnp`` part
is written ``dnp=True``, and a net tie comes back with its vendored footprint, so neither is unexpressed."""

from __future__ import annotations

from pathlib import Path

from _importcode import build, imported, unfitted

from fenolite.backends.kicad.sexpr import parse


def _footprint(root, ref: str):  # noqa: ANN001, ANN202
    for node in root.nodes("footprint"):
        for prop in node.nodes("property"):
            atoms = prop.atoms()
            if len(atoms) >= 2 and atoms[0].value == "Reference" and atoms[1].value == ref:
                return node
    raise AssertionError(ref)


def test_dnp_and_net_tie_are_kept(tmp_path: Path) -> None:
    reply = imported(tmp_path, unfitted(tmp_path / "src"), "--confirm")
    assert reply.exit_code == 0, reply.error
    assert reply.result["unexpressed"] == []
    code = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert "dnp=True" in code and code.count("dnp=True") == 1
    assert build(tmp_path / "out").exit_code == 0
    root = parse((tmp_path / "out" / "built" / "unfitted.kicad_pcb").read_text(encoding="utf-8"))
    attr = _footprint(root, "R101").find("attr")
    assert attr is not None and [a.value for a in attr.atoms()] == ["smd", "dnp"]
    assert _footprint(root, "R201").find("net_tie_pad_groups") == parse('(net_tie_pad_groups "1, 2")')
