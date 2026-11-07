# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The v0.7 release record says only what exists (capability release-gate, "Release record of v0.7",
"Open tasks in the record of v0.7", "Sections of the record of v0.7", "Scope of 0.7.0 of 2026-11-06",
"Version 0.7.0" and "History row and roadmap of 0.7.0"; change c0469). As for v0.6, the record has one row
per change, named by its folder, and this guard holds each row to that folder's task list, so that no open
task goes unnamed and no row ships with a task left open. A change added after v0.6.0 that shipped no code
has an entry under "Left out of the rows" instead of a row."""

from __future__ import annotations

import ast
import importlib.util
import re
import sys
from pathlib import Path

import pytest

import fenolite

ROOT = Path(__file__).resolve().parents[2]
RECORD = ROOT / "docs" / "release" / "v0.7.md"
HISTORY = ROOT / "docs" / "evidence" / "residue-history.md"
CHANGELOG = ROOT / "CHANGELOG.md"
ROADMAP = ROOT / "docs" / "roadmap.md"
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
CHANGES = ROOT / "openspec" / "changes"
RELEASED = "0.7.0"
PREVIOUS = "0.6.0"
RELEASE_CHANGE = "c0469"
FIRST, LAST = 243, 467
"""The ids of the folders added after ``v0.6.0`` on the base of lote-29 (c0243 to c0467)."""
HEADER = "| change | what ships | proof | job | open tasks | result |"
FIELDS = ("change", "ships", "proof", "job", "open", "result")
SHIPS, DEFERRED, PENDING = "ships", "ships with deferred tasks", "pending"
RESULTS = (SHIPS, DEFERRED, PENDING)
PLACEHOLDER = "TODO(coordinator)"
V07_CHANGES: tuple[str, ...] = (
    "c0160-convert-to-altium",
    "c0172-altium-draftsman",
    "c0173-board-panels",
    "c0175-board-engineering-tools",
    "c0181-altium-native-layers",
    "c0216-contract-v1",
    "c0217-result-schemas-v1",
    "c0218-model-schema-1-0",
    "c0219-conformance-matrix",
    "c0220-legal-history-1-0",
    "c0241-altium-edit-sessions",
    "c0243-role-copper",
    "c0244-critical-routes",
    "c0246-quantity-ranges",
    "c0247-connection-helpers",
    "c0248-device-catalog",
    "c0249-design-lock",
    "c0250-manual-edit-merge",
    "c0251-circuit-blocks",
    "c0252-parametric-interfaces",
    "c0253-electrical-contracts",
    "c0254-parametric-part-selection",
    "c0255-relative-placement",
    "c0256-design-testing",
    "c0257-interface-pin-assignment",
    "c0258-signal-topologies",
    "c0259-library-data-format",
    "c0260-footprint-generators",
    "c0261-symbol-generator",
    "c0262-library-rules",
    "c0263-passive-families",
    "c0264-library-import",
    "c0265-datasheet-proposals",
    "c0266-device-packs",
    "c0267-supplier-lookup",
    "c0268-block-records",
    "c0269-block-schematic",
    "c0270-block-tests",
    "c0271-block-layouts",
    "c0272-starter-blocks",
    "c0273-block-packages",
    "c0274-electrical-requirements",
    "c0275-board-to-code",
    "c0276-drawn-schematic",
    "c0277-dsl-board-coverage",
    "c0278-fidelity-proof",
    "c0279-fenolite-library",
    "c0280-route-proposals",
    "c0281-import-copy-fidelity",
    "c0282-import-copper-exact",
    "c0300-viewer-shell",
    "c0301-viewer-inspector",
    "c0302-viewer-run-checks",
    "c0303-viewer-actions",
    "c0304-viewer-build",
    "c0305-viewer-roles",
    "c0311-cross-platform-batch-gates",
    "c0315-import-derive-once",
    "c0316-residue-web-paths",
    "c0317-import-edge-fields",
    "c0318-import-footprint-identity",
    "c0319-integration-repairs",
    "c0320-drawn-bus-resolution",
    "c0321-block-temp-cleanup",
    "c0323-build-byte-diagnostics",
    "c0324-technical-layer-tables",
    "c0326-drawn-font-preservation",
    "c0327-contextual-symbol-definitions",
    "c0329-sheet-custom-properties",
    "c0330-root-sheet-presentation-identity",
    "c0331-altium-drawn-bus-aliases",
    "c0332-certified-neck-cut",
    "c0333-library-audit-repairs",
    "c0334-bom-only-components",
    "c0335-librepcb-seed-compatibility",
    "c0336-local-power-aliases",
    "c0337-drawn-font-styles",
    "c0339-drawn-empty-title-blocks",
    "c0340-project-geometry-and-teardrop-proof",
    "c0341-nested-device-review",
    "c0342-source-footprint-alias",
    "c0343-formatted-bus-prefixes",
    "c0344-kicad-project-sheet-identity",
    "c0345-custom-footprint-field-poses",
    "c0346-equivalent-cyclic-orientation",
    "c0347-census-floor-upgrade",
    "c0348-intersheet-label-fields",
    "c0349-outline-footprint-membership",
    "c0350-native-root-hierarchical-labels",
    "c0351-declared-project-template",
    "c0352-import-project-rule-semantics",
    "c0353-embedded-empty-pin-numbers",
    "c0354-declared-project-resources",
    "c0355-verified-native-identity",
    "c0356-import-explicit-kicad-target",
    "c0357-measured-hash-pin-names",
    "c0358-native-custom-property-preservation",
    "c0359-declared-native-rule-context",
    "c0363-native-tab-property-preservation",
    "c0364-import-board-failures",
    "c0365-router-search",
    "c0366-router-role-costs",
    "c0367-router-negotiated-reroute",
    "c0368-router-external-candidates",
    "c0369-router-proposal-viewer",
    "c0370-router-completion-review",
    "c0371-conversion-equivalence-scope",
    "c0372-generated-schematic-limit",
    "c0373-pcb-only-net-conflicts",
    "c0374-embedded-board-arrays",
    "c0375-import-copper-coverage",
    "c0376-altium-copper-shapes",
    "c0377-altium-rule-coverage",
    "c0378-altium-bodies-and-edge-rings",
    "c0379-altium-tab-properties",
    "c0380-ci-profiles-and-coverage",
    "c0381-light-push-feedback",
    "c0384-native-identity-follow-up",
    "c0385-catalog-pin-order",
    "c0386-embedded-board-placement",
    "c0387-altium-body-measurements",
    "c0388-draftsman-native-document",
    "c0389-altium-native-rounds-follow-up",
    "c0401-fidelity-census-follow-up",
    "c0402-deterministic-exact-budget",
    "c0403-board-rebuild-fixes",
    "c0404-capture-graphic-nets-model-review",
    "c0405-library-gallery-design",
    "c0406-readable-schematic-layout",
    "c0407-altium-keepouts-cutouts-slots",
    "c0408-built-net-spelling",
    "c0409-altium-import-fidelity",
    "c0410-keepout-pads-library-keepouts",
    "c0411-footprint-rule-areas",
    "c0412-kicad-altium-write-gaps",
    "c0413-teardrop-proof-rotated-custom-parents",
    "c0414-empty-schematic-footprint-field",
    "c0415-review-content-digest",
    "c0416-level3-slot-length-axis",
    "c0417-jlc-supplier-lookup",
    "c0418-gallery-provenance-attribution",
    "c0419-library-symbol-fields",
    "c0420-altium-import-residue",
    "c0421-equivalent-pairing-noise",
    "c0422-altium-footprint-content",
    "c0423-altium-models-to-kicad",
    "c0424-altium-rules-lossless",
    "c0425-import-identity-residue",
    "c0426-import-selfcheck-exactness",
    "c0427-import-unexpressed-kinds",
    "c0428-altium-convert-new-losses",
    "c0429-conversion-ledger-consistency",
    "c0430-altium-flip-texts",
    "c0431-altium-net-tie-copper",
    "c0432-place-converted-board",
    "c0433-altium-unnumbered-pads",
    "c0434-altium-rules-written",
    "c0435-flow-b-fidelity",
    "c0436-convert-pour-needs-geo",
    "c0437-check-speed",
    "c0439-altium-pour-cutouts",
    "c0440-pad-mask-roundtrip",
    "c0441-board-shape-roundtrip",
    "c0442-altium-keepout-lines",
    "c0443-altium-component-cutouts",
    "c0444-roundtrip-lost-pad-connectivity",
    "c0445-via-mask-roundtrip",
    "c0446-altium-polygon-thresholds",
    "c0447-roundtrip-free-pads",
    "c0448-build-altium-parity",
    "c0449-altium-embedded-models",
    "c0450-altium-records-roundtrip",
    "c0451-roundtrip-texts-and-links",
    "c0452-altium-edit-gaps",
    "c0453-altium-flip-side",
    "c0454-altium-component-copper",
    "c0455-altium-keepout-fills",
    "c0457-carried-rules-matched-by-content",
    "c0458-built-project-models",
    "c0459-altium-board-regions-lost",
    "c0460-altium-union-and-font-references",
    "c0461-altium-classes-split-planes",
    "c0462-altium-rule-scopes-complete",
    "c0463-altium-pour-without-repour",
    "c0464-altium-board6-carried",
    "c0465-check-allowances",
    "c0466-altium-planes-through-kicad",
    "c0467-altium-frame-through-kicad",
)
"""The changes of 0.7.0 with a row: every folder added after v0.6.0 that shipped code, and every change of an
earlier release for which code changed since 0.6.0 (the maintainer's approval of 2026-11-06)."""
LEFT_OUT: tuple[str, ...] = (
    "c0322-fixture-collection",
    "c0328-deterministic-boolean-realization",
    "c0338-librepcb-seed-curation",
)
"""Folders added after v0.6.0 that shipped no code: an entry under "Left out of the rows", no row."""
EARLIER: tuple[str, ...] = (
    "c0175",
    "c0081",
    "c0105",
    "c0092",
    "c0160",
    "c0166",
    "c0168",
    "c0170",
    "c0172",
    "c0173",
    "c0177",
    "c0178",
    "c0179",
    "c0180",
    "c0181",
    "c0186",
    "c0195",
    "c0196",
    "c0215",
    "c0216",
    "c0217",
    "c0218",
    "c0219",
    "c0220",
    "c0241",
)
"""Changes of earlier releases closed since 0.6.0 (and c0175, still open): an entry under "Changes of earlier
releases"."""
DEFERRED_AFTER = ("c0175", "c0384", "c0389", "c0417", "c0195", "5.4", "v0.8", "v1.0")
"""What "Deferred after v0.7" must name."""
NOT_IN_RELEASE = ("c0468", "v1.0")
"""What "Not in 0.7.0" must name; it must name no change of the release."""
RUN = re.compile(r"https://github\.com/[\w.-]+/[\w.-]+/actions/runs/\d+")
TASK = re.compile(r"^- \[( |x)\] (\d+\.\d+[a-z]?|[A-Z]\d+|\d+(?=\.\s))\b", re.MULTILINE)
"""A task number: ``1.2``, ``3.4a``, ``J1``, or ``1`` written ``1.`` (the router changes c0365 to c0370)."""
ID = re.compile(r"^c(\d{4})-")


def section(text: str, title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", text, re.MULTILINE | re.DOTALL)
    return match.group(1) if match else ""


def cells(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def rows(text: str) -> list[dict[str, str]]:
    lines = section(text, "Verdict per change").splitlines()
    start = next((i for i, line in enumerate(lines) if line.startswith(HEADER)), None)
    if start is None:
        return []
    found: list[dict[str, str]] = []
    for line in lines[start + 2 :]:
        if not line.startswith("|"):
            break
        values = cells(line)
        assert len(values) == len(FIELDS), values
        found.append(dict(zip(FIELDS, values, strict=True)))
    return found


def jobs(workflow: str) -> set[str]:
    body = workflow.split("\njobs:\n", 1)[1] if "\njobs:\n" in workflow else ""
    return set(re.findall(r"^  ([A-Za-z0-9_-]+):\s*$", body, re.MULTILINE))


def proof_problem(proof: str) -> str:
    path, _, name = proof.partition("::")
    if not path.startswith("tests/"):
        return "not a path under tests/"
    file = ROOT / path
    if not file.is_file():
        return f"{path} does not exist"
    if name:
        tree = ast.parse(file.read_text(encoding="utf-8"))
        names = {node.name for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))}
        if name not in names:
            return f"{path} has no function {name}"
    return ""


def tasks_file(change: str) -> Path | None:
    """The task list of ``change``: its open folder, or its folder in the archive once it is archived."""
    folder = change if "-" in change else f"{change}-*"
    found = sorted(CHANGES.glob(f"{folder}/tasks.md")) or sorted(
        (CHANGES / "archive").glob(f"*-{folder}/tasks.md")
    )
    return found[0] if found else None


def tasks(change: str) -> dict[str, bool]:
    """Task number to ticked, from the change's ``tasks.md``."""
    file = tasks_file(change)
    if file is None:
        return {}
    return {number: mark == "x" for mark, number in TASK.findall(file.read_text(encoding="utf-8"))}


def folders_in_scope() -> set[str]:
    """Every change folder, open or archived, whose id lies in c0243..c0467."""
    names = {path.name for path in CHANGES.iterdir() if path.is_dir()}
    names |= {re.sub(r"^\d{4}-\d{2}-\d{2}-", "", path.name) for path in (CHANGES / "archive").iterdir()}
    return {name for name in names if (m := ID.match(name)) and FIRST <= int(m.group(1)) <= LAST}


def named(cell: str) -> list[str]:
    return [] if cell in ("—", "-", "") else [part.strip() for part in cell.split(",")]


def entry(text: str, title: str, change: str) -> bool:
    return any(e.startswith(f"**{change}.") for e in section(text, title).split("\n- "))


def row_problems(text: str, row: dict[str, str], known_jobs: set[str]) -> list[str]:
    change = row["change"]
    problems: list[str] = []
    why = proof_problem(row["proof"])
    if why:
        problems.append(f"{change}: proof {why}")
    problems.extend(
        f"{change}: no job {job!r} in ci.yml" for job in named(row["job"]) if job not in known_jobs
    )
    result = row["result"]
    if result not in RESULTS:
        problems.append(f"{change}: result {result!r}")
    listed = tasks(change)
    if not listed:
        problems.append(f"{change}: no tasks.md")
    given = named(row["open"])
    problems.extend(
        f"{change}: {number} is not a task of its tasks.md" for number in given if number not in listed
    )
    problems.extend(
        f"{change}: task {number} is open and not named"
        for number, ticked in listed.items()
        if not ticked and number not in given
    )
    if result == SHIPS and given:
        problems.append(f"{change}: a row that ships names open tasks")
    if result in (DEFERRED, PENDING) and not given:
        problems.append(f"{change}: a row that is {result} names no open task")
    if result == DEFERRED and not entry(text, "Deferred to the next release", change):
        problems.append(f"{change}: no entry under '## Deferred to the next release'")
    if result == PENDING and not entry(text, "Pending on the release branch", change):
        problems.append(f"{change}: no entry under '## Pending on the release branch'")
    return problems


def left_out_problems(text: str, changes: list[str]) -> list[str]:
    """Each change left out has its entry and no row; every folder of the range has a row or an entry."""
    problems: list[str] = []
    for folder in LEFT_OUT:
        if not entry(text, "Left out of the rows", folder):
            problems.append(f"{folder}: no entry under '## Left out of the rows'")
        if folder in changes:
            problems.append(f"{folder}: left out, but it has a row")
    known = set(V07_CHANGES) | set(LEFT_OUT)
    problems.extend(
        f"{folder}: added after v{PREVIOUS} but neither a row nor left out"
        for folder in sorted(folders_in_scope() - known)
    )
    return problems


def earlier_problems(text: str) -> list[str]:
    """Each change of an earlier release closed since 0.6.0 has an entry under its section."""
    body = section(text, "Changes of earlier releases")
    return [
        f"{change}: no entry under '## Changes of earlier releases'"
        for change in EARLIER
        if not any(e.startswith(f"**{change}") for e in body.split("\n- "))
    ]


def record_problems(text: str, *, workflow: str) -> list[str]:
    """Everything the guard refuses in the record of ``0.7.0``."""
    problems: list[str] = []
    known_jobs = jobs(workflow)
    found = rows(text)
    if not found:
        return ["the table of '## Verdict per change' is missing"]
    changes = [row["change"] for row in found]
    problems.extend(f"{change}: no row" for change in V07_CHANGES if change not in changes)
    problems.extend(
        f"{change}: not a change of {RELEASED}"
        for change in changes
        if change not in V07_CHANGES and change not in LEFT_OUT
    )
    problems.extend(
        f"{change}: more than one row" for change in sorted(set(changes)) if changes.count(change) > 1
    )
    for row in found:
        problems.extend(row_problems(text, row, known_jobs))
    problems.extend(left_out_problems(text, changes))
    problems.extend(earlier_problems(text))
    after = section(text, "Deferred after v0.7")
    problems.extend(
        f"deferred after v0.7: {words!r} is missing" for words in DEFERRED_AFTER if words not in after
    )
    absent = section(text, f"Not in {RELEASED}")
    problems.extend(
        f"not in {RELEASED}: {words!r} is missing" for words in NOT_IN_RELEASE if words not in absent
    )
    problems.extend(
        f"not in {RELEASED}: {change} is a change of the release"
        for change in sorted({folder.split("-", 1)[0] for folder in V07_CHANGES})
        if re.search(rf"\b{change}\b", absent)
    )
    if "experimental" not in section(text, "Altium write"):
        problems.append("altium write: the section does not say that the write stays experimental")
    limits = section(text, "Recorded limits")
    problems.extend(
        f"limits: {words!r} is missing"
        for words in ("private gate", "contract stays `v0`")
        if words not in limits
    )
    runs = section(text, "Runs and versions")
    if not RUN.search(runs):
        problems.append("runs: no CI run is linked")
    problems.extend(
        f"runs: {words!r} is missing"
        for words in ("9.0.9", "10.0.6", "release candidate", f"release-{RELEASED}")
        if words not in runs
    )
    build = section(text, "Release build")
    problems.extend(
        f"release build: the section lacks {words!r}"
        for words in (
            "git worktree add",
            "never from the working tree",
            f"v{RELEASED}",
            "tools/release.py check",
        )
        if words not in build
    )
    steps = section(text, "Maintainer's steps")
    problems.extend(
        f"maintainer's steps: {words!r} is missing"
        for words in (
            "verdict",
            "`dev` to `main`",
            f"v{RELEASED}",
            "clean checkout",
            "Publish",
            "`main` into `dev`",
        )
        if words not in steps
    )
    for title in ("Archive order", "Deferred after v0.7"):
        if not section(text, title).strip():
            problems.append(f"{title.lower()}: the section is missing")
    verdict = section(text, "Verdict").strip()
    pending = [row["change"] for row in found if row["result"] == PENDING]
    if not verdict:
        problems.append("verdict: the section is missing")
    elif verdict != "pending":
        if pending:
            problems.append(f"verdict: written while {', '.join(pending)} is pending")
        if PLACEHOLDER in text:
            problems.append(f"verdict: written while a {PLACEHOLDER} placeholder stands")
    return problems


def history_problems(text: str, *, version: str) -> list[str]:
    """At ``0.7.0`` the row ``v0.7.0`` exists with 0 hits; its private gate is ``not run`` or ``on``.
    Before the version commit the row may be absent (c0469 task 1.3), but a written row must hold."""
    row = next(
        (line for line in text.splitlines() if line.startswith("|") and f"| v{RELEASED} |" in line), ""
    )
    if not row:
        return [f"{HISTORY.name}: no v{RELEASED} row"] if version == RELEASED else []
    found = cells(row)
    if len(found) != 7:
        return [f"{HISTORY.name}: the v{RELEASED} row needs 7 cells"]
    problems: list[str] = []
    if found[5] != "not run" and not found[5].startswith("on"):
        problems.append(
            f"{HISTORY.name}: the private gate column of v{RELEASED} says {found[5]!r}, not 'not run' or 'on'"
        )
    if found[6] != "0":
        problems.append(f"{HISTORY.name}: the v{RELEASED} row reports {found[6]} hit(s)")
    return problems


def changelog_problems(text: str, *, version: str) -> list[str]:
    """At ``0.7.0`` the headings start ``Unreleased``, ``0.7.0`` and ``0.6.0``; the ``[0.7.0]`` section has
    exactly one ``Added``, ``Changed`` and ``Fixed``, and no entry twice."""
    headings = re.findall(r"^## \[([^\]]+)\]", text, re.MULTILINE)
    if RELEASED not in headings:
        return [f"no [{RELEASED}] section at version {version}"] if version == RELEASED else []
    problems: list[str] = []
    if version == RELEASED and headings[:3] != ["Unreleased", RELEASED, PREVIOUS]:
        problems.append(f"the sections start {headings[:3]}, not ['Unreleased', '{RELEASED}', '{PREVIOUS}']")
    unreleased = re.search(r"^## \[Unreleased\]\n(.*?)(?=^## \[|\Z)", text, re.MULTILINE | re.DOTALL)
    if version == RELEASED and unreleased and unreleased.group(1).strip():
        problems.append("[Unreleased] is not empty at the release")
    released = re.search(
        rf"^## \[{re.escape(RELEASED)}\][^\n]*\n(.*?)(?=^## \[|\Z)", text, re.MULTILINE | re.DOTALL
    )
    body = released.group(1) if released else ""
    names = re.findall(r"^### (.+)$", body, re.MULTILINE)
    if released and sorted(names) != ["Added", "Changed", "Fixed"]:
        problems.append(f"[{RELEASED}]: the headings are {names}, not one Added, Changed and Fixed each")
    entries = [line for line in body.splitlines() if line.startswith("- ")]
    problems.extend(
        f"[{RELEASED}]: the entry {line[:60]!r} appears twice"
        for line in sorted(set(entries))
        if entries.count(line) > 1
    )
    loose = [line for line in body.split("###", 1)[0].splitlines() if line.startswith("- ")]
    if loose:
        problems.append(f"[{RELEASED}]: {len(loose)} entries stand before the first '###' heading")
    return problems


def milestone_row(text: str, milestone: str) -> str:
    milestones = section(text, "Milestones")
    return next(
        (
            line
            for line in milestones.splitlines()
            if line.startswith("|") and len(cells(line)) > 1 and cells(line)[1] == milestone
        ),
        "",
    )


def roadmap_problems(text: str) -> list[str]:
    """The milestone row of v0.7 names the release change and the record."""
    row = milestone_row(text, "v0.7")
    if not row:
        return ["roadmap: no milestone row for v0.7"]
    return [
        f"roadmap: the row of v0.7 does not name {words}"
        for words in (RELEASE_CHANGE, "docs/release/v0.7.md")
        if words not in row
    ]


def record() -> str:
    return RECORD.read_text(encoding="utf-8")


def check(text: str) -> list[str]:
    return record_problems(text, workflow=WORKFLOW.read_text(encoding="utf-8"))


def row_line(text: str, change: str) -> str:
    return next(line for line in text.splitlines() if line.startswith(f"| {change} |"))


def with_cell(text: str, change: str, field: str, value: str) -> str:
    line = row_line(text, change)
    values = cells(line)
    values[FIELDS.index(field)] = value
    return text.replace(line, "| " + " | ".join(values) + " |", 1)


def with_verdict(text: str, verdict: str) -> str:
    return re.sub(r"## Verdict\n\n.*\Z", f"## Verdict\n\n{verdict}\n", text, flags=re.DOTALL)


SHIPPED = "c0432-place-converted-board"
ROUNDS = "c0389-altium-native-rounds-follow-up"


def test_record_is_consistent() -> None:
    """Scenario "Every change present"."""
    assert check(record()) == []


def test_missing_change_proof_and_job_are_named() -> None:
    text = record()
    without = text.replace(row_line(text, SHIPPED) + "\n", "", 1)
    assert f"{SHIPPED}: no row" in check(without)
    gone = with_cell(text, SHIPPED, "proof", "tests/unit/cli/test_missing.py")
    assert any("test_missing.py does not exist" in p for p in check(gone))
    proof = row_line(text, SHIPPED).split(" | ")[2].partition("::")[0]
    named_gone = with_cell(text, SHIPPED, "proof", f"{proof}::test_gone")
    assert any("has no function test_gone" in p for p in check(named_gone))
    assert f"{SHIPPED}: no job 'kicad-11' in ci.yml" in check(with_cell(text, SHIPPED, "job", "kicad-11"))


def test_c0468_is_not_a_row() -> None:
    """Scenario "c0468 named as a row"."""
    text = record()
    folder = "c0468-library-generator-families"
    stray = text.replace(
        row_line(text, SHIPPED),
        row_line(text, SHIPPED) + "\n" + row_line(text, SHIPPED).replace(SHIPPED, folder),
    )
    assert f"{folder}: not a change of {RELEASED}" in check(stray)


def test_open_task_must_be_named() -> None:
    """Scenario "An open task not named"."""
    open_now = [number for number, ticked in tasks(ROUNDS).items() if not ticked]
    if open_now:
        kept = ", ".join(open_now[1:]) or "—"
        assert f"{ROUNDS}: task {open_now[0]} is open and not named" in check(
            with_cell(record(), ROUNDS, "open", kept)
        )
    current = row_line(record(), ROUNDS).split(" | ")[4]
    extra = "9.9" if current == "—" else f"{current}, 9.9"
    assert f"{ROUNDS}: 9.9 is not a task of its tasks.md" in check(with_cell(record(), ROUNDS, "open", extra))


def test_results_need_their_entries() -> None:
    """Scenario "A pending row without its entry"."""
    text = record()
    assert f"{SHIPPED}: result 'mostly ships'" in check(with_cell(text, SHIPPED, "result", "mostly ships"))
    assert f"{SHIPPED}: a row that is pending names no open task" in check(
        with_cell(text, SHIPPED, "result", "pending")
    )
    for row in rows(text):
        if row["result"] == PENDING:
            change = row["change"]
            gone = text.replace(f"- **{change}.**", "- **gone.**", 1)
            assert f"{change}: no entry under '## Pending on the release branch'" in check(gone)
            break
    if not all(tasks(ROUNDS).values()):
        assert f"{ROUNDS}: a row that ships names open tasks" in check(
            with_cell(text, ROUNDS, "result", "ships")
        )
        no_entry = text.replace(f"- **{ROUNDS}.**", "- **The rounds.**", 1)
        assert f"{ROUNDS}: no entry under '## Deferred to the next release'" in check(no_entry)


def test_left_out_changes_have_no_row() -> None:
    """Scenario "A change that shipped no code given a row"."""
    text = record()
    if not LEFT_OUT:
        pytest.skip("no change is left out")
    folder = LEFT_OUT[0]
    stray = text.replace(
        row_line(text, SHIPPED),
        row_line(text, SHIPPED) + "\n" + row_line(text, SHIPPED).replace(SHIPPED, folder),
    )
    assert f"{folder}: left out, but it has a row" in check(stray)
    assert f"{folder}: no entry under '## Left out of the rows'" in check(
        text.replace(f"- **{folder}.**", "- **gone.**", 1)
    )


def test_every_folder_of_the_range_is_accounted_for(monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Scope of 0.7.0": a folder of the range with neither a row nor an entry is named."""
    monkeypatch.setitem(globals(), "folders_in_scope", lambda: {*V07_CHANGES, *LEFT_OUT, "c0300-stray"})
    assert "c0300-stray: added after v0.6.0 but neither a row nor left out" in check(record())


@pytest.mark.parametrize("change", EARLIER)
def test_earlier_changes_have_their_entry(change: str) -> None:
    text = record()
    body = section(text, "Changes of earlier releases")
    gone = body.replace(f"- **{change}", "- **gone", 1)
    assert f"{change}: no entry under '## Changes of earlier releases'" in check(text.replace(body, gone, 1))


@pytest.mark.parametrize("words", DEFERRED_AFTER)
def test_deferred_items_are_named(words: str) -> None:
    body = section(record(), "Deferred after v0.7")
    text = record().replace(body, body.replace(words, "x"), 1)
    assert f"deferred after v0.7: {words!r} is missing" in check(text)


def test_not_in_release_and_altium_write() -> None:
    text = record()
    body = section(text, f"Not in {RELEASED}")
    assert f"not in {RELEASED}: 'c0468' is missing" in check(
        text.replace(body, body.replace("c0468", "x"), 1)
    )
    late = text.replace(body, body + f"- **c0432**: after `{RELEASED}`.\n", 1)
    assert f"not in {RELEASED}: c0432 is a change of the release" in check(late)
    altium = section(text, "Altium write")
    assert any(
        p.startswith("altium write")
        for p in check(text.replace(altium, altium.replace("experimental", "x"), 1))
    )


def test_verdict_over_pending_rows_and_placeholders() -> None:
    """Scenario "Verdict over a placeholder"."""
    text = record()
    assert not [p for p in check(text) if p.startswith("verdict")]
    decided = with_verdict(text, f"Released as v{RELEASED}.")
    if PLACEHOLDER in text:
        assert f"verdict: written while a {PLACEHOLDER} placeholder stands" in check(decided)
    clean = with_verdict(text.replace(PLACEHOLDER, "run"), f"Released as v{RELEASED}.")
    for change in [row["change"] for row in rows(clean) if row["result"] == PENDING]:
        clean = with_cell(clean, change, "result", DEFERRED)
        if not entry(clean, "Deferred to the next release", change):
            body = section(clean, "Deferred to the next release")
            clean = clean.replace(body, body + f"- **{change}.** moved.\n", 1)
    assert not [p for p in check(clean) if p.startswith("verdict")]


def test_steps_and_build_are_stated() -> None:
    text = record()
    assert any(p.startswith("release build") for p in check(text.replace("never from the working tree", "x")))
    assert any(p.startswith("maintainer's steps") for p in check(text.replace("`main` into `dev`", "x")))
    assert any(
        p.startswith(f"runs: 'release-{RELEASED}'") for p in check(text.replace(f"release-{RELEASED}", "x"))
    )


def test_history_row() -> None:
    """Scenario "History row required"."""
    text = HISTORY.read_text(encoding="utf-8")
    assert history_problems(text, version=fenolite.__version__) == []
    without = "\n".join(line for line in text.splitlines() if f"| v{RELEASED} |" not in line)
    assert history_problems(without, version=RELEASED) == [f"{HISTORY.name}: no v{RELEASED} row"]
    assert history_problems(without, version="0.7.0.dev0") == []
    hits = without + f"\n| 2026-11-06 | v{RELEASED} | root .. abc | all | 5 | on | 2 |\n"
    assert any("2 hit(s)" in p for p in history_problems(hits, version=RELEASED))
    odd = without + f"\n| 2026-11-06 | v{RELEASED} | root .. abc | all | 5 | maybe | 0 |\n"
    assert any("private gate column" in p for p in history_problems(odd, version=RELEASED))


def test_changelog_section() -> None:
    """Scenario "Versions agree": the order of the sections and a clean ``[0.7.0]``."""
    text = CHANGELOG.read_text(encoding="utf-8")
    assert changelog_problems(text, version=fenolite.__version__) == []
    assert changelog_problems("## [Unreleased]\n", version=RELEASED) == [
        f"no [{RELEASED}] section at version {RELEASED}"
    ]
    full = "### Added\n\n- a\n\n### Changed\n\n- b\n\n### Fixed\n\n- c\n\n"
    good = f"## [Unreleased]\n\n## [{RELEASED}] - d\n\n{full}## [{PREVIOUS}] - d\n"
    assert changelog_problems(good, version=RELEASED) == []
    left = f"## [Unreleased]\n\n- b\n\n## [{RELEASED}] - d\n\n{full}## [{PREVIOUS}] - d\n"
    assert "[Unreleased] is not empty at the release" in changelog_problems(left, version=RELEASED)


def test_versions_agree() -> None:
    """Scenario "Versions agree": the package, its alias, the alias pin and the release tool."""
    alias = (ROOT / "packaging" / "phenolite" / "pyproject.toml").read_text(encoding="utf-8")
    version = fenolite.__version__
    assert f'version = "{version}"' in alias and f"fenolite=={version}" in alias
    if version == RELEASED:
        spec = importlib.util.spec_from_file_location("release_tool_v07", ROOT / "tools" / "release.py")
        assert spec and spec.loader
        tool = importlib.util.module_from_spec(spec)
        sys.modules["release_tool_v07"] = tool
        spec.loader.exec_module(tool)
        assert tool.check(ROOT, f"v{RELEASED}") == []


def test_roadmap_names_the_release() -> None:
    text = ROADMAP.read_text(encoding="utf-8")
    assert roadmap_problems(text) == []
    row = milestone_row(text, "v0.7")
    assert f"roadmap: the row of v0.7 does not name {RELEASE_CHANGE}" in roadmap_problems(
        text.replace(row, row.replace(RELEASE_CHANGE, "c9999"))
    )
