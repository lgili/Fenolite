## ADDED Requirements

### Requirement: Stack-ups with masks, sheets and kinds in an Altium build
The Altium build SHALL take the stack values of the PCB document from a `Board.stackup` that holds the entries and fields of `design-model`, "Stack-up in the board model" (solder mask, silkscreen and paste entries, sheets, `dielectric_kind`, `color`, `impedance_controlled`), by the rules below, and SHALL name every value that the document does not hold. The rules apply alike to `lens.altium_copper.stack_from_stackup` (a build, "Copper in an Altium build") and to `backends.altium.lower.stack_from_stackup` (the write of a model), which reports through its account where the build gives an issue.
- Entries of kind `soldermask`, `silkscreen` and `solderpaste` MUST be passed over: the stack of the document holds the copper layers and the dielectrics between them (`altium-pcb-writer`, "Layer stacks of any even count").
- A dielectric entry whose `dielectric_kind` is set MUST be written with that kind: `DIELTYPE` 1 for `core` and 2 for `prepreg`, the values recorded in `docs/formats/altium/pcb-copper.md` ("Layer stack"). An entry without one MUST take the kind of `dielectric_kinds(count)` as before. A stack-up that holds none of the new fields MUST therefore give the document it gave before this requirement, byte for byte.
- A gap between two copper entries that holds two or more dielectric entries (the sheets of one dielectric) does not fit the document, which holds one dielectric per gap. The build MUST then write Fenolite's default stack values and give one `altium.not-lowered` info with `where` `stackup` whose message names the gap, as "Copper in an Altium build" rules for a stack-up that does not fit. Sheets MUST NOT be merged, dropped or averaged.
- When the stack-up fits and holds a value for which the document has no recorded key (a solder mask entry of thickness above 0, a non-empty `color`, a non-empty `finish`, or `impedance_controlled` true), the build MUST give one `altium.not-lowered` info with `where` `stackup` that lists the kinds of value left out; the copper and dielectric values MUST be written. A stack-up without such a value MUST give no issue.
- The Altium import MUST NOT fill `dielectric_kind`, `color` or `impedance_controlled` through this requirement: an imported stack-up keeps the defaults, and the round trips of `altium-verification` compare the models they compared before.
- This requirement adds no record, key or format fact and no issue code, and the evidence of the build does not change.

#### Scenario: Script stack-up with masks and stated kinds
- **GIVEN** a four-layer blink variant whose `design.stackup(...)` lists a 10 µm mask, 35 µm copper, a 0.2 mm prepreg, 17.5 µm copper, a 1.2 mm core, 17.5 µm copper, a 0.2 mm prepreg, 35 µm copper and a 10 µm mask, without a colour and without a finish
- **WHEN** it is built with `--target altium` and the PCB document is read back
- **THEN** the board has four copper layers with those copper thicknesses, the three dielectrics are a prepreg, a core and a prepreg with those heights within 2 nm, and `issues` holds one `altium.not-lowered` info with `where` `stackup` that names the solder mask thickness and nothing else

#### Scenario: A core where the table says prepreg
- **GIVEN** a two-layer model whose stack-up holds `F.Cu`, one dielectric entry with `dielectric_kind == "prepreg"` and `B.Cu`
- **WHEN** `build_altium` runs and the document is read back
- **THEN** the one dielectric has `DIELTYPE` 2, where the same model without `dielectric_kind` gives 1, and `issues` holds no `altium.not-lowered` with `where` `stackup`

#### Scenario: Two sheets in one gap
- **GIVEN** the four-layer board of `kicad-file-backend`, "Four-layer node projected" (`tests/data/kicad/board/stackup_four.kicad_pcb`), whose core between `In1.Cu` and `In2.Cu` holds two sheets
- **WHEN** its model is written as an Altium PCB document
- **THEN** the document holds the default stack values, and exactly one `altium.not-lowered` (or one skipped `stackup` entry of the account) names the gap between `In1.Cu` and `In2.Cu`

#### Scenario: Stack-ups without the new fields keep their bytes
- **WHEN** `uv run pytest tests/unit/lens/test_altium_pcb_complete.py tests/unit/lens/test_altium_pcb_golden.py tests/unit/lens/test_altium_copper_golden.py` builds the committed Altium samples
- **THEN** every file equals the committed one
