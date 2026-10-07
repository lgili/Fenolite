# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Freerouting on plane layers, planes, routing layers and rules (capability kicad-oracle, "Plane routing
passes the oracle"; change c0107): ``H-G-DSN-LAYERS``, ``H-G-DSN-PLANE``, ``H-G-DSN-CLEARANCE`` and
``H-G-DSN-EDGE``.

Each test writes a design file with ``write_dsn`` from the plane bench of ``_planebench.py`` (or its edge
bench), runs the jar named by ``FENOLITE_FREEROUTING_JAR`` as a subprocess in a temporary folder that is also
its ``HOME``, reads the session back with Fenolite's own reader and judges the copper it holds; two outcomes
are judged by ``kicad-cli``. With ``FENOLITE_ROUTING_EVIDENCE=1`` each outcome is written to
``docs/evidence/routing/freerouting-<version>.json`` with the hash of the jar that ran in its detail; run that
mode without ``-n``, one file at a time. The jar is never downloaded by a test.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import os
import re
import shutil
import subprocess
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path

import _planebench as pb
import pytest
from _resources import FREEROUTING_ENV, kicad_cli
from _specctra import Bench

from fenolite.backends.kicad import pro
from fenolite.backends.kicad.cli import KicadCli
from fenolite.backends.kicad.lowering import millimetres
from fenolite.backends.kicad.pcb import write_board
from fenolite.backends.specctra.dsn import DsnDefaults, DsnResult, write_dsn
from fenolite.backends.specctra.ses import read_session, to_copper
from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.geometry import Thick, thick_closer_than, thick_touch
from fenolite.model.board import Keepout, Track, Via
from fenolite.model.design import Design
from fenolite.model.rules import Rule, Selector
from fenolite.routing.merge import apply
from fenolite.routing.plugins.specctra.freerouting import UNROUTED_NET
from fenolite.routing.protocol import RoutingResult

pytestmark = pytest.mark.needs_freerouting

PINNED_VERSION = "2.4.1"
JAVA_MIN = 25
PASSES = 20
TIMEOUT = 900
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "docs" / "evidence" / "routing" / f"freerouting-{PINNED_VERSION}.json"
WRITE = "FENOLITE_ROUTING_EVIDENCE"
DEFAULTS = DsnDefaults(width=200_000, clearance=200_000, via_diameter=600_000, via_drill=300_000)
ROUTED = (*pb.SIGNALS, *pb.HIGH)
PLANE_NETS = ("GND", "VCC")


# -- running the jar


def _java() -> str:
    java = os.environ.get("FENOLITE_JAVA") or shutil.which("java")
    if not java:
        pytest.fail("no Java runtime: set FENOLITE_JAVA or put java on PATH", pytrace=False)
    return java


def _java_version(java: str) -> str:
    done = subprocess.run([java, "-version"], capture_output=True, text=True, timeout=60, check=False)
    lines = (done.stderr or done.stdout).splitlines()
    return lines[0].strip() if lines else ""


def _jar_label() -> str:
    jar = Path(os.environ[FREEROUTING_ENV])
    return f"jar {hashlib.sha256(jar.read_bytes()).hexdigest()[:12]}, {_java_version(_java())}"


def _record(outcome: str, value: str, detail: str) -> None:
    """Add one outcome to the results file when ``FENOLITE_ROUTING_EVIDENCE=1``. The file's own ``jar_sha256``
    names the jar of the earlier outcomes and is left as it is: the detail of each outcome of this file
    names the jar that ran it."""
    if os.environ.get(WRITE) != "1":
        return
    data: dict[str, object] = json.loads(EVIDENCE.read_text(encoding="utf-8"))
    outcomes = data.get("outcomes")
    merged: dict[str, object] = dict(outcomes) if isinstance(outcomes, dict) else {}
    merged[outcome] = {"value": value, "detail": f"{detail}; {_jar_label()}"}
    data["outcomes"] = dict(sorted(merged.items()))
    EVIDENCE.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


@dataclasses.dataclass(frozen=True)
class Routed:
    """One Freerouting run: the design file, the copper the session adds on every net, and the nets whose
    connections Freerouting says it left open."""

    written: DsnResult
    tracks: tuple[Track, ...]
    vias: tuple[Via, ...]
    open_nets: Mapping[str, int]
    names: Mapping[str, str]

    def of(self, *nets: str) -> list[Track]:
        return [track for track in self.tracks if self.names.get(track.net_id or "") in nets]

    def layers_of(self, *nets: str) -> dict[str, int]:
        found: dict[str, int] = {}
        for track in self.of(*nets):
            found[track.layer] = found.get(track.layer, 0) + 1
        return dict(sorted(found.items()))


def route(design: Design, pads: object, outline: object, folder: Path, **more: object) -> Routed:
    """Write the design file of ``design`` and run Freerouting on it in ``folder``."""
    selected = more.pop("selected", ROUTED)
    written = write_dsn(
        design,
        pads=pads,
        outline=outline,
        selected=selected,
        defaults=DEFAULTS,
        **more,  # type: ignore[arg-type]
    )
    return route_text(written, design, folder)


def route_text(written: DsnResult, design: Design, folder: Path) -> Routed:
    """Run Freerouting on the design file ``written`` in ``folder``."""
    java = _java()
    match = re.search(r'"?(\d+)[.\d]*', _java_version(java).split("version")[-1])
    if match is None or int(match.group(1)) < JAVA_MIN:
        pytest.fail(
            f"Freerouting {PINNED_VERSION} needs Java {JAVA_MIN}: {_java_version(java)!r}", pytrace=False
        )
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "board.dsn").write_text(written.text, encoding="utf-8")
    command = [
        java, "-jar", os.environ[FREEROUTING_ENV], "-de", "board.dsn", "-do", "board.ses",
        "-mp", str(PASSES), "-mt", "1", "-da", "--gui.enabled=false",
    ]  # fmt: skip
    env = {**os.environ, "HOME": str(folder), "LANG": "C"}
    done = subprocess.run(
        command, cwd=folder, env=env, capture_output=True, text=True, timeout=TIMEOUT, check=False
    )
    output = done.stdout + done.stderr
    session_file = folder / "board.ses"
    if not session_file.is_file():
        tail = "\n".join(output.splitlines()[-20:])
        pytest.fail(f"Freerouting wrote no session (exit {done.returncode})\n{tail}", pytrace=False)
    session = read_session(session_file.read_text(encoding="utf-8"), file="board.ses")
    every = tuple(sorted(net.name for net in design.circuit.nets))
    tracks, vias, issues = to_copper(session, written.names, selected=every)
    assert not [issue for issue in issues if issue.severity == "error"], issues
    open_nets: dict[str, int] = {}
    for found in UNROUTED_NET.finditer(output):
        # the last line that names a net is its final count
        open_nets[written.names.nets.get(found["name"], found["name"])] = int(found["count"])
    names = {net.id: net.name for net in design.circuit.nets}
    return Routed(written, tracks, vias, {k: v for k, v in open_nets.items() if v}, names)


@pytest.fixture(scope="module")
def hermetic(tmp_path_factory: pytest.TempPathFactory) -> Iterator[Path]:
    folder = tmp_path_factory.mktemp("planes")
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv("KICAD_CONFIG_HOME", str(folder / "kicad-config"))
        yield folder


@pytest.fixture(scope="module")
def bare(hermetic: Path) -> pb.Loaded:
    """The plane bench as built: plane layers, zones, rules, no copper."""
    return pb.load(pb.build_project(hermetic / "bare"))


@pytest.fixture(scope="module")
def fanned_board(hermetic: Path) -> Path:
    """The plane bench after ``fenolite route`` made its plane fan-out (the plane nets alone selected)."""
    board = pb.build_project(hermetic / "fanned")
    code, env, err = pb.run_cli(
        "route",
        str(board),
        "--router",
        "direct",
        "--nets",
        "GND",
        "--nets",
        "VCC",
        "--confirm",
        "--no-backup",
    )
    assert code == 0, err
    assert env["result"]["plane_fanout"]["vias"] == len(pb.PLANE_PADS)  # type: ignore[index]
    return board


@pytest.fixture(scope="module")
def fanned(fanned_board: Path) -> pb.Loaded:
    return pb.load(fanned_board)


def run(found: pb.Loaded, folder: Path, **more: object) -> Routed:
    more.setdefault("plane_layers", found.plane_layers)
    return route(found.design, found.pads, found.outline, folder, **more)


@pytest.fixture(scope="module")
def planes(fanned: pb.Loaded, hermetic: Path) -> Routed:
    """The fanned-out bench routed with its plane layers, planes and rules: the run of three outcomes."""
    return run(fanned, hermetic / "run-planes")


# -- H-G-DSN-LAYERS


def test_layers_power(planes: Routed) -> None:
    """``dsn-power-layers``: no wire on a layer written ``(type power)``."""
    assert "(type power)" in planes.written.text
    on = planes.layers_of(*ROUTED, *PLANE_NETS)
    inner = {layer: count for layer, count in on.items() if layer in pb.PLANE_LAYERS}
    equal = bool(on) and not inner
    _record(
        "dsn-power-layers",
        "equal" if equal else "different",
        f"plane bench with fan-out, In1.Cu and In2.Cu written (type power): tracks per layer {on}; "
        f"open nets {dict(planes.open_nets)}",
    )
    assert equal, f"tracks per layer: {on}"


def test_layers_use_layer(fanned: pb.Loaded, hermetic: Path) -> None:
    """``dsn-use-layer``: the wires of a class whose circuit holds ``use_layer`` stay on the named layer."""
    found = run(fanned, hermetic / "run-use-layer", net_layers={name: ("F.Cu",) for name in pb.SIGNALS})
    assert "(use_layer F.Cu)" in " ".join(found.written.text.split())
    sig, high = found.layers_of(*pb.SIGNALS), found.layers_of(*pb.HIGH)
    equal = bool(sig) and set(sig) == {"F.Cu"}
    _record(
        "dsn-use-layer",
        "equal" if equal else "different",
        f"class SIG with (use_layer F.Cu): SIG tracks per layer {sig}, HV tracks per layer {high}; "
        f"open nets {dict(found.open_nets)}",
    )
    assert equal, f"SIG tracks per layer: {sig}"


# -- H-G-DSN-PLANE


def test_plane_alone(bare: pb.Loaded, hermetic: Path) -> None:
    """``dsn-plane-alone``, recorded: without fan-out Freerouting brings no SMD pin to a plane on a ``power``
    layer; the plane nets stay open (``open``), or it closes them (``closed``)."""
    found = run(bare, hermetic / "run-alone")
    plane_vias = [via for via in found.vias if found.names.get(via.net_id or "") in PLANE_NETS]
    plane_tracks = found.layers_of(*PLANE_NETS)
    left = {net: count for net, count in found.open_nets.items() if net in PLANE_NETS}
    value = "open" if left else "closed"
    _record(
        "dsn-plane-alone",
        value,
        f"plane bench without fan-out: Freerouting reports open connections {left} on the plane nets, adds "
        f"{len(plane_vias)} via(s) and tracks per layer {plane_tracks} to them",
    )
    assert value == "open", "Freerouting now joins SMD pins to a plane: record it and revisit Decision 3"
    assert not any(layer in pb.PLANE_LAYERS for layer in plane_tracks)


def test_plane_fanout(planes: Routed) -> None:
    """``dsn-plane-fanout``: with one protected via per SMD pad, Freerouting adds no copper to the plane nets
    and reports no open connection on them."""
    added = len(planes.of(*PLANE_NETS)) + len(
        [via for via in planes.vias if planes.names.get(via.net_id or "") in PLANE_NETS]
    )
    left = {net: count for net, count in planes.open_nets.items() if net in PLANE_NETS}
    wiring = planes.written.text.count("(type protect)")
    equal = added == 0 and not left
    _record(
        "dsn-plane-fanout",
        "equal" if equal else "different",
        f"plane bench with the fan-out of fenolite route ({wiring} protected items in the file): "
        f"{added} item(s) added to GND and VCC, open plane connections {left}; "
        f"open nets {dict(planes.open_nets)}",
    )
    assert equal, f"added {added}, open {left}"


# -- H-G-DSN-CLEARANCE


def _merged(found: pb.Loaded, routed: Routed, nets: Sequence[str]) -> Design:
    tracks = tuple(dataclasses.replace(t, id="") for t in routed.of(*nets))
    vias = tuple(
        dataclasses.replace(v, id="") for v in routed.vias if routed.names.get(v.net_id or "") in nets
    )
    return apply(found.design, RoutingResult(tracks=tracks, vias=vias))


def _hv_sig_findings(cli: KicadCli, board: Path, design: Design) -> int:
    """The clearance violations of KiCad's report that name an item of an ``HV`` net and one of a ``SIG``
    net, on ``design`` written over ``board`` (its project and rules files stay)."""
    board.write_text(write_board(design, target=10).text, encoding="utf-8")
    files = {p.name: p for p in (board.with_suffix(".kicad_pro"), board.with_suffix(".kicad_dru"))}
    report = cli.drc(board, files=files).report
    assert report is not None, "kicad-cli wrote no DRC report"
    count = 0
    for violation in report.violations:
        text = " ".join(item.description for item in violation.items)
        high = any(f"[{net}]" in text for net in pb.HIGH)
        low = any(f"[{net}]" in text for net in pb.SIGNALS)
        count += violation.type == "clearance" and high and low
    return count


@pytest.mark.needs_kicad
def test_clearance_class_class(hermetic: Path) -> None:
    """``dsn-class-class``: with the 1 mm rule between ``HV`` and ``SIG`` written as ``class_class``, KiCad's
    DRC finds no clearance violation between the two classes on the routed bench. The bench is the variant
    whose ``HV`` nets must pass the pads and wires of ``SIG``, and every routed net is kept to ``F.Cu``, so
    the two classes share a layer; the same run without the rule in the file is the control."""
    binary = kicad_cli()
    assert binary is not None
    cli = KicadCli(Path(binary), timeout=300)
    built = pb.build_project(hermetic / "near", hv_near=True)
    code, _env, err = pb.run_cli(
        "route",
        str(built),
        "--router",
        "direct",
        "--nets",
        "GND",
        "--nets",
        "VCC",
        "--confirm",
        "--no-backup",
    )
    assert code == 0, err
    near = pb.load(built)
    one_layer = {name: ("F.Cu",) for name in ROUTED}
    counts: dict[str, int] = {}
    routed_high: dict[str, int] = {}
    left: dict[str, dict[str, int]] = {}
    for label, used in (("with", near), ("without", pb.with_rules(near, replace=True))):
        found = run(used, hermetic / f"run-class-{label}", net_layers=one_layer)
        has_pair = "class_class" in found.written.text
        assert has_pair == (label == "with")
        board = hermetic / f"class-{label}" / built.name
        board.parent.mkdir()
        for beside in (built.with_suffix(".kicad_pro"), built.with_suffix(".kicad_dru")):
            shutil.copyfile(beside, board.parent / beside.name)
        counts[label] = _hv_sig_findings(cli, board, _merged(near, found, ROUTED))
        routed_high[label] = len(found.of(*pb.HIGH))
        left[label] = dict(found.open_nets)
    equal = counts["with"] == 0 and routed_high["with"] > 0
    _record(
        "dsn-class-class",
        "equal" if equal else "different",
        f"kicad-cli {cli.version()}: the bench with J3 in the upper right corner, every routed net kept to "
        f"F.Cu; with (class_class (classes HV SIG) (rule (clearance 1000))) {counts['with']} HV-SIG "
        f"clearance violation(s), {routed_high['with']} HV track(s), open nets {left['with']}; control "
        f"without the rule in the file: {counts['without']} violation(s), {routed_high['without']} HV "
        f"track(s), open nets {left['without']}",
    )
    assert equal, (counts, routed_high)


def test_clearance_layer_rule(fanned: pb.Loaded, hermetic: Path) -> None:
    """``dsn-layer-rule``: a ``layer_rule`` width holds on its layer and the class width on the others."""
    width = Rule(
        id=derived_id("rul", "gate", "sig-top"), name="sig-top", kind="track_width",
        selector_a=Selector("netclass", "SIG"), layers=("F.Cu",), opt=350_000,
    )  # fmt: skip
    found = run(pb.with_rules(fanned, width), hermetic / "run-layer-rule")
    flat = " ".join(found.written.text.split()).replace("( ", "(").replace(" )", ")")
    assert "(layer_rule F.Cu (rule (width 350)))" in flat
    widths: dict[str, dict[int, int]] = {}
    for track in found.of(*pb.SIGNALS):
        per = widths.setdefault(track.layer, {})
        per[track.width] = per.get(track.width, 0) + 1
    top = widths.get("F.Cu", {})
    others = {layer: per for layer, per in widths.items() if layer != "F.Cu"}
    # a segment of another width on F.Cu: where does it lie?
    odd = [track for track in found.of(*pb.SIGNALS) if track.layer == "F.Cu" and track.width != 350_000]
    at_pads = 0
    for track in odd:
        ends = (track.start, track.end)
        at_pads += any(
            abs(pad.position.x - end.x) <= 1_600_000 and abs(pad.position.y - end.y) <= 1_600_000
            for pad in fanned.pads
            if pad.net_id == track.net_id
            for end in ends
        )
    equal = bool(top) and set(top) == {350_000} and all(set(per) == {200_000} for per in others.values())
    _record(
        "dsn-layer-rule",
        "equal" if equal else "different",
        f"class SIG with (layer_rule F.Cu (rule (width 350))): SIG track widths in nm per layer {widths}; "
        f"{len(odd)} segment(s) on F.Cu are not 350 um wide, {at_pads} of them end within 1.6 mm of a pad of "
        "their net",
    )
    # what holds on this jar: most of the wire takes the layer width and no segment keeps the class width
    # of 200 um; the narrower segments lie at the pins, and no source explains them
    assert top.get(350_000, 0) > len(odd) and 200_000 not in top and at_pads >= len(odd) - 1, widths
    assert all(set(per) == {200_000} for per in others.values()), widths


def test_clearance_keepout(fanned: pb.Loaded, hermetic: Path) -> None:
    """``dsn-keepout``: no wire enters a keep-out for tracks, and each wire keeps the larger of the default
    and its class clearance from it."""
    board = fanned.design.board
    assert board is not None
    low, high = pb.at(9, 9, fanned.design), pb.at(11, 21, fanned.design)
    ring = (low, Point(high.x, low.y), high, Point(low.x, high.y))
    area = Keepout(
        id=derived_id("kpo", "gate", "band"), outline=ring, layers=("F.Cu", "B.Cu"), no_tracks=True
    )
    design = dataclasses.replace(fanned.design, board=dataclasses.replace(board, keepouts=(area,)))
    found = run(dataclasses.replace(fanned, design=design), hermetic / "run-keepout")
    assert "wire_keepout" in found.written.text
    shape = Thick(ring, 0, filled=True)
    classes = {c.id: c for c in design.circuit.netclasses}
    inside, close = 0, 0
    for track in found.tracks:
        net = next(n for n in design.circuit.nets if n.id == track.net_id)
        cls = classes.get(net.netclass_id or "")
        wanted = max(DEFAULTS.clearance, (cls.clearance if cls is not None else 0) or 0)
        wire = Thick((track.start, track.end), track.width)
        inside += thick_touch(wire, shape)
        close += thick_closer_than(wire, shape, wanted - 2_000)  # the file's resolution is 0.1 um
    equal = bool(found.tracks) and inside == 0 and close == 0
    _record(
        "dsn-keepout",
        "equal" if equal else "different",
        f"a 2 mm by 12 mm keep-out for tracks on F.Cu and B.Cu between J1 and U1: {len(found.tracks)} "
        f"track(s), {inside} inside it, {close} closer than the larger of the default and class clearance; "
        f"open nets {dict(found.open_nets)}",
    )
    assert equal, (inside, close)


# -- H-G-DSN-EDGE


def _edge_findings(cli: KicadCli, folder: Path, design: Design, minimum: int) -> tuple[int, int]:
    """``copper_edge_clearance`` violations of KiCad's report on ``design`` under a project whose
    ``min_copper_edge_clearance`` is ``minimum``: those that name a track, and all of them."""
    folder.mkdir(parents=True, exist_ok=True)
    board = folder / "edge.kicad_pcb"
    board.write_text(write_board(design, target=10).text, encoding="utf-8")
    data = pro.template(10)
    data["board"]["design_settings"]["rules"]["min_copper_edge_clearance"] = millimetres(minimum)  # type: ignore[index]
    project = board.with_suffix(".kicad_pro")
    project.write_text(pro.write_project_text(data), encoding="utf-8")
    report = cli.drc(board, files={project.name: project}).report
    assert report is not None, "kicad-cli wrote no DRC report"
    found = [v for v in report.violations if v.type == "copper_edge_clearance"]
    on_tracks = [v for v in found if any("Track" in item.description for item in v.items)]
    return len(on_tracks), len(found)


def _with_bands(written: DsnResult, rings: Sequence[Sequence[Point]], half_width: int) -> DsnResult:
    """``written`` with one ``(keepout (path signal <2 x half_width> <p> <q>))`` per edge of every ring,
    before the via list: the edge bands of Decision 11, which the writer does not write (its fallback)."""

    def um(nm: int) -> str:
        return f"{nm / 1000:g}"

    bands = "".join(
        f"    (keepout\n      (path signal {um(2 * half_width)} {um(a.x)} {um(-a.y)} {um(b.x)} {um(-b.y)})\n"
        "    )\n"
        for ring in rings
        for a, b in zip(ring, (*ring[1:], ring[0]), strict=True)
    )
    head, mark, tail = written.text.partition("    (via ")
    assert mark, "the structure holds no via list"
    return dataclasses.replace(written, text=head + bands + mark + tail)


@pytest.mark.needs_kicad
def test_edge_band(tmp_path: Path) -> None:
    """``dsn-edge-band``, the measurement behind Decision 11's fallback: with keep-out bands of half width
    ``E - d`` along every edge, KiCad finds no ``copper_edge_clearance`` on the routed copper where the
    route passes a 4 mm passage, but in the 2 mm passage of the edge bench the route that the file without
    bands makes is lost. The writer therefore writes no band and reports the edge clearance as not sent."""
    binary = kicad_cli()
    assert binary is not None
    cli = KicadCli(Path(binary), timeout=300)
    minimum = pb.EDGE_RULE
    half = minimum - DEFAULTS.clearance
    results: dict[tuple[int, str], tuple[int, int, int]] = {}
    for passage in (2, 4):
        edge = pb.edge_bench(minimum, passage)
        assert edge.write().text.count("(path signal") == 1, "the writer adds no band of its own"
        for label in ("bands", "plain"):
            folder = tmp_path / f"{label}-{passage}"
            # route() writes the file itself; the bands are added to that text before the jar reads it
            written = write_dsn(
                edge.design, pads=edge.pads, outline=edge.outline, selected=edge.selected, defaults=DEFAULTS
            )
            if label == "bands":
                written = _with_bands(written, edge.outline, half)
            found = route_text(written, edge.design, folder)
            merged = apply(
                edge.design,
                RoutingResult(
                    tracks=tuple(dataclasses.replace(t, id="") for t in found.tracks),
                    vias=tuple(dataclasses.replace(v, id="") for v in found.vias),
                ),
            )
            on_tracks, _every = _edge_findings(cli, tmp_path / f"drc-{label}-{passage}", merged, minimum)
            results[(passage, label)] = (len(found.tracks), on_tracks, len(found.open_nets))
    narrow, wide = results[(2, "bands")], results[(4, "bands")]
    lost = results[(2, "plain")][0] > 0 and (narrow[0] == 0 or narrow[2] > 0)
    holds = narrow[0] > 0 and narrow[1] == 0 and not lost and wide[0] > 0 and wide[1] == 0
    _record(
        "dsn-edge-band",
        "equal" if holds else "different",
        f"kicad-cli {cli.version()}, edge bench (a 1 mm slot between the two pads, edge clearance "
        f"{minimum // 1000} um, bands of {2 * half // 1000} um added to the file by the test), as (tracks, "
        f"copper_edge_clearance on tracks, open nets): 2 mm passage with bands {narrow}, without "
        f"{results[(2, 'plain')]}; 4 mm passage with bands {wide}, without {results[(4, 'plain')]}",
    )
    # the control of both passages: without bands the route hugs the end of the slot and KiCad reports it
    assert results[(2, "plain")][1] > 0 and results[(4, "plain")][1] > 0, results
    # where there is room the bands do what they are for
    assert wide[0] > 0 and wide[1] == 0, results
    if holds:
        pytest.fail(
            "the 2 mm passage now keeps its route with bands: H-G-DSN-EDGE holds on this jar; revisit "
            "Decision 11's fallback",
            pytrace=False,
        )


def test_skip_reason_names_the_variable() -> None:
    """The marker's skip reason names ``FENOLITE_FREEROUTING_JAR`` (scenario "Skipped without the tools");
    with the jar present this test only checks the name the suite reads."""
    assert FREEROUTING_ENV == "FENOLITE_FREEROUTING_JAR"
    assert isinstance(Bench, type)
