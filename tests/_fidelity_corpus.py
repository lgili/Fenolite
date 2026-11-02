# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""External-only fidelity project descriptors and exact count ratchets (c0278)."""

from __future__ import annotations

import hashlib
import re
import tomllib
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Any
from urllib.parse import unquote, urlparse

from _corpus import manifest_items, require

from fenolite.checks.equivalence.model import KINDS
from fenolite.library.licences import shipped

SCHEMA = "fenolite.fidelity-ratchet.v0"
ATTRIBUTIONS = frozenset(("fenolite", "upstream", "tool", "undecided"))
COUNT_KEYS = frozenset(f"{level}:{kind}" for level, kind, _ in KINDS)
SUFFIXES = frozenset((".kicad_pcb", ".kicad_pro", ".kicad_sch", ".kicad_dru"))
_RESTRICTED = re.compile(r"(?:\bNC\b|\bND\b|non[- ]?commercial|no[- ]?derivatives)", re.I)


def _path(row: Mapping[str, Any]) -> PurePosixPath:
    return PurePosixPath(unquote(urlparse(str(row["url"])).path))


def _family_path(row: Mapping[str, Any]) -> PurePosixPath:
    path = _path(row)
    if "demos" in path.parts:
        return PurePosixPath(*path.parts[path.parts.index("demos") + 1 :])
    return path


def _same_ref(row: Mapping[str, Any], ref: str) -> bool:
    return row["ref"] == ref or bool(
        re.search(r"\bidentical at tag " + re.escape(ref) + r"\b", str(row.get("notes", "")), re.I)
    )


def _allowed(row: Mapping[str, Any]) -> bool:
    return shipped().deny_reason(str(row["license"])) is None and not _RESTRICTED.search(
        str(row["license_variant"])
    )


def rtf_roots(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Every allow-listed KiCad demo board, including heavy rows and both registered versions."""
    return [row for row in rows if "origin:kicad-demos" in row["uses"]
            and _path(row).suffix == ".kicad_pcb" and _allowed(row)]  # fmt: skip


def project_rows(board: Mapping[str, Any], rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """Declared inputs beneath the upstream folder, at the same ref or an explicitly identical tag.

    Another board in the folder is not copied: verify-source receives one explicit original. Paths and
    file names stay in external descriptors, never in a count baseline or evidence table.
    """
    url = urlparse(str(board["url"]))
    prefix = _family_path(board).parent
    found = []
    for row in rows:
        other = urlparse(str(row["url"]))
        path = _family_path(row)
        if not _same_ref(row, str(board["ref"])) or (other.scheme, other.netloc) != (url.scheme, url.netloc):
            continue
        if "origin:kicad-demos" not in row["uses"] or not path.is_relative_to(prefix) or not _allowed(row):
            continue
        if row["id"] == board["id"] or path.suffix in SUFFIXES - {".kicad_pcb"}:
            found.append(row)
    return sorted(found, key=lambda row: row["id"])


def rtf_ids(rows: Sequence[dict[str, Any]]) -> frozenset[str]:
    return frozenset(row["id"] for board in rtf_roots(rows) for row in project_rows(board, rows))


def rtf_problems(rows: Sequence[dict[str, Any]]) -> list[str]:
    wanted = rtf_ids(rows)
    problems = []
    for row in rows:
        tagged = "rtf" in row["uses"]
        if tagged and not _allowed(row):
            problems.append(
                f"{row['id']}: rtf forbids licence {row['license']} {row['license_variant']}".rstrip()
            )
        elif tagged != (row["id"] in wanted):
            state = "lacks" if row["id"] in wanted else "carries"
            problems.append(f"{row['id']}: {state} rtf; it marks exactly allow-listed demo project inputs")
    return problems


def materialize(board: Mapping[str, Any], rows: Sequence[dict[str, Any]], folder: Path) -> Path:
    """Copy only SHA-declared cached inputs into ``folder``; missing resources retain require's rules."""
    cached = {item.id: item for item in manifest_items("rtf")}
    require(cached[str(board["id"])])  # heavy input/resource checks happen before any copy
    prefix = _family_path(board).parent
    for row in project_rows(board, rows):
        path = _family_path(row)
        if path.parent == prefix and path.suffix in (".kicad_pro", ".kicad_dru"):
            if path.stem != _path(board).stem:
                continue  # an unrouted variant is not the other board's project
        relative = path.relative_to(prefix)
        assert not relative.is_absolute() and ".." not in relative.parts
        source = require(cached[row["id"]])
        target = folder.joinpath(*relative.parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        data = source.read_bytes()
        assert hashlib.sha256(data).hexdigest() == row["sha256"], f"{row['id']}: cached SHA-256 changed"
        target.write_bytes(data)
    project = folder / _path(board).with_suffix(".kicad_pro").name
    return project if project.is_file() else folder


def load_ratchet(path: Path) -> dict[str, Any]:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    if data.get("schema") != SCHEMA or set(data) - {"schema", "run", "row", "pending"}:
        raise ValueError("invalid fidelity ratchet schema or members")
    seen = set()
    for row in data.get("row", []):
        if set(row) != {"id", "counts", "reason", "attribution"}:
            raise ValueError("a ratchet row holds only id, counts, reason and attribution")
        ident = row["id"]
        if ident in seen or not re.fullmatch(r"kicad-demo-[0-9-]+-pcb-\d{2}", ident):
            raise ValueError("ratchet ids must be unique opaque corpus board ids")
        seen.add(ident)
        if not row["reason"].strip() or row["attribution"] not in ATTRIBUTIONS:
            raise ValueError(f"{ident}: ratchet needs a reason and closed attribution")
        if any(key not in COUNT_KEYS or type(value) is not int or value <= 0
               for key, value in row["counts"].items()):  # fmt: skip
            raise ValueError(f"{ident}: ratchet counts need known level/kind keys and positive integers")
    pending = data.get("pending", {})
    if seen & pending.keys() or any(not str(reason).strip() for reason in pending.values()):
        raise ValueError("a row is measured or pending, never both; pending rows need a reason")
    return data


def ratchet_problems(ident: str, counts: Mapping[str, int], baseline: Mapping[str, int]) -> list[str]:
    """Both directions fail: improvements require lowering the reviewed baseline too."""
    problems = []
    for key in sorted(counts.keys() | baseline.keys()):
        now, allowed = counts.get(key, 0), baseline.get(key, 0)
        if now > allowed:
            problems.append(f"{ident}: {key} grew from {allowed} to {now}")
        elif now < allowed:
            problems.append(f"{ident}: {key} fell from {allowed} to {now}; lower the ratchet entry")
    return problems


__all__ = ["SCHEMA", "load_ratchet", "materialize", "project_rows", "ratchet_problems", "rtf_ids",
           "rtf_problems", "rtf_roots"]  # fmt: skip
