# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored c0368 contracts, including a real isolated fake-tool subprocess."""

import sys
from dataclasses import replace
from pathlib import Path

import pytest
from _fakerouter import create_fake_router
from _searchbench import bench

from fenolite.routing.budget import Budget
from fenolite.routing.external_candidates import SUPPORTED, Adapter, Outcome, Provenance, unsupported
from fenolite.routing.plugins.kicad.routingtools import KicadRoutingToolsRouter
from fenolite.routing.protocol import JobPair, RouterStatus, RoutingResult


def descriptor(name="kicadroutingtools", projection="board"):
    return Adapter(
        name, projection, lambda _: RouterStatus(True, version="authored"), lambda _: RoutingResult()
    )


def test_only_explicit_local_adapter_projection_is_supported():
    assert SUPPORTED == ("freerouting", "kicadroutingtools")
    assert descriptor().projection == "board"
    assert descriptor("freerouting", "copper").projection == "copper"
    for name, projection in (("cloud", "board"), ("freerouting", "board"), ("docker:image", "copper")):
        with pytest.raises(ValueError):
            descriptor(name, projection)


def test_import_and_contract_construction_start_no_process(monkeypatch):
    monkeypatch.setattr("subprocess.Popen", lambda *a, **k: pytest.fail("unexpected process"))
    assert descriptor().name == "kicadroutingtools"
    assert Outcome().candidates == ()
    assert Provenance("kicadroutingtools", "0.22.1", "inputs", "job").deterministic is False


@pytest.mark.parametrize("kind", ["group", "fanout", "join", "role-net"])
def test_nonordinary_subjects_are_explicitly_refused(kind):
    job, subject, _ = bench()
    assert unsupported(job, replace(subject, kind=kind)) == "external-unsupported"


def test_atomic_pairs_including_unselected_partner_are_refused():
    job, subject, _ = bench()
    assert unsupported(job, subject) == ""
    pair = JobPair("p", "SIG", "WALL", 100_000, 100_000)
    assert unsupported(replace(job, pairs=(pair,)), subject) == "external-unsupported"
    assert unsupported(job, replace(subject, group="critical")) == "external-unsupported"
    assert unsupported(job, replace(subject, a=replace(subject.a, net="WALL"))) == "external-unsupported"


def test_authored_fake_checkout_uses_existing_process_adapter(tmp_path: Path, monkeypatch):
    checkout = create_fake_router(tmp_path)
    router = KicadRoutingToolsRouter(checkout, sys.executable)
    adapter = Adapter(router.name, "board", lambda _: router.available(), router.route)
    assert adapter.prepare(Budget(5)).available
    # The fake is authored in this repository; it is not a vendored external router.
    ran = Budget(5).run([sys.executable, "-c", "print('authored fake process')"], cwd=checkout)
    assert ran.returncode == 0 and ran.stdout.strip() == "authored fake process"


def _track(*slots: tuple[str, str]):
    from fenolite.core.coords import Point
    from fenolite.model.base import ExtBag
    from fenolite.model.board import Track

    modeled = tuple(("slot:.:modeled", name) for name in ("width", "layer", "net_id", "native_ids"))
    return Track(
        id="trk-a",
        start=Point(106_000_000, 110_800_000),
        end=Point(124_000_000, 110_800_000),
        width=250_000,
        layer="F.Cu",
        net_id="net-a",
        ext={"kicad": ExtBag("20260206", (*slots, *modeled))},
    )


def test_a_respelled_modelled_number_is_not_opaque_output():
    """KiCadRoutingTools writes ``106.000000``: the reader keeps that child, whose value the model holds."""
    from fenolite.routing.external_candidates import _opaque

    respelled = (
        ("slot:.:opaque@20260206", "(start 106.000000 110.800000)"),
        ("slot:.:opaque@20260206", "(end 124.000000 110.800000)"),
    )
    assert not _opaque(_track(*respelled))
    # a different value, a fraction of a nanometre or any other child stays opaque: fail closed
    for fragment in (
        "(start 106.000001 110.800000)",
        "(start 106.0000001 110.800000)",
        "(start 106 110.8 0)",
        "(tstamp 0f0f)",
        "(locked yes)",
    ):
        assert _opaque(_track(("slot:.:opaque@20260206", fragment), respelled[1])), fragment
