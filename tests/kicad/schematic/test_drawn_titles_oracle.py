# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored drawing-sheet title control through the installed KiCad process (c0339, S-1206)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import _kicad
import pytest
from _drawn_titles import DATE, dated_parent_blank_child
from _fidelity import ALL_LEVELS, roundtrip, snapshot

pytestmark = pytest.mark.needs_kicad


def test_native_parent_date_and_blank_child_remain_visible_and_blank(tmp_path: Path) -> None:
    version = _kicad.supported_version()
    original = dated_parent_blank_child(tmp_path / "original", int(version.split(".")[0]))
    before = snapshot(original)
    output = tmp_path / "roundtrip"
    reply = roundtrip(original, output)
    assert reply.exit_code == 0, (reply.error, reply.result.get("differences"))
    assert tuple(row["level"] for row in reply.result["levels"]) == ALL_LEVELS
    assert all(row["status"] == "equal" for row in reply.result["levels"])
    assert reply.result["accepted"] == reply.result["differences"] == []
    receipts = []
    for side, source in (("original", original), ("generated", output / "built")):
        folder = tmp_path / f"native-{side}"
        project = folder / "input"
        shutil.copytree(source, project)
        inputs = snapshot(project)
        argv = [
            _kicad.cli(),
            "sch",
            "export",
            "svg",
            "--black-and-white",
            "-o",
            str(folder / "svg"),
            str(project / "drawn_full.kicad_sch"),
        ]
        exported = subprocess.run(
            argv,
            env=_kicad.oracle_env(folder / "config"),
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
        assert exported.returncode == 0, (argv, exported.stdout, exported.stderr)
        after = snapshot(project)
        assert {name: after[name] for name in inputs} == inputs
        created = {name: digest for name, digest in after.items() if name not in inputs}
        assert set(created) <= {"drawn_full.kicad_prl"}
        svgs = sorted((folder / "svg").glob("*.svg"))
        assert len(svgs) == 2, [path.name for path in svgs]
        pages = {}
        for svg in svgs:
            descs = [
                node.text or ""
                for node in ET.fromstring(svg.read_bytes()).iter()
                if node.tag.rsplit("}", 1)[-1] in {"desc", "text"}
            ]
            dated = any(DATE in text for text in descs)
            assert dated == (svg.stem == "drawn_full"), (svg.name, descs)
            pages[svg.name] = {"sha256": hashlib.sha256(svg.read_bytes()).hexdigest(), "date_visible": dated}
        receipts.append(
            {
                "side": side,
                "version": version,
                "argv": argv,
                "exit": exported.returncode,
                "inputs": inputs,
                "created": created,
                "pages": pages,
            }
        )
    assert snapshot(original) == before
    (tmp_path / "title-receipt.json").write_text(json.dumps(receipts, indent=2, sort_keys=True) + "\n")
