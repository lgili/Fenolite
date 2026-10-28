# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The glue of ``fenolite place --strategy reuse`` (capability layout-reuse, "Placement of a copied
block" and "Copper of a copied block"; ``docs/placement.md``, "Layout reuse").

``fenolite.reuse`` fits the block and maps the copper; this module moves the footprints with
``backends.kicad.replace.move_footprint``, measures the moved pads against the fit, picks the reference
copper of the block and the pads that each reference zone joins, and settles the copy on the target board:
it prunes what ends nowhere with ``tidy.prune``, drops islands and copied zones that lost a pad, and drops
what the copper check finds, until nothing changes.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection, Mapping, Sequence
from dataclasses import dataclass
from math import isqrt

from fenolite.backends.base import BoardPad
from fenolite.backends.kicad.replace import PlacementError, move_footprint
from fenolite.core.errors import Issue
from fenolite.model.board import Arc, Track, Via, Zone
from fenolite.model.design import Design
from fenolite.model.library import FootprintDef
from fenolite.reuse import BlockFit, CopiedItem, CopperCopy, Dropped, Layout, with_copper, with_outlines
from fenolite.reuse.codes import issue
from fenolite.reuse.copper import Copper
from fenolite.tidy import Check, fresh_clashes, prune
from fenolite.tidy.graph import Piece, groups, net_pieces

COPPER_KINDS = ("track", "arc", "via")


@dataclass(frozen=True, slots=True)
class Moved:
    """The target board with the fitted parts moved, the ids of the footprints that moved, and the
    issues of the moves (``place.locked``, ``place.no-definition``)."""

    design: Design
    moved: tuple[str, ...]
    issues: tuple[Issue, ...]


def apply_fit(design: Design, fit: BlockFit, *, definitions: Mapping[str, FootprintDef]) -> Moved:
    """``design`` with each placed part of ``fit`` at its new placement. A part already there is not
    touched, so a locked anchor stays without ``--force``; a turn or a side change needs the part's
    library definition in ``definitions`` (by lib id)."""
    moved: list[str] = []
    issues: list[Issue] = []
    for part in fit.placed:
        placement = part.placement
        assert placement is not None
        if placement == part.before:
            continue
        try:
            changed = move_footprint(
                design,
                part.footprint_id,
                at=placement.at,
                rotation=placement.rotation,
                side=placement.side,
                definitions=definitions,
            )
        except PlacementError as error:
            issues.extend(error.issues)
            continue
        if changed is not design:
            design = changed
            moved.append(part.footprint_id)
    return Moved(design, tuple(moved), tuple(issues))


def _distance(dx: int, dy: int) -> int:
    square = dx * dx + dy * dy
    root = isqrt(square)
    return root if root * root == square else root + 1


def landed(fit: BlockFit, pads: Sequence[BoardPad]) -> dict[str, BoardPad]:
    """Reference pad id → the record of ``pads`` (the board after the moves) of its paired pad: the pad of
    the part's footprint with the pair's number nearest the goal, since a move may give pads new ids and
    pads paired by net may share a number."""
    records: dict[tuple[str, str], list[BoardPad]] = {}
    for record in pads:
        records.setdefault((record.footprint_id, record.number), []).append(record)
    found: dict[str, BoardPad] = {}
    for part in fit.placed:
        for match in part.pads:
            held = records.get((part.footprint_id, match.number), [])
            if held:
                found[match.reference_pad_id] = min(
                    held,
                    key=lambda record: (
                        _distance(record.position.x - match.goal.x, record.position.y - match.goal.y),
                        record.pad_id,
                    ),
                )
    return found


def misplaced(fit: BlockFit, pads: Sequence[BoardPad], *, moved: Collection[str]) -> list[Issue]:
    """A ``reuse.check-failed`` for each moved part with a pad farther than the tolerance from its goal,
    measured on ``pads``, the board-frame records of the board after the moves."""
    found = landed(fit, pads)
    issues: list[Issue] = []
    for part in fit.placed:
        if part.footprint_id not in moved:
            continue
        for match in part.pads:
            record = found.get(match.reference_pad_id)
            if record is None:
                far = None
            else:
                far = _distance(record.position.x - match.goal.x, record.position.y - match.goal.y)
            if far is None or far > fit.tolerance:
                where = "is missing" if far is None else f"lies {far} nm from its goal"
                issues.append(
                    issue(
                        "reuse.check-failed",
                        f"pad {match.number} of {part.ref} {where} after the move; nothing is written",
                        where=part.ref,
                        hint="report the two boards: the fit and the move disagree",
                    )
                )
                break
    return issues


def block_items(reference: Layout, fit: BlockFit) -> frozenset[str]:
    """The reference tracks, arcs and vias joined to a paired pad of a placed part, through tracks, arcs,
    vias and those pads only: neither fills nor other pads join, so a plane does not bring the whole
    net in."""
    paired = {match.reference_pad_id for part in fit.placed for match in part.pads}
    pads = [record for record in reference.pads if record.pad_id in paired]
    shaped = net_pieces(with_outlines(reference.design), pads)
    found: set[str] = set()
    for net, held in shaped.pieces.items():
        if net in shaped.unsupported:
            continue
        pieces = [piece for piece in held if piece.kind != "fill"]
        roots = groups(pieces)
        joined = {roots[piece.ident] for piece in pieces if piece.kind == "pad"}
        found.update(
            piece.ident for piece in pieces if piece.kind in COPPER_KINDS and roots[piece.ident] in joined
        )
    return frozenset(found)


@dataclass(frozen=True, slots=True)
class Settled:
    """The target board with the copper that stays (locked), the copies that stay, every item left out
    with its reason, and the issues (``reuse.check-failed`` for a finding that names no copy)."""

    design: Design
    kept: tuple[CopiedItem, ...]
    dropped: tuple[Dropped, ...]
    issues: tuple[Issue, ...]
    passes: int


def _held(design: Design) -> list[Track | Arc | Via]:
    board = design.board
    return [*board.tracks, *board.arcs, *board.vias] if board is not None else []


def settle_copper(
    placed: Design,
    copy: CopperCopy,
    *,
    pads: Sequence[BoardPad],
    check: Check,
    images: Mapping[str, str] | None = None,
) -> Settled:
    """``placed`` with the copies of ``copy`` that stay, locked. Pass after pass until one drops nothing:

    1. ``tidy.prune`` on the copies' nets removes copies with a free end and vias joined on fewer than two
       layers (the copper of ``placed`` is kept), and a net it cannot shape drops its copies;
    2. a group of a net (as the copper check joins copper, fills included) whose copies join fewer than
       two pads and neither copper nor a fill of ``placed`` is an island, and its copies go; a copied zone
       whose group lacks the image of a pad its reference fill joined goes as ``pad-lost``;
    3. the copper check of the board, against that of ``placed``: each copy a new finding names goes,
       with the finding's code as its reason.

    ``pads`` are the board-frame pad records of ``placed``; ``images`` maps a reference pad id to the id
    of its paired pad there (``landed``), for the pads of copied zones."""
    live = {item.item.id: item for item in copy.items}
    dropped = list(copy.dropped)
    base = check(placed)
    old = {item.id for item in _held(placed)}
    names = {net.id: net.name for net in placed.circuit.nets}
    images = images or {}
    issues: list[Issue] = []
    passes = 0

    def drop(ident: str, reason: str, detail: str) -> None:
        held = live.pop(ident)
        dropped.append(Dropped(held.source, kind_of(held.item), held.net, reason, detail))

    def copied(piece: Piece) -> str | None:
        """The id of the copy a piece belongs to (a fill: its zone), or ``None``."""
        ident = piece.ident.split("#", 1)[0] if piece.kind == "fill" else piece.ident
        return ident if ident in live else None

    while live:
        passes += 1
        design = with_copper(placed, [held.item for held in live.values()])
        nets = sorted({names.get(held.item.net_id or "", "") for held in live.values()} - {""})
        pruned = prune(design, pads=pads, nets=nets, keep=old)
        before = len(live)
        for edit in pruned.edits:
            for ident in edit.removed:
                if ident in live:
                    drop(ident, edit.reason, f"pruned at {edit.at.x},{edit.at.y} nm")
        skipped = {found.where for found in pruned.issues if found.code == "tidy.net-skipped"}
        for ident, held in list(live.items()):
            if names.get(held.item.net_id or "", "") in skipped:
                drop(ident, "net-skipped", "the target net holds copper that could not be shaped")
        if len(live) != before:
            continue
        shaped = net_pieces(design, pads)
        for net in sorted({held.item.net_id for held in live.values() if held.item.net_id is not None}):
            pieces = shaped.pieces.get(net, ())
            roots = groups(pieces)
            for root in sorted({roots[piece.ident] for piece in pieces if copied(piece) is not None}):
                members = [piece for piece in pieces if roots[piece.ident] == root]
                pad_count = sum(1 for piece in members if piece.kind == "pad")
                anchored = any(
                    piece.ident in old or (piece.kind == "fill" and copied(piece) is None)
                    for piece in members
                )
                held_pads = {piece.ident for piece in members if piece.kind == "pad"}
                for piece in members:
                    owner = copied(piece)
                    if owner is None:
                        continue
                    if pad_count < 2 and not (pad_count >= 1 and anchored):
                        drop(owner, "island", f"it joins {pad_count} pad(s) of its net")
                        continue
                    lost = [pad for pad in live[owner].joins if images.get(pad) not in held_pads]
                    if lost:
                        drop(owner, "pad-lost", f"its copy no longer joins {len(lost)} of its pads")
        if len(live) != before:
            continue
        fresh = fresh_clashes(base, check(design))
        named = False
        for clash in fresh:
            for ident in clash.items:
                if ident in live:
                    drop(ident, clash.code, f"on {clash.layer}, {clash.gap} nm from {', '.join(clash.items)}")
                    named = True
        if named:
            continue
        for clash in fresh:
            issues.append(
                issue(
                    "reuse.check-failed",
                    f"the board with the copied copper has {clash.code} on {clash.layer} between "
                    f"{', '.join(clash.items)} that the board before lacks; nothing is written",
                    where=", ".join(clash.items),
                    hint="report the two boards; run reuse without --copper meanwhile",
                )
            )
        break
    kept = tuple(
        dataclasses.replace(held, item=dataclasses.replace(held.item, locked=True)) for held in live.values()
    )
    design = with_copper(placed, [held.item for held in kept])
    order = {item.item.id: index for index, item in enumerate(copy.items)}
    kept = tuple(sorted(kept, key=lambda held: order[held.item.id]))
    return Settled(design, kept, tuple(dropped), tuple(issues), passes)


def zone_pads(reference: Layout) -> dict[str, frozenset[str]]:
    """Reference zone id → the ids of the pads its stored fill joins, through any copper of its net, as
    the copper check joins copper (a zone without an outline takes that of its fill); zones without a fill,
    or of a net that cannot be shaped, are left out."""
    shaped = net_pieces(with_outlines(reference.design), reference.pads)
    found: dict[str, set[str]] = {}
    for net, pieces in shaped.pieces.items():
        if net in shaped.unsupported:
            continue
        roots = groups(pieces)
        joined: dict[int, set[str]] = {}
        for piece in pieces:
            if piece.kind == "pad":
                joined.setdefault(roots[piece.ident], set()).add(piece.ident)
        for piece in pieces:
            if piece.kind == "fill":
                zone = piece.ident.split("#", 1)[0]
                found.setdefault(zone, set()).update(joined.get(roots[piece.ident], set()))
    return {zone: frozenset(pads) for zone, pads in found.items()}


def kind_of(item: Copper) -> str:
    """``track``, ``arc``, ``via`` or ``zone``."""
    if isinstance(item, Zone):
        return "zone"
    return "via" if isinstance(item, Via) else "arc" if isinstance(item, Arc) else "track"


__all__ = [
    "COPPER_KINDS",
    "Moved",
    "Settled",
    "apply_fit",
    "block_items",
    "kind_of",
    "landed",
    "misplaced",
    "settle_copper",
    "zone_pads",
]
