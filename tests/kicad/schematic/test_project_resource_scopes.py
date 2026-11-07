# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual native worksheet text follows its independent project scope (c0354)."""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path

import _kicad
import pytest
from _project_resources import WORKSHEET, source_with_resource
from _project_template import built, imported, snapshot

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("scope", ["pcbnew", "schematic", "distinct"])
def test_native_project_resource_scope_text_survives_import_build(tmp_path: Path, scope: str) -> None:
    version = _kicad.supported_version()
    target = int(version.split(".")[0])
    original = source_with_resource(tmp_path, target, "pcbnew" if scope == "distinct" else scope)
    if scope == "distinct":
        (original.parent / "frames/schematic.kicad_wks").write_bytes(
            WORKSHEET.replace(b"AUTHORED FRAME", b"AUTHORED SCHEMATIC")
        )
        project = json.loads(original.read_text())
        project["schematic"]["page_layout_descr_file"] = "frames/schematic.kicad_wks"
        original.write_text(json.dumps(project, sort_keys=True, indent=2) + "\n")
    before = snapshot(original.parent)
    code = imported(tmp_path, original, target=target)
    generated = built(tmp_path, code, target=target)
    receipts = []
    for side, source in (("original", original), ("generated", generated)):
        work = tmp_path / f"native-{side}"
        native_input = work / "input"
        shutil.copytree(source.parent, native_input)
        inputs = snapshot(native_input)
        for kind, suffix in (("pcb", ".kicad_pcb"), ("sch", ".kicad_sch")):
            output = work / kind
            output.mkdir()
            native = native_input / source.with_suffix(suffix).name
            argv = [_kicad.cli(), kind, "export", "svg"]
            if kind == "pcb":
                argv += ["-l", "Edge.Cuts", "--mode-single", "-o", str(output / "board.svg")]
            else:
                argv += ["-o", str(output)]
            argv += [str(native)]
            exported = subprocess.run(
                argv,
                env=_kicad.oracle_env(work / "config"),
                capture_output=True,
                text=True,
                timeout=60,
                check=False,
            )
            assert exported.returncode == 0, (argv, exported.stdout, exported.stderr)
            svgs = sorted(output.glob("*.svg"))
            assert {p.name for p in svgs} == (
                {"board.svg"}
                if kind == "pcb"
                else {f"{source.stem}.svg", f"{source.stem}-ch1.svg", f"{source.stem}-ch2.svg"}
            )
            expected = (
                "AUTHORED SCHEMATIC"
                if scope == "distinct" and kind == "sch"
                else "AUTHORED FRAME"
                if scope == "distinct" or scope == {"pcb": "pcbnew", "sch": "schematic"}[kind]
                else None
            )
            pages = {}
            for svg in svgs:
                strings = [
                    "".join(node.itertext())
                    for node in ET.fromstring(svg.read_bytes()).iter()
                    if node.tag.rsplit("}", 1)[-1] in {"text", "desc"}
                ]
                markers = sorted({text for text in strings if text.startswith("AUTHORED")})
                assert markers == ([] if expected is None else [expected]), (scope, kind, svg.name, markers)
                pages[svg.name] = {"sha256": hashlib.sha256(svg.read_bytes()).hexdigest(), "markers": markers}
            after = snapshot(native_input)
            assert {name: after[name] for name in inputs} == inputs
            assert set(after) - set(inputs) <= {source.with_suffix(".kicad_prl").name}
            receipts.append(
                {"side": side, "kind": kind, "version": version, "inputs": inputs, "pages": pages}
            )
    assert snapshot(original.parent) == before
    (tmp_path / "native-resource-scopes.json").write_text(
        json.dumps(receipts, indent=2, sort_keys=True) + "\n"
    )
