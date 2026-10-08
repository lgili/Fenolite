# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The catalog's default pin-to-pad map, applied to the model of a design script (change c0147).

A part of an anode-first catalog symbol (pin 1 ``A``, pin 2 ``K``) on a catalog land whose pad 1 is the
cathode, that gives no ``pad_map``, gets ``catalog.CATHODE_FIRST_PAD_MAP``: the anode pin on the anode pad
and the cathode pin on the cathode pad (capability fenolite-component-catalog, "Default pin-to-pad map of
the cathode-first lands"). An explicit map always wins. A symbol or footprint that the design authors under
the same lib id is not the catalog's, and gets no default. The model is shared by the KiCad and the Altium
targets, so both write the same pad nets; ``cmd_build`` reports each part (``build.pad-map-default``).
"""

from __future__ import annotations

import dataclasses
from collections.abc import Collection

from fenolite.catalog import default_pad_map
from fenolite.dsl.convert import PATH_PROPERTY
from fenolite.model.circuit import Component
from fenolite.model.design import Design


@dataclasses.dataclass(frozen=True, slots=True)
class DefaultPadMap:
    """One part that got the catalog's default map: its reference, path, symbol, land and pairs."""

    ref: str
    path: str
    symbol: str
    footprint: str
    pairs: tuple[tuple[str, str], ...]


def apply_default_pad_maps(
    model: Design, *, authored_symbols: Collection[str] = (), authored_footprints: Collection[str] = ()
) -> tuple[Design, tuple[DefaultPadMap, ...]]:
    """``model`` with the catalog's default map on every component that needs one, and those components
    in model order. A component that holds a map, or whose symbol or footprint the design authors, is
    left as it is; a model without such a component is returned unchanged."""
    applied: list[DefaultPadMap] = []
    components: list[Component] = []
    for component in model.circuit.components:
        pairs: tuple[tuple[str, str], ...] = ()
        if (
            not component.pin_pad_map
            and component.lib_symbol_ref not in authored_symbols
            and component.lib_footprint_ref not in authored_footprints
        ):
            pairs = default_pad_map(component.lib_symbol_ref, component.lib_footprint_ref)
        if pairs:
            path = component.properties.get(PATH_PROPERTY, component.ref)
            applied.append(
                DefaultPadMap(
                    component.ref, path, component.lib_symbol_ref, component.lib_footprint_ref, pairs
                )
            )
            component = dataclasses.replace(component, pin_pad_map=pairs)
        components.append(component)
    if not applied:
        return model, ()
    circuit = dataclasses.replace(model.circuit, components=tuple(components))
    return dataclasses.replace(model, circuit=circuit), tuple(applied)


__all__ = ["DefaultPadMap", "apply_default_pad_maps"]
