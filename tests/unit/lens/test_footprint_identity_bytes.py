# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Complete ordinary build bytes from immutable 96d687d1 before c0318's optional field."""

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
        ("blink_2layer", 9, "9f5f2dd1fed3870bd5def864192e44bbb0cab4ecdccdd0939438460ff0590bab"),
        ("blink_2layer", 10, "7cabb64df1465cbd606bad0afadaf6030b33efbaafb947abc10959be46accaf0"),
        ("blink_routed", 9, "7d1b7f91e066e55cc088e39e8de1dc8ef00a856f7d2bd4d085c0af3624cedb69"),
        ("blink_routed", 10, "c46c8f8861592f811a337be699065b06ca1e99947d490d56bfbccf2a5ab704fe"),
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
