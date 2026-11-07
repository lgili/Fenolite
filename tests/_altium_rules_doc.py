# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored Altium rule records in Fenolite's own sample project (change c0424).

``project(folder, records)`` copies ``tests/data/altium/board6`` into ``folder`` and replaces the
``Rules6`` storage of its PCB document with ``records``: each a kind number and the keys from ``RULEKIND``
on. The kind numbers are those of the public PCB documents (S-1838, ``KIND_NUMBERS``); the keys of each kind
are those of the public rule file S-0297 and the public documents. Every value is Fenolite's own.
"""

from __future__ import annotations

import shutil
import struct
from collections.abc import Sequence
from pathlib import Path

from fenolite.backends.altium.cfb import storage_from_paths, write_compound
from fenolite.backends.altium.pcbdoc import common_fields
from fenolite.backends.altium.pcbrecords import property_block
from fenolite.backends.altium.read.cfb import open_compound

ROOT = Path(__file__).resolve().parents[1]
BOARD6 = ROOT / "tests" / "data" / "altium" / "board6"
KIND_NUMBERS = {
    "Clearance": 0, "Width": 2, "MatchedLengths": 4, "PlaneConnect": 6, "RoutingTopology": 7,
    "RoutingPriority": 8, "RoutingLayers": 9, "RoutingCorners": 10, "RoutingVias": 11, "PlaneClearance": 12,
    "SolderMaskExpansion": 13, "PasteMaskExpansion": 14, "ShortCircuit": 15, "UnRoutedNet": 16,
    "PolygonConnect": 20, "ComponentClearance": 24, "HoleSize": 42, "FabricationTestpoint": 43,
    "FabricationTestPointUsage": 44, "LayerPairs": 48, "FanoutControl": 49, "Height": 50,
    "DiffPairsRouting": 51, "HoleToHoleClearance": 52, "MinimumSolderMaskSliver": 53,
    "SilkToSolderMaskClearance": 54, "SilkToSilkClearance": 55, "NetAntennae": 56, "AssemblyTestpoint": 57,
    "AssemblyTestPointUsage": 58, "SilkToBoardRegionClearance": 59, "UnpouredPolygon": 62,
    "BoardOutlineClearance": 63, "MinimumAnnularRing": 19,
}  # fmt: skip
"""Rule kind → the kind number of its records in the public PCB documents (S-1838)."""
UNMEASURED = 65535
"""The number given to an authored record of a kind that no public document holds (Supply Nets): it is no
format fact, and the tests only check that it travels unchanged."""

Pairs = Sequence[tuple[str, str]]


def rule(
    kind: str,
    *keys: tuple[str, str],
    name: str = "",
    scope: str = "All",
    scope2: str = "All",
    priority: int = 1,
    enabled: bool = True,
    net_scope: str = "AnyNet",
) -> tuple[int, Pairs]:
    """One authored record: its kind number and its keys from ``RULEKIND`` on."""
    header = (
        ("RULEKIND", kind), ("NETSCOPE", net_scope), ("LAYERKIND", "SameLayer"), ("SCOPE1EXPRESSION", scope),
        ("SCOPE2EXPRESSION", scope2), ("NAME", name or f"{kind}_{priority}"),
        ("ENABLED", "TRUE" if enabled else "FALSE"), ("PRIORITY", str(priority)), ("COMMENT", ""),
        ("UNIQUEID", f"C424{len(kind):02d}{priority:02d}"), ("DEFINEDBYLOGICALDOCUMENT", "FALSE"),
    )  # fmt: skip
    return KIND_NUMBERS.get(kind, UNMEASURED), (*header, *keys)


ONE_OF_EACH = (
    rule("Clearance", ("GAP", "8mil"), ("GENERICCLEARANCE", "8mil"), net_scope="DifferentNets"),
    rule("Clearance", ("GAP", "20mil"), ("GENERICCLEARANCE", "20mil"), name="Wide", priority=2,
         net_scope="DifferentNets", enabled=False),
    rule("Width", ("MINLIMIT", "6mil"), ("PREFEREDWIDTH", "8mil"), ("MAXLIMIT", "20mil")),
    rule("Width", ("MINLIMIT", "4mil"), ("PREFEREDWIDTH", "5mil"), ("MAXLIMIT", "6mil"), name="Thin",
         priority=2, enabled=False),
    rule("RoutingVias", ("VIASTYLE", "Through Hole"), ("MINWIDTH", "20mil"), ("WIDTH", "24mil"),
         ("MAXWIDTH", "30mil"), ("MINHOLEWIDTH", "10mil"), ("HOLEWIDTH", "12mil"), ("MAXHOLEWIDTH", "16mil")),
    rule("RoutingVias", ("VIASTYLE", "Through Hole"), ("MINWIDTH", "18mil"), ("WIDTH", "18mil"),
         ("MAXWIDTH", "18mil"), ("MINHOLEWIDTH", "8mil"), ("HOLEWIDTH", "8mil"), ("MAXHOLEWIDTH", "8mil"),
         name="Small", priority=2, enabled=False),
    rule("HoleSize", ("ABSOLUTEVALUES", "TRUE"), ("MINLIMIT", "8mil"), ("MAXLIMIT", "200mil")),
    rule("BoardOutlineClearance", ("GAP", "10mil"), ("GENERICCLEARANCE", "10mil"), net_scope="DifferentNets"),
    rule("HoleToHoleClearance", ("GAP", "10mil"), ("ALLOWSTACKEDMICROVIAS", "FALSE")),
    rule("HoleToHoleClearance", ("GAP", "6mil"), ("ALLOWSTACKEDMICROVIAS", "TRUE"), name="Stacked",
         priority=2, scope="IsVia"),
    rule("MinimumAnnularRing", ("MINIMUMRING", "5mil")),
    rule("SilkToSilkClearance", ("SILKTOSILKCLEARANCE", "4mil")),
    rule("ComponentClearance", ("GAP", "8mil"), ("COLLISIONCHECKMODE", "3"), ("VERTICALGAP", "8mil"),
         ("SHOWDISTANCES", "FALSE")),
    rule("DiffPairsRouting", ("MAXLIMIT", "9mil"), ("MINLIMIT", "5mil"), ("MOSTFREQGAP", "7mil"),
         ("MAXUNCOUPLEDLENGTH", "200mil"), ("TOPLAYER_MINWIDTH", "5mil"), ("TOPLAYER_MAXWIDTH", "9mil"),
         ("TOPLAYER_PREFWIDTH", "7mil")),
    rule("RoutingLayers", ("TOP LAYER_V5", "TRUE"), ("BOTTOM LAYER_V5", "FALSE"), scope="InNet('GND')"),
    rule("RoutingLayers", ("TOP LAYER_V5", "TRUE"), ("BOTTOM LAYER_V5", "TRUE"), name="Open", priority=2),
    rule("SolderMaskExpansion", ("EXPANSION", "2mil")),
    rule("PasteMaskExpansion", ("EXPANSION", "0mil")),
    rule("PlaneClearance", ("CLEARANCE", "12mil")),
    rule("PlaneConnect", ("PLANECONNECTSTYLE", "Relief"), ("RELIEFEXPANSION", "10mil")),
    rule("ShortCircuit", ("ALLOWED", "FALSE")),
    rule("NetAntennae", ("NETANTENNAETOLERANCE", "0mil")),
    rule("Height", ("MINHEIGHT", "0mil"), ("PREFHEIGHT", "500mil"), ("MAXHEIGHT", "1000mil")),
    rule("SilkToSolderMaskClearance", ("MINSILKSCREENTOMASKGAP", "3mil"),
         ("CLEARANCETOEXPOSEDCOPPER", "TRUE")),
    rule("SilkToBoardRegionClearance"),
    rule("MinimumSolderMaskSliver", ("MINSOLDERMASKWIDTH", "4mil")),
    rule("RoutingTopology", ("TOPOLOGY", "Shortest")),
    rule("RoutingPriority", ("ROUTINGPRIORITY", "0")),
    rule("RoutingCorners", ("CORNERSTYLE", "45-Degree"), ("MINSETBACK", "10mil"), ("MAXSETBACK", "100mil")),
    rule("FanoutControl"),
    rule("FabricationTestpoint"),
    rule("FabricationTestPointUsage"),
    rule("AssemblyTestpoint"),
    rule("AssemblyTestPointUsage"),
    rule("SupplyNets"),
    rule("UnRoutedNet"),
    rule("UnpouredPolygon"),
    rule("LayerPairs", ("ENFORCE", "TRUE")),
    rule("MatchedLengths"),
    rule("PolygonConnect", ("CONNECTSTYLE", "Relief"), ("RELIEFCONDUCTORWIDTH", "0.4mm"),
         ("RELIEFENTRIES", "4"), ("POLYGONRELIEFANGLE", "90 Angle"), ("AIRGAPWIDTH", "0.3mm")),
)  # fmt: skip
"""One record of each kind, and the disabled records: Routing Vias, Width and Clearance."""


def project(folder: Path, records: Sequence[tuple[int, Pairs]]) -> Path:
    """The sample project in ``folder`` with ``records`` as the rules of its PCB document; its ``.PrjPcb``."""
    folder.mkdir(parents=True, exist_ok=True)
    for path in BOARD6.iterdir():
        shutil.copy(path, folder / path.name)
    document = folder / "board6.PcbDoc"
    streams = open_compound(document.read_bytes()).as_dict()
    data = b"".join(
        struct.pack("<H", number) + property_block([*common_fields("TOP"), *keys], spaced_keys=True)
        for number, keys in records
    )
    streams["Rules6/Data"] = data
    streams["Rules6/Header"] = struct.pack("<I", len(records))
    document.write_bytes(write_compound(storage_from_paths(streams)))
    return folder / "board6.PrjPcb"
