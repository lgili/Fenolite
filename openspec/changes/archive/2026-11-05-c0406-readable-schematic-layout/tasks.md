## 1. Evidence and drafting rules

- [x] 1.1 `docs/schematic-drafting.md`: the drafting rules the wired layout follows, each with its public
  source (new rows in `docs/evidence/sources.md`), and the Fenolite choices kept apart from them. Proof:
  `uv run pytest tests/unit/test_docs_sources.py -q` (or the docs residue scan of `make check-fast`).
- [x] 1.2 `docs/formats/kicad/schematic.md`: power symbol named by its Value with a generic hidden pin
  name, coincident pin ends join, measured on 10.0.6 and the pinned 9.0.9 image (2026-11-05). Proof: the
  oracle test of 5.2.

## 2. Power symbols and net roles

- [x] 2.1 `symembed.power_symbol(kind, target, library)` (`GND`, `RAIL`), authored. Proof:
  `uv run pytest tests/unit/backends/kicad/test_symembed_power.py -q`.
- [x] 2.2 Net roles: `schwired.name_role` and `schwired.net_role` (supply: ground, negative, rail; signal),
  with interface kinds, power pins and bus members gathered by `schgen` from the design.
  Proof: `uv run pytest tests/unit/backends/kicad/test_schwired.py -k roles -q`.

## 3. Wired layout

- [x] 3.1 Clusters: ranked anchors, attachment of two-pin parts to nodes, bridges, chains, columns and
  rows, decoupling row, slots with text rooms, power symbols of anchor pins. Proof: `test_schwired.py -k cluster`.
- [x] 3.2 Placement of clusters by signal flow, followers beside their neighbour, column wrap, alignment
  and the paper. Proof: `test_schwired.py -k flow`.
- [x] 3.3 Router: grid, obstacles, A* joins to a Steiner tree, junctions, wire cuts, per-cluster drawing.
  Proof: `test_schwired.py -k route`.
- [x] 3.4 Net-name labels and field poses. Proof: `test_schwired.py -k labels`.
- [x] 3.5 `schgen`: `layout="wired"`, power symbols and flags, fallbacks, `GeneratedSchematic`
  `power_symbols` and `fallbacks`; `build` and the CLI default to `"wired"`. Proof:
  `uv run pytest tests/unit/backends/kicad/test_schgen.py tests/unit/lens/test_build_schematic.py -q -n 2`.

## 4. Own netlist and measures

- [x] 4.1 `sch_netlist`: junctions, wire chains, crossings, labels on wires, Fenolite power symbols.
  Proof: `uv run pytest tests/unit/backends/kicad/test_sch_netlist.py -q`.
- [x] 4.2 `fenolite.backends.kicad.schreadability.measure_sheet`. Proof:
  `uv run pytest tests/unit/backends/kicad/test_schreadability.py -q`.

## 5. Authored designs, oracles and renders

- [x] 5.1 `tests/_wireddesigns.py`: authored designs (op-amp stage, MCU with crystal, reset and LED, linear
  regulator with input and output, transistor switch, two-module design). Measures and generated designs.
  Proof: `uv run pytest tests/unit/backends/kicad/test_schwired.py -q`.
- [x] 5.2 `tests/kicad/schematic/test_wired_oracle.py`: ERC and netlist of the built designs on the local
  10.0.6. Proof: `uv run pytest tests/kicad/schematic/test_wired_oracle.py -q`.
- [x] 5.3 Before/after renders (`kicad-cli sch export svg`, 10.0.6) under `docs/renders/c0406/`, with a
  README giving the measures. Proof: files present.

## 6. Ripple and closure

- [x] 6.1 Tests that assumed the build's default layout name it or follow the wired sheet; `tests/data/build_bytes.json`
  measured again. Proof: `uv run pytest tests/unit/test_build_bytes.py -q -n 2`.
- [x] 6.2 Agent guide line for `--schematic-layout wired` and the measures; `uv run python tools/gen_agent_guide.py`.
  Proof: `uv run pytest tests/unit/agent/test_pages.py -q -n 2`.
- [x] 6.3 CHANGELOG line under `## [Unreleased]`.
- [x] 6.4 `npx -y @fission-ai/openspec validate --all --strict`; ruff check, ruff format --check, `pyright src`
  and the focused tests (the coordinator runs `make check-fast` on the integrated batch, 2026-11-05).
