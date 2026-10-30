# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The pin solve (change c0257, ``docs/pins.md``), published as ``fenolite.lens.pins``.

A device record offers interface options (``[[options]]``: "I2C1 on PB6/PB7 or PB8/PB9"), a script takes
one interface of a kind from a part (``part.take(I2C)``), and ``solve`` gives every take one alternative so
that no pin serves two takes, a pin connected or marked by hand, or another take. The solve is a pure
function of the takes, the device records, the fixed pins and the locked choices: valid locked choices are
kept first, the others are searched depth first with forward checking in the canonical order (part path,
take key, option name, alternative index), and the first complete assignment wins. ``--seed`` does not
enter it.

This module reads plain data only (``TakeRequest``, ``DeviceDef``). It lives in ``model`` so that both the
DSL (``fenolite.dsl.take``, whose ``to_model`` solves against an empty lock as it assigns refs) and the build
(``fenolite.cli._pins``, against the design lock) reach it under the package layering; ``fenolite.lens.pins``
is its public name.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import cast

from fenolite.core.errors import Issue, Severity
from fenolite.model.library import DeviceDef

PIN_ISSUE_CODES: Mapping[str, Severity] = MappingProxyType(
    {
        "pins.unsatisfiable": "error",
        "pins.option-unknown": "error",
        "pins.pinned-conflict": "error",
        "pins.search-limit": "error",
        "pins.lock-stale": "warning",
        "pins.unused-take": "warning",
        "pins.lock-dropped": "info",
    }
)
"""The issue codes of the pin solve (``lens.pins.PIN_ISSUE_CODES``); they are also build issue codes
(``lens.build.BUILD_ISSUE_CODES``)."""
SOURCES: tuple[str, ...] = ("solved", "locked", "pinned")
"""Where a choice comes from: the search, a valid lock entry, or the take's own ``pins=``."""
MAX_STEPS = 100_000
"""The default bound of candidate trials of one solve (``pins.search-limit``)."""
LOCK_FIELDS: tuple[str, ...] = ("kind", "option", "alternative", "pins")
"""The fields of a ``[pins."<key>"]`` entry of the design lock that the solve reads (``choice`` is text)."""


def issue(code: str, message: str, where: str = "", hint: str = "") -> Issue:
    return Issue(code, PIN_ISSUE_CODES[code], message, where=where, hint=hint)


@dataclass(frozen=True, slots=True)
class TakeRequest:
    """One ``part.take(...)`` of a script: the part path, the take key, the kind, the ``option`` and ``pins``
    filters (role → function), and where the script made it (``file:line``)."""

    part: str
    take: str
    kind: str
    option: str | None = None
    pins: Mapping[str, str] = field(default_factory=lambda: MappingProxyType({}))
    where: str = ""

    @property
    def key(self) -> str:
        """The lock key ``<part path>/<take key>``."""
        return f"{self.part}/{self.take}"

    def order(self) -> tuple[str, str]:
        return (self.part, self.take)


@dataclass(frozen=True, slots=True)
class Candidate:
    """One alternative of one option: what a take may be given."""

    option: str
    alternative: int
    pins: Mapping[str, str]
    evidence: str

    def used(self) -> frozenset[str]:
        return frozenset(self.pins.values())


@dataclass(frozen=True, slots=True)
class LockedChoice:
    """A ``[pins]`` entry of the design lock, as the solve reads it."""

    kind: str
    option: str
    alternative: int
    pins: Mapping[str, str]


@dataclass(frozen=True, slots=True)
class PinChoice:
    """The choice of one take: its lock ``key``, part path, kind, option name, alternative index, role →
    function, ``source`` (``SOURCES``) and the option's evidence label."""

    key: str
    part: str
    kind: str
    option: str
    alternative: int
    pins: Mapping[str, str]
    source: str
    evidence: str = ""

    def text(self) -> str:
        """The human text of the choice: ``I2C1 on PB8/PB9`` (pins in code-point order of their roles)."""
        return choice_text(self.option, self.pins)

    def as_json(self) -> dict[str, object]:
        """The object of ``result.pins``."""
        return {
            "key": self.key,
            "kind": self.kind,
            "option": self.option,
            "alternative": self.alternative,
            "pins": dict(sorted(self.pins.items())),
            "source": self.source,
        }

    def lock_entry(self) -> dict[str, object]:
        """The ``[pins."<key>"]`` entry of the design lock (``choice`` is added when written)."""
        return {
            "kind": self.kind,
            "option": self.option,
            "alternative": self.alternative,
            "pins": dict(sorted(self.pins.items())),
        }


@dataclass(frozen=True, slots=True)
class PinSolution:
    """What ``solve`` gives: the ``choices`` sorted by key (a take with an error has none), the issues, the
    number of candidate ``steps`` the search tried, and the keys of the stale lock entries."""

    choices: tuple[PinChoice, ...] = ()
    issues: tuple[Issue, ...] = ()
    steps: int = 0
    stale: tuple[str, ...] = ()

    def by_key(self) -> dict[str, PinChoice]:
        return {choice.key: choice for choice in self.choices}


def choice_text(option: str, pins: Mapping[str, str]) -> str:
    """``<option> on <pin>/<pin>``, pins in code-point order of their roles."""
    return f"{option} on {'/'.join(pin for _, pin in sorted(pins.items()))}"


def candidates(device: DeviceDef, kind: str) -> list[Candidate]:
    """Every alternative of every option of ``kind`` of ``device``, by option name then alternative index."""
    found: list[Candidate] = []
    for option in sorted((o for o in device.options if o.kind == kind), key=lambda o: o.name):
        for index, alternative in enumerate(option.alternatives):
            found.append(Candidate(option.name, index, MappingProxyType(dict(alternative)), option.evidence))
    return found


def read_locked(entries: Mapping[str, Mapping[str, object]]) -> dict[str, LockedChoice]:
    """The ``[pins]`` entries of a lock (checked by ``fenolite.dsl.lock.read_lock``) as ``LockedChoice``."""
    found: dict[str, LockedChoice] = {}
    for key, entry in entries.items():
        raw = entry.get("pins", {})
        pins: Mapping[object, object] = cast(Mapping[object, object], raw) if isinstance(raw, Mapping) else {}
        alternative = entry.get("alternative", -1)
        found[key] = LockedChoice(
            kind=str(entry.get("kind", "")),
            option=str(entry.get("option", "")),
            alternative=alternative if isinstance(alternative, int) else -1,
            pins=MappingProxyType({str(role): str(pin) for role, pin in pins.items()}),
        )
    return found


class _Limit(Exception):
    """The search tried more than ``max_steps`` candidates."""


class _Search:
    """A depth-first search with forward checking over ``domains`` (take index → its candidates, in
    canonical order), with ``taken`` pins per part unavailable."""

    def __init__(self, max_steps: int) -> None:
        self.max_steps = max_steps
        self.steps = 0

    def run(
        self,
        takes: Sequence[TakeRequest],
        domains: Sequence[Sequence[Candidate]],
        taken: Mapping[str, frozenset[str]],
    ) -> list[Candidate] | None:
        used: dict[str, set[str]] = {part: set(pins) for part, pins in taken.items()}
        chosen: list[Candidate] = []

        def free(index: int, candidate: Candidate) -> bool:
            return not (candidate.used() & used.setdefault(takes[index].part, set()))

        def step(index: int) -> bool:
            if index == len(takes):
                return True
            part = takes[index].part
            for candidate in domains[index]:
                self.steps += 1
                if self.steps > self.max_steps:
                    raise _Limit
                if not free(index, candidate):
                    continue
                used[part] |= candidate.used()
                chosen.append(candidate)
                ahead = all(
                    any(free(later, other) for other in domains[later])
                    for later in range(index + 1, len(takes))
                )
                if ahead and step(index + 1):
                    return True
                chosen.pop()
                used[part] -= candidate.used()
            return False

        return chosen if step(0) else None


def _minimal_conflict(
    takes: Sequence[TakeRequest],
    domains: Sequence[Sequence[Candidate]],
    taken: Mapping[str, frozenset[str]],
    search: _Search,
) -> list[int]:
    """The smallest conflicting set of takes found by deletion: drop takes one at a time in reverse order
    while the rest stays unsatisfiable. Indices into ``takes``, in order."""
    kept = list(range(len(takes)))
    for index in reversed(range(len(takes))):
        trial = [i for i in kept if i != index]
        if search.run([takes[i] for i in trial], [domains[i] for i in trial], taken) is None:
            kept = trial
    return kept


def solve(
    takes: Sequence[TakeRequest],
    devices: Mapping[str, DeviceDef],
    fixed: Mapping[str, frozenset[str]],
    locked: Mapping[str, LockedChoice],
    *,
    max_steps: int = MAX_STEPS,
) -> PinSolution:
    """The choice of every take (``docs/pins.md``, "The solve").

    ``devices`` maps a part path to its device record and ``fixed`` a part path to the functions connected
    or marked no-connect by hand. ``locked`` holds the ``[pins]`` entries of the lock by key.

    1. A take whose ``option`` names no option of its kind is ``pins.option-unknown``; ``pins`` that match no
       alternative, or that name a fixed pin, are ``pins.pinned-conflict``.
    2. A valid locked choice (option, alternative and pins unchanged, no fixed or taken pin, within the
       take's filters) is kept, source ``locked``; an invalid one is ``pins.lock-stale`` and solved again.
    3. The other takes, in order of (part path, take key), are searched depth first with forward checking
       over their candidates in order of (option name, alternative index); the first complete assignment wins.
    4. No assignment: ``pins.unsatisfiable`` naming the smallest conflicting set of takes and their pins;
       more than ``max_steps`` candidate trials: ``pins.search-limit``.
    """
    issues: list[Issue] = []
    choices: list[PinChoice] = []
    stale: list[str] = []
    ordered = sorted(takes, key=TakeRequest.order)
    domains: dict[str, list[Candidate]] = {}
    for take in ordered:
        device = devices[take.part]
        all_of_kind = candidates(device, take.kind)
        found = all_of_kind
        if take.option is not None:
            found = [c for c in found if c.option == take.option]
            if not found:
                names = sorted({c.option for c in all_of_kind})
                issues.append(
                    issue(
                        "pins.option-unknown",
                        f"take {take.key}: device {device.id} has no {take.kind} option {take.option!r}; "
                        f"its {take.kind} options: {', '.join(names) or 'none'}",
                        take.where or take.key,
                        "name one of the options of the device record, or leave option= out",
                    )
                )
                continue
        if take.pins:
            found = [c for c in found if all(c.pins.get(role) == pin for role, pin in take.pins.items())]
            hand = sorted(set(take.pins.values()) & fixed.get(take.part, frozenset()))
            if not found or hand:
                why = (
                    f"names the pin {hand[0]}, which is connected or marked by hand"
                    if hand
                    else "matches no alternative of the device"
                )
                given = ", ".join(f"{role}={pin}" for role, pin in sorted(take.pins.items()))
                issues.append(
                    issue(
                        "pins.pinned-conflict",
                        f"take {take.key}: pins={{{given}}} {why} ({device.id})",
                        take.where or take.key,
                        "give pins that one alternative of the device offers, or leave pins= out",
                    )
                )
                continue
        domains[take.key] = found
    taken: dict[str, set[str]] = {part: set(pins) for part, pins in fixed.items()}
    open_takes: list[TakeRequest] = []
    for take in ordered:
        found = domains.get(take.key)
        if found is None:
            continue
        entry = locked.get(take.key)
        if entry is not None:
            match = next(
                (
                    c
                    for c in found
                    if entry.kind == take.kind
                    and c.option == entry.option
                    and c.alternative == entry.alternative
                    and dict(c.pins) == dict(entry.pins)
                ),
                None,
            )
            if match is not None and not (match.used() & taken.setdefault(take.part, set())):
                taken[take.part] |= match.used()
                choices.append(_choice(take, match, "pinned" if take.pins else "locked"))
                continue
            stale.append(take.key)
            issues.append(
                issue(
                    "pins.lock-stale",
                    f"take {take.key}: the locked choice {choice_text(entry.option, entry.pins)} is no "
                    "longer "
                    "valid (the device record, the take or a hand connection changed); it is solved again",
                    take.key,
                    "review result.pins and the planned lock write",
                )
            )
        open_takes.append(take)
    search = _Search(max_steps)
    frozen_taken = {part: frozenset(pins) for part, pins in taken.items()}
    open_domains = [domains[take.key] for take in open_takes]
    try:
        found_all = search.run(open_takes, open_domains, frozen_taken)
        if found_all is None:
            try:
                conflict = _minimal_conflict(open_takes, open_domains, frozen_taken, _Search(max_steps))
            except _Limit:
                conflict = list(range(len(open_takes)))
            names = [open_takes[i].key for i in conflict]
            pins = sorted(
                {f"{open_takes[i].part}:{pin}" for i in conflict for c in open_domains[i] for pin in c.used()}
            )
            issues.append(
                issue(
                    "pins.unsatisfiable",
                    f"no pin assignment exists for the takes {', '.join(names)}: they compete for "
                    f"{', '.join(pins)}",
                    names[0] if names else "",
                    "drop a take, widen its option= or pins=, or free a pin connected by hand",
                )
            )
        else:
            for take, candidate in zip(open_takes, found_all, strict=True):
                choices.append(_choice(take, candidate, "pinned" if take.pins else "solved"))
    except _Limit:
        issues.append(
            issue(
                "pins.search-limit",
                f"the pin solve tried more than {max_steps} candidates without an answer "
                f"({len(open_takes)} takes)",
                open_takes[0].key if open_takes else "",
                "narrow the takes with option= or pins=",
            )
        )
    return PinSolution(
        choices=tuple(sorted(choices, key=lambda c: c.key)),
        issues=tuple(issues),
        steps=search.steps,
        stale=tuple(stale),
    )


def _choice(take: TakeRequest, candidate: Candidate, source: str) -> PinChoice:
    return PinChoice(
        key=take.key,
        part=take.part,
        kind=take.kind,
        option=candidate.option,
        alternative=candidate.alternative,
        pins=candidate.pins,
        source=source,
        evidence=candidate.evidence,
    )


def dropped_issues(locked: Mapping[str, object], takes: Sequence[TakeRequest]) -> list[Issue]:
    """``pins.lock-dropped`` for each lock entry whose key no take has any more."""
    keys = {take.key for take in takes}
    return [
        issue(
            "pins.lock-dropped",
            f"the lock entry {key} names no take of the script any more; it is removed",
            key,
        )
        for key in sorted(locked)
        if key not in keys
    ]


__all__ = [
    "LOCK_FIELDS",
    "MAX_STEPS",
    "PIN_ISSUE_CODES",
    "SOURCES",
    "Candidate",
    "LockedChoice",
    "PinChoice",
    "PinSolution",
    "TakeRequest",
    "candidates",
    "choice_text",
    "dropped_issues",
    "issue",
    "read_locked",
    "solve",
]
