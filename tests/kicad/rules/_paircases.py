# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Which net names KiCad takes as one differential pair (capability kicad-oracle, "Differential pair names
are probed"; hypothesis H-K-DIFFPAIR-NAMES; change c0073).

One bench holds, per case, two parallel tracks 0.3 mm apart on the case's two nets. One rule per case
selects ``A.inDiffPair('<base>')`` with a 3 mm clearance, so a pair that KiCad recognises gives a clearance
violation between its two tracks, and the others give none: the default clearance is below 0.3 mm. The
canary is scoped to its own net. Every case has its own net names, authored for this bench."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from functools import cache
from types import MappingProxyType

import _kindcases as kc
import _rulebench as rb

CASES: Mapping[str, tuple[str, str, str]] = MappingProxyType(
    {
        "pn": ("USBA", "USBA_P", "USBA_N"),
        "pn-full": ("USBG_", "USBG_P", "USBG_N"),
        "plusminus": ("USBB", "USBB+", "USBB-"),
        "dpdn": ("USBD_D", "USBD_DP", "USBD_DN"),
        "bare": ("USBE", "USBEP", "USBEN"),
        "dpdm": ("USBC_D", "USBC_DP", "USBC_DM"),
        "lower": ("USBF_", "USBF_p", "USBF_n"),
        "mixed": ("USBH", "USBH_P", "USBH-"),
    }
)
"""Case → the base name of the rule's ``inDiffPair()`` and the two net names."""
PAIRED = ("pn", "pn-full", "plusminus", "dpdn", "bare")
"""The cases whose names are equal except for a last ``P`` then ``N``, or ``+`` then ``-``."""
GAP = 300_000


def label(case: str) -> str:
    return case.replace("-", "_")


@cache
def bench() -> rb.Bench:
    made = rb.builder()
    for case, (_, positive, negative) in CASES.items():
        made.pair(label(case), positive, negative, gap=GAP)
    return made.build()


def rules() -> str:
    text = "".join(
        f'(rule "dp_{label(case)}"\n\t(condition "A.inDiffPair(\'{base}\')")\n'
        "\t(constraint clearance (min 3mm))\n)\n"
        for case, (base, _, _) in CASES.items()
    )
    return kc.rules_text(text)


@cache
def pairs() -> kc.Run:
    return kc.run(bench(), rules())


def recognised(result: kc.Run, case: str) -> bool:
    """Whether the clearance violation between the two tracks of ``case`` is reported."""
    return result.between(label(case), frozenset({"clearance"}))


def pair_probe(case: str) -> str:
    result = pairs()
    if not result.canary:
        return "inconclusive"
    return rb.outcome(recognised(result, case))


def pair_probes() -> dict[str, tuple[Callable[[], str], tuple[int, ...]]]:
    """``probe id → (function, majors)`` for ``_probes.PROBES``."""
    return {f"dru-diffpair-{case}": (lambda case=case: pair_probe(case), (9, 10)) for case in CASES}


__all__ = ["CASES", "PAIRED", "bench", "pair_probe", "pair_probes", "pairs", "recognised", "rules"]
