## Why

`fenolite equivalent A B` compares components, the netlist, footprints with their pads, and placement (levels 1 to 4, c0045). It does not look at copper. Two boards with the same parts in the same places are reported equivalent when one is routed and the other is not, or when a conversion dropped every via.

The roadmap puts level 5, "routing (tracks and vias per net)", in v0.4, because the write side needs it: a KiCad board whose copper was written into an Altium document (c0038, c0053), and an imported Altium board written back (c0090), are judged by it. It is also the level the conversion of v0.5a will be measured with.

## What Changes

- **Level 5** of `equivalent`: for each net, the same pads are joined by copper on both sides, by the same number of vias per layer pair, with a routed length per layer that is equal within a tolerance.
- **A connectivity reading of copper** (`checks/equivalence/routing.py`): tracks, arcs, vias and filled zones of one net are grouped into connected pieces by exact geometry, and each piece is described by the pads it touches.
- **Differences are located**: a net whose pads are joined differently, a net with another via count, a net whose length differs, copper on a net that the other side lacks.
- **`--level 5`** on the command, the default level when both sides hold copper, and the triangle oracle of c0045 extended to it.

Size: 4.25 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `design-equivalence`: ADDED "Routed connectivity of a net", "Level 5 compares routing per net", "Level 5 in the equivalent command", "Level 5 over the triangle"; these supersede the level bound of "Equivalent command" and of "Equivalence documentation".

## Non-goals

- No comparison of the path a track takes: two routes of one connection with the same layers and length are equal at this level. Exact geometry is level 7 (v0.6).
- No comparison of track widths against rules (level 6) and no impedance or length matching (analyses, v0.6).
- No judgement of unfilled zones: a zone without fill is not copper, and the level says how many it left out.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- The level's code is `INFERRED` under `H-G-EQ-L5`; it is general, with no format fact.
- Over the triangle (a KiCad board, the Altium document written from it, and KiCad's import of that document) the level holds on the samples and on the corpus boards of c0045's list: `ORACLE-VERIFIED(kicad-cli 10.0.x)` for `H-G-EQ-L5-TRIANGLE` on those boards.

## Open decision for the maintainer

- **Question.** How strict is level 5: the same connectivity per net with length within a tolerance, or the same segments within a tolerance?
- **Default written here.** Connectivity per net, via counts per layer pair, and length per layer within a tolerance. Exact geometry stays level 7.
- **Alternative.** Segment-by-segment equality (each track, arc and via matched within the length tolerance).
- **To switch.** Add the requirement "Level 5 strict mode" (option `--routing exact`, which matches copper items one to one with `checks.diff` inside the level) and one task; the default and the other requirements stay. The helper that RT-A2 uses for item comparison already exists.

## Impact

- New: `checks/equivalence/routing.py`; changed `checks/equivalence/{levels,codes,report}.py`, `cli/cmd_equivalent.py`.
- Pages: `docs/equivalence.md`, `docs/cli-contract.md` ("equivalent"), `docs/evidence/equivalence-triangle.md`, the roadmap's level table.
- `max_level` returns 5 when both sides hold copper; the default level of the command follows it, so a run without `--level` can report new differences.
- Depends on: c0045 (levels 1 to 4), c0029 (exact copper geometry). Nothing of v0.4; c0090 and c0092 use it.
