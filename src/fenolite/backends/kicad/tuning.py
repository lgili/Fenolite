# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""KiCad 10 tuning profiles for impedance targets: written into a project and read back (change c0105).

Facts: ``docs/formats/kicad/project.md``, "Tuning profiles". A profile is an entry of
``tuning_profiles.tuning_profiles_impedance_geometric``, named by the class key ``tuning_profile``; the key
names and value kinds are those of the bench that ``pcb drc`` 10.0.6 loaded and judged on 2026-10-05
(``H-K-PRO-TUNING-DRC``; owed: the probes ``pro-tuning-*`` of ``tests/kicad/impedance/_zbench.py``), and
no source document states them; the key set of a GUI save is ``INFERRED`` until ``H-K-PRO-TUNING-KEYS``
is settled. KiCad 9 has no profile: a target-9
project is returned unchanged, and the derived rules of the design check the geometry on both majors.

The script wins, as for class values: a profile named like a target is replaced, the other profiles are
kept in place, and none is deleted.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, cast

from fenolite.backends.kicad import _json
from fenolite.backends.kicad._json import JsonNumber, JsonObject
from fenolite.backends.kicad.proerrors import project_issue
from fenolite.core.errors import Issue
from fenolite.core.evidence import Evidence, Level
from fenolite.core.ids import derived_id
from fenolite.model.design import Design
from fenolite.model.rules import ImpedanceTarget, RuleSet, TraceGeometry

PROFILES_POINTER = "/tuning_profiles/tuning_profiles_impedance_geometric"
CLASS_KEY = "tuning_profile"
PROFILE_KEY_PATHS: frozenset[str] = frozenset(
    {
        "/tuning_profiles/tuning_profiles_impedance_geometric",
        "/tuning_profiles/tuning_profiles_impedance_geometric/*",
        "/tuning_profiles/tuning_profiles_impedance_geometric/*/*",
        "/net_settings/classes/*/tuning_profile",
    }
)
"""The key paths this module governs for target 10; ``*/*`` stands for every path below an entry. They
are taken out of the template-value, added-path and keep rules of the project writer."""
ENTRY_KEYS: tuple[str, ...] = (
    "profile_name",
    "type",
    "target_impedance",
    "enable_time_domain_tuning",
    "layer_entries",
    "via_prop_delay",
    "via_overrides",
)
"""The keys of a profile as ``lower_profile`` writes them (``meta.version`` 0, the 10.0.6 template)."""
LAYER_KEYS: tuple[str, ...] = (
    "signal_layer",
    "top_reference_layer",
    "bottom_reference_layer",
    "width",
    "diff_pair_gap",
    "delay",
)
TYPES = {"single": 0, "differential": 1}
EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-PRO-TUNING-DRC", "H-K-PRO-TUNING-KEYS"))


def _number(text: str) -> JsonNumber:
    return JsonNumber(text if text else "0")


def lower_profile(target: ImpedanceTarget) -> JsonObject:
    """The entry of ``tuning_profiles_impedance_geometric`` for ``target``: its name, type 0 or 1, the
    exact text of ``ohms`` (``0`` when empty), no time-domain tuning, one layer entry per row in stack order
    (with one reference, it is the bottom one), widths and gaps as integer nanometres, delays 0."""
    entries: list[JsonObject] = []
    for row in target.layers:
        refs = row.references
        top, bottom = (refs[0], refs[1]) if len(refs) == 2 else ("", refs[0] if refs else "")
        entries.append(
            {
                "signal_layer": row.layer,
                "top_reference_layer": top,
                "bottom_reference_layer": bottom,
                "width": JsonNumber(str(row.width)),
                "diff_pair_gap": JsonNumber(str(row.gap if target.kind == "differential" and row.gap else 0)),
                "delay": JsonNumber("0"),
            }
        )
    return {
        "profile_name": target.name,
        "type": JsonNumber(str(TYPES[target.kind])),
        "target_impedance": _number(target.ohms),
        "enable_time_domain_tuning": False,
        "layer_entries": entries,
        "via_prop_delay": JsonNumber("0"),
        "via_overrides": [],
    }


def _object(parent: JsonObject, key: str, where: str) -> JsonObject:
    value = parent.setdefault(key, {})
    if not isinstance(value, dict):
        raise ValueError(f"{where} is not an object")
    return cast(JsonObject, value)


def apply_profile_keys(text: str, design: Design, *, target: int, issues: list[Issue] | None = None) -> str:
    """``text`` with the impedance targets of ``design`` written as tuning profiles (target 10 only): a
    profile named like a target is replaced in place, the other targets are appended sorted by name, every
    other profile is kept; the class key of each class of a target names the target, and
    ``kicad.project.profile-reassigned`` reports a class that named another non-empty profile."""
    found = issues if issues is not None else []
    targets = design.rules.impedance if design.rules is not None else ()
    if target != 10 or not targets:
        return text
    data = _json.loads(text)
    holder = _object(data, "tuning_profiles", "/tuning_profiles")
    holder.setdefault("meta", {"version": JsonNumber("0")})
    raw = holder.setdefault("tuning_profiles_impedance_geometric", [])
    if not isinstance(raw, list):
        raise ValueError(f"{PROFILES_POINTER} is not a list")
    profiles = cast(list[Any], raw)
    lowered = {t.name: lower_profile(t) for t in targets}
    placed: set[str] = set()
    for index, entry in enumerate(profiles):
        name = cast(JsonObject, entry).get("profile_name") if isinstance(entry, dict) else None
        if isinstance(name, str) and name in lowered and name not in placed:
            profiles[index] = lowered[name]
            placed.add(name)
    profiles.extend(lowered[name] for name in sorted(lowered) if name not in placed)
    by_id = {c.id: c.name for c in design.circuit.netclasses}
    owner = {by_id[i]: t.name for t in targets for i in t.netclass_ids if i in by_id}
    settings = _object(data, "net_settings", "/net_settings")
    classes = settings.get("classes")
    for index, entry in enumerate(cast(list[Any], classes) if isinstance(classes, list) else []):
        if not isinstance(entry, dict):
            continue
        item = cast(JsonObject, entry)
        name = item.get("name")
        if not isinstance(name, str) or name not in owner:
            continue
        old = item.get(CLASS_KEY)
        if isinstance(old, str) and old and old != owner[name]:
            found.append(
                project_issue(
                    "kicad.project.profile-reassigned",
                    f"net class {name} named the tuning profile {old!r}; it now names {owner[name]!r}, the "
                    "impedance target of the script",
                    where=f"/net_settings/classes/{index}/{CLASS_KEY}",
                    hint=f"the profile {old!r} is kept in the project",
                )
            )
        item[CLASS_KEY] = owner[name]
    return _json.dumps(data)


@dataclass(frozen=True, slots=True)
class ProfileEntry:
    """One layer entry of a profile as read: its layer, references (non-empty, as written), width and
    gap in nm."""

    layer: str
    references: tuple[str, ...]
    width: int
    gap: int


@dataclass(frozen=True, slots=True)
class TuningProfile:
    """A profile of ``tuning_profiles_impedance_geometric`` as read: its name, kind, the text of its
    target impedance (``""`` for 0), and the entries that could be read."""

    name: str
    kind: str
    ohms: str
    entries: tuple[ProfileEntry, ...]
    index: int


def _nm(value: Any) -> int | None:
    """A width or gap as written (an integer of nanometres, ``350000.0`` included), or ``None``."""
    if not isinstance(value, JsonNumber):
        return None
    try:
        number = Decimal(value.text)
    except InvalidOperation:
        return None
    if number != number.to_integral_value() or number < 0:
        return None
    return int(number)


def _ohms(value: Any) -> str | None:
    if not isinstance(value, JsonNumber):
        return None
    number = Decimal(value.text)
    if number < 0:
        return None
    if number == 0:
        return ""
    text = format(number.normalize(), "f")
    return text


def read_profiles(data: JsonObject, *, issues: list[Issue] | None = None) -> tuple[TuningProfile, ...]:
    """The tuning profiles of a project tree. An entry that is not an object or lacks a key of the written
    form, a profile without a string name or a known type, and a width or gap that is not a whole number
    of nanometres, give ``kicad.project.unread-entry`` and are skipped."""
    found = issues if issues is not None else []
    raw = _json.get(data, PROFILES_POINTER)
    profiles: list[TuningProfile] = []
    for index, entry in enumerate(cast(list[Any], raw) if isinstance(raw, list) else []):
        where = f"{PROFILES_POINTER}/{index}"
        item = cast(JsonObject, entry) if isinstance(entry, dict) else None
        name = item.get("profile_name") if item is not None else None
        kind = item.get("type") if item is not None else None
        ohms = _ohms(item.get("target_impedance")) if item is not None else None
        kinds = {"0": "single", "1": "differential"}
        if (
            item is None
            or not isinstance(name, str)
            or not isinstance(kind, JsonNumber)
            or kind.text not in kinds
        ):
            found.append(project_issue("kicad.project.unread-entry", "a tuning profile without a name or a "
                                       "type 0 or 1 is not read", where=where))  # fmt: skip
            continue
        rows: list[ProfileEntry] = []
        layers = item.get("layer_entries")
        for k, layer in enumerate(cast(list[Any], layers) if isinstance(layers, list) else []):
            row = cast(JsonObject, layer) if isinstance(layer, dict) else {}
            width, gap = _nm(row.get("width")), _nm(row.get("diff_pair_gap"))
            refs = [row.get("top_reference_layer"), row.get("bottom_reference_layer")]
            signal = row.get("signal_layer")
            if (
                any(key not in row for key in LAYER_KEYS)
                or not isinstance(signal, str)
                or not all(isinstance(r, str) for r in refs)
                or width is None
                or gap is None
            ):
                found.append(
                    project_issue(
                        "kicad.project.unread-entry",
                        f"a layer entry of the tuning profile {name!r} lacks a key of the written form or "
                        "has a width or gap that is not a whole number of nanometres; it is not read",
                        where=f"{where}/layer_entries/{k}",
                    )
                )
                continue
            rows.append(ProfileEntry(signal, tuple(cast(str, r) for r in refs if r), width, gap))
        profiles.append(TuningProfile(name, kinds[kind.text], ohms or "", tuple(rows), index))
    return tuple(profiles)


def lift_profiles(
    design: Design,
    profiles: Sequence[TuningProfile],
    class_keys: Sequence[tuple[str, str]],
    *,
    issues: list[Issue] | None = None,
) -> Design:
    """``design`` with ``RuleSet.impedance`` set from the profiles that a class names: one target per such
    profile, of the classes that name it in ``class_keys`` order (``(class name, profile name)``). A layer
    entry whose layer or references are not copper layers of the board gives
    ``kicad.project.unread-entry`` and is skipped; a profile left without an entry gives no target."""
    found = issues if issues is not None else []
    named: dict[str, list[str]] = {}
    for cls, profile in class_keys:
        if profile:
            named.setdefault(profile, []).append(cls)
    by_name = {c.name: c.id for c in design.circuit.netclasses}
    copper = (
        [
            layer.name
            for layer in sorted(design.board.layers, key=lambda la: la.ordinal)
            if layer.kind == "copper"
        ]
        if design.board is not None
        else []
    )
    rank = {name: i for i, name in enumerate(copper)}
    targets: list[ImpedanceTarget] = []
    seen: set[str] = set()
    for profile in profiles:
        classes = [by_name[c] for c in named.get(profile.name, ()) if c in by_name]
        if not classes or profile.name in seen:
            continue
        seen.add(profile.name)
        rows: list[TraceGeometry] = []
        for entry in profile.entries:
            if any(name not in rank for name in (entry.layer, *entry.references)) or not entry.references:
                found.append(
                    project_issue(
                        "kicad.project.unread-entry",
                        f"a layer entry of the tuning profile {profile.name!r} names a layer that is not a "
                        f"copper layer of the board ({entry.layer}); it is not read",
                        where=f"{PROFILES_POINTER}/{profile.index}",
                    )
                )
                continue
            gap = entry.gap if profile.kind == "differential" else None
            refs = tuple(sorted(entry.references, key=lambda n: rank[n]))
            rows.append(TraceGeometry(entry.layer, refs, entry.width, gap))
        if not rows:
            continue
        targets.append(
            ImpedanceTarget(
                id=derived_id("imp", "kicad", f"profile:{profile.name}"),
                name=profile.name,
                kind="differential" if profile.kind == "differential" else "single",
                netclass_ids=tuple(classes),
                ohms=profile.ohms,
                layers=tuple(sorted(rows, key=lambda r: rank[r.layer])),
            )
        )
    if not targets:
        return design
    rules = design.rules if design.rules is not None else RuleSet(id=derived_id("rst", "kicad", "rules"))
    return dataclasses.replace(design, rules=dataclasses.replace(rules, impedance=tuple(targets)))


__all__ = [
    "CLASS_KEY",
    "ENTRY_KEYS",
    "EVIDENCE",
    "LAYER_KEYS",
    "PROFILES_POINTER",
    "PROFILE_KEY_PATHS",
    "ProfileEntry",
    "TuningProfile",
    "apply_profile_keys",
    "lift_profiles",
    "lower_profile",
    "read_profiles",
]
