# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""``PROVENANCE.json`` of a library item (schema ``fenolite.provenance.v0``; change c0279,
``docs/library-repo.md``, "Provenance").

The record says where an item came from (``origin``: ``converted``, ``authored`` or ``seeded``), under
which licence, how it was converted (tools, replayable steps, the outputs tree), and, for a board, the
fidelity proof of change c0278 (member ``fidelity``). It embeds c0275's import record (member ``import``)
verbatim. :func:`provenance_problems` lists every rule a record breaks, each naming its field.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, cast

from fenolite.library.items import SHA256, TREE, Item

PROVENANCE_SCHEMA = "fenolite.provenance.v0"
IMPORT_SCHEMA = "fenolite.import-provenance.v0"
ORIGINS: tuple[str, ...] = ("converted", "authored", "seeded")
TOOLS: tuple[str, ...] = ("fenolite", "kicad-cli")
"""The tools a conversion step may name; ``library replay`` refuses any other."""
EVIDENCE_LABELS = re.compile(
    r"KICAD-VERIFIED|ORACLE-VERIFIED\([^()]+\)|CORPUS-VERIFIED|ALTIUM-VERIFIED\((kit|author-report)\)"
    r"|INFERRED|UNKNOWN|UNVERIFIED"
)
COMMIT = re.compile(r"[0-9a-f]{40}")
DATED = re.compile(r"(\d{4}-\d{2}-\d{2}): \S")
"""A dated modification notice starts with its date: ``2026-10-30: converted …``."""
PLAN_FLAG = "--plan"
"""A step never holds it: a plan id hashes its working folder and cannot replay elsewhere (c0281)."""


def _is_text_list(value: object, *, empty: bool = True) -> bool:
    if not isinstance(value, list):
        return False
    items = cast(list[object], value)
    return (empty or bool(items)) and all(isinstance(v, str) and v for v in items)


def step_problems(steps: object) -> list[str]:
    """The rules ``conversion.steps`` breaks: a list of ``{tool, argv}`` with ``tool`` in ``TOOLS``,
    ``argv`` a list of strings, and no ``--plan`` (a writing step is recorded with ``--confirm``)."""
    if not isinstance(steps, list) or not steps:
        return ["conversion.steps: a non-empty list of {tool, argv}"]
    problems: list[str] = []
    for index, raw in enumerate(cast(list[object], steps), start=1):
        where = f"conversion.steps[{index}]"
        if not isinstance(raw, dict):
            problems.append(f"{where}: an object of tool and argv")
            continue
        step = cast(dict[str, object], raw)
        tool = step.get("tool")
        if tool not in TOOLS:
            problems.append(f"{where}: the tool {tool!r} is not one of {', '.join(TOOLS)}")
        argv = step.get("argv")
        if not isinstance(argv, list) or not all(isinstance(a, str) for a in cast(list[object], argv)):
            problems.append(f"{where}: argv is a list of strings")
            continue
        words = cast(list[str], argv)
        if any(word == PLAN_FLAG or word.startswith(PLAN_FLAG + "=") for word in words):
            problems.append(
                f"{where}: holds --plan; a plan id hashes its working folder, so a writing step is "
                "recorded with --confirm alone"
            )
    return problems


def _upstream_problems(upstream: object, *, full: bool) -> list[str]:
    if not isinstance(upstream, dict):
        return ["upstream: an object with url and commit"]
    table = cast(dict[str, object], upstream)
    problems: list[str] = []
    url = table.get("url")
    if not isinstance(url, str) or not url.startswith(("https://", "http://", "file://")):
        problems.append(f"upstream.url: an address, not {url!r}")
    commit = table.get("commit")
    if not isinstance(commit, str) or not COMMIT.fullmatch(commit):
        problems.append(f"upstream.commit: a full 40-hex commit, not {commit!r}")
    if not full:
        return problems
    archive = table.get("archive_sha256")
    if archive is not None and (not isinstance(archive, str) or not SHA256.fullmatch(archive)):
        problems.append("upstream.archive_sha256: null or a SHA-256")
    for key in ("path", "retrieved", "spdx_expression", "source_location"):
        if not isinstance(table.get(key), str):
            problems.append(f"upstream.{key}: a string")
    return problems


def _conversion_problems(conversion: object) -> list[str]:
    if not isinstance(conversion, dict):
        return ["conversion: an object with tools, steps and outputs_tree"]
    table = cast(dict[str, object], conversion)
    problems: list[str] = []
    tools = table.get("tools")
    if not isinstance(tools, list) or not tools:
        problems.append("conversion.tools: a non-empty list of {name, version}")
    else:
        for index, raw in enumerate(cast(list[object], tools), start=1):
            row = cast(dict[str, object], raw) if isinstance(raw, dict) else {}
            if row.get("name") not in TOOLS or not isinstance(row.get("version"), str):
                problems.append(
                    f"conversion.tools[{index}]: name is one of {', '.join(TOOLS)}, with a version"
                )
    problems += step_problems(table.get("steps"))
    tree = table.get("outputs_tree")
    if not isinstance(tree, str) or not TREE.fullmatch(tree):
        problems.append(f"conversion.outputs_tree: fenolite-tree-1:<64 hex>, not {tree!r}")
    return problems


def _fidelity_problems(fidelity: object) -> list[str]:
    if not isinstance(fidelity, dict):
        return ["fidelity: c0278's member (accepted and proof) is required for a board"]
    table = cast(dict[str, object], fidelity)
    problems: list[str] = []
    if not isinstance(table.get("accepted", []), list):
        problems.append("fidelity.accepted: a list")
    proof = table.get("proof")
    if not isinstance(proof, dict) or not isinstance(cast(dict[str, object], proof).get("levels"), dict):
        problems.append("fidelity.proof.levels: a status per level")
    return problems


def provenance_problems(record: Mapping[str, Any], item: Item | None = None) -> list[str]:
    """Every rule of ``fenolite.provenance.v0`` that ``record`` breaks, and every disagreement with the
    item's manifest, each naming its field (and both values)."""
    problems: list[str] = []
    if record.get("schema") != PROVENANCE_SCHEMA:
        problems.append(f"schema: must be {PROVENANCE_SCHEMA!r}")
    if item is not None:
        for key in ("kind", "id", "version", "spdx"):
            mine, theirs = record.get(key), getattr(item, key)
            if mine != theirs:
                problems.append(f"{key}: PROVENANCE.json says {mine!r} and item.json says {theirs!r}")
    origin = record.get("origin")
    if origin not in ORIGINS:
        problems.append(f"origin: one of {', '.join(ORIGINS)}, not {origin!r}")
    spdx = record.get("spdx")
    if not isinstance(spdx, str):
        problems.append("spdx: one allow-listed SPDX id")
    notice = record.get("modification_notice")
    if not isinstance(notice, str) or not DATED.match(notice):
        problems.append("modification_notice: a dated notice 'YYYY-MM-DD: <what changed>'")
    if not _is_text_list(record.get("authors"), empty=False):
        problems.append("authors: a non-empty list of names as given upstream")
    if not _is_text_list(record.get("copyright", [])):
        problems.append("copyright: a list of the upstream copyright lines")
    digest = record.get("licence_text_sha256")
    if digest is not None and (not isinstance(digest, str) or not SHA256.fullmatch(digest)):
        problems.append("licence_text_sha256: the SHA-256 of the normalised LICENSE")
    evidence = record.get("evidence", "UNVERIFIED")
    if not isinstance(evidence, str) or not EVIDENCE_LABELS.fullmatch(evidence):
        problems.append(f"evidence: an evidence label, not {evidence!r}")
    trademarks = record.get("trademarks", {"marks": [], "restricted": False, "note": ""})
    if (
        not isinstance(trademarks, dict)
        or not isinstance(cast(dict[str, object], trademarks).get("restricted", False), bool)
        or not _is_text_list(cast(dict[str, object], trademarks).get("marks", []))
    ):
        problems.append("trademarks: {marks: [...], restricted: true|false, note}")
    featured = record.get("featured")
    if featured is not None and (
        not isinstance(featured, dict)
        or not isinstance(cast(dict[str, object], featured).get("permission"), str)
    ):
        problems.append("featured: null or {permission: <public link>, date}")
    review = record.get("licence_review")
    if review is not None and (
        not isinstance(review, dict)
        or not all(isinstance(cast(dict[str, object], review).get(k), str) for k in ("by", "date", "note"))
    ):
        problems.append("licence_review: null or {by, date, note}")
    if origin == "converted":
        problems += _upstream_problems(record.get("upstream"), full=True)
        problems += _conversion_problems(record.get("conversion"))
        imported = record.get("import")
        if not isinstance(imported, dict) or cast(dict[str, object], imported).get("schema") != IMPORT_SCHEMA:
            problems.append(f"import: c0275's record of schema {IMPORT_SCHEMA!r}, verbatim")
        else:
            licence = cast(dict[str, object], imported).get("licence")
            if licence is not None and licence != spdx:
                problems.append(f"import.licence: says {licence!r} and spdx says {spdx!r}")
        kind = record.get("kind")
        if kind == "board":
            problems += _fidelity_problems(record.get("fidelity"))
    elif origin == "authored":
        if record.get("upstream") is not None:
            problems.append("upstream: null for an authored item")
        if not _is_text_list(record.get("sources"), empty=False):
            problems.append("sources: the D- source ids of sources.toml that the authored item uses")
    elif origin == "seeded":
        problems += _upstream_problems(record.get("upstream"), full=False)
    return problems


def upstream_host(record: Mapping[str, Any]) -> str:
    """The host of ``upstream.url`` in lower case, or ``""``."""
    upstream = record.get("upstream")
    if not isinstance(upstream, dict):
        return ""
    url = cast(dict[str, object], upstream).get("url")
    if not isinstance(url, str) or "://" not in url:
        return ""
    return url.split("://", 1)[1].split("/", 1)[0].split("@")[-1].split(":")[0].lower()


def vendor_bundled(record: Mapping[str, Any]) -> bool:
    """Whether the item is marked as an example bundled with commercial CAD software."""
    upstream = record.get("upstream")
    return isinstance(upstream, dict) and cast(dict[str, object], upstream).get("vendor_bundled") is True


def notice_dated(record: Mapping[str, Any]) -> str | None:
    """The date of the modification notice, or ``None``."""
    notice = record.get("modification_notice")
    found = DATED.match(notice) if isinstance(notice, str) else None
    return None if found is None else found.group(1)


def steps_of(record: Mapping[str, Any]) -> Sequence[Mapping[str, Any]]:
    conversion = record.get("conversion")
    steps = cast(dict[str, object], conversion).get("steps") if isinstance(conversion, dict) else None
    return cast(list[Mapping[str, Any]], steps) if isinstance(steps, list) else []


__all__ = [
    "COMMIT",
    "IMPORT_SCHEMA",
    "ORIGINS",
    "PLAN_FLAG",
    "PROVENANCE_SCHEMA",
    "TOOLS",
    "notice_dated",
    "provenance_problems",
    "step_problems",
    "steps_of",
    "upstream_host",
    "vendor_bundled",
]
