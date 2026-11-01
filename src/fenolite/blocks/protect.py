# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""TVS plus series resistor with explicit working and clamp limits; S-1120, S-1125."""

from typing import Any

from fenolite.dsl import (
    REQUIRED,
    DslError,
    Ground,
    Net,
    at_least,
    at_most,
    between,
    block,
    connect,
    ohm,
    param,
    rating_of,
    resistor,
    schematic_group,
    value_of,
    volt,
)
from fenolite.dsl.block import Block


@block(
    id="Fenolite:protected_input",
    version="1.0.0",
    summary="Protected input with explicit clamp and downstream limits",
    category="protection",
    sources=("S-1120", "S-1124", "S-1125"),
)
def protected_input(
    b: Block,
    *,
    signal: Any = param(
        between(volt(0), volt(5)), doc="External signal in normal operation", unit="volt", min=volt(0)
    ),
    protection: str = param(
        REQUIRED, doc="Protection device id; its operating voltage is the stand-off limit"
    ),
    clamp: Any = param(
        REQUIRED, unit="volt", min=volt(0), doc="Clamping range at the surge being designed for"
    ),
    r_series: Any = param(
        ohm("1k"), doc="Series resistance, selected from the 0603 E96 1 % family", unit="ohm", min=ohm(10)
    ),
    abs_max: Any = param(REQUIRED, unit="volt", min=volt(0), doc="Downstream absolute maximum voltage"),
    inject_max: Any = param(None, doc="Downstream clamp current limit; requires hold"),
    hold: Any = param(None, doc="Voltage held by downstream clamps; requires inject_max"),
) -> None:
    ext = b.port("EXT", Net, direction="in", doc="Connector side; protection is placed at this edge")
    inner = b.port("INT", Net, direction="out", doc="Toward the protected input")
    gnd = b.port("GND", Ground, direction="in", doc="Short protection return")
    b.layout(reuse="layouts/protected_input.toml", copper=True)
    if not isinstance(protection, str) or not protection:  # pyright: ignore[reportUnnecessaryIsInstance]
        raise DslError("protected_input: protection is a device id")
    if (inject_max is None) != (hold is None):
        raise DslError("protected_input: give inject_max and hold together")
    tvs = b.part("tvs", device=protection)
    r = b.part("r", device=resistor(r_series, case="0603", series="E96"))
    assert tvs.device is not None
    connect(ext, *(tvs[number] for number in tvs.device.pin("K").pins), r[1])
    connect(gnd, *(tvs[number] for number in tvs.device.pin("A").pins))
    connect(inner, r[2])
    b.expect(
        at_least(rating_of(tvs, "voltage", limit="operating"), signal),
        "protection working voltage covers the signal",
    )
    if inject_max is None:
        b.expect(at_most(clamp, abs_max), "clamp below the downstream maximum")
    else:
        b.expect(
            at_least(inject_max, (clamp - hold) / value_of(r)), "current into the downstream clamps limited"
        )
        b.expect(at_most(hold, abs_max), "downstream held voltage below absolute maximum")
    b.schematic(schematic_group("protection", tvs, r, title="Protected input"))


__all__ = ["protected_input"]
