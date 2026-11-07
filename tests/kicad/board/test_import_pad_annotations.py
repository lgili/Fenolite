# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Actual native load/save of independently authored physical annotations (c0355)."""

from __future__ import annotations

import hashlib
import json
import runpy
from collections import Counter
from pathlib import Path

import _kicad
import pytest

from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.sexpr import dumps, parse_bytes

pytestmark = pytest.mark.needs_kicad


def _annotations(data: bytes) -> Counter[tuple[str, str, str, tuple[str, ...]]]:
    rows = []
    for fp in parse_bytes(data).nodes("footprint"):
        ref = next(p.atoms()[1].value for p in fp.nodes("property") if p.atoms()[0].value == "Reference")
        for pad in fp.nodes("pad"):
            uid = pad.find("uuid")
            assert uid is not None
            rows.append(
                (
                    ref,
                    uid.atoms()[0].value,
                    pad.atoms()[0].value,
                    tuple(
                        dumps(c, style="compact") for c in pad.nodes() if c.name in {"pinfunction", "pintype"}
                    ),
                )
            )
    return Counter(rows)


def test_authored_metadata_native_load_and_exact_save(tmp_path: Path) -> None:
    helper = Path(__file__).resolve().parents[2] / "unit/importer/test_pad_annotations.py"
    text = runpy.run_path(str(helper))["authored"]()
    data = text.encode()
    source = tmp_path / "authored.kicad_pcb"
    source.write_bytes(data)
    cli = KicadCli(Path(_kicad.cli()))
    version = cli.version()
    drc = cli.drc(source)
    for name, output in drc.run.outputs.items():
        if name.endswith(".json"):
            (tmp_path / Path(name).name).write_bytes(output)
    assert drc.run.ok and drc.report is not None
    receipt = {
        "native_version": version,
        "native_load_exit": drc.run.returncode,
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "physical_pads": sum(_annotations(data).values()),
        "all_drc_retained": True,
    }
    if version.startswith("10."):
        saved = cli.upgrade_board(source)
        (tmp_path / "native-saved.kicad_pcb").write_bytes(saved)
        expected = _annotations(data)
        pad = parse_bytes(data).nodes("footprint")[0].nodes("pad")[0]
        uid = pad.find("uuid")
        assert uid is not None
        authored_empty = (
            "R1",
            uid.atoms()[0].value,
            "1",
            ('(pinfunction "")', '(pintype "AUTH_UNKNOWN+no_connect")'),
        )
        assert expected[authored_empty] == 1
        del expected[authored_empty]
        # Independent observed native10 serialization: only this authored empty function is omitted.
        expected[("R1", uid.atoms()[0].value, "1", ('(pintype "AUTH_UNKNOWN+no_connect")',))] += 1
        assert _annotations(saved) == expected
        receipt["saved_sha256"] = hashlib.sha256(saved).hexdigest()
        receipt["exact_all_other_annotation_presence_values"] = True
        receipt["native_empty_function_omitted"] = 1
    assert source.read_bytes() == data
    (tmp_path / "native-annotation-proof.json").write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n"
    )
