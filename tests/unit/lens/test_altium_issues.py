# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium build's closed table of issue codes (capability altium-build, "Altium build issue codes";
change c0032; ``altium.schematic-too-large`` of change c0033, "Altium schematic format option").

Each case below is a sample variant and the codes its build must report; ``test_closed_set`` runs every
case and checks that the codes produced are exactly the table's, with the table's severities.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager

import pytest
from _altium import sample

import fenolite.lens.altium as lens_altium
from fenolite.backends.altium import cfb
from fenolite.core.errors import Issue
from fenolite.dsl import Design, DiffPair, Net, Part, connect, mm, to_model
from fenolite.lens.altium import ALTIUM_ISSUE_CODES, build_altium

PASS_THROUGH = ("model.", "build.layout-exists")


def _lib_id(d: Design) -> None:
    d.parts["J1"].lib_id = "HDR2"


def _footprint_form(d: Design) -> None:
    d.parts["R2"].footprint = "R0603"


def _text(d: Design) -> None:
    d.parts["power/C1"].value = "10µF"


def _comment_reference(d: Design) -> None:
    d.parts["R2"].value = "=Value"


def _net_pipe(d: Design) -> None:
    d.add(Net("A|B"))


def _case(d: Design) -> None:
    connect(Net("gnd"), d.parts["U2"]["5"], d.parts["R2"]["3"])


def _no_footprint(d: Design) -> None:
    d.parts["led/D1"].footprint = None


def _not_lowered(d: Design) -> None:
    d.board(mm(50), mm(30))
    d.parts["J1"].place(mm(5), mm(5))
    d.rules.netclass("PWR", clearance=mm(0.3), nets=(d.nets["VIN"], d.nets["GND"]))
    d.add(DiffPair(d.nets["EN"], d.nets["LED_DRV"]))


def _custom_sheet(d: Design) -> None:
    a, b = Net("BIG_A"), Net("BIG_B")
    for n in range(1, 701):
        part = Part(f"X{n}", "L.SchLib:RES", "L.PcbLib:R0603", "1k")
        d.add(part)
        connect(a, part[1])
        connect(b, part[2])


def _nothing(d: Design) -> None:
    return None


@contextmanager
def _same_unique_ids() -> Iterator[None]:
    original = lens_altium.unique_id
    lens_altium.unique_id = lambda key: "AAAAAAAA"  # type: ignore[assignment]
    try:
        yield
    finally:
        lens_altium.unique_id = original  # type: ignore[assignment]


CASES: dict[str, tuple[Callable[[Design], None], dict[str, object], set[str]]] = {
    "lib-id": (_lib_id, {}, {"altium.lib-id-form"}),
    "footprint-form": (_footprint_form, {}, {"altium.footprint-form"}),
    "non-ascii": (_text, {}, {"altium.text-unwritable"}),
    "comment-reference": (_comment_reference, {}, {"altium.text-unwritable"}),
    "net-pipe": (_net_pipe, {}, {"altium.text-unwritable"}),
    "case": (_case, {}, {"altium.name-case-collision"}),
    "no-footprint": (_no_footprint, {}, {"altium.no-footprint", "altium.generic-symbols"}),
    "not-lowered": (_not_lowered, {"placed": ("J1",)}, {"altium.not-lowered", "altium.generic-symbols"}),
    "project-kept": (_nothing, {"project_exists": True}, {"altium.project-kept", "altium.generic-symbols"}),
    "custom-sheet": (_custom_sheet, {}, {"altium.sheet-custom", "altium.generic-symbols"}),
    "clean": (_nothing, {}, {"altium.generic-symbols"}),
}


def run_case(name: str) -> tuple[Issue, ...]:
    change, kwargs, _ = CASES[name]
    design = sample()
    change(design)
    return build_altium(to_model(design), name=design.name, **kwargs).issues  # type: ignore[arg-type]


@contextmanager
def _no_fat_sector() -> Iterator[None]:
    original = cfb.MAX_FAT_SECTORS
    cfb.MAX_FAT_SECTORS = 0
    try:
        yield
    finally:
        cfb.MAX_FAT_SECTORS = original


def run_too_large_case(form: str = "binary") -> tuple[Issue, ...]:
    with _no_fat_sector():
        design = sample()
        output = build_altium(to_model(design), name=design.name, form=form)  # type: ignore[arg-type]
        assert (output.files == {}) is (form == "binary")
        return output.issues


def run_unique_id_case() -> tuple[Issue, ...]:
    with _same_unique_ids():
        design = sample()
        return build_altium(to_model(design), name=design.name).issues


@pytest.mark.parametrize("name", sorted(CASES))
def test_case(name: str) -> None:
    issues = run_case(name)
    altium = {i.code for i in issues if not i.code.startswith(PASS_THROUGH)}
    assert altium == CASES[name][2], [i.code for i in issues]


def test_unique_id_collision() -> None:
    issues = run_unique_id_case()
    found = [i for i in issues if i.code == "altium.unique-id-collision"]
    assert len(found) == 7 and all(i.severity == "error" for i in found)


def test_closed_set() -> None:
    produced: dict[str, set[str]] = {}
    for name in CASES:
        for found in run_case(name):
            produced.setdefault(found.code, set()).add(found.severity)
    for found in (*run_unique_id_case(), *run_too_large_case()):
        produced.setdefault(found.code, set()).add(found.severity)
    for code, severities in produced.items():
        if code.startswith(PASS_THROUGH):
            continue
        assert code in ALTIUM_ISSUE_CODES, code
        assert severities == {ALTIUM_ISSUE_CODES[code]}, (code, severities)
    assert set(ALTIUM_ISSUE_CODES) <= set(produced), set(ALTIUM_ISSUE_CODES) - set(produced)


def test_the_table() -> None:
    assert dict(ALTIUM_ISSUE_CODES) == {
        "altium.lib-id-form": "error",
        "altium.footprint-form": "error",
        "altium.text-unwritable": "error",
        "altium.name-case-collision": "error",
        "altium.unique-id-collision": "error",
        "altium.schematic-too-large": "error",
        "altium.no-footprint": "warning",
        "altium.sheet-custom": "warning",
        "altium.generic-symbols": "info",
        "altium.not-lowered": "info",
        "altium.project-kept": "info",
    }


def test_too_large_refused() -> None:
    """With ``cfb.MAX_FAT_SECTORS`` patched to 0 the binary build gives no file; ASCII is not limited."""
    found = [i for i in run_too_large_case() if i.code == "altium.schematic-too-large"]
    assert len(found) == 1 and found[0].severity == "error" and found[0].where == "altium_sample.SchDoc"
    assert "--altium-format ascii" in found[0].hint
    assert "altium.schematic-too-large" not in {i.code for i in run_too_large_case("ascii")}


def test_not_lowered_names_each_kind() -> None:
    found = [i for i in run_case("not-lowered") if i.code == "altium.not-lowered"]
    assert [i.where for i in found] == ["board", "placements", "rules", "interfaces"]
    assert "J1" in found[1].message and "PWR" in found[2].message and "EN/LED_DRV" in found[3].message


def test_errors_write_nothing() -> None:
    for name in ("lib-id", "footprint-form", "non-ascii", "case"):
        design = sample()
        CASES[name][0](design)
        assert build_altium(to_model(design), name=design.name).files == {}


def test_model_issues_pass_through() -> None:
    design = sample()
    design.add(Part("Z1", "L.SchLib:RES", "L.PcbLib:R0603", "1k"))
    connect(Net("FLOATING"), design.parts["Z1"][1])
    codes = [i.code for i in build_altium(to_model(design), name=design.name).issues]
    assert "model.single-pin-net" in codes
