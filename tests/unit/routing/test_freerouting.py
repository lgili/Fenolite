# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The Freerouting plugin with a fake ``java`` (capability routing, "Freerouting plugin"; change c0023).
Hermetic: no Java, no jar of Freerouting and no network."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from _fakefreerouting import create_fake_docker, create_fake_jar, create_fake_java
from _placed import mm, pt
from _resources import posix_tools
from _specctra import Bench, two_pads

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
from fenolite.routing.protocol import JobNet, JobPad, Router, RoutingJob
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


def _router(tmp_path: Path, *, version: str = "25.0.1", timeout: float = 60) -> FreeroutingRouter:
    return FreeroutingRouter(create_fake_jar(tmp_path), create_fake_java(tmp_path, version=version), timeout)


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
    ]
    merged = apply(job.design, result)
    assert merged.board is not None and len(merged.board.tracks) == 2 and len(merged.board.vias) == 1


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


def test_timeout(tmp_path: Path, record: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FAKE_JAVA_MODE", "sleep")
    result = _router(tmp_path, timeout=0.5).route(_job())
    assert [issue.code for issue in result.issues] == ["route.tool-failed"]
    assert "0.5 s" in result.issues[0].message and result.tracks == ()


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
