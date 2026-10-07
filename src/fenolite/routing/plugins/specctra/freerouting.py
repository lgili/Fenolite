# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Freerouting adapter (capability routing, "Freerouting plugin"; change c0023).

Freerouting is a GPL-3.0 program: it runs as a subprocess, or in a container, on a Specctra design file in
a temporary folder, and its session file is read back into tracks and vias. Fenolite never imports or
vendors it (ADR-0006), and this module opens no network connection: the jar is downloaded only by
``fenolite fetch freerouting --confirm`` (ADR-0007). The jar is ``path``, else ``FENOLITE_FREEROUTING_JAR``,
else the file that command installed in the tools folder (``fenolite.core.tools``); ``java`` is
``FENOLITE_JAVA``, else the one on ``PATH``. A ``path`` of the form ``docker:<image>`` runs that image with
the network disabled.

A job is routed inside one time budget (``routing.budget``; change c0109): one run per tier, each on a
design file that declares only the nets of that tier, with the copper of earlier tiers as protected
wiring. The optimizer is switched off (``H-G-DSN-NOOPT``): with it on, the session is written only when
the optimizer ends, and a run stopped before that gives nothing. ``optimize=on`` runs it afterwards on
the time that is left and keeps the first session when that run is cut.

The flag that disables its analytics is always passed and cannot be removed through router options.
``sends_data_offsite`` is ``False``: the pinned image routes with the network disabled (``H-G-DSN-OFFLINE``,
recorded on 2026-10-04).
"""

from __future__ import annotations

import dataclasses
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path
from typing import Any, cast

from fenolite.backends.specctra.dsn import DsnDefaults, DsnResult, write_dsn
from fenolite.backends.specctra.ses import read_session, to_copper
from fenolite.core.errors import FormatError, Issue
from fenolite.core.evidence import Evidence
from fenolite.core.tools import tool_path
from fenolite.model.board import Track, Via
from fenolite.model.design import Design
from fenolite.routing.budget import Budget, exhausted
from fenolite.routing.merge import RoutingError, apply
from fenolite.routing.protocol import JobNet, RouterRun, RouterStatus, RoutingJob, RoutingResult

PINNED_VERSION = "2.4.1"
PINNED_REVISION = "ae3d377740b6ffa744bed1bab26625fe0278fa90"
"""The commit of the tag ``v2.4.1`` (S-0223), which the jar's manifest names as its build revision."""
JAVA_MIN = 25
DEFAULT_PASSES = 20
DEFAULT_BUDGET = 900
"""Seconds for the whole job when neither the job nor the constructor names a budget."""
OPTIMIZER_OFF = "--router.optimizer.enabled=false"
"""The setting that stops the optimization stage (S-0222; ``-mt 0`` does not, ``H-G-DSN-NOOPT``)."""
JAR_ENV = "FENOLITE_FREEROUTING_JAR"
FETCH_NAME = "freerouting"
"""The folder of the jar in the tools folder, and the name of its row in ``fenolite fetch``."""
FETCH_COMMAND = "fenolite fetch freerouting --confirm"
"""The command that installs the pinned jar where the plugin finds it (ADR-0007)."""
JAVA_ENV = "FENOLITE_JAVA"
DOCKER_PREFIX = "docker:"
# The jar inside the pinned image: its default command starts the API server, so the plugin names the jar
# itself (read from the image configuration of 2.4.1, S-0226).
IMAGE_JAR = "/app/freerouting-executable.jar"
FALLBACK = DsnDefaults(width=200_000, clearance=200_000, via_diameter=600_000, via_drill=300_000)
"""The board defaults of ``fenolite route`` for a design without a ``Default`` class."""
EVIDENCE = Evidence(
    oracle=f"Freerouting {PINNED_VERSION}",
    hypotheses=(
        "H-G-DSN-ACCEPT",
        "H-G-DSN-NETLESS-2",
        "H-G-DSN-NOOPT",
        "H-G-DSN-PROTECT",
        "H-G-DSN-ROUTE",
        "H-G-DSN-UNITS",
    ),
)
"""Describes the plugin; a route itself is always ``UNVERIFIED``."""
_JAR_NAME = re.compile(r"freerouting-(\d+(?:\.\d+)+)(?:-[\w.]+)?\.jar$")


def java_major(version_line: str) -> int | None:
    """The Java major of the first line of ``java -version`` (JEP 223, S-0081): ``1.8.0_402`` gives 8,
    ``17.0.2`` 17."""
    match = re.search(r'"(\d+)(?:\.(\d+))?', version_line) or re.search(r"\b(\d+)(?:\.(\d+))?", version_line)
    if match is None:
        return None
    first = int(match.group(1))
    return int(match.group(2)) if first == 1 and match.group(2) else first


def jar_version(jar: Path) -> str:
    """The Freerouting version of ``jar`` without running it: the pinned version when its manifest names
    the pinned build revision, else the version in its file name, else ``unknown``."""
    try:
        with zipfile.ZipFile(jar) as archive:
            manifest = archive.read("META-INF/MANIFEST.MF").decode("utf-8", errors="replace")
    except (OSError, KeyError, zipfile.BadZipFile):
        manifest = ""
    if re.search(rf"^Build-Revision:\s*{PINNED_REVISION}\s*$", manifest, flags=re.MULTILINE):
        return PINNED_VERSION
    named = _JAR_NAME.search(jar.name)
    return named.group(1) if named else "unknown"


def _line(text: str, folder: Path) -> str:
    return re.sub(r"[\x00-\x1f\x7f]", " ", text.replace(str(folder), "<run-dir>")).strip()[:300]


def _tail(output: str, folder: Path, count: int = 20) -> tuple[str, ...]:
    lines = [_line(line, folder) for line in output.splitlines()]
    return tuple(line for line in lines if line)[-count:]


UNROUTED_NET = re.compile(r"Net '(?P<name>[^\n]*?)' \((?P<count>\d+) unrouted connections?\)")
UNROUTED_TOTAL = re.compile(r"\((?P<count>\d+) unrouted and \d+ violations?\)")


def _unrouted_report(output: str) -> tuple[tuple[str, ...], int]:
    """What Freerouting's own output says it left open: the written names of the nets it lists with
    unrouted connections, and the count of its last score line (0 without one). A session holds the
    wires that were routed and says nothing about a connection that was not, so a net with copper may
    still be open (``H-G-DSN-INCOMPLETE``)."""
    nets = tuple(dict.fromkeys(match["name"] for match in UNROUTED_NET.finditer(output)))
    totals = [int(match["count"]) for match in UNROUTED_TOTAL.finditer(output)]
    return nets, (totals[-1] if totals else 0)


def _defaults(design: Design) -> DsnDefaults:
    """The values of the design's ``Default`` class, each falling back to ``FALLBACK``."""
    found = next((c for c in design.circuit.netclasses if c.name.casefold() == "default"), None)
    if found is None:
        return FALLBACK
    try:
        return DsnDefaults(
            width=found.track_width or FALLBACK.width,
            clearance=found.clearance or FALLBACK.clearance,
            via_diameter=found.via_diameter or FALLBACK.via_diameter,
            via_drill=found.via_drill or FALLBACK.via_drill,
        )
    except ValueError:
        return FALLBACK


class FreeroutingRouter:
    """Route the selected nets with Freerouting, through a Specctra design file and its session."""

    name = "freerouting"
    description = (
        "Routes nets with the external Freerouting autorouter (GPL-3.0, run as a subprocess) through a "
        "Specctra design file; its analytics are always disabled."
    )
    sends_data_offsite = False
    default_budget: float = DEFAULT_BUDGET

    def __init__(
        self, path: str | Path | None = None, java: str | Path | None = None, budget: float | None = None
    ) -> None:
        self._path = str(path) if path else ""
        self._java = str(java) if java else ""
        self.budget = budget
        """Seconds for a job that names no budget of its own; ``None`` gives ``DEFAULT_BUDGET``."""

    # The environment and the tools folder are read on use, not at construction: the registry builds one
    # instance per process.

    def _located(self) -> tuple[str, str | None]:
        """The location and which of the three places gave it: the constructor's path (``argument``),
        ``FENOLITE_FREEROUTING_JAR`` (``env``), or the file ``fenolite fetch`` installed (``fetched``, only
        when it exists); ``("", None)`` without any."""
        if self._path:
            return self._path, "argument"
        named = os.environ.get(JAR_ENV, "")
        if named:
            return named, "env"
        try:
            fetched = tool_path(FETCH_NAME, f"freerouting-{PINNED_VERSION}.jar")
        except ValueError:  # a relative FENOLITE_TOOLS_DIR names no folder
            return "", None
        return (str(fetched), "fetched") if fetched.is_file() else ("", None)

    @property
    def _raw(self) -> str:
        return self._located()[0]

    @property
    def jar_source(self) -> str | None:
        """Which place gave the jar: ``argument``, ``env`` or ``fetched``; ``None`` without a jar."""
        raw, source = self._located()
        return None if not raw or raw.startswith(DOCKER_PREFIX) else source

    @property
    def jar_missing(self) -> bool:
        """Whether a jar is what is missing: none is named, or the named file does not exist."""
        return not self.image and (self.jar is None or not self.jar.is_file())

    @property
    def image(self) -> str:
        """The container image of a ``docker:<image>`` location, else ``""``."""
        raw = self._raw
        return raw[len(DOCKER_PREFIX) :] if raw.startswith(DOCKER_PREFIX) else ""

    @property
    def jar(self) -> Path | None:
        """The jar: the constructor's path, else ``FENOLITE_FREEROUTING_JAR``, else the fetched file;
        ``None`` without any."""
        raw = self._raw
        return Path(raw).expanduser() if raw and not raw.startswith(DOCKER_PREFIX) else None

    @property
    def java(self) -> str:
        """The Java to run: the constructor's, else ``FENOLITE_JAVA``, else ``java`` on ``PATH``."""
        return self._java or os.environ.get(JAVA_ENV) or shutil.which("java") or ""

    # --- availability -----------------------------------------------------------------------------

    def java_version(self) -> tuple[str, int | None]:
        """The first line of ``java -version`` and its major; ``("", None)`` when java cannot run."""
        if not self.java:
            return "", None
        try:
            done = subprocess.run(
                [self.java, "-version"], capture_output=True, text=True, timeout=60, check=False
            )
        except (OSError, subprocess.TimeoutExpired):
            return "", None
        lines = (done.stderr or done.stdout).splitlines()
        line = lines[0].strip() if lines else ""
        return line, java_major(line)

    def available(self) -> RouterStatus:
        """Whether the jar and a Java of at least ``JAVA_MIN`` are here (or Docker, for an image). It runs
        ``java -version`` at most; it never starts the router."""
        if self.image:
            if shutil.which("docker") is None:
                return RouterStatus(
                    False, path=f"{DOCKER_PREFIX}{self.image}", reason="docker not found on PATH"
                )
            tag = self.image.rsplit(":", 1)[-1] if ":" in self.image.rsplit("/", 1)[-1] else "unknown"
            return RouterStatus(True, f"{DOCKER_PREFIX}{self.image}", tag.split("@", 1)[0])
        if self.jar is None:
            return RouterStatus(
                False,
                reason=f"no Freerouting jar: run '{FETCH_COMMAND}', or set {JAR_ENV}",
            )
        if not self.jar.is_file():
            return RouterStatus(
                False,
                path=str(self.jar),
                reason=(
                    f"the Freerouting jar {self.jar} is missing: run '{FETCH_COMMAND}', or correct {JAR_ENV}"
                ),
            )
        version = jar_version(self.jar)
        line, major = self.java_version()
        if major is None or major < JAVA_MIN:
            found = f"found {line!r}" if line else f"no java found (set {JAVA_ENV} or put java on PATH)"
            return RouterStatus(
                False,
                path=str(self.jar),
                version=version,
                reason=f"Freerouting {PINNED_VERSION} needs Java {JAVA_MIN} or newer: {found}",
            )
        return RouterStatus(True, str(self.jar), version)

    # --- routing ----------------------------------------------------------------------------------

    def command(self, folder: Path, passes: int, *, optimizer: bool = False) -> list[str]:
        """The command line of one run in ``folder``; the analytics flag is always part of it, and the
        optimizer is switched off unless ``optimizer`` is true."""
        arguments = [
            "-de",
            "board.dsn",
            "-do",
            "board.ses",
            "-mp",
            str(passes),
            "-mt",
            "1",
            "-da",
            "--gui.enabled=false",
        ]
        if not optimizer:
            arguments.append(OPTIMIZER_OFF)
        if self.image:
            mount = f"{folder}:/work"
            return [
                "docker", "run", "--rm", "--network", "none", "-v", mount, "-w", "/work",
                "-e", "HOME=/work", self.image, "java", "-jar", IMAGE_JAR, *arguments,
            ]  # fmt: skip
        return [self.java, "-jar", str(self.jar), *arguments]

    def _failed(
        self, job: RoutingJob, version: str, code: str, message: str, log: tuple[str, ...] = ()
    ) -> RoutingResult:
        return RoutingResult(
            unrouted=tuple(net.name for net in job.nets),
            issues=(Issue(code, "error", message, self.name),),
            tool=self.name,
            tool_version=version,
            log=log,
            evidence=Evidence(),
        )

    def _options(self, job: RoutingJob, tiers: int, issues: list[Issue]) -> tuple[int, bool]:
        """The passes and whether the optimizer run is asked for; every other option is reported."""
        passes = DEFAULT_PASSES
        optimize = False

        def ignored(key: str, value: str, why: str) -> None:
            issues.append(
                Issue(
                    "route.option-ignored",
                    "warning",
                    f"the router option {key}={value} {why} and was ignored",
                    key,
                    hint="supported: max-passes=N, optimize=on|off; analytics are always disabled",
                )
            )

        for key, value in job.options.items():
            if key == "max-passes" and value.isdigit() and int(value) > 0:
                passes = int(value)
            elif key == "optimize" and value in ("on", "off"):
                if value == "on" and tiers > 1:
                    ignored(key, value, "cannot be used with more than one tier (--order)")
                else:
                    optimize = value == "on"
            else:
                ignored(key, value, f"is not supported by {self.name}")
        return passes, optimize

    def _run(
        self,
        budget: Budget,
        text: str,
        passes: int,
        *,
        optimizer: bool,
    ) -> tuple[str, str | None, tuple[str, ...], float, str]:
        """One process on the design file ``text`` in a fresh temporary folder.

        Returns the outcome (``done``, ``failed``, ``cut`` or ``unstarted``), the session text when one
        was written by a process that ended in time, the tail of the output, the seconds and the whole
        output. A process stopped by the budget gives no session: Freerouting writes it only when routing
        has finished.
        """
        with tempfile.TemporaryDirectory(prefix="fenolite-freerouting-") as name:
            folder = Path(name)
            (folder / "board.dsn").write_text(text, encoding="utf-8", newline="\n")
            done = budget.run(
                self.command(folder, passes, optimizer=optimizer),
                cwd=folder,
                env={**os.environ, "HOME": str(folder), "LANG": "C", "LC_ALL": "C"},
            )
            output = done.stdout + "\n" + done.stderr
            log = _tail(output, folder)
            if not done.started:
                return "unstarted", None, log, 0.0, output
            if done.cut:
                return "cut", None, log, done.seconds, output
            session_file = folder / "board.ses"
            if not session_file.is_file():
                last = log[-1] if log else "no output"
                why = f"Freerouting wrote no session (exit {done.returncode}): {last}"
                return "failed", why, log, done.seconds, output
            try:
                return "done", session_file.read_text(encoding="utf-8"), log, done.seconds, output
            except UnicodeDecodeError as error:
                why = f"Freerouting's session cannot be read: {_line(str(error), folder)}"
                return "failed", why, log, done.seconds, output

    def _copper(
        self, session_text: str, written: DsnResult, selected: tuple[str, ...]
    ) -> tuple[tuple[Track, ...], tuple[Via, ...], tuple[Issue, ...]] | str:
        """The copper of a session for ``selected``, or why the session cannot be read."""
        try:
            session = read_session(session_text, file="board.ses")
            return to_copper(session, written.names, selected=selected)
        except FormatError as error:
            return f"Freerouting's session cannot be read: {_line(str(error), Path('board.ses'))}"

    def route(self, job: RoutingJob) -> RoutingResult:
        """Route the job tier by tier inside its budget: write a design file, run Freerouting on it and
        take the session's copper for the tier's nets. Every failure comes back as an issue; nothing is
        written outside a temporary folder."""
        status = self.available()
        version = status.version
        if not status.available:
            return self._failed(
                job, version, "route.tool-missing", status.reason or "Freerouting is unavailable"
            )
        pads = job.extra.get("board_pads")
        outline = job.extra.get("outline")
        if not isinstance(pads, tuple) or not isinstance(outline, tuple) or not outline:
            return self._failed(
                job,
                version,
                "route.tool-failed",
                "Freerouting needs the board-frame pads and a closed board outline (RoutingJob.extra)",
            )
        budget = Budget(job.budget or self.budget or DEFAULT_BUDGET)
        issues: list[Issue] = []
        tiers: dict[int, list[JobNet]] = {}
        for net in job.nets:
            tiers.setdefault(net.tier, []).append(net)
        passes, optimize = self._options(job, len(tiers), issues)
        defaults = _defaults(job.design)
        current = job.design
        tracks: list[Track] = []
        vias: list[Via] = []
        runs: list[RouterRun] = []
        not_attempted: list[str] = []
        incomplete: set[str] = set()
        cut_nets = 0
        ended = False
        log: tuple[str, ...] = ()
        declared: set[str] = set()
        job_names = {net.name for net in job.nets}

        def note(found: tuple[Issue, ...] | list[Issue]) -> None:
            issues.extend(issue for issue in found if issue not in issues)

        try:
            net_layers = {net.name: net.layers for net in job.nets if net.layers is not None}
            for tier in sorted(tiers):
                names = tuple(net.name for net in tiers[tier])
                if ended or budget.left() <= 0:  # no process starts once the budget is spent
                    ended = True
                    not_attempted.extend(names)
                    continue
                try:
                    # The nets of earlier tiers are outside this run: they leave the network section and
                    # their copper, old and new, is protected wiring without a net.
                    written = write_dsn(
                        current,
                        pads=cast(Any, pads),  # BoardPad records: typed in backends.base, out of reach here
                        outline=cast(Any, outline),
                        selected=names,
                        defaults=defaults,
                        others="netless",
                        # change c0107: the plane layers of the job and the layers its nets are kept
                        # to; the rules travel in the design. A job without them writes the file it
                        # wrote before.
                        plane_layers=job.plane_layers,
                        net_layers=net_layers,
                    )
                except ValueError as error:
                    return self._failed(
                        job, version, "route.tool-failed", f"no design file could be written: {error}"
                    )
                note(written.issues)
                declared.update(name for name in written.names.nets.values() if name not in names)
                outcome, session_text, log, seconds, output = self._run(
                    budget, written.text, passes, optimizer=False
                )
                if outcome == "unstarted":
                    ended = True
                    not_attempted.extend(names)
                    continue
                if outcome == "cut":
                    ended = True
                    cut_nets += len(names)
                    runs.append(RouterRun(names, tier, seconds, "cut"))
                    continue
                got = self._copper(session_text or "", written, names) if outcome == "done" else session_text
                if isinstance(got, str) or got is None:
                    runs.append(RouterRun(names, tier, seconds, "failed"))
                    issues.append(Issue("route.tool-failed", "error", got or "no session", self.name))
                    continue
                runs.append(RouterRun(names, tier, seconds, "done"))
                if optimize:
                    better = self._optimized(budget, written, passes, names, tier, runs, issues)
                    if better is not None:
                        got, log, output = better
                run_tracks, run_vias, found = got
                note(found)
                open_nets, open_total = _unrouted_report(output)
                incomplete.update(written.names.nets.get(name, name) for name in open_nets)
                if open_total and not open_nets:
                    issues.append(
                        Issue(
                            "route.unrouted",
                            "warning",
                            f"Freerouting reports {open_total} unrouted connection(s) and names no net",
                            self.name,
                            hint="run 'fenolite check': KiCad's DRC lists the unconnected items",
                        )
                    )
                try:
                    current = apply(current, RoutingResult(tracks=run_tracks, vias=run_vias))
                except RoutingError as error:
                    issues.extend(error.issues)
                    runs[-1] = dataclasses.replace(runs[-1], outcome="failed")
                    continue
                tracks.extend(run_tracks)
                vias.extend(run_vias)
        except OSError as error:
            return self._failed(job, version, "route.tool-failed", f"Freerouting could not run: {error}")
        if cut_nets or not_attempted:
            issues.append(exhausted(budget.seconds, cut_nets, len(not_attempted), self.name))
        outside = sorted(declared - job_names)
        if outside:
            shown = ", ".join(outside[:5]) + (f" and {len(outside) - 5} more" if len(outside) > 5 else "")
            issues.append(
                Issue(
                    "route.net-declared",
                    "info",
                    f"{len(outside)} net(s) outside the job stayed declared in the design file, because "
                    f"their class clearance is larger than the default rule: {shown}",
                    outside[0],
                    hint="the router may route them too; that copper is not taken",
                )
            )
        if version != PINNED_VERSION:
            issues.append(
                Issue(
                    "route.tool-unpinned",
                    "warning",
                    f"expected Freerouting {PINNED_VERSION}, found {version}",
                    self.name,
                )
            )
        with_copper = {item.net_id for item in (*tracks, *vias)}
        routed = tuple(
            net.name for net in job.nets if net.net_id in with_copper and net.name not in incomplete
        )
        return RoutingResult(
            tracks=tuple(tracks),
            vias=tuple(vias),
            routed=routed,
            unrouted=tuple(net.name for net in job.nets if net.name not in routed),
            issues=tuple(issues),
            tool=self.name,
            tool_version=version,
            log=log,
            evidence=Evidence(oracle=f"Freerouting {version}", hypotheses=EVIDENCE.hypotheses),
            runs=tuple(runs),
            not_attempted=tuple(not_attempted),
        )

    def _optimized(
        self,
        budget: Budget,
        written: DsnResult,
        passes: int,
        names: tuple[str, ...],
        tier: int,
        runs: list[RouterRun],
        issues: list[Issue],
    ) -> tuple[tuple[tuple[Track, ...], tuple[Via, ...], tuple[Issue, ...]], tuple[str, ...], str] | None:
        """The second run of ``optimize=on``: the same design file with the optimizer, on the time left.

        Returns its copper, log and output when it wrote a readable session in time; else ``None``, with
        ``route.optimizer-cut`` (info) reported: the first session is kept.
        """
        outcome, session_text, log, seconds, output = self._run(budget, written.text, passes, optimizer=True)
        if outcome != "unstarted":
            runs.append(RouterRun(names, tier, seconds, "cut" if outcome == "cut" else "failed"))
        got = self._copper(session_text or "", written, names) if outcome == "done" else None
        if got is None or isinstance(got, str):
            why = {
                "unstarted": "no time was left for it",
                "cut": "the budget ended before it wrote a session",
            }.get(outcome, "it wrote no session that can be read")
            issues.append(
                Issue(
                    "route.optimizer-cut",
                    "info",
                    f"the optimizer run of Freerouting gave nothing ({why}); the copper of the first "
                    f"run is kept",
                    self.name,
                    hint="run route again with --rip and a larger --timeout to give the optimizer more time",
                )
            )
            return None
        runs[-1] = dataclasses.replace(runs[-1], outcome="done")
        return got, log, output


__all__ = [
    "DEFAULT_BUDGET",
    "DEFAULT_PASSES",
    "EVIDENCE",
    "JAVA_MIN",
    "OPTIMIZER_OFF",
    "PINNED_REVISION",
    "PINNED_VERSION",
    "FreeroutingRouter",
    "jar_version",
    "java_major",
]
