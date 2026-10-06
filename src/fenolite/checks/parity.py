# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Schematic against board, and symbol pins against footprint pads (capability verification-loop, "Parity
comparison" and "Parity issue codes"; change c0072).

``compare`` takes a ``SchematicSide`` (components by reference and the net of every pin, built by a
backend) and a board model, and reports every difference. It needs no tool. The categories and their
keys are those of KiCad's own parity test, measured on 9.0.9 and 10.0.6 (``docs/formats/kicad/drc.md``,
"Schematic parity"; ``H-K-PARITY-TYPES``), so that the two can be compared entry by entry:
``oracle_entry`` gives the KiCad type and key of a finding. The agreement on the public demos is
``H-K-PARITY-OWN``.

Components and footprints are matched by reference only. A component is matched with the first footprint
of its reference in board order; a footprint that is marked as not in the schematic (``board_only``) is
never extra.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType

from fenolite.backends.base import SchematicSide, SideComponent
from fenolite.core.errors import Issue, Severity
from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import FootprintInstance, Pad
from fenolite.model.design import Design

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-PARITY-OWN",))
"""``INFERRED`` until ``H-K-PARITY-OWN`` is verified; it then still names the hypothesis, because the
public demos are not every project."""

MISSING = "parity.missing-footprint"
EXTRA = "parity.extra-footprint"
DUPLICATE = "parity.duplicate-footprints"
MISMATCH = "parity.footprint-mismatch"
NET_CONFLICT = "parity.net-conflict"
PIN_WITHOUT_PAD = "parity.pin-without-pad"
PAD_WITHOUT_PIN = "parity.pad-without-pin"
ORACLE_DIFFERS = "parity.oracle-differs"

PARITY_ISSUE_CODES: Mapping[str, tuple[Severity, ...]] = MappingProxyType(
    {
        MISSING: ("error",),
        EXTRA: ("error",),
        DUPLICATE: ("error",),
        NET_CONFLICT: ("error",),
        PIN_WITHOUT_PAD: ("error", "warning"),
        MISMATCH: ("warning",),
        ORACLE_DIFFERS: ("warning",),
        PAD_WITHOUT_PIN: ("info",),
    }
)
"""The closed table of the parity codes; ``parity.oracle-differs`` is the code of the stage
(``checks.parity_stage``)."""

KICAD_TYPES: Mapping[str, str] = MappingProxyType(
    {
        MISSING: "missing_footprint",
        EXTRA: "extra_footprint",
        DUPLICATE: "duplicate_footprints",
        MISMATCH: "footprint_symbol_mismatch",
        NET_CONFLICT: "net_conflict",
        PIN_WITHOUT_PAD: "net_conflict",
    }
)
"""Code → the type of KiCad's parity test that reports the same difference (``H-K-PARITY-TYPES``). KiCad
reports a pin without a pad as a ``net_conflict`` of the footprint; a pad that no pin names and that is
on no net is reported by Fenolite only."""
SUMMARY_KEYS: tuple[str, ...] = (
    *(code for code in PARITY_ISSUE_CODES if code != ORACLE_DIFFERS),
    "refs_one_side",
    "connections_missing",
    "nets_split",
)
BOARD_ONLY = "board_only"
UNNUMBERED_KIND = "np_thru_hole"
FIELDS: tuple[str, ...] = ("value", "footprint", "attributes")
"""The fields of a ``parity.footprint-mismatch``. ``attributes`` are the flags of ``SHARED_ATTRIBUTES``
that the symbol and the footprint do not share, one finding for all of them."""
SHARED_ATTRIBUTES: tuple[str, ...] = ("dnp", "exclude_from_bom")


@dataclass(frozen=True, slots=True)
class ParityFinding:
    """One difference: ``key`` is the reference, or ``REF-PAD`` for a pad or a pin; ``field`` names the
    differing field of a ``parity.footprint-mismatch``; ``schematic`` and ``board`` are the two values
    (a value, a library id or a net name; ``""`` for none)."""

    code: str
    severity: Severity
    key: str
    field: str = ""
    schematic: str = ""
    board: str = ""

    def to_json(self) -> dict[str, str]:
        return {
            "code": self.code,
            "severity": self.severity,
            "key": self.key,
            "field": self.field,
            "schematic": self.schematic,
            "board": self.board,
        }


@dataclass(frozen=True, slots=True)
class ParityReport:
    """The findings sorted by code, key and field, and the counts: one per code, and the three derived
    ones (``refs_one_side``, ``connections_missing``, ``nets_split``)."""

    findings: tuple[ParityFinding, ...]
    summary: Mapping[str, int]
    evidence: Evidence = EVIDENCE


def _named(value: str) -> str:
    return f"'{value}'" if value else "none"


def message(finding: ParityFinding) -> str:
    """One sentence for a finding."""
    key, schematic, board = finding.key, finding.schematic, finding.board
    if finding.code == MISSING:
        return f"the schematic component {key} has no footprint on the board"
    if finding.code == EXTRA:
        return f"the footprint {key} has no component in the schematic"
    if finding.code == DUPLICATE:
        return f"another footprint holds the reference {key or '(none)'}"
    if finding.code == MISMATCH:
        where = f"{_named(board)} on the board and {_named(schematic)} in the schematic"
        return f"{key}: the {finding.field} is {where}"
    if finding.code == NET_CONFLICT:
        return f"pad {key} is on the net {_named(board)}; the schematic gives {_named(schematic)}"
    if finding.code == PIN_WITHOUT_PAD:
        return f"pin {key} (net {_named(schematic)}) names no pad of the footprint, so it cannot be connected"
    if finding.code == PAD_WITHOUT_PIN:
        return f"pad {key} is named by no pin of the symbol"
    raise KeyError(finding.code)


HINTS: Mapping[str, str] = MappingProxyType(
    {
        MISSING: "update the board from the schematic, or rebuild",
        EXTRA: "remove the footprint, or mark it as not in the schematic",
        DUPLICATE: "give each footprint its own reference",
        MISMATCH: "update the board from the schematic, or rebuild",
        NET_CONFLICT: "update the board from the schematic, or rebuild",
        PIN_WITHOUT_PAD: "choose a footprint with a pad of that number, or correct the symbol's pin number",
        PAD_WITHOUT_PIN: "",
    }
)


def finding_issue(finding: ParityFinding) -> Issue:
    """The issue of a finding: its code and severity, ``where`` its key."""
    return Issue(
        finding.code, finding.severity, message(finding), where=finding.key, hint=HINTS[finding.code]
    )


def oracle_entry(finding: ParityFinding) -> tuple[str, str] | None:
    """``(KiCad type, key)`` of the entry that KiCad's parity test gives for the same difference, or
    ``None`` when KiCad reports nothing for it. The key is the reference, or ``REF-PAD`` for a pad;
    KiCad names the footprint, not the pin, for a pin without a pad."""
    kind = KICAD_TYPES.get(finding.code)
    if kind is None:
        return None
    if finding.code == PIN_WITHOUT_PAD:
        return kind, finding.key.rsplit("-", 1)[0]
    return kind, finding.key


def _references(board: Design) -> dict[str, list[FootprintInstance]]:
    assert board.board is not None
    refs = {component.id: component.ref for component in board.circuit.components}
    found: dict[str, list[FootprintInstance]] = {}
    for footprint in board.board.footprints:
        found.setdefault(refs.get(footprint.component_id, ""), []).append(footprint)
    return found


def _is_component(ref: str) -> bool:
    return bool(ref) and not ref.startswith("#")


def _pad_net(pad: Pad, names: Mapping[str, str]) -> str:
    return names.get(pad.net_id, "") if pad.net_id is not None else ""


def _same_net(node: str, net: str, single_prefix: str) -> bool:
    """Whether the board net ``net`` is the schematic net ``node``: the same name, or, for the net of one
    pin on no net, that name with the ``_<n>`` that a further pad of the pin's number carries."""
    if node == net:
        return True
    if not single_prefix or not node.startswith(single_prefix) or not net.startswith(f"{node}_"):
        return False
    return net[len(node) + 1 :].isdecimal()


def compare(side: SchematicSide, board: Design, *, issues: list[Issue] | None = None) -> ParityReport:
    """Every difference between ``side`` and ``board`` (a ``Design`` with a board), and their counts. One
    issue per finding is appended to ``issues`` when it is given. Nothing is read and nothing is changed."""
    if board.board is None:
        raise ValueError("the parity comparison needs a design with a board")
    components: dict[str, SideComponent] = {
        ref: component for ref, component in side.components.items() if _is_component(ref)
    }
    values = {component.id: component.value for component in board.circuit.components}

    def folded(name: str) -> str:
        for text, replacement in side.fold:
            name = name.replace(text, replacement)
        return name

    names = {net.id: folded(net.name) for net in board.circuit.nets}
    nodes = {key: folded(net) for key, net in side.nodes.items()}
    by_ref = _references(board)
    members: dict[str, int] = Counter(nodes.values())
    found: list[ParityFinding] = []
    missing_connections = 0
    seen: dict[str, set[str]] = defaultdict(set)  # schematic net → board net names of its pads

    for ref in components:
        if ref not in by_ref:
            found.append(ParityFinding(MISSING, "error", ref))
    for ref, footprints in by_ref.items():
        in_schematic = [fp for fp in footprints if BOARD_ONLY not in fp.attributes]
        found += [ParityFinding(DUPLICATE, "error", ref) for _ in in_schematic[1:]]
        if ref not in components:
            found += [ParityFinding(EXTRA, "error", ref) for _ in in_schematic]
            continue
        component, footprint = components[ref], footprints[0]
        flags = {a for a in footprint.attributes if a in SHARED_ATTRIBUTES}
        for name, schematic, on_board in (
            ("value", component.value, values.get(footprint.component_id, "")),
            ("footprint", component.footprint, footprint.lib_ref),
            ("attributes", ",".join(sorted(component.attributes)), ",".join(sorted(flags))),
        ):
            if schematic != on_board:
                found.append(ParityFinding(MISMATCH, "warning", ref, name, schematic, on_board))
        numbers: set[str] = set()
        for pad in footprint.pads:
            if not pad.number:
                continue
            numbers.add(pad.number)
            key = f"{ref}-{pad.number}"
            node = nodes.get((ref, pad.number))
            net = _pad_net(pad, names)
            if node is not None and net:
                seen[node].add(node if _same_net(node, net, side.single_prefix) else net)
            if node is None and not net:
                if pad.kind != UNNUMBERED_KIND and pad.number not in component.pins:
                    found.append(ParityFinding(PAD_WITHOUT_PIN, "info", key))
            elif not _same_net(node or "", net, side.single_prefix):
                found.append(ParityFinding(NET_CONFLICT, "error", key, schematic=node or "", board=net))
                missing_connections += 1 if node and not net else 0
        # a pin without a number names no pad at all: it is not compared, as an unnumbered pad is not
        for pin in sorted(component.pins - numbers - {""}):
            node = nodes.get((ref, pin), "")
            severity: Severity = "error" if node and members[node] > 1 else "warning"
            found.append(ParityFinding(PIN_WITHOUT_PAD, severity, f"{ref}-{pin}", schematic=node))

    # an info per pad number, not per copper shape of that number
    unique = {(f.code, f.key, f.field, f.schematic, f.board): f for f in found if f.code == PAD_WITHOUT_PIN}
    found = [f for f in found if f.code != PAD_WITHOUT_PIN] + list(unique.values())
    findings = tuple(sorted(found, key=lambda f: (f.code, f.key, f.field, f.schematic, f.board)))
    counts = Counter(f.code for f in findings)
    summary: dict[str, int] = {code: counts.get(code, 0) for code in SUMMARY_KEYS[:-3]}
    summary["refs_one_side"] = counts.get(MISSING, 0) + counts.get(EXTRA, 0)
    summary["connections_missing"] = missing_connections
    summary["nets_split"] = sum(1 for net, on_board in seen.items() if on_board != {net})
    if issues is not None:
        issues += [finding_issue(f) for f in findings]
    return ParityReport(findings, MappingProxyType(summary))


__all__ = [
    "DUPLICATE",
    "EVIDENCE",
    "EXTRA",
    "FIELDS",
    "KICAD_TYPES",
    "MISMATCH",
    "MISSING",
    "NET_CONFLICT",
    "ORACLE_DIFFERS",
    "PAD_WITHOUT_PIN",
    "PARITY_ISSUE_CODES",
    "PIN_WITHOUT_PAD",
    "SHARED_ATTRIBUTES",
    "SUMMARY_KEYS",
    "ParityFinding",
    "ParityReport",
    "SchematicSide",
    "SideComponent",
    "compare",
    "finding_issue",
    "message",
    "oracle_entry",
]
