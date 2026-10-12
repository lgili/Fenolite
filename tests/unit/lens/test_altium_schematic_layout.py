# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Native presentation capture with authored circuits and opaque container streams."""

from __future__ import annotations

import json

import pytest
from _altium import records

from fenolite.backends.altium.ascii import encode_records
from fenolite.backends.altium.cfb import write_compound
from fenolite.backends.altium.project import write_project
from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read.sch.framing import deframe, enframe
from fenolite.core.errors import FormatError
from fenolite.dsl import Design, Net, Part, connect, to_model
from fenolite.lens.altium import generic_pins
from fenolite.lens.altium_schematic import LayoutConflict, capture, read_snapshot, replay


def generated(form: str = "ascii") -> dict[str, bytes]:
    design = Design("LayoutDemo")
    r1 = Part("R1", "Demo:R", "Demo:R", value="1k")
    r2 = Part("R2", "Demo:R", "Demo:R", value="2k")
    design.add(r1, r2)
    connect(Net("SIGNAL"), r1[1], r2[1])
    connect(Net("RETURN"), r1[2], r2[2])
    model = generic_pins(to_model(design))
    return {
        name: data
        for name, data in write_project(model, name=design.name, form=form).items()
        if name.endswith(".SchDoc")
    }


@pytest.mark.parametrize("form", ["ascii", "binary"])
def test_native_presentation_and_repeated_capture(form: str) -> None:
    baseline = generated(form)
    name = next(iter(baseline))
    doc = sch.read_schematic(baseline[name])
    if form == "ascii":
        edited = {name: baseline[name].replace(b"FONTNAME1=Times New Roman", b"FONTNAME1=Courier New")}
    else:
        streams = dict(doc.streams)
        streams["FileHeader"] = enframe(
            (frame.kind, frame.payload.replace(b"Times New Roman", b"Courier New"))
            for frame in deframe(streams["FileHeader"], where="FileHeader")
        )
        streams["NativeAssets"] = b"authored opaque asset bytes"
        edited = {name: write_compound(streams.items())}
    assert edited != baseline
    snapshot = capture(baseline, edited)
    assert replay(baseline, snapshot) == edited
    assert capture(baseline, replay(baseline, snapshot)) == snapshot
    assert read_snapshot(snapshot)[name].data == edited[name]


@pytest.mark.parametrize(
    "before,after",
    [
        (b"SIGNAL", b"OTHER"),
        (b"TEXT=1k", b"TEXT=3k"),
        (b"LIBREFERENCE=R", b"LIBREFERENCE=Z"),
        (b"MODELNAME=R", b"MODELNAME=Z"),
    ],
)
def test_electrical_or_symbol_change_is_refused(before: bytes, after: bytes) -> None:
    baseline = generated()
    edited = {name: data.replace(before, after) for name, data in baseline.items()}
    assert edited != baseline
    with pytest.raises(LayoutConflict):
        capture(baseline, edited)


def test_source_conflict_and_new_unsaved_sheet() -> None:
    baseline = generated()
    snapshot = capture(baseline, baseline)
    changed = {name: data.replace(b"TEXT=1k", b"TEXT=3k") for name, data in baseline.items()}
    with pytest.raises(LayoutConflict):
        replay(changed, snapshot)
    with pytest.raises(LayoutConflict):
        replay({}, snapshot)
    extra = {**baseline, "New.SchDoc": next(iter(baseline.values()))}
    assert replay(extra, snapshot) == extra


@pytest.mark.parametrize(
    "text", ["{}", '{"schema":"bad","sheets":{}}', '{"schema":"a","schema":"b","sheets":{}}']
)
def test_invalid_snapshot(text: str) -> None:
    with pytest.raises(FormatError):
        read_snapshot(text)


def test_corrupt_or_unsafe_snapshot() -> None:
    baseline = generated()
    payload = json.loads(capture(baseline, baseline))
    name = next(iter(payload["sheets"]))
    payload["sheets"][name]["data"] = "bad"
    with pytest.raises(FormatError):
        read_snapshot(json.dumps(payload))
    payload = json.loads(capture(baseline, baseline))
    payload["sheets"]["../Escape.SchDoc"] = payload["sheets"].pop(name)
    with pytest.raises(FormatError):
        read_snapshot(json.dumps(payload))


def test_incomplete_capture() -> None:
    with pytest.raises(LayoutConflict):
        capture(generated(), {})


def test_component_unit_identity_change_is_refused() -> None:
    baseline = generated()
    name = next(iter(baseline))
    uid = sch.read_schematic(baseline[name]).components()[0].unique_id.encode("ascii")
    edited = {name: baseline[name].replace(uid, b"ABCDEFGH")}
    assert edited != baseline
    with pytest.raises(LayoutConflict):
        capture(baseline, edited)


def test_native_format_change_keeps_the_saved_bytes() -> None:
    baseline = generated("ascii")
    edited = generated("binary")
    assert replay(baseline, capture(baseline, edited)) == edited


@pytest.mark.parametrize("transform", ["move", "rotate", "mirror"])
def test_component_and_wire_geometry_survives(transform: str) -> None:
    baseline = generated()
    name = next(iter(baseline))
    edited_records = records(baseline[name])
    for fields in edited_records:
        point_pairs = [("LOCATION.X", "LOCATION.Y"), ("CORNER.X", "CORNER.Y")]
        point_pairs += [(f"X{i}", f"Y{i}") for i in range(1, int(fields.get("LOCATIONCOUNT", "0")) + 1)]
        for xkey, ykey in point_pairs:
            if xkey not in fields and ykey not in fields:
                continue
            x, y = int(fields.get(xkey, "0")), int(fields.get(ykey, "0"))
            if transform == "rotate":
                x, y = 1000 - y, x
            elif transform == "mirror":
                x = 1000 - x
            else:
                x, y = x + 50, y + 70
            fields[xkey], fields[ykey] = str(x), str(y)
        if fields.get("RECORD") == "1":
            if transform == "rotate":
                fields["ORIENTATION"] = "1"
            elif transform == "mirror":
                fields["ISMIRRORED"] = "T"
        if "PINCONGLOMERATE" in fields:
            value = int(fields["PINCONGLOMERATE"])
            direction = value & 3
            if transform == "rotate":
                direction = (direction + 1) % 4
            elif transform == "mirror":
                direction = (2 - direction) % 4
            fields["PINCONGLOMERATE"] = str((value & ~3) | direction)
    edited = {name: encode_records([list(fields.items()) for fields in edited_records])}
    assert edited != baseline
    assert replay(baseline, capture(baseline, edited)) == edited


def test_replay_rechecks_a_hand_edited_snapshot() -> None:
    baseline = generated()
    payload = json.loads(capture(baseline, baseline))
    name = next(iter(baseline))
    import base64

    from fenolite.lens.altium_schematic import digest

    tampered = baseline[name].replace(b"SIGNAL", b"OTHER")
    payload["sheets"][name]["sha256"] = digest(tampered)
    payload["sheets"][name]["data"] = base64.b64encode(tampered).decode("ascii")
    with pytest.raises(LayoutConflict):
        replay(baseline, json.dumps(payload))
