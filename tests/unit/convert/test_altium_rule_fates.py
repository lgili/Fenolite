# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The fate of every Altium rule record in a conversion to KiCad (capability design-conversion, "Fate of every
Altium rule record", "Limits the KiCad rule cannot take" and "Shadowed imported rules keep Altium's order";
change c0424).

Every record is authored here in Fenolite's own sample project (``_altium_rules_doc``): one record of each
rule kind of the public PCB documents, with the keys of the public rule file and documents (S-0297, S-1838)
and Fenolite's own values."""

from __future__ import annotations

import re
from pathlib import Path

from _altium_rules_doc import ONE_OF_EACH, rule
from _altium_rules_doc import project as rules_project

from fenolite.api import run
from fenolite.api.commands import Reply
from fenolite.convert import Conversion, convert_project
from fenolite.convert.sources import read_source

RECORDS = ONE_OF_EACH
KEPT_KINDS = {
    "Height", "PlaneClearance", "PlaneConnect", "NetAntennae", "SilkToSolderMaskClearance",
    "SilkToBoardRegionClearance", "MinimumSolderMaskSliver", "RoutingTopology", "RoutingPriority",
    "RoutingCorners", "FanoutControl", "FabricationTestpoint", "FabricationTestPointUsage",
    "AssemblyTestpoint", "AssemblyTestPointUsage", "SupplyNets", "UnRoutedNet", "UnpouredPolygon",
    "LayerPairs", "MatchedLengths",
}  # fmt: skip


def _convert(tmp_path: Path, records: tuple[object, ...] = RECORDS) -> Conversion:
    source = read_source(rules_project(tmp_path / "src", records))  # type: ignore[arg-type]
    return convert_project(source, to="kicad", allow_lossy=True)


def _row(conversion: Conversion):  # noqa: ANN202 - the report row of rules
    (row,) = [row for row in conversion.report.rows if row.kind == "rule"]
    return row


def _dru(conversion: Conversion) -> str:
    return next(data for name, data in conversion.files.items() if name.endswith(".kicad_dru")).decode()


def test_no_rule_record_is_lost(tmp_path: Path) -> None:
    conversion = _convert(tmp_path)
    row = _row(conversion)
    assert row.lost == 0, [r for r in row.reasons if r.outcome == "lost"]
    kept = {r.reason for r in row.reasons if r.outcome == "kept"}
    assert any("disabled" in reason for reason in kept)
    assert all(reason.startswith("kept for an Altium write: ") for reason in kept)
    assert row.kept >= len(KEPT_KINDS) + 3  # the kept kinds and the three disabled records
    assert row.written + row.changed + row.kept == row.source
    assert any(issue.code == "convert.kept" for issue in conversion.issues)
    assert not any(issue.code == "convert.lossy" and "rule" in issue.message for issue in conversion.issues)


def test_kicad_holds_the_rules_it_can_express(tmp_path: Path) -> None:
    dru = _dru(_convert(tmp_path))
    for constraint in (
        "silk_clearance", "courtyard_clearance", "diff_pair_gap", "diff_pair_uncoupled", "hole_to_hole",
        "disallow track", "via_diameter", "hole_size", "edge_clearance", "annular_width", "track_width",
    ):  # fmt: skip
        assert constraint in dru, constraint


def test_the_changed_records_name_their_reason(tmp_path: Path) -> None:
    changed = {r.reason for r in _row(_convert(tmp_path)).reasons if r.outcome == "changed"}
    for words in (
        "Component Clearance", "Differential Pairs Routing", "stacked micro vias", "SolderMaskExpansion",
        "PasteMaskExpansion", "Short Circuit", "Polygon Connect Style",
    ):  # fmt: skip
        assert any(words in reason for reason in changed), words


def test_drill_opt_is_left_out_and_reported(tmp_path: Path) -> None:
    conversion = _convert(tmp_path)
    dru = _dru(conversion)
    (drill,) = [block for block in dru.split("(rule ") if "hole_size" in block and "via" in block.lower()][:1]
    assert "(min 0.254mm)" in drill and "(max 0.4064mm)" in drill and "opt" not in drill
    changed = [r for r in _row(conversion).reasons if r.outcome == "changed"]
    assert any("'opt'" in r.reason and "via_drill" in r.reason for r in changed)
    assert not any("via_drill" in r.reason for r in _row(conversion).reasons if r.outcome == "lost")


STAMP = "2026-11-05T00:00:00Z"
VIAS = (
    rule("RoutingVias", ("VIASTYLE", "Through Hole"), ("MINWIDTH", "20mil"), ("WIDTH", "24mil"),
         ("MAXWIDTH", "30mil"), ("MINHOLEWIDTH", "10mil"), ("HOLEWIDTH", "12mil"), ("MAXHOLEWIDTH", "16mil")),
)  # fmt: skip
SHADOWED = (
    rule("Clearance", ("GAP", "8mil"), ("GENERICCLEARANCE", "8mil"), name="Everything",
         net_scope="DifferentNets"),
    rule("Clearance", ("GAP", "20mil"), ("GENERICCLEARANCE", "20mil"), name="Ground", priority=2,
         scope="InNet('GND')", net_scope="DifferentNets"),
)  # fmt: skip


def _issues(reply: Reply) -> list[dict[str, object]]:
    assert reply.envelope is not None
    return list(reply.envelope.get("issues", ()))


def _imported(tmp_path: Path, records: tuple[object, ...]) -> tuple[str, list[dict[str, object]]]:
    source = rules_project(tmp_path / "src", records)  # type: ignore[arg-type]
    reply = run(
        "import", str(source), "--to", "python", "--out", "out", "--allow-lossy", "--confirm", cwd=tmp_path,
        timestamp=STAMP,
    )  # fmt: skip
    assert reply.exit_code == 0, reply.error
    return (tmp_path / "out" / "design.py").read_text(encoding="utf-8"), _issues(reply)


def test_drill_limits_reach_the_python_import(tmp_path: Path) -> None:
    code, issues = _imported(tmp_path, VIAS)
    call = re.search(r'design\.rules\.rule\(\s*"routingvias_1_2",.*?\n\)\n', code, re.DOTALL)
    assert call is not None, code
    drill = call.group(0)
    assert '"hole_size"' in drill and 'select.item("via")' in drill, drill
    assert 'min=mm("0.254")' in drill and 'max=mm("0.4064")' in drill and "opt=" not in drill, drill
    changed = [str(issue["message"]) for issue in issues if issue["code"] == "convert.changed"]
    assert any("'opt'" in message for message in changed), issues


def test_shadowed_rules_keep_altiums_order(tmp_path: Path) -> None:
    _imported(tmp_path, SHADOWED)
    built = run("build", "design.py", "--out", "built", "--confirm", cwd=tmp_path / "out", timestamp=STAMP)
    assert built.exit_code == 0, built.error
    shadowed = [issue for issue in _issues(built) if issue["code"] == "rules.shadowed"]
    # Altium's priority 1 governs every object, also the GND net that the priority-2 rule names: the
    # notice names the rule Altium applies as the governing one
    assert shadowed and all("governing rule 'everything'" in str(i["message"]) for i in shadowed)
    assert all("ground" in str(i["message"]) for i in shadowed)
