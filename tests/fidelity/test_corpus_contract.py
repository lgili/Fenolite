# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The fidelity corpus ratchet fails for regressions and stale improvements (c0278)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from _corpus import CorpusItem
from _fidelity_corpus import SCHEMA, load_ratchet, materialize, ratchet_problems

ID = "kicad-demo-10-0-6-pcb-03"


def test_ratchet_catches_both_directions_and_new_kinds() -> None:
    assert ratchet_problems(ID, {"7:text-field": 2}, {"7:text-field": 2}) == []
    assert ratchet_problems(ID, {}, {"7:text-field": 2}) == [
        f"{ID}: 7:text-field fell from 2 to 0; lower the ratchet entry"
    ]
    assert ratchet_problems(ID, {"7:text-field": 3}, {"7:text-field": 2}) == [
        f"{ID}: 7:text-field grew from 2 to 3"
    ]
    assert ratchet_problems(ID, {"S:item-missing": 1}, {}) == [f"{ID}: S:item-missing grew from 0 to 1"]


def _file(tmp_path: Path, body: str) -> Path:
    path = tmp_path / "accepted.toml"
    path.write_text(f'schema = "{SCHEMA}"\n' + body, encoding="utf-8")
    return path


def test_unmeasured_rows_are_explicit_not_zero_baselines(tmp_path: Path) -> None:
    path = _file(tmp_path, f'[pending]\n"{ID}" = "requires an actual all-level run"\n')
    record = load_ratchet(path)
    assert "row" not in record and record["pending"][ID]
    assert "counts" not in json.dumps(record)


@pytest.mark.parametrize(
    "counts", ('{"7:text-field"=true}', '{"7:text-field"=-1}', '{"6:via-missing"=1}', '{"7:text-field"=0}')
)
def test_ratchet_rejects_non_counts_and_wrong_level(tmp_path: Path, counts: str) -> None:
    path = _file(
        tmp_path, f'[[row]]\nid="{ID}"\ncounts={counts}\nreason="authored test"\nattribution="fenolite"\n'
    )
    with pytest.raises(ValueError, match="counts"):
        load_ratchet(path)


def test_measured_row_has_no_upstream_names_or_values(tmp_path: Path) -> None:
    row = f'[[row]]\nid="{ID}"\ncounts={{}}\nreason="authored test"\nattribution="fenolite"\n'
    path = _file(tmp_path, row)
    assert load_ratchet(path)["row"][0]["counts"] == {}
    path = _file(tmp_path, row + 'board = "an upstream file name"\n')
    with pytest.raises(ValueError, match="only id, counts, reason"):
        load_ratchet(path)


def test_duplicate_or_already_measured_pending_rows_refuse(tmp_path: Path) -> None:
    row = f'[[row]]\nid="{ID}"\ncounts={{}}\nreason="authored test"\nattribution="fenolite"\n'
    with pytest.raises(ValueError, match="unique"):
        load_ratchet(_file(tmp_path, row + row))
    with pytest.raises(ValueError, match="never both"):
        load_ratchet(_file(tmp_path, row + f'[pending]\n"{ID}"="not actually pending"\n'))


def test_materialize_keeps_a_board_variant_separate_from_another_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import _fidelity_corpus

    rows, items = [], []
    for ident, name, data in (
        (ID, "unrouted.kicad_pcb", b"authored board"),
        ("kicad-demo-10-0-6-pro-03", "routed.kicad_pro", b"authored project"),
    ):
        path = tmp_path / "cache" / ident / name
        path.parent.mkdir(parents=True)
        path.write_bytes(data)
        rows.append(
            {
                "id": ident,
                "url": "https://example.invalid/ref/demo/" + name,
                "ref": "authored",
                "license": "CC0-1.0",
                "license_variant": "",
                "uses": ["origin:kicad-demos", "rtf"],
                "sha256": hashlib.sha256(data).hexdigest(),
            }
        )
        items.append(CorpusItem(ident, path, "CC0-1.0", ("rtf",), "kicad-demos", False))
    monkeypatch.setattr(_fidelity_corpus, "manifest_items", lambda _: items)
    out = materialize(rows[0], rows, tmp_path / "original")
    assert out == tmp_path / "original"
    assert {p.name for p in out.iterdir()} == {"unrouted.kicad_pcb"}
    assert items[0].path.read_bytes() == b"authored board"
    items[0].path.write_bytes(b"changed cache")
    with pytest.raises(AssertionError, match="cached SHA-256 changed"):
        materialize(rows[0], rows, tmp_path / "changed")
