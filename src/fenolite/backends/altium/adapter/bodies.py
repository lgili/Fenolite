# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Component bodies of imported footprints (capability altium-import, "Component body records";
``docs/formats/altium/pcb-bodies.md``, "Mapping to the model"; change c0043)."""

# evidence: see import_evidence

from __future__ import annotations

from fenolite.backends.altium.adapter import units
from fenolite.backends.altium.adapter.codes import issue
from fenolite.backends.altium.adapter.context import Context
from fenolite.backends.altium.adapter.copper import region_points
from fenolite.backends.altium.adapter.ids import Exact, bag
from fenolite.backends.altium.read.bodies import BodyRecord
from fenolite.geometry.transform import Transform
from fenolite.model.board import ComponentBody, Side


def component_body(
    record: BodyRecord,
    frame: Transform | None,
    ctx: Context,
    *,
    locator: str,
    section: str,
    mounted_side: Side = "top",
) -> ComponentBody:
    """The model body of ``record`` with its outline in the footprint frame (``frame`` is the inverse of
    the footprint's placement; ``None`` in a library). Every input body is kept; unproved heights or
    projection are marked unknown (c0099). Reader records retain native bytes, without an ext copy."""
    overall, standoff = record.overall_height, record.standoff_height
    reasons: list[str] = []
    if overall is None or standoff is None:
        ctx.issues.append(
            issue("altium.import.bad-length", "a height of the component body is not a length", locator)
        )
        reasons.append("invalid source height")
    # S-0709 supports this ordinal interpretation, but does not prove file encoding.
    projection = record.body_projection
    projected_side = "top" if projection == 0 else "bottom" if projection == 1 else None
    if projected_side != mounted_side:
        reasons.append("unproved or different projection side")
    if overall is not None and standoff is not None and overall < standoff:
        reasons.append("overall height below standoff")
    if record.properties.text("MODEL.MODELTYPE") not in ("", "0", "1"):
        reasons.append("unsupported model type")
    if reasons:
        ctx.issues.append(
            issue("altium.import.body-unknown", "; ".join(reasons) + "; body retained", locator)
        )
    exact = Exact(ctx.census)
    height, height_exact = (0, True) if overall is None else units.units_length(overall)
    stand, stand_exact = (0, True) if standoff is None else units.units_length(standoff)
    if not height_exact:
        exact.inexact("height", str(overall))
    if not stand_exact:
        exact.inexact("standoff", str(standoff))
    absolute = region_points(record.outline)
    outline = absolute if frame is None else tuple(frame.apply(point) for point in absolute)
    layer = ctx.layers.name(record.layer) if record.layer is not None else ""
    model = record.model_name
    kind = "model" if model else "extruded"
    name = record.identifier
    ident = ctx.ids.content(
        "bdy", section, kind, height, stand, [[p.x, p.y] for p in outline], layer, model, name
    )
    return ComponentBody(
        id=ident,
        provenance=ctx.provenance(locator),
        ext=bag(exact.pairs()),
        kind=kind,
        height=height,
        standoff=stand,
        outline=outline,
        layer=layer,
        model=model,
        name=name,
        z_min=None if reasons else stand,
        z_max=None if reasons else height,
        projection_unknown=bool(reasons),
    )


__all__ = ["component_body"]
