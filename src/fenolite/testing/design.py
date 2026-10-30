# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Build-backed assertions with private plans and deterministic inputs (c0256)."""

from __future__ import annotations

import shutil
import tempfile
import weakref
from collections.abc import Mapping
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from fenolite.testing.findings import Findings
    from fenolite.testing.views import NetView, PartView, PinView

from fenolite import api
from fenolite.core.evidence import Evidence
from fenolite.core.state import using_state
from fenolite.model.canonical import load_dir

DEFAULT_TIMESTAMP = "2026-01-01T00:00:00Z"
BLOCK_PATH = "fenolite.path"
"""The component property that holds a block part's path, such as ``dut/U1`` (change c0251)."""
INSTANCE = "dut"
"""The instance name ``instantiate`` gives the block: its ports are the nets ``dut/<port>``."""
BENCH_BOARD_MM = 100
"""The side of the square board of an ``instantiate`` design, in millimetres: room for a block's parts."""
_PENDING: dict[str, tuple[object, dict[str, object]]] = {}
"""The block and parameters an ``instantiate`` script takes, by key, while its build runs."""
BENCH = """from fenolite.dsl import Design, mm
from fenolite.testing.design import _PENDING

block, params = _PENDING[{key!r}]
design = Design({name!r})
design.board(mm({side}), mm({side}))
design.use(block, {instance!r}, **params)
"""


class TestingError(AssertionError):
    """A build or query failed; the original diagnostic is retained in its message."""

    __test__ = False


def checked(reply: api.Reply) -> api.Reply:
    if reply.exit_code:
        error = reply.error or {}
        issues = (reply.envelope or {}).get("issues", [])
        detail = " ".join(str(error.get(k, "")) for k in ("code", "message", "where", "hint"))
        # a refused build names its error findings (a circuit rating, a model error), not only FEN-5001
        errors = "; ".join(
            f"{found.get('code')} at {found.get('where', '')}: {found.get('message', '')}"
            for found in issues
            if found.get("severity") == "error"
        )
        detail = f"{detail.strip()}: {errors}" if errors else detail.strip()
        raise TestingError(detail or str(issues) or f"command exited {reply.exit_code}")
    return reply


def evidence_of(data: Mapping[str, Any]) -> Evidence:
    return Evidence(data.get("level", "UNVERIFIED"), data.get("oracle"), tuple(data.get("hypotheses", ())))


class TestDesign:
    """A built design; close removes only the private folder owned by this object."""

    __test__ = False

    def __init__(self, path: Path, private: Path, reply: api.Reply) -> None:
        self.path = path
        self.model = load_dir(path / ".fenolite")
        self.board = api.read_board(path)
        self.evidence = evidence_of((reply.envelope or {}).get("evidence", {}))
        self._build_issues = tuple((reply.envelope or {}).get("issues", ()))
        self._private = private
        self._finalizer = weakref.finalize(self, shutil.rmtree, private, ignore_errors=True)

    def _open(self) -> None:
        if not self._finalizer.alive:
            raise TestingError("the test design is closed")

    def __enter__(self) -> TestDesign:
        self._open()
        return self

    def __exit__(self, *args: object) -> None:
        self.close()

    def net(self, name: str) -> NetView:
        from fenolite.testing.views import NetView, unknown

        self._open()
        circuit = self.model.circuit
        net = next((net for net in circuit.nets if net.name == name), None)
        if net is None:
            # a port of several members (a block's Rail port ``dut/VOUT``) reads as its only or main member
            from fenolite.dsl.portnets import MAIN_MEMBERS

            members = {
                n.name.removeprefix(f"{name}."): n for n in circuit.nets if n.name.startswith(f"{name}.")
            }
            main = next((members[m] for m in MAIN_MEMBERS.values() if m in members), None)
            net = next(iter(members.values())) if len(members) == 1 else main
        if net is None:
            raise unknown("net", name, tuple(n.name for n in circuit.nets))
        refs = {part.id: part.ref for part in circuit.components}
        classes = {cls.id: cls.name for cls in circuit.netclasses}
        roles = self.model.rules.roles if self.model.rules else None
        role = next((r.kind for r in roles.nets if r.net == net.name), None) if roles else None
        return NetView(
            net.name,
            net.id,
            classes.get(net.netclass_id or ""),
            role,
            None,
            tuple(sorted(f"{refs[p.component_id]}-{p.pin}" for p in net.members)),
        )

    def ref(self, ref: str) -> PartView:
        from fenolite.testing.views import PartView, PinView, unknown

        self._open()
        parts = self.model.circuit.components
        part = next((p for p in parts if ref in (p.ref, p.path, p.properties.get(BLOCK_PATH))), None)
        if part is None:
            names = {p.ref for p in parts} | {
                p.properties[BLOCK_PATH] for p in parts if BLOCK_PATH in p.properties
            }
            raise unknown("part", ref, tuple(sorted(names)))
        nets = {(p.component_id, p.pin): n.name for n in self.model.circuit.nets for p in n.members}
        pins = tuple(
            PinView(f"{part.ref}-{p.number}", p.id, nets.get((part.id, p.number))) for p in part.pins
        )
        aliases = tuple(
            (name, view)
            for pin, view in zip(part.pins, pins, strict=True)
            for name in (pin.number, pin.name)
            if name
        )
        return PartView(part.ref, part.id, part.value, part.lib_footprint_ref, None, pins, aliases)

    def _endpoint(self, item: PinView | NetView | str) -> tuple[str | None, tuple[str, ...]]:
        from fenolite.testing.views import NetView, PinView

        if isinstance(item, NetView):
            mine = self.net(item.name)
            if mine.id != item.id:
                raise TestingError("net belongs to a different design")
            return mine.name, mine.pins
        if isinstance(item, PinView):
            where = item.where
        else:
            where = item
        ref, sep, number = where.rpartition("-")
        if not sep:
            raise TestingError(f"expected REF-PIN, got {where!r}")
        pin = self.ref(ref)[number]
        if isinstance(item, PinView) and pin != item:
            raise TestingError("pin belongs to a different design")
        return pin.net, (pin.where,)

    def connected(
        self, a: PinView | NetView | str, b: PinView | NetView | str, *, copper: bool = False
    ) -> bool:
        self._open()
        net_a, pins_a = self._endpoint(a)
        net_b, pins_b = self._endpoint(b)
        if net_a is None or net_a != net_b:
            return False
        if not copper:
            return True
        from fenolite.analysis.connectivity import connectivity

        row = connectivity(self.board.design, pads=self.board.pads).net(net_a)
        if row is None or row.unsupported:
            return False
        parts = {p.ref: p for p in self.model.circuit.components}
        pads: set[str] = set()
        for where in (*pins_a, *pins_b):
            ref, _, pin = where.rpartition("-")
            pads.update(f"{ref}-{pad}" for pad in parts[ref].pads_of(pin))
        return bool(pads) and any(pads <= set(island) for island in row.pads)

    def findings(
        self, pattern: str = "*", *, stages: tuple[str, ...] | None = None, severity: str | None = None
    ) -> Findings:
        import fnmatch

        from fenolite.checks.stages import ORACLE_STAGES, STAGE_ORDER
        from fenolite.checks.subjects import Subject
        from fenolite.testing.findings import Finding, Findings

        self._open()
        selected = (
            tuple(s for s in STAGE_ORDER if s not in ORACLE_STAGES) if stages is None else tuple(stages)
        )
        for stage in selected:
            if stage in ORACLE_STAGES:
                raise TestingError(f"{stage} needs kicad-cli; run fenolite check instead")
            if stage not in STAGE_ORDER:
                raise TestingError(f"unknown check stage {stage!r}")
        if not selected:
            raise TestingError("select at least one tool-free check stage")
        if severity not in (None, "error", "warning", "info"):
            raise TestingError(f"unknown severity {severity!r}")
        with using_state(self._private / "state"):
            reply = api.run("check", str(self.path), "--stages", ",".join(selected))
        if reply.exit_code not in (0, 5):
            checked(reply)
        envelope = reply.envelope or {}
        subjects = {
            row["issue"]: tuple(Subject(**s) for s in row["items"])
            for row in reply.result.get("subjects", ())
        }
        items = [
            Finding(i["code"], i["severity"], i["message"], i.get("where", ""), subjects.get(k, ()))
            for k, i in enumerate(envelope.get("issues", ()))
        ]
        unattached = [i for i in self._build_issues if i["code"] == "build.unattached"]
        items += [Finding(i["code"], i["severity"], i["message"], i.get("where", "")) for i in unattached]
        evidence = evidence_of(envelope.get("evidence", {}))
        if unattached:
            evidence = Evidence.combine(evidence, self.evidence)
        return Findings(
            (
                f
                for f in items
                if fnmatch.fnmatchcase(f.code, pattern) and (severity is None or f.severity == severity)
            ),
            evidence,
        )

    def close(self) -> None:
        self._finalizer()


def instantiate(block: object, /, **params: object) -> TestDesign:
    """Build the c0251 block ``block`` alone, used once as ``dut`` with ``params``, as ``load`` builds a
    script: a throwaway script in the temporary folder makes the design on a square board, so its ports are
    the nets ``dut/<port>`` and its parts the refs ``dut/<name>``. No file is written outside that folder."""
    import inspect

    from fenolite.dsl.block import BlockDef

    if not isinstance(block, BlockDef):
        raise TestingError(f"instantiate takes a @block function, not {block!r}")
    private = Path(tempfile.mkdtemp(prefix="fenolite-test-"))
    try:
        folder = private / "bench"
        folder.mkdir()
        key = private.name
        script = folder / "design.py"
        text = BENCH.format(key=key, name=f"{block.name}_bench", side=BENCH_BOARD_MM, instance=INSTANCE)
        script.write_text(text, encoding="utf-8")
        source = inspect.getsourcefile(block.function)
        # the project devices beside the block's file, or beside its package (a script folder's devices/)
        places = (Path(source).parent, Path(source).parent.parent) if source else ()
        devices = next((place / "devices" for place in places if (place / "devices").is_dir()), None)
        if devices is not None:
            shutil.copytree(devices, folder / "devices")
        _PENDING[key] = (block, dict(params))
        try:
            return _load(script, private, private / "build", seed=0, timestamp=DEFAULT_TIMESTAMP)
        finally:
            del _PENDING[key]
    except BaseException:
        shutil.rmtree(private, ignore_errors=True)
        raise


def load(
    path: str | Path,
    *,
    seed: int = 0,
    timestamp: str = DEFAULT_TIMESTAMP,
    kicad_version: int | None = None,
    workdir: str | Path | None = None,
) -> TestDesign:
    """Build through dry-run/confirm replay; never remove a caller-provided workdir."""
    source = Path(path).resolve()
    private = Path(tempfile.mkdtemp(prefix="fenolite-test-"))
    out = private / "build" if workdir is None else Path(workdir).resolve()
    try:
        return _load(source, private, out, seed=seed, timestamp=timestamp, kicad_version=kicad_version)
    except BaseException:
        shutil.rmtree(private, ignore_errors=True)
        raise


def _load(
    source: Path, private: Path, out: Path, *, seed: int, timestamp: str, kicad_version: int | None = None
) -> TestDesign:
    """The dry-run/confirm build of ``source`` into ``out``, with its state under ``private``."""
    args = [str(source), "--out", str(out)]
    if kicad_version is not None:
        args += ["--kicad-version", str(kicad_version)]
    with using_state(private / "state"):
        planned = checked(api.run("build", *args, "--dry-run", seed=seed, timestamp=timestamp))
        written = checked(
            api.run(
                "build",
                *args,
                "--confirm",
                "--plan",
                str(planned.result["plan_id"]),
                seed=seed,
                timestamp=timestamp,
            )
        )
    devices = source.parent / "devices"
    if out.parent == private and devices.is_dir() and not (private / "devices").exists():
        # fenolite check reads the device records from devices/ of the build's parent, as for a build
        # beside its script: the private build gets a copy, so circuit findings judge the same records
        shutil.copytree(devices, private / "devices")
    return TestDesign(out, private, written)
