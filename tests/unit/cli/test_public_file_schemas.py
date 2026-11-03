# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Prepared schemas describe authored documents; real readers accept both supported IDs."""

from __future__ import annotations

import importlib.util
import json
import random
import sys
import tomllib
from argparse import Namespace
from datetime import UTC, datetime
from pathlib import Path

import _schema
import pytest

from fenolite.analysis.requirements import load_requirements
from fenolite.cli.api import Context
from fenolite.cli.cmd_place import _constraints
from fenolite.core.coords import Point
from fenolite.core.errors import FormatError
from fenolite.exports.assembly import read_template
from fenolite.exports.drawing_spec import read_spec
from fenolite.exports.preset import read_preset
from fenolite.view.review import read_review

ROOT = Path(__file__).resolve().parents[3]
TOML_INPUTS = (
    (
        "requirements",
        load_requirements,
        '[[current]]\nselect = { net = "SUPPLY" }\ncurrent = "20mA"\ntemp_rise = "5K"\n',
    ),
    ("drawing-spec", read_spec, '[page]\npaper = "A4"\ngap = "4mm"\n[fab]\nnotes = ["Authored note."]\n'),
    ("export-preset", read_preset, "[gerbers]\nprecision = 6\n[drill]\nmirror_y = false\n"),
    ("assembly-template", read_template, "[placement.rotation.bottom]\nsign = -1\noffset = 90.5\n"),
)


def _tool():
    spec = importlib.util.spec_from_file_location("_public_format_generator", ROOT / "tools/gen_schemas.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _schema_of(identifier):
    # Device/family v0 are existing distinct dialects; every other public v0 has a prepared mirror.
    prepared = (
        identifier
        if identifier in {"fenolite.device.v0", "fenolite.family.v0"}
        else identifier.removesuffix(".v0") + ".v1"
        if identifier.endswith(".v0")
        else identifier
    )
    return _schema.load(f"formats/{prepared}.json"), prepared


@pytest.mark.parametrize(("name", "reader", "body"), TOML_INPUTS, ids=[row[0] for row in TOML_INPUTS])
def test_supported_input_ids_have_equal_meaning_and_future_ids_still_fail(name, reader, body):
    old = f'schema = "fenolite.{name}.v0"\n' + body
    new = old.replace(f"{name}.v0", f"{name}.v1")
    assert reader(old) == reader(new)
    schema, _ = _schema_of(f"fenolite.{name}.v0")
    assert _schema.validate(tomllib.loads(new), schema) == []
    with pytest.raises(FormatError):
        reader(new.replace(f"{name}.v1", f"{name}.v2"))


def test_review_v0_and_v1_keep_marks_and_reject_bad_coordinates():
    mark = {"id": "m1", "doc": "board.kicad_pcb", "x_nm": 5, "y_nm": -7, "note": "Authored note."}
    old = {"schema": "fenolite.review.v0", "marks": [mark]}
    new = {**old, "schema": "fenolite.review.v1"}
    assert read_review(old) == read_review(new)
    schema, _ = _schema_of(old["schema"])
    assert _schema.validate(new, schema) == []
    invalid = {**new, "marks": [{**mark, "x_nm": "5"}]}
    assert _schema.validate(invalid, schema)
    with pytest.raises(FormatError):
        read_review(invalid)
    with pytest.raises(FormatError):
        read_review({**new, "schema": "fenolite.review.v2"})


def test_placement_request_v1_uses_the_real_command_reader(tmp_path):
    ctx = Context("json", 0, datetime(2026, 1, 1, tzinfo=UTC), random.Random(0), False, tmp_path)
    path = tmp_path / "constraints.json"
    args = Namespace(constraints=path.name, max_candidates=None, pitch=None, gap=None, margin=None)
    body = {"schema": "fenolite.placement-request.v0", "constraints": {"pitch": 1000000}}
    path.write_text(json.dumps(body))
    old = _constraints(args, ctx, 500000, 0, 0)
    body["schema"] = "fenolite.placement-request.v1"
    path.write_text(json.dumps(body))
    assert _constraints(args, ctx, 500000, 0, 0).constraints.pitch == old.constraints.pitch == 1000000
    schema, _ = _schema_of(body["schema"])
    assert _schema.validate(body, schema) == []
    body["constraints"]["pitch"] = "1mm"
    assert _schema.validate(body, schema)
    path.write_text(json.dumps(body))
    with pytest.raises(Exception) as caught:
        _constraints(args, ctx, 500000, 0, 0)
    assert getattr(caught.value, "code", "") == "FEN-3004"


TRUSTED = tuple(
    sorted(
        {
            *ROOT.glob("src/fenolite/catalog/data/**/*.toml"),
            *ROOT.glob("src/fenolite/catalog/families/*.toml"),
            *ROOT.glob("tests/data/pins/*.toml"),
            *ROOT.glob("tests/data/drawn/*/schematic.toml"),
            *ROOT.glob("examples/blocks/layouts/*.toml"),
            *ROOT.glob("examples/blocks/golden/*.json"),
            *ROOT.glob("examples/library-devices/source/**/*.toml"),
            *ROOT.glob("examples/library-devices/source/**/item.json"),
            *ROOT.glob("examples/library-devices/source/**/PROVENANCE.json"),
            *ROOT.glob("docs/evidence/altium-kit/*.json"),
            ROOT / "examples/import_python/PROVENANCE.json",
        }
    )
)


@pytest.mark.parametrize("path", TRUSTED, ids=lambda path: path.relative_to(ROOT).as_posix())
def test_shipped_and_authored_document_shapes(path):
    raw = tomllib.loads(path.read_text()) if path.suffix == ".toml" else json.loads(path.read_text())
    identifier = raw.get("schema")
    if identifier is None:  # e.g. the record version index, which has no serialized schema ID
        return
    schema, prepared = _schema_of(
        "fenolite.library-metadata.v1" if path.name == "library.toml" else identifier
    )
    assert _schema.validate({**raw, "schema": prepared}, schema) == [], path


def test_prepared_kit_manifest_is_accepted_without_changing_its_data():
    from fenolite.cli._kit import kit_sources
    from fenolite.verify.kit.manifest import kit_files, read_kit

    old = json.loads(kit_files(kit_sources())["kit.json"])
    new = {**old, "schema": "fenolite.altium-kit.v1"}
    before, after = read_kit(json.dumps(old).encode()), read_kit(json.dumps(new).encode())
    assert before.files == after.files and before.steps == after.steps and before.samples == after.samples
    schema, _ = _schema_of(old["schema"])
    assert _schema.validate(new, schema) == []


def test_pose_role_and_lock_readers_accept_the_prepared_ids(tmp_path):
    from fenolite.dsl.lock import read_lock
    from fenolite.lens.drawn import read_drawn
    from fenolite.lens.edits import read_edits
    from fenolite.lens.placements import read_placements
    from fenolite.reuse.blocklayout import read_block_layout
    from fenolite.roles.rolemanifest import loads
    from fenolite.roles.store import loads_document

    for schema, reader, body in (
        ("lock", lambda text: read_lock(text, file="design.lock"), 'design = "authored"\n'),
        ("placements", lambda text: read_placements(text, origin=Point(0, 0)), "[part.R1]\nx = 1\ny = 2\n"),
        ("edits", lambda text: read_edits(text, origin=Point(0, 0)), ""),
    ):
        old = f'schema = "fenolite.{schema}.v0"\n' + body
        new = old.replace(f"{schema}.v0", f"{schema}.v1")
        assert reader(old) == reader(new)
    for name, reader, body in (
        ("roles", loads_document, {"roles": {}}),
        ("role-copper", loads, {"items": [{"key": "authored", "sha256": "a" * 64}]}),
    ):
        old = {"schema": f"fenolite.{name}.v0", **body}
        assert reader(json.dumps(old)) == reader(json.dumps({**old, "schema": f"fenolite.{name}.v1"}))
    old = (ROOT / "examples/blocks/layouts/divider.toml").read_text()
    source, prepared = tmp_path / "old.toml", tmp_path / "new.toml"
    source.write_text(old)
    prepared.write_text(old.replace("block-layout.v0", "block-layout.v1"))
    assert read_block_layout(source) == read_block_layout(prepared)
    drawn = (ROOT / "tests/data/drawn/flat/schematic.toml").read_text()
    assert read_drawn(drawn) == read_drawn(drawn.replace("drawn-schematic.v0", "drawn-schematic.v1"))


@pytest.mark.parametrize(
    "relative",
    (
        "tests/data/library/pins/two_pin.toml",
        "tests/data/library/packages/two_pad.toml",
        "tests/data/library/parts/example_reg_grade.toml",
    ),
)
def test_record_mirror_ids_preserve_canonical_data_and_review_digests(relative):
    from fenolite.catalog.records import parse_record, record_digest, record_text

    text = (ROOT / relative).read_text()
    identifier = tomllib.loads(text)["schema"]
    old = parse_record(text)
    new = parse_record(text.replace(identifier, identifier[:-1] + "1", 1))
    assert old == new
    assert record_digest(new) == record_digest(old)
    assert parse_record(record_text(new)) == new


def test_generated_record_dispatch_accepts_both_versions(tmp_path):
    from fenolite.cli._library_check import load

    ctx = Context("json", 0, datetime(2026, 1, 1, tzinfo=UTC), random.Random(0), False, tmp_path)
    for relative in ("tests/data/library_rules/good/packages/chip.toml", "tests/data/pins/example_dual.toml"):
        text = (ROOT / relative).read_text()
        schema = tomllib.loads(text)["schema"]
        first, second = tmp_path / ("old-" + Path(relative).name), tmp_path / ("new-" + Path(relative).name)
        first.write_text(text)
        second.write_text(text.replace(schema, schema[:-1] + "1", 1))
        old, _ = load([str(first)], ctx)
        new, _ = load([str(second)], ctx)
        assert len(old) == len(new) == 1
        assert (old[0].kind, old[0].id) == (new[0].kind, new[0].id)


def test_public_container_readers_accept_mirrors_and_keep_writers_at_v0(tmp_path):
    from fenolite.dsl.blockitem import read_item
    from fenolite.exports.manifest import load
    from fenolite.importer.provenance import copy_mode
    from fenolite.library.items import read_item as read_library_item
    from fenolite.library.provenance import provenance_problems
    from fenolite.library.release import library_meta
    from fenolite.model import canonical
    from fenolite.testing.blocks import differing_paths

    item_path = ROOT / "examples/library-devices/source/symbols/cc0/FenoliteDevices/DemoTwoPin/item.json"
    item = json.loads(item_path.read_text())
    assert read_library_item(json.dumps(item).encode()) == read_library_item(
        json.dumps({**item, "schema": "fenolite.library-item.v1"}).encode()
    )
    provenance_path = item_path.with_name("PROVENANCE.json")
    provenance = json.loads(provenance_path.read_text())
    assert provenance_problems({**provenance, "schema": "fenolite.provenance.v1"}) == []
    assert copy_mode({"schema": "fenolite.import-provenance.v1", "copy": True})
    metadata = tmp_path / "library.toml"
    metadata.write_text('schema = "fenolite.library.v0"\nname = "authored"\nversion = "1.0.0"\n')
    old_metadata = library_meta(tmp_path)
    metadata.write_text(metadata.read_text().replace("fenolite.library.v0", "fenolite.library-metadata.v1"))
    assert library_meta(tmp_path) == old_metadata
    manifest = json.loads((ROOT / "tests/data/exports/manifest_v01.json").read_text())
    assert (
        load(json.dumps(manifest)).artifacts
        == load(json.dumps({**manifest, "schema": "fenolite.artifacts.v1"})).artifacts
    )
    gold = {"schema": "fenolite.block-golden.v0", "circuit": {"net": "AUTHORED"}}
    prepared = {**gold, "schema": "fenolite.block-golden.v1"}
    assert differing_paths(canonical.dumps(gold).encode(), canonical.dumps(prepared).encode()) == ()
    assert differing_paths(b"malformed", b"malformed") == ("$",)
    prepared["circuit"] = {"net": "CHANGED"}
    assert differing_paths(canonical.dumps(gold).encode(), canonical.dumps(prepared).encode()) == (
        "circuit.net",
    )
    records = sorted((ROOT / "tests/data/library_repo/block_items").rglob("block.json"))
    assert records
    block = json.loads(records[0].read_text())
    assert (
        read_item(json.dumps(block)).digest
        == read_item(json.dumps({**block, "schema": "fenolite.block-item.v1"})).digest
    )


def test_every_source_id_requires_an_explicit_decision_and_public_format_target(monkeypatch, tmp_path):
    tool = _tool()
    inventory = tool._formats_module()
    found = inventory.inventory(ROOT)
    assert not set(found) - inventory.FORMATS.keys()
    targets = {target.schema_id for target in tool.TARGETS}
    for identifier in found:
        row = inventory.FORMATS[identifier]
        if row.owner != "formats":
            continue
        prepared = (
            identifier
            if identifier in {"fenolite.device.v0", "fenolite.family.v0"}
            else identifier.removesuffix(".v0") + ".v1"
            if identifier.endswith(".v0")
            else identifier
        )
        assert prepared in targets
    source = tmp_path / "src/fenolite/authored.py"
    source.parent.mkdir(parents=True)
    source.write_text('SCHEMA = "fenolite.authored.v0"\n')
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    assert tool.main(["--formats", "--check"]) == 1


def test_evidence_artifacts_have_internal_decisions_without_model_or_public_targets() -> None:
    tool = _tool()
    inventory = tool._formats_module()
    production = inventory.inventory(ROOT)
    targets = {target.schema_id for target in tool.TARGETS}
    for identifier, paths in inventory.TEST_EVIDENCE_FORMATS.items():
        assert paths and any(identifier in (ROOT / path).read_text(encoding="utf-8") for path in paths)
        assert identifier not in production
        row = inventory.FORMATS[identifier]
        assert row.classification == "internal" and row.owner == "internal" and row.reference is None
        assert identifier not in targets and identifier.removesuffix(".v0") + ".v1" not in targets
    artifact = json.loads((ROOT / "docs/evidence/drawn-schematic.json").read_text(encoding="utf-8"))
    assert artifact["schema"] == "fenolite.drawn-corpus-measurement.v0"
    assert artifact["observations"]  # historical measured runs, not canonical model layer files


def test_internal_census_ids_do_not_become_public_schema_mirrors(monkeypatch, tmp_path) -> None:
    tool = _tool()
    inventory = tool._formats_module()
    source = tmp_path / "src/fenolite/authored.py"
    source.parent.mkdir(parents=True)
    source.write_text(repr(tuple(inventory.TEST_EVIDENCE_FORMATS)), encoding="utf-8")
    monkeypatch.setattr(tool, "ROOT", tmp_path)
    assert tool._format_targets() == []


def test_bounded_geometry_trace_marker_is_not_a_schema_id() -> None:
    tool = _tool()
    inventory = tool._formats_module()
    for marker, path in inventory.TEST_DIAGNOSTIC_MARKERS.items():
        assert marker in (ROOT / path).read_text(encoding="utf-8")
        assert inventory.ID.fullmatch(marker) is None
        assert marker not in inventory.FORMATS
        assert all(target.schema_id != marker for target in tool.TARGETS)
        assert marker in tool.format_readme()
