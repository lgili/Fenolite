# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Component bodies in an Altium build (capability altium-build, "Component bodies in an Altium build";
capability altium-pcb-writer, "Component bodies are reported"; capability altium-verification, "Component
bodies in the round trips"; change c0121; hypothesis ``H-A-PCBX-BODY-READBACK``).

The sample ``body2`` (``tests/_altium_body2.py``) built with ``--altium-bodies extruded`` must give the five
files under ``tests/data/altium/body2/`` byte for byte; ``FENOLITE_GOLDEN_WRITE=1`` rewrites them, and the
SHA-256 values of step X8 of ``docs/evidence/altium-pcb.md`` are then updated (``-k protocol`` checks
them). With ``FENOLITE_ALTIUM_BODY2=<folder>`` the test ``-k golden`` also writes the two file sets of step
X8 there, ``saved/`` and ``short/``, with a ``README.md``, for the maintainer to open in Altium Designer;
the folder must lie outside the repository. With ``FENOLITE_ALTIUM_BODY2_SAVED=<file>`` the test ``-k
saved_report`` prints counts of a document that Altium saved (step X8.6); the file is never committed.

Everything here is Fenolite reading what Fenolite wrote. Nothing says that Altium takes a written body:
that is step X8, which is pending, and it is why the option is off by default.
"""

from __future__ import annotations

import dataclasses
import hashlib
import io
import json
import os
import re
import struct
import sys
import tempfile
from collections import Counter
from functools import cache
from pathlib import Path
from typing import Any

import pytest
from _altium import blink_resolver, blink_tree
from _altium_board6 import board6_build, read_document
from _altium_board6 import project_files as board6_files
from _altium_body2 import (
    BODIES,
    FILES,
    NAME,
    TABLE,
    WRITTEN,
    body,
    body2_build,
    body2_model,
    body2_placements,
    library_body,
    project_files,
)

import fenolite.cli.main as cli_main
from fenolite.backends.altium import lower, pcbdoc, pcbrecords
from fenolite.backends.altium.backend import AltiumBackend
from fenolite.backends.altium.bodydiff import body_count, body_differences, body_view
from fenolite.backends.altium.cfb import Storage, write_compound
from fenolite.backends.altium.pcbdoc import BODIES_OFF, BODY_IS_MODEL, BODY_NO_OUTLINE, BODY_STORAGES
from fenolite.backends.altium.read import cfb as read_cfb
from fenolite.backends.altium.read.bodies import BodyRecord, read_bodies
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.backends.altium.read.pcblib import read_pcblib
from fenolite.backends.altium.read.pcbprims import BODY, RawPrimitive
from fenolite.backends.altium.roundtrip import BODY_SCOPE, RT_A2_SCOPE
from fenolite.backends.altium.roundtrip import body_changes as as_changes
from fenolite.backends.base import BodyComparer, Change
from fenolite.checks.rta3 import compare
from fenolite.core.coords import Point
from fenolite.lens import altium_copper
from fenolite.lens.altium import build_altium, write_model
from fenolite.lens.build import BuildOutput
from fenolite.model.board import ComponentBody
from fenolite.model.design import Design

ROOT = Path(__file__).resolve().parents[2].parent


def body_changes(reference: Design, reading: Design) -> tuple[Change, ...]:
    """The differences of the kind ``body`` as the round trips report them."""
    changes, evidence = AltiumBackend().body_differences(reference, reading)
    assert changes == as_changes(body_differences(reference, reading))
    assert evidence.hypotheses == ("H-A-PCBX-BODY-READBACK",) and isinstance(AltiumBackend(), BodyComparer)
    return changes


BODY2_DIR = ROOT / "tests" / "data" / "altium" / "body2"
PROTOCOL = ROOT / "docs" / "evidence" / "altium-pcb.md"
WRITE = os.environ.get("FENOLITE_GOLDEN_WRITE") == "1"
HANDOVER = os.environ.get("FENOLITE_ALTIUM_BODY2")
SAVED = os.environ.get("FENOLITE_ALTIUM_BODY2_SAVED")
DOCUMENT, LIBRARY = f"{NAME}.PcbDoc", f"{NAME}.PcbLib"
MM = 1_000_000


@cache
def built(mode: str = "extruded", rotation: int = 0, form: str = "saved") -> BuildOutput:
    with tempfile.TemporaryDirectory() as folder:
        output = body2_build(Path(folder), rotation=rotation, bodies=mode, body_form=form)  # type: ignore[arg-type]
    assert not [found for found in output.issues if found.severity == "error"], output.issues
    return output


def _records(data: bytes) -> tuple[tuple[BodyRecord, ...], tuple[BodyRecord, ...], dict[str, bytes]]:
    """The body records of both storages of a PCB document, and the two ``Header`` streams."""
    document = read_pcbdoc(data, file=DOCUMENT, strict=True)
    plain, shape = (document.storages[name] for name in BODY_STORAGES)
    headers = {BODY_STORAGES[0]: plain["Header"], BODY_STORAGES[1]: shape["Header"]}
    return read_bodies(plain["Data"]), read_bodies(shape["Data"], shape_based=True), headers


def _body_issues(output: BuildOutput) -> list[Any]:
    return [i for i in output.issues if i.code == "altium.not-lowered" and i.where.startswith("body/")]


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- the sample -----------------------------------------------------------------------------------------


def _readme(saved: dict[str, bytes], short: dict[str, bytes]) -> str:
    """The README of the folder of step X8: what to open, what to look at, what to report."""
    lines = [
        "# Step X8: component bodies (Fenolite change c0121)",
        "",
        "Two builds of the sample `body2` with `--altium-bodies extruded`, for Altium Designer 26. The steps",
        "are in Part X of `docs/evidence/altium-pcb.md` of the repository (step X8); a menu path or a dialog",
        "name may read differently in version 26. Nothing in these files was opened in Altium before.",
        "",
        "- `saved/`: each body holds the 35 keys of a body that Altium saved, with two stand-in values",
        "  (`MODELID` derived by Fenolite, `MODEL.CHECKSUM=0`). This is the form the option writes.",
        "- `short/`: each body holds the first 21 keys only, without any model key. Built for this step",
        "  only.",
        "",
        "## What to open",
        "",
        "1. `saved/body2.PrjPcb`, then `body2.PcbDoc` (X8.1 to X8.4, and X8.6).",
        "2. `short/body2.PrjPcb`, then `body2.PcbDoc` (X8.5).",
        "3. `saved/body2.PcbLib`, the footprint of `U1` (X8.7).",
        "",
        "## What to look at",
        "",
        "- On opening: a repair prompt, or a message in the Messages panel.",
        '- The PCB panel in the mode "3D Models" (or select each body in 2D): three bodies, each owned by',
        "  the footprint of the table.",
        "- The properties of each body: identifier, board side, layer, overall height, standoff height.",
        "- The 3D view: three solids at the heights of the table; body 2 below the board.",
        "",
        "| body | footprint | board side | layer | overall height | standoff height | identifier |",
        "|---|---|---|---|---|---|---|",
    ]
    for number, (ref, side, layer, height, standoff, identifier) in enumerate(TABLE, start=1):
        lines.append(
            f"| {number} | {ref} | {side} | {layer} | {height} | {standoff} | {identifier or '(empty)'} |"
        )
    lines += [
        "",
        "A fourth body of the model names a 3D model; Fenolite does not write it, so the document holds",
        "three.",
        "",
        "## What to report (one line each)",
        "",
        "The tool as `AD <major>.<minor>`, the date, and per step `as expected` or what differed in one",
        "sentence: X8.1, X8.2, X8.3, X8.4, X8.5 (the same four on `short/`), X8.6 (the printed counts),",
        "X8.7. Do not send a file that Altium wrote.",
        "",
        "## SHA-256",
        "",
    ]
    for folder, files in (("saved", saved), ("short", short)):
        lines += [f"- `{folder}/{name}`: `{_sha(files[name])}`" for name in FILES]
    return "\n".join(lines) + "\n"


def test_body2_golden_files() -> None:
    """Scenario "Sample with bodies": the committed files equal a fresh build with the option; three bodies
    are written, and the one that names a model is reported."""
    output = built()
    pcb = output.summary["pcb"]
    assert isinstance(pcb, dict) and list(pcb) == ["written", "not_lowered", "bodies"]
    assert pcb["bodies"] == "extruded" and pcb["written"]["body"] == 3 and pcb["not_lowered"] == {"body": 1}
    (reported,) = _body_issues(output)
    assert reported.where == f"body/{body('b4').id}" and reported.severity == "info"
    assert "MODEL" in reported.message and "1.6 mm" in reported.message and BODY_IS_MODEL in reported.message
    files = project_files(output)
    assert sorted(files) == sorted(FILES)
    if HANDOVER:
        target = Path(HANDOVER).resolve()
        assert ROOT.resolve() not in (target, *target.parents), "the folder is inside the repository"
        short = project_files(built(form="short"))
        for folder, group in (("saved", files), ("short", short)):
            (target / folder).mkdir(parents=True, exist_ok=True)
            for name in FILES:
                (target / folder / name).write_bytes(group[name])
        (target / "README.md").write_text(_readme(files, short), encoding="utf-8", newline="\n")
    if WRITE:
        BODY2_DIR.mkdir(parents=True, exist_ok=True)
        for name in FILES:
            (BODY2_DIR / name).write_bytes(files[name])
        pytest.skip("body2 golden files rewritten (FENOLITE_GOLDEN_WRITE=1)")
    assert sorted(p.name for p in BODY2_DIR.iterdir()) == sorted(FILES)
    for name in FILES:
        assert (BODY2_DIR / name).read_bytes() == files[name], f"{name} differs from a fresh build"


def test_body2_records() -> None:
    """The three written bodies in both storages, in the order of the components, as the fact rows say."""
    plain, shape, headers = _records(built().files[DOCUMENT])
    assert len(plain) == len(shape) == 3 and set(headers.values()) == {struct.pack("<I", 3)}
    document = read_pcbdoc(built().files[DOCUMENT], file=DOCUMENT)
    refs = [component.source_designator for component in document.components]
    assert [refs[record.component] for record in plain] == ["D1", "R1", "U1"]  # type: ignore[index]
    assert [row[0] for row in sorted(BODIES, key=lambda row: row[1]) if row[2] == "extruded"] == list(WRITTEN)
    expected = {
        "D1": (70, "MECHANICAL14", "1", "39.3701mil", "0mil", "LED", 4),
        "R1": (69, "MECHANICAL13", "0", "157.4803mil", "19.685mil", "STANDOFF", 6),
        "U1": (69, "MECHANICAL13", "0", "98.4252mil", "0mil", "", 4),
    }
    for a, b, key in zip(plain, shape, WRITTEN, strict=True):
        assert a.properties.raw == b.properties.raw and a.properties.keys() == pcbrecords.BODY_KEYS
        fields = {name: a.properties.get_all(name)[0] for name in a.properties.keys()}
        layer, text, side, overall, standoff, name, count = expected[refs[a.component]]  # type: ignore[index]
        assert (a.layer, fields["V7_LAYER"], fields["BODYPROJECTION"]) == (layer, text, side)
        assert (fields["OVERALLHEIGHT"], fields["MODEL.EXTRUDED.MAXZ"]) == (overall, overall)
        assert (fields["STANDOFFHEIGHT"], fields["MODEL.EXTRUDED.MINZ"]) == (standoff, standoff)
        assert a.identifier == name and len(a.outline) == count and len(b.outline) == count
        assert fields["MODELID"] == pcbrecords.body_model_id(body(key).id) and fields["MODEL.CHECKSUM"] == "0"
    # the library holds the body of the definition of U1, and no other
    library = read_pcblib(built().files[LIBRARY], file=LIBRARY, strict=True)
    found = {
        footprint.name: [p for p in footprint.primitives if isinstance(p, RawPrimitive) and p.type == BODY]
        for footprint in library.footprints
    }
    assert sorted(len(bodies) for bodies in found.values()) == [0, 0, 1]
    ((name, (primitive,)),) = [(name, bodies) for name, bodies in found.items() if bodies]
    (record,) = read_bodies(primitive.raw)
    assert "QFP" in name and record.component is None and record.overall_height == 984252
    assert record.properties.text("MODELID") == pcbrecords.body_model_id(library_body().id)


def test_body2_golden_protocol_names_the_bytes() -> None:
    """Step X8 of Part X names the SHA-256 of every committed file of the sample and of the short set,
    its seven steps, the rows it settles, and that the option stays off until it is reported."""
    text = PROTOCOL.read_text(encoding="utf-8")
    part = text[text.index("## Part X") :]
    step = part[part.index("**X8**") :]
    digests = dict(
        re.findall(
            r"^ *\| `tests/data/altium/body2/([^`]+)` \| `([0-9a-f]{64})` \|", part, flags=re.MULTILINE
        )
    )
    assert sorted(digests) == sorted(FILES)
    for name, digest in digests.items():
        assert _sha((BODY2_DIR / name).read_bytes()) == digest, name
    short = dict(re.findall(r"^ *\| `short/([^`]+)` \| `([0-9a-f]{64})` \|", part, flags=re.MULTILINE))
    files = project_files(built(form="short"))
    assert sorted(short) == sorted(FILES)
    for name, digest in short.items():
        assert _sha(files[name]) == digest, name
    for number in range(1, 8):
        assert f"**X8.{number}**" in step, number
    for row in ("OPEN", "SHORT", "ID", "LIB"):
        assert f"H-A-PCBX-BODY-{row}" in step, row
    flat = " ".join(step.split())
    assert "session 2" in flat and "session-2/X8-bodies" in flat
    assert "stays `off` until step X8 is reported" in flat
    assert "Altium Designer 26" in flat


def test_body2_short_set_differs_in_the_bodies_only() -> None:
    """The second file set of step X8: 21 keys per body, and every other file as in the first set."""
    saved, short = project_files(built()), project_files(built(form="short"))
    assert [name for name in FILES if saved[name] != short[name]] == [DOCUMENT]
    plain, shape, _headers = _records(short[DOCUMENT])
    for record in (*plain, *shape):
        assert len(record.properties.keys()) == 21 and not record.properties.get_all("MODELID")
    assert [r.overall_height for r in plain] == [r.overall_height for r in _records(saved[DOCUMENT])[0]]


def test_body2_saved_report(capsys: pytest.CaptureFixture[str]) -> None:
    """Step X8.6: counts of a document that Altium saved from ``saved/body2.PcbDoc``. Prints counts only."""
    if not SAVED:
        pytest.skip("set FENOLITE_ALTIUM_BODY2_SAVED=<the PcbDoc that Altium saved> (step X8.6)")
    data = Path(SAVED).read_bytes()
    document = read_pcbdoc(data, file=Path(SAVED).name)
    names = {name.lower(): name for name in document.storages}
    plain = read_bodies(document.storages[names[BODY_STORAGES[0].lower()]]["Data"])
    shape = read_bodies(document.storages[names[BODY_STORAGES[1].lower()]]["Data"], shape_based=True)
    written = {pcbrecords.body_model_id(body(key).id) for key in WRITTEN}
    kept = sum(1 for record in plain if record.properties.text("MODELID") in written)
    nonzero = sum(1 for record in plain if record.properties.text("MODEL.CHECKSUM") not in ("", "0"))
    keys = Counter(len(record.properties.keys()) for record in plain)
    with capsys.disabled():
        print(
            f"\nbodies: {len(plain)} in {BODY_STORAGES[0]}, {len(shape)} in {BODY_STORAGES[1]}; "
            f"{kept} keep the MODELID that was written; {nonzero} hold a MODEL.CHECKSUM other than 0; "
            f"keys per body: {dict(sorted(keys.items()))}"
        )
    assert len(plain) == len(shape)


# --- without the option ---------------------------------------------------------------------------------


def test_without_the_option_nothing_is_written() -> None:
    """Scenario "Body height" on the sample: every body is reported with its height and the option, both
    storages are empty, and the stored board holds no body."""
    output = built("off")
    pcb = output.summary["pcb"]
    assert pcb["bodies"] == "off" and pcb["written"]["body"] == 0 and pcb["not_lowered"] == {"body": 4}  # type: ignore[index]
    issues = _body_issues(output)
    assert sorted(i.where for i in issues) == sorted(f"body/{body(row[0]).id}" for row in BODIES)
    assert all(BODIES_OFF in i.message and "--altium-bodies extruded" in i.hint for i in issues)
    (first,) = [i for i in issues if i.where == f"body/{body('b1').id}"]
    assert "2.5 mm" in first.message
    plain, shape, headers = _records(output.files[DOCUMENT])
    assert plain == shape == () and set(headers.values()) == {bytes(4)}
    assert output.layout is not None and body_count(output.layout) == 0


def test_without_the_option_a_board_keeps_its_bytes() -> None:
    """With ``off``, and with ``extruded`` on a design without a body, every file is the file of before:
    ``board6``, which holds no body, gives its committed bytes in both modes, and a build adds no body."""
    committed = ROOT / "tests" / "data" / "altium" / "board6"
    with tempfile.TemporaryDirectory() as folder:
        for mode in ("off", "extruded"):
            output = board6_build(Path(folder), bodies=mode)
            assert output.summary["pcb"]["bodies"] == mode  # type: ignore[index]
            for name, data in board6_files(output).items():
                assert data == (committed / name).read_bytes(), (mode, name)
            assert not _body_issues(output)
    # the sample without its bodies, built with the option, is the sample built without the option but
    # for the issues: no body is invented for a footprint that has none
    bare = body2_model(keys=())
    with tempfile.TemporaryDirectory() as folder:
        with_option = body2_build(Path(folder), bare, bodies="extruded", library=False)
        without = body2_build(Path(folder), bare, bodies="off", library=False)
    assert project_files(with_option) == project_files(without)
    assert _records(with_option.files[DOCUMENT])[0] == ()
    assert with_option.summary["pcb"]["written"]["body"] == 0  # type: ignore[index]


def test_unknown_mode_is_refused() -> None:
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        resolver = blink_resolver(root, blink_tree(root))
        with pytest.raises(ValueError, match="unknown body mode"):
            build_altium(body2_model(), name=NAME, resolver=resolver, bodies="all")
    for call in (lower.from_design, lower.write_design, write_model):
        with pytest.raises(ValueError, match="unknown body mode"):
            call(body2_model(), bodies="all", **({"issues": []} if call is lower.from_design else {}))  # type: ignore[arg-type]


# --- bodies that are written, and bodies that are not ------------------------------------------------------


def _one_body(rotation: int, side: str, **changes: object) -> tuple[Design, ComponentBody]:
    """The sample's model with one body alone, on ``R1``, placed on ``side`` and turned by ``rotation``."""
    wanted = dataclasses.replace(body("b3"), standoff=0, height=2_500_000, name="", layer="", **changes)  # type: ignore[arg-type]
    model = body2_model(rotation, keys=())
    assert model.board is not None
    footprints = tuple(
        dataclasses.replace(fp, side=side, bodies=(wanted,))  # type: ignore[arg-type]
        if fp.id.startswith("fp_") and fp.lib_ref.endswith("R_0603")
        else fp
        for fp in model.board.footprints
    )
    assert sum(len(fp.bodies) for fp in footprints) == 1
    return dataclasses.replace(model, board=dataclasses.replace(model.board, footprints=footprints)), wanted


def _build_one(model: Design, rotation: int, side: str, mode: str = "extruded") -> BuildOutput:
    placements = {
        path: dataclasses.replace(place, side=side) if path == "R1" else place
        for path, place in body2_placements(rotation).items()
    }
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        resolver = blink_resolver(root, blink_tree(root))
        return build_altium(
            model, name=NAME, resolver=resolver, placed=tuple(placements), placements=placements, bodies=mode
        )


def test_body_written_on_the_bottom_side() -> None:
    """Scenario "Body written": the footprint on the bottom side, turned by 90 degrees."""
    rectangle = (Point(-MM, -2 * MM), Point(MM, -2 * MM), Point(MM, 2 * MM), Point(-MM, 2 * MM))
    model, wanted = _one_body(90_000_000, "bottom", outline=rectangle)
    output = _build_one(model, 90_000_000, "bottom")
    pcb = output.summary["pcb"]
    assert pcb["written"]["body"] == 1 and "body" not in pcb["not_lowered"] and not _body_issues(output)  # type: ignore[index]
    plain, shape, headers = _records(output.files[DOCUMENT])
    (a,), (b,) = plain, shape
    document, design = read_document(output.files[DOCUMENT], DOCUMENT)
    assert set(headers.values()) == {struct.pack("<I", 1)}
    assert a.body_projection == b.body_projection == 1 and a.layer == b.layer == 70
    assert document.components[a.component].source_designator == "R1"  # type: ignore[index]
    assert design.board is not None
    (footprint,) = [fp for fp in design.board.footprints if fp.bodies]
    (read,) = footprint.bodies
    assert (footprint.side, read.kind, read.layer) == ("bottom", "extruded", "Mech.14")
    assert abs(read.height - 2_500_000) <= 2 and read.standoff == 0
    assert len(read.outline) == 4
    for got, want in zip(read.outline, wanted.outline, strict=True):
        assert abs(got.x - want.x) <= 2 and abs(got.y - want.y) <= 2


def test_bodies_that_have_no_record() -> None:
    """Scenario "Bodies that have no record": a body of kind ``model``, one without outline and one whose
    height equals its standoff give three issues with their own reasons; a footprint without a body gives
    none; both storages stay empty."""
    model = body2_model(keys=())
    assert model.board is not None
    square = body("b1").outline
    bodies = (
        ComponentBody(id="bdy_model", kind="model", height=MM, outline=square, model="x.step"),
        ComponentBody(id="bdy_flat", kind="extruded", height=MM),
        ComponentBody(id="bdy_low", kind="extruded", height=MM, standoff=MM, outline=square),
    )
    first, *others = model.board.footprints
    board = dataclasses.replace(model.board, footprints=(dataclasses.replace(first, bodies=bodies), *others))
    with tempfile.TemporaryDirectory() as folder:
        output = body2_build(Path(folder), dataclasses.replace(model, board=board), library=False)
    pcb = output.summary["pcb"]
    assert pcb["not_lowered"] == {"body": 3} and pcb["written"]["body"] == 0  # type: ignore[index]
    reasons = {i.where: i.message for i in _body_issues(output)}
    assert sorted(reasons) == ["body/bdy_flat", "body/bdy_low", "body/bdy_model"]
    assert BODY_IS_MODEL in reasons["body/bdy_model"] and BODY_NO_OUTLINE in reasons["body/bdy_flat"]
    assert "is not above its standoff" in reasons["body/bdy_low"]
    assert all("(height 1 mm)" in message for message in reasons.values())
    plain, shape, headers = _records(output.files[DOCUMENT])
    assert plain == shape == () and set(headers.values()) == {bytes(4)}


def test_body_of_a_footprint_that_is_no_component() -> None:
    """A footprint whose component the document does not hold has no component record to own its body:
    the body is reported, and the bodies of the components that are there are placed."""
    model = body2_model()
    inputs = lower.from_design(model, issues=[], bodies="extruded")
    assert inputs.pcb is not None
    fewer = dataclasses.replace(inputs.pcb, components=inputs.pcb.components[:1], bodies=())
    assert fewer.components[0].ref == "D1"
    issues: list[Any] = []
    placed, counts = altium_copper.lower_bodies(model, fewer, "extruded", issues)
    assert counts == (1, 3) and [b.body_id for b in placed] == [body("b2").id]
    reasons = sorted(i.message.split(": ", 1)[1] for i in issues)
    assert reasons == [pcbdoc.BODY_NO_FOOTPRINT] * 3  # the model body too: no component owns it
    assert altium_copper.lower_bodies(model, fewer, "off", []) == ((), (0, 4))


# --- read-back and round trips ---------------------------------------------------------------------------


@pytest.mark.parametrize("rotation", [0, 90_000_000, 30_000_000])
def test_readback_of_the_sample(rotation: int) -> None:
    """``H-A-PCBX-BODY-READBACK``: the written bodies of ``body2``, top and bottom, at 0, 90 and 30 degrees,
    read back through the reader and the import to the model's bodies inside ``BODY_SCOPE``."""
    output = built(rotation=rotation)
    stored = output.layout
    assert stored is not None and body_count(stored) == 3
    _document, read = read_document(output.files[DOCUMENT], DOCUMENT)
    reading = AltiumBackend().in_model_frame(stored, read)
    assert body_count(reading) == 3
    assert body_changes(stored, reading) == ()
    # the stored bodies are the model's, and the reading holds their values within the tolerance
    assert reading.board is not None and stored.board is not None
    by_ref = {c.id: c.ref for c in reading.circuit.components}
    sides = {by_ref[fp.component_id]: fp.side for fp in reading.board.footprints if fp.bodies}
    assert sides == {"D1": "bottom", "R1": "top", "U1": "top"}
    views = {
        by_ref[fp.component_id]: body_view(fp.bodies[0], bottom=fp.side == "bottom")
        for fp in reading.board.footprints
        if fp.bodies
    }
    assert {ref: (view["layer"], view["name"], view["kind"]) for ref, view in views.items()} == {
        "D1": ("Mech.14", "LED", "extruded"),
        "R1": ("Mech.13", "STANDOFF", "extruded"),
        "U1": ("Mech.13", "", "extruded"),
    }
    assert abs(views["R1"]["standoff"] - 500_000) <= 2 and abs(views["R1"]["height"] - 4_000_000) <= 2
    assert len(views["R1"]["outline"]) == 6
    assert tuple(BODY_SCOPE.fields) == ("body",) and "body" not in RT_A2_SCOPE.fields
    assert BODY_SCOPE.fields["body"] == ("kind", "height", "standoff", "outline", "layer", "name")
    assert BODY_SCOPE.length_tolerance == 2


def test_readback_compares_a_ring_and_the_default_layer() -> None:
    """The outline is a ring (any start, the same order), and a body without a layer equals its default."""
    a = body("b3")
    turned = dataclasses.replace(a, outline=(*a.outline[2:], *a.outline[:2]), layer="F.Fab")
    assert body_view(a, bottom=False)["layer"] == body_view(turned, bottom=False)["layer"] == "Mech.13"
    assert body_view(a, bottom=False)["outline"] == body_view(turned, bottom=False)["outline"]
    assert body_view(dataclasses.replace(a, layer=""), bottom=True)["layer"] == "Mech.14"
    model = body2_model(keys=("b3",))
    assert model.board is not None

    def with_body(changed: ComponentBody) -> Design:
        assert model.board is not None
        footprints = tuple(
            dataclasses.replace(fp, bodies=(changed,)) if fp.bodies else fp for fp in model.board.footprints
        )
        return dataclasses.replace(model, board=dataclasses.replace(model.board, footprints=footprints))

    assert body_changes(model, with_body(turned)) == ()
    near = dataclasses.replace(
        a, height=a.height + 2, outline=tuple(Point(p.x + 2, p.y - 2) for p in a.outline)
    )
    assert body_changes(model, with_body(near)) == ()
    for far in (
        dataclasses.replace(a, height=a.height + 3),
        dataclasses.replace(a, outline=(Point(a.outline[0].x + 3, a.outline[0].y), *a.outline[1:])),
        dataclasses.replace(a, outline=tuple(reversed(a.outline))),
        dataclasses.replace(a, name="OTHER"),
        dataclasses.replace(a, layer="Mech.2"),
        dataclasses.replace(a, kind="model", model="x.step"),
    ):
        (change,) = body_changes(model, with_body(far))
        assert (change.path, change.change) == ("/body/0", "changed")
    without = dataclasses.replace(
        model,
        board=dataclasses.replace(
            model.board, footprints=tuple(dataclasses.replace(fp, bodies=()) for fp in model.board.footprints)
        ),
    )
    assert [(c.path, c.change) for c in body_changes(model, without)] == [("/body/0", "removed")]
    assert [(c.path, c.change) for c in body_changes(without, model)] == [("/body/0", "added")]


def _write(folder: Path, output: BuildOutput) -> Path:
    for name, data in output.files.items():
        target = folder / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    return folder


def _check(monkeypatch: pytest.MonkeyPatch, folder: Path) -> tuple[int, dict[str, Any]]:
    out, err = io.StringIO(), io.StringIO()
    with monkeypatch.context() as patch:
        patch.setattr(sys, "stdout", out)
        patch.setattr(sys, "stderr", err)
        code = cli_main.main(["check", str(folder), "--stages", "roundtrip.rta2", "--json"])
    return code, json.loads(out.getvalue())


def test_rta2_compares_the_bodies_of_a_build(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "Own sample", RT-A2: the build with bodies holds the level with 0 differences and lists the
    kind ``body`` as compared; the build without them compares no body."""
    code, env = _check(monkeypatch, _write(tmp_path / "with", built()))
    assert code == 0, env["issues"]
    (stage,) = env["result"]["stages"]
    summary = stage["summary"]
    assert (stage["status"], summary["holds"], summary["differences"]) == ("ok", True, 0)
    assert summary["compared"]["pcb"] == sorted(
        [*(kind for kind in RT_A2_SCOPE.fields if kind not in ("component", "net", "no_connect")), "body"]
    )
    assert stage["evidence"]["level"] == "INFERRED"
    assert {"H-A-VER-RTA2-3", "H-A-PCBX-BODY-READBACK"} <= set(stage["evidence"]["hypotheses"])
    code, env = _check(monkeypatch, _write(tmp_path / "without", built("off")))
    assert code == 0, env["issues"]
    (stage,) = env["result"]["stages"]
    assert "body" not in stage["summary"]["compared"]["pcb"] and stage["summary"]["holds"] is True
    assert "H-A-PCBX-BODY-READBACK" not in stage["evidence"]["hypotheses"]


def _move_a_vertex(document: Path) -> None:
    """Move the first vertex of the first body by 100 units in X and Y, in both storages, by an edit of
    the records."""
    data = document.read_bytes()
    streams: dict[str, bytes] = {}
    read = read_pcbdoc(data, file=document.name)
    for name, shape_based in zip(BODY_STORAGES, (False, True), strict=True):
        records = list(read_bodies(read.storages[name]["Data"], shape_based=shape_based))
        first = records[0]
        fields = {key: first.properties.get_all(key)[0] for key in first.properties.keys()}
        vertices = [(int(v.x), int(v.y)) for v in first.outline]
        vertices[0] = (vertices[0][0] + 100, vertices[0][1] + 100)
        moved = pcbrecords.body_record(
            first.layer or 0,
            vertices,
            component=first.component if first.component is not None else pcbrecords.NO_INDEX,
            standoff=int(first.standoff_height or 0),
            overall=int(first.overall_height or 0),
            bottom=first.body_projection == 1,
            identifier=first.identifier,
            model_id=fields["MODELID"],
            shape_based=shape_based,
        )
        streams[name] = moved + b"".join(record.raw for record in records[1:])

    def replaced(entries: Any) -> tuple[Any, ...]:
        out: list[Any] = []
        for entry in entries:
            if isinstance(entry, Storage) and entry.name in streams:
                inner = tuple(
                    (n, streams[entry.name] if n == "Data" else content) for n, content in entry.entries
                )
                out.append(Storage(entry.name, inner))
            elif isinstance(entry, Storage):
                out.append(Storage(entry.name, replaced(entry.entries)))
            else:
                out.append(entry)
        return tuple(out)

    document.write_bytes(write_compound(replaced(read_cfb.open_compound(data, file=document.name).tree())))


def test_rta2_catches_a_moved_vertex(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Scenario "A moved vertex is caught"."""
    folder = _write(tmp_path, built())
    _move_a_vertex(folder / DOCUMENT)
    code, env = _check(monkeypatch, folder)
    assert code == 5
    (failed,) = [i for i in env["issues"] if i["code"] == "check.rta2-failed"]
    assert failed["where"].startswith("pcb:/body/") and failed["severity"] == "error"
    summary = env["result"]["stages"][0]["summary"]
    assert (summary["holds"], summary["differences"]) == (False, 1)


def test_rta3_on_the_committed_sample() -> None:
    """Scenario "Own sample", RT-A3: the committed document is read, its model is written with bodies and
    read again; the three bodies are written and compared, and the level holds. The body of kind ``model``
    was never written, so the document holds three and none is a difference. Without the option the trip
    is the trip of before: the three bodies are counted as not written."""
    path = BODY2_DIR / DOCUMENT
    trip = AltiumBackend().model_roundtrip(path, compare=compare, bodies="extruded")
    assert trip.judged and trip.equal and trip.differences == ()
    assert trip.written["body"] == 3 and "body" not in trip.unwritten
    assert "H-A-PCBX-BODY-READBACK" in trip.evidence.hypotheses and trip.evidence.level.name == "INFERRED"
    first = AltiumBackend().read(path).design
    assert body_count(first) == 3
    plain = AltiumBackend().model_roundtrip(path, compare=compare)
    assert plain.judged and plain.equal and plain.unwritten["body"] == 3 and "body" not in plain.written
    assert "H-A-PCBX-BODY-READBACK" not in plain.evidence.hypotheses


def test_rta3_write_reports_the_bodies_by_reason() -> None:
    """The write of a model: ``from_design`` with ``bodies="extruded"`` writes the extruded bodies of the
    instances into the document, gives the synthesised definitions no body, and counts every other body
    by its reason; a rewrite decides nothing about bodies."""
    model = body2_model()
    issues: list[Any] = []
    inputs = lower.from_design(model, issues=issues, bodies="extruded")
    assert inputs.pcb is not None and inputs.bodies == "extruded"
    assert inputs.written["body"] == 3 and inputs.counts()["body"] == 1
    assert inputs.not_lowered["body"] == (body("b4").id,) and dict(inputs.body_reasons) == {BODY_IS_MODEL: 1}
    assert [placed.body_id for placed in inputs.pcb.bodies] == [body(key).id for key in WRITTEN]
    assert all(not component.footprint.defn.bodies for component in inputs.pcb.components)
    assert all(not component.footprint.bodies for component in inputs.pcb.components)
    off = lower.from_design(model, issues=[])
    assert off.pcb is not None and off.pcb.bodies == () and off.bodies == "off"
    assert off.counts()["body"] == 4 and dict(off.body_reasons) == {BODIES_OFF: 4}
    assert off.reasons["body"] == BODIES_OFF and "body" not in off.written
    written = write_model(model, allow_lossy=True, bodies="extruded")
    plain, shape, _headers = _records(written.files[DOCUMENT])
    assert len(plain) == len(shape) == 3
    assert write_model(model, allow_lossy=True).files[DOCUMENT] != written.files[DOCUMENT]
    read = AltiumBackend().read(BODY2_DIR / DOCUMENT).design
    for rewrite in (False, True):
        again = lower.from_design(read, issues=[], rewrite=rewrite, bodies="extruded")
        assert again.written["body"] == 3 and "body" not in again.counts()
        assert lower.from_design(read, issues=[], rewrite=rewrite).counts()["body"] == 3
