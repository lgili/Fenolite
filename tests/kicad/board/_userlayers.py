# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Authored user-layer and undeclared-layer probes (c0161 task 1.2)."""

from __future__ import annotations


def board(count: int = 45, *, undeclared: bool = False) -> bytes:
    rows = "\n".join(f'({37 + 2 * n} "User.{n}" user)' for n in range(1, count + 1))
    lines = "\n".join(
        f'(gr_line (start 1 {n}) (end 2 {n}) (stroke (width 0.1) (type default)) (layer "User.{n}"))'
        for n in range(1, count + 1)
    )
    if undeclared:
        lines += '\n(gr_line (start 3 3) (end 4 3) (stroke (width 0.1) (type default)) (layer "Alien.Layer"))'
    return f"""(kicad_pcb (version 20241229) (generator "fenolite-tests")
      (general (thickness 1.6)) (paper "A4")
      (layers (0 "F.Cu" signal) (2 "B.Cu" signal) (25 "Edge.Cuts" user) {rows})
      (setup (pad_to_mask_clearance 0))
      (gr_rect (start 0 0) (end 10 50) (stroke (width 0.05) (type default)) (fill none) (layer "Edge.Cuts"))
      {lines})""".encode()


def probe() -> str:
    from _probes import runner

    for n in (1, 45):
        run = runner().run(
            ["pcb", "export", "svg", "-l", f"User.{n}", "--mode-single", "-o", "out.svg", "probe.kicad_pcb"],
            files={"probe.kicad_pcb": board()},
        )
        if not run.ok or "out.svg" not in run.outputs:
            return "not-equal"
    return "equal"
