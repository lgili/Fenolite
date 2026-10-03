## Why

The maintainer compiled a Fenolite-written project in Altium Designer 26.5. The electrical rules check
reported floating input pins and nets with no driving source for pins that the design leaves
unconnected on purpose. The DSL has no way to say "this pin is intentionally unconnected", so the Altium
schematic holds no No ERC directive, and Fenolite's own `erc.lite.floating-pin` warns about the same
pins.

## What Changes

- **DSL.** `fenolite.dsl.no_connect(*pins)` marks pins as intentionally unconnected, for example
  `no_connect(u1[11], u1[12])`. A designator that is marked and connected raises `DslError`.
- **Model.** `Circuit.no_connects: tuple[PinRef, ...]` records the marks, next to the net members and
  in the same form. The field is additive: its default `()` is omitted from `circuit.json`, and the
  schema is regenerated. `Design.validate()` reports `model.no-connect-on-net` (error) for a marked
  pin that a net lists.
- **Altium schematic.** Each marked pin gets no wire stub and one No ERC directive (`RECORD=22`,
  "Suppress All Violations") at its electrical end, in the ASCII and the binary form. The record is a
  fact of S-0130 and S-0131; the first task records it in
  `docs/formats/altium/schematic-ascii.md`. The symbol writer is unchanged; a generic body gains the
  marked pins, because it holds "the pins the design uses".
- **KiCad target.** The build writes no schematic yet (v0.2a). The marks are resolved to pin numbers
  and kept in `.fenolite/circuit.json`; the written KiCad files do not change. A pin that is marked
  and on a net gives `build.no-connect-on-net` (error).
- **Check.** `erc.lite.floating-pin` no longer warns for a marked pin.
- **Evidence.** A second script in `examples/altium_kicad/` (three marked pins, one unmarked control
  pin), its golden files, and Part N of `docs/evidence/altium-schematic.md`.

## Capabilities

### Modified Capabilities (no new capability)

- `design-model`: ADDED "No-connect marks in the circuit model".
- `design-dsl`: ADDED "No-connect marks in the DSL" and "No-connect marks in a build".
- `verification-loop`: MODIFIED "ERC lite stage".
- `altium-schematic-writer`: ADDED "No-connect directives on the sheet" and "No-connect directives
  read back"; MODIFIED "Connectivity on the sheet" and "Generic component bodies" (texts of c0034).
- `altium-build`: ADDED "No-connect marks in an Altium build" and "No-connect sample and author
  report"; MODIFIED "Altium symbol sources" (text of c0035).

## Non-goals

- No KiCad schematic and no KiCad no-connect flag: that is v0.2a, which lowers `Circuit.no_connects`.
- No change to the written `.kicad_pcb`, `.kicad_pro` or `.kicad_dru`, and no pad pin type.
- No "Suppress Specific Violations" mode, no other directive style, no directive on a wire or a net.
- No change to library symbols from KiCad symbols, to pin electrical types or to `Pin.etype`.
- No automatic marking of unused pins, no Altium reader, no new `check` stage.

## Evidence level required

- Record 22 and its keys: `INFERRED` (S-0130, S-0131, S-0180) under `H-A-SCH-NC-RECORD`,
  `H-A-SCH-NC-ERC` and `H-A-SCH-NC-VIEWER`, until the maintainer reports Part N with Altium Designer
  26.5 and the Altium 365 Viewer. A confirmed row becomes
  `ALTIUM-VERIFIED(author-report; AD 26.5; <date>; no artefact)`. An author report never promotes an
  operation, so the Altium build stays `INFERRED` and experimental.
- Fenolite's own readback (`tests/_altium_read.py`) proves that the directives sit on the marked
  pins' ends in both forms. It raises no label.
- DSL, model, KiCad build: Fenolite's own rules, proved by unit tests. `erc.lite` stays `INFERRED`
  (`H-K-CHECK-ERC`).

## Impact

- Code: `model/circuit.py`, `model/design.py`, `dsl/part.py`, `dsl/convert.py`, `lens/build.py`,
  `lens/altium.py`, `checks/erc_lite.py`, `backends/altium/{layout,schdoc,project}.py`, the circuit
  schema.
- Docs: the DSL, model, Altium and CLI pages, two format pages, the evidence page, the registers.
- Order: implemented and archived right after c0035 (chain c0032 → c0033 → c0034 → c0035). No
  requirement of c0020, c0021 or c0028–c0031 is touched.
- Size: 2.25 design-days.
