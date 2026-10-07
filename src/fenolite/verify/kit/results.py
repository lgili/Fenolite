# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Checking a kit folder after a run (capability altium-verification, "Kit result verification";
``docs/altium-kit.md``, "What kit verify checks").

``verify_results`` reads the folder and writes nothing. It checks the kit's own files against ``kit.json``,
the form, every result file and typed value, and scans the result files for strings that look like a home
folder, any other absolute path of the machine, or a login name. The verdict holds one outcome per step
and per hypothesis:

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


_PART = r"[^\\/\x00-\x1f\x7f-\x9f\"'<>|*?:=;,]"
"""One character of a folder or file name, in 8-bit text of any Western code page or in UTF-16."""
_SEP = r"(?:\\{1,2}|/)"
DRIVE_PATH = re.compile(
    rf"(?<![A-Za-z0-9_])[A-Za-z]:{_SEP}(?! ){_PART}{{1,80}}(?:{_SEP}{_PART}{{1,80}}){{0,40}}"
)
"""A path that starts at a drive letter, with ``\\``, a doubled ``\\`` (escaped text) or ``/`` between
its parts: ``D:\\work\\kit\\flat.PcbDoc``, ``file:///E:/kit/drc.html``."""
SHARE_PATH = re.compile(
    r"(?<![\\:A-Za-z0-9_])\\\\(?:\\\\)?[A-Za-z0-9._$-]{2,64}" + rf"(?:\\{{1,2}}{_PART}{{1,80}}){{1,40}}"
)
"""A path on a share: two backslashes (four in escaped text), a server name and at least one part."""
POSIX_PATH = re.compile(
    r"(?<![A-Za-z0-9_.:<~/\\-])/(?!/)[A-Za-z][A-Za-z0-9._+@~-]{1,63}(?:/[A-Za-z0-9._+@~-]{1,80}){1,40}"
)
"""A path from the root of a POSIX system with at least two parts, the first starting with a letter; it
does not follow a letter, a digit, a colon or ``<``, so a web address, a date, a fraction, a closing tag
and a stream name such as ``Board6/Data`` are not one."""
MIN_PATH_TEXT = 3
"""The least number of characters after the root that make a drive path: fewer are taken for bytes that
only look like one."""


@dataclass(frozen=True, slots=True)
class PrivacyFinding:
    """A string of a result file that looks like personal data: where it is and what it looks like."""

    file: str
    offset: int
    kind: Literal["home-folder", "absolute-path", "login-name"]
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
    ``kit.json`` (a project file that was only saved again is in ``resaved`` instead); ``form_problems``
    what is wrong with the form as a whole; ``results`` every file of ``results/`` that the run left (the
    kit's own files there excluded), by path below the kit."""

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
    resaved: tuple[str, ...] = ()
    """The project files of the kit's samples whose bytes are not the manifest's and that still list
    exactly their sample's documents: the tool saved them again (``saved_again``). They fail nothing."""

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


def _texty(text: str) -> bool:
    """True for a match that reads as text: bytes of a compressed stream give short runs with odd signs."""
    plain = sum(1 for char in text if char.isalnum() or char in " ._-\\/:()")
    return plain * 10 >= len(text) * 9


def absolute_paths(text: str) -> list[tuple[int, str]]:
    """``(index, path)`` of every absolute path of ``text`` that is under no home folder."""
    found: list[tuple[int, str]] = []
    for pattern in (DRIVE_PATH, SHARE_PATH, POSIX_PATH):
        for match in pattern.finditer(text):
            path = match.group(0).rstrip(" .")
            rest = path[3:] if pattern is DRIVE_PATH else path
            if len(rest) >= MIN_PATH_TEXT and _texty(path) and HOME_FOLDER.match(path) is None:
                found.append((match.start(), path))
    return found


def privacy_scan(files: Mapping[str, bytes]) -> tuple[PrivacyFinding, ...]:
    """What a published archive of ``files`` (path → bytes) would give away about the machine of the run:
    the strings that look like a home folder (``home-folder``), like any other absolute path of that
    machine, on a drive, on a share or from a POSIX root (``absolute-path``), and like a login name
    (``login-name``), each with the file and the byte offset; at most ``MAX_PRIVACY_PER_FILE`` per file.

    A file is read three times: as 8-bit text, which finds a string in ASCII, in the code page of an
    Altium record and in UTF-8, and as UTF-16 from its first and from its second byte, which finds a wide
    string at any alignment. A relative path, a stream name and a web address are not reported."""
    found: list[PrivacyFinding] = []
    for path in sorted(files):
        data = files[path]
        seen: dict[tuple[int, str], PrivacyFinding] = {}
        views = (
            (data.decode("latin-1"), 1, 0),
            (data.decode("utf-16-le", errors="replace"), 2, 0),
            (data[1:].decode("utf-16-le", errors="replace"), 2, 1),
        )
        for text, width, shift in views:
            for match in HOME_FOLDER.finditer(text):
                offset = match.start() * width + shift
                seen.setdefault(
                    (offset, "home-folder"), PrivacyFinding(path, offset, "home-folder", match.group(0))
                )
            for index, name in absolute_paths(text):
                offset = index * width + shift
                seen.setdefault(
                    (offset, "absolute-path"), PrivacyFinding(path, offset, "absolute-path", name)
                )
            for match in _LOGIN.finditer(text):
                offset = match.start(1) * width + shift
                seen.setdefault(
                    (offset, "login-name"), PrivacyFinding(path, offset, "login-name", match.group(1))
                )
        found += [seen[key] for key in sorted(seen)][:MAX_PRIVACY_PER_FILE]
    return tuple(found)


PROJECT_SUFFIX = ".prjpcb"
_SECTION = re.compile(r"\[([^\]\r\n]*)\]")
_DOCUMENT_SECTION = re.compile(r"Document[0-9]+")
_DOCUMENT_KEY = "documentpath"
_UTF8_MARK = b"\xef\xbb\xbf"
"""The byte-order mark that a project file saved by Altium Designer 26 starts with; Fenolite writes none."""


def project_documents(data: bytes) -> list[str] | None:
    """The document paths that the bytes of an Altium project file list, in file order: the value of
    ``DocumentPath`` of each section ``[Document<n>]``. ``None`` for bytes that are no project file: no
    section ``[Design]``, or a byte that no line of text holds. A UTF-8 byte-order mark before the first
    section is skipped: the project file that the first manual run returned starts with one.

    A project file is text in sections of ``key=value`` lines (``docs/formats/altium/project.md``). This
    reads only what the manifest check needs; the product's reader is ``backends.altium.read.project``,
    which ``verify`` may not import, and a test holds the two equal on the kit's projects."""
    if b"\x00" in data:
        return None
    section = ""
    seen_design = False
    documents: list[str] = []
    for line in data.removeprefix(_UTF8_MARK).decode("latin-1").splitlines():
        line = line.strip()
        head = _SECTION.fullmatch(line)
        if head is not None:
            section = head.group(1)
            seen_design = seen_design or section.casefold() == "design"
            continue
        key, equals, value = line.partition("=")
        if equals and key.strip().casefold() == _DOCUMENT_KEY and _DOCUMENT_SECTION.fullmatch(section):
            documents.append(value.strip())
    return documents if seen_design else None


def sample_documents(kit: Kit, project: str) -> list[str]:
    """The documents of the sample whose project file is the kit file ``project``: the names of the kit's
    files in the same folder, the project file left out, sorted."""
    folder = project.rsplit("/", 1)[0] + "/"
    names = [path[len(folder) :] for path in kit.files if path.startswith(folder) and path != project]
    return sorted(name for name in names if "/" not in name)


def saved_again(kit: Kit, path: str, data: bytes) -> bool:
    """True when ``data``, the bytes found at the kit path ``path`` with another digest than the
    manifest's, are a sample's project file that the tool saved again: ``path`` is ``<sample>/<name>.PrjPcb``
    of a sample, and the bytes list exactly that sample's documents, each by its name in the sample's
    folder. Altium writes the project file again, with every key it knows, when the project is saved;
    the documents are what the steps open."""
    sample, _, name = path.partition("/")
    if sample not in kit.samples or "/" in name or not name.casefold().endswith(PROJECT_SUFFIX):
        return False
    listed = project_documents(data)
    if listed is None:
        return False
    return sorted(item.casefold() for item in listed) == sorted(
        item.casefold() for item in sample_documents(kit, path)
    )


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


def _strays(saved: Path, asked: frozenset[str], root: Path) -> list[str]:
    """The files beside the absent result file ``saved`` that have its name with another ending and that
    no step asks for: a document of another kind saved in the place of the one the step wants."""
    if not saved.parent.is_dir():
        return []
    return sorted(
        other.name
        for other in saved.parent.iterdir()
        if other.is_file()
        and other.stem.casefold() == saved.stem.casefold()
        and other.relative_to(root / RESULTS).as_posix() not in asked
    )


def _file_step(
    step: Step, root: Path, judge: DocumentJudge, asked: frozenset[str] = frozenset()
) -> tuple[Outcome, tuple[str, ...]]:
    saved = root.joinpath(RESULTS, *PurePosixPath(step.result).parts)
    if not saved.is_file():
        strays = _strays(saved, asked, root)
        if strays:
            return "fail", (
                f"{RESULTS}/{step.result} does not exist, and the folder holds {', '.join(strays)}, which no "
                f"step asks for: the step wants {saved.name}, not another document of the project",
            )
        return "skipped", (f"{RESULTS}/{step.result} does not exist",)
    data = saved.read_bytes()
    if not data:
        return "fail", (f"{RESULTS}/{step.result} is empty",)
    own = root.joinpath(*PurePosixPath(step.document).parts)
    reasons: list[str] = []
    told: set[str] = set()
    for check in step.checks:
        if check in JUDGED_CHECKS:
            # two checks of one step may find the same thing (a file of another kind): it is said once
            found = [text for text in judge(check, own, saved) if text not in told]
            told.update(found)
            reasons += [f"{check}: {text}" for text in found]
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
    resaved: list[str] = []
    for path, digest in sorted(kit.files.items()):
        target = root.joinpath(*PurePosixPath(path).parts)
        if not target.is_file():
            changed[path] = f"{path} is missing"
            continue
        data = target.read_bytes()
        if sha256_bytes(data) == digest:
            continue
        if saved_again(kit, path, data):
            resaved.append(path)
        else:
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

    asked = frozenset(step.result for step in kit.steps if step.kind == "file")
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
            outcome, reasons = _file_step(step, root, judge, asked)
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
        resaved=tuple(resaved),
    )


__all__ = [
    "ALTIUM_VERSION",
    "DRIVE_PATH",
    "JUDGED_CHECKS",
    "OS_FAMILIES",
    "PENDING_BLOCKS",
    "POSIX_PATH",
    "SHARE_PATH",
    "SCRIPT_HYPOTHESIS",
    "HOME_FOLDER",
    "DocumentJudge",
    "HypothesisVerdict",
    "KitVerdict",
    "absolute_paths",
    "PrivacyFinding",
    "ResultFile",
    "StepVerdict",
    "form_problems",
    "privacy_scan",
    "project_documents",
    "sample_documents",
    "saved_again",
    "verify_results",
]
