# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Opt-in same-run hashes for one pinned authored fixture; no production geometry changes."""

from __future__ import annotations

import hashlib
import inspect
import json
from collections.abc import Callable, Generator, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, cast

ROOT = Path(__file__).resolve().parents[1]
SOURCE_FILES = {
    "examples/board_40parts/design.py": ("0ebcccadfbd38656de7f30921d19cd8dde55647875441fbfd0fe95bec7f1203c"),
    "examples/board_40parts/fp-lib-table": (
        "328ee0774905427ea2615cff33272e01e92f8cf0ca59999b6827472ba6f46e1d"
    ),
    "examples/board_40parts/sym-lib-table": (
        "6de7325d528a108419ac2319446929c1e940d51044dcff7c437941425b62927a"
    ),
    "tests/data/libs/Mini_v9.kicad_sym": ("1587899e7bfbd5161722d35808a8c8125e7ead77c740113028c2c84910e6fedf"),
    "tests/data/libs/Mini_v9.pretty/Mini_LED_THT_3mm.kicad_mod": (
        "c7b983f563898280b4c7a3d2647653a90e8688505e988dc9d23666748e9a7ee9"
    ),
    "tests/data/libs/Mini_v9.pretty/Mini_QFP-32_7x7mm_P0.8mm.kicad_mod": (
        "796c8dbd4386d3371970294120fe4a56e0766bb1731454ef9dbd89725cd61cf1"
    ),
    "tests/data/libs/Mini_v9.pretty/Mini_R_0603.kicad_mod": (
        "8a69fd538ee10ea412e2b5cc1c3d63f4834a12c5d1ad45443697d3f3eb65a5b5"
    ),
}
METHODS = ("union", "intersection", "difference", "offset", "stroke")
MAX_OPS = 512
MAX_VERTICES = 200_000
MAX_TRACE_BYTES = 192 * 1024
PUBLIC_CONTEXT_SHA256 = "01f92da8e31919c700f179e5324bcc5c3638a189ea9dfd55e6ea3101ef40428b"


def authored_source(source_root: Path, out: Path) -> bool:
    """Refuse edited/symlinked fixture inputs and ambient project/previous-output contexts."""
    if source_root.resolve() != ROOT or out.exists():
        return False
    try:
        for name, digest in SOURCE_FILES.items():
            path = ROOT / name
            if path.is_symlink() or not path.resolve().is_relative_to(ROOT):
                return False
            if hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                return False
        script = ROOT / "examples/board_40parts/design.py"
        for folder in (out.parent, *script.parents):
            for name in ("devices", "fenolite_library", "edits.toml", "placements.toml", "design.lock"):
                path = folder / name
                if path.exists():
                    if path != ROOT / "examples/devices":
                        return False
                    entries = sorted(path.rglob("*"), key=lambda p: p.relative_to(path).as_posix())
                    if any(p.is_symlink() for p in entries):
                        return False
                    rows = [
                        (p.relative_to(path).as_posix(), hashlib.sha256(p.read_bytes()).hexdigest())
                        for p in entries
                        if p.is_file()
                    ]
                    if (
                        hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()
                        != PUBLIC_CONTEXT_SHA256
                    ):
                        return False
            for name in ("fp-lib-table", "sym-lib-table"):
                path = folder / name
                if path.exists() and path != script.parent / name:
                    return False
    except (OSError, ValueError):
        return False
    return True


def summary(value: Any, *, paths: bool = False) -> dict[str, object]:
    """Hash canonical integer data without exposing or modifying the original operands."""
    from fenolite.geometry.polygon import Polygon, normalize_polygons
    from fenolite.geometry.vector import Point

    if paths:
        if not isinstance(value, (tuple, list)):
            raise ValueError("unsupported operand")
        rings = [tuple(ring) for ring in cast(Sequence[Sequence[Point]], value)]
        count = sum(map(len, rings))
        if count > MAX_VERTICES:
            raise ValueError("vertex limit")
        for ring in rings:
            if any(
                type(p.x) is not int or type(p.y) is not int or max(abs(p.x), abs(p.y)) > 2**31 - 1
                for p in ring
            ):
                raise ValueError("integer domain")
        ordered = [[(p.x, p.y) for p in ring] for ring in rings]
        canonical = sorted(
            min([(p.x, p.y) for p in ring], [(p.x, p.y) for p in reversed(ring)]) for ring in rings
        )
        polygons, holes = 0, 0
    else:
        given: Any = (value,) if isinstance(value, Polygon) else value
        if not isinstance(given, (tuple, list)) or any(
            not isinstance(p, Polygon) for p in cast(list[Any], given)
        ):
            raise ValueError("unsupported operand")
        polys = cast(Sequence[Polygon], given)
        count = sum(len(ring) for poly in polys for ring in poly.rings())
        if count > MAX_VERTICES:
            raise ValueError("vertex limit")
        for poly in polys:
            for ring in poly.rings():
                if any(
                    type(p.x) is not int or type(p.y) is not int or max(abs(p.x), abs(p.y)) > 2**31 - 1
                    for p in ring
                ):
                    raise ValueError("integer domain")
        normalized = normalize_polygons(polys)
        ordered = [
            {
                "outer": [(p.x, p.y) for p in poly.outer],
                "holes": [[(p.x, p.y) for p in ring] for ring in poly.holes],
            }
            for poly in polys
        ]
        canonical = [
            {
                "outer": [(p.x, p.y) for p in poly.outer],
                "holes": [[(p.x, p.y) for p in ring] for ring in poly.holes],
            }
            for poly in normalized
        ]
        polygons, holes = len(normalized), sum(len(p.holes) for p in normalized)
    encoded = json.dumps(canonical, sort_keys=True, separators=(",", ":")).encode()
    return {
        "sha256": hashlib.sha256(encoded).hexdigest(),
        "ordered_sha256": hashlib.sha256(
            json.dumps(ordered, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "polygons": polygons,
        "holes": holes,
        "vertices": count,
    }


@dataclass
class Trace:
    rows: list[dict[str, object]] = field(default_factory=lambda: list[dict[str, object]]())
    seen: int = 0
    row_bytes: int = 0
    errors: int = 0
    limited: bool = False

    def append(self, row: dict[str, object]) -> None:
        size = len(json.dumps(row, sort_keys=True, separators=(",", ":")).encode())
        if len(self.rows) >= MAX_OPS or self.row_bytes + size > MAX_TRACE_BYTES:
            self.limited = True
            return
        self.rows.append(row)
        self.row_bytes += size

    def data(self) -> dict[str, object]:
        return {
            "format": "authored-geometry-hashes-v0",
            "index_base": 0,
            "operations": self.rows,
            "seen": self.seen,
            "errors": self.errors,
            "limited": self.limited,
            "max_operations": MAX_OPS,
            "max_row_bytes": MAX_TRACE_BYTES,
        }


def _wrap(name: str, original: Callable[..., Any], trace: Trace) -> Callable[..., Any]:
    signature = inspect.signature(original)

    def observed(*args: Any, **kwargs: Any) -> Any:
        before: dict[str, object] | None = None
        if len(trace.rows) < MAX_OPS and not trace.limited:
            try:
                bound = signature.bind(*args, **kwargs)
                bound.apply_defaults()
                arguments = bound.arguments
                operands = (
                    ("subject", "cut")
                    if name == "certified-neck-cut"
                    else ("a", "b")
                    if name in ("intersection", "difference")
                    else ("paths",)
                    if name == "stroke"
                    else ("polys",)
                )
                parameters = {
                    key: arguments[key] for key in ("delta", "join", "tol", "miter_limit") if key in arguments
                }
                if any(type(v) is not int for key, v in parameters.items() if key != "join"):
                    raise ValueError("parameter domain")
                if "join" in parameters and parameters["join"] not in ("round", "miter", "square"):
                    raise ValueError("parameter domain")
                before = {
                    "method": name,
                    "inputs": [summary(arguments[key], paths=name == "stroke") for key in operands],
                    "parameters": parameters,
                }
            except Exception:
                before = None
                trace.errors += 1
        # The original method is called exactly once, outside every observer-error handler.
        result = original(*args, **kwargs)
        trace.seen += 1
        if before is not None:
            try:
                trace.append({"index": trace.seen - 1, **before, "output": summary(result)})
            except Exception:
                trace.errors += 1
        else:
            trace.limited |= len(trace.rows) >= MAX_OPS
        return result

    return observed


@contextmanager
def observe(example: str, target: str, out: Path, source_root: Path) -> Generator[Trace | None, None, None]:
    try:
        from _builddiagnostics import CASE, destination

        eligible = (
            (example, target) == CASE
            and destination(source_root) is not None
            and authored_source(source_root, out)
        )
    except Exception:
        eligible = False
    if not eligible:
        yield None
        return
    trace = Trace()
    originals: dict[str, Any] = {}
    backend: Any = None
    cut_module: Any = None
    cut_original: Any = None
    try:
        from fenolite.backends.altium import pour
        from fenolite.geometry.boolean.clipper import ClipperBackend

        backend = ClipperBackend
        for name in METHODS:
            originals[name] = getattr(backend, name)
            setattr(backend, name, _wrap(name, originals[name], trace))
        cut_module = pour
        cut_original = pour._certified_neck_cut
        pour._certified_neck_cut = _wrap("certified-neck-cut", cut_original, trace)
    except Exception:
        for name, original in originals.items():
            setattr(backend, name, original)
        if cut_original is not None:
            cut_module._certified_neck_cut = cut_original
        yield None
        return
    try:
        yield trace
    finally:
        for name, original in originals.items():
            setattr(backend, name, original)
        if cut_original is not None:
            cut_module._certified_neck_cut = cut_original
