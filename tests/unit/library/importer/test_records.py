# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Local record origins, deterministic bytes, STEP and Altium symbols (c0264)."""

from __future__ import annotations

import hashlib
import tomllib
from dataclasses import replace
from pathlib import Path

from _library_import import DATA

from fenolite.backends.kicad.mod import read_footprint
from fenolite.backends.kicad.sexpr import parse
from fenolite.backends.kicad.sym import read_symbol_library
from fenolite.catalog.records import (
    ImportOrigin,
    PackageRecord,
    footprint_def,
    load_tree,
    parse_record,
    record_text,
    record_uid,
)
from fenolite.core.coords import Point
from fenolite.library.importer.native import read_native_definitions
from fenolite.library.importer.records import make_records, record_edited
from fenolite.library.importer.sources import read_sources
from fenolite.model.board import ComponentBody


def test_origin_rows_and_canonical_records() -> None:
    source = read_sources([DATA / "exb6202.zip"])
    imported = make_records(source, device_id=None, date="2026-10-29")
    for record in imported.records:
        assert record.header.evidence == "UNVERIFIED" and record.header.licence == "see source terms"
        assert isinstance(record.header.origin, ImportOrigin)
        assert record.header.origin.tool == "fenolite library import"
        assert record.header.origin.date == "2026-10-29" and not record.header.origin.shippable
        assert [(s.file, s.member, s.sha256) for s in record.header.origin.source] == [
            (s.file, s.member, hashlib.sha256(s.data).hexdigest()) for s in source.sources
        ]
        text = record_text(record)
        assert "[origin]" in text and parse_record(text) == record and not record_edited(record)
        assert record_edited(replace(record, header=replace(record.header, summary="edited")))
        for row in tomllib.loads(text)["origin"]["source"]:
            assert not row["file"].startswith("/") and ":" not in row["file"]


def test_step_is_copied_without_changes_and_given_a_placement() -> None:
    imported = make_records(read_sources([DATA / "exb6202.zip"]), device_id=None, date="2026-10-29")
    assert imported.files["EXB6202.step"] == (DATA / "exb6202.step").read_bytes()
    footprint = read_footprint(imported.files["EXB6202.kicad_mod"].decode())
    assert footprint.models == ("EXB6202.step",)
    (model,) = parse(imported.files["EXB6202.kicad_mod"].decode()).nodes("model")
    for key in ("offset", "rotate"):
        assert [a.value for a in model.nodes(key)[0].nodes("xyz")[0].atoms()] == ["0", "0", "0"]
    assert "library.import-step-unchecked" in {i.code for i in imported.issues}
    bare = replace(
        read_sources([DATA / "exb6202.zip"]),
        footprint=replace(imported.footprint, models=(), placements=(), ext={}),
    )
    added = make_records(bare, device_id=None, date="2026-10-29")
    assert "library.import-step-placement" in {i.code for i in added.issues}


def test_same_sources_and_date_give_same_bytes_and_stable_ids() -> None:
    sources = read_sources([DATA / "exb6202.zip"])
    first = make_records(sources, device_id=None, date="2026-10-29")
    assert first == make_records(sources, device_id=None, date="2026-10-29")
    for kind in ("device", "pins", "package"):
        assert record_uid(kind, "Imported:EXB6202") == record_uid(kind, first.device.header.id)
    assert sorted(first.files) == [
        "EXB6202.kicad_mod",
        "EXB6202.kicad_sym",
        "EXB6202.step",
        "device.toml",
        "package.toml",
        "pins.toml",
    ]


def test_altium_canonical_symbol_retains_pin_facts() -> None:
    source = read_sources([DATA / "exb6202.SchLib", DATA / "exb6202.PcbLib"])
    imported = make_records(source, device_id="Project:Example", date="2026-10-29")
    (symbol,) = read_symbol_library(imported.files["Example.kicad_sym"].decode())
    assert [(p.number, p.name, p.etype) for p in symbol.pins] == [
        (p.number, p.name, p.etype) for p in source.symbol.pins
    ]
    assert "library.import-symbol-regenerated" in {i.code for i in imported.issues}


def test_altium_body_is_retained_in_package_and_native_build(tmp_path: Path) -> None:
    from fenolite.backends.altium.pcblib import LibFootprint, write_pcblib

    source = read_sources([DATA / "exb6202.zip"])
    body = ComponentBody(
        id="bdy_00000000-0000-4000-8000-000000000001",
        kind="extruded",
        height=1_524_000,
        outline=(
            Point(-1_270_000, -1_270_000),
            Point(1_270_000, -1_270_000),
            Point(1_270_000, 1_270_000),
            Point(-1_270_000, 1_270_000),
        ),
        layer="F.Fab",
        z_min=0,
        z_max=1_524_000,
    )
    footprint = replace(
        source.footprint,
        pads=tuple(replace(p, shape="rect", corner_ratio=None, ext={}) for p in source.footprint.pads),
        bodies=(body,),
    )
    library = tmp_path / "body.PcbLib"
    library.write_bytes(write_pcblib([LibFootprint(footprint, bodies=(body,))], filename=library.name))
    selected = read_sources([DATA / "exb6202.SchLib", library])
    assert len(selected.footprint.bodies) == 1
    imported = make_records(selected, device_id=None, date="2026-11-01")
    package = parse_record(imported.files["package.toml"].decode())
    assert isinstance(package, PackageRecord) and len(package.bodies) == 1
    actual = selected.footprint.bodies[0]
    assert package.bodies[0].height == actual.height and package.bodies[0].outline == actual.outline
    assert footprint_def(package).bodies[0].projection_unknown == actual.projection_unknown
    root = tmp_path / "devices/Imported/EXB6202"
    root.mkdir(parents=True)
    for name, data in imported.files.items():
        (root / name).write_bytes(data)
    native = read_native_definitions(load_tree(tmp_path / "devices", label="devices/"), tmp_path)
    assert native.footprints["Imported:EXB6202"].bodies == footprint_def(package).bodies
