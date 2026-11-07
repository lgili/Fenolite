# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The rank of imported rules (capability imported-rules, "Imported rules keep the source's rank"; change
c0409, B4). An Altium rule "<class> x All" ranked below a pairwise rule of that class stays an ordinary rule
with its priority, never a class minimum that would govern the pairwise rule, and the written priorities are
Altium's own numbers.

The source is authored here: the blink example with one pairwise and one one-sided clearance rule, built for
Altium by Fenolite and imported back."""

from __future__ import annotations

import re
from pathlib import Path

from _importcode import ROOT, STAMP

from fenolite.api import run
from fenolite.importer.emit.design import _ranked  # pyright: ignore[reportPrivateUsage]
from fenolite.model.rules import Rule, Selector

EXAMPLE = ROOT / "examples" / "blink_2layer"
RULES = """
from fenolite.dsl import select
design.rules.rule(
    "pwr_led", "clearance", where=select.netclass("PWR"), between=select.net("LED_A"), min=mm(0.15),
    priority=1,
)
design.rules.rule("pwr_all", "clearance", where=select.netclass("PWR"), min=mm(0.4), priority=2)
"""


def _project(folder: Path) -> None:
    folder.mkdir()
    (folder / "design.py").write_text((EXAMPLE / "design.py").read_text(encoding="utf-8") + RULES)
    for name in ("fp-lib-table", "sym-lib-table"):
        text = (EXAMPLE / name).read_text(encoding="utf-8")
        (folder / name).write_text(text.replace("${KIPRJMOD}/../..", ROOT.as_posix()))


def _call(code: str, name: str) -> str:
    match = re.search(r'design\.rules\.rule\(\s*"' + name + r'",.*?\n?\)\n', code, re.DOTALL)
    assert match is not None, f"no rule {name}"
    return match.group(0)


def test_one_sided_class_rule_keeps_its_rank(tmp_path: Path) -> None:
    _project(tmp_path / "src")
    built = run(
        "build", "design.py", "--target", "altium", "--out", "alt", "--confirm", cwd=tmp_path / "src",
        timestamp=STAMP,
    )  # fmt: skip
    assert built.exit_code == 0, built.error
    source = tmp_path / "src" / "alt" / "blink.PrjPcb"
    reply = run(
        "import", str(source), "--to", "python", "--out", "out", "--confirm", cwd=tmp_path, timestamp=STAMP
    )
    assert reply.exit_code == 0, reply.error
    code = (tmp_path / "out" / "design.py").read_text(encoding="utf-8")
    minimums = [line for line in code.splitlines() if line.startswith("design.rules.minimum(")]
    assert minimums and not any("netclass=" in line for line in minimums)
    one_sided = _call(code, "clearance_pwr")
    assert 'where=select.netclass("PWR")' in one_sided and "between=" not in one_sided
    assert "priority=2" in one_sided
    pairwise = _call(code, "clearance_pwr_to_net_led_a")
    assert 'between=select.net("LED_A")' in pairwise and "priority=1" in pairwise
    rebuilt = run("build", "design.py", "--out", "built", "--confirm", cwd=tmp_path / "out", timestamp=STAMP)
    assert rebuilt.exit_code == 0, rebuilt.error
    dru = next((tmp_path / "out" / "built").glob("*.kicad_dru")).read_text(encoding="utf-8")
    # the later rule governs in KiCad: the pairwise rule, Altium's priority 1, comes after the class rule
    assert dru.index('"fenolite_2_clearance_pwr"') < dru.index('"fenolite_1_clearance_pwr_to_net_led_a"')
    assert "fenolite_1_min_clearance_pwr" not in dru


def _rule(name: str, priority: int) -> Rule:
    return Rule(
        id=f"rul_0c409000-0000-4000-8000-00000000000{priority}", name=name, kind="clearance",
        selector_a=Selector("all"), min=100_000, priority=priority,
    )  # fmt: skip


def test_written_priorities_only_when_they_give_the_file_order() -> None:
    kept = (_rule("fenolite_3_low", 2), _rule("fenolite_1_high", 1))
    assert [rule.priority for rule in _ranked(kept)] == [3, 1]
    swapped = (_rule("fenolite_1_high", 2), _rule("fenolite_3_low", 1))
    assert [rule.priority for rule in _ranked(swapped)] == [2, 1]
    unnamed = (_rule("fenolite_3_low", 2), _rule("hand", 1))
    assert [rule.priority for rule in _ranked(unnamed)] == [2, 1]
