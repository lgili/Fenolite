# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Panel scripts: several copies of one built board (capability design-dsl, "Panel scripts" and "Panel fit
rule"; change c0173).

A panel script binds ``panel`` at module level::

    from fenolite.dsl import Panel, mm

    panel = Panel("blink_panel", board="../blink/out/blink.kicad_pcb")
    panel.grid(2, 4)
    panel.rails(top=mm(5), bottom=mm(5))
    panel.separate("vscore", between="rows")
    panel.separate("tabs", between="columns")
    panel.fiducials()
    panel.tooling_holes()

``board`` names a built board file relative to the script: a ``.kicad_pcb`` (any target) or a ``.PcbDoc``
(``--target altium`` only). Coordinates are panel-relative: the origin is the panel's top-left corner and Y
points down, as ``board()`` of a design script. Every bad value raises ``DslError`` at the call, naming the
argument, and records nothing. Lengths are ``Length`` values (``mm()``) or strings with a unit; angles are
quarter turns in degrees.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import PurePosixPath, PureWindowsPath

from fenolite.core.coords import Point
from fenolite.core.ids import derived_id
from fenolite.core.trig import QUARTER_TURN
from fenolite.dsl.errors import DslError
from fenolite.dsl.units import as_nm, as_udeg, mm
from fenolite.model.panel import (
    BETWEEN,
    DEFAULT_GAP,
    METHODS,
    FiducialSet,
    PanelArray,
    PanelFiducial,
    PanelFit,
    PanelFrame,
    PanelHole,
    PanelLimits,
    PanelSource,
    Separation,
    TabSpec,
    ToolingSet,
    VScoreSpec,
)
from fenolite.model.panel import Panel as ModelPanel

BOARD_SUFFIXES = {".kicad_pcb": "kicad", ".pcbdoc": "altium"}
"""The board files a panel names, by suffix (case-insensitive for ``.PcbDoc``)."""
REF_CHARS = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789_-")
COUNT_LIMITS = frozenset({"tab_holes", "fiducial_count"})


def _length(call: str, name: str, value: object, *, positive: bool = True, zero: bool = False) -> int:
    nm = as_nm(value, name=f"{call}: {name}")
    if nm < 0 or (nm == 0 and not zero):
        raise DslError(
            f"{call}: {name} must be {'at least 0' if zero else 'a positive length'}, got {value!r}"
        )
    return nm


def _quarter(call: str, value: object) -> int:
    if isinstance(value, bool):
        raise DslError(f"{call}: rot must be 0, 90, 180 or 270 degrees, not {value!r}")
    udeg = as_udeg(value, name=f"{call}: rot")
    if udeg % QUARTER_TURN:
        raise DslError(f"{call}: rot must be 0, 90, 180 or 270 degrees, not {value!r}")
    return udeg


def _ref(call: str, ref: object) -> str:
    if not isinstance(ref, str) or not ref or not set(ref) <= REF_CHARS:
        raise DslError(f"{call}: ref must be a name of letters, digits, '_' and '-', not {ref!r}")
    return ref


class Panel:
    """A panel of copies of the built board ``board`` (a path relative to the script)."""

    def __init__(self, name: str, *, board: str, limits: dict[str, object] | None = None) -> None:
        if not isinstance(name, str) or not name or not set(name) <= REF_CHARS:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"Panel(): name must be a name of letters, digits, '_' and '-', not {name!r}")
        if not isinstance(board, str) or not board:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"Panel(): board must name a built board file, not {board!r}")
        suffix = PurePosixPath(board.replace("\\", "/")).suffix.lower()
        if suffix not in BOARD_SUFFIXES:
            raise DslError(f"Panel(): board must be a .kicad_pcb or a .PcbDoc, not {board!r}")
        if PurePosixPath(board).is_absolute() or PureWindowsPath(board).is_absolute():
            raise DslError(f"Panel(): board must be relative to the script, not the absolute {board!r}")
        self.name = name
        self.board = board.replace("\\", "/")
        self.backend = BOARD_SUFFIXES[suffix]
        self.limits = self._limits(limits or {})
        self.array = PanelArray()
        self.fit_spec: PanelFit | None = None
        self.frame = PanelFrame()
        self.separations: dict[str, str] = {}
        self.tab_spec = TabSpec()
        self.vscore_spec = VScoreSpec()
        self.fiducial_list: list[PanelFiducial] = []
        self.hole_list: list[PanelHole] = []
        self.fiducial_set: FiducialSet | None = None
        self.tooling_set: ToolingSet | None = None
        self._gap_given = False
        self._arranged = False

    @staticmethod
    def _limits(given: dict[str, object]) -> PanelLimits:
        names = {f for f in PanelLimits.__dataclass_fields__}
        values: dict[str, int] = {}
        for key, value in given.items():
            if key not in names:
                raise DslError(f"Panel(): limits has no limit {key!r} (limits: {', '.join(sorted(names))})")
            if key in COUNT_LIMITS:
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise DslError(f"Panel(): limits[{key!r}] must be a count of at least 0, not {value!r}")
                values[key] = value
            else:
                values[key] = _length("Panel()", f"limits[{key!r}]", value, zero=True)
        return PanelLimits(**values)

    # --- the arrangement ------------------------------------------------------------------------------

    def _gaps(self, call: str, gap: object, gap_x: object, gap_y: object) -> tuple[int, int, bool]:
        if gap is not None and (gap_x is not None or gap_y is not None):
            raise DslError(f"{call}: give gap, or gap_x and gap_y, not both")
        base = DEFAULT_GAP if gap is None else _length(call, "gap", gap)
        gx = base if gap_x is None else _length(call, "gap_x", gap_x)
        gy = base if gap_y is None else _length(call, "gap_y", gap_y)
        return gx, gy, gap is not None or gap_x is not None or gap_y is not None

    def _once(self, call: str) -> None:
        if self._arranged:
            raise DslError(f"{call}: the copies are arranged once, by grid() or fit()")

    def grid(
        self,
        rows: int,
        cols: int,
        *,
        gap: object = None,
        gap_x: object = None,
        gap_y: object = None,
        rot: int | str = 0,
        mirror: bool = False,
    ) -> None:
        """``rows`` × ``cols`` copies, ``gap`` (2 mm by default) between tabbed copies, or ``gap_x`` between
        columns and ``gap_y`` between rows; each copy turned by ``rot`` (0, 90, 180 or 270 degrees).
        ``mirror`` is Altium's Mirrored property of an Embedded Board Array, refused by every other form."""
        call = "grid()"
        self._once(call)
        for name, value in (("rows", rows), ("cols", cols)):
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:  # pyright: ignore[reportUnnecessaryIsInstance]
                raise DslError(f"{call}: {name} must be a whole number of at least 1, not {value!r}")
        gx, gy, given = self._gaps(call, gap, gap_x, gap_y)
        rotation = _quarter(call, rot)
        if not isinstance(mirror, bool):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"{call}: mirror must be a bool, not {mirror!r}")
        self.array = PanelArray(rows, cols, gx, gy, rotation, mirror)
        self._gap_given = given
        self._arranged = True

    def fit(self, width: object, height: object, *, gap: object = None, rot: int | str = 0) -> None:
        """As many copies as ``width`` × ``height`` holds with the rails and gaps: ``cols = ⌊(U + g) / (b +
        g)⌋``, ``U`` the width inside the rails and their gaps, ``b`` the board's width after the turn, ``g``
        the gap; rows likewise. ``rot="auto"`` takes the quarter turn that holds more, 0° on a tie. The panel
        has the size of what it holds; the reply's ``unused`` gives the rest."""
        call = "fit()"
        self._once(call)
        w = _length(call, "width", width)
        h = _length(call, "height", height)
        gx, gy, given = self._gaps(call, gap, None, None)
        auto = rot == "auto"
        rotation = 0 if auto else _quarter(call, rot)
        self.array = PanelArray(1, 1, gx, gy, rotation)
        self.fit_spec = PanelFit(w, h, auto)
        self._gap_given = given
        self._arranged = True

    def rails(
        self, *, top: object = None, bottom: object = None, left: object = 0, right: object = 0
    ) -> None:
        """Rails of these widths (``0`` for none); ``top`` and ``bottom`` are 5 mm by default (S-0798)."""
        call = "rails()"
        values: list[int] = []
        for name, value in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
            if value is None:
                value = mm(5)
            values.append(0 if value == 0 else _length(call, name, value, zero=True))
        self.frame = PanelFrame(*values)

    def separate(self, method: str, *, between: str) -> None:
        """Separate the edge set ``between`` (``columns``, ``rows`` or ``rails``) by ``method``: ``vscore``
        (the boards touch, one straight score line per boundary) or ``tabs`` (a routed gap held by tabs
        with mouse bites). An edge set left unnamed is tabbed."""
        call = "separate()"
        if method not in METHODS:
            raise DslError(f"{call}: method must be one of {', '.join(METHODS)}, not {method!r}")
        if between not in BETWEEN:
            raise DslError(f"{call}: between must be one of {', '.join(BETWEEN)}, not {between!r}")
        if between in self.separations:
            raise DslError(f"{call}: the edge set {between!r} is already separated")
        self.separations[between] = method

    def tabs(
        self,
        *,
        width: object = None,
        pitch: object = None,
        drill: object = None,
        hole_gap: object = None,
        holes: int = 5,
        inset: object = 0,
    ) -> None:
        """The tabs of routed edges: ``width`` wide (5 mm), one per ``pitch`` of edge length (55 mm), each
        with a row of ``holes`` holes of ``drill`` (0.6 mm) at each board edge, ``hole_gap`` (0.4 mm) from
        hole edge to hole edge, tangent to the edge outside the board, or reaching ``inset`` into it (at
        most a third of the drill)."""
        call = "tabs()"
        default = TabSpec()
        w = default.width if width is None else _length(call, "width", width)
        p = default.pitch if pitch is None else _length(call, "pitch", pitch)
        d = default.drill if drill is None else _length(call, "drill", drill)
        g = default.hole_gap if hole_gap is None else _length(call, "hole_gap", hole_gap, zero=True)
        if isinstance(holes, bool) or not isinstance(holes, int) or holes < 0:  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"{call}: holes must be a whole number of at least 0, not {holes!r}")
        i = 0 if inset == 0 else _length(call, "inset", inset, zero=True)
        if 3 * i > d:
            raise DslError(f"{call}: inset must be at most a third of the drill, not {inset!r}")
        if holes and holes * d + (holes - 1) * g > w:
            raise DslError(f"{call}: width {w} nm cannot hold a row of {holes} holes of {d} nm")
        self.tab_spec = TabSpec(w, p, d, g, holes, i)

    def vscore(self, *, clearance: object = None, layer: str = "V-Score", line_width: object = None) -> None:
        """The score lines: on the layer named ``layer``, drawn ``line_width`` wide (0.1 mm); copper is kept
        ``clearance`` (0.45 mm, S-0799) from them."""
        call = "vscore()"
        c = VScoreSpec().clearance if clearance is None else _length(call, "clearance", clearance, zero=True)
        lw = VScoreSpec().line_width if line_width is None else _length(call, "line_width", line_width)
        if not isinstance(layer, str) or not layer or not layer.isprintable():  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"{call}: layer must be a printable name, not {layer!r}")
        self.vscore_spec = VScoreSpec(layer, lw, c)

    def _side(self, call: str, side: object) -> str:
        if side not in ("top", "bottom"):
            raise DslError(f"{call}: side must be 'top' or 'bottom', not {side!r}")
        return str(side)

    def _taken(self, call: str, ref: str) -> None:
        if any(item.ref == ref for item in (*self.fiducial_list, *self.hole_list)):
            raise DslError(f"{call}: ref {ref!r} is taken")

    def fiducial(
        self, ref: str, x: object, y: object, *, copper: object = None, mask: object = None, side: str = "top"
    ) -> None:
        """A fiducial ``ref`` at ``(x, y)``: copper ``copper`` wide (1 mm) in a mask opening ``mask`` wide (2
        mm), on ``side`` (S-0797)."""
        call = "fiducial()"
        name = _ref(call, ref)
        self._taken(call, name)
        at = Point(as_nm(x, name=f"{call}: x"), as_nm(y, name=f"{call}: y"))
        c = mm(1).nm if copper is None else _length(call, "copper", copper)
        m = mm(2).nm if mask is None else _length(call, "mask", mask)
        if m <= c:
            raise DslError(f"{call}: mask must be above copper, not {mask!r}")
        self.fiducial_list.append(PanelFiducial(name, at, self._side(call, side), c, m))  # pyright: ignore[reportArgumentType]

    def fiducials(
        self, *, copper: object = None, mask: object = None, sides: tuple[str, ...] = ("top",)
    ) -> None:
        """Three fiducials in an L on the rails per side of ``sides``, named ``PFID<n>``: copper ``copper``
        wide (1 mm) in a mask opening ``mask`` wide (2 mm)."""
        call = "fiducials()"
        c = mm(1).nm if copper is None else _length(call, "copper", copper)
        m = mm(2).nm if mask is None else _length(call, "mask", mask)
        if m <= c:
            raise DslError(f"{call}: mask must be above copper, not {mask!r}")
        if not isinstance(sides, tuple) or not sides or len(set(sides)) != len(sides):  # pyright: ignore[reportUnnecessaryIsInstance]
            raise DslError(f"{call}: sides must be a tuple of 'top' and/or 'bottom', not {sides!r}")
        chosen = tuple(self._side(call, side) for side in sides)
        self.fiducial_set = FiducialSet(c, m, chosen)  # pyright: ignore[reportArgumentType]

    def tooling_hole(self, ref: str, x: object, y: object, *, drill: object = None) -> None:
        """A non-plated tooling hole ``ref`` of ``drill`` (3 mm, S-0800) at ``(x, y)``."""
        call = "tooling_hole()"
        name = _ref(call, ref)
        self._taken(call, name)
        at = Point(as_nm(x, name=f"{call}: x"), as_nm(y, name=f"{call}: y"))
        d = mm(3).nm if drill is None else _length(call, "drill", drill)
        self.hole_list.append(PanelHole(name, at, d))

    def tooling_holes(self, *, drill: object = None) -> None:
        """Four non-plated tooling holes of ``drill`` (3 mm) at the corners of the rails, named
        ``PTH<n>``."""
        call = "tooling_holes()"
        self.tooling_set = ToolingSet(mm(3).nm if drill is None else _length(call, "drill", drill))

    # --- the model ------------------------------------------------------------------------------------

    def to_model(self, *, sha256: str = "") -> ModelPanel:
        """The model panel of this script; ``sha256`` is the digest of the board file when it was read."""
        separations = tuple(Separation(b, self.separations[b]) for b in BETWEEN if b in self.separations)  # pyright: ignore[reportArgumentType]
        return ModelPanel(
            id=derived_id(
                "pnl", "panel", "panel"
            ),  # fenolite.panel.ids.panel_id(); dsl does not import panel
            name=self.name,
            source=PanelSource(self.board, sha256, self.backend),  # pyright: ignore[reportArgumentType]
            array=self.array,
            fit=self.fit_spec,
            frame=self.frame,
            separations=separations,
            tabs=self.tab_spec,
            vscore=self.vscore_spec,
            fiducials=tuple(self.fiducial_list),
            tooling_holes=tuple(self.hole_list),
            fiducial_set=self.fiducial_set,
            tooling_set=self.tooling_set,
            limits=self.limits,
        )


def with_source(panel: ModelPanel, sha256: str) -> ModelPanel:
    """``panel`` with the digest of its board file."""
    return replace(panel, source=replace(panel.source, sha256=sha256))


__all__ = ["BOARD_SUFFIXES", "Panel", "with_source"]
