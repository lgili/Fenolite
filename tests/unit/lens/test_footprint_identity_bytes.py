# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Ordinary build bytes:96d687d1 baseline, reviewed c0344 identity-cache-only refresh.

The complete maps prove only .pro and its paired manifest changed; every physical
file and all Altium files retain their immutable baseline bytes.

Change c0406 makes wired the default schematic layout: the four KiCad maps were
recorded again on 2026-11-05, and only the schematic, ``lib/fenolite.kicad_sym``
(Fenolite's power symbols beside the flag) and ``build.json`` differ from the
96d687d1 maps; the Altium maps are unchanged.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from _schema_pin import legacy_meta_bytes

from fenolite.api import run

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize(
    "example,target,expected",
    (
        ("blink_2layer", 9, "cafb646d96fd3ecb7e8b75225294cc3ef86863d6b07fcb97c05feb1d902d5f22"),
        ("blink_2layer", 10, "cb7067beb8c6008da95c19c7cc73d729074cd485e701628a337cc701891a3f50"),
        ("blink_routed", 9, "e2e385b2cb73ff639fb9284d82afd5f7962602625850c26db483408a69f8c01a"),
        ("blink_routed", 10, "c78de63e2cbe51e0bedb244b5ea9940d86ae5941998209b5dfe6a8d7574c2de9"),
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
        p.relative_to(out).as_posix(): hashlib.sha256(
            legacy_meta_bytes(p.read_bytes())
            if p.relative_to(out).as_posix() == ".fenolite/meta.json"
            else p.read_bytes()
        ).hexdigest()
        for p in out.rglob("*")
        if p.is_file()
    }
    assert (
        hashlib.sha256(json.dumps(table, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
        == expected
    )
