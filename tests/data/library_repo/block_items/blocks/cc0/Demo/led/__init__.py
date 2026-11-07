# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite: a synthetic library block, not a validated indicator circuit.
"""A minimal two-terminal block for library-item and upgrade tests."""

from fenolite.dsl import Net, block, connect, param

__all__ = ["led"]


@block(
    id="Demo:led",
    version="1.0.0",
    summary="Authored two-terminal test block",
    category="indicator",
    licence="CC0-1.0",
    sources=("authored for Fenolite",),
)
def led(b, *, resistance=param("1k", doc="synthetic resistor value")):
    positive = b.port("POS", Net, direction="in", doc="positive terminal")
    negative = b.port("NEG", Net, direction="in", doc="negative terminal")
    resistor = b.part("R", "Mini:Mini_R", footprint="Mini:Mini_R_0603", prefix="R", value=resistance)
    connect(positive, resistor[1])
    connect(negative, resistor[2])
