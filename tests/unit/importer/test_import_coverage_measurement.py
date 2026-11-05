# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Real source-emission counts agree with complete imports; observations claim no conversion proof."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

import pytest
from _importcode import grouped
from _importcoverage import OUTPUT, PAGE, ROOT, counts, declared, digest, measure, observation, table

from fenolite.api import run

AUTHORED = ROOT / "tests/data/import_python/two_sheet/two_sheet.kicad_pcb"


@pytest.mark.parametrize("kind", ["authored-project", "authored-opaque"])
def test_measurement_agrees_with_complete_cli(
    kind: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "config"))
    path = AUTHORED if kind == "authored-project" else grouped(tmp_path)
    before = path.read_bytes()
    measured = measure(path, ident=kind, date="2026-11-01")
    reply = run(
        "import",
        str(path),
        "--to",
        "python",
        "--out",
        "out",
        "--allow-lossy",
        "--dry-run",
        cwd=tmp_path,
        timestamp="2026-11-01T00:00:00Z",
    )
    assert reply.exit_code == 0, (reply.error, (reply.envelope or {}).get("issues"))
    assert reply.result["equivalence"]["equivalent"] is True
    assert measured["unexpressed"] == counts(reply.result["unexpressed"])
    assert measured["counts"] == reply.result["counts"]
    assert path.read_bytes() == before and not (tmp_path / "out").exists()


def test_measurement_does_not_rebuild(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    def forbidden(*args: object, **kwargs: object) -> None:
        raise AssertionError("source emission must not be confused with a full conversion proof")

    monkeypatch.setattr("subprocess.run", forbidden)
    monkeypatch.setattr("subprocess.Popen", forbidden)
    monkeypatch.setattr("fenolite.cli.cmd_import._build", forbidden)
    measured = measure(AUTHORED, ident="authored", date="2026-11-01")
    assert measured["input_sha256"] == hashlib.sha256(AUTHORED.read_bytes()).hexdigest()
    assert set(measured) == {"id", "input_sha256", "unexpressed", "counts", "measurement_sha256"}
    assert "equivalent" not in measured and "seconds" not in measured


def test_observations_cover_all_declared_rows_and_bound_inputs() -> None:
    data = observation()
    assert data["schema"] == "fenolite.import-coverage.v0" and data["verification"] == "emission-only"
    assert data["date"] == "2026-11-04"
    entries = {row["id"]: row for row in declared()}
    assert {row["id"] for row in data["rows"]} == set(entries)
    assert len(data["rows"]) == len(entries) == 18
    assert {"kicad-demo-10-0-6-pcb-06", "kicad-demo-10-0-6-pcb-18"} <= set(entries)
    assert data["measurement_sha256"] == digest(
        {key: value for key, value in data.items() if key != "measurement_sha256"}
    )
    for row in data["rows"]:
        assert row["input_sha256"] == entries[row["id"]]["sha256"]
        assert row["measurement_sha256"] == digest(
            {key: value for key, value in row.items() if key != "measurement_sha256"}
        )
        assert set(row) == {"id", "input_sha256", "unexpressed", "counts", "measurement_sha256"}
        assert row["unexpressed"] == counts(row["unexpressed"])
        assert all(set(item) == {"kind", "count"} and item["count"] > 0 for item in row["unexpressed"])
    assert table(data) in PAGE.read_text(encoding="utf-8")
    assert all(re.fullmatch("[0-9a-f]{64}", data[key]) for key in ("tool_sha256", "measurement_sha256"))
    assert (
        data["tool_sha256"]
        == hashlib.sha256((ROOT / "tools/measure_import_coverage.py").read_bytes()).hexdigest()
    )
    assert re.fullmatch("[0-9a-f]{40}", data["base_commit"])
    assert OUTPUT.name in PAGE.read_text(encoding="utf-8")


def test_historical_conversion_table_is_preserved() -> None:
    # Keep the 16 local conversions and both observed CI conversions, including their original times.
    text = PAGE.read_text(encoding="utf-8")
    historical = text.split("<!-- import-corpus:begin -->", 1)[1].split("<!-- import-corpus:end -->", 1)[0]
    assert (
        hashlib.sha256(historical.encode("utf-8")).hexdigest()
        == "63b107b962134bcde1ab8c032128bb7c5361d2e53c6c705b6ab110aaa38422f1"
    )
    rows = [line for line in historical.splitlines() if re.match(r"\| \d\d \|", line)]
    assert len(rows) == 18
    assert all("| yes |" in row for row in rows)
    assert any(row.startswith("| 06 |") for row in rows)
    assert any(row.startswith("| 18 |") for row in rows)
