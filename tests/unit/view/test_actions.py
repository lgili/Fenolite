# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The allow-list of the viewer's writing actions (capability board-viewer, "Allowed actions"; c0303)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from fenolite.view.actions import ALTIUM, ActionRefused, ActionRequest, Context, offered, plan, with_flags
from fenolite.view.project import ProjectTree, load_tree

ROOT = Path(__file__).resolve().parents[3]
BOARD = ROOT / "tests" / "data" / "kicad" / "board" / "two_layer.kicad_pcb"
ALTIUM_PROJECT = ROOT / "tests" / "data" / "altium" / "blink" / "blink.PrjPcb"
FINDINGS = (
    {"code": "kicad.drc.clearance", "stage": "drc.kicad", "where": "R1-1, D1-2"},
    {"code": "copper.short", "stage": "copper.clearance", "where": "R1-1, D1-2"},
    {"code": "kicad.drc.unconnected-items", "stage": "drc.kicad", "where": "a:b"},
)
CONTEXT = Context(refs=frozenset({"R1", "D1"}), findings=FINDINGS)


@pytest.fixture
def tree(tmp_path: Path) -> ProjectTree:
    shutil.copy(BOARD, tmp_path / BOARD.name)
    return load_tree(tmp_path / BOARD.name)


def _words(tree: ProjectTree, action: str, **options: object) -> list[str]:
    found = plan({"action": action, "doc": "doc1", "options": options}, tree, CONTEXT)
    assert isinstance(found, ActionRequest), found
    return list(found.words)


def test_templates_give_the_expected_words(tree: ProjectTree) -> None:
    name = BOARD.name
    assert _words(tree, "fill") == ["fill", "--", name]
    assert _words(tree, "tidy", prune=True) == ["tidy", "--prune", "--gate=drc", "--", name]
    assert _words(tree, "tidy", chamfer=True, zones=True, gate_drc=False) == [
        "tidy", "--chamfer", "--zones", "--", name,
    ]  # fmt: skip
    assert _words(tree, "silk", designators=True, keep=True) == [
        "silk",
        "--designators",
        "--keep",
        "--",
        name,
    ]
    assert _words(tree, "testpoints", grid="2.54mm") == ["testpoints", "--place", "--grid=2.54mm", "--", name]
    assert _words(tree, "move", ref="R1", x="12.5mm", y="7mm", rot="90") == [
        "place", "--move=R1=12.5mm,7mm,90", "--", name,
    ]  # fmt: skip
    assert _words(tree, "shift", refs=["R1", "D1"], dx="-1mm", dy="0mm") == [
        "place", "--shift=R1,D1", "--by=-1mm,0mm", "--", name,
    ]  # fmt: skip
    assert _words(tree, "turn", refs=["R1"], about_x="10mm", about_y="5mm", angle="-45") == [
        "place", "--turn=R1", "--about=10mm,5mm", "--angle=-45", "--", name,
    ]  # fmt: skip
    assert _words(tree, "waive", finding=0, reason="by design") == [
        "check", "--exclude=kicad.drc.clearance:R1-1:D1-2", "--reason=by design", "--", name,
    ]  # fmt: skip
    assert _words(tree, "export", kinds=["pdf", "gerbers"]) == [
        "export",
        "--out=fab",
        "--gerbers",
        "--pdf",
        "--",
        name,
    ]
    assert _words(tree, "bom") == ["bom", "--out=fab/bom.csv", "--", name]
    assert with_flags(("fill", "--", name), "--dry-run") == ["fill", "--dry-run", "--", name]


@pytest.mark.parametrize(
    ("action", "options", "reason"),
    [
        ("format_disk", {}, "not an action"),
        ("export", {"out": "../out"}, "leaves the project"),
        ("export", {"out": "/tmp/out"}, "not a relative path"),
        ("export", {"out": "C:/out"}, "not a relative path"),
        ("export", {"out": "fab\\x"}, "not a relative path"),
        ("export", {"kinds": ["step"]}, "each one of"),
        ("bom", {"out": "fab/bom.txt"}, "ending in .csv"),
        ("move", {"ref": "U99", "x": "1mm", "y": "1mm"}, "not a part of this board"),
        ("move", {"ref": "R1", "x": "1", "y": "1mm"}, "a length with its unit"),
        ("move", {"ref": "R1", "x": "1mm; rm -rf", "y": "1mm"}, "a length with its unit"),
        ("move", {"ref": "R1", "x": "1mm"}, "needs y"),
        ("shift", {"refs": ["R1", "R1,U1"], "dx": "1mm", "dy": "1mm"}, "not a part"),
        ("waive", {"finding": 0, "reason": "two\nlines"}, "one line"),
        ("waive", {"finding": 0, "reason": ""}, "one line"),
        ("waive", {"finding": 1, "reason": "ok"}, "only a finding of KiCad's DRC"),
        ("waive", {"finding": 2, "reason": "ok"}, "does not name one or two items"),
        ("waive", {"finding": 9, "reason": "ok"}, "the index of a finding"),
        ("silk", {"no_backup": True, "clip": True}, "--no-backup is never set"),
        ("silk", {"out": "x.kicad_pcb"}, "takes no option 'out'"),
        ("silk", {}, "choose designators or clip"),
        ("tidy", {"zones": True, "prune": True}, "zones goes with chamfer"),
        ("testpoints", {"grid": "-1mm"}, "above 0"),
        ("fill", {"kicad_cli": "/bin/sh"}, "takes no option"),
    ],
)
def test_refused_actions(tree: ProjectTree, action: str, options: dict[str, object], reason: str) -> None:
    """Scenario "Refused actions"."""
    found = plan({"action": action, "doc": "doc1", "options": options}, tree, CONTEXT)
    assert isinstance(found, ActionRefused)
    assert reason in found.reason


def test_symlink_out_of_the_root_is_refused(tmp_path: Path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    shutil.copy(BOARD, project / BOARD.name)
    (tmp_path / "elsewhere").mkdir()
    (project / "fab").symlink_to(tmp_path / "elsewhere")
    found = plan({"action": "export", "doc": "doc1", "options": {"out": "fab"}}, load_tree(project), CONTEXT)
    assert isinstance(found, ActionRefused) and "outside the project" in found.reason


def test_altium_documents_are_not_written() -> None:
    tree = load_tree(ALTIUM_PROJECT)
    board = next(d for d in tree.documents if d.kind == "pcb")
    found = plan({"action": "silk", "doc": board.id, "options": {"clip": True}}, tree, CONTEXT)
    assert isinstance(found, ActionRefused) and found.reason == ALTIUM
    offer = offered(tree, board)
    assert all(not row["available"] and row["why"] == ALTIUM for row in offer.values())


def test_roles_names_checked_against_the_role_data(tree: ProjectTree) -> None:
    """Scenario "Confirm a role from the page" (c0305): Confirm roles is ``roles --accept`` and
    ``--accept-group`` on the board, naming only the inferred roles and groups of the session's role data."""
    context = Context(roles=frozenset({"SW", "GH"}), groups=frozenset({"hot_SW"}))

    def ask(**options: object) -> ActionRequest | ActionRefused:
        return plan({"action": "roles", "doc": "doc1", "options": options}, tree, context)

    found = ask(nets=["SW"])
    assert isinstance(found, ActionRequest) and list(found.words) == [
        "roles",
        "--accept=SW",
        "--",
        BOARD.name,
    ]
    both = ask(nets=["SW", "GH", "SW"], groups=["hot_SW"])
    assert isinstance(both, ActionRequest)
    assert list(both.words) == ["roles", "--accept=SW,GH", "--accept-group=hot_SW", "--", BOARD.name]
    assert found.target == tree.root / BOARD.name
    for options, reason in (
        ({"nets": ["NOPE"]}, "'NOPE' is not an inferred net"),
        ({"groups": ["SW"]}, "'SW' is not an inferred group"),
        ({"nets": ["SW,GH"]}, "is not an inferred net"),
        ({"nets": "SW"}, "a list of names"),
        ({}, "choose the nets or groups"),
    ):
        refused = ask(**options)
        assert isinstance(refused, ActionRefused) and reason in refused.reason, (options, refused)
    bare = plan({"action": "roles", "doc": "doc1", "options": {"nets": ["SW"]}}, tree, CONTEXT)
    assert isinstance(bare, ActionRefused) and "no role data" in bare.reason


def test_offered_lists_every_action(tree: ProjectTree) -> None:
    offer = offered(tree, tree.document("doc1"))
    assert sorted(offer) == sorted(
        ["bom", "export", "fill", "move", "roles", "shift", "silk", "testpoints", "tidy", "turn", "waive"]
    )
    assert offer["tidy"]["options"]["gate_drc"]["default"] is True and offer["fill"]["available"] is True
