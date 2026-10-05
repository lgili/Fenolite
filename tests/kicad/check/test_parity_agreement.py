# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fenolite's parity comparison gives the counts of KiCad's parity test (capability kicad-oracle, "Own
parity agrees with kicad-cli"; ``H-K-PARITY-OWN``; change c0072): on the built blink and its edits, with
the nodes from the netlist export and from the own netlist, and on every corpus demo of the running
major's tag that has a board and a schematic. A mismatch is a defect of ``checks/parity.py``."""

from __future__ import annotations

from pathlib import Path

import _erccases
import _paritycases as cases
import _paritycorpus as corpus
import pytest
from _probes import run

from fenolite.checks import parity

pytestmark = pytest.mark.needs_kicad


def test_blink_and_its_edits() -> None:
    differing = cases.blink_agreement()
    assert not differing, "\n".join(differing)
    assert run("parity-own-agreement") == "equal"


def test_blink_in_agreement_has_no_finding(tmp_path: Path) -> None:
    board, schematic = cases.blink_project(tmp_path)
    found = cases.compare(board, schematic, own_netlist=True)
    assert found.agree and not found.findings and not found.others


def _demos(folder: Path) -> list[corpus.DemoProject]:
    major = _erccases.major()
    projects, left = corpus.demo_projects(
        folder, corpus.TAG_OF_MAJOR[major], newest=corpus.newest_schematic(major)
    )
    print(f"demos: {len(projects)} compared, left out {left}")
    return projects


@pytest.mark.needs_corpus
@pytest.mark.slow
def test_corpus_demos(tmp_path: Path) -> None:
    projects = _demos(tmp_path)
    assert projects, "no corpus demo with a board and a schematic is cached"
    differing: list[str] = []
    others: dict[str, int] = {}
    for project in projects:
        found = cases.compare(project.board, project.schematic)
        differing += cases.differences(project.id, found)
        for kind, count in found.others.items():
            others[kind] = others.get(kind, 0) + count
        print(f"{project.id}: {dict(found.kicad)}")
    print(f"types without a Fenolite code: {others}")
    assert not differing, "\n".join(differing)


@pytest.mark.needs_corpus
@pytest.mark.parametrize("edit", cases.PROBED)
def test_demo_edits(edit: str, tmp_path: Path) -> None:
    project = cases.pic_project(tmp_path)
    if project is None:
        pytest.skip("the pic_programmer demo of this major's tag is not in the corpus cache")
    board, schematic = project
    cases.with_edit(board, edit, cases.PIC)
    found = cases.compare(board, schematic)
    differing = cases.differences(f"pic_programmer/{edit}", found)
    assert not differing, "\n".join(differing)
    if edit == "dup":
        codes = [f.code for f in found.findings]
        assert codes.count(parity.DUPLICATE) == 1 and codes.count(parity.MISSING) == 1
        assert codes.count(parity.NET_CONFLICT) == found.kicad["net_conflict"]


def test_check_compares_with_kicad(tmp_path: Path) -> None:
    """``check --stages drc.kicad,parity`` on the blink whose pad 2 of ``R1`` is on ``GND``
    (verification-loop, "Parity stage", scenario "Agreement with KiCad")."""
    from _checkrun import check, stage
    from _projects import built_blink_project

    root = built_blink_project(tmp_path / "blink", target=_erccases.major())
    (root / _erccases.BOARD).write_bytes(_erccases.conflict_files()[_erccases.BOARD])
    _, env, _, err = check(root, "--stages", "drc.kicad,parity")
    assert env, err
    found = [(i["code"], i["where"]) for i in env["issues"]]
    assert ("kicad.drc.net-conflict", "R1-2") in found
    assert not [code for code, _ in found if code.startswith("parity.")], found
    summary = stage(env, "parity")["summary"]
    assert summary["compared"] is True and summary["differences"] == 0 and summary["netlist"] == "own"
    assert summary["parity.net-conflict"] == 1
    # the unedited project: nothing on either side
    clean = built_blink_project(tmp_path / "clean", target=_erccases.major())
    _, env, _, err = check(clean, "--stages", "drc.kicad,parity")
    assert env, err
    assert stage(env, "parity")["summary"]["compared"] is True
    assert not [i for i in env["issues"] if i["code"].startswith("parity.")]
