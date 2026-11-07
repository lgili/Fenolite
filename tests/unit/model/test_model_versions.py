# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Version syntax, pure migration and the model writer's independently activated v1."""

from __future__ import annotations

import copy
import json

import pytest

from fenolite import __version__
from fenolite.model import canonical
from fenolite.model.design import SCHEMA_VERSION, Design, parse_version, readable
from fenolite.model.migrate import FutureVersionError, MigrationError, migrate


@pytest.mark.parametrize("version,expected", [("0", (0, 0)), ("1.0", (1, 0)), ("12.34", (12, 34))])
def test_parse_version(version: str, expected: tuple[int, int]) -> None:
    assert parse_version(version) == expected


@pytest.mark.parametrize("version", ["", "1", "v1.0", "01.0", "1.00", "1.0.0", " 1.0", "1.0\n", "-1.0"])
def test_reject_noncanonical_version(version: str) -> None:
    with pytest.raises(ValueError):
        parse_version(version)
    assert not readable(version)


def test_readability_and_writer_are_model_versions() -> None:
    assert SCHEMA_VERSION == "1.1"
    assert readable("0") and readable("1.0") and readable("1.1")
    assert not any(readable(version) for version in ("0.1", "0.0", "1.2", "2.0"))
    meta = json.loads(canonical.dump_texts(Design.new("authored", seed=1))["meta.json"])
    assert meta["schema_version"] == "1.1"  # the writer always stamps the current version (c0462, D4)
    assert meta["fenolite_version"] == __version__ == "0.7.0"


def test_pure_step_keeps_integer_units_ids_and_opaque_fragments() -> None:
    data = {
        "meta.json": {"schema_version": "0"},
        "board.json": {"id": "brd_x", "x": -123, "ext": {"kicad": ["opaque", {"n": 7}]}},
    }
    before = copy.deepcopy(data)
    migrated, steps = migrate(data, "0")
    assert data == before
    assert steps == ("0 -> 1.0", "1.0 -> 1.1")
    before["meta.json"]["schema_version"] = "1.1"
    assert migrated == before
    migrated["board.json"]["ext"]["kicad"].append("changed")
    assert data != migrated and data["board.json"]["ext"]["kicad"] == ["opaque", {"n": 7}]
    again, steps = migrate(before, "1.1")
    assert again == before and again is not before and steps == ()
    one = copy.deepcopy(before)
    one["meta.json"]["schema_version"] = "1.0"
    assert migrate(one, "1.0") == (before, ("1.0 -> 1.1",))


@pytest.mark.parametrize("version", ["1.2", "2.0"])
def test_future_version_names_reader_and_input(version: str) -> None:
    with pytest.raises(FutureVersionError, match=rf"{version!r}.*'1.1'") as caught:
        migrate({"meta.json": {"schema_version": version}}, version)
    assert caught.value.cli_code == "FEN-3002"


@pytest.mark.parametrize("version", ["0.0", "0.1"])
def test_no_silent_missing_migration_path(version: str) -> None:
    with pytest.raises(MigrationError, match="no unique migration path"):
        migrate({"meta.json": {"schema_version": version}}, version)


def test_current_fields_and_bom_validation_survive_legacy_read() -> None:
    from dataclasses import replace

    from fenolite.core.coords import Point
    from fenolite.model import Component
    from fenolite.model.drawn import DrawnField, DrawnFont, DrawnLabel

    design = Design.new("current-fields", seed=34)
    assert design.board is not None
    component = Component(id="cmp_authored", ref="DOC1", bom_only=True)
    design = replace(
        design,
        circuit=replace(design.circuit, components=(component,)),
        board=replace(design.board, max_curve_error=10_000),
    )
    data = {name: json.loads(text) for name, text in canonical.dump_texts(design).items()}
    data["meta.json"]["schema_version"] = "0"
    before = copy.deepcopy(data)
    migrated, _ = migrate(data, "0")
    current = canonical.from_data(migrated)
    assert data == before
    assert current.board is not None and current.board.max_curve_error == 10_000
    assert current.circuit.components == (component,)
    assert not [issue for issue in current.validate() if issue.code == "model.bom-only"]
    invalid = replace(component, board_only=True)
    invalid_design = replace(current, circuit=replace(current.circuit, components=(invalid,)))
    assert [(i.code, i.severity) for i in invalid_design.validate() if i.code == "model.bom-only"] == [
        ("model.bom-only", "error")
    ]
    label = DrawnLabel(
        "global",
        "AUTHORED",
        Point(-254_000, 508_000),
        font=DrawnFont(thickness=0, bold=False, italic=False, face="Authored Face"),
        justify="",
        intersheet_refs=DrawnField("Intersheetrefs", Point(254_000, 0), hide=False),
    )
    payload = {"meta.json": {"schema_version": "0"}, "label": json.loads(canonical.dumps(label))}
    upgraded, _ = migrate(payload, "0")
    assert canonical.loads(json.dumps(upgraded["label"]), DrawnLabel) == label
    assert upgraded["label"] == payload["label"]


@pytest.mark.parametrize("version", ["0", "1.0", "2.0"])
def test_legacy_pin_view_refuses_noncurrent_schema_markers(version):
    import json

    from _schema_pin import legacy_meta_bytes

    with pytest.raises(AssertionError):
        legacy_meta_bytes(json.dumps({"schema_version": version}).encode())


def test_legacy_pin_view_preserves_every_other_byte():
    from _schema_pin import legacy_meta_bytes

    current = b'{"schema_version": "1.1", "extra": [0, false, "1.1"], "opaque": "kept"}\n'
    assert (
        legacy_meta_bytes(current)
        == b'{"schema_version": "0", "extra": [0, false, "1.1"], "opaque": "kept"}\n'
    )
