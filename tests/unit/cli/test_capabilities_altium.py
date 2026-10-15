# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Installed capabilities and build notices follow per-kind graduation decisions."""

from __future__ import annotations

import importlib.util
import json
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
from _altium import hier, sample

from fenolite.backends.altium import claims, graduation
from fenolite.cli.main import main
from fenolite.core.evidence import Evidence, Level
from fenolite.dsl import to_model
from fenolite.lens.altium import _written_claims, build_altium

ROOT = Path(__file__).resolve().parents[3]


def test_packaged_decisions_match_repository_rule() -> None:
    spec = importlib.util.spec_from_file_location(
        "fenolite_graduation_generator", ROOT / "tools/gen_altium_graduation.py"
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert graduation.SNAPSHOT.read_text(encoding="utf-8") == module.render()


def test_capabilities_cover_every_write_kind(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["capabilities", "--json", "--no-tools"]) == 0
    result = json.loads(capsys.readouterr().out)["result"]
    backend = next(b for b in result["backends"] if b["name"] == "altium")
    pending = {
        kind: reasons for entry in result["experimental"] for kind, reasons in entry["missing"].items()
    }
    assert set(backend["write_kinds"]) | set(pending) == {
        r.kind for r in claims.MATRIX if r.write is not None
    }
    assert not set(backend["write_kinds"]) & set(pending)
    assert pending == {kind: list(reasons) for kind, reasons in claims.GRADUATION_MISSING.items() if reasons}


def test_changed_write_declaration_fails_closed() -> None:
    row = next(r for r in claims.RAW_MATRIX if r.kind == "altium_schlib")
    assert row.write is not None
    changed = replace(row, write=Evidence(Level.INFERRED, hypotheses=(*row.write.hypotheses, "H-A-UNIT")))
    rows, reasons = graduation.decisions([changed], claims.OWN_READBACK)
    assert "write" in rows[0].experimental and "snapshot" in reasons[row.kind][0]


def test_malformed_conditions_are_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = json.loads(graduation.SNAPSHOT.read_text(encoding="utf-8"))
    data["kinds"]["altium_schlib"]["missing"] = [42]
    path = tmp_path / "graduation.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    monkeypatch.setattr(graduation, "SNAPSHOT", path)
    with pytest.raises(ValueError, match="invalid graduation conditions"):
        graduation.decisions(claims.RAW_MATRIX, claims.OWN_READBACK)


def _promoted_matrix(monkeypatch: pytest.MonkeyPatch, pending: str | None = None) -> None:
    monkeypatch.setattr(
        claims,
        "MATRIX",
        tuple(
            replace(
                row,
                experimental=("write",) if row.kind == pending else (),
                write=replace(
                    row.write, level=Level.INFERRED if row.kind == pending else Level.CORPUS_VERIFIED
                )
                if row.write
                else None,
            )
            for row in claims.MATRIX
        ),
    )


def test_all_graduated_capabilities_omit_experimental_entries(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _promoted_matrix(monkeypatch)
    assert main(["capabilities", "--json", "--no-tools"]) == 0
    result = json.loads(capsys.readouterr().out)["result"]
    assert result["experimental"] == []
    altium = next(b for b in result["backends"] if b["name"] == "altium")
    assert set(altium["write_kinds"]) == {r.kind for r in claims.MATRIX if r.write}
    assert "write" in altium["operations"]


def test_all_graduated_build_has_no_notice_and_combines_written_evidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _promoted_matrix(monkeypatch)
    built = build_altium(to_model(sample()), name="Graduated")
    assert built.files
    assert not any(issue.code == "altium.experimental" for issue in built.issues)
    assert built.summary["experimental"] is False
    assert built.evidence.level is Level.CORPUS_VERIFIED


def test_current_build_reports_one_notice_for_actual_files() -> None:
    built = build_altium(to_model(sample()), name="Current")
    notices = [issue for issue in built.issues if issue.code == "altium.experimental"]
    assert len(notices) == 1 and notices[0].severity == "info"
    assert "altium_schdoc_binary" in notices[0].message
    assert "altium_pcbdoc" not in notices[0].message


def test_mixed_build_reports_only_harness(monkeypatch: pytest.MonkeyPatch) -> None:
    _promoted_matrix(monkeypatch, "altium_harness")
    built = build_altium(to_model(hier()), name="Mixed", sheets="modules")
    assert any(name.endswith(".Harness") for name in built.files)
    notices = [issue for issue in built.issues if issue.code == "altium.experimental"]
    assert len(notices) == 1 and notices[0].message == "Experimental Altium write kinds: altium_harness"
    assert built.evidence.level is Level.INFERRED


def test_discovery_does_not_read_checkout_evidence(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    read_text = Path.read_text

    def guarded(path: Path, *args: Any, **kwargs: Any) -> str:
        assert not path.resolve().is_relative_to(ROOT / "docs")
        assert not path.resolve().is_relative_to(ROOT / "tests")
        return read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded)
    assert main(["capabilities", "--json", "--no-tools"]) == 0
    assert json.loads(capsys.readouterr().out)["result"]["matrix"]


def test_mixed_matrix_names_only_written_experimental_kind_and_keeps_inputs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _promoted_matrix(monkeypatch, "altium_harness")
    evidence, pending = _written_claims(
        {"Sheet.SchDoc": b"", "Signals.Harness": b"", ".fenolite/design.json": b""},
        "binary",
        [Evidence(Level.INFERRED, hypotheses=("H-A-DSL-FOOTPRINT",))],
    )
    assert pending == ("altium_harness",)
    assert evidence.level is Level.INFERRED and "H-A-DSL-FOOTPRINT" in evidence.hypotheses
    assert "H-A-PCB-ECO" not in evidence.hypotheses
