# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Ordinary build bytes:96d687d1 baseline, reviewed c0344 identity-cache-only refresh.

The complete maps prove only .pro and its paired manifest changed; every physical
file and all Altium files retain their immutable baseline bytes.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from fenolite.api import run

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "example,target,expected",
    (
        ("blink_2layer", 9, "a9ebec6035e6be6c530e2754482225dac71eea11ea7c1b3a96b9e971d87df413"),
        ("blink_2layer", 10, "cf761b2bd534acd7cd819a29c53abed470ca50ee99fcef289d55d1dfa3ae94f0"),
        ("blink_routed", 9, "2e7d755f1107dd887cc1d300c2ef011d5eafbadc29a0e7ab7a14aef9a4ba2f85"),
        ("blink_routed", 10, "1e9d7244200e79eb87e7ebba0210da7cb45b840a524bcb4883a7c1380f280343"),
        ("blink_2layer", "altium", "3a1e39ac04eb48f4cbad82d49570ba3b02ee769e2d7f02655d79483df879373f"),
        ("blink_routed", "altium", "3e0554d61440dc1573dee7bbc505c93710b3223b08ac89775193a311acef20f1"),
    ),
)
def test_optional_definition_changes_no_default_file(
    example: str, target: int | str, expected: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    out = tmp_path / "out"
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kc"))
    if target == "altium":
        pytest.importorskip("pyclipper")  # the immutable baseline used the geo extra/default computed pour
        target_args = ("--target", "altium")
    else:
        target_args = ("--kicad-version", str(target))
    reply = run(
        "build",
        str(ROOT / "examples" / example / "design.py"),
        "--out",
        str(out),
        "--confirm",
        "--seed",
        "1",
        *target_args,
        timestamp="2026-01-01T00:00:00Z",
    )
    assert reply.exit_code == 0, reply.error
    table = {
        p.relative_to(out).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in out.rglob("*")
        if p.is_file()
    }
    assert (
        hashlib.sha256(json.dumps(table, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        == expected
    )
