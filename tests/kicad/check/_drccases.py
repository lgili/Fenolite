# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Probes of change c0020 on DRC findings (capability kicad-oracle, "DRC finding facts proved per
major"): the ``drc-type-*``, ``drc-sev-*``, ``drc-ignored-checks-*`` and ``drc-item-uuids`` rows of
``_probes.PROBES``, settling ``H-K-DRC-TYPES``, ``H-K-PRO-SEV`` and ``H-K-DRC-UUID``.

Each case writes its project with ``_fixtures`` into a fresh temporary folder, runs ``pcb drc`` once per
session on the project's copy set, and reads the report. The ``clearance`` cases run c0018's overlap
bench, whose canary must fire; the ignored ``clearance`` run cannot carry a canary (ignoring the type
removes the canary's violation too), so it is judged against its fired pair (Decision 20).
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from functools import cache
from pathlib import Path

import _fixtures as fx
import _rulebench as rb
import _rulecases
from _checkcases import plain_drc, workdir
from _projects import STEM

from fenolite.backends.base import DrcReport, DrcViolation
from fenolite.backends.kicad.pcb import read_board

TYPES = ("clearance", "shorting_items", "unconnected_items")
"""Each type with its fixture: the overlap bench, the bridging track and the missing track."""
FIXTURES: dict[str, Callable[..., Path]] = {
    "clearance": fx.overlap_bench,
    "shorting_items": fx.bridging,
    "unconnected_items": fx.missing_track,
}
UUID = re.compile(r'\(uuid "?([0-9a-fA-F-]{36})"?\)')


def _major() -> int:
    return _rulecases.major()


def _slug(type_: str) -> str:
    return type_.replace("_", "-")


@cache
def project(type_: str, value: str = "") -> Path:
    """The fixture of ``type_`` for the running major, with its severity set to ``value`` when given."""
    root = FIXTURES[type_](workdir(f"drc-{_slug(type_)}-{value or 'default'}"), major=_major())
    if value:
        fx.with_severity(root, type_, value)
    return root


@cache
def report(type_: str, value: str = "") -> DrcReport | None:
    return plain_drc(project(type_, value)).report


def entries(found: DrcReport, type_: str) -> tuple[DrcViolation, ...]:
    return found.of_type(type_)


def _canary(found: DrcReport) -> bool:
    return rb.canary_fired(found, _rulecases.order_bench())


def _pair_ok(type_: str) -> bool:
    """For ``clearance``: the default run's canary fired, and the ignored project differs from the default
    one only in the severity key."""
    if type_ != "clearance":
        return True
    default = report(type_)
    if default is None or not _canary(default):
        return False
    files = [project(type_, v) / f"{STEM}.kicad_pro" for v in ("", "ignore")]
    plain, ignored = (json.loads(f.read_text(encoding="utf-8")) for f in files)
    severities = ignored.get("board", {}).get("design_settings", {}).get("rule_severities", {})
    if severities.pop(type_, None) != "ignore":
        return False
    return _without_empty(ignored) == _without_empty(plain)


def _without_empty(data: dict[str, object]) -> dict[str, object]:
    """``data`` with empty dictionaries removed, so ``{}`` and ``{"board": {...: {}}}`` compare equal."""
    out: dict[str, object] = {}
    for key, value in data.items():
        if isinstance(value, dict):
            value = _without_empty(value)  # type: ignore[arg-type]
            if not value:
                continue
        out[key] = value
    return out


def type_present(type_: str) -> str:
    found = report(type_)
    if found is None or (type_ == "clearance" and not _canary(found)):
        return "inconclusive"
    return "present" if entries(found, type_) else "absent"


def type_ignored(type_: str) -> str:
    found = report(type_, "ignore")
    if found is None or not _pair_ok(type_):
        return "inconclusive"
    return "present" if entries(found, type_) else "absent"


def severity(type_: str, value: str) -> str:
    """``equal`` when every entry of ``type_`` has severity ``value`` (and there is one), else
    ``different``."""
    found = report(type_, value)
    if found is None or (type_ == "clearance" and not _canary(found)):
        return "inconclusive"
    got = entries(found, type_)
    return "equal" if got and all(v.severity == value for v in got) else "different"


def ignored_checks(type_: str) -> str:
    found = report(type_, "ignore")
    if found is None or not _pair_ok(type_):
        return "inconclusive"
    return "present" if type_ in found.ignored_checks else "absent"


def pad_names(root: Path) -> dict[str, str]:
    """``pad uuid → REF-PIN`` of the project's written board."""
    design = read_board((root / f"{STEM}.kicad_pcb").read_text(encoding="utf-8"))
    assert design.board is not None
    refs = {c.id: c.ref for c in design.circuit.components}
    return {
        p.native_ids["kicad"]: f"{refs[fp.component_id]}-{p.number}"
        for fp in design.board.footprints
        for p in fp.pads
    }


def board_uuids(root: Path) -> frozenset[str]:
    text = (root / f"{STEM}.kicad_pcb").read_text(encoding="utf-8")
    return frozenset(m.lower() for m in UUID.findall(text))


def _pads_of(found: tuple[DrcViolation, ...], names: dict[str, str]) -> list[frozenset[str]]:
    return [frozenset(names[i.uuid] for i in v.items if i.uuid in names) for v in found]


def item_uuids() -> str:
    """``equal`` when every item uuid of the bridging and missing-track entries is a uuid of the written
    board, the short names ``R1-2`` and the missing connection names ``R1-2`` and ``D1-2``."""
    cases = (("shorting_items", frozenset({"R1-2"})), ("unconnected_items", frozenset({"R1-2", "D1-2"})))
    for type_, pads in cases:
        found = report(type_)
        if found is None:
            return "inconclusive"
        got = entries(found, type_)
        root = project(type_)
        if not got or any(i.uuid.lower() not in board_uuids(root) for v in got for i in v.items):
            return "different"
        if pads not in _pads_of(got, pad_names(root)):
            return "different"
    return "equal"


def drc_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    both = (9, 10)
    probes: dict[str, tuple[Callable[[], str], tuple[int, ...]]] = {"drc-item-uuids": (item_uuids, both)}
    for type_ in TYPES:
        slug = _slug(type_)
        probes[f"drc-type-{slug}"] = (lambda t=type_: type_present(t), both)
        probes[f"drc-type-{slug}-ignored"] = (lambda t=type_: type_ignored(t), both)
        for value in ("warning", "error"):
            probes[f"drc-sev-{slug}-{value}"] = (lambda t=type_, v=value: severity(t, v), both)
        probes[f"drc-ignored-checks-{slug}"] = (lambda t=type_: ignored_checks(t), (10,))
    return probes


__all__ = [
    "TYPES",
    "board_uuids",
    "drc_probes",
    "entries",
    "ignored_checks",
    "item_uuids",
    "pad_names",
    "project",
    "report",
    "severity",
    "type_ignored",
    "type_present",
]
