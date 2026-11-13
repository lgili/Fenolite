# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Small benches of the route search on an existing board (change c0501), authored for Fenolite: a pad
ringed by eight pads of another net, a slot between two pads of different net classes, and two pads of one
net with a rule area across the line between them. Lengths in nanometres."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from fenolite.core.coords import Point
from fenolite.model.board import Board, Keepout, Layer
from fenolite.model.circuit import Circuit, Net, NetClass
from fenolite.model.design import Design, DesignHeader
from fenolite.model.rules import RuleSubject
from fenolite.routing.octilinear import World
from fenolite.routing.protocol import JobAttach, JobNet, JobSubject, RoutingJob

MM = 1_000_000
LAYERS = ("F.Cu", "B.Cu")


@dataclass(frozen=True)
class Copper:
    layer: str
    core: tuple[Point, ...]
    width: int
    filled: bool = False


@dataclass(frozen=True)
class BenchPad:
    """What ``World`` reads of a board-frame pad."""

    ref: str
    number: str
    net: str
    position: Point
    copper: tuple[Copper, ...]
    hole: tuple[Point, ...] = ()
    drill: int | None = None
    layers: tuple[str, ...] = field(default=("F.Cu",))


def round_pad(ref: str, net: str, at: Point, diameter: int = MM) -> BenchPad:
    return BenchPad(ref, "1", net, at, (Copper("F.Cu", (at,), diameter),))


def rect_pad(ref: str, net: str, x0: int, y0: int, x1: int, y1: int) -> BenchPad:
    ring = (Point(x0, y0), Point(x1, y0), Point(x1, y1), Point(x0, y1))
    at = Point((x0 + x1) // 2, (y0 + y1) // 2)
    return BenchPad(ref, "1", net, at, (Copper("F.Cu", ring, 0, True),))


def square(half: int, tall: int | None = None) -> tuple[Point, ...]:
    up = half if tall is None else tall
    return (Point(-half, -up), Point(half, -up), Point(half, up), Point(-half, up))


@dataclass(frozen=True)
class Bench:
    job: RoutingJob
    subject: JobSubject
    world: World
    pads: tuple[BenchPad, ...]


def bench(
    pads: tuple[BenchPad, ...],
    start: Point,
    end: Point,
    *,
    net: str = "A",
    width: int = 200_000,
    clearance: int = 200_000,
    half: int = 8 * MM,
    tall: int | None = None,
    keepouts: tuple[Keepout, ...] = (),
    classes: dict[str, str] | None = None,
    rule: Callable[[RuleSubject, RuleSubject], int] | None = None,
    extra: dict[str, object] | None = None,
) -> Bench:
    """A two-layer board ``2 * half`` square about the origin with ``pads`` and a connection of ``net`` from
    ``start`` to ``end`` on ``F.Cu``; ``classes`` gives a net its class, ``rule`` the clearance in force."""
    names = sorted({net, *(p.net for p in pads)})
    owned = sorted(set((classes or {}).values()))
    netclasses = tuple(NetClass(id=f"ncl_{c}", name=c) for c in owned)
    nets = tuple(
        Net(id=f"net_{n}", name=n, netclass_id=f"ncl_{classes[n]}" if classes and n in classes else None)
        for n in names
    )
    design = Design(
        header=DesignHeader(id="des_bench", name="bench", schema_version="0", fenolite_version="0"),
        circuit=Circuit(nets=nets, netclasses=netclasses),
        board=Board(
            id="brd_bench",
            layers=tuple(
                Layer(id=f"lyr_{i}", name=n, kind="copper", ordinal=i) for i, n in enumerate(LAYERS)
            ),
            keepouts=keepouts,
        ),
    )
    subject = JobSubject(
        f"connection:{net}:S~E",
        "connection",
        net,
        JobAttach("pad", net, start, ("F.Cu",), "S-1"),
        JobAttach("pad", net, end, ("F.Cu",), "E-1"),
        width,
        ("F.Cu",),
        600_000,
        300_000,
    )
    rings = (square(half, tall),)
    given: dict[str, object] = {"outline": rings, "board_pads": pads, **(extra or {})}
    if rule is not None:
        given["clearance"] = rule
    job = RoutingJob(
        design,
        (JobNet(net, f"net_{net}", (), width, clearance, 600_000, 300_000),),
        LAYERS,
        extra=given,
        subjects=(subject,),
    )
    return Bench(job, subject, World(job, pads, rings), pads)


def ring(free: int = 100_000, *, opened: int = 0, **options: object) -> Bench:
    """A 1 mm pad of net ``A`` at the origin ringed by eight 1 mm pads of net ``B`` on a square of side
    ``2 p``, ``B1`` lower left and on anticlockwise: with the 0.2 mm clearance each free gap between two
    neighbours is ``free``. ``opened`` moves the corner pad ``B5`` (upper right) up by that much, so the gap
    between ``B4`` (right) and ``B5`` widens by it. The connection runs from the origin to (5 mm, 0)."""
    p = MM + 2 * 200_000 + free
    places = ((-p, -p), (0, -p), (p, -p), (p, 0), (p, p + opened), (0, p), (-p, p), (-p, 0))
    pads = (
        round_pad("A1", "A", Point(0, 0)),
        *(round_pad(f"B{i}", "B", Point(x, y)) for i, (x, y) in enumerate(places, start=1)),
    )
    return bench(pads, Point(0, 0), Point(5 * MM, 0), **options)  # type: ignore[arg-type]


def slot() -> Bench:
    """A 3 mm slot between a pad of class ``HV`` (net ``H``, left) and a pad of class ``Default`` (net
    ``D``, right), each from the slot to the edge of a 5 × 9 mm board; net ``S`` runs from below the slot to
    above it. The
    clearance in force: 0.5 mm between ``HV`` and ``S`` (a rule over the 1 mm class value), 0.2 mm else."""
    pads = (
        rect_pad("H1", "H", -2_500_000, -MM, -1_500_000, MM),
        rect_pad("D1", "D", 1_500_000, -MM, 2_500_000, MM),
    )

    def rule(a: RuleSubject, b: RuleSubject) -> int:
        nets = {a.net, b.net}
        if nets == {"H", "S"}:
            return 500_000
        return MM if "H" in nets else 200_000

    classes = {"H": "HV", "D": "Default", "S": "Default"}
    return bench(
        pads,
        Point(0, -3 * MM),
        Point(0, 3 * MM),
        net="S",
        half=2_500_000,
        tall=4_500_000,
        classes=classes,
        rule=rule,
    )


def across(**flags: bool) -> Bench:
    """Two pads of net ``A`` 6 mm apart on ``F.Cu`` and a rule area on ``F.Cu`` across the line between
    them, forbidding what ``flags`` names (``no_tracks``, ``no_vias``, ``no_copper_pour``, ...)."""
    pads = (round_pad("P1", "A", Point(-3 * MM, 0)), round_pad("P2", "A", Point(3 * MM, 0)))
    area = Keepout(id="kpo_across", outline=square(MM), layers=("F.Cu",), name="across", **flags)
    return bench(pads, Point(-3 * MM, 0), Point(3 * MM, 0), keepouts=(area,))


RETURN_TRACE = '''
"""The return-trace bench of change c0501, authored for Fenolite: two 0603 parts C1 and C2 whose pads 2 are
on GND, a part R1 of two other nets between them, and a band forbidding poured copper only across the
board between C1 and R1. A GND track on the Top Layer gives the clones of ``fenolite path`` a template."""

from fenolite.dsl import Design, Net, Part, connect, mm

design = Design("bench")
design.board(mm(30), mm(20))
c1 = Part("C1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="100n")
r1 = Part("R1", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="1k")
c2 = Part("C2", "Mini:Mini_R", footprint="Mini:Mini_R_0603", value="100n")
design.add(c1, r1, c2)
design.rules.rule("gap", "clearance", min=mm(0.2))
gnd, a, b = Net("GND"), Net("A"), Net("B")
connect(gnd, c1[2], c2[2])
connect(a, c1[1], r1[1])
connect(b, r1[2], c2[1])
c1.place(mm(6), mm(10))
r1.place(mm(15), mm(10))
c2.place(mm(24), mm(10))
design.track("stub", (mm(2), mm(2)), (mm(5), mm(2)), width=mm(0.25), net=gnd)
band = ((mm(10), mm(1)), (mm(11), mm(1)), (mm(11), mm(19)), (mm(10), mm(19)))
design.rule_area("no_pour", band, forbid=("pours",))
'''


def return_trace(folder: Path) -> Path:
    """The PCB document of ``RETURN_TRACE`` built for Altium into ``folder / "bench"``, its libraries the
    authored ``Mini`` libraries of the test data (linked as ``folder / "libs"``)."""
    import contextlib
    import io
    import json

    from fenolite.cli import main as cli_main

    data = Path(__file__).resolve().parent / "data"
    (folder / "libs").symlink_to(data / "libs", target_is_directory=True)
    project = folder / "bench"
    project.mkdir()
    for table in ("fp-lib-table", "sym-lib-table"):
        (project / table).write_bytes((data / "altium_edit" / table).read_bytes())
    script = project / "bench.py"
    script.write_text(RETURN_TRACE.lstrip(), encoding="utf-8")
    out = folder / "built"
    flags = ("--seed", "501", "--timestamp", "2026-11-13T00:00:00Z", "--altium-pour", "outline")
    args = ["build", str(script), "--out", str(out), "--target", "altium", *flags, "--confirm", "--json"]
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = cli_main.main([*args, "--no-backup"])
    assert code == 0, (json.loads(stdout.getvalue() or "{}").get("issues"), stderr.getvalue())
    [document] = sorted(out.glob("*.PcbDoc"))
    return document
