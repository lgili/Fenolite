# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Read-only release migration, future refusal, and the authored model/example corpus (c0218)."""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import _schema
import pytest
from hypothesis import given, settings
from strategies import designs

from fenolite.cli._script import run_design_script
from fenolite.core.errors import FormatError
from fenolite.dsl import to_model
from fenolite.model import Board, canonical
from fenolite.model.design import Design
from fenolite.model.migrate import FutureVersionError, MigrationError, Step, migrate

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / "tests/data/model"
RELEASES = tuple(DATA / f"v0.{minor}.0" for minor in range(1, 6))


@pytest.mark.parametrize("folder", RELEASES, ids=lambda p: p.name)
def test_every_release_loads_readonly_and_preserves_layers(folder: Path) -> None:
    before = {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}
    design = canonical.load_dir(folder)
    notes = [i for i in design.findings.issues if i.code == "model.migrated"]
    assert len(notes) == 1 and notes[0].severity == "info" and notes[0].where == str(folder)
    assert "0 -> 1.0" in notes[0].message and "1.0 -> 1.1" in notes[0].message
    assert design.header.schema_version == "1.1" and len(design.circuit.components) == 3
    findings = dataclasses.replace(
        design.findings, issues=tuple(i for i in design.findings.issues if i not in notes)
    )
    texts = canonical.dump_texts(dataclasses.replace(design, findings=findings))
    for name, _, _ in canonical.LAYER_FILES:
        if name != "meta.json":
            assert json.loads(texts[name]) == json.loads(before[name])
    assert before == {p.name: p.read_bytes() for p in folder.iterdir() if p.is_file()}


def test_current_folder_and_unrelated_files(tmp_path: Path) -> None:
    canonical.dump_dir(Design.new("authored", seed=2), tmp_path)
    (tmp_path / "build.json").write_text("not model JSON")
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    assert not canonical.load_dir(tmp_path).findings.issues
    assert before == {p.name: p.read_bytes() for p in tmp_path.iterdir()}


@pytest.mark.parametrize("version", ["1.2", "2.0", "99.0"])
def test_future_refused_before_unknown_layers(tmp_path: Path, version: str) -> None:
    (tmp_path / "meta.json").write_text(json.dumps({"schema_version": version, "future_field": "unknown"}))
    with pytest.raises(FutureVersionError, match=rf"{version!r}.*'1.1'") as caught:
        canonical.load_dir(tmp_path)
    assert caught.value.locator == "/schema_version" and caught.value.cli_code == "FEN-3002"


@pytest.mark.parametrize("version", [None, 1, True, "1", "1.0.0", "01.0"])
def test_bad_version_is_format_error(tmp_path: Path, version: object) -> None:
    (tmp_path / "meta.json").write_text(json.dumps({"schema_version": version}))
    with pytest.raises(MigrationError) as caught:
        canonical.load_dir(tmp_path)
    assert caught.value.cli_code == "FEN-3004"


def test_migration_precedes_current_validation(tmp_path: Path) -> None:
    data = canonical.read_data(RELEASES[1])
    data["board.json"] = json.loads((DATA / "v0.2.1/blink_2layer.board.json").read_text())
    migrated, _ = migrate(data, "0")
    assert _schema.validate(migrated["board.json"], _schema.load("fenolite.model.v1/board.json")) == []
    assert canonical.from_data(migrated).board is not None
    data["board.json"]["future_unknown"] = 5
    for name, value in data.items():
        (tmp_path / name).write_text(json.dumps(value))
    with pytest.raises(FormatError) as caught:
        canonical.load_dir(tmp_path)
    assert caught.value.locator == "/future_unknown"


def test_invalid_chains_are_not_silent(monkeypatch: pytest.MonkeyPatch) -> None:
    import fenolite.model.migrate as module

    data = {"meta.json": {"schema_version": "0"}}
    monkeypatch.setattr(module, "STEPS", ())
    with pytest.raises(MigrationError, match="no unique migration path"):
        migrate(data, "0")
    step = Step("0", "1.0", lambda value: value, "broken authored step")
    monkeypatch.setattr(module, "STEPS", (step,))
    with pytest.raises(MigrationError, match="did not set its target"):
        migrate(data, "0")
    monkeypatch.setattr(module, "STEPS", (step, step))
    with pytest.raises(MigrationError, match="no unique migration path"):
        migrate(data, "0")


def _round_trip_legacy(design: Design) -> None:
    current = canonical.dump_texts(design)
    raw = {name: json.loads(text) for name, text in current.items()}
    raw["meta.json"]["schema_version"] = "0"
    migrated, steps = migrate(raw, "0")
    assert steps == ("0 -> 1.0", "1.0 -> 1.1")
    assert canonical.dump_texts(canonical.from_data(migrated)) == current


@settings(max_examples=30, deadline=None)
@given(designs())
def test_corpus_of_the_tests_generated_models(design: Design) -> None:
    """Use the same complete-model strategy as the canonical/property test suite."""
    _round_trip_legacy(design)


@pytest.mark.parametrize("path", sorted(DATA.rglob("*.json")), ids=lambda p: str(p.relative_to(DATA)))
def test_corpus_of_the_tests_committed_documents(path: Path) -> None:
    if path.name in dict((name, cls) for name, _, cls in canonical.LAYER_FILES):
        folder = path.parent
        assert canonical.load_dir(folder).header.schema_version == "1.1"
    else:
        # Standalone older board/rules layers have no folder version to migrate.
        text = path.read_text(encoding="utf-8")
        layer = next((name, cls) for name, _, cls in canonical.LAYER_FILES if path.name.endswith("." + name))
        value = canonical.loads(text, layer[1], file=str(path))
        assert canonical.dumps(value) == text
        assert _schema.validate(json.loads(text), _schema.load("fenolite.model.v1/" + layer[0])) == []


@pytest.mark.parametrize(
    "script",
    sorted((ROOT / "examples").rglob("design.py")),
    ids=lambda p: str(p.relative_to(ROOT / "examples")),
)
def test_corpus_of_the_tests_examples(script: Path) -> None:
    """Elaborate every authored example; migration does not require native tools or asset lookup."""
    _round_trip_legacy(to_model(run_design_script(script).design))


@pytest.mark.parametrize("folder", RELEASES, ids=lambda p: p.name)
def test_release_board_numeric_waiver_is_only_authored_nanometre_geometry(folder: Path) -> None:
    import re

    text = (folder / "board.json").read_text()
    numbers = set(re.findall(r"(?<![0-9A-Za-z.\-_])[0-9]{9,10}(?![0-9A-Za-z.\-_])", text))
    assert numbers == {
        "100000000",
        "109000000",
        "114000000",
        "115000000",
        "120000000",
        "130000000",
        "132000000",
        "138000000",
        "150000000",
    }
    board = canonical.loads(text, Board)
    assert {(fp.position.x, fp.position.y) for fp in board.footprints} == {
        (132_000_000, 109_000_000),
        (114_000_000, 115_000_000),
        (138_000_000, 120_000_000),
    }
