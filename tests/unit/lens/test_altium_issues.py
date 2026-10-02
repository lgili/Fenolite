# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Altium build's closed table of issue codes (capability altium-build, "Altium build issue codes";
change c0032; ``altium.schematic-too-large`` of change c0033, "Altium schematic format option").

Each case below is a sample variant and the codes its build must report; ``test_closed_set`` runs every
case and checks that the codes produced are exactly the table's, with the table's severities.
"""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

import pytest
from _altium import EXAMPLE_DIR, blink, blink_resolver, blink_tree, example, example_resolver, sample

import fenolite.lens.altium as lens_altium
from fenolite.backends.altium import cfb
from fenolite.core.errors import Issue
from fenolite.dsl import Design, DiffPair, Net, Part, connect, mm, placements, to_model
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


def _library_case(d: Design) -> None:
    d.parts["J1"].lib_id = "fenolitesample.schlib:HDR2"


def _long_lib_ref(d: Design) -> None:
    d.parts["J1"].lib_id = "FenoliteSample.SchLib:" + "HEADER_" * 6


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
    "no-footprint": (
        _no_footprint,
        {},
        {
            "altium.no-footprint",
            "altium.generic-symbols",
            "altium.pcbdoc-not-written",
            "altium.schlib-generic",
        },
    ),
    "not-lowered": (
        _not_lowered,
        {"placed": ("J1",)},
        {
            "altium.not-lowered",
            "altium.generic-symbols",
            "altium.pcbdoc-not-written",
            "altium.schlib-generic",
        },
    ),
    "project-kept": (
        _nothing,
        {"project_exists": True},
        {
            "altium.project-kept",
            "altium.schlib-not-in-project",
            "altium.generic-symbols",
            "altium.pcbdoc-not-written",
            "altium.schlib-generic",
        },
    ),
    "custom-sheet": (
        _custom_sheet,
        {},
        {
            "altium.sheet-custom",
            "altium.generic-symbols",
            "altium.pcbdoc-not-written",
            "altium.schlib-generic",
        },
    ),
    "clean": (_nothing, {}, {"altium.generic-symbols", "altium.schlib-generic", "altium.pcbdoc-not-written"}),
    "library-case": (_library_case, {}, {"altium.symbol-name-collision", "altium.schlib-generic"}),
    "section-key": (
        _long_lib_ref,
        {},
        {
            "altium.section-key",
            "altium.generic-symbols",
            "altium.pcbdoc-not-written",
            "altium.schlib-generic",
        },
    ),
}


KICAD_CASES: dict[str, tuple[tuple[str, str], tuple[str, str], set[str]]] = {
    "kicad-clean": (
        ("", ""),
        ("", ""),
        {"altium.symbol-simplified", "altium.footprint-unresolved", "altium.pcbdoc-not-written"},
    ),
    "unknown-pin": (
        ("u1[8]", 'u1["XYZ"]'),
        ("", ""),
        {"altium.unknown-pin", "altium.symbol-simplified"},
    ),
    "off-grid": (
        ("", ""),
        ("(at 0 3.81 270)", "(at 0.001 3.81 270)"),
        {"altium.symbol-off-grid", "altium.symbol-simplified"},
    ),
    "lossy": (
        ("", ""),
        (
            "(pin passive line\n\t\t\t\t(at 2.54 -7.62 90)",
            "(pin no_connect non_logic\n\t\t\t\t(at 2.54 -7.62 90)",
        ),
        {
            "altium.pin-lossy",
            "altium.symbol-simplified",
            "altium.footprint-unresolved",
            "altium.pcbdoc-not-written",
        },
    ),
    "pin-text-too-long": (
        ("", ""),
        ('"CLK"', '"' + "C" * 256 + '"'),
        {"altium.pin-text-too-long", "altium.symbol-simplified"},
    ),
    "description": (
        ("", ""),
        ("Resistor drawn upright", "Résistance"),
        {"altium.text-unwritable", "altium.symbol-simplified"},
    ),
}
"""KiCad-example variants (change c0034): (script change, library change, codes)."""


def run_kicad_case(name: str) -> tuple[Issue, ...]:
    (old, new), (lib_old, lib_new), _ = KICAD_CASES[name]
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        copy = root / "example"
        shutil.copytree(EXAMPLE_DIR, copy)
        if lib_old:
            library = copy / "FenoliteDemo.kicad_sym"
            text = library.read_text(encoding="utf-8")
            assert lib_old in text, lib_old
            library.write_text(text.replace(lib_old, lib_new), encoding="utf-8")
        design = example(old, new) if old else example()
        resolver = example_resolver(root, project_dir=copy)
        return build_altium(to_model(design), name=design.name, resolver=resolver).issues


@pytest.mark.parametrize("name", sorted(KICAD_CASES))
def test_kicad_case(name: str) -> None:
    issues = run_kicad_case(name)
    altium = {i.code for i in issues if not i.code.startswith(PASS_THROUGH)}
    assert altium == KICAD_CASES[name][2], [i.code for i in issues]


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
        assert output.files == {}
        expected = "altium.schematic-too-large" if form == "binary" else "altium.library-too-large"
        assert expected in {i.code for i in output.issues}
        return output.issues


def run_unique_id_case() -> tuple[Issue, ...]:
    with _same_unique_ids():
        design = sample()
        return build_altium(to_model(design), name=design.name).issues


TRAPEZOID = ("Mini_R_0603", '(pad "1" smd roundrect', '(pad "1" smd trapezoid')
OTHER_ROW = (
    '(descr "Authored CC0 mini library"))',
    '(descr "Authored CC0 mini library"))\n\t(lib (name "Other") (type "KiCad") '
    '(uri "${KIPRJMOD}/../../tests/data/libs/Mini.pretty") (options "") (descr ""))',
)
SECOND_R = (
    "design.add(u1, r1, d1)",
    'r2 = Part("R2", "Mini:Mini_R", footprint="Other:Mini_R_0603", value="1k")\ndesign.add(u1, r1, d1, r2)',
)
BLINK_CODES = {"altium.not-lowered", "altium.symbol-simplified", "altium.primitive-dropped",
               "altium.footprint-extras-dropped"}  # fmt: skip
PCB_CASES: dict[str, tuple[dict[str, object], set[str]]] = {
    "blink": ({}, BLINK_CODES),
    "blink-kept": (
        {"project_exists": True},
        BLINK_CODES | {"altium.project-kept", "altium.schlib-not-in-project", "altium.pcb-not-in-project"},
    ),
    "blink-unplaced": (
        {"script": ("r1.place(mm(32), mm(9))", "")},
        BLINK_CODES | {"altium.pcb-staged"},
    ),
    "blink-unsupported": (
        {"footprint": TRAPEZOID},
        BLINK_CODES | {"altium.footprint-unsupported", "altium.pcbdoc-not-written"},
    ),
    "blink-collision": (
        {"fp_table": OTHER_ROW, "script": SECOND_R},
        BLINK_CODES | {"altium.footprint-name-collision", "altium.pcbdoc-not-written"},
    ),
}
"""Blink variants (change c0035): tree edits and build arguments, and the codes the build reports."""


def run_pcb_case(name: str) -> tuple[Issue, ...]:
    edits, _ = PCB_CASES[name]
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        project = blink_tree(
            root,
            fp_table=edits.get("fp_table", ("", "")),  # type: ignore[arg-type]
            footprint=edits.get("footprint", ("", "", "")),  # type: ignore[arg-type]
        )
        script = edits.get("script", ("", ""))
        design = blink(*script)  # type: ignore[misc]
        kwargs = {k: v for k, v in edits.items() if k == "project_exists"}
        return build_altium(
            to_model(design),
            name=design.name,
            placed=tuple(placements(design)),
            placements=placements(design),
            resolver=blink_resolver(root, project),
            **kwargs,  # type: ignore[arg-type]
        ).issues


def run_pcb_too_large() -> tuple[Issue, ...]:
    import fenolite.backends.altium.project as altium_project

    original = altium_project.write_pcblib

    def refuse(footprints: object) -> bytes:
        raise cfb.CompoundTooLarge("patched")

    altium_project.write_pcblib = refuse  # type: ignore[assignment]
    try:
        with tempfile.TemporaryDirectory() as folder:
            design = blink()
            output = build_altium(to_model(design), name=design.name, resolver=blink_resolver(Path(folder)))
    finally:
        altium_project.write_pcblib = original  # type: ignore[assignment]
    assert output.files == {}
    return output.issues


@pytest.mark.parametrize("name", sorted(PCB_CASES))
def test_pcb_case(name: str) -> None:
    issues = run_pcb_case(name)
    altium = {i.code for i in issues if not i.code.startswith(PASS_THROUGH)}
    assert altium == PCB_CASES[name][1], [i.code for i in issues]


def test_pcb_too_large() -> None:
    """``altium-build`` "PCB issue codes", "Too large refused"."""
    found = [i for i in run_pcb_too_large() if i.code == "altium.pcb-too-large"]
    assert len(found) == 1 and found[0].severity == "error" and found[0].where == "blink.PcbLib"


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
    for name in KICAD_CASES:
        for found in run_kicad_case(name):
            produced.setdefault(found.code, set()).add(found.severity)
    for name in PCB_CASES:
        for found in run_pcb_case(name):
            produced.setdefault(found.code, set()).add(found.severity)
    for found in (
        *run_unique_id_case(),
        *run_too_large_case(),
        *run_too_large_case("ascii"),
        *run_pcb_too_large(),
    ):
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
        "altium.library-too-large": "error",
        "altium.unknown-pin": "error",
        "altium.symbol-off-grid": "error",
        "altium.pin-text-too-long": "error",
        "altium.symbol-name-collision": "error",
        "altium.pcb-too-large": "error",
        "altium.no-footprint": "warning",
        "altium.sheet-custom": "warning",
        "altium.pin-lossy": "warning",
        "altium.footprint-unresolved": "warning",
        "altium.footprint-unsupported": "warning",
        "altium.footprint-name-collision": "warning",
        "altium.primitive-dropped": "warning",
        "altium.generic-symbols": "info",
        "altium.symbol-simplified": "info",
        "altium.section-key": "info",
        "altium.schlib-generic": "info",
        "altium.schlib-not-in-project": "info",
        "altium.not-lowered": "info",
        "altium.project-kept": "info",
        "altium.footprint-extras-dropped": "info",
        "altium.pcbdoc-not-written": "info",
        "altium.pcb-staged": "info",
        "altium.pcb-not-in-project": "info",
    }


def test_too_large_refused() -> None:
    """With ``cfb.MAX_FAT_SECTORS`` patched to 0 the binary build gives no file. The ASCII schematic is not
    limited, but the libraries are always compound files, so the ASCII build gives
    ``altium.library-too-large`` instead (change c0034)."""
    found = [i for i in run_too_large_case() if i.code == "altium.schematic-too-large"]
    assert len(found) == 1 and found[0].severity == "error" and found[0].where == "altium_sample.SchDoc"
    assert "--altium-format ascii" in found[0].hint
    ascii_codes = {i.code for i in run_too_large_case("ascii")}
    assert "altium.schematic-too-large" not in ascii_codes and "altium.library-too-large" in ascii_codes


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


def test_library_infos_name_the_libraries() -> None:
    (generic,) = [i for i in run_case("clean") if i.code == "altium.schlib-generic"]
    assert generic.where == "FenoliteSample.SchLib" and "stands in for a real library" in generic.message
    (listing,) = [i for i in run_case("project-kept") if i.code == "altium.schlib-not-in-project"]
    assert "FenoliteSample.SchLib" in listing.message
    (key,) = [i for i in run_case("section-key") if i.code == "altium.section-key"]
    assert "HEADER_HEADER_" in key.message


def test_generic_symbols_only_for_altium_links() -> None:
    assert "altium.generic-symbols" not in {i.code for i in run_kicad_case("kicad-clean")}
    (info,) = [i for i in run_case("clean") if i.code == "altium.generic-symbols"]
    assert info.message.startswith("8 component(s) of Altium links")


def test_off_grid_names_symbol_and_pin() -> None:
    (found,) = [i for i in run_kicad_case("off-grid") if i.code == "altium.symbol-off-grid"]
    assert "FenoliteDemo:R_V pin 1" in found.message and found.where == "FenoliteDemo:R_V"
