# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Committed JSON Schemas equal what tools/gen_schemas.py generates, and the validator works."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import _schema
import pytest

ROOT = Path(__file__).resolve().parents[2]


def _generator() -> ModuleType:
    spec = importlib.util.spec_from_file_location("gen_schemas", ROOT / "tools" / "gen_schemas.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclasses need the module registered
    spec.loader.exec_module(module)
    return module


GEN = _generator()


@pytest.mark.parametrize("target", GEN.TARGETS, ids=lambda t: t.schema_id)
def test_schema_file_matches_generator(target: object) -> None:
    path = ROOT / target.out  # type: ignore[attr-defined]
    assert path.exists(), f"{target.out} missing: run tools/gen_schemas.py"  # type: ignore[attr-defined]
    assert path.read_text(encoding="utf-8") == GEN.render(target), (
        f"{target.out} is stale: run tools/gen_schemas.py"  # type: ignore[attr-defined]
    )


def test_check_mode_passes() -> None:
    assert GEN.main(["--check"]) == 0


def test_validator_rejects_bad_envelopes() -> None:
    schema = _schema.load("fenolite.envelope.v0.json")
    good = {
        "ok": True, "command": "x", "schema": "fenolite.x.v0", "input": None, "result": {},
        "issues": [], "evidence": {"level": "UNVERIFIED", "oracle": None, "hypotheses": []},
        "receipt": None, "elapsed_ms": 0,
    }  # fmt: skip
    assert _schema.validate(good, schema) == []
    assert _schema.validate({**good, "extra": 1}, schema)
    assert _schema.validate({**good, "schema": "x.v0"}, schema)
    assert _schema.validate({**good, "elapsed_ms": -1}, schema)
    bad_issue = {
        "code": "Bad",
        "severity": "error",
        "message": "m",
        "where": "",
        "hint": "",
        "retryable": False,
    }
    assert _schema.validate({**good, "issues": [bad_issue]}, schema)
    assert _schema.validate(
        {**good, "evidence": {"level": "MAYBE", "oracle": None, "hypotheses": []}}, schema
    )
    missing = dict(good)
    del missing["receipt"]
    assert _schema.validate(missing, schema)


def test_error_schema() -> None:
    schema = _schema.load("fenolite.error.v0.json")
    ok = {"code": "FEN-2001", "message": "m", "hint": "h", "retryable": False, "where": ""}
    assert _schema.validate(ok, schema) == []
    assert _schema.validate({**ok, "code": "FEN-8001"}, schema)
