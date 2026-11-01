# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Provenance of an import (capability board-to-code, "Provenance of an import"; change c0275)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from _importcode import PROJECT, TWO_SHEET, imported

URL = "https://example.invalid/b.git"
STATED = (
    "--licence", "CC0-1.0", "--source", URL, "--revision", "abc123",
    "--copyright", "2026 The Test Authors",
)  # fmt: skip


def test_header_and_record(tmp_path: Path) -> None:
    notice = tmp_path / "LICENSE"
    notice.write_bytes(b"Authored for Fenolite: a licence text of the test.\n")
    reply = imported(tmp_path, PROJECT, *STATED, "--licence-file", str(notice), "--confirm")
    assert reply.exit_code == 0, reply.error
    out = tmp_path / "out"
    for script in ("design.py", "copper.py"):
        lines = (out / script).read_text(encoding="utf-8").splitlines()
        assert lines[0] == "# SPDX-License-Identifier: CC0-1.0"
        assert lines[1] == "# SPDX-FileCopyrightText: 2026 The Test Authors"
        assert lines[2].startswith(f"# Converted from {URL}@abc123 by Fenolite ")
        assert lines[2].endswith(" on 2026-10-30;")
        assert lines[3] == "# modified: format conversion to the Fenolite DSL."
    assert (out / "LICENSE").read_bytes() == notice.read_bytes()
    record = json.loads((out / "PROVENANCE.json").read_text(encoding="utf-8"))
    assert record["schema"] == "fenolite.import-provenance.v0"
    assert record["licence"] == "CC0-1.0" and record["notices"] == ["LICENSE"]
    assert record["equivalence"] == {"equivalent": True, "levels": [1, 2, 3, 4, 5]}
    digests = {row["file"]: row["sha256"] for row in record["inputs"]}
    for name in ("two_sheet.kicad_pcb", "two_sheet.kicad_pro", "two_sheet.kicad_sch", "sheets/ch1.kicad_sch"):
        assert digests[name] == hashlib.sha256((TWO_SHEET / name).read_bytes()).hexdigest()
    text = (out / "PROVENANCE.json").read_text(encoding="utf-8")
    assert str(tmp_path) not in text and str(TWO_SHEET) not in text
    assert text == json.dumps(record, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    codes = [i["code"] for i in (reply.envelope or {})["issues"]]
    assert "import.provenance-missing" not in codes and "import.timestamp-missing" not in codes


def test_missing_licence(tmp_path: Path) -> None:
    reply = imported(tmp_path, PROJECT, "--confirm")
    assert reply.exit_code == 0, reply.error
    header = (tmp_path / "out" / "design.py").read_text(encoding="utf-8").splitlines()[0]
    assert header == "# SPDX-License-Identifier: NOASSERTION"
    (found,) = [i for i in (reply.envelope or {})["issues"] if i["code"] == "import.provenance-missing"]
    assert found["severity"] == "warning"
