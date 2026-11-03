## Why

A microcontroller usually offers each peripheral on several pin sets: an I2C on two pairs of pins, a UART
on three. Today a Fenolite script names the pins by hand (`u2["PB7"]`), so the author must read the
datasheet's pin table, avoid pins that another function already uses, and redo it when a better pair
appears during layout. Nothing records why a pair was chosen, and nothing refuses two functions on one pin
until KiCad's ERC, if ever.

The research of 2026-10-29 (`docs/research/circuit-as-code.md`, section 12, core change L) takes one
concept from JITX's public documentation: a device *offers* interface options and a consumer *requires* one
interface, and a solver picks. Fenolite does not copy JITX's choice of fixing the pins only when they are
routed, which leaves the choice as hidden state.

## What Changes

- **Interface options in device records.** A device of the catalog (c0248) MAY declare, per interface kind,
  named options and their pin alternatives: "I2C1 on PB6/PB7 or PB8/PB9". Each alternative maps the roles
  of the interface kind (c0252) to pin names of the device.
- **`part.take(KIND, *, name=None, option=None, pins=None)`** in the DSL returns an interface whose pins are
  chosen at build time; it connects as a whole with `connect` (c0252) and helpers (c0247).
- **A deterministic build-time solve.** After the script runs, every take is assigned an alternative so that
  no pin serves two takes or a pin already connected by hand. The search order is canonical (part path,
  take key, option name, alternative index), so the result is a pure function of the design, the catalog and
  the lock: identical under any `--seed` and on every platform.
- **Shown and recorded.** The build's `result.pins` lists every choice with its source (`solved`, `locked`,
  `pinned`), and the `[pins]` section of `<script stem>.lock` (c0249) records it through the plan, so a later
  build keeps it, and `--frozen` refuses to change it.
- **Findings.** `pins.unsatisfiable` (with the smallest conflicting set of takes), `pins.option-unknown`,
  `pins.pinned-conflict`, `pins.search-limit`, `pins.lock-stale`, `pins.unused-take`.

Depends on: c0248 (device records), c0249 (the lock and `--frozen`), c0251 (block paths in take keys) and
c0252 (interface kinds and interface-to-interface `connect`). Later than c0256; possibly after 1.0
(research, "Proposed order", step 7), unless a reference board needs it earlier.

## Non-goals

- No pin-swap during routing and no write-back of a swap from the board; a manual swap goes through c0250.
- No general constraint solver: only "one alternative per take, no pin twice". Electrical compatibility
  (levels, drive) is c0253's.
- No alternate-function register values or firmware output.
- No device data from any vendor file format; options are authored from public datasheets in device TOML.

## Evidence level required

- The solve: `INFERRED`, a pure function tested on authored devices, with `H-G-PIN-SOLVE-DETERMINISTIC`
  measured by the unit jobs on three platforms.
- Interface options of a device: the device record's own label (c0248); an option without a source is
  `UNVERIFIED`, and a build that takes it says so in `evidence`.

## Impact

- New: `src/fenolite/dsl/take.py`, `src/fenolite/lens/pins.py` (the solve), `docs/pins.md`,
  `examples/pins/`, `tests/unit/lens/test_pins.py`, `tests/unit/dsl/test_take.py`.
- Changed: the device schema and loader of c0248, the lock schema of c0249 (`[pins]`), `lens/build.py`,
  `cli/cmd_build.py`, `explain.toml`, `docs/dsl.md`, `docs/cli-contract.md`, the guide page `parts`,
  `CHANGELOG.md`.
- Size: about 7 design-days.
