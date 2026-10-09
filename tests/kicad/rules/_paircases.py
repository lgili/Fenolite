# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Which net names KiCad takes as one differential pair (capability kicad-oracle, "Differential pair names
are probed"; hypothesis H-K-DIFFPAIR-NAMES; change c0073), and the names with a tail of digits and
underscores after the polarity character (hypothesis H-K-DIFFPAIR-NAMES-2; change c0104).

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
        "tail-digit": ("TA_", "TA_P1", "TA_N1"),
        "tail-underscore": ("TB_", "TB_P_2", "TB_N_2"),
        "tail-bare": ("TD", "TDP1", "TDN1"),
        "tail-differs": ("TC_", "TC_P1", "TC_N2"),
        "tail-letter": ("TG_", "TG_PA", "TG_NA"),
        "tail-base": ("TE_", "TE_P1", "TE_N1"),
        "tail-base-short": ("TF_P", "TF_P1", "TF_N1"),
    }
)
"""Case → the base name of the rule's ``inDiffPair()`` and the two net names. The ``tail-`` cases are those
of ``H-K-DIFFPAIR-NAMES-2``: a run of digits and underscores after the polarity character."""
OLD_CASES = ("pn", "pn-full", "plusminus", "dpdn", "bare", "dpdm", "lower", "mixed")
"""The eight cases of ``H-K-DIFFPAIR-NAMES``, whose outcomes the new rule keeps."""
PAIRED = (
    "pn",
    "pn-full",
    "plusminus",
    "dpdn",
    "bare",
    "tail-digit",
    "tail-underscore",
    "tail-bare",
    "tail-base",
)
"""The cases whose rule finds the pair: the names are equal except for ``P`` then ``N``, or ``+`` then
``-``, followed in both by the same run of digits and underscores, and the base is the text before it."""
NAMES_PAIR = (*PAIRED, "tail-base-short")
"""The cases whose two names form a pair. In ``tail-base-short`` they do, and the rule finds nothing,
because its base is the name without its last character and not the text before the polarity."""
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


__all__ = [
    "CASES",
    "NAMES_PAIR",
    "OLD_CASES",
    "PAIRED",
    "bench",
    "pair_probe",
    "pair_probes",
    "pairs",
    "recognised",
    "rules",
]
