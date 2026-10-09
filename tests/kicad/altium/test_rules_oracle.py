# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rule records of a built PCB document against ``kicad-cli pcb import`` (capability altium-pcb-writer,
"Rule lowering table"; change c0084; ``docs/evidence/altium-pcb.md``, "Rules against KiCad's importer").

The routed sample is built with one rule of every ``exact`` kind and imported with ``kicad-cli pcb import
--format altium``. ``pcb import`` writes the board file only, and KiCad keeps its rule minimums in the
project file, so the import shows one thing: the clearance of the zones it makes, which it takes from a
Clearance rule (here the first of its kind). The other six kinds must load without an error or a
warning; their values are not in the imported board, and this test says nothing about them. ``pcb import``
exists from 10.0 only (S-0166). A pass settles no Altium row.
"""

from __future__ import annotations

import dataclasses
import json
import re
import subprocess
import tempfile
from functools import cache
from pathlib import Path

import pytest
from _altium_copper import NAME, routed_build, routed_model
from _kicad import oracle_env
from _resources import kicad_cli, kicad_cli_major

from fenolite.backends.altium import pcbdoc, rulemap
from fenolite.backends.altium.read.pcb import read_pcbdoc
from fenolite.model.rules import Rule, RuleSet, Selector

pytestmark = pytest.mark.needs_kicad

ALL = Selector("all")
GAP = 170_000
"""The clearance of the design's rule: another value than Fenolite's default, so the import shows which
rule KiCad read."""
RULES = (
    Rule(id="rul_c0084_a", name="gap", kind="clearance", selector_a=ALL, min=GAP),
    Rule(id="rul_c0084_b", name="edge", kind="edge_clearance", selector_a=ALL, min=510_000),
    Rule(
        id="rul_c0084_c",
        name="w",
        kind="track_width",
        selector_a=ALL,
        min=130_000,
        opt=260_000,
        max=2_100_000,
    ),
    Rule(
        id="rul_c0084_d",
        name="via_d",
        kind="via_diameter",
        selector_a=ALL,
        min=530_000,
        opt=610_000,
        max=810_000,
    ),
    Rule(
        id="rul_c0084_e",
        name="via_h",
        kind="via_drill",
        selector_a=ALL,
        min=270_000,
        opt=310_000,
        max=410_000,
    ),
    Rule(id="rul_c0084_f", name="holes", kind="hole_size", selector_a=ALL, min=290_000, max=6_100_000),
    Rule(id="rul_c0084_g", name="apart", kind="hole_to_hole", selector_a=ALL, min=230_000),
    Rule(id="rul_c0084_h", name="ring", kind="annular_width", selector_a=ALL, min=110_000),
)
ALLOWED_WARNING = re.compile(r"Layer 'Internal Plane \d+' could not be mapped and will be skipped\.")
ZONE_CLEARANCE = re.compile(r"\(clearance ([0-9.]+)\)")


@dataclasses.dataclass(frozen=True)
class Imported:
    code: int
    stdout: str
    report: dict[str, object]
    text: str
    kinds: tuple[str, ...]


@cache
def imported(with_rules: bool) -> Imported:
    cli = kicad_cli()
    assert cli is not None
    if kicad_cli_major() == 9:
        pytest.skip("no `pcb import` before 10.0")
    model = routed_model()
    if with_rules:
        model = dataclasses.replace(model, rules=RuleSet(id="rst_c0084", rules=RULES))
    with tempfile.TemporaryDirectory() as folder:
        root = Path(folder)
        output = routed_build(root / "build", model)
        assert not [found for found in output.issues if found.severity == "error"]
        data = output.files[f"{NAME}.PcbDoc"]
        kinds = tuple(rule.rule_kind or "" for rule in read_pcbdoc(data, file=f"{NAME}.PcbDoc").rules)
        source, target, report = root / f"{NAME}.PcbDoc", root / "b.kicad_pcb", root / "r.json"
        source.write_bytes(data)
        env = oracle_env(root / "config")
        proc = subprocess.run(
            [cli, "pcb", "import", "--format", "altium", "--report-format", "json",
             "--report-file", str(report), "-o", str(target), str(source)],
            capture_output=True, text=True, timeout=300, env=env, check=False,
        )  # fmt: skip
        assert target.is_file(), proc.stdout + proc.stderr
        found = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
        written = sorted(p.name for p in root.iterdir() if p.is_file())
        assert written == ["b.kicad_pcb", "r.json", f"{NAME}.PcbDoc"]  # no project file: no rule minimums
        return Imported(
            proc.returncode, proc.stdout + proc.stderr, found, target.read_text(encoding="utf-8"), kinds
        )


def test_every_lowered_kind_is_written_and_loads() -> None:
    """KiCad's importer loads a document that holds the seven kinds of the table, with no error and no
    warning but the planes outside the stack."""
    result = imported(True)
    assert set(result.kinds) == set(rulemap.KIND_ORDER)
    assert result.code == 0, result.stdout
    assert result.report.get("errors") == []
    lines = result.stdout.splitlines()
    assert not [line for line in lines if line.startswith("Error:") or "Error during" in line]
    warnings = [line for line in lines if "Warning:" in line]
    assert all(ALLOWED_WARNING.search(line) for line in warnings), warnings
    assert result.report.get("warnings") in ([], None)


def test_the_clearance_rule_is_read_into_the_zones() -> None:
    """The one kind the import shows: each zone gets the clearance of a Clearance rule. With the design's
    rule, which is then the first of its kind, that is its value; without it, Fenolite's 0.2 mm, which both
    the class rule and the default hold."""
    assert GAP != pcbdoc.DEFAULT_CLEARANCE
    with_rule = [float(value) for value in ZONE_CLEARANCE.findall(imported(True).text)]
    without = [float(value) for value in ZONE_CLEARANCE.findall(imported(False).text)]
    assert with_rule and len(with_rule) == len(without)
    assert all(abs(value * 1_000_000 - GAP) <= 10 for value in with_rule), with_rule
    assert all(abs(value * 1_000_000 - pcbdoc.DEFAULT_CLEARANCE) <= 10 for value in without), without


def test_the_other_kinds_are_not_in_the_imported_board() -> None:
    """What the oracle cannot show: no value of the six other kinds is a design-rule value of the board
    file (KiCad keeps those in the project file, which ``pcb import`` does not write)."""
    text = imported(True).text
    assert "(rule " not in text and "net_class" not in text and "min_track_width" not in text
    assert "edge_clearance" not in text and "hole_to_hole" not in text and "annular" not in text
