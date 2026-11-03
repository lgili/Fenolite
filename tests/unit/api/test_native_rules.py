# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native project-context level6, separately from pure canonical model rules (c0352)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
from _importcode import TWO_SHEET

from fenolite.api import equivalent
from fenolite.api.sides import read_side
from fenolite.core.errors import FormatError


def project(folder: Path) -> Path:
    shutil.copytree(TWO_SHEET, folder)
    return folder / "two_sheet.kicad_pro"


def edit(path: Path, change) -> None:
    data = json.loads(path.read_text())
    change(data)
    path.write_text(json.dumps(data))


@pytest.mark.parametrize(
    "key",
    (
        "min_clearance",
        "min_track_width",
        "min_via_diameter",
        "min_through_hole_diameter",
        "min_copper_edge_clearance",
    ),
)
def test_native_floor_tamper_below_all_class_limits_is_a_level6_difference(tmp_path: Path, key: str) -> None:
    a, b = project(tmp_path / "a"), project(tmp_path / "b")
    edit(a, lambda data: data["board"]["design_settings"]["rules"].update({key: 0.001}))
    edit(b, lambda data: data["board"]["design_settings"]["rules"].update({key: 0.002}))
    result = equivalent(a, b, level=6)
    assert not result.equivalent
    assert result.report is not None
    assert any(d.level == 6 and d.field == key for d in result.report.differences)
    # The hard floor has no canonical Design field; no hidden property is fabricated.
    assert equivalent(read_side(a).design, read_side(b).design, level=6).equivalent


def test_default_native_class_tamper_is_not_hidden_by_empty_readside_classes(tmp_path: Path) -> None:
    a, b = project(tmp_path / "a"), project(tmp_path / "b")
    edit(a, lambda data: data["net_settings"]["classes"][0].update(clearance=0.15))
    edit(b, lambda data: data["net_settings"]["classes"][0].update(clearance=0.2))
    result = equivalent(a, b, level=6)
    assert not result.equivalent
    assert result.report is not None
    assert any(d.kind == "netclass-field" and d.field == "clearance" for d in result.report.differences)


def test_native_assignment_change_fails_with_unchanged_class_values(tmp_path: Path) -> None:
    a, b = project(tmp_path / "a"), project(tmp_path / "b")
    for path in (a, b):
        edit(
            path,
            lambda data: data["net_settings"].update(
                netclass_patterns=[{"netclass": "Power", "pattern": "VIN"}], netclass_assignments={}
            ),
        )
    edit(b, lambda data: data["net_settings"].update(netclass_patterns=[]))
    result = equivalent(a, b, level=6)
    assert not result.equivalent
    assert result.report is not None
    assert any(d.kind == "netclass-members" for d in result.report.differences)


def test_traced_native_context_cannot_be_reused_after_its_bytes_change(tmp_path: Path) -> None:
    from fenolite.api._native_rules import context

    path = project(tmp_path / "source")
    side = read_side(path)
    path.write_text(path.read_text() + " ")
    with pytest.raises(FormatError, match="changed"):
        context(side)


@pytest.mark.parametrize("fault", ("duplicate-class", "inexact-class", "missing-floor", "future"))
def test_unjudged_or_malformed_native_rules_cannot_claim_complete_equality(
    tmp_path: Path, fault: str
) -> None:
    a, b = project(tmp_path / "a"), project(tmp_path / "b")

    def change(data):
        if fault == "duplicate-class":
            data["net_settings"]["classes"].append(data["net_settings"]["classes"][0].copy())
        elif fault == "inexact-class":
            data["net_settings"]["classes"][0]["clearance"] = 0.0000001
        elif fault == "missing-floor":
            data["board"]["design_settings"]["rules"].pop("min_clearance")
        else:
            data["meta"]["version"] = 999

    edit(a, change)
    with pytest.raises(FormatError):
        equivalent(a, b, level=6)


def test_tamper_is_detected_on_reused_and_fresh_native_paths(tmp_path: Path) -> None:
    a, b = project(tmp_path / "a"), project(tmp_path / "b")
    for path in (a, b):
        edit(path, lambda data: data["board"]["design_settings"]["rules"].update(min_clearance=0.001))
    assert equivalent(a, b, level=6).equivalent
    edit(b, lambda data: data["board"]["design_settings"]["rules"].update(min_clearance=0.002))
    assert not equivalent(a, b, level=6).equivalent
    shutil.copytree(b.parent, tmp_path / "fresh")
    assert not equivalent(a, tmp_path / "fresh" / b.name, level=6).equivalent


def test_renamed_raw_net_is_bound_by_partition_and_effective_class(tmp_path: Path) -> None:
    from fenolite.backends.kicad.sexpr import Atom, AtomKind, Node, dumps, parse

    a, b = project(tmp_path / "a"), project(tmp_path / "b")
    for path in (a, b):
        edit(
            path,
            lambda data: data["net_settings"].update(
                netclass_patterns=[{"netclass": "Power", "pattern": "VIN"}], netclass_assignments={}
            ),
        )

    def rename(node):
        return node.with_children(
            tuple(
                rename(child)
                if isinstance(child, Node)
                else Atom.string("RENAMED{slash}VIN")
                if node.name == "net" and child.kind == AtomKind.STRING and child.value == "VIN"
                else child
                for child in node.children
            )
        )

    board = b.with_suffix(".kicad_pcb")
    board.write_text(dumps(rename(parse(board.read_text()))))
    edit(
        b,
        lambda data: data["net_settings"].update(
            netclass_patterns=[{"netclass": "Power", "pattern": "RENAMED{slash}VIN"}], netclass_assignments={}
        ),
    )
    result = equivalent(a, b, level=6)
    assert result.equivalent, result.report.differences if result.report else None
    edit(b, lambda data: data["net_settings"].update(netclass_patterns=[]))
    result = equivalent(a, b, level=6)
    assert not result.equivalent
    assert result.report is not None and any(d.kind == "netclass-members" for d in result.report.differences)


def test_multiple_effective_native_classes_are_not_collapsed_to_one(tmp_path: Path) -> None:
    a, b = project(tmp_path / "a"), project(tmp_path / "b")
    edit(
        a,
        lambda data: data["net_settings"].update(
            netclass_patterns=[
                {"netclass": "Default", "pattern": "VIN"},
                {"netclass": "Power", "pattern": "VIN"},
            ],
            netclass_assignments={},
        ),
    )
    with pytest.raises(FormatError, match="not fully represented"):
        equivalent(a, b, level=6)


def test_native_summary_names_judged_scope_and_preserves_existing_differences(tmp_path: Path) -> None:
    a, b = project(tmp_path / "a"), project(tmp_path / "b")
    edit(
        b, lambda data: data["board"]["design_settings"]["rules"].update(min_clearance=0.001, max_error=0.01)
    )
    result = equivalent(a, b, level=6)
    assert result.report is not None
    fields = {d.field for d in result.report.differences}
    assert {"min_clearance", "max_curve_error"} <= fields
    level = next(level for level in result.report.levels if level.level == 6)
    context = level.summary["native_project_rules"]
    assert "min_clearance" in context["judged_keys"]
    assert context["a_read_files"] and context["b_read_files"]
    assert "custom DRU" in context["unjudged"]


@pytest.mark.parametrize("fault", ("duplicate-reference", "conflicting-stacked-pad", "unbound-net"))
def test_native_physical_binding_ambiguity_never_claims_class_equality(tmp_path: Path, fault: str) -> None:
    from fenolite.backends.kicad.derived_teardrops import native_net
    from fenolite.backends.kicad.sexpr import Node, dumps, parse

    a, b = project(tmp_path / "a"), project(tmp_path / "b")
    board = a.with_suffix(".kicad_pcb")
    root = parse(board.read_text())
    fp = root.nodes("footprint")[0]
    if fault == "duplicate-reference":
        root = root.with_children((*root.children, fp))
    elif fault == "unbound-net":
        orphan = parse(
            '(segment (start 10 10) (end 11 10) (width 0.1) (layer "F.Cu") '
            '(net "AUTHOR_UNBOUND") (uuid "00000000-0000-4000-8000-000000003559"))'
        )
        root = root.with_children((*root.children, orphan))
    else:
        pad = next(p for p in fp.nodes("pad") if p.nodes("net"))
        other = next(
            p
            for f in root.nodes("footprint")
            for p in f.nodes("pad")
            if p.nodes("net") and native_net(p, root) != native_net(pad, root)
        )
        changed = pad.with_children(
            tuple(
                other.nodes("net")[0] if isinstance(child, Node) and child.name == "net" else child
                for child in pad.children
            )
        )
        changed_fp = fp.with_children((*fp.children, changed))
        root = root.with_children(tuple(changed_fp if child is fp else child for child in root.children))
    board.write_text(dumps(root))
    with pytest.raises(FormatError):
        equivalent(a, b, level=6)
