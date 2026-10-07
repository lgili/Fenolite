# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""What every error code and issue code means and what to do about it (capability cli-contract, "Explain
command").

The texts live in ``data/explain.toml``, one table per code, written for Fenolite from its code and its
docs. ``TABLES`` names every issue-code table of the package; a test keeps the names, the codes and the
entries in step, so a new code without an explanation fails the suite.
"""

from __future__ import annotations

import importlib
import tomllib
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from importlib import resources
from typing import Any, Literal, cast

from fenolite.cli.errors import REGISTRY

TABLES: tuple[tuple[str, str], ...] = (
    ("fenolite.analysis.codes", "ISSUE_CODES"),
    ("fenolite.backends.altium.adapter.codes", "IMPORT_ISSUE_CODES"),
    ("fenolite.backends.altium.read.pcbprops", "PCB_READ_ISSUE_CODES"),
    ("fenolite.backends.altium.read.sch.issues", "ISSUE_CODES"),
    ("fenolite.backends.altium.read.sheet", "ISSUE_CODES"),
    ("fenolite.backends.kicad.copper", "COPPER_ISSUE_CODES"),
    ("fenolite.backends.kicad.erc", "ISSUE_CODES"),
    ("fenolite.backends.kicad.fill", "ISSUE_CODES"),
    ("fenolite.backends.kicad.frame", "FRAME_ISSUE_CODES"),
    ("fenolite.backends.kicad.liberrors", "ISSUE_CODES"),
    ("fenolite.backends.kicad.mod", "WRITE_ISSUE_CODES"),
    ("fenolite.backends.kicad.pcb", "ISSUE_CODES"),
    ("fenolite.backends.kicad.pcb", "WRITE_ISSUE_CODES"),
    ("fenolite.backends.kicad.proerrors", "ISSUE_CODES"),
    ("fenolite.backends.kicad.rulemap", "RULE_ISSUE_CODES"),
    ("fenolite.backends.kicad.sch", "ISSUE_CODES"),
    ("fenolite.backends.kicad.sch", "WRITE_ISSUE_CODES"),
    ("fenolite.backends.kicad.sch_netlist", "ISSUE_CODES"),
    ("fenolite.backends.kicad.schgen", "ISSUE_CODES"),
    ("fenolite.backends.kicad.stackup", "MERGE_ISSUE_CODES"),
    ("fenolite.backends.kicad.stackup", "READ_ISSUE_CODES"),
    ("fenolite.backends.kicad.stackup", "WRITE_ISSUE_CODES"),
    ("fenolite.backends.kicad.wks", "ISSUE_CODES"),
    ("fenolite.backends.kicad.zones", "MERGE_ISSUE_CODES"),
    ("fenolite.backends.kicad.zones", "PAD_ZONE_ISSUE_CODES"),
    ("fenolite.backends.specctra.dsn", "ISSUE_CODES"),
    ("fenolite.checks.codes", "ISSUE_CODES"),
    ("fenolite.checks.equivalence.codes", "ISSUE_CODES"),
    ("fenolite.checks.parity", "PARITY_ISSUE_CODES"),
    ("fenolite.cli.cmd_doctor", "ISSUE_CODES"),
    ("fenolite.cli.cmd_fmt", "ISSUE_CODES"),
    ("fenolite.cli.cmd_kit", "ISSUE_CODES"),
    ("fenolite.cli.cmd_restore", "ISSUE_CODES"),
    ("fenolite.cli.cmd_roundtrip", "ISSUE_CODES"),
    ("fenolite.exports.codes", "ISSUE_CODES"),
    ("fenolite.lens.altium", "ALTIUM_ISSUE_CODES"),
    ("fenolite.lens.altium_copper", "COPPER_ISSUE_CODES"),
    ("fenolite.lens.build", "BUILD_ISSUE_CODES"),
    ("fenolite.lens.preserve", "PRESERVE_ISSUE_CODES"),
    ("fenolite.lens.sync", "SYNC_ISSUE_CODES"),
    ("fenolite.model.design", "MODEL_ISSUE_CODES"),
    ("fenolite.placement.codes", "ISSUE_CODES"),
    ("fenolite.routing.codes", "ISSUE_CODES"),
    ("fenolite.templates.spec", "ISSUE_CODES"),
)
"""``(module, name)`` of every mapping of the package whose name ends in ``ISSUE_CODES``, sorted."""

ORACLES = ("kicad",)
"""The oracle names that stand for ``<oracle>`` in the keys of the check tables."""
ORACLE = "<oracle>"
FAMILY_SUFFIX = ".*"
SEVERITY_ORDER = ("error", "warning", "info")
Kind = Literal["error", "issue"]


@dataclass(frozen=True, slots=True)
class Explanation:
    """The explanation of one code. ``family`` names the family entry that explains it, or is ``""``."""

    code: str
    kind: Kind
    meaning: str
    fix: str
    see: str
    family: str = ""


def _spelled(key: str) -> list[str]:
    """The codes a table key stands for: ``<oracle>`` by each oracle, a ``<type>`` suffix as a family."""
    head, bracket, _ = key.rpartition(".<")
    if bracket:  # ``<oracle>.drc.<type>``: every code of the family ``<oracle>.drc.*``
        key = head + FAMILY_SUFFIX
    if ORACLE not in key:
        return [key]
    return [key.replace(ORACLE, oracle) for oracle in ORACLES]


@cache
def all_codes() -> Mapping[str, tuple[str, ...]]:
    """Every code of ``TABLES`` and of the FEN registry → its severities (none for an error code). A
    family is one key that ends in ``.*``."""
    found: dict[str, set[str]] = {code: set() for code in REGISTRY}
    for module, name in TABLES:
        table = cast(Mapping[str, Any], getattr(importlib.import_module(module), name))
        for key, value in table.items():
            severities = (value,) if isinstance(value, str) else tuple(value)
            for code in _spelled(key):
                found.setdefault(code, set()).update(severities)
    return {code: tuple(s for s in SEVERITY_ORDER if s in found[code]) for code in sorted(found)}


@cache
def entries() -> Mapping[str, Mapping[str, str]]:
    """The tables of ``data/explain.toml``: code → ``meaning``, ``fix`` and ``see``."""
    text = resources.files("fenolite.cli").joinpath("data", "explain.toml").read_text(encoding="utf-8")
    return cast(Mapping[str, Mapping[str, str]], tomllib.loads(text))


def family_of(code: str) -> str:
    """The family key ``<prefix>.*`` of ``all_codes()`` that ``code`` belongs to, the longest first, or
    ``""``."""
    families = [key for key in all_codes() if key.endswith(FAMILY_SUFFIX)]
    for family in sorted(families, key=len, reverse=True):
        prefix = family[: -len(FAMILY_SUFFIX)]
        if code.startswith(prefix + ".") and len(code) > len(prefix) + 1:
            return family
    return ""


def explain(code: str) -> Explanation | None:
    """The explanation of ``code``: its own entry, else the entry of its family, else ``None``."""
    known = all_codes()
    table = entries()
    family = ""
    if code in known and code in table and not code.endswith(FAMILY_SUFFIX):
        key = code
    else:
        family = code if code in known and code.endswith(FAMILY_SUFFIX) else family_of(code)
        if not family:
            return None
        key = family
    entry = table.get(key)
    if entry is None:
        return None
    kind: Kind = "error" if code in REGISTRY else "issue"
    return Explanation(code, kind, entry["meaning"], entry["fix"], entry["see"], family)


__all__ = ["TABLES", "Explanation", "all_codes", "entries", "explain", "family_of"]
