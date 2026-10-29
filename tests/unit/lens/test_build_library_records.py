# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Library records used by a build (change c0259; capability library-records, "Deprecated records in a
build" and "Review entries"). The records are authored for Fenolite as test data."""

from __future__ import annotations

import io
import json
from pathlib import Path

import pytest

import fenolite.cli.main as cli_main
from fenolite.catalog.records import parse_record, record_digest

ROOT = Path(__file__).resolve().parents[3]
LIBRARY = ROOT / "tests" / "data" / "library"
TWO_PIN = (LIBRARY / "pins" / "two_pin.toml").read_text(encoding="utf-8")
TWO_PAD = (LIBRARY / "packages" / "two_pad.toml").read_text(encoding="utf-8")
SCRIPT = """\
from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("records")
design.board(mm(20), mm(10))
x1 = Part("X1", "Proj:Two_Pin", footprint="Proj:Two_Pad", value="1")
design.add(x1)
connect(Net("A"), x1[1])
connect(Net("B"), x1[2])
x1.place(mm(10), mm(5))
"""


@pytest.fixture(autouse=True)
def isolated(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    for name in ("KICAD10_FOOTPRINT_DIR", "KICAD10_SYMBOL_DIR", "KICAD9_FOOTPRINT_DIR", "KICAD9_SYMBOL_DIR"):
        monkeypatch.delenv(name, raising=False)


def build(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, package: str
) -> tuple[int, list[dict[str, str]], str]:
    folder = tmp_path / "proj"
    (folder / "devices").mkdir(parents=True)
    (folder / "devices" / "two_pin.toml").write_text(TWO_PIN, encoding="utf-8")
    (folder / "devices" / "two_pad.toml").write_text(package, encoding="utf-8")
    (folder / "design.py").write_text(SCRIPT, encoding="utf-8")
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main(
        ["build", str(folder / "design.py"), "--out", str(tmp_path / "out"), "--confirm", "--json"]
    )
    envelope = json.loads(out.getvalue()) if out.getvalue() else {}
    return code, envelope.get("issues", []), err.getvalue()


def test_deprecated_footprint_used(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    deprecated = TWO_PAD.replace(
        'generator = "explicit"',
        'deprecated = { by = "Proj:B", since = "1.0.1", reason = "pad 3 added" }\ngenerator = "explicit"',
    )
    code, issues, err = build(monkeypatch, tmp_path, deprecated)
    assert code == 0, err
    found = [issue for issue in issues if issue["code"] == "library.deprecated"]
    assert len(found) == 1 and found[0]["severity"] == "warning" and "Proj:B" in found[0]["message"]
    assert (tmp_path / "out" / "records.kicad_pcb").is_file()


def test_stale_review(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    old = "0" * 64
    review = (
        f'\n[[reviewed_by]]\nwho = "maintainer"\ndate = "2026-10-29"\nversion = "1.0.0"\ndigest = "{old}"\n'
        'evidence = "UNVERIFIED"\n'
    )
    assert record_digest(parse_record(TWO_PAD + review)) != old
    code, issues, err = build(monkeypatch, tmp_path, TWO_PAD + review)
    assert code == 0, err
    found = [issue for issue in issues if issue["code"] == "library.review-stale"]
    assert len(found) == 1 and found[0]["severity"] == "info" and "Proj:Two_Pad" in found[0]["message"]
