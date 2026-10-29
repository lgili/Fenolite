## Why

`docs/research/electrical-requirements.md` (2026-10-29) reviewed the electrical contracts of the batch
(c0246 ranges, c0248 device ratings, c0252 parametric interfaces, c0253 electrical contracts) against what
other tools do. Its section 4 lists the corrections. Those that touch only c0252 and c0253 were made in
those two changes, which are not implemented yet. The rest cut across changes that other agents are
implementing now (c0246, c0248), or add behaviour no single change owns:

- A device record puts an operating minimum (VIN ≥ 2.7 V) in the slot that the checks read as an absolute
  rating, so a derating "toward zero" *loosens* it. A limit between two pins (BST−SW, a high-side Vgs)
  cannot be written. Pins have no logic thresholds.
- Ranges have no temperature unit, although c0253 compares an ambient range in degrees Celsius, and no
  V·V or A·A product, so `expect()` cannot state a power. One-sided ranges cannot enter arithmetic.
- The living waivers accept only copper and DRC findings. A `circuit.*` error stops the build with no way
  to accept a known risk, and a waiver that outlives the value it accepted would hide a new overload.
- A net behind a ferrite, a fuse or a 0 Ω link has no voltage unless one is declared again, and no row
  says where a value came from. KiCad users know the symptom: a supply through a ferrite is "not driven".
- Track current and voltage drop can be decided only after routing; until then a row is reported as if
  it passed.
- The requirement table is not yet a verification matrix: nothing gives stable row ids, a status per row
  and the inputs it was judged on, in one export.
- The roles' classifier has no `FB`, so the one classifier that c0253 now uses cannot tell a ferrite.

## What Changes

The change is implemented in two steps. **Phase A** lands right after c0246 and c0248 (step 2 of the
batch) and before c0252 and c0253, which read it. **Phases B to F** land after c0253.

- **Phase A: c0248 delta, device limits.**
  - Every device rating and pin limit is `abs_max` (an absolute maximum rating) or `operating` (the range
    the part needs to work): `VIN = { pins = ["5"], voltage = { operating = { min = "2.7V", max = "6V" },
    abs_max = "6.5V" } }`. A string is a maximum. The single `{ min, max }` form of c0248 is refused with a
    hint, so no record holds an ambiguous limit.
  - `[[limits]]` states a voltage between two functions: `between = ["BST", "SW"]`, `voltage = { abs_max
    = "6V" }`.
  - Logic thresholds on pins: `input_high_min`, `input_low_max`, `output_high_min`, `output_low_max` and
    `output_current_max`, each from the datasheet. A c0252 logic or bus port of the device takes them from
    its member pins when its own table omits them.
  - An optional `class` key (the roles' class names), read by `roles.classify` right after the user's class.
  - Temperatures are stored in millikelvin (`"-40degC"` and `"233.15K"` both read).
- **Phase A: c0246 extension, units and products.**
  - The unit `kelvin`; `celsius(x)` and `kelvin(x)` at the DSL boundary; absolute temperatures print in
    degrees Celsius in messages and tables.
  - The products volt·volt → V², ampere·ampere → A², and the results V²/Ω → watt and A²·Ω → watt.
  - One-sided ranges enter `+`, `-` and, when both operands are non-negative, `*` and `/`, as long as the
    result keeps at least one bound.
- **Phase B: the roles' classifier gains `FB`.** The classes `ferrite`, `fuse` and `jumper` join c0222's
  vocabulary, with the prefixes `FB`, `F` and `JP`, tested once in `fenolite.roles.classify`. c0253 judges a
  ferrite's current like an inductor's (derating key `ferrite_current`).
- **Phase C: waivers of `circuit.*` findings.** `design.waive("circuit.rating-voltage", "C3:voltage",
  reason=..., digest="9f2c4a1b0d3e5f67")` accepts one finding: its code, its row (the scope) and the
  **digest of the judged value and limit at waiver time**. When the value or the limit changes, the digest
  differs, the finding stands again, and `check.waiver-expired` says why. Build and check apply the same
  waivers. The living requirement "Waivers in the check" is extended.
- **Phase D: voltage propagation.** A net with no stated voltage takes the voltage of the stated nets it
  reaches through links: parts of class `ferrite`, `fuse` or `net_tie`, a `jumper` whose class the user
  stated, and a resistor whose value range is exactly 0 Ω. Every bound records its **origin** (`declared`,
  `rig`, `role`, `requirements`, `option`, `propagated` with the links it went through). c0252's rails take
  a propagated voltage instead of `circuit.rail-unset`.
- **Phase E: decidable stages.** Each requirement row has a stage at which it can be decided (`build`,
  `place`, `route`). A row whose stage is not reached for its subject is `deferred (route)`, never `pass`;
  a row that already fails keeps failing.
- **Phase F: the verification matrix.** `fenolite check --matrix` returns the rows of `circuit.rules` and
  `roles.rules` with stable ids, status (`pass`, `fail`, `unsure`, `unknown`, `deferred`, `waived`),
  value, limit, source, origin, evidence, decidable stage and digest, and a receipt of the inputs (model
  and device digests). It stays read-only.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `fenolite-component-catalog`: ADDED "Absolute and operating limits of a device", "Limits between two
  pins", "Logic thresholds of device pins", "Device class key" and "Device temperatures in kelvin".
- `design-model`: ADDED "Limits in device definitions" and "Kelvin ranges in the model"; MODIFIED
  "Waivers in the findings layer" (the value digest).
- `design-dsl`: ADDED "Temperatures in the DSL", "Products of ranges" and "One-sided range arithmetic";
  MODIFIED "Waivers in the DSL" (`circuit.*` codes with a digest).
- `verification-loop`: MODIFIED "Waivers in the check"; ADDED "Waivers that expire", "Circuit waiver
  codes", "Voltage propagation through links", "Origins of applied values", "Decidable stages of
  requirement rows" and "Stable requirement row ids".
- `cli-contract`: ADDED "Verification matrix of check".
- `net-roles`: MODIFIED "Part classes" (`ferrite`, `fuse`, `jumper`, the device `class` key).

## Dependencies

- **Phase A** needs c0246 (ranges, `Decimal10`, the unit table) and c0248 (device records, `DeviceDef`,
  `core/quantities`). c0252 and c0253 need phase A.
- **Phases B to F** need c0252 (the stage `circuit.rules`, rails, ports) and c0253 (the requirement
  table, the value sources, the classes injected from `roles.classify`).
- Works with c0249 (the lock keeps refs stable, so row ids stay stable), c0250 (a kept edit changes a
  digest, so its waiver expires), c0245 (the viewer reads the same rows) and c0256 (tests read the matrix).
- 0.7.0 is not released before phase C: without it a `circuit.*` error cannot be accepted.

## Non-goals

- No solver and no inferred voltage: propagation copies a stated range through a link; it computes no
  drop, divides nothing and crosses no regulator, inductor or resistor other than 0 Ω.
- No propagated current: a series part's current stays c0253's smaller bound of its two nets.
- No shipped threshold, derating or temperature table: thresholds come from datasheets through records.
- No waiver of a `kicad.erc.*` or `parity.*` finding (unchanged), and no blanket waiver of a code.
- No export file: `--matrix` is a reply of `check`, which stays read-only.
- No change of c0246's or c0248's folders: this change carries their deltas.

## Evidence level required

- Units, products, one-sided arithmetic, limits and thresholds: exact arithmetic and parsing, unit- and
  property-tested; no external fact, so no label beyond the device record's own.
- Propagation, decidable stages and the matrix: `INFERRED`, hypotheses `H-G-CIRCUIT-PROPAGATION` and
  `H-G-CIRCUIT-ROW-IDS` (registered by tasks 4.3 and 6.3), combined with the device records' labels as in
  c0253 (lowest wins).
- Waivers: `INFERRED`; the digest is a SHA-256 of canonical JSON.

## Impact

- New: `src/fenolite/checks/circuit/propagate.py`, `checks/circuit/matrix.py`, `checks/circuit/decidable.py`;
  `examples/circuit/ferrite/` (good and bad); tests under `tests/unit/catalog`, `tests/unit/dsl`,
  `tests/unit/checks/circuit`, `tests/unit/roles`, `tests/unit/cli`.
- Changed: `core/quantities.py` (kelvin, temperature texts), `dsl/quantity.py` (`celsius`, `kelvin`, the
  products, one-sided arithmetic), `model/circuit.py` (`RangeUnit`), `model/library.py` (`Rating.limit`,
  `DevicePin.ratings` and `thresholds`, `PinPairLimit`, `DeviceDef.limits` and `cls`),
  `catalog/devices.py`, `dsl/rails.py` (thresholds from pins), `roles/classify.py`, `model/rules.py`
  (`PART_CLASSES`), `model/findings.py` (`Waiver.digest`), `dsl/design.py` (`waive`),
  `checks/waivers.py`, `checks/circuit/*`, `core/requirement_table.py`, `cli/cmd_check.py`,
  `cli/cmd_build.py`, `checks/codes.py`, `explain.toml`, schemas, `docs/catalog/README.md`, `docs/dsl.md`,
  `docs/contracts.md`, `docs/roles.md`, `docs/cli-contract.md`, `docs/design-model.md`, the agent guide
  pages `design-script`, `checks` and `board-power`, and `CHANGELOG.md`.
- Size: about 11 design-days (phase A 4, B 1, C 2, D 2, E 1, F 1).
