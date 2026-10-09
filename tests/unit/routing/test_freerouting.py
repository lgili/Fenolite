# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Freerouting plugin with a fake ``java`` (capability routing, "Freerouting plugin"; change c0023).
Hermetic: no Java, no jar of Freerouting and no network."""

from __future__ import annotations

import dataclasses
import json
import os
from pathlib import Path

import pytest
from _fakefreerouting import create_fake_docker, create_fake_jar, create_fake_java
from _placed import Part, design_of, mm, pt
from _resources import posix_tools
from _specctra import Bench, bench, netless_bench, two_pads

from fenolite.backends.specctra.lexer import SNode, parse
from fenolite.core.evidence import Level
from fenolite.model.circuit import NetClass
from fenolite.routing.codes import ISSUE_CODES
from fenolite.routing.merge import apply
from fenolite.routing.plugins.specctra import freerouting
from fenolite.routing.plugins.specctra.freerouting import (
    JAVA_MIN,
    PINNED_VERSION,
    FreeroutingRouter,
    jar_version,
    java_major,
)
from fenolite.routing.protocol import FinishedRun, JobNet, JobPad, Router, RoutingJob, router_features
from fenolite.routing.registry import routers

pytestmark = posix_tools
SESSION = Path(__file__).resolve().parents[2] / "data" / "specctra" / "two_pads.ses"
PROJECT = Path(__file__).resolve().parents[3]


def _job(b: Bench | None = None, **options: str) -> RoutingJob:
    b = b or two_pads()
    net = b.design.nets_by_name["A"]
    pads = tuple(
        JobPad(pad.ref, pad.number, "A", pad.position, pad.layers, pad.drill)
        for pad in b.pads
        if pad.net == "A"
    )
    job_net = JobNet("A", net.id, pads, mm(0.25), mm(0.2), mm(0.6), mm(0.3))
    extra = {"board_pads": b.pads, "outline": b.outline}
    return RoutingJob(b.design, (job_net,), ("F.Cu", "B.Cu"), options, extra)


@pytest.fixture
def record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "record.json"
    monkeypatch.setenv("FAKE_JAVA_RECORD", str(path))
    monkeypatch.setenv("FAKE_JAVA_SESSION", str(SESSION))
    monkeypatch.delenv("FAKE_JAVA_MODE", raising=False)
    monkeypatch.delenv("FENOLITE_FREEROUTING_JAR", raising=False)
    monkeypatch.delenv("FENOLITE_JAVA", raising=False)
    return path


def _router(tmp_path: Path, *, version: str = "25.0.1", budget: float | None = 60) -> FreeroutingRouter:
    return FreeroutingRouter(create_fake_jar(tmp_path), create_fake_java(tmp_path, version=version), budget)


def _saved(record: Path) -> dict[str, object]:
    return json.loads(record.read_text(encoding="utf-8"))


def test_route_with_a_fake_java(tmp_path: Path, record: Path) -> None:
    """Scenario "Fake java"."""
    router = _router(tmp_path)
    status = router.available()
    assert status.available and status.version == PINNED_VERSION and status.path.endswith("router.jar")
    job = _job()
    result = router.route(job)
    assert [issue.code for issue in result.issues] == [], result.issues
    assert [(t.start, t.end, t.layer) for t in result.tracks] == [
        (pt(10.8, 10), pt(15, 12), "F.Cu"),
        (pt(15, 12), pt(19.2, 10), "F.Cu"),
    ]
    assert [(v.position, v.diameter, v.drill) for v in result.vias] == [(pt(15, 12), mm(0.6), mm(0.3))]
    assert result.routed == ("A",) and result.unrouted == ()
    assert result.tool == "freerouting" and result.tool_version == PINNED_VERSION
    assert result.evidence.level is Level.UNVERIFIED and "Freerouting" in (result.evidence.oracle or "")
    saved = _saved(record)
    argv = saved["argv"]
    assert isinstance(argv, list)
    assert argv[:2] == ["-jar", str(tmp_path / "router.jar")]
    assert argv[2:] == [
        "-de",
        "board.dsn",
        "-do",
        "board.ses",
        "-mp",
        "20",
        "-mt",
        "1",
        "-da",
        "--gui.enabled=false",
        "--router.automatic_neckdown=false",
        "--router.optimizer.enabled=false",
    ]
    assert not any("fanout" in word for word in argv)
    assert [(run.nets, run.tier, run.outcome) for run in result.runs] == [(("A",), 0, "done")]
    assert result.not_attempted == ()
    merged = apply(job.design, result)
    assert merged.board is not None and len(merged.board.tracks) == 2 and len(merged.board.vias) == 1


def test_one_unit_and_one_finished_run(tmp_path: Path, record: Path) -> None:
    """The plugin's one process is one unit of progress and, with copper, one finished run (capability
    routing, "Router runs reported for progress and resumption"; change c0120)."""
    events: list[tuple[str, str, str]] = []

    class Recorder:
        def step(self, name: str, *, index: int | None = None, total: int | None = None) -> None:
            events.append(("step", name, f"{index}/{total}"))

        def done(self, name: str, *, detail: str = "") -> None:
            events.append(("done", name, detail))

    runs: list[FinishedRun] = []
    job = dataclasses.replace(_job(), on_run=runs.append, progress=Recorder())
    result = _router(tmp_path).route(job)
    assert events == [("step", "freerouting", "1/1"), ("done", "freerouting", "routed")]
    (run,) = runs
    assert run.nets == ("A",) and run.tracks == result.tracks and run.vias == result.vias
    assert run.arcs == () and run.tier == 0 and len(result.tracks) == 2


def test_failed_process_is_not_a_finished_run(
    tmp_path: Path, record: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_JAVA_MODE", "fail")
    events: list[tuple[str, str]] = []

    class Recorder:
        def step(self, name: str, *, index: int | None = None, total: int | None = None) -> None:
            events.append(("step", ""))

        def done(self, name: str, *, detail: str = "") -> None:
            events.append(("done", detail))

    runs: list[FinishedRun] = []
    result = _router(tmp_path).route(dataclasses.replace(_job(), on_run=runs.append, progress=Recorder()))
    assert runs == [] and result.tracks == () and events == [("step", ""), ("done", "failed")]


def test_run_folder_is_temporary_and_is_home(tmp_path: Path, record: Path) -> None:
    _router(tmp_path).route(_job())
    saved = _saved(record)
    cwd = Path(str(saved["cwd"]))
    assert "fenolite-freerouting-" in cwd.name
    assert Path(str(saved["home"])).resolve() == cwd.resolve()
    assert not cwd.is_relative_to(PROJECT) and not cwd.exists()


def test_java_too_old(tmp_path: Path, record: Path) -> None:
    """Scenario "Java too old"."""
    router = _router(tmp_path, version="17.0.2")
    status = router.available()
    assert status.available is False and f"Java {JAVA_MIN}" in status.reason and "17.0.2" in status.reason
    result = router.route(_job())
    assert result.tracks == () and result.unrouted == ("A",)
    assert [issue.code for issue in result.issues] == ["route.tool-missing"]
    assert not record.exists()


def test_analytics_cannot_be_re_enabled(tmp_path: Path, record: Path) -> None:
    """Scenario "Analytics cannot be re-enabled"."""
    result = _router(tmp_path).route(_job(da="false"))
    argv = _saved(record)["argv"]
    assert isinstance(argv, list) and "-da" in argv
    (warning,) = result.issues
    assert warning.code == "route.option-ignored" and warning.severity == "warning"
    assert "da=false" in warning.message and warning.where == "da"
    assert len(result.tracks) == 2
    assert ISSUE_CODES["route.option-ignored"] == "warning"


@pytest.mark.parametrize(("value", "passes", "ignored"), [("5", "5", 0), ("0", "20", 1), ("many", "20", 1)])
def test_max_passes(tmp_path: Path, record: Path, value: str, passes: str, ignored: int) -> None:
    result = _router(tmp_path).route(_job(**{"max-passes": value}))
    argv = _saved(record)["argv"]
    assert isinstance(argv, list) and argv[argv.index("-mp") + 1] == passes
    assert [issue.code for issue in result.issues] == ["route.option-ignored"] * ignored


def test_open_connections_come_from_the_router_output(
    tmp_path: Path, record: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A session holds the routed wires only: a net that the router reports with unrouted connections is
    listed as unrouted although it has copper (``H-G-DSN-INCOMPLETE``)."""
    lines = (
        "Net 'A' (1 unrouted connections):",
        "INFO Optimization stage completed: final score: 883.31 (1 unrouted and 0 violations).",
    )
    monkeypatch.setenv("FAKE_JAVA_OUTPUT", "\n".join(lines))
    result = _router(tmp_path).route(_job())
    assert result.routed == () and result.unrouted == ("A",)
    assert len(result.tracks) == 2, "the partial copper is still returned"
    assert [issue.code for issue in result.issues] == []

    monkeypatch.setenv("FAKE_JAVA_OUTPUT", lines[1])
    result = _router(tmp_path).route(_job())
    assert result.routed == ("A",)
    assert [(issue.code, issue.severity) for issue in result.issues] == [("route.unrouted", "warning")]
    assert "1 unrouted connection" in result.issues[0].message

    monkeypatch.setenv("FAKE_JAVA_OUTPUT", "final score: 1000.00 (0 unrouted and 0 violations)")
    result = _router(tmp_path).route(_job())
    assert result.routed == ("A",) and result.unrouted == () and not result.issues


def test_no_session(tmp_path: Path, record: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "No session"."""
    monkeypatch.setenv("FAKE_JAVA_MODE", "none")
    result = _router(tmp_path).route(_job())
    assert result.tracks == () and result.vias == () and result.routed == () and result.unrouted == ("A",)
    (issue,) = result.issues
    assert issue.code == "route.tool-failed" and issue.severity == "error" and "no session" in issue.message


@pytest.mark.parametrize(("mode", "text"), [("fail", "exit 3"), ("garbage", "cannot be read")])
def test_failures_come_back_as_issues(
    tmp_path: Path, record: Path, monkeypatch: pytest.MonkeyPatch, mode: str, text: str
) -> None:
    monkeypatch.setenv("FAKE_JAVA_MODE", mode)
    result = _router(tmp_path).route(_job())
    assert result.tracks == () and result.unrouted == ("A",)
    assert [issue.code for issue in result.issues] == ["route.tool-failed"]
    assert text in result.issues[0].message
    assert str(_saved(record)["cwd"]) not in " ".join((*result.log, result.issues[0].message))


def test_budget_cut(tmp_path: Path, record: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Freerouting cut": reaching the budget is a warning and no tool failure (change c0109;
    it was ``route.tool-failed`` when the limit was the plugin's own)."""
    monkeypatch.setenv("FAKE_JAVA_MODE", "sleep")
    job = dataclasses.replace(_job(), budget=1)
    result = _router(tmp_path, budget=None).route(job)
    assert result.tracks == () and result.vias == () and result.unrouted == ("A",)
    assert [(run.nets, run.outcome) for run in result.runs] == [(("A",), "cut")]
    (issue,) = result.issues
    assert (issue.code, issue.severity) == ("route.budget-exhausted", "warning")
    assert "1 s" in issue.message and "(1 net(s))" in issue.message
    assert result.not_attempted == ()


def test_budget_of_the_constructor_serves_a_job_without_one(
    tmp_path: Path, record: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_JAVA_MODE", "sleep")
    result = _router(tmp_path, budget=0.5).route(_job())
    assert [issue.code for issue in result.issues] == ["route.budget-exhausted"]
    assert "0.5 s" in result.issues[0].message and result.tracks == ()
    assert freerouting.DEFAULT_BUDGET == 900 and FreeroutingRouter.default_budget == 900


def test_job_without_pads_or_outline(tmp_path: Path, record: Path) -> None:
    job = _job()
    for extra in ({}, {"board_pads": job.extra["board_pads"], "outline": ()}):
        bare = RoutingJob(job.design, job.nets, job.layers, {}, extra)
        result = _router(tmp_path).route(bare)
        assert [issue.code for issue in result.issues] == ["route.tool-failed"]
        assert "RoutingJob.extra" in result.issues[0].message
    assert not record.exists()


def test_session_that_moves_a_component_gives_no_copper(
    tmp_path: Path, record: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    moved = tmp_path / "moved.ses"
    moved.write_text(SESSION.read_text(encoding="utf-8").replace("100000 -100000", "100000 -110000"))
    monkeypatch.setenv("FAKE_JAVA_SESSION", str(moved))
    result = _router(tmp_path).route(_job())
    assert result.tracks == () and result.unrouted == ("A",)
    assert [issue.code for issue in result.issues] == ["specctra.session-moved"]


def test_another_version_is_allowed_with_a_warning(tmp_path: Path, record: Path) -> None:
    jar = create_fake_jar(tmp_path, "freerouting-2.3.0.jar", revision="0" * 40)
    router = FreeroutingRouter(jar, create_fake_java(tmp_path))
    assert router.available().version == "2.3.0"
    result = router.route(_job())
    assert len(result.tracks) == 2
    (warning,) = result.issues
    assert (
        warning.code == "route.tool-unpinned"
        and "2.3.0" in warning.message
        and PINNED_VERSION in warning.message
    )


def test_jar_version(tmp_path: Path) -> None:
    assert jar_version(create_fake_jar(tmp_path, "a.jar")) == PINNED_VERSION
    assert jar_version(create_fake_jar(tmp_path, "freerouting-2.4.0.jar", revision=None)) == "2.4.0"
    assert jar_version(create_fake_jar(tmp_path, "b.jar", revision=None)) == "unknown"
    plain = tmp_path / "freerouting-9.9.jar"
    plain.write_bytes(b"not a zip")
    assert jar_version(plain) == "9.9"


@pytest.mark.parametrize(
    ("line", "major"),
    [
        ('openjdk version "26.0.2" 2026-07-21', 26),
        ('openjdk version "25" 2025-09-16', 25),
        ('java version "1.8.0_402"', 8),
        ('openjdk version "17.0.2" 2022-01-18', 17),
        ("", None),
        ("no digits here", None),
    ],
)
def test_java_major(line: str, major: int | None) -> None:
    assert java_major(line) == major


def test_location_from_the_environment(tmp_path: Path, record: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = FreeroutingRouter().available()
    assert missing.available is False and "FENOLITE_FREEROUTING_JAR" in missing.reason
    assert "fenolite fetch freerouting --confirm" in missing.reason
    assert FreeroutingRouter().jar_source is None and FreeroutingRouter().jar_missing is True
    monkeypatch.setenv("FENOLITE_FREEROUTING_JAR", str(tmp_path / "absent.jar"))
    absent = FreeroutingRouter().available()
    assert absent.available is False and "missing" in absent.reason
    monkeypatch.setenv("FENOLITE_FREEROUTING_JAR", str(create_fake_jar(tmp_path)))
    monkeypatch.setenv("FENOLITE_JAVA", str(create_fake_java(tmp_path)))
    assert FreeroutingRouter().available().available is True
    assert not record.exists()  # available() starts no router
    monkeypatch.setenv("FENOLITE_JAVA", str(tmp_path / "no-java"))
    no_java = FreeroutingRouter().available()
    assert no_java.available is False and f"Java {JAVA_MIN}" in no_java.reason


def test_fetched_jar_is_found(tmp_path: Path, record: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Fetched jar is found" (c0078): the tools folder is the third place, read on use."""
    router = FreeroutingRouter(java=create_fake_java(tmp_path))  # built before the folder holds anything
    tools = tmp_path / "tools"
    monkeypatch.setenv("FENOLITE_TOOLS_DIR", str(tools))
    assert router.available().available is False and router.jar_source is None and router.jar is None
    (tools / "freerouting").mkdir(parents=True)
    fetched = create_fake_jar(tools / "freerouting", f"freerouting-{PINNED_VERSION}.jar")
    status = router.available()
    assert status.available is True and status.path == str(fetched) and status.version == PINNED_VERSION
    assert router.jar_source == "fetched" and router.jar == fetched and router.jar_missing is False
    other = create_fake_jar(tmp_path, "other.jar")
    monkeypatch.setenv("FENOLITE_FREEROUTING_JAR", str(other))
    assert router.jar_source == "env" and router.jar == other
    named = FreeroutingRouter(create_fake_jar(tmp_path, "named.jar"), create_fake_java(tmp_path))
    assert named.jar_source == "argument" and named.jar == tmp_path / "named.jar"
    assert not record.exists()  # nothing of this started the router


def test_fetched_jar_of_another_version_is_not_looked_for(
    tmp_path: Path, record: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tools = tmp_path / "tools"
    monkeypatch.setenv("FENOLITE_TOOLS_DIR", str(tools))
    (tools / "freerouting").mkdir(parents=True)
    create_fake_jar(tools / "freerouting", "freerouting-2.5.0.jar")
    router = FreeroutingRouter(java=create_fake_java(tmp_path))
    assert router.jar_source is None and router.available().available is False
    monkeypatch.setenv("FENOLITE_TOOLS_DIR", "relative")  # names no folder: no jar, and no exception
    assert router.jar_source is None and router.jar is None


def test_fetched_is_not_the_source_of_an_image(tmp_path: Path, record: Path) -> None:
    assert FreeroutingRouter("docker:example/router:2.4.1").jar_source is None
    assert FreeroutingRouter("docker:example/router:2.4.1").jar_missing is False


def test_container_command_line(tmp_path: Path, record: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """``docker:<image>`` runs the image with the run folder mounted and the network disabled."""
    image = "ghcr.io/freerouting/freerouting:2.4.1"
    router = FreeroutingRouter(f"docker:{image}")
    monkeypatch.setenv("PATH", str(tmp_path / "nothing"))
    assert router.available().available is False
    monkeypatch.setenv("PATH", str(create_fake_docker(tmp_path)) + os.pathsep + os.defpath)
    status = router.available()
    assert status.available and status.version == "2.4.1" and status.path == f"docker:{image}"
    assert not record.exists()
    result = router.route(_job())
    assert len(result.tracks) == 2 and [issue.code for issue in result.issues] == []
    argv = _saved(record)["argv"]
    assert isinstance(argv, list)
    assert argv[:4] == ["run", "--rm", "--network", "none"]
    mount = argv[argv.index("-v") + 1]
    assert mount.endswith(":/work") and "fenolite-freerouting-" in mount
    assert argv[argv.index(image) + 1 :] == [
        "java", "-jar", "/app/freerouting-executable.jar",
        "-de", "board.dsn", "-do", "board.ses", "-mp", "20", "-mt", "1", "-da", "--gui.enabled=false",
        "--router.automatic_neckdown=false", "--router.optimizer.enabled=false",
    ]  # fmt: skip


def test_defaults_come_from_the_default_class(tmp_path: Path, record: Path) -> None:
    b = two_pads()
    default = NetClass(id="cls_00000000-0000-4000-8000-000000000009", name="Default", track_width=mm(0.4))
    circuit = type(b.design.circuit)(
        components=b.design.circuit.components, nets=b.design.circuit.nets, netclasses=(default,)
    )
    design = type(b.design)(header=b.design.header, circuit=circuit, board=b.design.board)
    assert freerouting._defaults(design).width == mm(0.4)  # pyright: ignore[reportPrivateUsage]
    assert freerouting._defaults(b.design) == freerouting.FALLBACK  # pyright: ignore[reportPrivateUsage]


def test_registered_and_not_offsite() -> None:
    """The entry point; ``sends_data_offsite`` is false since ``H-G-DSN-OFFLINE`` was recorded."""
    registered = routers()
    assert "freerouting" in registered
    router: Router = registered["freerouting"]
    assert isinstance(router, FreeroutingRouter)
    assert router.sends_data_offsite is False
    assert "analytics" in router.description


# --- neck-down, the fanout stage and no router feature (change c0110) ---------------------------------


def test_fanout_stage_off_and_neckdown_never_on(tmp_path: Path, record: Path) -> None:
    """Scenario "Fanout stage off, neck-down never on"."""
    result = _router(tmp_path).route(_job(fanout="off", automatic_neckdown="true"))
    argv = _saved(record)["argv"]
    assert isinstance(argv, list)
    assert "--router.automatic_neckdown=false" in argv and "--router.fanout.enabled=false" in argv
    assert not any("automatic_neckdown=true" in word for word in argv)
    (warning,) = result.issues
    assert warning.code == "route.option-ignored" and warning.where == "automatic_neckdown"
    result = _router(tmp_path).route(_job(fanout="maybe"))
    argv = _saved(record)["argv"]
    assert isinstance(argv, list) and not any("fanout" in word for word in argv[2:])
    assert "--router.automatic_neckdown=false" in argv
    (warning,) = result.issues
    assert warning.code == "route.option-ignored" and warning.where == "fanout"
    _router(tmp_path).route(_job(fanout="on"))
    argv = _saved(record)["argv"]
    assert isinstance(argv, list) and not any("fanout" in word for word in argv[2:])


def test_no_features() -> None:
    """Scenario "No features" (requirement "Freerouting declares no router feature")."""
    assert router_features(FreeroutingRouter()) == frozenset()
    assert FreeroutingRouter.features == frozenset()


# --- nets outside the job, tiers and the optimizer (change c0109) --------------------------------------

SESSION_HEAD = """(session board.ses
  (base_design board.dsn)
  (placement
    (resolution um 10)
    (component R1 (place R1 100000 -100000 front 0))
    (component R2 (place R2 200000 -100000 front 0))
    (component R3 (place R3 100000 -150000 front 0))
    (component R4 (place R4 200000 -150000 front 0))
  )
  (was_is)
  (routes
    (resolution um 10)
    (parser (host_cad fenolite))
    (network_out
      (net {net} (wire (path F.Cu 2500 108000 {y} 192000 {y})))
    )
  )
)
"""


def _four(**tiers: int) -> tuple[Bench, RoutingJob]:
    """R1-R2 on ``CLK`` and R3-R4 on ``D0``, 5 mm below; the job holds the nets named in ``tiers``."""
    b = bench(
        design_of(
            Part("R1", "Mini_R_0603", 10, 10, nets={"2": "CLK"}),
            Part("R2", "Mini_R_0603", 20, 10, nets={"1": "CLK"}),
            Part("R3", "Mini_R_0603", 10, 15, nets={"2": "D0"}),
            Part("R4", "Mini_R_0603", 20, 15, nets={"1": "D0"}),
        ),
        selected=tuple(tiers),
    )
    nets = []
    for name, tier in tiers.items():
        pads = tuple(
            JobPad(pad.ref, pad.number, name, pad.position, pad.layers, pad.drill)
            for pad in b.pads
            if pad.net == name
        )
        net_id = b.design.nets_by_name[name].id
        nets.append(JobNet(name, net_id, pads, mm(0.25), mm(0.2), mm(0.6), mm(0.3), tier=tier))
    nets.sort(key=lambda net: (net.tier, net.name))
    extra = {"board_pads": b.pads, "outline": b.outline}
    return b, RoutingJob(b.design, tuple(nets), ("F.Cu", "B.Cu"), {}, extra)


def _session(tmp_path: Path, net: str, y: int) -> Path:
    path = tmp_path / f"{net}.ses"
    path.write_text(SESSION_HEAD.format(net=net, y=y), encoding="utf-8")
    return path


def _runs(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _network(text: str) -> list[str]:
    network = next(node for node in parse(text).items if isinstance(node, SNode) and node.head == "network")
    return [net.words[0] for net in network.all("net")]


def _wiring(text: str) -> tuple[SNode, ...]:
    wiring = next(node for node in parse(text).items if isinstance(node, SNode) and node.head == "wiring")
    return tuple(node for node in wiring.items if isinstance(node, SNode))


@pytest.fixture
def runs(tmp_path: Path, record: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "runs.jsonl"
    monkeypatch.setenv("FAKE_JAVA_RUNS", str(path))
    return path


def test_other_nets_are_left_out_of_the_design_file(
    tmp_path: Path, runs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario "Other nets left out of the design file"."""
    monkeypatch.setenv("FAKE_JAVA_SESSION", str(_session(tmp_path, "CLK", -100000)))
    _b, job = _four(CLK=0)
    result = _router(tmp_path).route(job)
    assert result.routed == ("CLK",) and len(result.tracks) == 1
    (run,) = _runs(runs)
    assert _network(run["dsn"]) == ["CLK"], "D0 is outside the job and is not declared"
    library = next(n for n in parse(run["dsn"]).items if isinstance(n, SNode) and n.head == "library")
    pins = {(image.words[0], pin.words[1]) for image in library.all("image") for pin in image.all("pin")}
    assert {("R3", "2"), ("R4", "1")} <= pins, "the pins of D0 stay in their images"


def test_tiers_give_one_run_each(tmp_path: Path, runs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Scenario "Two tiers with Freerouting"."""
    monkeypatch.setenv("FAKE_JAVA_SESSION_1", str(_session(tmp_path, "CLK", -100000)))
    monkeypatch.setenv("FAKE_JAVA_SESSION_2", str(_session(tmp_path, "D0", -150000)))
    b, job = _four(D0=1, CLK=0)
    result = _router(tmp_path).route(job)
    assert [issue.code for issue in result.issues] == [], result.issues
    first, second = _runs(runs)
    assert _network(first["dsn"]) == ["CLK"] and _network(second["dsn"]) == ["D0"]
    assert _wiring(first["dsn"]) == ()
    # the first session's wire is fixed input of the second run: protected, and on no net
    assert _wiring(second["dsn"]) == (
        SNode(
            "wire",
            (
                SNode("path", ("F.Cu", "250", "10800", "-10000", "19200", "-10000")),
                SNode("type", ("protect",)),
            ),
        ),
    )
    assert [(run.nets, run.tier, run.outcome) for run in result.runs] == [
        (("CLK",), 0, "done"),
        (("D0",), 1, "done"),
    ]
    ids = {b.design.nets_by_name[name].id for name in ("CLK", "D0")}
    assert {track.net_id for track in result.tracks} == ids and len(result.tracks) == 2
    assert result.routed == ("CLK", "D0") and result.unrouted == ()
    merged = apply(job.design, result)
    assert merged.board is not None and len(merged.board.tracks) == 2


def test_tiers_second_run_cut_keeps_the_first(
    tmp_path: Path, runs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_JAVA_SESSION", str(_session(tmp_path, "CLK", -100000)))
    monkeypatch.setenv("FAKE_JAVA_SLEEP_RUN", "2")
    _b, job = _four(CLK=0, D0=1)
    result = _router(tmp_path, budget=None).route(dataclasses.replace(job, budget=2))
    assert [run.outcome for run in result.runs] == ["done", "cut"]
    assert len(result.tracks) == 1 and result.routed == ("CLK",) and result.unrouted == ("D0",)
    assert [issue.code for issue in result.issues] == ["route.budget-exhausted"]


def test_tiers_not_attempted_after_a_cut(tmp_path: Path, runs: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_JAVA_MODE", "sleep")
    _b, job = _four(CLK=0, D0=1)
    result = _router(tmp_path, budget=None).route(dataclasses.replace(job, budget=0.5))
    assert [(run.nets, run.outcome) for run in result.runs] == [(("CLK",), "cut")]
    assert result.not_attempted == ("D0",) and result.unrouted == ("CLK", "D0")
    (issue,) = result.issues
    assert issue.code == "route.budget-exhausted" and "1 net(s) were not attempted" in issue.message
    assert len(_runs(runs)) == 1


def test_optimize_run_replaces_the_first_session(
    tmp_path: Path, runs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``optimize=on``: a second run of the same design file with the optimizer; its session is taken."""
    better = tmp_path / "better.ses"
    text = SESSION.read_text(encoding="utf-8").replace("-120000", "-130000")
    better.write_text(text, encoding="utf-8")
    monkeypatch.setenv("FAKE_JAVA_SESSION_2", str(better))
    result = _router(tmp_path).route(_job(optimize="on"))
    first, second = _runs(runs)
    assert "--router.optimizer.enabled=false" in first["argv"]
    assert "--router.optimizer.enabled=false" not in second["argv"]
    assert first["dsn"] == second["dsn"]
    assert [run.outcome for run in result.runs] == ["done", "done"]
    assert [issue.code for issue in result.issues] == []
    assert [(t.start, t.end) for t in result.tracks] == [
        (pt(10.8, 10), pt(15, 13)),
        (pt(15, 13), pt(19.2, 10)),
    ], "the copper is the second session's, not both"


def test_optimize_run_cut_keeps_the_first_session(
    tmp_path: Path, runs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario "Optimizer run cut"."""
    monkeypatch.setenv("FAKE_JAVA_MODE", "sleep-optimizer")
    job = dataclasses.replace(_job(optimize="on"), budget=2)
    result = _router(tmp_path, budget=None).route(job)
    assert [(t.start, t.end) for t in result.tracks] == [
        (pt(10.8, 10), pt(15, 12)),
        (pt(15, 12), pt(19.2, 10)),
    ]
    assert [run.outcome for run in result.runs] == ["done", "cut"]
    (issue,) = result.issues
    assert (issue.code, issue.severity) == ("route.optimizer-cut", "info")
    assert result.routed == ("A",) and result.not_attempted == ()
    assert ISSUE_CODES["route.optimizer-cut"] == "info"


def test_optimize_run_that_fails_keeps_the_first_session(
    tmp_path: Path, runs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    garbage = tmp_path / "garbage.ses"
    garbage.write_text("(pcb not-a-session)", encoding="utf-8")
    monkeypatch.setenv("FAKE_JAVA_SESSION_2", str(garbage))
    result = _router(tmp_path).route(_job(optimize="on"))
    assert len(result.tracks) == 2 and [run.outcome for run in result.runs] == ["done", "failed"]
    assert [issue.code for issue in result.issues] == ["route.optimizer-cut"]


def test_optimize_is_ignored_with_tiers_and_checked(
    tmp_path: Path, runs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("FAKE_JAVA_SESSION_1", str(_session(tmp_path, "CLK", -100000)))
    monkeypatch.setenv("FAKE_JAVA_SESSION_2", str(_session(tmp_path, "D0", -150000)))
    _b, job = _four(CLK=0, D0=1)
    result = _router(tmp_path).route(dataclasses.replace(job, options={"optimize": "on"}))
    assert len(_runs(runs)) == 2, "one run per tier and no optimizer run"
    (issue,) = result.issues
    assert issue.code == "route.option-ignored" and "tier" in issue.message
    runs.unlink()
    monkeypatch.delenv("FAKE_JAVA_SESSION_1")
    monkeypatch.delenv("FAKE_JAVA_SESSION_2")
    result = _router(tmp_path).route(_job(optimize="yes"))
    assert [issue.code for issue in result.issues] == ["route.option-ignored"] and len(_runs(runs)) == 1
    runs.unlink()
    result = _router(tmp_path).route(_job(optimize="off"))
    assert not result.issues and len(_runs(runs)) == 1


def test_net_of_a_wider_class_stays_declared_and_is_named(
    tmp_path: Path, runs: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The fallback of ``H-G-DSN-NETLESS``: a net outside the job whose class clearance is larger than
    the default rule stays declared, and one ``route.net-declared`` (info) names it."""
    b = netless_bench()
    session = tmp_path / "a.ses"
    session.write_text(
        "(session board.ses (base_design board.dsn) (placement (resolution um 10)) (was_is)\n"
        "  (routes (resolution um 10) (parser (host_cad fenolite))\n"
        "    (network_out (net A (wire (path F.Cu 2500 108000 -90950 192000 -90950))))))\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("FAKE_JAVA_SESSION", str(session))
    net = b.design.nets_by_name["A"]
    pads = tuple(
        JobPad(pad.ref, pad.number, "A", pad.position, pad.layers, pad.drill)
        for pad in b.pads
        if pad.net == "A"
    )
    job = RoutingJob(
        b.design,
        (JobNet("A", net.id, pads, mm(0.25), mm(0.2), mm(0.6), mm(0.3)),),
        ("F.Cu", "B.Cu"),
        {},
        {"board_pads": b.pads, "outline": b.outline},
    )
    result = _router(tmp_path).route(job)
    (run,) = _runs(runs)
    assert _network(run["dsn"]) == ["A", "B"], "C is left out; B is in a class with a wider clearance"
    (issue,) = result.issues
    assert (issue.code, issue.severity, issue.where) == ("route.net-declared", "info", "B")
    assert "1 net(s)" in issue.message and issue.message.endswith(": B")
    assert result.routed == ("A",) and len(result.tracks) == 1
    assert ISSUE_CODES["route.net-declared"] == "info"


# --- planes, layers and rules (change c0107) -------------------------------------------------------------


def test_planes_layers_and_rules_reach_the_design_file(
    tmp_path: Path, record: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scenario "Recorded design file" (capability routing, "Freerouting plugin sends planes, layers and
    rules"; change c0107): the kept file holds the power layers, a plane, ``use_layer`` and ``class_class``,
    and the arguments are those of a job without them."""
    import dataclasses

    import _planebench as pb

    monkeypatch.setenv("KICAD_CONFIG_HOME", str(tmp_path / "kicad-config"))
    found = pb.load(pb.build_project(tmp_path / "bench"))
    by_net: dict[str, list[JobPad]] = {}
    for pad in found.pads:
        if pad.net in (*pb.SIGNALS, *pb.HIGH):
            by_net.setdefault(pad.net, []).append(
                JobPad(pad.ref, pad.number, pad.net, pad.position, pad.layers, pad.drill)
            )
    nets = tuple(
        JobNet(name, found.net_id(name), tuple(pads), mm(0.2), mm(0.2), mm(0.6), mm(0.3),
               ("F.Cu",) if name == "SIG1" else None)
        for name, pads in sorted(by_net.items())
    )  # fmt: skip
    extra = {"board_pads": found.pads, "outline": found.outline}
    layers = ("F.Cu", "In1.Cu", "In2.Cu", "B.Cu")
    job = RoutingJob(found.design, nets, layers, {}, extra, plane_layers=pb.PLANE_LAYERS)
    kept = tmp_path / "kept.dsn"
    monkeypatch.setenv("FAKE_JAVA_KEEP_DSN", str(kept))
    monkeypatch.setenv("FAKE_JAVA_MODE", "none")
    router = _router(tmp_path)
    router.route(job)
    text = " ".join(kept.read_text(encoding="utf-8").split()).replace("( ", "(").replace(" )", ")")
    assert "(layer In1.Cu (type power))" in text and "(layer In2.Cu (type power))" in text
    assert "(plane GND (polygon In1.Cu 0 " in text and "(plane VCC (polygon In2.Cu 0 " in text
    assert "(use_layer F.Cu)" in text and "(class SIG@2 SIG1 " in text
    assert "(class_class (classes HV SIG) (rule (clearance 1000)))" in text
    assert "(class_class (classes HV SIG@2) (rule (clearance 1000)))" in text
    planes_argv = _saved(record)["argv"]
    plain = dataclasses.replace(
        job, plane_layers=(), nets=tuple(dataclasses.replace(net, layers=None) for net in nets)
    )
    router.route(plain)
    assert _saved(record)["argv"] == planes_argv
    before = " ".join(kept.read_text(encoding="utf-8").split())
    assert "(type power)" not in before and "use_layer" not in before and "(plane " not in before
