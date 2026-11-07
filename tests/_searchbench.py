# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Small authored physical boards for bounded router search; no external board inputs."""

from fenolite.core.coords import Point
from fenolite.model.board import Board, Layer, Track
from fenolite.model.circuit import Circuit, Net
from fenolite.model.design import Design, DesignHeader
from fenolite.routing.octilinear import World
from fenolite.routing.protocol import JobAttach, JobNet, JobSubject, RoutingJob

MM = 1_000_000
START = Point(2 * MM, 5 * MM)
END = Point(10 * MM, 5 * MM)


def point(x: int, y: int) -> Point:
    return Point(x * MM, y * MM)


def wall(ident: str, x: int, y0: int, y1: int, layer: str = "F.Cu", width: int = 200_000) -> Track:
    return Track(id=ident, start=point(x, y0), end=point(x, y1), width=width, layer=layer, net_id="net_wall")


def bench(
    *,
    layers: tuple[str, ...] = ("F.Cu", "B.Cu"),
    tracks: tuple[Track, ...] = (),
    start: Point = START,
    end: Point = END,
    ends: tuple[tuple[str, ...], tuple[str, ...]] = (("F.Cu",), ("F.Cu",)),
    holes: tuple[tuple[Point, ...], ...] = (),
    allowed: tuple[str, ...] | None = None,
) -> tuple[RoutingJob, JobSubject, World]:
    design = Design(
        header=DesignHeader(id="des_search", name="search", schema_version="0", fenolite_version="0"),
        circuit=Circuit(nets=(Net(id="net_sig", name="SIG"), Net(id="net_wall", name="WALL"))),
        board=Board(
            id="brd_search",
            layers=tuple(
                Layer(id=f"lyr_{i}", name=name, kind="copper", ordinal=i) for i, name in enumerate(layers)
            ),
            tracks=tracks,
        ),
    )
    subject = JobSubject(
        "connection:SIG:A~B",
        "connection",
        "SIG",
        JobAttach("pad", "SIG", start, ends[0], "A-1"),
        JobAttach("pad", "SIG", end, ends[1], "B-1"),
        100_000,
        allowed or layers,
        600_000,
        300_000,
    )
    net = JobNet("SIG", "net_sig", (), 100_000, 100_000, 600_000, 300_000)
    rings = ((point(0, 0), point(12, 0), point(12, 10), point(0, 10)), *holes)
    job = RoutingJob(design, (net,), layers, extra={"outline": rings, "board_pads": ()}, subjects=(subject,))
    return job, subject, World(job, (), rings)
