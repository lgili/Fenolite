# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Fenolite's own Altium output read back by the product reader, compared with the test readers, which share
no code with it (capability altium-schematic-reader, "Own output read back by the product reader")."""

from __future__ import annotations

import functools
import subprocess
from pathlib import Path

import pytest
from _altium import example_files, hier, no_connect_files, sample_model
from _altium_read import LibRecord, read_records, read_schlib
from _cfb_read import deframe, read_compound

from fenolite.backends.altium.read import sch
from fenolite.backends.altium.read import schlib as product_schlib
from fenolite.core.errors import Issue
from fenolite.dsl import to_model
from fenolite.lens.altium import build_altium

ROOT = Path(__file__).resolve().parents[5]
DATA = ROOT / "tests" / "data" / "altium"
Fields = list[tuple[str, str]]


@functools.cache
def builds() -> dict[str, bytes]:
    """File label → bytes of every Altium example build: the KiCad example and the no-connect example in both
    forms, the sample in both forms and the hierarchy sample's module sheets."""
    out: dict[str, bytes] = {}
    for form in ("ascii", "binary"):
        for name, data in example_files(form).items():
            out[f"altium_kicad/{form}/{name}"] = data
        for name, data in no_connect_files(form).items():
            out[f"no_connect/{form}/{name}"] = data
        sample = build_altium(sample_model(), name="altium_sample", form=form)  # type: ignore[arg-type]
        for name, data in sample.files.items():
            out[f"sample/{form}/{name}"] = data
    hierarchy = build_altium(to_model(hier()), name="altium_hier", sheets="modules")
    for name, data in hierarchy.files.items():
        out[f"hier/{name}"] = data
    return {label: data for label, data in out.items() if label.lower().endswith((".schdoc", ".schlib"))}


def committed() -> dict[str, bytes]:
    return {
        path.relative_to(DATA).as_posix(): path.read_bytes()
        for path in sorted(DATA.rglob("*"))
        if path.suffix.lower() in (".schdoc", ".schlib")
    }


def _fields(record: sch.SchRecord) -> Fields:
    assert record.props is not None
    return [(p.key, p.raw.decode("ascii")) for p in record.props.items if p.raw is not None]


def _schematic_problems(data: bytes) -> list[str]:
    issues: list[Issue] = []
    document = sch.read_schematic(data, issues=issues)
    problems = [f"issue {issue.code} at {issue.where}" for issue in issues]
    if sch.check_identity(document):
        problems.append("identity")
    if document.form == "ascii":
        expected = read_records(data)
        found = [dict(_fields(record)) for record in document.records]
        if found != expected:
            problems.append("ASCII records differ from tests/_altium_read.read_records")
        return problems
    streams = read_compound(data)
    expected_main = deframe(streams["FileHeader"])
    found_main = [_fields(document.header), *(_fields(record) for record in document.records)]
    if found_main != expected_main:
        problems.append("FileHeader records differ from tests/_cfb_read.deframe")
    if "Additional" in streams:
        assert document.additional_header is not None
        found_add = [
            _fields(document.additional_header),
            *(_fields(record) for record in document.additional),
        ]
        if found_add != deframe(streams["Additional"]):
            problems.append("Additional records differ from tests/_cfb_read.deframe")
    return problems


PIN_KEYS = {
    "UNKNOWN": "unknown_byte",
    "OWNERPARTID": "owner_part",
    "OWNERPARTDISPLAYMODE": "display_mode",
    "SYMBOL_INNEREDGE": "inner_edge",
    "SYMBOL_OUTEREDGE": "outer_edge",
    "SYMBOL_INSIDE": "inside",
    "SYMBOL_OUTSIDE": "outside",
    "DESCRIPTION": "description",
    "FORMALTYPE": "formal_type",
    "ELECTRICAL": "electrical",
    "PINCONGLOMERATE": "conglomerate",
    "PINLENGTH": "length",
    "LOCATION.X": "x",
    "LOCATION.Y": "y",
    "COLOR": "color",
    "NAME": "name",
    "DESIGNATOR": "designator",
    "SWAPIDGROUP": "swap_group",
    "PARTANDSEQUENCE": "part_and_sequence",
    "DEFAULTVALUE": "default_value",
}


def _library_record(record: sch.SchRecord) -> LibRecord:
    fields = record.pin_fields
    if fields is None:
        return dict(_fields(record))
    out: LibRecord = {"BINARY": True, "RECORD": "2"}
    for key, attribute in PIN_KEYS.items():
        value = getattr(fields, attribute)
        out[key] = value.decode("ascii") if isinstance(value, bytes) else value
    return out


def _library_problems(data: bytes) -> list[str]:
    issues: list[Issue] = []
    library = product_schlib.read_schlib(data, issues=issues)
    problems = [f"issue {issue.code} at {issue.where}" for issue in issues]
    if sch.check_identity(library):
        problems.append("identity")
    expected = read_schlib(data)
    found = {
        component.storage_name: [_library_record(r) for r in component.records]
        for component in library.components
    }
    if found != expected:
        problems.append("library records differ from tests/_altium_read.read_schlib")
    return problems


def _problems(data: bytes) -> list[str]:
    return _library_problems(data) if sch.detect(data) == "library" else _schematic_problems(data)


@pytest.mark.parametrize("label", sorted(committed()))
def test_committed_samples_agree(label: str) -> None:
    assert _problems(committed()[label]) == []


@pytest.mark.parametrize("label", sorted(builds()))
def test_example_builds_agree(label: str) -> None:
    assert _problems(builds()[label]) == []


def test_binary_and_ascii_forms_give_equal_typed_records() -> None:
    pairs = 0
    for label, data in builds().items():
        if "/ascii/" not in label or not label.endswith(".SchDoc"):
            continue
        binary = builds()[label.replace("/ascii/", "/binary/")]
        ascii_records = sch.read_schematic(data).records
        binary_records = sch.read_schematic(binary).records
        assert [(type(r), r.props.items if r.props else None) for r in ascii_records] == [
            (type(r), r.props.items if r.props else None) for r in binary_records
        ], label
        pairs += 1
    assert pairs >= 3


def test_the_comparison_sees_a_difference() -> None:
    data = committed()["sample/altium_sample.SchDoc"]
    changed = data.replace(b"|RECORD=25|", b"|RECORD=25|EXTRA=1|", 1)
    assert changed != data
    expected = read_records(changed)
    found = [dict(_fields(record)) for record in sch.read_schematic(changed).records]
    assert found == expected  # both readers see the new key
    found[1]["X"] = "1"
    assert found != expected


def test_readers_stay_independent() -> None:
    result = subprocess.run(
        [
            "git",
            "grep",
            "-n",
            "backends.altium.read",
            "tests/_altium_read.py",
            "tests/_cfb_read.py",
            "tests/_altium_pcb_read.py",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.stdout == ""
