# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Checking a kit folder after a run (capability altium-verification, "Kit result verification";
``docs/altium-kit.md``, "What kit verify checks").

``verify_results`` reads the folder and writes nothing. It checks the kit's own files against ``kit.json``,
the form, every result file and typed value, and scans the result files for strings that look like a home
folder or a login name. The verdict holds one outcome per step and per hypothesis:

- a step is ``pass``, ``fail`` or ``skipped`` (its file is absent, or its value is not typed);
- a hypothesis is ``pass`` when every step that names it passes, ``fail`` when one fails, ``skipped`` when
  one was not done, and ``pending`` when its steps pass but one of them holds a check that waits for a
  change that is not implemented (``steps.PENDING_BLOCKS``): a pending check is never passed silently.

Reading a saved document needs Fenolite's readers and ``equivalent``, which ``verify`` may not import
(``package-layering``): ``judge`` is an argument, and ``fenolite.cli._kit.judge_document`` is the one the
``kit`` command passes.

Stdlib and ``fenolite.core`` only.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Literal, cast

from fenolite.core.io import sha256_bytes
from fenolite.verify.kit.manifest import EXPECTED_FILE, FORM_FILE, FORM_SCHEMA, Kit, load_kit
from fenolite.verify.kit.script import DONE, LOG, log_outcomes
from fenolite.verify.kit.steps import KIT_SAMPLE, PENDING_REASONS, RESULTS, Step

Outcome = Literal["pass", "fail", "skipped"]
HypothesisOutcome = Literal["pass", "fail", "skipped", "pending"]
DocumentJudge = Callable[[str, Path, Path], Sequence[str]]
"""``judge(check, own, saved)``: the problems the machine check ``check`` finds on the file ``saved`` that
a run left, against the kit's document ``own``; empty for a pass."""

JUDGED_CHECKS = frozenset({"resave", "netlist", "parity", "poured", "copper.clearance"})
"""The checks that read a document; the others read text or only look for the file."""
ALTIUM_VERSION = re.compile(r"AD [0-9]+\.[0-9]+")
OS_FAMILIES = ("Windows", "Linux", "macOS")
DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
PENDING_BLOCKS: Mapping[str, tuple[str, ...]] = {}
"""A pending check → the hypotheses whose criterion needs it; they stay ``pending`` while it is."""
SCRIPT_HYPOTHESIS = "H-A-KIT-SCRIPT"
"""Settled only by a run in which the script did every scripted step."""
MAX_PRIVACY_PER_FILE = 20
_ERROR_LINE = re.compile(r"^\s*\[?\s*(fatal error|error)\s*\]?(\s|$)", re.IGNORECASE)
HOME_FOLDER = re.compile(
    r"(?:[A-Za-z]:\\(?:Users|Documents and Settings)\\|/Users/|/home/)[^\\/\x00-\x1f\"'<>|*?:]{1,64}"
)
_LOGIN = re.compile(
    r"(?i)\b(?:user ?name|username|author|login|owner|last ?saved ?by|modified ?by)\s*[=:]\s*"
    r"([^\s\x00-\x1f|=:;,\"'<>]{2,64})"
)


@dataclass(frozen=True, slots=True)
class PrivacyFinding:
    """A string of a result file that looks like personal data: where it is and what it looks like."""

    file: str
    offset: int
    kind: Literal["home-folder", "login-name"]
    text: str


@dataclass(frozen=True, slots=True)
class StepVerdict:
    id: str
    sample: str
    kind: str
    outcome: Outcome
    reasons: tuple[str, ...] = ()
    scripted: bool = False
    pending: tuple[str, ...] = ()
    """The checks of the step that were not run, each with the change it waits for."""


@dataclass(frozen=True, slots=True)
class HypothesisVerdict:
    id: str
    outcome: HypothesisOutcome
    form: bool
    """True when a step that names the row ends in a typed value."""
    steps: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class ResultFile:
    path: str
    sha256: str
    size: int


@dataclass(frozen=True, slots=True)
class KitVerdict:
    """What ``verify_results`` found. ``kit_problems`` are the kit's own files that differ from
    ``kit.json``; ``form_problems`` what is wrong with the form as a whole; ``results`` every file of
    ``results/`` that the run left (the kit's own files there excluded), by path below the kit."""

    kit: Kit
    synthetic: bool
    altium_version: str
    os_family: str
    date: str
    kit_problems: tuple[str, ...]
    form_problems: tuple[str, ...]
    steps: tuple[StepVerdict, ...]
    hypotheses: tuple[HypothesisVerdict, ...]
    privacy: tuple[PrivacyFinding, ...]
    results: tuple[ResultFile, ...]

    @property
    def failed(self) -> tuple[StepVerdict, ...]:
        return tuple(step for step in self.steps if step.outcome == "fail")

    @property
    def passed(self) -> bool:
        """True when the kit's files and the form are sound and every step passed."""
        return (
            not self.kit_problems
            and not self.form_problems
            and all(step.outcome == "pass" for step in self.steps)
        )


def privacy_scan(files: Mapping[str, bytes]) -> tuple[PrivacyFinding, ...]:
    """The strings of ``files`` (path → bytes) that look like a home folder path or a login name, in 8-bit
    and in UTF-16 text, with the file and the byte offset; at most ``MAX_PRIVACY_PER_FILE`` per file."""
    found: list[PrivacyFinding] = []
    for path in sorted(files):
        data = files[path]
        seen: dict[tuple[int, str], PrivacyFinding] = {}
        views = ((data.decode("latin-1"), 1), (data.decode("utf-16-le", errors="replace"), 2))
        for text, width in views:
            for match in HOME_FOLDER.finditer(text):
                seen.setdefault(
                    (match.start() * width, "home-folder"),
                    PrivacyFinding(path, match.start() * width, "home-folder", match.group(0)),
                )
            for match in _LOGIN.finditer(text):
                seen.setdefault(
                    (match.start(1) * width, "login-name"),
                    PrivacyFinding(path, match.start(1) * width, "login-name", match.group(1)),
                )
        found += [seen[key] for key in sorted(seen)][:MAX_PRIVACY_PER_FILE]
    return tuple(found)


def _text(data: bytes) -> str:
    if data.startswith((b"\xff\xfe", b"\xfe\xff")):
        return data.decode("utf-16", errors="replace")
    return data.decode("utf-8-sig", errors="replace")


def _lines(data: bytes) -> list[str]:
    return [line.strip() for line in _text(data).splitlines() if line.strip()]


def _messages(data: bytes) -> list[str]:
    lines = _lines(data)
    if not lines:
        return ["the file is empty: write the line 'no messages' for an empty Messages panel"]
    errors = [line for line in lines if _ERROR_LINE.match(line)]
    return [f"{len(errors)} message(s) of the class Error, the first: {errors[0][:120]}"] if errors else []


def _listing(data: bytes) -> list[str]:
    lines = _lines(data)
    if not lines:
        return ["the file lists no generated file"]
    pathed = [line for line in lines if "/" in line or "\\" in line]
    return [f"{len(pathed)} line(s) hold a folder; write the file names only"] if pathed else []


def form_problems(form: object, steps: Sequence[Step]) -> list[str]:
    """What is wrong with a form as a whole: its schema, the tool version, the system, the date and its
    fields. The values themselves are judged step by step."""
    if not isinstance(form, dict):
        return ["the form is not a JSON object"]
    body = cast(dict[str, Any], form)
    found: list[str] = []
    if body.get("schema") != FORM_SCHEMA:
        found.append(f"the form's schema is not {FORM_SCHEMA}")
    version = body.get("altium_version")
    if not isinstance(version, str) or ALTIUM_VERSION.fullmatch(version) is None:
        found.append("altium_version is not of the form 'AD <major>.<minor>'")
    if body.get("os_family") not in OS_FAMILIES:
        found.append(f"os_family is not one of {', '.join(OS_FAMILIES)}")
    date = body.get("date")
    if not isinstance(date, str) or DATE.fullmatch(date) is None:
        found.append("date is not of the form YYYY-MM-DD")
    if not isinstance(body.get("synthetic"), bool):
        found.append("synthetic is not true or false")
    values = body.get("values")
    wanted = sorted(step.result for step in steps if step.kind == "form")
    if not isinstance(values, dict) or sorted(cast(dict[str, Any], values)) != wanted:
        found.append("values does not hold exactly one field per form step of the kit")
    unknown = sorted(set(body) - {"schema", "altium_version", "os_family", "date", "synthetic", "values"})
    if unknown:
        found.append(f"unknown field(s): {', '.join(unknown)}")
    return found


def _typed(step: Step, value: object) -> tuple[Outcome, tuple[str, ...]]:
    if value is None:
        return "skipped", ("no value is typed",)
    kinds: Mapping[str, type] = {"bool": bool, "int": int, "text": str}
    kind = kinds[cast(str, step.value_type)]
    if type(value) is not kind:
        return "fail", (f"the value {value!r} is not of the type {step.value_type}",)
    if value != step.expected:
        return "fail", (f"the value is {value!r}; expected {step.expected!r}",)
    return "pass", ()


def _pending(step: Step) -> tuple[str, ...]:
    return tuple(
        f"{name}: pending on {change} ({PENDING_REASONS.get(change, 'not implemented')})"
        for name, change in sorted(step.pending.items())
    )


def _file_step(step: Step, root: Path, judge: DocumentJudge) -> tuple[Outcome, tuple[str, ...]]:
    saved = root.joinpath(RESULTS, *PurePosixPath(step.result).parts)
    if not saved.is_file():
        return "skipped", (f"{RESULTS}/{step.result} does not exist",)
    data = saved.read_bytes()
    if not data:
        return "fail", (f"{RESULTS}/{step.result} is empty",)
    own = root.joinpath(*PurePosixPath(step.document).parts)
    reasons: list[str] = []
    for check in step.checks:
        if check in JUDGED_CHECKS:
            reasons += [f"{check}: {text}" for text in judge(check, own, saved)]
        elif check == "messages":
            reasons += [f"{check}: {text}" for text in _messages(data)]
        elif check == "listing":
            reasons += [f"{check}: {text}" for text in _listing(data)]
    return ("fail", tuple(reasons)) if reasons else ("pass", ())


def _hypotheses(kit: Kit, steps: Sequence[StepVerdict]) -> tuple[HypothesisVerdict, ...]:
    by_id = {verdict.id: verdict for verdict in steps}
    named: dict[str, list[Step]] = {}
    for step in kit.steps:
        for ident in step.hypotheses:
            named.setdefault(ident, []).append(step)
    found: list[HypothesisVerdict] = []
    for ident in sorted(named):
        members = named[ident]
        outcomes = [by_id[step.id].outcome for step in members]
        outcome: HypothesisOutcome
        if "fail" in outcomes:
            outcome = "fail"
        elif "skipped" in outcomes:
            outcome = "skipped"
        elif any(ident in PENDING_BLOCKS.get(name, ()) for step in members for name in step.pending):
            outcome = "pending"
        elif ident == SCRIPT_HYPOTHESIS and not all(by_id[step.id].scripted for step in members):
            outcome = "skipped"
        else:
            outcome = "pass"
        found.append(
            HypothesisVerdict(
                ident, outcome, any(step.kind == "form" for step in members), tuple(s.id for s in members)
            )
        )
    return tuple(found)


def verify_results(folder: Path, *, judge: DocumentJudge) -> KitVerdict:
    """The verdict on the kit folder ``folder`` after a run; nothing is written. ``FormatError`` when the
    folder holds no ``kit.json``."""
    root = Path(folder)
    kit = load_kit(root)
    changed: dict[str, str] = {}
    for path, digest in sorted(kit.files.items()):
        target = root.joinpath(*PurePosixPath(path).parts)
        if not target.is_file():
            changed[path] = f"{path} is missing"
        elif sha256_bytes(target.read_bytes()) != digest:
            changed[path] = f"{path} differs from its digest in kit.json"
    touched = {path.split("/", 1)[0] for path in changed}

    form: object = None
    whole: list[str] = []
    form_path = root.joinpath(*PurePosixPath(FORM_FILE).parts)
    if not form_path.is_file():
        whole.append(f"{FORM_FILE} does not exist")
    else:
        try:
            form = json.loads(form_path.read_text(encoding="utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            whole.append(f"{FORM_FILE} is not JSON: {exc}")
        else:
            whole += form_problems(form, kit.steps)
    body = cast(dict[str, Any], form) if isinstance(form, dict) else {}
    values = cast(dict[str, Any], body["values"]) if isinstance(body.get("values"), dict) else {}

    log_path = root.joinpath(*PurePosixPath(LOG).parts)
    log = log_outcomes(_text(log_path.read_bytes())) if log_path.is_file() else {}

    verdicts: list[StepVerdict] = []
    for step in kit.steps:
        scripted = step.scripted and log.get(step.id) == DONE
        folder_name = step.document.split("/", 1)[0] if step.sample == KIT_SAMPLE else step.sample
        if folder_name in touched:
            outcome: Outcome = "fail"
            reasons: tuple[str, ...] = (
                f"the kit file {sorted(p for p in changed if p.startswith(folder_name + '/'))[0]} differs "
                "from its manifest: build the kit again and repeat the run",
            )
        elif step.kind == "form":
            outcome, reasons = _typed(step, values.get(step.result))
        else:
            outcome, reasons = _file_step(step, root, judge)
        verdicts.append(
            StepVerdict(step.id, step.sample, step.kind, outcome, reasons, scripted, _pending(step))
        )

    own = {path for path in kit.files if path.startswith(RESULTS + "/")}
    held: dict[str, bytes] = {}
    results_dir = root / RESULTS
    if results_dir.is_dir():
        for path in sorted(results_dir.rglob("*")):
            rel = path.relative_to(root).as_posix()
            if path.is_file() and rel not in own and path.name != EXPECTED_FILE:
                held[rel] = path.read_bytes()
    return KitVerdict(
        kit=kit,
        synthetic=body.get("synthetic") is not False,
        altium_version=body["altium_version"] if isinstance(body.get("altium_version"), str) else "",
        os_family=body["os_family"] if isinstance(body.get("os_family"), str) else "",
        date=body["date"] if isinstance(body.get("date"), str) else "",
        kit_problems=tuple(changed[path] for path in sorted(changed)),
        form_problems=tuple(whole),
        steps=tuple(verdicts),
        hypotheses=_hypotheses(kit, verdicts),
        privacy=privacy_scan(held),
        results=tuple(ResultFile(path, sha256_bytes(data), len(data)) for path, data in sorted(held.items())),
    )


__all__ = [
    "ALTIUM_VERSION",
    "JUDGED_CHECKS",
    "OS_FAMILIES",
    "PENDING_BLOCKS",
    "SCRIPT_HYPOTHESIS",
    "HOME_FOLDER",
    "DocumentJudge",
    "HypothesisVerdict",
    "KitVerdict",
    "PrivacyFinding",
    "ResultFile",
    "StepVerdict",
    "form_problems",
    "privacy_scan",
    "verify_results",
]
