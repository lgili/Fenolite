# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The evidence label grammar and the verify package's imports (capability verification-evidence)."""

from __future__ import annotations

import ast
import subprocess
import sys
from pathlib import Path

import pytest

from fenolite.core.evidence import Level
from fenolite.verify import ID_PATTERN, parse_level

VERIFY = Path(__file__).resolve().parents[3] / "src" / "fenolite" / "verify"


@pytest.mark.parametrize(
    ("text", "level"),
    [
        ("KICAD-VERIFIED (9.0.x, 10.0.x)", Level.KICAD_VERIFIED),
        ("KICAD-VERIFIED (10.0.x)", Level.KICAD_VERIFIED),
        (
            "ALTIUM-VERIFIED(author-report; AD 24.x; 2026-09; no artefact)",
            Level.ALTIUM_VERIFIED_AUTHOR_REPORT,
        ),
        ("ALTIUM-VERIFIED(kit)", Level.ALTIUM_VERIFIED_KIT),
        ("ALTIUM-VERIFIED(kit; 0123abcd)", Level.ALTIUM_VERIFIED_KIT),
        ("ALTIUM-VERIFIED(kit) (24.x)", Level.ALTIUM_VERIFIED_KIT),
        ("ORACLE-VERIFIED(freerouting) (2.4.1)", Level.ORACLE_VERIFIED),
        ("ORACLE-VERIFIED (kicad-import)", Level.ORACLE_VERIFIED),
        ("CORPUS-VERIFIED (two origins)", Level.CORPUS_VERIFIED),
        ("INFERRED (9.0 side)", Level.INFERRED),
    ],
)
def test_qualified_labels(text: str, level: Level) -> None:
    assert parse_level(text) is level


def test_every_level_value_parses() -> None:
    for level in Level:
        assert parse_level(level.value) is level


@pytest.mark.parametrize(
    "text",
    [
        "ALTIUM-VERIFIED",
        "ALTIUM-VERIFIED(report)",
        "kicad-verified",
        "INFERRED(x)",
        "KICAD-VERIFIEDX",
        "",
        "KICAD-VERIFIED ()",
        "KICAD-VERIFIED (a (b))",
        "ORACLE-VERIFIED( )",
    ],
)
def test_malformed_labels_are_rejected(text: str) -> None:
    with pytest.raises(ValueError) as info:
        parse_level(text)
    assert repr(text) in str(info.value)


def test_id_pattern() -> None:
    assert ID_PATTERN.fullmatch("H-K-SEXPR-NUM-WRITE-2")
    assert not ID_PATTERN.fullmatch("H-X-UNIT") and not ID_PATTERN.fullmatch("H-K-unit")
    assert [m.group() for m in ID_PATTERN.finditer("see H-K-UNIT, XH-K-UNIT and H-G-ANGLE.")] == [
        "H-K-UNIT",
        "H-G-ANGLE",
    ]


def test_import_stays_light() -> None:
    code = (
        "import sys, fenolite.verify; print(sorted(m for m in sys.modules if m.startswith("
        "('fenolite.model', 'fenolite.geometry', 'fenolite.backends'))))"
    )
    out = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True).stdout
    assert out.strip() == "[]"


def _imports(path: Path) -> list[str]:
    names: list[str] = []
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append("." * node.level + (node.module or ""))
    return names


def test_only_the_standard_library_and_core_are_imported() -> None:
    problems: list[str] = []
    for path in sorted(VERIFY.rglob("*.py")):
        for name in _imports(path):
            top = name.split(".")[0]
            allowed = (
                name == "__future__"
                or top in sys.stdlib_module_names
                or name == "fenolite.core"
                or name.startswith(("fenolite.core.", "fenolite.verify"))
            )
            if not allowed:
                problems.append(f"{path.name}: {name}")
    assert not problems, problems
