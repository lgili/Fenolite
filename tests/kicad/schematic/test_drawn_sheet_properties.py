# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Original CC0 sheet text controls exported by the actual native CLI (c0329)."""

from __future__ import annotations

import hashlib
import json
import xml.etree.ElementTree as ET
from pathlib import Path

import _drawn
import _probes
import pytest

from fenolite.backends.kicad.sexpr import dumps, parse

pytestmark = pytest.mark.needs_kicad


@pytest.mark.parametrize("source_major", (9, 10))
@pytest.mark.parametrize("text", ("AuthoredCustomSheetProperty", "~"))
def test_native_custom_sheet_text(source_major: int, text: str, tmp_path: Path) -> None:
    cli = _probes.runner()
    version = cli.version()
    if source_major > cli.major():
        pytest.skip("an older native reader cannot prove a newer source format")
    output = _drawn.build("full", source_major)
    assert output.files and not any(issue.severity == "error" for issue in output.issues)
    files = {name: data for name, data in output.files.items() if name.endswith(".kicad_sch")}
    name = _drawn.root_name(output)
    root = parse(files[name].decode())
    sheet = root.nodes("sheet")[0]
    prop = parse(f'(property "AuthoredCustom" "{text}" (at 5 5 0) (effects (font (size 1.27 1.27))))')
    changed = sheet.with_children((*sheet.children, prop))
    files[name] = dumps(
        root.with_children(changed if item is sheet else item for item in root.children)
    ).encode()
    args = [
        "sch",
        "export",
        "svg",
        "--black-and-white",
        "--exclude-drawing-sheet",
        "-o",
        "svg/",
        name,
    ]
    result = cli.run(args, files=files, folders=("svg",))

    def hashes(mapping: dict[str, bytes]) -> dict[str, str]:
        return {key: hashlib.sha256(value).hexdigest() for key, value in sorted(mapping.items())}

    receipt = {
        "native_version": version,
        "source_major": source_major,
        "args": args,
        "input_sha256": hashes(files),
        "output_sha256": hashes(result.outputs),
        "outcome": result.outcome,
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }
    (tmp_path / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n")
    assert result.ok, receipt
    assert not set(files).intersection(result.outputs), "native export changed a source"
    svg = {key: data for key, data in result.outputs.items() if key.endswith(".svg")}
    assert svg, receipt
    for key, data in svg.items():
        (tmp_path / Path(key).name).write_bytes(data)
    descriptions = [
        item.text
        for data in svg.values()
        for item in ET.fromstring(data).iter()
        if item.tag.rsplit("}", 1)[-1] == "desc"
    ]
    expected = 0 if text == "~" and source_major == 9 and cli.major() >= 10 else 1
    assert descriptions.count(text) == expected, (receipt, descriptions)
