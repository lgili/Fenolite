## Why

c0268 to c0271 give a block a record, a schematic, tests and a layout, but Fenolite ships no block. A user
still writes a divider, a filter or an LED resistor by hand, and every agent re-derives the same arithmetic.
Section 3.6 of `docs/research/circuit-blocks.md` (2026-10-29) proposes five small starter blocks that prove
the whole chain and are useful on their own. The libraries compared in section 1 ship mostly IC drivers and a
few generic blocks, and none ships requirements that are judged on every build.

## What Changes

- **`fenolite.blocks`**, a package of the core (standard library only, Apache-2.0, versioned with Fenolite),
  with five blocks, each `1.0.0`, authored for Fenolite:

  | block | ports | judged on every build (`expect`) |
  |---|---|---|
  | `Fenolite:voltage_divider` | HI, OUT, LO | output within its range over tolerances; resistor power within rating |
  | `Fenolite:rc_lowpass` | IN, OUT, GND | cut-off within its range, with π enclosed; capacitor voltage rating |
  | `Fenolite:led_indicator` | HI, LO | LED current within the requested window and the LED's rating; source limit; resistor power |
  | `Fenolite:i2c_pullups` | BUS, RAIL | each pull-up between the bus minimum and maximum of its mode |
  | `Fenolite:protected_input` | EXT, INT, GND | protection rating covers the signal; clamp below the downstream maximum, or injected current limited |

- Each block wraps a c0254 generator (or picks a part by query), states its parameters with c0268's
  metadata (unit, range, choices, documentation), and ships c0270's usage example, tests and golden file,
  and c0271's layout, captured from its usage board.
- **Exact arithmetic.** Every expectation is c0253 range arithmetic on exact fractions; π is c0254's
  rational enclosure. Worked numbers are scenarios (divider: 137 kΩ over 52.3 kΩ, 3.202246 V to 3.430848 V).
- **One new check**, `circuit.pullup-parallel` (warning): a bus line pulled up by more than one resistor.
- **Generated documentation**: one page per block under `docs/blocks/`, written from the records by c0268's
  `tools/gen_block_docs.py` and checked for drift.
- **Sources** registered in `docs/evidence/sources.md`: textbook relations (divider ratio, Joule power, RC
  cut-off, LED series resistor, interval bounds, protection-diode terms) and the I2C-bus specification by
  document id only (UM10204). No vendor reference design or table is used.
- **Later** (listed, not built): decoupling set, reverse-polarity protection, crystal, reset, connector with ESD.

## Non-goals

- No block for a specific IC, no vendor device record, no value table copied from any source.
- No derating number: power and voltage are judged against ratings at 100 % in expectations (c0253 applies
  the user's policy to its own ratings checks).
- No second package (`fenolite-blocks`, c0273).

## Evidence level required

- Block arithmetic: `INFERRED` with `H-G-STARTER-ENCLOSURE` (each judged range encloses the brute-force
  worst case over the corners).
- Usage boards and layouts: `KICAD-VERIFIED` read-back on targets 9 and 10 and `H-K-BLOCK-LAYOUT-DRC` (c0271).
- Records: `INFERRED`, the lowest label of their sources.

## Impact

- New: `src/fenolite/blocks/` (`divider.py`, `rc.py`, `led.py`, `i2c.py`, `protect.py`, and per block the
  `usage/`, `tests/`, `golden/` and `layouts/` files), `docs/blocks/` pages.
- Changed: `tools/gen_block_docs.py` (c0268; expectations, usage and layout sections), the blocks'
  `VERSIONS.toml` (c0268), `checks/circuit/` (`circuit.pullup-parallel`), `explain.toml`, `docs/evidence/sources.md`,
  `docs/dsl.md`, the import-graph test, guide pages `design-script` and `dsl-reference`, `CHANGELOG.md`.
- Depends on: c0268, c0269, c0270, c0271, c0254 (generators), c0253 (expectations), c0252 (rails, buses).
- Size: about 8 design-days (M).
