# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Readable schematic in an Altium build (capability altium-build, "Readable schematic in an Altium
build"; change c0086).

- ``test_readback`` settles ``H-A-SCHX-READBACK`` at INFERRED: the tree sample and every example read
  back, with Fenolite's own reader and importer, to the nets, designators, modules, buses, values and
  parameters they were written from.
- ``test_nets_unchanged``: the nets and designators of every committed sample are those recorded before
  this change (``tests/data/altium/nets_before_c0086.json``, read from the files of commit 6cdf0aea).
- ``test_tree``: a fresh build equals the committed ``tests/data/altium/tree/``.
- ``test_generic``: ``symbol_bodies="generic"`` still gives the bytes of the four samples as the
  maintainer's author reports covered them (``tests/data/altium/generic/``). Change c0134 changed three
  symbols of the example library, so the two samples that use it are built for this test from the
  library of commit 6cdf0aea, kept as ``tests/data/altium/generic/library/FenoliteDemo.kicad_sym``.

``FENOLITE_GOLDEN_WRITE=1`` rewrites the tree files instead of comparing them.
"""

from __future__ import annotations

import dataclasses
import json
import os
import tempfile
from pathlib import Path

import pytest
from _altium import (
    EXAMPLE_DIR,
    EXAMPLE_NETS,
    HIER_NETS,
    NO_CONNECT_NETS,
    SAMPLE_NETS,
    blink,
    blink_resolver,
    example,
    example_resolver,
    hier,
    no_connect_example,
    sample,
)
from _altium_copper import routed_build
from _altium_job import example_sheet, sheet_parameters
from _altium_tree import (
    TREE_DIR,
    TREE_FILES,
    TREE_NETS,
    documents,
    nets_of,
    project_files,
    read_back,
    tree_build,
    tree_model,
)

from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.read.sch import Parameter
from fenolite.backends.altium.read.schlib import read_schlib
from fenolite.backends.altium.read.sheet import import_sheet
from fenolite.backends.altium.schdot import written_scope
from fenolite.dsl import placements, to_model
from fenolite.lens.altium import build_altium
from fenolite.lens.build import BuildOutput

DATA = Path(__file__).resolve().parents[3] / "tests" / "data" / "altium"
RECORDED = DATA / "nets_before_c0086.json"
GENERIC = DATA / "generic"
WRITE = os.environ.get("FENOLITE_GOLDEN_WRITE") == "1"
FORMS = ("binary", "ascii")
BODIES = ("graphics", "generic")


FROZEN_LIBRARY = GENERIC / "library" / "FenoliteDemo.kicad_sym"
"""The example library as commit 6cdf0aea held it, before change c0134 hid the pin names of ``CONN2`` and
gave ``MCU8`` and ``DUAL_OPAMP`` larger bodies. The generic copies of ``kicad_example`` and ``no_connect``
are builds of this library, so ``test_generic`` builds them from it."""


def frozen_project(folder: Path) -> Path:
    """A project folder under ``folder`` with the example's own library table and ``FROZEN_LIBRARY``."""
    project = folder / "project"
    project.mkdir(parents=True)
    (project / "sym-lib-table").write_bytes((EXAMPLE_DIR / "sym-lib-table").read_bytes())
    (project / FROZEN_LIBRARY.name).write_bytes(FROZEN_LIBRARY.read_bytes())
    return project


def build_example(which: str, folder: Path, *, frozen: bool = False, **kwargs: object) -> BuildOutput:
    """One of the example scripts built for the Altium target; ``frozen`` resolves the symbols of the
    two samples of ``examples/altium_kicad`` from ``FROZEN_LIBRARY`` instead of the example's library."""
    if which == "sample":
        design = sample()
        return build_altium(to_model(design), name=design.name, **kwargs)  # type: ignore[arg-type]
    if which == "hier":
        design = hier()
        return build_altium(to_model(design), name=design.name, **kwargs)  # type: ignore[arg-type]
    if which in ("kicad_example", "no_connect"):
        design = example() if which == "kicad_example" else no_connect_example()
        resolver = example_resolver(folder, frozen_project(folder)) if frozen else example_resolver(folder)
        return build_altium(to_model(design), name=design.name, resolver=resolver, **kwargs)  # type: ignore[arg-type]
    if which == "blink":
        design = blink()
        return build_altium(
            to_model(design),
            name=design.name,
            placed=tuple(placements(design)),
            placements=placements(design),
            resolver=blink_resolver(folder),
            **kwargs,  # type: ignore[arg-type]
        )
    assert which == "routed"
    return routed_build(folder, **kwargs)


EXPECTED: dict[str, dict[str, set[tuple[str, str]]] | None] = {
    "sample": SAMPLE_NETS,
    "hier": HIER_NETS,
    "kicad_example": EXAMPLE_NETS,
    "no_connect": NO_CONNECT_NETS,
    "blink": None,
    "routed": None,
}
"""Example → its nets written out by hand, or ``None``: then the built model is the reference."""


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("bodies", BODIES)
@pytest.mark.parametrize("which", sorted(EXPECTED))
def test_readback_of_the_examples(which: str, bodies: str, form: str, tmp_path: Path) -> None:
    """``test_readback``: every example script, in both forms and with both symbol bodies, reads back to
    its nets and designators; ``hier`` also as sheets per module."""
    modes = ("flat", "modules") if which == "hier" else ("flat",)
    for sheets in modes:
        output = build_example(
            which, tmp_path / "libs" / sheets, form=form, symbol_bodies=bodies, sheets=sheets
        )
        assert output.files, [i.message for i in output.issues if i.severity == "error"]
        design = read_back(tmp_path / "out" / sheets, output)
        expected = EXPECTED[which] or nets_of(output.design)
        assert nets_of(design) == expected
        assert sorted(c.ref for c in design.circuit.components) == sorted(
            c.ref for c in output.design.circuit.components
        )


@pytest.mark.parametrize("form", FORMS)
@pytest.mark.parametrize("sheets", ["flat", "modules"])
def test_readback_of_the_tree(form: str, sheets: str, tmp_path: Path) -> None:
    """``test_readback``: the symbols' pins, the modules, the bus, the texts and the parameters of the
    tree sample come back as they were written."""
    output = tree_build(form=form, sheets=sheets)
    assert not [i for i in output.issues if i.severity == "error"]
    design, model = read_back(tmp_path, output), output.design
    assert nets_of(design) == TREE_NETS == nets_of(model)
    mine = {c.ref: c for c in design.circuit.components}
    for want in model.circuit.components:
        got = mine[want.ref]
        assert got.value == want.value, want.ref
        kept = {k: v for k, v in want.properties.items() if not k.startswith("fenolite.")}
        assert {k: got.properties.get(k) for k in kept} == kept, want.ref
    assert sorted(m.path for m in design.circuit.modules) == (
        ["io", "io/leds", "power"] if sheets == "modules" else []
    )
    names = {net.id: net.name for net in design.circuit.nets}
    assert {(bus.name, tuple(names[m.net_id] for m in bus.members)) for bus in design.circuit.buses} == {
        ("D", ("D0", "D1", "D2", "D3"))
    }


def test_nets_unchanged() -> None:
    """Scenario "Nets unchanged": the netlist and the designators read from each committed sample project
    equal the ones recorded from the files this change found."""
    recorded = json.loads(RECORDED.read_text(encoding="utf-8"))
    # the seven sample projects that existed at commit 6cdf0aea; later samples have no reading before
    assert sorted({project.split("/")[0] for project in recorded}) == [
        "blink", "hier", "kicad_example", "no_connect", "routed", "sample",
    ]  # fmt: skip
    assert len(recorded) == 7
    for project, before in recorded.items():
        design = AltiumBackend().read(DATA / project).design
        refs = {c.id: c.ref for c in design.circuit.components}
        nets = {
            n.name: sorted(f"{refs[m.component_id]}.{m.pin}" for m in n.members) for n in design.circuit.nets
        }
        assert nets == before["nets"], project
        assert sorted(refs.values()) == before["refs"], project


def test_tree() -> None:
    """Scenario "Tree sample": the built files equal the committed ones, and the summary counts four
    sheets, eight symbols drawn from their graphics and none simplified."""
    output = tree_build()
    assert [i.code for i in output.issues if i.severity in ("warning", "error")] == ["altium.pin-lossy"]
    files = project_files(output)
    assert sorted(files) == sorted(TREE_FILES)
    summary = output.summary["schematic"]
    assert summary == {
        "sheets": 4,
        "symbols": "graphics",
        "symbols_drawn": 8,
        "symbols_simplified": 0,
        "buses": 4,
        "parameters": 2,
        "directions": "on",
        "directed": 6,
    }
    assert output.summary["sheets"] == [
        "tree.SchDoc",
        "tree_io.SchDoc",
        "tree_io.leds.SchDoc",
        "tree_power.SchDoc",
    ]
    if WRITE:
        for name, data in files.items():
            (TREE_DIR / name).write_bytes(data)
        pytest.skip("tree golden files rewritten (FENOLITE_GOLDEN_WRITE=1)")
    assert sorted(p.name for p in TREE_DIR.iterdir()) == sorted([*TREE_FILES, "design.py"])
    for name, data in files.items():
        assert (TREE_DIR / name).read_bytes() == data, f"tree/{name} differs from a fresh build"
    assert tree_build().files == output.files  # a second build gives the same bytes


def test_tree_library_draws_pin_names_only_on_the_plain_box() -> None:
    """Change c0134, on the committed library: the transistor and the two amplifiers, whose names lay on
    each other, draw none and keep every name in the file; the regulator, a plain box of 600 mil sized
    for its names, draws them; every pin number is drawn."""
    library = read_schlib((TREE_DIR / "tree.SchLib").read_bytes(), file="tree.SchLib")
    pins = {c.name: [(p.designator, p.name, p.name_shown) for p in c.pins] for c in library.components}
    assert sorted(pins["BJT_NPN"]) == [("1", "B", False), ("2", "C", False), ("3", "E", False)]
    amplifier = [
        ("1", "", False),
        ("2", "+", False),
        ("3", "-", False),
        ("4", "V+", False),
        ("5", "V-", False),
    ]
    assert sorted(pins["Comparator"]) == sorted(pins["Operational_Amplifier"]) == amplifier
    assert sorted(pins["Linear_Regulator"]) == [("1", "IN", True), ("2", "GND", True), ("3", "OUT", True)]
    assert all(p.designator_shown for c in library.components for p in c.pins)
    ends = {p.name: tuple(v.nm() // 25_400 for v in p.location) for p in library.get("Linear_Regulator").pins}
    assert ends == {"IN": (-300, 200), "GND": (0, -300), "OUT": (300, 200)}  # body ends, in mil


def test_tree_script_alone_builds_without_the_bus() -> None:
    """The DSL has no bus: the script as it is gives the same sheets with member ports instead."""
    model = tree_model()
    stripped = tree_build(dataclasses.replace(model, circuit=dataclasses.replace(model.circuit, buses=())))
    sheets = documents(stripped)
    assert all(sheet.buses() == () for sheet in sheets.values())
    assert sorted(p.name for p in sheets["tree_io.leds.SchDoc"].ports()) == ["D0", "D1", "D2", "D3", "LED_K"]


GENERIC_FILES = {
    "blink": ("blink.SchDoc", "blink.SchLib"),
    "kicad_example": ("altium_kicad.SchDoc", "altium_kicad.SchLib"),
    "no_connect": ("altium_no_connect.SchDoc", "altium_no_connect.SchLib"),
    "routed": ("routed.SchDoc", "routed.SchLib"),
}
"""Sample → the files that differ between the two symbol bodies; every other file of a sample is the
same in both and is compared by the sample's own golden test."""


@pytest.mark.parametrize("which", sorted(GENERIC_FILES))
def test_generic(which: str) -> None:
    """``--altium-symbols generic`` gives the bytes of commit 6cdf0aea, the form that the maintainer's
    author reports covered; the other files of the sample do not depend on the option. The symbols of
    ``kicad_example`` and ``no_connect`` come from the library of that commit (``FROZEN_LIBRARY``)."""
    with tempfile.TemporaryDirectory() as folder:
        generic = project_files(
            build_example(which, Path(folder) / "a", symbol_bodies="generic", frozen=True)
        )
        graphics = project_files(build_example(which, Path(folder) / "b"))
    assert sorted(p.name for p in (GENERIC / which).iterdir() if p.is_file()) == sorted(GENERIC_FILES[which])
    for name in GENERIC_FILES[which]:
        assert (GENERIC / which / name).read_bytes() == generic[name], f"generic/{which}/{name}"
        assert generic[name] != graphics[name], name
    assert {n for n in generic if generic[n] != graphics[n]} == set(GENERIC_FILES[which])


def test_generic_ascii_no_connect() -> None:
    with tempfile.TemporaryDirectory() as folder:
        output = build_example("no_connect", Path(folder), symbol_bodies="generic", form="ascii", frozen=True)
    golden = GENERIC / "no_connect" / "ascii" / "altium_no_connect.SchDoc"
    assert golden.read_bytes() == output.files["altium_no_connect.SchDoc"]


def test_generic_form_of_the_example_library_as_it_is_now() -> None:
    """The example library of today builds in the generic form as well, to the same nets; its bytes are
    not those of the kept copies, because ``CONN2`` no longer shows names that repeat its pin numbers and
    ``MCU8`` and ``DUAL_OPAMP`` hold their pins further out (change c0134)."""
    with tempfile.TemporaryDirectory() as folder:
        for which, nets in (("kicad_example", EXAMPLE_NETS), ("no_connect", NO_CONNECT_NETS)):
            now = build_example(which, Path(folder) / which / "now", symbol_bodies="generic")
            then = build_example(which, Path(folder) / which / "then", symbol_bodies="generic", frozen=True)
            assert not [i for i in now.issues if i.severity == "error"]
            assert nets_of(read_back(Path(folder) / which / "out", now)) == nets
            changed = {name for name in project_files(now) if now.files[name] != then.files[name]}
            assert changed == set(GENERIC_FILES[which]), which


def test_flat_default_sheets_and_library_do_not_depend_on_the_sheet_mode() -> None:
    flat, modules = tree_build(sheets="flat"), tree_build()
    assert flat.files["tree.SchLib"] == modules.files["tree.SchLib"]
    assert flat.summary["schematic"]["sheets"] == 1  # type: ignore[index]


@pytest.mark.parametrize("form", FORMS)
def test_drawing_sheet_on_every_sheet_of_the_tree(form: str, tmp_path: Path) -> None:
    """The drawing sheet of change c0087 and the module tree of this change: every sheet, the one two
    levels down too, holds the frame and the sheet parameters with its number of four, and the project
    still reads back to its nets."""
    sheet = example_sheet()
    built = tree_build(form=form, drawing_sheet=sheet)
    plain = tree_build(form=form)
    assert not [i for i in built.issues if i.severity == "error"]
    info = built.summary["drawing_sheet"]
    assert isinstance(info, dict)
    pages = {page["file"]: page for page in info["pages"]}
    assert list(pages) == ["tree.SchDoc", "tree_io.SchDoc", "tree_io.leds.SchDoc", "tree_power.SchDoc"]
    for number, (name, page) in enumerate(pages.items(), start=1):
        data = built.files[name]
        imported = import_sheet(data, allow_lossy=True)
        size = {"width": page["width"], "height": page["height"], "paper": page["paper"]}
        assert written_scope(imported.sheet, **size) == written_scope(sheet, **size), name
        assert sheet_parameters(data) == {"SheetNumber": str(number), "SheetTotal": "4"}, name
        assert data != plain.files[name]
    assert nets_of(read_back(tmp_path, built)) == TREE_NETS
    # the hidden parameters of a component stay the component's: C1 keeps MPN and Note
    power = documents(built)["tree_power.SchDoc"]
    owned = sorted(r.name for r in power.of_type(Parameter) if r.owner is not None and r.hidden)
    assert owned == ["MPN", "Note"]
    assert plain.summary["drawing_sheet"] is None  # the lens default of change c0087: no sheet, no job
