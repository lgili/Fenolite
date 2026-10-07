# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Take ``examples/yardstick`` through the loop of its stage and judge the run (capability release-gate,
"Yardstick stages", "Yardstick runner", "Yardstick budgets" and "Yardstick record"; change c0119).

    uv run python tools/yardstick.py run --out build/yardstick --record build/yardstick/record.json
    uv run python tools/yardstick.py row build/yardstick/record.json --url <run url>
    uv run python tools/yardstick.py rebase RECORD RECORD RECORD

``run`` reads ``STAGE`` from the example without running it, then runs each step of the stage as one
child process ``python -m fenolite <args> --json`` in the output folder, which becomes the project
folder. For each step it keeps the exit code, the wall seconds, the peak resident memory of the step's
largest process, the bytes of the reply and the issue counts. It then reads the board's measures,
applies the acceptance rules and the budgets of ``tools/yardstick_budgets.toml``, writes a record
(``fenolite.yardstick-record.v0``) and a Markdown summary, and exits 0 (passed), 1 (a step, a rule or a
budget failed) or 2 (usage, or a missing tool, library cache, corpus row or budget table).

Seconds and MiB are measures of one runner: no evidence label moves on a budget. Standard library only.
"""

from __future__ import annotations

import argparse
import ast
import datetime
import hashlib
import json
import math
import os
import platform
import re
import statistics
import subprocess
import sys
import time
import tomllib
from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
EXAMPLE = ROOT / "examples" / "yardstick"
BUDGETS = ROOT / "tools" / "yardstick_budgets.toml"
PAGE = ROOT / "docs" / "evidence" / "yardstick.md"
ARCHIVE = ROOT / "openspec" / "changes" / "archive"
CORPUS_MANIFEST = ROOT / "tests" / "corpus" / "manifest.toml"
SCHEMA = "fenolite.yardstick-record.v0"
SEED = "250025"
TIMESTAMP = "2026-10-04T00:00:00Z"
TARGET = "10"
RUN_DIR = "yardstick-run"
"""The runner's own folder inside the output folder: the replies and an empty KiCad configuration."""
FENOLITE: tuple[str, ...] = (sys.executable, "-m", "fenolite")
"""The command of a step; the tests put a fake here."""
LIBS_CACHE = "FENOLITE_LIBS_CACHE"
CORPUS_CACHE = "FENOLITE_CORPUS_CACHE"
WRITING = ("--seed", SEED, "--timestamp", TIMESTAMP, "--no-backup", "--confirm")
PAGE_SECTIONS = ("How to read", "Stages", "Runs", "Budgets", "Not measured")
STAGE_STATES = ("reached", "waiting", "not reached")
ACCEPTED_KEYS = ("stage", "type", "reason", "owner")
UNCONNECTED = "unconnected_items"

STAGES: dict[int, tuple[tuple[str, ...], tuple[str, ...]]] = {
    1: (
        (),
        (
            "capabilities", "build-dry", "build", "fill", "check", "export", "render", "bom", "pnp",
            "manifest", "rebuild-dry", "rebuild", "inspect", "build-install", "heavy-read", "heavy-rt1",
        ),
    ),
    2: (("c0100", "c0101"), ()),
    3: (("c0102", "c0103", "c0104", "c0105", "c0111", "c0112", "c0113", "c0114"), ("impedance",)),
    4: (
        ("c0106", "c0107", "c0108", "c0109", "c0110", "c0115"),
        ("route-pairs", "route", "fill-routed", "check-routed", "net", "analyze"),
    ),
    5: (("c0116", "c0117", "c0118"), ("export-package", "testpoints")),
}  # fmt: skip
"""Per stage: the changes it needs archived, and the steps it adds to the stage before."""

_BUILD = ("build", "{script}", "--out", ".", "--kicad-version", TARGET)
_COMMANDS: dict[str, tuple[str, ...]] = {
    "capabilities": ("capabilities",),
    "build-dry": (*_BUILD, "--dry-run"),
    "build": (*_BUILD, *WRITING),
    "fill": ("fill", "{board}", *WRITING),
    "check": ("check", ".", "--format", "concise"),
    "export": ("export", ".", "-o", "fab", "--all", "--manifest", *WRITING),
    "render": ("render", ".", "-o", "fab", "--svg", "--manifest", *WRITING),
    "bom": ("bom", ".", "--source", "model", "--out", "fab/bom.csv", "--manifest", *WRITING),
    "pnp": ("pnp", ".", "--out", "fab/pnp.csv", "--manifest", *WRITING),
    "manifest": ("manifest", ".", "--artifacts", "fab", "--no-check", *WRITING),
    "rebuild-dry": (*_BUILD, "--dry-run"),
    "rebuild": (*_BUILD, *WRITING),
    "inspect": ("inspect", "{board}"),
    "build-install": (
        "build",
        "{script}",
        "--out",
        f"{RUN_DIR}/install",
        "--kicad-version",
        TARGET,
        "--dry-run",
    ),
    "heavy-read": ("inspect", "{heavy}"),
    "heavy-rt1": ("roundtrip", "{heavy}", "--level", "rt1"),
}
"""The command line of each step that this base can run; the steps of stages 3 to 5 get theirs with the
changes that own the commands (tasks 7.2, 8.1, 8.2 and 9.1 of c0119)."""
_STOPS_THE_LOOP = ("build", "fill")
_INDEPENDENT = ("capabilities", "build-install", "heavy-read", "heavy-rt1")
_NEEDS_BOARD = ("{board}",)


class Usage(Exception):
    """A usage error or a missing resource: ``run`` exits 2 with the message."""


@dataclass(frozen=True, slots=True)
class Step:
    """One step of a stage: its name, the ``fenolite`` arguments (``None`` while no change gives the
    command), the exit code its stage expects and the corpus row of a heavy step."""

    name: str
    args: tuple[str, ...] | None
    expect: int = 0
    row: str = ""
    drop_env: tuple[str, ...] = ()

    @property
    def base(self) -> str:
        return self.name.split(":", 1)[0]


@dataclass(frozen=True, slots=True)
class Finding:
    """A budget that a step crossed."""

    step: str
    measure: str
    value: float
    budget: float

    def text(self) -> str:
        unit = "s" if self.measure == "seconds" else "MiB"
        return (
            f"{self.step}: {self.measure} {self.value:.1f} {unit} over the budget of {self.budget:g} {unit}"
        )


@dataclass(frozen=True, slots=True)
class Accepted:
    """An accepted finding of the budgets file."""

    stage: str
    type: str
    reason: str
    owner: str


@dataclass(frozen=True, slots=True)
class StageBudgets:
    """The table ``[stage<n>]`` of the budgets file."""

    source: str
    steps: Mapping[str, Mapping[str, float]]
    accepted: tuple[Accepted, ...] = ()
    ratchets: Mapping[str, int] = field(default_factory=dict)

    def of(self, step: str) -> Mapping[str, float] | None:
        """The budget of a step: its own table, else that of its base name (``heavy-read`` for
        ``heavy-read:<row>``)."""
        found = self.steps.get(step)
        return found if found is not None else self.steps.get(step.split(":", 1)[0])


@dataclass(frozen=True, slots=True)
class Measured:
    """What a child process cost."""

    exit: int
    seconds: float
    peak_mib: float | None


# --------------------------------------------------------------------------------------------------
# The stage


def read_stage(path: Path) -> int:
    """``STAGE`` of the script at ``path``, read from its syntax tree: the script never runs."""
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as error:
        raise Usage(f"cannot read STAGE from {path.name}: {error}") from error
    for node in tree.body:
        targets = node.targets if isinstance(node, ast.Assign) else ()
        if isinstance(node, ast.AnnAssign):
            targets = (node.target,)
        if not any(isinstance(target, ast.Name) and target.id == "STAGE" for target in targets):
            continue
        value = node.value if isinstance(node, (ast.Assign, ast.AnnAssign)) else None
        if isinstance(value, ast.Constant) and type(value.value) is int and value.value in STAGES:
            return value.value
        raise Usage(f"STAGE of {path.name} must be a whole number from 1 to {max(STAGES)}")
    raise Usage(f"{path.name} holds no module-level STAGE")


def stage_needs(stage: int) -> tuple[str, ...]:
    """Every change the stages up to ``stage`` need archived."""
    return tuple(change for number in sorted(STAGES) if number <= stage for change in STAGES[number][0])


def stage_problems(stage: int, archived: Sequence[str], page: str) -> list[str]:
    """What forbids ``stage`` in the example: a change it needs that is neither archived (a folder name of
    ``openspec/changes/archive``) nor named as cut in the ``Stages`` section of the page."""
    stages = _section(page, "Stages")
    problems: list[str] = []
    for change in stage_needs(stage):
        if any(re.search(rf"(^|-){change}-", name) for name in archived):
            continue
        if re.search(rf"cut: [^)|]*\b{change}\b", stages):
            continue
        problems.append(f"STAGE = {stage} needs {change}, which is neither archived nor named as cut")
    return problems


def heavy_rows(manifest: Path = CORPUS_MANIFEST) -> tuple[tuple[str, str], ...]:
    """The corpus rows tagged ``heavy`` that are boards: ``(id, file name)`` in id order."""
    data = tomllib.loads(manifest.read_text(encoding="utf-8"))
    rows = [
        (str(row["id"]), str(row["url"]).rsplit("/", 1)[-1])
        for row in data.get("file", [])
        if "heavy" in row.get("uses", ()) and str(row.get("url", "")).endswith(".kicad_pcb")
    ]
    return tuple(sorted(rows))


def steps_for(stage: int, rows: Sequence[tuple[str, str]] | None = None) -> tuple[Step, ...]:
    """The steps of ``stage`` in the order the runner takes them. A heavy step is repeated once per heavy
    board, as ``heavy-read:<row id>``. ``check`` exits 5 before stage 4: the board is not routed."""
    if stage not in STAGES:
        raise Usage(f"STAGE must be a whole number from 1 to {max(STAGES)}, not {stage!r}")
    heavy = heavy_rows() if rows is None else tuple(rows)
    names = [name for number in sorted(STAGES) if number <= stage for name in STAGES[number][1]]
    steps: list[Step] = []
    for name in names:
        args = _COMMANDS.get(name)
        if name.startswith("heavy-"):
            for row, file_name in heavy:
                found = tuple(f"{{corpus}}/{row}/{file_name}" if a == "{heavy}" else a for a in args or ())
                steps.append(Step(f"{name}:{row}", found, row=row))
            continue
        expect = 5 if name == "check" and stage < 4 else 0
        drop = (LIBS_CACHE,) if name == "build-install" else ()
        steps.append(Step(name, args, expect=expect, drop_env=drop))
    return tuple(steps)


def peak_mib(usage: Any, system: str) -> float:
    """``ru_maxrss`` in MiB: the value is in bytes on macOS (``darwin``) and in kibibytes on Linux."""
    value = float(getattr(usage, "ru_maxrss", usage))
    return value / (1024 * 1024) if system.startswith("darwin") else value / 1024


# --------------------------------------------------------------------------------------------------
# Budgets


def load_budgets(path: Path) -> dict[str, Any]:
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as error:
        raise Usage(f"cannot read the budgets file {path.name}: {error}") from error


def stage_budgets(data: Mapping[str, Any], stage: int) -> StageBudgets:
    """The table of ``stage``; a missing table, or an accepted finding without one of its four keys, is a
    usage error that names it."""
    table = data.get(f"stage{stage}")
    if not isinstance(table, dict):
        raise Usage(f"the budgets file has no table [stage{stage}]")
    accepted: list[Accepted] = []
    for key, entry in sorted(dict(table.get("accepted", {})).items()):
        missing = [name for name in ACCEPTED_KEYS if not str(dict(entry).get(name, "")).strip()]
        if missing:
            raise Usage(f"[stage{stage}.accepted.{key}] lacks {', '.join(missing)}")
        accepted.append(Accepted(*(str(entry[name]) for name in ACCEPTED_KEYS)))
    steps = {str(name): dict(values) for name, values in dict(table.get("steps", {})).items()}
    ratchets = {str(name): int(value) for name, value in dict(table.get("ratchets", {})).items()}
    return StageBudgets(str(table.get("source", "")), steps, tuple(accepted), ratchets)


def judge(record: Mapping[str, Any], budgets: StageBudgets) -> list[Finding]:
    """Every step of ``record`` whose seconds or peak MiB exceed its budget. A step without a budget, or
    without a measure, fails nothing."""
    findings: list[Finding] = []
    for step in record["steps"]:
        budget = budgets.of(step["name"])
        if budget is None or step.get("status") == "skipped":
            continue
        for measure, key in (("seconds", "seconds"), ("mib", "peak_mib")):
            value, limit = step.get(key), budget.get(measure)
            if value is not None and limit is not None and value > limit:
                findings.append(Finding(step["name"], measure, float(value), float(limit)))
    return findings


def round_up(value: float, step: int) -> int:
    return int(math.ceil(round(value / step, 6))) * step


def rebase(records: Sequence[Mapping[str, Any]], *, provisional: bool = False) -> str:
    """The budgets that the rule gives, as TOML. From three records: seconds are the median times 1.5,
    rounded up to 10 s, and MiB the largest times 1.25, rounded up to 50 MiB. From one local record
    (``provisional``): seconds times 4 and MiB times 2, rounded the same way."""
    if provisional and len(records) != 1:
        raise Usage("rebase --provisional takes one record")
    if not provisional and len(records) != 3:
        raise Usage("rebase takes the records of three runs (or one with --provisional)")
    stages = {record["stage"] for record in records}
    if len(stages) != 1:
        raise Usage("rebase takes records of one stage")
    stage = stages.pop()
    names: list[str] = []
    for record in records:
        for step in record["steps"]:
            if step["name"] not in names:
                names.append(step["name"])
    source = "provisional" if provisional else "runs " + ", ".join(_run_name(record) for record in records)
    lines = [f"[stage{stage}]", f'source = "{source}"']
    for name in names:
        found = [s for record in records for s in record["steps"] if s["name"] == name]
        seconds = [
            s["seconds"] for s in found if s.get("seconds") is not None and s.get("status") != "skipped"
        ]
        peaks = [
            s["peak_mib"] for s in found if s.get("peak_mib") is not None and s.get("status") != "skipped"
        ]
        if len(seconds) != len(records) or len(peaks) != len(records):
            continue
        if provisional:
            budget = (round_up(seconds[0] * 4, 10), round_up(peaks[0] * 2, 50))
        else:
            budget = (round_up(statistics.median(seconds) * 1.5, 10), round_up(max(peaks) * 1.25, 50))
        key = name if re.fullmatch(r"[A-Za-z0-9_-]+", name) else json.dumps(name)
        lines += ["", f"[stage{stage}.steps.{key}]", f"seconds = {budget[0]}", f"mib = {budget[1]}"]
    return "\n".join(lines) + "\n"


def _run_name(record: Mapping[str, Any]) -> str:
    return str(record.get("run") or f"{record.get('date', '')[:10]}@{str(record.get('commit', ''))[:8]}")


# --------------------------------------------------------------------------------------------------
# The page


def _section(page: str, title: str) -> str:
    match = re.search(rf"^## {re.escape(title)}\n(.*?)(?=^## |\Z)", page, re.S | re.M)
    return match.group(1) if match else ""


def _rows(section: str) -> list[list[str]]:
    """The body rows of the first Markdown table of a section."""
    lines = [line.strip() for line in section.splitlines() if line.strip().startswith("|")]
    rows = [[cell.strip() for cell in line.strip("|").split("|")] for line in lines]
    return [row for row in rows[1:] if not all(set(cell) <= set("-: ") for cell in row)]


def page_problems(page: str) -> list[str]:
    """What is wrong with ``docs/evidence/yardstick.md``: a missing section, a stage without exactly one
    state, a row of ``Runs`` without a stage from 1 to 5 or without a verdict."""
    problems = [
        f"the section '## {title}' is missing" for title in PAGE_SECTIONS if not _section(page, title)
    ]
    states: Counter[str] = Counter()
    for row in _rows(_section(page, "Stages")):
        if len(row) < 2 or not row[1].startswith(STAGE_STATES):
            problems.append(f"Stages: the row of stage {row[0]} has no state of {', '.join(STAGE_STATES)}")
        states[row[0]] += 1
    for stage in STAGES:
        if states[str(stage)] != 1:
            problems.append(f"Stages: stage {stage} has {states[str(stage)]} rows, not one")
    for row in _rows(_section(page, "Runs")):
        if len(row) != 10:
            problems.append(f"Runs: a row has {len(row)} cells, not 10: {row[0]}")
        elif row[2] not in {str(stage) for stage in STAGES}:
            problems.append(f"Runs: the row of {row[0]} has the stage {row[2]!r}")
        elif row[8] not in ("passed", "failed"):
            problems.append(f"Runs: the row of {row[0]} has the verdict {row[8]!r}")
    return problems


def row(record: Mapping[str, Any], url: str | None = None) -> str:
    """One row of the ``Runs`` table: date, commit, stage, run, total seconds, largest peak MiB, open
    connections, DRC errors, verdict, note."""
    steps = [step for step in record["steps"] if step.get("status") != "skipped"]
    total = sum(step.get("seconds") or 0 for step in steps)
    peaks = [step["peak_mib"] for step in steps if step.get("peak_mib") is not None]
    drc = dict(record.get("board", {}).get("drc", {}))
    open_count = drc.get("unconnected")
    capped = bool(drc.get("unconnected_capped"))
    errors = sum(count for kind, count in dict(drc.get("errors", {})).items() if kind != UNCONNECTED)
    cells = [
        str(record.get("date", ""))[:10],
        str(record.get("commit", ""))[:8],
        str(record.get("stage", "")),
        url or str(record.get("run") or "local"),
        f"{total:.0f}",
        f"{max(peaks):.0f}" if peaks else "—",
        "—" if open_count is None else (f"≥ {open_count}" if capped else str(open_count)),
        str(errors) if drc else "—",
        str(record.get("verdict", "")),
        "KiCad's report is capped" if capped else "",
    ]
    return "| " + " | ".join(cells) + " |"


# --------------------------------------------------------------------------------------------------
# Running


def run_child(command: Sequence[str], cwd: Path, env: Mapping[str, str], out: Path, err: Path) -> Measured:
    """Run one child process to its end: the exit code, the wall seconds of a monotonic clock and the
    peak resident memory that ``os.wait4`` reports for it (``None`` where the system has no ``wait4``)."""
    start = time.monotonic()
    with out.open("wb") as stdout, err.open("wb") as stderr:
        process = subprocess.Popen(  # noqa: S603
            list(command), cwd=cwd, env=dict(env), stdout=stdout, stderr=stderr, stdin=subprocess.DEVNULL
        )
        wait4 = getattr(os, "wait4", None)
        if wait4 is None:
            return Measured(process.wait(), time.monotonic() - start, None)
        _, status, usage = wait4(process.pid, 0)
        process.returncode = os.waitstatus_to_exitcode(status)
    return Measured(process.returncode, time.monotonic() - start, peak_mib(usage, sys.platform))


def _sha256(path: Path) -> str | None:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None


def _load(path: Path) -> dict[str, Any]:
    try:
        found = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return found if isinstance(found, dict) else {}


def _result(reply: Mapping[str, Any]) -> dict[str, Any]:
    found = reply.get("result")
    return found if isinstance(found, dict) else {}


def _issue_counts(reply: Mapping[str, Any]) -> dict[str, int]:
    """Issue counts by code: the summary of a concise ``check`` reply, else the issues themselves."""
    summary = _result(reply).get("issues_summary")
    if isinstance(summary, list):
        return {str(entry["code"]): int(entry["count"]) for entry in summary}
    counts = Counter(str(issue.get("code")) for issue in reply.get("issues", []) if isinstance(issue, dict))
    return dict(sorted(counts.items()))


class Run:
    """One run of the runner: the folders, the steps taken and what they left."""

    def __init__(self, *, example: Path, out: Path, stage: int, budgets: StageBudgets, corpus: Path) -> None:
        self.example, self.out, self.stage, self.budgets, self.corpus = example, out, stage, budgets, corpus
        self.own = out / RUN_DIR
        self.steps: list[dict[str, Any]] = []
        self.replies: dict[str, dict[str, Any]] = {}
        self.rules: list[dict[str, Any]] = []
        self.board_before_rebuild: str | None = None
        self.dry_changes: list[str] = []

    # ---- paths and text

    def board(self) -> Path | None:
        found = sorted(self.out.glob("*.kicad_pcb"))
        return found[0] if len(found) == 1 else None

    def clean(self, text: str) -> str:
        """``text`` without an absolute path: the folders of the run become placeholders."""
        home = str(Path.home())
        for path, name in (
            (str(self.out.resolve()), "."),
            (str(self.out), "."),
            (str(self.example), "{example}"),
            (str(self.corpus), "{corpus}"),
            (str(ROOT), "{repo}"),
        ):
            text = text.replace(path, name)
        return text.replace(home, "~") if len(home) > 1 else text

    def resolve(self, arg: str) -> str:
        board = self.board()
        return (
            arg.replace("{script}", str(self.example / "design.py"))
            .replace("{corpus}", str(self.corpus))
            .replace("{board}", board.name if board else "{board}")
        )

    # ---- one step

    def skip(self, step: Step, reason: str) -> None:
        self.steps.append(
            {"name": step.name, "args": list(step.args or ()), "status": "skipped", "reason": reason}
        )

    def take(self, step: Step) -> dict[str, Any]:
        assert step.args is not None
        reply_file = self.own / "replies" / (step.name.replace(":", "_") + ".json")
        error_file = reply_file.with_suffix(".stderr")
        env = {key: value for key, value in os.environ.items() if key not in step.drop_env}
        env.setdefault("KICAD_CONFIG_HOME", str(self.own / "kicad-config"))
        if step.base == "rebuild":
            board = self.board()
            self.board_before_rebuild = _sha256(board) if board else None
        command = [*FENOLITE, *(self.resolve(arg) for arg in step.args), "--json"]
        measured = run_child(command, self.out, env, reply_file, error_file)
        reply = _load(reply_file)
        self.replies[step.name] = reply
        if step.base == "rebuild-dry":  # judged against the files as they are now, before the rebuild
            self.dry_changes = sorted(
                str(planned["path"])
                for planned in _result(reply).get("plan", [])
                if not str(planned["path"]).startswith(".fenolite/")
                and _sha256(self.out / str(planned["path"])) != planned.get("sha256")
            )
        entry: dict[str, Any] = {
            "name": step.name,
            "args": [*step.args, "--json"],
            "status": "ok" if measured.exit == step.expect else "failed",
            "exit": measured.exit,
            "expected_exit": step.expect,
            "seconds": round(measured.seconds, 3),
            "peak_mib": None if measured.peak_mib is None else round(measured.peak_mib, 1),
            "reply_bytes": reply_file.stat().st_size,
            "reply": reply_file.relative_to(self.out).as_posix(),
            "issues": _issue_counts(reply),
            "budget": None,
        }
        if measured.exit != step.expect:
            error = _load(error_file)
            entry["error"] = self.clean(f"{error.get('code', '')} {error.get('message', '')}".strip())
        budget = self.budgets.of(step.name)
        if budget is not None:
            entry["budget"] = {"seconds": budget.get("seconds"), "mib": budget.get("mib")}
        self.steps.append(entry)
        return entry

    # ---- rules

    def rule(self, name: str, passed: bool, detail: str = "") -> None:
        text = detail if not passed or detail.startswith("only ") else ""
        self.rules.append({"rule": name, "passed": passed, "detail": self.clean(text)})

    def ran(self, name: str) -> bool:
        return any(step["name"] == name and step["status"] != "skipped" for step in self.steps)

    def judge_exits(self) -> None:
        for step in self.steps:
            if step["status"] == "skipped":
                continue
            detail = "" if step["status"] == "ok" else (
                f"{step['name']} exited {step['exit']}, not {step['expected_exit']}: {step.get('error', '')}"
            )  # fmt: skip
            self.rule(f"exit.{step['name']}", step["status"] == "ok", detail)

    def judge_check(self) -> dict[str, dict[str, Any]]:
        """The stages of ``check``: each that ran is ``ok``, or holds only error types that are accepted
        for it (``unconnected_items`` of ``drc.kicad`` before stage 4 needs no entry). Returns the accepted
        types with their counts."""
        counted: dict[str, dict[str, Any]] = {}
        if not self.ran("check"):
            return counted
        result = _result(self.replies["check"])
        stages = [stage for stage in result.get("stages", []) if isinstance(stage, dict)]
        errors = {
            str(entry["code"]): int(dict(entry.get("by_severity", {})).get("error", 0))
            for entry in result.get("issues_summary", [])
        }
        claimed = {code for stage in stages for code in dict(dict(stage.get("summary", {})).get("types", {}))}
        if not stages:
            self.rule("check.stages", False, "the reply of check holds no stage")
        for stage in stages:
            name, status = str(stage.get("name")), str(stage.get("status"))
            summary = dict(stage.get("summary", {}))
            by_type = dict(summary.get("by_type", {}))
            if name == "drc.kicad" and summary.get("unconnected"):
                by_type.setdefault(UNCONNECTED, summary["unconnected"])
            types = {str(code): str(kind) for code, kind in dict(summary.get("types", {})).items()}
            found = {kind: errors[code] for code, kind in types.items() if errors.get(code)}
            if not types:
                prefix = name.split(".", 1)[0] + "."
                found = {
                    code: n
                    for code, n in errors.items()
                    if n and code.startswith(prefix) and code not in claimed
                }
            allowed = {entry.type: entry for entry in self.budgets.accepted if entry.stage == name}
            for kind, entry in allowed.items():
                count = int(by_type.get(kind, found.get(kind, 0)))
                if count:
                    counted[f"{name}:{kind}"] = {
                        "stage": name,
                        "type": kind,
                        "count": count,
                        "owner": entry.owner,
                        "reason": entry.reason,
                    }
            free = {UNCONNECTED} if name == "drc.kicad" and self.stage < 4 else set()
            refused = sorted(kind for kind in found if kind not in allowed and kind not in free)
            if status == "skipped":
                continue
            if status == "ok" and not refused:
                self.rule(f"check.{name}", True)
            elif refused:
                self.rule(f"check.{name}", False, f"check: {name} holds {', '.join(refused)}")
            elif found:
                self.rule(f"check.{name}", True, f"only {', '.join(sorted(found))}")
            else:
                self.rule(f"check.{name}", False, f"check: {name} is {status} with no finding type")
            if name == "copper.clearance":
                count = int(summary.get("clearance", 0)) + int(summary.get("shorts", 0))
                self.rule(
                    "check.copper.clearance.no-finding", count == 0, f"{count} finding(s)" if count else ""
                )
            if name == "netlist.assignment_compare":
                count = sum(int(pair.get("differences", 0)) for pair in summary.get("pairs", []))
                self.rule(
                    "check.netlist.no-difference", count == 0, f"{count} difference(s)" if count else ""
                )
        return counted

    def judge_manifest(self) -> None:
        if not self.ran("manifest"):
            return
        listed = {
            str(entry.get("path"))
            for entry in _result(self.replies["manifest"]).get("artifacts", [])
            if entry
        }
        written: set[str] = set()
        for step, key in (("export", "artifacts"), ("render", "views")):
            if self.ran(step):
                written |= {f"fab/{entry['path']}" for entry in _result(self.replies[step]).get(key, [])}
        written |= {f"fab/{name}.csv" for name in ("bom", "pnp") if self.ran(name)}
        missing = sorted(written - listed)
        self.rule("manifest.lists-artefacts", not missing, f"the manifest lacks {', '.join(missing)}")

    def judge_rebuild(self) -> None:
        if self.ran("rebuild-dry"):
            changed = self.dry_changes
            self.rule(
                "rebuild-dry.no-write", not changed, f"the dry run plans to change {', '.join(changed)}"
            )
        if self.ran("rebuild"):
            board = self.board()
            after = _sha256(board) if board else None
            same = after is not None and after == self.board_before_rebuild
            name = board.name if board else "the board"
            self.rule(
                "rebuild.board-unchanged", same, "" if same else f"the rebuild changed the bytes of {name}"
            )

    # ---- measures

    def measures(self) -> dict[str, Any]:
        board: dict[str, Any] = {}
        file = self.board()
        if file is not None:
            board["file"] = file.name
            board["bytes"] = file.stat().st_size
            model = self.out / ".fenolite"
            board["fenolite_bytes"] = sum(p.stat().st_size for p in model.rglob("*") if p.is_file())
        stages = {
            str(stage.get("name")): dict(stage.get("summary", {}))
            for stage in _result(self.replies.get("check", {})).get("stages", [])
        }
        if "model.validate" in stages:
            board["parts"] = stages["model.validate"].get("components")
            board["nets"] = stages["model.validate"].get("nets")
        pairs = stages.get("netlist.assignment_compare", {}).get("pairs", [])
        if pairs:
            board["pads"] = pairs[0].get("common")
        layers = stages.get("copper.clearance", {}).get("layers")
        if layers:
            board["copper_layers"] = len(layers)
        if "zone.fill" in stages:
            board["zones"] = {
                key: stages["zone.fill"].get(key) for key in ("zones", "current", "unfilled", "stale")
            }
        summary = _result(self.replies.get("check", {})).get("issues_summary", [])
        severities = {str(entry["code"]): dict(entry.get("by_severity", {})) for entry in summary}
        for name, key in (("drc.kicad", "drc"), ("erc.kicad", "erc")):
            if name not in stages:
                continue
            types = dict(stages[name].get("types", {}))
            found: dict[str, Any] = {"errors": {}, "warnings": {}}
            for code, kind in sorted(types.items()):
                for severity, group in (("error", "errors"), ("warning", "warnings")):
                    if severities.get(code, {}).get(severity):
                        found[group][kind] = severities[code][severity]
            if name == "drc.kicad":
                found["unconnected"] = stages[name].get("unconnected")
                limits = [dict(limit) for limit in stages[name].get("limits", [])]
                found["limits"] = limits
                found["unconnected_capped"] = any(limit.get("type") == UNCONNECTED for limit in limits)
            board[key] = found
        for name, summary_of in stages.items():
            if name.startswith("place."):
                board.setdefault("placement", {})[name] = summary_of
        if "manifest" in self.replies:
            board["artefacts"] = _result(self.replies["manifest"]).get("states")
        cache, install = self.replies.get("build-dry"), self.replies.get("build-install")
        seconds = {step["name"]: step.get("seconds") for step in self.steps if step["status"] == "ok"}
        if cache and install and seconds.get("build-dry") and seconds.get("build-install"):
            board["library_read"] = {
                "cache_seconds": seconds["build-dry"],
                "install_seconds": seconds["build-install"],
                "ratio": round(seconds["build-install"] / seconds["build-dry"], 1),
                "same_board": _plan_board(cache) is not None and _plan_board(cache) == _plan_board(install),
            }
        return board


def _plan_board(reply: Mapping[str, Any]) -> str | None:
    for entry in _result(reply).get("plan", []):
        if str(entry.get("path", "")).endswith(".kicad_pcb"):
            return str(entry.get("sha256"))
    return None


def _commit() -> str:
    done = subprocess.run(  # noqa: S603
        ["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    return done.stdout.strip() or os.environ.get("GITHUB_SHA", "unknown")


def _runner() -> dict[str, Any]:
    memory = None
    try:
        memory = round(os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE") / (1024 * 1024))
    except (AttributeError, OSError, ValueError):
        pass
    return {
        "system": platform.system(),
        "machine": platform.machine(),
        "cpus": os.cpu_count(),
        "memory_mib": memory,
    }


def _tools(reply: Mapping[str, Any]) -> dict[str, Any]:
    result = _result(reply)
    tools = {
        str(name): dict(tool).get("version")
        for name, tool in dict(result.get("tools", {})).items()
        if isinstance(tool, dict)
    }
    routers = [str(router.get("name")) for router in result.get("routers", []) if isinstance(router, dict)]
    return {"fenolite": result.get("fenolite_version"), **tools, "routers": routers}


def run(
    *,
    example: Path = EXAMPLE,
    out: Path,
    budgets_file: Path = BUDGETS,
    record_file: Path | None = None,
    summary_file: Path | None = None,
    only: Sequence[str] = (),
    skip_heavy: bool = False,
) -> tuple[int, dict[str, Any]]:
    """Run the steps of the example's stage and judge them: the exit code (0 or 1) and the record.
    ``Usage`` is raised for what ``main`` turns into exit 2."""
    stage = read_stage(example / "design.py")
    budgets = stage_budgets(load_budgets(budgets_file), stage)
    steps = list(steps_for(stage))
    if skip_heavy:
        steps = [step for step in steps if not step.row]
    if only:
        unknown = sorted(set(only) - {step.name for step in steps} - {step.base for step in steps})
        if unknown:
            raise Usage(f"--only names no step of stage {stage}: {', '.join(unknown)}")
        steps = [step for step in steps if step.name in only or step.base in only]
    pending = [step.name for step in steps if step.args is None]
    if pending:
        raise Usage(f"stage {stage} has steps without a command line on this base: {', '.join(pending)}")
    cache = os.environ.get(LIBS_CACHE, "")
    if not cache or not Path(cache).is_dir():
        raise Usage(
            f"{LIBS_CACHE} names no library cache; fill one with tools/kicad_libs_fetch.py --tag 10.0.6"
        )
    corpus = Path(os.environ.get(CORPUS_CACHE) or Path.home() / ".cache" / "fenolite" / "corpus")
    for step in steps:
        heavy = [arg for arg in step.args or () if arg.startswith("{corpus}/")]
        if heavy and not Path(heavy[0].replace("{corpus}", str(corpus))).is_file():
            raise Usage(
                f"the corpus row {step.row} is not in the corpus cache; fetch it with "
                f"tools/corpus_fetch.py --uses heavy --only {step.row}, or pass --skip-heavy"
            )
    out = out.resolve()
    if not only and out.exists() and any(out.iterdir()):
        raise Usage(f"the output folder {out} is not empty; remove it or name another")
    this = Run(example=example.resolve(), out=out, stage=stage, budgets=budgets, corpus=corpus)
    (this.own / "replies").mkdir(parents=True, exist_ok=True)
    (this.own / "kicad-config").mkdir(exist_ok=True)

    stopped = ""
    for step in steps:
        if stopped and step.base not in _INDEPENDENT:
            this.skip(step, f"{stopped} failed")
            continue
        if any(mark in arg for arg in step.args or () for mark in _NEEDS_BOARD) and this.board() is None:
            this.skip(step, "the project holds no board")
            continue
        entry = this.take(step)
        if step.name == "capabilities":
            tool = dict(_result(this.replies[step.name]).get("tools", {})).get("kicad-cli")
            if entry["status"] != "ok" or not isinstance(tool, dict) or not tool.get("version"):
                raise Usage("capabilities names no kicad-cli; install KiCad 10 or set FENOLITE_KICAD_CLI")
        if entry["status"] != "ok" and step.base in _STOPS_THE_LOOP:
            stopped = step.name

    this.judge_exits()
    accepted = this.judge_check()
    this.judge_manifest()
    this.judge_rebuild()
    record: dict[str, Any] = {
        "schema": SCHEMA,
        "date": datetime.datetime.now(datetime.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": _commit(),
        "stage": stage,
        "run": os.environ.get("GITHUB_RUN_ID"),
        "runner": _runner(),
        "tools": _tools(this.replies.get("capabilities", {})),
        "board": this.measures(),
        "steps": this.steps,
        "rules": this.rules,
        "accepted": [accepted[key] for key in sorted(accepted)],
        "budgets": {"file": budgets_file.name, "source": budgets.source, "findings": []},
        "verdict": "failed",
    }
    findings = judge(record, budgets)
    record["budgets"]["findings"] = [
        {"step": f.step, "measure": f.measure, "value": round(f.value, 3), "budget": f.budget}
        for f in findings
    ]
    failed = [rule for rule in this.rules if not rule["passed"]]
    record["verdict"] = "failed" if failed or findings or stopped else "passed"
    text = summary(record)
    target = record_file or this.own / "record.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if summary_file is not None:
        with summary_file.open("a", encoding="utf-8") as stream:
            stream.write(text)
    return (0 if record["verdict"] == "passed" else 1), record


def summary(record: Mapping[str, Any]) -> str:
    """The Markdown summary of a record: the steps with their budgets, what failed, what was accepted."""

    def cell(value: object, form: str = "{}") -> str:
        return "—" if value is None else form.format(value)

    lines = [
        f"## Yardstick, stage {record['stage']}: {record['verdict']}",
        "",
        f"Commit `{str(record['commit'])[:8]}`, {record['date']}, budgets: {record['budgets']['source']}.",
        "",
        "| step | exit | seconds | budget s | peak MiB | budget MiB | reply bytes |",
        "|---|---|---|---|---|---|---|",
    ]
    for step in record["steps"]:
        if step["status"] == "skipped":
            lines.append(f"| `{step['name']}` | skipped ({step['reason']}) | | | | | |")
            continue
        budget = step.get("budget") or {}
        lines.append(
            f"| `{step['name']}` | {step['exit']} | {cell(step['seconds'], '{:.1f}')} | "
            f"{cell(budget.get('seconds'))} | {cell(step['peak_mib'], '{:.0f}')} | "
            f"{cell(budget.get('mib'))} | {step['reply_bytes']} |"
        )
    failed = [rule for rule in record["rules"] if not rule["passed"]]
    findings = record["budgets"]["findings"]
    if failed or findings:
        lines += ["", "Failed:", ""]
        lines += [f"- `{rule['rule']}`: {rule['detail']}" for rule in failed]
        lines += [
            f"- budget: {Finding(f['step'], f['measure'], f['value'], f['budget']).text()}" for f in findings
        ]
    if record["accepted"]:
        lines += ["", "Accepted findings:", ""]
        lines += [
            f"- `{entry['stage']}` `{entry['type']}`: {entry['count']} (owner: {entry['owner']})"
            for entry in record["accepted"]
        ]
    board = record.get("board", {})
    drc = board.get("drc", {})
    capped = " (its report is capped)" if drc.get("unconnected_capped") else ""
    lines += [
        "",
        f"Board: {cell(board.get('parts'))} parts, {cell(board.get('nets'))} nets, "
        f"{cell(board.get('pads'))} pads on nets, {cell(board.get('copper_layers'))} copper layers; "
        f"KiCad counts {cell(drc.get('unconnected'))} open connections{capped}.",
        "",
    ]
    return "\n".join(lines)


# --------------------------------------------------------------------------------------------------
# Command line


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=(__doc__ or "").split("\n\n")[0])
    commands = parser.add_subparsers(dest="command", required=True)
    run_ = commands.add_parser("run", help="run the steps of the example's stage and judge them")
    run_.add_argument("--example", type=Path, default=EXAMPLE, help="the folder of design.py")
    run_.add_argument("--out", type=Path, required=True, help="the output folder; it becomes the project")
    run_.add_argument("--budgets", type=Path, default=BUDGETS, help="the budgets file")
    run_.add_argument("--record", type=Path, default=None, help="where to write the record (JSON)")
    run_.add_argument("--summary", type=Path, default=None, help="a Markdown file to append the summary to")
    run_.add_argument(
        "--only", default="", metavar="STEP,…", help="run only these steps, on an existing project"
    )
    run_.add_argument("--skip-heavy", action="store_true", help="leave the heavy corpus boards out")
    row_ = commands.add_parser("row", help="print the row of docs/evidence/yardstick.md for a record")
    row_.add_argument("record", type=Path)
    row_.add_argument("--url", default=None, help="the URL of the run")
    rebase_ = commands.add_parser(
        "rebase", help="print the budgets that the rule gives from records, as TOML"
    )
    rebase_.add_argument("records", type=Path, nargs="+")
    rebase_.add_argument("--provisional", action="store_true", help="one local record: seconds x 4, MiB x 2")
    return parser


def _read_record(path: Path) -> dict[str, Any]:
    found = _load(path)
    if found.get("schema") != SCHEMA:
        raise Usage(f"{path.name} is no record of the schema {SCHEMA}")
    return found


def main(argv: list[str] | None = None) -> int:
    try:
        args = _parser().parse_args(argv)
    except SystemExit as stop:
        return 2 if stop.code else 0
    try:
        if args.command == "row":
            print(row(_read_record(args.record), args.url))
            return 0
        if args.command == "rebase":
            print(rebase([_read_record(path) for path in args.records], provisional=args.provisional), end="")
            return 0
        code, record = run(
            example=args.example,
            out=args.out,
            budgets_file=args.budgets,
            record_file=args.record,
            summary_file=args.summary,
            only=tuple(name for name in args.only.split(",") if name),
            skip_heavy=args.skip_heavy,
        )
    except Usage as error:
        print(f"yardstick: {error}", file=sys.stderr)
        return 2
    print(summary(record))
    return code


if __name__ == "__main__":
    sys.exit(main())
