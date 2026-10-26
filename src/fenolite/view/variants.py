# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The assembly variants of an Altium project on its sheets and its board (capability variant-view, change
c0186).

``variant_states(variants, sheets)`` resolves each variant of ``read.variants`` to the parts as the scenes
name them: a part variation is matched by the last segment of its ``UniqueId`` path against the unique ids
of the sheets' parts (a variation keeps the designator the part had when it was made, ``X?`` for one never
annotated), and by its designator when the path names a part of a repeated channel or no part has the id.
The result maps each variant name to ``{ref: {"kind": ..., "params": {...}}}``; scenes carry it as
``variants`` and the page shows the one chosen. Standard library only.
"""

from __future__ import annotations

from typing import Any, cast

from fenolite.backends.altium.read.variants import KINDS, Variant

NO_VARIATIONS = "[No Variations]"


def _uids(sheets: dict[str, dict[str, Any]]) -> dict[str, str]:
    out: dict[str, str] = {}
    for scene in sheets.values():
        for comp in cast("list[dict[str, Any]]", scene.get("comps", [])):
            uid = comp.get("uid")
            if uid:
                out[str(uid)] = str(comp.get("group") or comp["ref"])
    return out


def variant_states(
    variants: tuple[Variant, ...], sheets: dict[str, dict[str, Any]]
) -> dict[str, dict[str, dict[str, Any]]]:
    """Per variant name, the state of every part it varies, keyed by the part's reference in the scenes."""
    uids = _uids(sheets)
    out: dict[str, dict[str, dict[str, Any]]] = {}
    for variant in variants:
        states: dict[str, dict[str, Any]] = {}
        renamed: dict[str, str] = {}
        for variation in variant.variations:
            path = [segment for segment in variation.unique_id.split("\\") if segment]
            ref = uids.get(path[-1]) if len(path) == 1 else None
            ref = ref or variation.designator
            renamed[variation.designator] = ref
            states[ref] = {"kind": KINDS.get(variation.kind, "unknown"), "params": {}}
        for designator, values in variant.parameters.items():
            ref = renamed.get(designator, designator)
            states.setdefault(ref, {"kind": KINDS[0], "params": {}})["params"] = dict(values)
        out[variant.name or f"Variant {len(out) + 1}"] = states
    return out


def counts(states: dict[str, dict[str, Any]], refs: list[str]) -> dict[str, int]:
    """How many of ``refs`` a variant fits and does not fit."""
    not_fitted = sum(1 for ref in refs if states.get(ref, {}).get("kind") == "not fitted")
    return {"fitted": len(refs) - not_fitted, "not_fitted": not_fitted}


__all__ = ["NO_VARIATIONS", "counts", "variant_states"]
