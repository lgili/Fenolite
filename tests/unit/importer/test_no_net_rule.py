# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""A rule on the items without a net is imported (capability import-python, "Rules on items without a net";
change c0409, B7). The Altium scope ``InNet('No Net')`` maps to ``model.rules.NO_NET`` with no
``rule-unmapped`` (``docs/formats/altium/rule-file.md``, ``H-A-RD-PRJ-SCOPE-NONET``, INFERRED), and the
emitted code writes it as ``select.no_net()``. The rules are authored here."""

from __future__ import annotations

from pathlib import Path

from _importcode import ROOT, STAMP

from fenolite.api import run
from fenolite.backends.altium.read.rules import HEADER_KEYS, Field, map_rules
from fenolite.backends.altium.read.scope import parse_scope
from fenolite.importer.emit.design import _selector  # pyright: ignore[reportPrivateUsage]
from fenolite.model.rules import NO_NET, Selector

EXAMPLE = ROOT / "examples" / "blink_2layer"
RULE = """
from fenolite.dsl import select
design.rules.rule("netless", "clearance", where=select.no_net(), min=mm(0.3))
"""


def _clearance(scope: str) -> list[Field]:
    values = {
        "RULEKIND": "Clearance", "NETSCOPE": "DifferentNets", "LAYERKIND": "SameLayer",
        "SCOPE1EXPRESSION": scope, "SCOPE2EXPRESSION": "All", "NAME": "Netless", "ENABLED": "TRUE",
        "PRIORITY": "1", "COMMENT": "", "UNIQUEID": "C0409B7A", "DEFINEDBYLOGICALDOCUMENT": "FALSE",
    }  # fmt: skip
    return [*((key, values[key]) for key in HEADER_KEYS), ("GAP", "0.3mm")]


def test_altium_scope_of_netless_items() -> None:
    assert parse_scope("InNet('No Net')") == NO_NET
    assert parse_scope("Not InNet('No Net')") == Selector("not", items=(NO_NET,))
    mapping = map_rules([_clearance("InNet('No Net')")], origin="board.RUL")
    assert mapping.unmapped == ()
    (rule,) = mapping.ruleset.rules
    assert rule.selector_a == NO_NET and rule.min == 300_000
    assert _selector(rule.selector_a, set()) == "select.no_net()"


def test_kicad_project_round_trip(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "design.py").write_text((EXAMPLE / "design.py").read_text(encoding="utf-8") + RULE)
    for name in ("fp-lib-table", "sym-lib-table"):
        text = (EXAMPLE / name).read_text(encoding="utf-8")
        (source / name).write_text(text.replace("${KIPRJMOD}/../..", ROOT.as_posix()))
    built = run("build", "design.py", "--out", "kicad", "--confirm", cwd=source, timestamp=STAMP)
    assert built.exit_code == 0, built.error
    dru = next((source / "kicad").glob("*.kicad_dru")).read_text(encoding="utf-8")
    assert "(condition \"A.NetName == ''\")" in dru
    project = next((source / "kicad").glob("*.kicad_pro"))
    reply = run("import", str(project), "--to", "python", "--out", "out", "--confirm", cwd=tmp_path,
                timestamp=STAMP)  # fmt: skip
    assert reply.exit_code == 0, reply.error
    code = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    assert "where=select.no_net()" in code
    assert not any("netless" in str(item) for item in reply.result["unexpressed"])
