# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Read-only intake of authored Part F/J observations, with the kit's privacy scan first.

Reports contain hashes, counts, format member names and positions only. They are measurements by
Fenolite, never a native application verdict. A refused scan reports no matched private text.

A person who reviewed the absolute folder that a native run wrote into its files may name exactly that one
folder with ``FENOLITE_KIT_REVIEWED_PREFIX`` (or ``reviewed_prefix=``): a finding whose matched text is that
folder or lies under it counts as ``reviewed`` and does not refuse; every other finding still refuses. The
prefix itself is never reported, only the count of reviewed findings. Unset, nothing changes.
"""

from __future__ import annotations

import hashlib
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

from fenolite.backends.altium.read.draftsman import decode, read_draftsman, summary
from fenolite.backends.altium.roundtrip import diff_records
from fenolite.backends.base import Change
from fenolite.verify.kit.results import privacy_scan

_SUFFIXES = frozenset((".pcbdwf", ".dwfdot", ".pcbdoc", ".pcblib", ".schdoc", ".schlib", ".prjpcb", ".pdf"))
_F0_BASE = {2: 1, 3: 1, 4: 3, 5: 1, 6: 5, 7: 1, 8: 1, 9: 5, 10: 7, 11: 1, 12: 5, 13: 10}


REVIEWED_PREFIX_ENV = "FENOLITE_KIT_REVIEWED_PREFIX"
_ABSOLUTE = re.compile(r"(?:[A-Za-z]:[\\/]|\\\\[^\\/]|/)")
_SEPARATORS = re.compile(r"[\\/]+")


class ObservationError(ValueError):
    """An observation set is ambiguous, missing, malformed, or needs local privacy review."""


def _folder_key(path: str) -> str:
    """``path`` with each run of separators as one ``/`` and no trailing one (a share keeps ``//`` in
    front); a drive or share path, which Windows compares without case, is case-folded. ``C:\\\\Kit\\\\A``
    and ``c:/kit/a`` give the same key."""
    key = _SEPARATORS.sub("/", path).rstrip("/")
    if path.startswith("\\"):
        return "/" + key.casefold()
    return key if path.startswith("/") else key.casefold()


def reviewed_prefix(value: str | None = None) -> str | None:
    """The folder key of the one reviewed prefix: ``value``, else ``FENOLITE_KIT_REVIEWED_PREFIX``, else
    ``None``. It must be one absolute folder below a root: a drive, a share or a POSIX root alone, a
    relative path or a list refuses (the message never holds the value)."""
    text = os.environ.get(REVIEWED_PREFIX_ENV) if value is None else value
    if text is None or text == "":
        return None
    key = _folder_key(text.strip())
    if (
        text != text.strip()
        or _ABSOLUTE.match(text) is None
        or any(char in text for char in ';\n\r\t\x00*?"<>|')
        or len([part for part in key.split("/") if part]) < 2
    ):
        raise ObservationError(f"{REVIEWED_PREFIX_ENV} must name exactly one absolute folder below a root")
    return key


def _reviewed(text: str, prefix: str | None) -> bool:
    if prefix is None:
        return False
    key = _folder_key(text)
    return key == prefix or key.startswith(prefix + "/")


def scan_folder(folder: Path, reviewed: str | None = None) -> tuple[dict[str, bytes], int]:
    """The files of ``folder`` that the intake reads, and how many privacy findings lie under the reviewed
    prefix (``reviewed``, see ``reviewed_prefix``). Raw files and decoded Draftsman chunks are scanned
    before any document member is interpreted; any other finding refuses."""
    prefix = reviewed_prefix(reviewed)
    if folder.is_symlink() or not folder.is_dir():
        raise ObservationError("observations need a real directory")
    found: dict[str, bytes] = {}
    scan: dict[str, bytes] = {}
    for path in sorted(folder.rglob("*")):
        if path.is_symlink():
            raise ObservationError("observation folders must contain no symbolic links")
        if not path.is_file() or path.suffix.casefold() not in _SUFFIXES:
            continue
        name = path.relative_to(folder).as_posix()
        data = path.read_bytes()
        found[name] = data
        scan[name] = data
    raw = [finding for finding in privacy_scan(scan) if not _reviewed(finding.text, prefix)]
    if raw:
        raise ObservationError(
            f"kit privacy scan requires local review ({len(raw)} finding(s)); no member read"
        )
    for name, data in found.items():
        if Path(name).suffix.casefold() in (".pcbdwf", ".dwfdot"):
            scan[name + "#decoded"] = decode(data)[1]
    findings = privacy_scan(scan)
    decoded = [finding for finding in findings if not _reviewed(finding.text, prefix)]
    if decoded:
        raise ObservationError(
            f"decoded kit privacy scan requires local review ({len(decoded)} finding(s)); no member read"
        )
    return found, len(findings)


def checked_files(folder: Path, reviewed: str | None = None) -> dict[str, bytes]:
    """Scan raw files and decoded Draftsman chunks before interpreting any document member
    (``scan_folder``, whose reviewed prefix ``reviewed`` defaults to ``FENOLITE_KIT_REVIEWED_PREFIX``)."""
    return scan_folder(folder, reviewed)[0]


def _privacy(count: int) -> dict[str, object]:
    """The report's privacy fields: counts only, never a matched text or the reviewed prefix."""
    return {"privacy_scan": "reviewed" if count else "passed", "privacy_reviewed": count}


def _members(root: ET.Element) -> dict[str, tuple[str, tuple[tuple[str, str], ...]]]:
    found: dict[str, tuple[str, tuple[tuple[str, str], ...]]] = {}

    def visit(element: ET.Element, path: str) -> None:
        found[path] = (element.text or "", tuple(sorted(element.attrib.items())))
        counts: Counter[str] = Counter()
        for child in element:
            tag = child.tag.rsplit("}", 1)[-1]
            index = counts[tag]
            counts[tag] += 1
            visit(child, f"{path}/{tag}[{index}]")

    visit(root, "Document")
    return found


def observe_f0(folder: Path, reviewed: str | None = None) -> dict[str, object]:
    """F0 hashes and structural differences from each authored control, without content values."""
    files, count = scan_folder(folder, reviewed)
    cases: dict[int, tuple[str, bytes]] = {}
    for name, data in files.items():
        match = re.fullmatch(r"F0-(0[1-9]|1[0-3])\.(?:PCBDwf|DwfDot)", Path(name).name, re.I)
        if match is None:
            continue
        case = int(match[1])
        if case in cases:
            raise ObservationError(f"more than one file for F0.{case}")
        cases[case] = (name, data)
    roots = {case: read_draftsman(data).root for case, (_, data) in cases.items()}
    rows: list[dict[str, object]] = []
    for case, (name, data) in sorted(cases.items()):
        root = roots[case]
        base = _F0_BASE.get(case)
        changed: list[str] | None = None
        if base in roots:
            before, after = _members(roots[base]), _members(root)
            changed = sorted(key for key in before.keys() | after.keys() if before.get(key) != after.get(key))
        scope = summary(read_draftsman(data))
        rows.append(
            {
                "case": f"F0.{case}",
                "file": name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "elements": sum(1 for _ in root.iter()),
                "sheets": len(scope.sheets),
                "items": dict(sorted(Counter(i.kind for s in scope.sheets for i in s.items).items())),
                "control": None if base is None else f"F0.{base}",
                "changed_members": changed,
            }
        )
    return {
        "schema": "fenolite.altium-observations.v0",
        "round": "F0",
        "native_verdict": "unjudged",
        "evidence": "INFERRED",
        **_privacy(count),
        "files": rows,
        "missing": [f"F0.{n}" for n in range(1, 14) if n not in cases],
    }


def observe_j(folder: Path, reviewed: str | None = None) -> dict[str, object]:
    """Separate a native plain resave from record edits; never infer index-maintenance rules."""
    files, count = scan_folder(folder, reviewed)
    by_name: dict[str, tuple[str, bytes]] = {}
    for name, data in files.items():
        key = Path(name).name.casefold()
        if key in by_name:
            raise ObservationError("observation file basenames must be unique")
        by_name[key] = (name, data)
    rows: list[dict[str, object]] = []
    for key, (name, data) in sorted(by_name.items()):
        match = re.fullmatch(r"j(\d\d)-[^.]+\.(pcbdoc|pcblib|schdoc)", key)
        if match is None:
            continue
        case, suffix = int(match[1]), match[2]
        if case not in range(1, 22):
            continue
        base = "j01-resave.pcbdoc" if suffix == "pcbdoc" and case != 1 else f"edit.{suffix}"
        if case == 17:
            base = next(
                (name for name in by_name if name.startswith("j16-") and name.endswith(".pcbdoc")), ""
            )
        held = by_name.get(base)
        counts: dict[str, int] | None = None
        resaved: list[Change] = []
        if held is not None:
            report = diff_records(
                held[1],
                data,
                kind={"pcbdoc": "altium_pcbdoc", "pcblib": "altium_pcblib", "schdoc": "altium_schdoc_binary"}[
                    suffix
                ],
                resave=resaved,
            )
            counts = dict(sorted(Counter(change.change for change in report.changes).items()))
        rows.append(
            {
                "case": f"J{case}",
                "file": name,
                "sha256": hashlib.sha256(data).hexdigest(),
                "control": None if held is None else held[0],
                "changes_by_kind": counts,
                "resave_changes": len(resaved) if held is not None else None,
            }
        )
    return {
        "schema": "fenolite.altium-observations.v0",
        "round": "J",
        "native_verdict": "unjudged",
        "evidence": "INFERRED",
        **_privacy(count),
        "files": rows,
    }


__all__ = [
    "REVIEWED_PREFIX_ENV",
    "ObservationError",
    "checked_files",
    "observe_f0",
    "observe_j",
    "reviewed_prefix",
    "scan_folder",
]
