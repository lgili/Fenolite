# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Resolution of the query parts of a design against the lock's picks and the rows (change c0254,
``docs/picking.md``, "Resolution in a build").

``resolve`` is pure: equal queries, lock entries and rows give equal picks, findings and entries. For each
query part, in path order, it applies the table of ``design.md``, decision 9:

- no lock entry: the best match is picked (``pick.new``), or ``pick.no-match`` when no row matches;
- equal query text and row hash: the locked device;
- equal query text, changed row hash, still meeting the query: the row as it is now (``pick.row-changed``);
- the locked row is gone: ``pick.row-missing``;
- changed query text that the locked row still meets: the device is kept (``pick.query-changed``);
- changed query text it no longer meets: ``pick.stale``, never a silent swap.

A locked pick is never replaced by a better match: improvement is a decision, made with
``fenolite pick --update`` (the paths of ``update`` are resolved as if the lock held nothing for them).
The parts of one generator call are resolved together: a locked group is judged with its new inputs, never
searched again; an unlocked group is solved (``gen.achieved`` or ``gen.unachievable``).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from types import MappingProxyType

from fenolite.core.errors import Issue
from fenolite.core.partquery import PartQuery
from fenolite.pick.codes import issue
from fenolite.pick.generators import Solution, registry
from fenolite.pick.lockpicks import PickEntry
from fenolite.pick.match import failure, match, unknown_rows, unverified_ahead
from fenolite.pick.rows import Row

STATES: tuple[str, ...] = ("ok", "new", "stale", "row-changed", "row-missing", "no-match")
"""The states of a pick that ``fenolite pick`` lists; the last four but ``row-changed`` are errors."""
ERROR_STATES = frozenset({"stale", "row-missing", "no-match"})


@dataclass(frozen=True, slots=True)
class Pick:
    """The state of one query part: its path, canonical query text, picked row (``None`` when nothing was
    picked), lock entry (the new one, or the old one when nothing changes) and state."""

    path: str
    query: str
    state: str
    row: Row | None
    entry: PickEntry | None
    before: str | None = None
    """The device the lock held before, when it differs from the entry's."""

    def as_json(self) -> dict[str, object]:
        entry = self.entry
        return {
            "path": self.path,
            "query": self.query,
            "device": entry.device if entry is not None else None,
            "row": entry.row if entry is not None else None,
            "catalog": entry.catalog if entry is not None else None,
            "state": self.state,
            "evidence": self.row.evidence if self.row is not None else None,
            "before": self.before,
        }


@dataclass(frozen=True, slots=True)
class Resolution:
    """The picks of every query part in path order, the new lock entries, the findings and the results of
    the generators (``result.generators``)."""

    picks: tuple[Pick, ...]
    entries: Mapping[str, PickEntry]
    issues: tuple[Issue, ...]
    generators: tuple[Mapping[str, object], ...] = ()
    changes: tuple[tuple[str, str | None, str | None, str], ...] = field(default=())
    """``(path, device before, device after, reason)`` of each change of the lock."""

    @property
    def refused(self) -> bool:
        return any(found.severity == "error" for found in self.issues)

    def rows(self) -> dict[str, Row]:
        """Path → the picked row of every part that has one."""
        return {pick.path: pick.row for pick in self.picks if pick.row is not None}


def _entry(query: str, row: Row, by: str, achieved: str = "") -> PickEntry:
    return PickEntry(query, row.device, row.row, row.catalog, row.sha256, by, achieved)


def _by_device(rows: Sequence[Row]) -> dict[str, Row]:
    found: dict[str, Row] = {}
    for row in rows:
        found.setdefault(row.device, row)
    return found


def _meets(query: PartQuery, row: Row) -> str | None:
    """``None`` when ``row`` meets ``query`` (a locked row's own evidence is not judged again), else the
    text of its first failed constraint."""
    missed = failure(query, row)
    if missed is None or missed.reason == "unverified":
        return None
    return missed.text


class _Builder:
    def __init__(self) -> None:
        self.picks: dict[str, Pick] = {}
        self.entries: dict[str, PickEntry] = {}
        self.issues: list[Issue] = []
        self.generators: list[Mapping[str, object]] = []
        self.changes: list[tuple[str, str | None, str | None, str]] = []

    def keep(self, path: str, query: str, row: Row, entry: PickEntry, state: str = "ok") -> None:
        self.picks[path] = Pick(path, query, state, row, entry)
        self.entries[path] = entry

    def change(self, path: str, before: PickEntry | None, after: PickEntry, reason: str) -> None:
        self.changes.append((path, before.device if before else None, after.device, reason))


def _new(build: _Builder, path: str, query: PartQuery, rows: Sequence[Row], before: PickEntry | None) -> None:
    text = query.text()
    result = match(query, rows)
    for found in unverified_ahead(query, result):
        build.issues.append(
            issue(
                "pick.row-unverified",
                f"{path}: the UNVERIFIED row {found.row.row} is ranked out of {text}; review it and "
                "raise its "
                "evidence, or name it with row=",
                path,
            )
        )
    best = result.best
    if best is None:
        build.picks[path] = Pick(path, text, "no-match", None, before)
        if before is not None:
            build.entries[path] = before
        failed = [found for found in result.excluded if found.key != "value"][:5]
        detail = "; ".join(f"{found.row.device}: {found.text}" for found in failed)
        build.issues.append(
            issue(
                "pick.no-match",
                f"{path}: no row meets {text}" + (f" (first failures: {detail})" if detail else ""),
                path,
                "relax the query, or add a row to devices/ beside the script; fenolite pick PATH "
                "--candidates "
                f"{path} lists the rows and why each is left out",
            )
        )
        for found in unknown_rows(result):
            build.issues.append(
                issue(
                    "pick.attribute-unknown",
                    f"{path}: the row {found.row.row} states no {found.key}, so it cannot meet {found.text}",
                    path,
                    f"state {found.key} in the row, with its source, if the part has it",
                )
            )
        return
    entry = _entry(text, best, "query")
    build.keep(path, text, best, entry, "new")
    if before is None:
        build.change(path, None, entry, "picked")
        build.issues.append(issue("pick.new", f"{path}: {text} picks {best.device}", path))
    elif before != entry:
        build.picks[path] = replace(build.picks[path], before=before.device)
        build.change(path, before, entry, "updated")


def _locked(build: _Builder, path: str, query: PartQuery, entry: PickEntry, row: Row | None) -> None:
    text = query.text()
    if row is None:
        build.picks[path] = Pick(path, text, "row-missing", None, entry)
        build.entries[path] = entry
        build.issues.append(
            issue(
                "pick.row-missing",
                f"{path}: the locked row {entry.row} (device {entry.device}, {entry.catalog}) is not "
                "in the catalog",
                path,
                f"restore the row, or re-pick with fenolite pick --update {path}",
            )
        )
        return
    missed = _meets(query, row)
    if missed is not None:
        build.picks[path] = Pick(path, text, "stale", row, entry)
        build.entries[path] = entry
        build.issues.append(
            issue(
                "pick.stale",
                f"{path}: the locked device {entry.device} no longer meets {text}: {missed}",
                path,
                f"fenolite pick --update {path}",
            )
        )
        return
    new = PickEntry(text, row.device, row.row, row.catalog, row.sha256, entry.by, entry.achieved)
    if text != entry.query:
        build.keep(path, text, row, new)
        build.change(path, entry, new, "query-changed")
        build.issues.append(
            issue(
                "pick.query-changed",
                f"{path}: the query is now {text}; the locked {row.device} still meets it",
                path,
            )
        )
    elif row.sha256 != entry.sha256:
        build.keep(path, text, row, new, "row-changed")
        build.change(path, entry, new, "row-changed")
        build.issues.append(
            issue(
                "pick.row-changed",
                f"{path}: the row {row.row} changed since it was picked and still meets {text}; its "
                "new hash is planned",
                path,
                "review the change of the row",
            )
        )
    else:
        build.keep(path, text, row, entry)


def _group(
    build: _Builder,
    members: Mapping[str, tuple[str, PartQuery]],
    locked: Mapping[str, PickEntry],
    rows: Sequence[Row],
    devices: Mapping[str, Row],
    update: frozenset[str],
) -> None:
    """Resolve the parts of one generator call (role → path and query)."""
    first = next(iter(members.values()))[1].generator
    assert first is not None
    solve, evaluate = registry()[first.name]
    paths = {role: path for role, (path, _) in members.items()}
    texts = {role: query.text() for role, (_, query) in members.items()}
    held = {role: locked.get(path) for role, path in paths.items()}
    fresh = any(entry is None for entry in held.values()) or any(path in update for path in paths.values())
    solution: Solution
    if not fresh:
        current = {role: devices.get(entry.device) for role, entry in held.items() if entry is not None}
        missing = [role for role, row in current.items() if row is None]
        if missing:
            for role in sorted(members):
                path, query = members[role]
                _locked(build, path, query, held[role], current.get(role))  # pyright: ignore[reportArgumentType]
            return
        chosen = {role: row for role, row in current.items() if row is not None}
        constraint = {role: _meets(members[role][1], chosen[role]) for role in members}
        solution = evaluate(first, chosen)
        if not solution.ok or any(found is not None for found in constraint.values()):
            reason = next((found for found in constraint.values() if found is not None), solution.message)
            for role in sorted(members):
                path, query = members[role]
                entry = held[role]
                assert entry is not None
                build.picks[path] = Pick(path, texts[role], "stale", chosen[role], entry)
                build.entries[path] = entry
                build.issues.append(
                    issue(
                        "pick.stale",
                        f"{path}: the locked {first.name} pick {entry.device} no longer meets its "
                        f"inputs: {reason}",
                        path,
                        f"fenolite pick --update {path}",
                    )
                )
            return
        for role in sorted(members):
            path = paths[role]
            entry = held[role]
            assert entry is not None
            row = chosen[role]
            new = PickEntry(
                texts[role], row.device, row.row, row.catalog, row.sha256, first.name, solution.achieved
            )
            state = "row-changed" if row.sha256 != entry.sha256 else "ok"
            build.keep(path, texts[role], row, new, state)
            if new != entry:
                reason = (
                    "query-changed"
                    if texts[role] != entry.query or new.achieved != entry.achieved
                    else "row-changed"
                )
                build.change(path, entry, new, reason)
                if reason == "query-changed":
                    build.issues.append(
                        issue(
                            "pick.query-changed",
                            f"{path}: the inputs of {first.name} are now {texts[role]}; the locked "
                            f"{row.device} still "
                            "meets them",
                            path,
                        )
                    )
                else:
                    build.issues.append(
                        issue(
                            "pick.row-changed",
                            f"{path}: the row {row.row} changed and still meets the inputs",
                            path,
                        )
                    )
    else:
        candidates = {role: match(query, rows).matches for role, (_, query) in members.items()}
        solution = solve(first, candidates)
        if not solution.ok:
            for role in sorted(members):
                path = paths[role]
                build.picks[path] = Pick(path, texts[role], "no-match", None, held[role])
                if held[role] is not None:
                    build.entries[path] = held[role]  # pyright: ignore[reportArgumentType]
            build.issues.append(issue("gen.unachievable", solution.message, first.group, solution.hint))
            build.generators.append(
                {
                    "group": first.group,
                    "generator": first.name,
                    "ok": False,
                    "message": solution.message,
                    "parts": dict(sorted(paths.items())),
                }
            )
            return
        for role in sorted(members):
            path = paths[role]
            row = solution.rows[role]
            entry = PickEntry(
                texts[role], row.device, row.row, row.catalog, row.sha256, first.name, solution.achieved
            )
            before = held[role]
            build.keep(path, texts[role], row, entry, "new" if before is None else "ok")
            if before is None:
                build.change(path, None, entry, "picked")
                build.issues.append(issue("pick.new", f"{path}: {first.name} picks {row.device}", path))
            elif before != entry:
                build.picks[path] = replace(build.picks[path], before=before.device)
                build.change(path, before, entry, "updated")
    build.issues.append(issue("gen.achieved", solution.message, first.group))
    build.generators.append(
        {
            "group": first.group,
            "generator": first.name,
            "ok": True,
            "message": solution.message,
            "achieved": solution.achieved,
            "parts": dict(sorted(paths.items())),
        }
    )


def resolve(
    queries: Mapping[str, PartQuery],
    locked: Mapping[str, PickEntry],
    rows: Sequence[Row],
    *,
    update: frozenset[str] = frozenset(),
) -> Resolution:
    """The picks of ``queries`` (component path → effective query) against the ``locked`` entries and the
    ``rows``; ``update`` names the paths to re-resolve against the current rows."""
    build = _Builder()
    devices = _by_device(rows)
    groups: dict[str, dict[str, tuple[str, PartQuery]]] = {}
    for path in sorted(queries):
        query = queries[path]
        if query.generator is not None:
            groups.setdefault(query.generator.group, {})[query.generator.role] = (path, query)
            continue
        entry = locked.get(path)
        if entry is None or path in update:
            _new(build, path, query, rows, entry)
        else:
            _locked(build, path, query, entry, devices.get(entry.device))
    for group in sorted(groups):
        _group(build, groups[group], locked, rows, devices, update)
    for path in sorted(set(locked) - set(queries)):
        build.changes.append((path, locked[path].device, None, "released"))
    ordered = {path: build.picks[path] for path in sorted(build.picks)}
    return Resolution(
        picks=tuple(ordered.values()),
        entries=MappingProxyType({path: build.entries[path] for path in sorted(build.entries)}),
        issues=tuple(build.issues),
        generators=tuple(build.generators),
        changes=tuple(sorted(build.changes)),
    )


__all__ = ["ERROR_STATES", "STATES", "Pick", "Resolution", "resolve"]
