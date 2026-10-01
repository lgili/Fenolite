# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The neutral design model (normative text: openspec capability ``design-model``)."""

from fenolite.model.base import Entity, ExtBag, Modeled, Opaque, Slot
from fenolite.model.board import (
    Arc,
    Board,
    FootprintAttribute,
    FootprintInstance,
    Graphic,
    Hole,
    Keepout,
    Layer,
    Outline,
    Pad,
    Padstack,
    PadstackLayer,
    StackLayer,
    Stackup,
    Text,
    Track,
    Via,
    ViaType,
    Zone,
    ZoneFill,
)
from fenolite.model.circuit import Circuit, Component, Interface, Module, Net, NetClass, Pin, PinRef
from fenolite.model.design import Design, DesignHeader
from fenolite.model.findings import Findings
from fenolite.model.manufacturing import Artefact, Manifest, PnpRow
from fenolite.model.rules import Rule, RuleSet, RuleSubject, Selector

__all__ = [
    "Arc",
    "Artefact",
    "Board",
    "Circuit",
    "Component",
    "Design",
    "DesignHeader",
    "Entity",
    "ExtBag",
    "Findings",
    "FootprintAttribute",
    "FootprintInstance",
    "Graphic",
    "Hole",
    "Interface",
    "Keepout",
    "Layer",
    "Manifest",
    "Modeled",
    "Module",
    "Net",
    "NetClass",
    "Opaque",
    "Outline",
    "Pad",
    "Padstack",
    "PadstackLayer",
    "Pin",
    "PinRef",
    "PnpRow",
    "Rule",
    "RuleSet",
    "RuleSubject",
    "Selector",
    "Slot",
    "StackLayer",
    "Stackup",
    "Text",
    "Track",
    "Via",
    "ViaType",
    "Zone",
    "ZoneFill",
]
