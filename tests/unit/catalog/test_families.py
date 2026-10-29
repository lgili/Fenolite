# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The shipped parametric families (change c0254; fenolite-component-catalog, "Parametric families in the
shipped catalog", "Catalog data version")."""

from __future__ import annotations

import re
import tomllib
from importlib import resources
from pathlib import Path

import pytest

from fenolite.catalog import CATALOG_VERSION, ENTRIES
from fenolite.pick.rows import ATTRIBUTE_UNITS, digest, family_text, shipped_families

ROOT = Path(__file__).resolve().parents[3]
SOURCES = ROOT / "docs" / "evidence" / "sources.md"


def run(monkeypatch: pytest.MonkeyPatch, cwd: Path, *args: str) -> tuple[int, dict, dict, str]:  # type: ignore[type-arg]
    import io
    import json

    import fenolite.cli.main as cli_main

    monkeypatch.chdir(cwd)
    out, err = io.StringIO(), io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    monkeypatch.setattr("sys.stderr", err)
    code = cli_main.main([*args, "--json"])
    return code, json.loads(out.getvalue() or "{}"), json.loads(err.getvalue() or "{}"), out.getvalue()


def _registered() -> set[str]:
    return set(re.findall(r"^\| (S-\d{4,}) \|", SOURCES.read_text(encoding="utf-8"), re.MULTILINE))


def test_every_family_number_has_a_source() -> None:
    families = shipped_families()
    registered = _registered()
    shipped = {entry.lib_id for entry in ENTRIES}
    kinds = {
        (f.kind, f.case, f.series if f.kind == "resistor" else str(f.attributes.get("dielectric")))
        for f in families
    }
    for case in ("0402", "0603", "0805", "1206"):
        assert {
            ("resistor", case, "E24"),
            ("resistor", case, "E96"),
            ("capacitor", case, "C0G"),
            ("capacitor", case, "X7R"),
        } <= kinds
    for family in families:
        numeric = {
            "values",
            "tolerance",
            "case",
            *(key for key in family.attributes if key in ATTRIBUTE_UNITS or key == "dielectric"),
        }
        assert numeric <= set(family.sources), (family.id, numeric - set(family.sources))
        for ids in family.sources.values():
            assert set(ids) <= registered, (family.id, ids)
        assert "mpn" not in family.texts and family.evidence in ("INFERRED", "UNKNOWN")
        assert family.symbol in shipped and family.footprint in shipped


def test_the_version_follows_the_data() -> None:
    text = (resources.files("fenolite.catalog") / "families" / "VERSIONS.toml").read_text(encoding="utf-8")
    recorded = tomllib.loads(text)["versions"][CATALOG_VERSION]
    current = {family.id: digest(family_text(family)) for family in shipped_families()}
    changed = sorted(key for key in current if recorded.get(key) != current[key])
    assert not changed, f"the families {', '.join(changed)} changed: give them a new CATALOG_VERSION"
    assert set(recorded) == set(current)


def test_catalog_lists_and_shows_families(monkeypatch: pytest.MonkeyPatch) -> None:
    code, env, err, _ = run(monkeypatch, ROOT, "catalog", "list", "--kind", "family")
    assert code == 0, err
    assert env["result"]["count"] == 16 and {row["kind"] for row in env["result"]["entries"]} == {"family"}
    code, env, err, _ = run(monkeypatch, ROOT, "catalog", "show", "Fenolite:R_0603_E96_1pct")
    assert code == 0, err
    assert (
        env["result"]["catalog"] == f"fenolite-catalog {CATALOG_VERSION}"
        and env["result"]["sources"]["power"]
    )
