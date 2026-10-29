## Why

Every passive of a Fenolite design is chosen by hand today: a symbol, a footprint and a value string
(`Part("R1", "Fenolite:Resistor", footprint="Fenolite:Chip_0603", value="45k3")`). Nothing records why
45.3 kΩ was chosen, nothing says what the divider achieves with real tolerances, and the next build
cannot tell whether a part still fits what the script asks for. The research of 2026-10-29
(`docs/research/circuit-as-code.md`, sections 8 and 9, core change H) found that JITX and atopile offer
parametric choice and generators, but all three tools studied resolve against a remote, changing parts
database, and atopile hides its picks inside the board file.

Fenolite can offer the same convenience while keeping its rules: the parts come from a **local,
versioned catalog**, every choice is **written to the design lock** (c0249) through plan/confirm, a pick
never changes by itself, and a generator writes **what it achieved** to the build evidence.

## What Changes

- **Queries.** `resistor(...)`, `capacitor(...)` and `inductor(...)` describe a part by value (a
  quantity, or a c0246 range), tolerance, ratings, case and dielectric. A query is accepted wherever a
  device is (`design.part(device=query)`, `b.part(name, device=query)` of c0251) and is resolved by the build, not the script.
- **Defaults.** `design.defaults(resistor={...}, ...)` and `b.defaults(...)` in a block body cascade
  design → block → call; the most specific level wins and `None` clears a key.
- **Pickable rows.** The catalog gains parametric rows: families (`fenolite.family.v0`, a case, a
  tolerance, an E-series and a value span, no MPN) and discrete device rows of c0248 that state a value.
  Fenolite ships a small set of families, every number with a public source; projects add their own.
- **Picks in the lock.** Each resolved query writes `[picks."<path>"]` to the design lock: the canonical
  query, the device, the row, its catalog version and SHA-256. A locked pick is reused as long as it still
  matches; a changed query that the locked part no longer meets is the error `pick.stale`, never a silent
  swap.
- **`fenolite pick PATH`** lists picks and their state, shows ranked candidates (`--candidates`), and
  re-resolves picks with `--update PATH...` through `--dry-run` / `--confirm --plan`.
- **Supplier proposals.** `fenolite pick --propose` turns rows from a file, or from a supplier plugin
  under `--allow-offsite`, into `UNVERIFIED` rows under `devices/proposed/`. It never writes the lock; the core opens
  no network connection.
- **Generators** over the same catalog, deterministic and exact: `voltage_divider` first (E-series pick,
  the achieved output range recorded), then `rc_lowpass`, `led_resistor`, `i2c_pull_ups` and `shunt`.

## Capabilities

### New Capabilities

- `part-selection`: query matching and ranking, the defaults cascade, pickable rows and series values,
  picks in the lock, resolution in a build, supplier proposals, the generators and their codes.

### Modified Capabilities

- `design-dsl`: ADDED "Part queries in the DSL", "Pins of query parts", "Query arguments", "Defaults in the DSL",
  "Generators in the DSL", "Generator arguments".
- `cli-contract`: ADDED "Pick command", "Pick listing", "Pick updates".
- `fenolite-component-catalog`: ADDED "Parametric families in the shipped catalog", "Catalog data
  version".
- `package-layering`: MODIFIED "Allowed import edges" (new package `pick` → `model`, `catalog`).

## Dependencies

c0246 (ranges: tolerances, targets, worst-case arithmetic), c0248 (device records a pick resolves to),
c0249 (the design lock, `--frozen`), c0251 (block paths and `b.defaults`). Used by c0247 (`decouple`,
`pull_up` take a query), c0252 (a `Rail`'s voltage feeds a divider), c0253 (ratings of picked parts are
checked with derating) and c0256 (tests assert achieved ranges). Implementation step 6, with c0255.

## Non-goals

- No live parts database, no network in the core, no supplier plugin shipped, no prices or stock.
- No general constraint solver; generators are closed formulas with a bounded search.
- No MPN choice by Fenolite: a family pick is generic; an MPN comes only from a row the user reviewed.
- No variants (alternate BOMs) in this change.

## Evidence level required

- Matching, ranking, lock round trip and generator arithmetic: `INFERRED`, proven by unit tests over
  authored catalogs (no tool can judge them).
- Shipped family attributes: the label of their source (`INFERRED` at best for typical values).
- A built board with picked parts: `KICAD-VERIFIED` read-back of value and footprint, as any build.

## Impact

- New: `src/fenolite/pick/` (`query.py`, `rows.py`, `series.py`, `match.py`, `lockpicks.py`,
  `resolve.py`, `propose.py`, `generators/{divider,rc,led,pullup,shunt}.py`, `codes.py`),
  `src/fenolite/dsl/query.py`, `src/fenolite/cli/cmd_pick.py`, `src/fenolite/catalog/families/*.toml`,
  `examples/picks/`, `docs/picking.md`.
- Changed: `dsl/design.py` (`defaults`, `part(query)`), `cli/cmd_build.py`, the import-graph test,
  `explain.toml`, `docs/dsl.md`, `docs/cli-contract.md`, guide pages `parts` and `design-script`.
- Sources: E-series values, the I2C pull-up window and chip-resistor ratings, registered at task 0.1.
- Size: about 12 design-days.
