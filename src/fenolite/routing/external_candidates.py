# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Opt-in local external-candidate contracts; backend construction belongs to orchestration.

No downloads, plugin discovery or processes start when this module is imported. A descriptor
is supplied by the CLI's explicit allowlist of existing subprocess adapters (c0368).
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Literal, cast

from fenolite.core.coords import Point
from fenolite.core.evidence import Evidence, Level
from fenolite.model.board import Track, Via
from fenolite.routing.budget import Budget
from fenolite.routing.protocol import Candidate, JobSubject, RouterStatus, RoutingJob, RoutingResult
from fenolite.routing.search import coupled_nets

EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-G-EXTERNAL-SCOPE", "H-G-EXTERNAL-BUDGET"))

SUPPORTED = ("freerouting", "kicadroutingtools")


@dataclass(frozen=True, slots=True)
class Adapter:
    """A locally configured existing adapter, not an arbitrary discovered router.

    ``prepare`` must use the supplied shared budget for any availability subprocess.
    ``route`` must validate the *raw* board/session delta before lifting selected copper.
    Tool inputs are reviewed dependencies; version alone never proves reproducibility.
    """

    name: str
    projection: Literal["board", "copper"]
    prepare: Callable[[Budget], RouterStatus]
    route: Callable[[RoutingJob], RoutingResult]
    dependencies: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.name not in SUPPORTED:
            raise ValueError("external candidates require an explicitly supported local adapter")
        expected = "board" if self.name == "kicadroutingtools" else "copper"
        if self.projection != expected:
            raise ValueError("adapter projection does not match its immutable-delta contract")


@dataclass(frozen=True, slots=True)
class Provenance:
    """Stable tool/job identity; elapsed time is deliberately not identity or a score."""

    router: str
    version: str
    inputs: str
    job: str
    deterministic: bool = False


@dataclass(frozen=True, slots=True)
class Outcome:
    """Nothing is applied: independently reviewed candidates, provenance and explicit refusals."""

    candidates: tuple[Candidate, ...] = ()
    provenance: tuple[tuple[str, Provenance], ...] = ()
    refusals: tuple[tuple[str, str, tuple[str, ...]], ...] = ()
    not_attempted: tuple[tuple[str, str], ...] = ()


def unsupported(job: RoutingJob, subject: JobSubject) -> str:
    """Never route one leg of an atomic pair/group as an ordinary connection."""
    if (
        subject.kind != "connection"
        or subject.group
        or subject.net in coupled_nets(job)
        or any(role.net == subject.net for role in job.roles)
        or any(subject.net in escape.nets for escape in job.escape)
        or subject.a.net != subject.net
        or subject.b.net != subject.net
    ):
        return "external-unsupported"
    return ""


class MissingTool(ValueError):
    """A specifically requested local tool is missing; orchestration maps this to exit 6."""

    def __init__(self, router: str, status: RouterStatus) -> None:
        self.router = router
        self.status = status
        super().__init__(status.reason or f"{router} is unavailable")


_SPELLING = re.compile(r"\((start|end|at|width|size|drill) ((?:-?\d+(?:\.\d+)? ?){1,2})\)")
"""A KiCad child that only spells a modelled number of the item, e.g. ``(start 106.000000 110.800000)``."""


def _mm_nm(text: str) -> int | None:
    """Exact nanometres of a decimal millimetre literal, or ``None`` when it is not a whole nanometre."""
    from decimal import Decimal

    value = Decimal(text) * 1_000_000
    return int(value) if value == value.to_integral_value() else None


def _respelled(item: Track | Via, fragment: str) -> bool:
    """True when an opaque KiCad slot only re-spells a value the item models, digit for digit.

    The KiCad reader keeps a modelled child whose text the writer would not reproduce byte for byte
    (``kicad.board.kept-opaque``), so a tool that writes ``106.000000`` leaves a slot whose value is
    already in the model. Any other content, or a value that differs from the model, stays opaque.
    """
    match = _SPELLING.fullmatch(fragment.strip())
    if match is None:
        return False
    head, numbers = match.group(1), tuple(_mm_nm(n) for n in match.group(2).split())
    if isinstance(item, Track):
        expected: dict[str, tuple[int, ...]] = {
            "start": (item.start.x, item.start.y),
            "end": (item.end.x, item.end.y),
            "width": (item.width,),
        }
    else:
        at = (item.position.x, item.position.y)
        expected = {"at": at, "size": (item.diameter,), "drill": (item.drill,)}
    return head in expected and numbers == expected[head]


def _opaque(item: Track | Via) -> bool:
    from dataclasses import fields

    modeled = {field.name for field in fields(item)}

    def kept(key: str, value: str) -> bool:
        if key == "slot:.:modeled":
            return value in modeled
        return key.startswith("slot:.:opaque") and _respelled(item, value)

    return any(
        backend != "kicad" or not all(kept(key, value) for key, value in bag.payload)
        for backend, bag in item.ext.items()
    )


def _candidate(job: RoutingJob, subject: JobSubject, router: str, result: RoutingResult) -> Candidate:
    from dataclasses import replace

    from fenolite.core.ids import content_hash, derived_id
    from fenolite.model.canonical import to_data
    from fenolite.routing.octilinear import length
    from fenolite.routing.propose import candidate_id

    def clean(item: Track | Via) -> Track | Via:
        return replace(item, id="", native_ids={}, provenance=None, ext={}, locked=False)

    copper = sorted((*result.tracks, *result.vias), key=lambda item: content_hash(to_data(clean(item))))
    source = f"external:{router}"
    ident = candidate_id(subject.key, source, (), [to_data(clean(item)) for item in copper])
    tracks: list[Track] = []
    vias: list[Via] = []
    for index, item in enumerate(copper):
        ident_item = derived_id("trk" if isinstance(item, Track) else "via", "proposal", f"{ident}:{index}")
        made = replace(clean(item), id=ident_item)
        if isinstance(made, Track):
            tracks.append(made)
        else:
            vias.append(made)
    used = set(job.layers) if vias else {track.layer for track in tracks}
    return Candidate(
        ident,
        subject.key,
        source,
        tracks=tuple(tracks),
        vias=tuple(vias),
        length=sum(length((track.start, track.end)) for track in tracks),
        layers=tuple(layer for layer in job.layers if layer in used),
    )


def generate_external(
    job: RoutingJob,
    subjects: tuple[JobSubject, ...],
    routers: tuple[Adapter, ...],
    *,
    budget: Budget,
    judge: Callable[[JobSubject, Candidate], str] | None,
) -> Outcome:
    """Generate whole, scoped candidates through existing adapters under one shared budget.

    The orchestration judge proves selected-component connectivity and final copper/role
    findings. Without that judge nothing runs. All tool outputs, including success with partial
    errors, fail closed; elapsed time is not included in candidate identity or provenance.
    """
    from dataclasses import replace

    from fenolite.core.ids import content_hash
    from fenolite.core.progress import NULL_PROGRESS
    from fenolite.model.canonical import to_data
    from fenolite.routing.negotiate import joint_geometry
    from fenolite.routing.octilinear import World
    from fenolite.routing.search_fields import board_fingerprint

    candidates: list[Candidate] = []
    provenance: list[tuple[str, Provenance]] = []
    refusals: list[tuple[str, str, tuple[str, ...]]] = []
    pending: list[tuple[str, str]] = []
    ordered = sorted({adapter.name: adapter for adapter in routers}.values(), key=lambda a: a.name)
    selected = sorted({subject.key: subject for subject in subjects}.values(), key=lambda s: s.key)
    for adapter in ordered:
        status: RouterStatus | None = None
        for subject in selected:
            if reason := unsupported(job, subject):
                refusals.append((subject.key, reason, (adapter.name,)))
                continue
            if judge is None:
                refusals.append((subject.key, "external-judge-missing", (adapter.name,)))
                continue
            if budget.left() <= 0:
                pending.append((subject.key, adapter.name))
                continue
            if status is None:
                status = adapter.prepare(budget)
                if budget.left() <= 0:
                    pending.append((subject.key, adapter.name))
                    continue
                if not status.available:
                    raise MissingTool(adapter.name, status)
            nets = tuple(net for net in job.nets if net.name == subject.net)
            if len(nets) != 1:
                refusals.append((subject.key, "external-net-missing", (adapter.name,)))
                continue
            extra = {
                **job.extra,
                "external_candidate": True,
                "routing_budget": budget,
                "external_status": status,
            }
            scoped = replace(
                job,
                nets=nets,
                subjects=(),
                pairs=(),
                roles=(),
                escape=(),
                options={},
                extra=extra,
                on_run=None,
                progress=NULL_PROGRESS,
            )
            result = adapter.route(scoped)
            reason = ""
            if (
                budget.left() <= 0
                or any(run.outcome != "done" for run in result.runs)
                or result.not_attempted
            ):
                reason = "external-incomplete"
            elif any(issue.severity == "error" for issue in result.issues):
                reason = "external-tool-failed"
            elif result.arcs or not result.tracks:
                reason = "external-unsupported-output"
            elif any(item.net_id != nets[0].net_id for item in (*result.tracks, *result.vias)):
                reason = "external-unselected-copper"
            elif any(_opaque(item) or item.locked for item in (*result.tracks, *result.vias)):
                reason = "external-unsupported-output"
            elif any(
                via.via_type != "through"
                or via.layers != (job.layers[0], job.layers[-1])
                or via.diameter < subject.via_diameter
                or via.drill != subject.via_drill
                or via.drill <= 0
                or via.diameter <= via.drill
                for via in result.vias
            ):
                reason = "external-via-scope"
            if not reason:
                candidate = _candidate(job, subject, adapter.name, result)
                pads = job.extra.get("board_pads", ())
                outline = job.extra.get("outline", ())
                if not isinstance(pads, tuple) or not isinstance(outline, tuple) or not outline:
                    reason = "external-geometry-missing"
                elif not joint_geometry(
                    replace(job, subjects=(subject,)),
                    World(job, cast(tuple[object, ...], pads), cast(tuple[tuple[Point, ...], ...], outline)),
                    (candidate,),
                ):
                    reason = "external-geometry"
                else:
                    reason = judge(subject, candidate)
                if not reason and budget.left() <= 0:
                    reason = "external-incomplete"
                if not reason:
                    candidates.append(candidate)
                    provenance.append(
                        (
                            candidate.id,
                            Provenance(
                                adapter.name,
                                status.version,
                                content_hash(adapter.dependencies),
                                content_hash(
                                    board_fingerprint(job.design),
                                    to_data(subject),
                                    to_data(nets),
                                    job.layers,
                                    dict(job.options),
                                ),
                            ),
                        )
                    )
            if reason:
                details = tuple(
                    f"{issue.code}: {issue.message}"[:300]
                    for issue in result.issues
                    if issue.severity == "error"
                )
                refusals.append((subject.key, reason, (adapter.name, *details)))
    return Outcome(tuple(candidates), tuple(provenance), tuple(refusals), tuple(pending))
