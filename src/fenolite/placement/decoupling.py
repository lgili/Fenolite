# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Reviewable capacitor-to-supply-bank suggestions from resolved physical incidences."""

from collections import defaultdict, deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from fenolite.model.circuit import PinRef
from fenolite.placement.topology import Incidence, PadIdentity


@dataclass(frozen=True, slots=True)
class SupplyBank:
    key: str
    supply: PinRef
    return_pin: PinRef
    source: str


@dataclass(frozen=True, slots=True)
class Capacitor:
    component_id: str
    first_pin: str
    second_pin: str
    function: Literal["unknown", "bypass", "bulk", "other"] = "unknown"
    dnp: bool = False


@dataclass(frozen=True, slots=True)
class BypassMatch:
    bank: SupplyBank
    cap_supply: tuple[PadIdentity, ...]
    cap_return: tuple[PadIdentity, ...]
    bank_supply: tuple[PadIdentity, ...]
    bank_return: tuple[PadIdentity, ...]


@dataclass(frozen=True, slots=True)
class CapacitorSuggestion:
    capacitor_id: str
    state: Literal["suggested", "ambiguous", "unmatched", "unresolved", "bulk", "excluded"]
    matches: tuple[BypassMatch, ...] = ()
    unresolved_banks: tuple[str, ...] = ()
    rule_version: str = "supply-return-match.v0"


def suggest_bypass(
    incidences: tuple[Incidence, ...],
    banks: tuple[SupplyBank, ...],
    capacitors: tuple[Capacitor, ...],
) -> tuple[CapacitorSuggestion, ...]:
    """Match typed terminals on both nets. Shared rails leave all compatible owners visible."""
    terminals = {row.terminal: row for row in incidences if row.problem is None and row.pads}
    by_rails: dict[tuple[str, str], list[tuple[SupplyBank, Incidence, Incidence]]] = defaultdict(list)
    unresolved: list[str] = []
    for bank in sorted(banks, key=lambda row: row.key):
        supply, ret = terminals.get(bank.supply), terminals.get(bank.return_pin)
        if supply is None or ret is None or supply.net_id == ret.net_id:
            unresolved.append(bank.key)
        else:
            by_rails[supply.net_id, ret.net_id].append((bank, supply, ret))

    results: list[CapacitorSuggestion] = []
    for cap in sorted(capacitors, key=lambda row: row.component_id):
        ident = cap.component_id
        if cap.dnp or cap.function == "other":
            results.append(CapacitorSuggestion(ident, "excluded"))
            continue
        if cap.function == "bulk":
            results.append(CapacitorSuggestion(ident, "bulk"))
            continue
        first = terminals.get(PinRef(ident, cap.first_pin))
        second = terminals.get(PinRef(ident, cap.second_pin))
        if first is None or second is None:
            results.append(CapacitorSuggestion(ident, "unresolved"))
            continue
        matches = tuple(
            BypassMatch(bank, supply.pads, ret.pads, bank_supply.pads, bank_return.pads)
            for supply, ret in ((first, second), (second, first))
            for bank, bank_supply, bank_return in by_rails.get((supply.net_id, ret.net_id), ())
            if bank.supply.component_id != ident and bank.return_pin.component_id != ident
        )
        if len(matches) > 1:
            state = "ambiguous"
        elif unresolved:
            state = "unresolved"
        else:
            state = "suggested" if matches else "unmatched"
        results.append(CapacitorSuggestion(ident, state, matches, tuple(unresolved)))
    return tuple(results)


@dataclass(frozen=True, slots=True)
class BankCoverage:
    assignments: tuple[tuple[str, str], ...]
    uncovered: tuple[str, ...]
    exhausted: bool


def assign_bypass_banks(
    eligible: Mapping[str, tuple[str, ...]], *, shareable: frozenset[str] = frozenset(), edge_budget: int
) -> BankCoverage:
    """Seed coverage using only reviewed edges, one capacitor per bank unless explicitly shared."""
    if type(edge_budget) is not int or edge_budget < 0:
        raise ValueError("edge budget must be a nonnegative integer")
    choices = {bank: tuple(sorted(set(caps))) for bank, caps in eligible.items()}
    owners: dict[str, str] = {}
    assigned: dict[str, str] = {}
    edges = 0
    exhausted = False
    for root in sorted(choices, key=lambda bank: (len(choices[bank]), bank)):
        queue = deque([root])
        previous: dict[str, str] = {}
        visited = {root}
        found: str | None = None
        while queue and found is None and not exhausted:
            bank = queue.popleft()
            for cap in choices[bank]:
                if edges == edge_budget:
                    exhausted = True
                    break
                edges += 1
                if cap in previous:
                    continue
                previous[cap] = bank
                owner = owners.get(cap)
                if owner is None:
                    found = cap
                    break
                if owner not in visited:
                    visited.add(owner)
                    queue.append(owner)
        while found is not None:
            bank = previous[found]
            old = assigned.get(bank)
            assigned[bank] = found
            if found not in shareable:
                owners[found] = bank
            found = old
        if exhausted:
            break
    return BankCoverage(
        tuple(sorted(assigned.items())), tuple(sorted(set(choices) - assigned.keys())), exhausted
    )
