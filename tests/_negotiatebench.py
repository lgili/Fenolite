# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Two crossing connections authored for bounded negotiation, no external layout inputs."""

from dataclasses import replace

from _searchbench import bench, point

from fenolite.model.circuit import Net
from fenolite.routing.octilinear import World


def negotiation_bench(*, tracks=()):
    job, a, _ = bench(tracks=tracks, allowed=("F.Cu",))
    a = replace(a, key="connection:A", net="SIG")
    b = replace(
        a,
        key="connection:B",
        net="SECOND",
        a=replace(a.a, net="SECOND", at=point(6, 2), name="B-1"),
        b=replace(a.b, net="SECOND", at=point(6, 8), name="B-2"),
    )
    design = replace(
        job.design,
        circuit=replace(
            job.design.circuit, nets=(*job.design.circuit.nets, Net(id="net_second", name="SECOND"))
        ),
    )
    job = replace(
        job,
        design=design,
        nets=(*job.nets, replace(job.nets[0], name="SECOND", net_id="net_second")),
        subjects=(a, b),
        extra={**job.extra, "copper_check": lambda design: [], "role_check": lambda design: []},
    )
    return job, World(job, (), job.extra["outline"])
