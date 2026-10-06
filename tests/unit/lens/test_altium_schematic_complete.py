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
  maintainer's author reports covered them (``tests/data/altium/generic/``).

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


def build_example(which: str, folder: Path, **kwargs: object) -> BuildOutput:
    """One of the example scripts built for the Altium target."""
    if which == "sample":
        design = sample()
        return build_altium(to_model(design), name=design.name, **kwargs)  # type: ignore[arg-type]
    if which == "hier":
        design = hier()
        return build_altium(to_model(design), name=design.name, **kwargs)  # type: ignore[arg-type]
    if which in ("kicad_example", "no_connect"):
        design = example() if which == "kicad_example" else no_connect_example()
        resolver = example_resolver(folder)
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
    author reports covered; the other files of the sample do not depend on the option."""
    with tempfile.TemporaryDirectory() as folder:
        generic = project_files(build_example(which, Path(folder) / "a", symbol_bodies="generic"))
        graphics = project_files(build_example(which, Path(folder) / "b"))
    assert sorted(p.name for p in (GENERIC / which).iterdir() if p.is_file()) == sorted(GENERIC_FILES[which])
    for name in GENERIC_FILES[which]:
        assert (GENERIC / which / name).read_bytes() == generic[name], f"generic/{which}/{name}"
        assert generic[name] != graphics[name], name
    assert {n for n in generic if generic[n] != graphics[n]} == set(GENERIC_FILES[which])


def test_generic_ascii_no_connect() -> None:
    with tempfile.TemporaryDirectory() as folder:
        files = build_example("no_connect", Path(folder), symbol_bodies="generic", form="ascii").files
    golden = GENERIC / "no_connect" / "ascii" / "altium_no_connect.SchDoc"
    assert golden.read_bytes() == files["altium_no_connect.SchDoc"]


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
