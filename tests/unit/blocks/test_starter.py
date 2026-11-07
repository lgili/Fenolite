# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The installed starter catalog is complete and its required inputs stay explicit."""

import re
from pathlib import Path

from fenolite import api
from fenolite.cli.blocksrc import duplicate_issues, find_blocks
from fenolite.dsl.record import record_data

NAMES = {"voltage_divider", "rc_lowpass", "led_indicator", "i2c_pullups", "protected_input"}


def test_five_listed_once_with_complete_records():
    entries = find_blocks()
    assert {e.id for e in entries} == {f"Fenolite:{name}" for name in NAMES}
    assert not duplicate_issues(entries)
    reply = api.run("blocks", "list")
    assert reply.exit_code == 0
    for entry in entries:
        record = entry.record
        assert record.header.version == "1.0.0" and record.header.licence == "Apache-2.0"
        assert record.header.evidence == "INFERRED"
        assert record.ports and all(port.doc for port in record.ports)
        assert record.layout == f"layouts/{entry.id.split(':')[1]}.toml"
        reply = api.run("blocks", "show", entry.id)
        assert reply.exit_code == 0
        assert all(reply.result["block"][kind] for kind in ("usage", "tests", "golden"))


def test_protection_required_inputs_typed():
    entry = next(e for e in find_blocks() if e.id.endswith(":protected_input"))
    params = {p["name"]: p for p in record_data(entry.record)["params"]}
    assert params["protection"]["type"] == "str"
    for key in ("protection", "clamp", "abs_max"):
        assert params[key]["required"] and params[key]["default"] is None
    assert params["clamp"]["unit"] == params["abs_max"]["unit"] == "volt"
    assert entry.record.elaboration == {"reason": "required parameter abs_max"}


def test_sources_registered():
    root = Path(__file__).resolve().parents[3]
    known = set(
        re.findall(r"^\| (S-\d+) \|", (root / "docs/evidence/sources.md").read_text(encoding="utf-8"), re.M)
    )
    for entry in find_blocks():
        assert entry.record.header.sources
        assert set(entry.record.header.sources) <= known
    i2c = next(e for e in find_blocks() if e.id.endswith(":i2c_pullups"))
    assert "S-0941" in i2c.record.header.sources


def test_authored_asset_manifest_covers_shipped_fixtures():
    import tomllib

    from fenolite.blocks.tests._support import ROOT

    data = tomllib.loads((ROOT / "MANIFEST.toml").read_text(encoding="utf-8"))
    wanted = {
        p.relative_to(ROOT).as_posix()
        for folder in ("usage", "devices", "layouts", "golden")
        for p in (ROOT / folder).rglob("*")
        if p.is_file() and p.suffix in (".py", ".toml", ".json")
    }
    assert {r["path"] for r in data["file"]} == wanted
    assert all(r["origin"] == "authored" for r in data["file"])
