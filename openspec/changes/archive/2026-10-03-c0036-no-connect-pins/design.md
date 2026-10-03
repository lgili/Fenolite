## Context

- The maintainer compiled a Fenolite-written project in Altium Designer 26.5. The compiler reported
  floating input pins and nets with no driving source for pins the design leaves open on purpose.
- The DSL (`fenolite.dsl`, c0011) has `connect(net, *pins)` and no way to mark a pin as unconnected.
  `to_model` gives components with empty `pins`; a build fills them from the symbol and rewrites net
  members, written as pin numbers or names, to pin numbers.
- The model has `Pin.etype`, whose value `no_connect` is the pin type a symbol declares. It is not a
  statement about one design, and it does not exist before a build.
- The Altium writer (c0032 to c0035) draws one wire stub per connected pin, with a net label or a
  power port. A pin on no net gets nothing. The binary form frames the records of
  `schdoc.schdoc_records(plan)` unchanged.
- Format facts, read on 2026-10-03 and to be recorded by task 1.2:
  - S-0130 lists record 22 as "No ERC", a cross that marks an intentional non-connection, with
    `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y`, `COLOR`, an optional `INDEXINSHEET`, and the optional
    keys `ISACTIVE=T`, `ORIENTATION`, `SUPPRESSALL=T`, `SYMBOL=Thin Cross` and `UNIQUEID`.
  - S-0131 (facts only) gives record number 22 the same meaning, reads its location, and takes
    "active" and "suppress all" as true when the keys are missing.
  - Altium's documentation (S-0180) describes the No ERC directive: it has selectable styles and two
    modes, "Suppress All Violations" and "Suppress Specific Violations".
  - No source says that a directive placed on a pin's electrical end without a wire suppresses the
    pin's violations. That is hypothesis `H-A-SCH-NC-ERC`.
- `checks.erc_lite` (c0013) reports `erc.lite.floating-pin` for every pin of a built model that no net
  lists, unless its `etype` is `no_connect`.
- The KiCad build writes no schematic until v0.2a.

## Goals / Non-Goals

**Goals**

- One DSL call marks pins as intentionally unconnected.
- The model keeps the marks, additively, through `.fenolite/`.
- The Altium schematic holds a No ERC directive at each marked pin, in both forms.
- The KiCad build keeps the marks, refuses a marked pin on a net, and `erc.lite` stops warning.
- A sample the maintainer can compile, with a positive control.

**Non-Goals**

- A KiCad schematic or KiCad's no-connect flag (v0.2a).
- Any change to the written KiCad files.
- "Suppress Specific Violations", other directive styles, directives on wires or nets.
- Changes to library symbols from KiCad symbols, to pin types or to `Pin.etype`.
- Automatic marking of unused pins, an Altium reader, a new `check` stage.

## Decisions

1. **DSL: a function `no_connect(*pins)` in `dsl/part.py`.** It mirrors `connect`, takes the same pin
   handles and marks pins of several parts in one call. Marks are stored as written in
   `Part.no_connects`.
   - Rejected: `u1.nc(11, 12)`. It adds a second way to name pins (bare designators instead of
     handles) and a method name that reads as a pin name.
   - Rejected: `connect(NC, u1[11])` with a reserved net. A net named `NC` would reach the board, the
     labels and the net classes, and every backend would have to filter it.
2. **Marked and connected is an error at three levels.** The DSL raises `DslError` when the same
   written designator is marked and connected, in either order. The builds catch the case that the
   DSL cannot see, a pin named once by number and once by name: `build.no-connect-on-net` (KiCad
   build) and `model.no-connect-on-net` (`Design.validate()`, which the Altium build runs after it
   rewrites the marks, and which the `model.validate` stage of `check` reports).
   - Rejected: a warning. The two statements contradict each other, and Altium would show a directive
     on a wired pin.
3. **Model: `Circuit.no_connects: tuple[PinRef, ...]`.** A mark has the form of a net member, so
   `to_model` can write it before any pin exists, and the builds resolve it with the code path that
   resolves net members.
   - Rejected: `Pin.no_connect: bool`. `to_model` gives no pins, so the DSL could not record a mark
     without a second field; and the mark belongs to the design's connectivity, not to the pin that
     the library defines.
   - Rejected: `Pin.etype = "no_connect"`. It overwrites the symbol's pin type (an input stays an
     input), and Altium's pin type would change with it.
   - Rejected: a reserved component property such as `fenolite.no_connect`. Properties are written
     onto KiCad footprints, and a comma-joined string is not a typed reference.
4. **Additive schema.** The field is last in `Circuit` with the default `()`. `canonical` omits
   defaults, so existing `circuit.json` files are unchanged and load. `SCHEMA_VERSION` stays `"0"`.
   `tools/gen_schemas.py` regenerates `schemas/fenolite.model.v0/circuit.json`.
5. **Altium record: record 22 with explicit flags.** Keys in this order: `RECORD=22`,
   `OWNERPARTID=-1`, `LOCATION.X`, `LOCATION.Y`, `COLOR=255`, `ISACTIVE=T`, `SUPPRESSALL=T`,
   `SYMBOL=Thin Cross`. The flags are written although one reader takes them as true by default,
   because no source says what Altium assumes. `COLOR=255` is red in the page's colour encoding.
   - Rejected: `ORIENTATION` from the pin direction. The thin cross is symmetric; a missing integer
     reads as 0.
   - Rejected: a `UNIQUEID`. Wires, labels and ports are written without one (c0032).
   - Rejected: changing the pin's electrical type to passive in the schematic. It hides the pin from
     every other rule and makes the sheet differ from the library.
6. **Position: the pin's electrical hot end, no stub.** A marked pin gets no wire. The directive's
   location is the hot end that a wire would start from.
   - Rejected: a short stub with the directive at its end. It adds a one-pin net with a wire, which
     is the object the compiler warned about.
7. **Record order: directives last.** They follow every stub, label and port, in component, part and
   pin order. A design without marks is written byte for byte as before, so no golden file of c0032
   to c0035 changes.
8. **Generic bodies count marked designators.** For an Altium link, the generic body holds the
   designators that the nets or the marks name. Without this, a mark on a pin that no net names has
   no pin to sit on. The symbol writer and the symbols from KiCad symbols are unchanged; only the
   input of a generic symbol grows when a design marks such a pin.
9. **KiCad target: keep, refuse, do not write.** The build resolves marks like net members, stores
   them in `.fenolite/circuit.json`, and changes no written KiCad file. v0.2a's schematic writer
   lowers them to KiCad's no-connect flags.
10. **ERC lite: one more exemption.** `erc.lite.floating-pin` skips a pin that `Circuit.no_connects`
    lists. No new code, stage or summary key.
11. **Sample: a second script in `examples/altium_kicad/`.** `no_connect.py` reuses the folder's
    authored CC0 symbol library, whose `MCU8` has input, output and passive pins. Pins 2, 4 and 8 are
    marked; pin 3, an input, is left open and unmarked as the positive control. The existing samples
    and their golden files stay untouched.
    - Rejected: marks in `examples/altium_sample`. Its generic pins are all passive, so the compiler
      would have nothing to report, and its record counts are written into several scenarios.

## Files and public API

| File | Change | Public API |
|---|---|---|
| `src/fenolite/model/circuit.py` | field | `Circuit.no_connects: tuple[PinRef, ...] = ()` |
| `src/fenolite/model/design.py` | findings | `Design.validate()` reports `model.no-connect-on-net`, and `model.unknown-component` and `model.unknown-pin` for marks |
| `schemas/fenolite.model.v0/circuit.json` | regenerated | optional `no_connects` |
| `src/fenolite/dsl/part.py` | function, attribute | `no_connect(*pins) -> None`; `Part.no_connects: set[str]`; `connect` refuses a marked designator |
| `src/fenolite/dsl/convert.py` | marks | `to_model` fills `Circuit.no_connects` |
| `src/fenolite/dsl/__init__.py` | re-export | `no_connect` |
| `src/fenolite/lens/build.py` | resolution | `BUILD_ISSUE_CODES["build.no-connect-on-net"]`; marks rewritten to pin numbers |
| `src/fenolite/checks/erc_lite.py` | rule | `erc.lite.floating-pin` skips marked pins |
| `src/fenolite/backends/altium/layout.py` | plan | `NoConnectMark`, `PartSpec.no_connects`, `SheetPlan.no_connects`, `part_marks(spec, x, y, part=1)` |
| `src/fenolite/backends/altium/schdoc.py` | record | record 22 in `schdoc_records(plan)` |
| `src/fenolite/backends/altium/project.py` | specs | `part_specs` fills `PartSpec.no_connects` and raises `ValueError` for a bad mark |
| `src/fenolite/lens/altium.py` | resolution | `kicad_pins` and `generic_pins` handle marks; `summary["no_connects"]`; three hypotheses in `ALTIUM_BUILD_EVIDENCE` |
| `examples/altium_kicad/no_connect.py` | new | the design `altium_no_connect` |
| `tests/data/altium/no_connect/` | new | four golden files |
| `tests/_altium_read.py` | reader | `read_no_connects(records)` |
| `tests/unit/dsl/test_no_connect.py`, `tests/unit/lens/test_build_no_connect.py`, `tests/unit/lens/test_altium_no_connect_golden.py` | new | tests |
| `tests/unit/model/test_circuit.py`, `test_design.py`, `tests/unit/checks/test_erc_lite.py`, `tests/unit/backends/altium/test_schdoc.py`, `test_layout.py`, `test_readback.py`, `tests/unit/lens/test_altium_build.py`, `test_altium_issues.py`, `test_build_issues.py` | extended | tests |
| `docs/dsl.md`, `docs/design-model.md`, `docs/altium.md`, `docs/cli-contract.md`, `docs/roadmap.md` | sections | — |
| `docs/formats/altium/schematic-ascii.md`, `schematic-binary.md`, `src/fenolite/backends/altium/PROVENANCE.md` | fact rows | — |
| `docs/evidence/altium-schematic.md`, `docs/hypotheses.md`, `docs/evidence/sources.md` | Part N, rows | — |

`fenolite.dsl` still imports only `core` and `model`. `backends.altium` still imports only `core` and
`model`. `checks` gains no import.

## Sources registered by this change

| id | URL | used for |
|---|---|---|
| S-0180 | https://www.altium.com/documentation/altium-designer/schematic/design-validation (section "No ERC") | the No ERC directive: its styles and its two modes, "Suppress All Violations" and "Suppress Specific Violations" |

Existing ids, whose "used for" cells task 1.1 widens: S-0130 (record 22 and its keys), S-0131 (record
number 22, location, the two defaults; facts only), S-0149 (the Viewer). S-0181 to S-0184 stay unused.

## Hypotheses registered by this change

| id | statement | test | criterion |
|---|---|---|---|
| `H-A-SCH-NC-RECORD` | Altium Designer opens a schematic, binary or ASCII, that holds record 22 with Fenolite's keys, without a prompt, and shows a No ERC directive at each marked pin's end | Part N, steps N1 and N3 | no prompt or repair offer; three directives at the ends of `U1` pins 2, 4 and 8 |
| `H-A-SCH-NC-ERC` | A directive at a pin's electrical end, without a wire, suppresses the compiler's messages for that pin, and only for that pin | Part N, steps N2 and N3 | no message names pins 2, 4 or 8; a floating-input message names pin 3 |
| `H-A-SCH-NC-VIEWER` | The Altium 365 Viewer draws the directives of the binary schematic | Part N, step N4 | three crosses at the marked pins |

All three start at `INFERRED` with the result `pending (author report)`. `H-K-CHECK-ERC` (c0013)
keeps bounding `erc.lite`.

## Evidence level per behaviour (before merge)

| Behaviour | Level | Basis |
|---|---|---|
| DSL marks, errors, `to_model` | Fenolite's own rule | unit tests |
| `Circuit.no_connects`, schema, validation findings | Fenolite's own rule | unit tests, schema drift test |
| KiCad build keeps marks; written KiCad files unchanged | Fenolite's own rule; no KiCad claim | byte comparison of two builds |
| `erc.lite.floating-pin` exemption | `INFERRED` (`H-K-CHECK-ERC`) | unit tests |
| Record 22 keys and values | `INFERRED` (S-0130, S-0131, S-0180), then `ALTIUM-VERIFIED(author-report; AD 26.5; <date>; no artefact)` per row | Part N |
| Directive sits on the marked pin's end, both forms | Fenolite's own readback (`tests/_altium_read.py`) | raises no label |
| Compiler stays silent for marked pins | `INFERRED` (`H-A-SCH-NC-ERC`), then author report | Part N, N2 and N3 |
| Viewer draws the directive | `INFERRED` (`H-A-SCH-NC-VIEWER`), then `A365 Viewer` author report | Part N, N4 |
| Altium build envelope | `INFERRED`, experimental | an author report never promotes an operation |

## Size (design-days)

| work | design-days |
|---|---|
| 1. sources, hypotheses, fact rows, provenance | 0.25 |
| 2. model field, validation, schema; DSL call and `to_model` | 0.5 |
| 3. Altium record, plan, build resolution, readback, sample and Part N | 0.75 |
| 4. KiCad build resolution and `erc.lite` | 0.25 |
| 5. documentation and the maintainer's report | 0.25 |
| 6. closing | 0.25 |
| **total** | **2.25** |

This is a size, not a calendar estimate. Nothing is optional; the only cut is step N4 (the Viewer),
which saves protocol text and no code.

## Overlaps with other active changes

- **c0032 → c0033 → c0034 → c0035 (implemented, not archived).** This change MODIFIES
  `altium-schematic-writer` "Connectivity on the sheet" and "Generic component bodies", both copied
  from c0034 (their latest text; c0035 does not modify them), and `altium-build` "Altium symbol
  sources", copied from c0035. `openspec archive` applies a MODIFIED delta only to a requirement that
  exists, so the archive order is c0032, c0033, c0034, c0035, then c0036.
- **Living specs.** `verification-loop` "ERC lite stage" is MODIFIED from `openspec/specs/`. The
  `design-model` and `design-dsl` deltas are ADDED only.
- **c0020, c0021, c0028 to c0031.** None modifies "ERC lite stage", "Connectivity on the sheet",
  "Generic component bodies" or "Altium symbol sources", and none adds a requirement with one of this
  change's names. c0020 and c0029 modify other `verification-loop` requirements; c0021 modifies
  `design-dsl` "Build command" and "Library resolution during build"; c0028 and c0031 modify
  `design-model` "Identifier derivation". This change is implemented right after c0035 and before
  them. If one of them later needs a requirement this change touches, it rebases onto this change.
- **Code overlap, no spec overlap.** c0028 to c0031 extend `dsl/part.py`, `dsl/convert.py` and
  `lens/build.py` with other functions; they merge after this change.

## Risks / Trade-offs

- **The directive may not suppress a pin without a wire** (`H-A-SCH-NC-ERC`). Mitigation: the control
  pin tells a working directive from a silent compiler. If N2 refutes it, the successor hypothesis
  tries a directive on a one-segment stub, and Decision 6 is revised with a regression test.
- **Unknown key values.** `SYMBOL=Thin Cross` holds a space and comes from one source. If Altium
  refuses or redraws it, the report names the fault and the row is superseded.
- **Older Fenolite readers.** A `circuit.json` with marks holds a key that an older schema may refuse.
  Files without marks are unaffected.
- **Generic library symbols change when a design marks a pin that no net names.** Altium then offers
  an update of that symbol. This only happens in designs that start using marks.

## Migration Plan

- No migration. Designs without marks give the same bytes in every target.
- A design that adds `no_connect(...)` and is rebuilt for Altium gets a new `<name>.SchDoc`; the
  edited-output rule of c0032 applies as for any other change of the script.
- Rollback: remove the calls from the script, or revert the change; no stored file needs repair.

## Open Questions

1. Should a generic body hold a marked pin that no net names (Decision 8)? Default: yes. The
   alternative, an info that the mark was skipped, makes marks useless for Altium links.
2. Should the Altium build warn about unmarked, unconnected pins of KiCad symbols? Default: no; that is
   the compiler's job, and `fenolite check` has `erc.lite` for the KiCad target.
3. Should `COLOR` follow the sheet's text colour instead of red? Default: red (`255`).
4. Does the maintainer want a `Part` method as well? Default: no; one way to mark a pin.
