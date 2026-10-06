# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Layers and stack-up of an imported board (capability altium-import, "Layers and stack-up";
``docs/formats/altium/import.md``, "Layers"; changes c0043 and c0124).

Copper layers are named by their position in the chain of the board record: ``F.Cu``, ``In<j>.Cu``,
``B.Cu``, whatever their Altium id. The other layers follow the closed table ``LAYERS``. Multi-Layer (74)
is no model layer. An internal plane (39 to 54) is a copper layer of the chain that is stored in negative: the
objects on it cut the plane and are no copper, so the import leaves them out and counts them per layer.
"""

# evidence: see import_evidence

from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from types import MappingProxyType

from fenolite.backends.altium.adapter import units
from fenolite.backends.altium.adapter.codes import issue
from fenolite.backends.altium.adapter.ids import Ids, bag
from fenolite.backends.altium.read.pcbstack import LAYER_NAMES, BoardRecord
from fenolite.backends.altium.read.rules import CopperLayer, CopperLayers
from fenolite.core.errors import Issue
from fenolite.core.provenance import Provenance
from fenolite.model.board import Layer, LayerKind, StackLayer, Stackup

TOP, BOTTOM, MULTI = 1, 32, 74
BACKEND = "altium"
FIRST_PLANE, LAST_PLANE = 39, 54
EDGE = "Edge.Cuts"
EDGE_ORDINAL = 100
ORDINAL_OFFSET = 100


def _table() -> dict[int, tuple[str, LayerKind]]:
    table: dict[int, tuple[str, LayerKind]] = {
        33: ("F.SilkS", "silkscreen"),
        34: ("B.SilkS", "silkscreen"),
        35: ("F.Paste", "solderpaste"),
        36: ("B.Paste", "solderpaste"),
        37: ("F.Mask", "soldermask"),
        38: ("B.Mask", "soldermask"),
        55: ("Altium.DrillGuide", "user"),
        56: ("Altium.KeepOut", "user"),
        73: ("Altium.DrillDrawing", "user"),
    }
    table.update({56 + n: (f"Mech.{n}", "mechanical") for n in range(1, 17)})
    return table


LAYERS: Mapping[int, tuple[str, LayerKind]] = MappingProxyType(_table())
"""Altium layer id → neutral name and kind, for the layers that are not copper (copper is named by chain
position, ``LayerMap``)."""


def copper_name(position: int, count: int) -> str:
    """The neutral name of the copper layer at ``position`` of a chain of ``count`` layers."""
    if position == 0:
        return "F.Cu"
    if position == count - 1:
        return "B.Cu"
    return f"In{position}.Cu"


class LayerMap:
    """The layers of one board: the copper chain, the names of the other layers, and which layers the
    imported objects use."""

    def __init__(self, chain: tuple[int, ...], record: BoardRecord | None = None) -> None:
        self.record = record
        self.issues: list[Issue] = []
        if len(chain) < 2:
            self.issues.append(
                issue(
                    "altium.import.bad-stack",
                    f"the copper chain holds {len(chain)} layer(s); the board is read with F.Cu and B.Cu",
                    "Board6/Data#0",
                )
            )
            chain = (TOP, BOTTOM)
        self.chain = chain
        self.copper: dict[int, str] = {
            layer: copper_name(position, len(chain)) for position, layer in enumerate(chain)
        }
        self.used: set[int] = set()
        self.cuts: Counter[int] = Counter()
        """Plane layer id → the free primitives on it that the import left out (``cut``)."""
        self._warned: set[int] = set()

    @classmethod
    def from_board(cls, record: BoardRecord) -> LayerMap:
        return cls(record.copper_chain, record)

    @classmethod
    def two_layer(cls) -> LayerMap:
        """The chain of a library: top and bottom."""
        return cls((TOP, BOTTOM))

    @property
    def copper_names(self) -> tuple[str, ...]:
        """The neutral copper names from top to bottom."""
        return tuple(self.copper[layer] for layer in self.chain)

    def is_copper(self, layer_id: int) -> bool:
        return layer_id in self.copper

    def is_plane(self, layer_id: int) -> bool:
        """Whether ``layer_id`` is an internal plane of the chain, on a net or not. Such a layer is stored in
        negative: an object on it is a place without copper (``import.md``, "Layers")."""
        return FIRST_PLANE <= layer_id <= LAST_PLANE and layer_id in self.copper

    def cut(self, layer_id: int) -> None:
        """Count one free primitive on the plane ``layer_id`` that gives no entity."""
        self.cuts[layer_id] += 1

    def copper_layers(self) -> CopperLayers:
        """The copper layers as the rule mapper takes them: the name the document gives each, its
        neutral name, and whether it is an internal signal layer (an id between top and bottom)."""
        return CopperLayers(
            tuple(
                CopperLayer(self.altium_name(layer), self.copper[layer], TOP < layer < BOTTOM)
                for layer in self.chain
            )
        )

    def peek(self, layer_id: int) -> str:
        """The neutral name of ``layer_id`` without marking it used: ``Altium.<id>`` outside the tables."""
        if layer_id in self.copper:
            return self.copper[layer_id]
        if layer_id in LAYERS:
            return LAYERS[layer_id][0]
        return f"Altium.{layer_id}"

    def name(self, layer_id: int) -> str:
        """The neutral name of ``layer_id``, marked as used. An id outside the chain and the table gives
        ``Altium.<id>`` and one ``altium.import.layer-outside-stack`` warning per id."""
        self.used.add(layer_id)
        if layer_id not in self.copper and layer_id not in LAYERS and layer_id not in self._warned:
            self._warned.add(layer_id)
            self.issues.append(
                issue(
                    "altium.import.layer-outside-stack",
                    f"layer {layer_id} is outside the copper chain and the layer table; "
                    f"its objects lie on Altium.{layer_id}",
                    f"Altium.{layer_id}",
                )
            )
        return self.peek(layer_id)

    def kind(self, layer_id: int) -> LayerKind:
        if layer_id in self.copper:
            return "copper"
        return LAYERS[layer_id][1] if layer_id in LAYERS else "user"

    def altium_name(self, layer_id: int) -> str:
        """The name the board record gives the layer, else the default name of the id, else ``""``."""
        if self.record is not None:
            for layer in self.record.layers:
                if layer.id == layer_id:
                    return layer.name
        return LAYER_NAMES.get(layer_id, "")

    def entities(self, ids: Ids, provenance: Provenance | None) -> tuple[Layer, ...]:
        """The ``Layer`` entities: every copper layer of the chain, ``Edge.Cuts``, and every other layer
        that ``name`` was asked for, in ordinal order. It is called after the primitives were read: the
        layer of a plane holds the count of what was left out on it (``plane_cuts``)."""
        out: list[Layer] = []

        def make(name: str, kind: LayerKind, ordinal: int, pairs: list[tuple[str, str]]) -> None:
            ident, native = ids.native("lay", f"layer:{name}")
            out.append(
                Layer(
                    id=ident,
                    native_ids=native,
                    provenance=provenance,
                    ext=bag(pairs),
                    name=name,
                    kind=kind,
                    ordinal=ordinal,
                )
            )

        planes: Mapping[int, str] = self.record.plane_nets if self.record is not None else {}
        for position, layer in enumerate(self.chain):
            pairs = [("layer_id", str(layer)), ("altium_name", self.altium_name(layer))]
            net = planes.get(layer - FIRST_PLANE + 1) if layer >= FIRST_PLANE else None
            if net:
                pairs.append(("plane_net", net))
            if self.cuts[layer]:
                pairs.append(("plane_cuts", str(self.cuts[layer])))
            make(self.copper[layer], "copper", position, pairs)
        make(EDGE, "edge", EDGE_ORDINAL, [])
        for layer in sorted(self.used - set(self.copper) - {MULTI}):
            pairs = [("layer_id", str(layer)), ("altium_name", self.altium_name(layer))]
            make(self.peek(layer), self.kind(layer), layer + ORDINAL_OFFSET, pairs)
        return tuple(out)


def copper_layers_of(layers: Iterable[Layer]) -> CopperLayers | None:
    """``LayerMap.copper_layers`` read back from the layers of an imported board (the ``layer_id`` and
    ``altium_name`` pairs of their ``altium`` bags), in ordinal order; ``None`` when a copper layer holds
    no such pairs (a board that is no import), so that no layer condition maps for it."""
    found: list[CopperLayer] = []
    for layer in sorted((entry for entry in layers if entry.kind == "copper"), key=lambda e: e.ordinal):
        pairs = dict(layer.ext[BACKEND].payload) if BACKEND in layer.ext else {}
        ident = pairs.get("layer_id", "")
        if "altium_name" not in pairs or not (ident.isascii() and ident.isdigit()):
            return None
        found.append(CopperLayer(pairs["altium_name"], layer.name, TOP < int(ident) < BOTTOM))
    return CopperLayers(tuple(found))


def _thickness(text: str | None, where: str, issues: list[Issue]) -> int | None:
    found = units.text_length(text)
    if found is None:
        issues.append(
            issue("altium.import.bad-length", "a stack thickness is not a length in mil or mm", where)
        )
        return None
    return found[0]


def stackup(
    record: BoardRecord, layers: LayerMap, ids: Ids, provenance: Provenance | None, issues: list[Issue]
) -> Stackup | None:
    """The stack-up: from the physical list when the record holds copper or dielectric entries (the
    entries of other kinds, overlays and masks, are left out), else from the numbered layers of the chain
    with one dielectric between neighbours. ``None`` when neither gives a layer."""
    found: list[tuple[str, str, int, str, str, str]] = []
    physical = [entry for entry in record.stack if entry.kind in ("signal", "plane", "dielectric")]
    if physical:
        for entry in physical:
            where = f"Board6/Data#0:V9_STACK_LAYER{entry.index}"
            if entry.kind == "dielectric":
                thickness = _thickness(entry.diel_height, where, issues)
                if thickness is not None:
                    found.append(
                        (
                            entry.name or f"dielectric {entry.number}",
                            "dielectric",
                            thickness,
                            entry.diel_material or "",
                            entry.diel_const or "",
                            entry.get("DIELLOSSTANGENT") or "",
                        )
                    )
                continue
            number = entry.number or 0
            layer_id = number if entry.kind == "signal" else FIRST_PLANE + number - 1
            thickness = _thickness(entry.copper_thickness, where, issues)
            if thickness is not None:
                found.append((layers.peek(layer_id), "copper", thickness, "", "", ""))
    else:
        numbered = {layer.id: layer for layer in record.layers}
        for position, layer_id in enumerate(layers.chain):
            layer = numbered.get(layer_id)
            if layer is None:
                continue
            where = f"Board6/Data#0:LAYER{layer_id}"
            thickness = _thickness(layer.copper_thickness, where, issues)
            if thickness is not None:
                found.append((layers.copper[layer_id], "copper", thickness, "", "", ""))
            if position < len(layers.chain) - 1:
                height = _thickness(layer.diel_height, where, issues)
                if height is not None:
                    name = f"dielectric {position + 1}"
                    found.append(
                        (name, "dielectric", height, layer.diel_material or "", layer.diel_const or "", "")
                    )
    if not found:
        return None
    entries: list[StackLayer] = []
    for position, (name, kind, thickness, material, epsilon, loss) in enumerate(found):
        ident, native = ids.native("sly", f"stack:{position}")
        entries.append(
            StackLayer(
                id=ident,
                native_ids=native,
                provenance=provenance,
                name=name,
                kind="copper" if kind == "copper" else "dielectric",
                thickness=thickness,
                material=material,
                epsilon_r=epsilon,
                loss_tangent=loss,
            )
        )
    ident, native = ids.native("stk", "stackup")
    return Stackup(id=ident, native_ids=native, provenance=provenance, layers=tuple(entries))


__all__ = ["EDGE", "LAYERS", "MULTI", "LayerMap", "copper_name", "stackup"]
