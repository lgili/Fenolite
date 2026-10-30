# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``fenolite library gallery`` (capability fenolite-library, "Gallery with attribution"; change c0279)."""

from __future__ import annotations

import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path
from typing import Any

import pytest

from fenolite.cli import main as cli_main

BOARD = "boards/cern-ohl-s/demo-src/blink"


def _cli(monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str) -> tuple[int, dict[str, Any]]:
    monkeypatch.chdir(cwd)
    out = io.StringIO()
    with redirect_stdout(out), redirect_stderr(io.StringIO()):
        code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue() or "{}")


def _site(monkeypatch: pytest.MonkeyPatch, demo: Path) -> dict[str, Any]:
    code, _ = _cli(
        monkeypatch,
        demo.parent,
        "library",
        "release",
        str(demo),
        "--version",
        "1.0.0",
        "--out",
        "dist",
        "--confirm",
    )
    assert code == 0
    code, envelope = _cli(
        monkeypatch,
        demo.parent,
        "library",
        "gallery",
        str(demo),
        "--release",
        "dist",
        "--out",
        "site",
        "--confirm",
    )
    assert code == 0, envelope
    return envelope


def test_card_attribution(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    """Scenario "Card attribution"."""
    code, _ = _cli(
        monkeypatch,
        demo.parent,
        "library",
        "release",
        str(demo),
        "--version",
        "1.0.0",
        "--out",
        "dist",
        "--confirm",
    )
    assert code == 0
    code, envelope = _cli(
        monkeypatch,
        demo.parent,
        "library",
        "gallery",
        str(demo),
        "--release",
        "dist",
        "--out",
        "site",
        "--dry-run",
    )
    assert code == 0 and not (demo.parent / "site").exists()
    assert "site/boards/demo-src/blink/index.html" in [row["path"] for row in envelope["result"]["plan"]]
    envelope = _site(monkeypatch, demo)
    page = (demo.parent / "site/boards/demo-src/blink/index.html").read_text(encoding="utf-8")
    assert (
        "Converted from the open-source design Blink demo board by Demo Board Authors "
        f"(https://example.org/demo-src/tree/{'1' * 40}/blink), licence CERN-OHL-S-2.0. "
        "Rendered by Fenolite"
    ) in page
    assert "Not endorsed by the authors." in page and "pass-with-accepted" in page
    assert (
        "fenolite get board demo-src/blink --release 1.0.0 --accept-licence CERN-OHL-S-2.0 --dry-run" in page
    )
    assert 'src="top.svg"' in page and "tree/v1.0.0/boards/cern-ohl-s/demo-src/blink" in page
    device = (demo.parent / "site/devices/Demo/EXB/index.html").read_text(encoding="utf-8")
    assert "Authored for fenolite-library" in device and "Not endorsed" not in device
    assert envelope["result"]["hidden"] == []


def test_restricted_marks_hidden(monkeypatch: pytest.MonkeyPatch, demo: Path) -> None:
    """Scenario "Restricted marks hidden"."""
    path = demo / BOARD / "PROVENANCE.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    record["trademarks"] = {"marks": ["Demo logo"], "restricted": True, "note": "logo on the silkscreen"}
    path.write_text(json.dumps(record, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    envelope = _site(monkeypatch, demo)
    assert not any("blink" in name for name in envelope["result"]["cards"])
    assert envelope["result"]["hidden"] == ["demo-src/blink"]
    assert not (demo.parent / "site/boards").exists()
    assert "blink" not in (demo.parent / "site/index.html").read_text(encoding="utf-8").lower()
