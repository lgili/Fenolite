# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Golden files of the Altium sample and the protocol page that names them (capability altium-build,
"Altium sample project" and scenario "Protocol names the sample bytes" of "Altium author reports"; change
c0032). These are the ASCII build (``form="ascii"``); the binary sample is checked by
``test_altium_binary_golden.py`` (change c0033).

``FENOLITE_GOLDEN_WRITE=1`` rewrites the four files under ``tests/data/altium/sample/`` instead of comparing
them; the SHA-256 values of ``docs/evidence/altium-schematic.md`` are then updated by hand.
"""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from functools import cache
from pathlib import Path

import pytest
from _altium import SAMPLE_NETS, sample

from fenolite.backends.altium.project import component_path, unique_id
from fenolite.dsl import to_model
from fenolite.lens.altium import build_altium

ROOT = Path(__file__).resolve().parents[3]
GOLDEN = ROOT / "tests" / "data" / "altium" / "sample"
PROTOCOL = ROOT / "docs" / "evidence" / "altium-schematic.md"
NAMES = (
    "altium_sample.PrjPcb",
    "altium_sample.SchDoc",
    "variants/altium_sample_lf.SchDoc",
    "variants/altium_sample_nouid.SchDoc",
)
WRITE = os.environ.get("FENOLITE_GOLDEN_WRITE") == "1"


def lf_variant(schdoc: bytes) -> bytes:
    """Every CR LF replaced by LF."""
    return schdoc.replace(b"\r\n", b"\n")


def nouid_variant(schdoc: bytes) -> bytes:
    """Every ``|UNIQUEID=…`` field removed, nothing else changed."""
    return re.sub(rb"\|UNIQUEID=[^|\r\n]*", b"", schdoc)


@cache
def fresh() -> dict[str, bytes]:
    design = sample()
    files = build_altium(to_model(design), name=design.name, form="ascii").files
    schdoc = files["altium_sample.SchDoc"]
    return {
        "altium_sample.PrjPcb": files["altium_sample.PrjPcb"],
        "altium_sample.SchDoc": schdoc,
        "variants/altium_sample_lf.SchDoc": lf_variant(schdoc),
        "variants/altium_sample_nouid.SchDoc": nouid_variant(schdoc),
    }


def test_golden_files_and_variants() -> None:
    files = fresh()
    assert tuple(files) == NAMES
    if WRITE:
        for rel, data in files.items():
            (GOLDEN / rel).parent.mkdir(parents=True, exist_ok=True)
            (GOLDEN / rel).write_bytes(data)
        pytest.skip("golden files rewritten (FENOLITE_GOLDEN_WRITE=1)")
    for rel, data in files.items():
        assert (GOLDEN / rel).read_bytes() == data, f"{rel} differs from a fresh build"


def test_variants() -> None:
    files = fresh()
    schdoc, lf, nouid = files["altium_sample.SchDoc"], files[NAMES[2]], files[NAMES[3]]
    assert b"\r" not in lf and lf.count(b"\n") == schdoc.count(b"\r\n") == 123
    assert b"UNIQUEID" not in nouid and schdoc.count(b"|UNIQUEID=") == 8
    assert nouid.count(b"\r\n") == 123 and nouid.split(b"\r\n")[0] == schdoc.split(b"\r\n")[0]
    stripped = [re.sub(rb"\|UNIQUEID=[A-Y]{8}", b"", line) for line in schdoc.split(b"\r\n")]
    assert nouid.split(b"\r\n") == stripped


def test_git_keeps_the_line_ends() -> None:
    if not (ROOT / ".git").exists():
        pytest.skip("not a git checkout")
    attributes = (ROOT / ".gitattributes").read_text(encoding="utf-8").split()
    assert attributes[attributes.index("*.SchDoc") + 1] == "-text"
    assert attributes[attributes.index("*.PrjPcb") + 1] == "-text"
    proc = subprocess.run(
        [
            "git",
            "check-attr",
            "text",
            "--",
            f"tests/data/altium/sample/{NAMES[1]}",
            f"tests/data/altium/sample/{NAMES[0]}",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0 and proc.stdout.count(": text: unset") == 2, proc.stdout


# --- the protocol page (docs/evidence/altium-schematic.md) -------------------------------------------


def _cells(line: str) -> list[str]:
    return [cell.strip().strip("`") for cell in line.strip().strip("|").split("|")]


def _table(text: str, header: str) -> list[list[str]]:
    lines = text.splitlines()
    start = lines.index(header)
    rows: list[list[str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        rows.append(_cells(line))
    return rows


def test_protocol_names_the_sample_bytes() -> None:
    text = PROTOCOL.read_text(encoding="utf-8")
    digests = {cells[0]: cells[1] for cells in _table(text, "| file | SHA-256 |")}
    assert sorted(digests) == sorted(f"tests/data/altium/sample/{name}" for name in NAMES)
    for path, digest in digests.items():
        assert re.fullmatch(r"[0-9a-f]{64}", digest), path
        assert hashlib.sha256((ROOT / path).read_bytes()).hexdigest() == digest, path


def test_protocol_net_table() -> None:
    text = PROTOCOL.read_text(encoding="utf-8")
    nets: dict[str, set[tuple[str, str]]] = {}
    for net, pins in _table(text, "| net | pins as (ref, pin) |"):
        nets[net] = {(ref, pin) for ref, pin in re.findall(r"\((\w+), (\w+)\)", pins)}
    design = sample()
    model = to_model(design)
    refs = {c.id: c.ref for c in model.circuit.components}
    expected = {n.name: {(refs[m.component_id], m.pin) for m in n.members} for n in model.circuit.nets}
    assert nets == expected == SAMPLE_NETS


def test_protocol_component_table() -> None:
    text = PROTOCOL.read_text(encoding="utf-8")
    rows = _table(text, "| ref | path | Design Item ID | Source | footprint | comment | unique id |")
    model = to_model(sample())
    expected: list[list[str]] = []
    for component in sorted(model.circuit.components, key=component_path):
        library, symbol = component.lib_symbol_ref.split(":", 1)
        footprint = component.lib_footprint_ref.split(":", 1)[1]
        comment = component.value or symbol
        expected.append(
            [
                component.ref,
                component_path(component),
                symbol,
                library,
                footprint,
                comment,
                unique_id(component.id),
            ]
        )
    assert rows == expected
