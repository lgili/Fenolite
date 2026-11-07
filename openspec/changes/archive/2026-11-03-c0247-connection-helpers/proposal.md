## Why

Every pin of a Fenolite design goes through `connect(net, *pins)`. That is exact but verbose for the
patterns every board repeats: a fuse and a diode in series, a decoupling capacitor beside a supply pin,
two I2C pull-ups, and the unused pins of a controller. The blink example marks 29 unused pins by hand
with a generator expression over pin numbers, and a typo there either hides a pin that should be wired or
flags one that is wired. Nothing records that a decoupling capacitor belongs near a particular pin unless
the author also writes a `near()` rule.

The research `docs/research/circuit-as-code.md`, section 6 and core change J, found three useful ideas:
atopile's series bridge through two-terminal parts, tscircuit's per-pin connections with a pull-up that
names its pin, and JITX's `no_connect()` on a port. Fenolite takes the concepts only, as plain functions
that lower to what the DSL already has.

## What Changes

- **Named ends of two-pin parts.** `r1.a` and `r1.b` name pins `1` and `2`. A part used through its ends
  is checked at build to have exactly two pins (`build.not-two-terminal`). The devices of c0248 may name
  their ends (`+`/`-`, `A`/`K`); until then the ends are the pin numbers.
- **`series(vin, f1, d1, vprot)`.** A chain from a net through two-pin parts to a net. Parts next to each
  other are joined by a new net named from their paths; a `Net` between parts names that joint; a tuple
  `(d1.b, d1.a)` turns a part around. Returns the new nets.
- **`decouple(rail, gnd, c1, c2, near=u1.pad(9), within=mm(3))`.** Joins each capacitor between the two
  nets and, with `near`, records one `near()` placement rule per capacitor (`decouple/<path>`), judged by
  the existing `placement.rules` stage.
- **`pull_up(target, rail, *resistors)` and `pull_down(target, gnd, *resistors)`.** The target is a net,
  one resistor, or an `I2C`, one resistor per line (SDA, then SCL).
- **`part.unused_no_connect(keep=())`.** At build, every pin of the part with no net and no mark is
  marked as not connected, except the pins in `keep`, pins of type `no_connect`, and must-connect pins: a
  `power_in` pin, or a pin a catalog device flags `must_connect` (c0248). A must-connect pin left open
  gives `build.must-connect-unconnected` (error). The marks are the ordinary no-connect marks.

## Capabilities

### Modified Capabilities

- `design-dsl`: MODIFIED "No-connect marks in the DSL" (it forbade automatic marking); ADDED
  requirements for named ends, series chains, decoupling, pull resistors, the unused-pin request, its
  build resolution, must-connect pins, the two-pin check, and documentation.

## Non-goals

- No part creation: every helper takes parts the script made. Choosing a part from a value
  (`capacitor(farad("100n"))`) is c0254.
- No interface-to-interface connection and no logic-level pull-ups on `Logic` interfaces (c0252).
- No placement: `decouple` records a rule; moving parts is c0255 and `fenolite place`.
- No default decoupling distance, resistor value or other engineering number.
- No new model field: helpers lower to nets, no-connect marks and proximity rules.

## Evidence level required

- DSL lowering: unit tests on `to_model`.
- Builds: `KICAD-VERIFIED` that the blink written with `u1.unused_no_connect()` builds the pinned bytes
  of the blink written with explicit marks, and that the new error codes stop the build with nothing
  written.

## Impact

- New: `src/fenolite/dsl/wiring.py` (`series`, `decouple`, `pull_up`, `pull_down`).
- Changed: `dsl/part.py` (`Part.a`, `Part.b`, `Part.unused_no_connect`), `dsl/convert.py` (two side
  channels), `dsl/__init__.py`, `lens/build.py` and `lens/altium.py` (resolution, two codes),
  `BUILD_ISSUE_CODES`, `cli/data/explain.toml`, `docs/dsl.md`, `docs/cli-contract.md`,
  `examples/blink_2layer/design.py`, the guide pages `design-script` and `dsl-reference`,
  `CHANGELOG.md`.
- Dependencies: implemented with c0246 (step 1 of the batch). c0248 adds device ends and the
  `must_connect` flag this change reads; c0252 widens `pull_up` to parametric interfaces; c0254 lets
  helpers take a value.
- Size: about 3 design-days.
