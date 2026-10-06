# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The container round-trip stages (capability verification-loop, "Document check pipeline"; change
c0044): verdicts per document become one stage per level."""

from __future__ import annotations

import pytest
from fakes import CONTAINER_EVIDENCE, passing

from fenolite.backends.base import ContainerRoundTrip
from fenolite.checks.containers import container_stage
from fenolite.core.evidence import Evidence, Level


def _failed(level: str, difference: str, **more: int) -> ContainerRoundTrip:
    return ContainerRoundTrip(
        level,  # type: ignore[arg-type]
        True,
        False,
        streams=3,
        different=(difference.split("#")[0],),
        difference=difference,
        evidence=CONTAINER_EVIDENCE,
        **more,
    )


def _unjudged(level: str, reason: str) -> ContainerRoundTrip:
    return ContainerRoundTrip(level, False, False, reason=reason)  # type: ignore[arg-type]


def test_failed_and_unjudged_verdicts() -> None:
    stage = container_stage(
        "roundtrip.rta0",
        "RT-A0",
        {
            "a.PcbDoc": _failed("RT-A0", "Nets6/Data"),
            "big.PcbDoc": _unjudged("RT-A0", "too-large"),
            "p.PrjPcb": _unjudged("RT-A0", "not-a-container"),
        },
    )
    assert (stage.name, stage.status, stage.reason) == ("roundtrip.rta0", "errors", "")
    assert [(i.code, i.severity, i.where) for i in stage.issues] == [
        ("check.roundtrip-unjudged", "info", "big.PcbDoc"),
        ("check.rta0-failed", "error", "a.PcbDoc:Nets6/Data"),
    ]
    assert "too-large" in stage.issues[0].message
    assert stage.summary == {
        "level": "RT-A0",
        "documents": 1,
        "streams": 3,
        "failed": 1,
        "unjudged": {"not-a-container": 1, "too-large": 1},
    }
    assert stage.evidence == Evidence()  # a failed copy lowers the stage to UNVERIFIED


def test_passing_stage_combines_the_verdicts_evidence() -> None:
    other = Evidence(Level.INFERRED, hypotheses=("H-FAKE-OTHER",))
    second = ContainerRoundTrip("RT-A0", True, True, streams=5, evidence=other)
    stage = container_stage("roundtrip.rta0", "RT-A0", {"a": passing("RT-A0"), "b": second})
    assert stage.status == "ok" and stage.issues == ()
    assert stage.summary == {"level": "RT-A0", "documents": 2, "streams": 7, "failed": 0, "unjudged": {}}
    assert stage.evidence == Evidence(Level.INFERRED, hypotheses=("H-FAKE-OTHER", "H-FAKE-RT"))


def test_rt_a1_summary_failure_and_normalised_streams() -> None:
    normalised = ContainerRoundTrip(
        "RT-A1", True, True, streams=4, records=20, bytes_equal=2, opaque_count=1, evidence=CONTAINER_EVIDENCE
    )
    stage = container_stage(
        "roundtrip.rta1",
        "RT-A1",
        {
            "a.SchDoc": _failed("RT-A1", "FileHeader#3", records=7, bytes_equal=2, opaque_count=2),
            "b.SchDoc": normalised,
            "c.SchDoc": passing("RT-A1"),
        },
    )
    assert [(i.code, i.severity, i.where) for i in stage.issues] == [
        ("check.rta1-failed", "error", "a.SchDoc:FileHeader#3"),
        ("check.rta1-normalised", "info", "b.SchDoc"),
    ]
    assert stage.issues[1].message.startswith("2 stream(s)")
    assert stage.summary == {
        "level": "RT-A1",
        "documents": 3,
        "streams": 9,
        "failed": 1,
        "unjudged": {},
        "records": 37,
        "bytes_equal": 6,
        "opaque_count": 3,
    }
    assert stage.status == "errors" and stage.evidence.level is Level.UNVERIFIED


def test_refused_readings_are_counted() -> None:
    stage = container_stage("roundtrip.rta1", "RT-A1", {"a.SchDoc": passing("RT-A1"), "b.PcbDoc": None})
    assert stage.status == "ok" and stage.issues == ()
    assert stage.summary["unjudged"] == {"read-refused": 1} and stage.summary["documents"] == 1


def test_no_judged_document_skips_the_stage() -> None:
    refused = container_stage("roundtrip.rta0", "RT-A0", {"a.PcbDoc": None, "b.PcbDoc": None})
    assert (refused.status, refused.reason, refused.issues) == ("skipped", "read-refused", ())
    assert refused.summary["unjudged"] == {"read-refused": 2} and refused.evidence == Evidence()
    text = container_stage("roundtrip.rta0", "RT-A0", {"p.PrjPcb": _unjudged("RT-A0", "not-a-container")})
    assert (text.status, text.reason, text.issues) == ("skipped", "not-judged", ())
    mixed = container_stage(
        "roundtrip.rta0", "RT-A0", {"a.PcbDoc": None, "big.PcbDoc": _unjudged("RT-A0", "writer-refused")}
    )
    assert (mixed.status, mixed.reason) == ("skipped", "not-judged")
    assert [(i.code, i.where) for i in mixed.issues] == [("check.roundtrip-unjudged", "big.PcbDoc")]
    assert container_stage("roundtrip.rta0", "RT-A0", {}).reason == "not-judged"


def test_verdict_of_another_level_is_refused() -> None:
    with pytest.raises(ValueError, match="RT-A1 verdict in the RT-A0 stage"):
        container_stage("roundtrip.rta0", "RT-A0", {"a": passing("RT-A1")})
