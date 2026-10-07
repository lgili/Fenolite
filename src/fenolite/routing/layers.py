# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Routing layers of a job: the copper layers that hold no plane, and the layers a net's tracks may use.

A plane layer takes no track (``RoutingJob.plane_layers``). A design rule of the kind ``no_tracks`` keeps
the tracks of the items it selects off its layers: ``allowed_layers`` subtracts those layers for one net
(capability routing, "Plane and routing layers in a routing job"; change c0107). The rule kind is not the
``no_tracks`` flag of a keep-out, which forbids tracks inside an outline whatever their net.
"""

from __future__ import annotations

from collections.abc import Collection, Sequence

from fenolite.model.circuit import Net
from fenolite.model.design import Design
from fenolite.model.rules import RuleSubject

DEFAULT_CLASS = "Default"
"""The class name a net without a class is matched under, as KiCad names it."""


def routing_layers(layers: Sequence[str], plane_layers: Collection[str]) -> tuple[str, ...]:
    """The members of ``layers`` that are not plane layers, in order."""
    return tuple(layer for layer in layers if layer not in plane_layers)


def class_name(design: Design, net: Net) -> str:
    """The name of the net's class, or ``Default``."""
    for netclass in design.circuit.netclasses:
        if netclass.id == net.netclass_id:
            return netclass.name
    return DEFAULT_CLASS


def allowed_layers(design: Design, net: Net, routing_layers: Sequence[str]) -> tuple[str, ...]:
    """The members of ``routing_layers`` that no ``no_tracks`` rule of the design forbids to ``net``.

    A rule of severity other than ``ignore`` forbids its ``layers`` when its ``selector_a`` matches a track
    of the net, under the net's name and the name of its class (``Default`` without one).
    """
    if design.rules is None:
        return tuple(routing_layers)
    subject = RuleSubject("track", net=net.name, netclass=class_name(design, net))
    forbidden: set[str] = set()
    for rule in design.rules.rules:
        if rule.kind == "no_tracks" and rule.severity != "ignore" and rule.selector_a.matches(subject):
            forbidden.update(rule.layers)
    return tuple(layer for layer in routing_layers if layer not in forbidden)


__all__ = ["DEFAULT_CLASS", "allowed_layers", "class_name", "routing_layers"]
