## ADDED Requirements

### Requirement: Stack-up in the board model
`Board.stackup` SHALL describe the board's build-up from its top face to its bottom face: `Stackup.layers` lists, in that order, every layer that its source keeps in a stack-up, and a board whose source states none has `stackup is None`.
- **Entries.** An entry of kind `copper` MUST be named after its copper layer in `Board.layers`. Entries of kind `soldermask`, `silkscreen` and `solderpaste` describe the outer layers and lie above the first copper entry or below the last. Every entry between two copper entries is of kind `dielectric`; a dielectric made of several sheets is one entry per sheet, consecutive, the sheets sharing a name. Silkscreen and paste entries have `thickness` 0.
- **New fields, with defaults.** `StackLayer.dielectric_kind: DielectricKind | None = None`, where `DielectricKind` is `core` or `prepreg` and `None` means not stated; `StackLayer.color: str = ""`, the colour as its source names it; `Stackup.impedance_controlled: bool = False`, true when the dielectric values are requirements for the fabricator. `material`, `epsilon_r` and `loss_tangent` keep their meaning, and `epsilon_r` and `loss_tangent` are plain decimal texts or empty; a `loss_tangent` may be `0`, which KiCad writes for a solder mask.
- The change MUST be additive: `canonical` omits the defaults, a `board.json` written before it MUST load with them, `SCHEMA_VERSION` stays `"0"`, and `schemas/fenolite.model.v0/board.json` MUST be regenerated with `DielectricKind` as a closed vocabulary.
- The other direction does not hold, and MUST be said: release 0.2.x cannot read a model document that carries `dielectric_kind`, `color` or `impedance_controlled`, because its reader refuses an unknown key. `docs/design-model.md` and the changelog MUST hold that sentence. The `board.json` that the code of release 0.2.1 wrote for `examples/blink_2layer`, committed by this change as `tests/data/model/v0.2.1/blink_2layer.board.json` (the 0.2.0 fixture of "Graphics and texts of a footprint instance" belongs to a change that is not on the branch), MUST still load unchanged and serialise again to its own bytes.
- **Helpers.** `Stackup.thickness() -> Nm` MUST return the sum of `thickness` over `layers`; this sum is the board thickness of the model, and the model holds no other. `Stackup.depth(name) -> tuple[Nm, Nm]` MUST return the depths, below the top face of the first entry, of the top face and the bottom face of the first entry of that name; an unknown name MUST raise `KeyError`. `Stackup.between(upper, lower) -> tuple[StackLayer, ...]` MUST return the entries strictly between the first entries named `upper` and `lower`, top to bottom; an unknown name MUST raise `KeyError`, and an `upper` that does not lie above `lower` MUST raise `ValueError`.
- **Findings.** When `Board.stackup` is not `None`, `Design.validate()` MUST report, with `where` set to the stack-up's id:
  - `model.stackup-order` (error): an entry of kind `soldermask`, `silkscreen` or `solderpaste` between two copper entries, or two entries of one such kind on one side; a dielectric entry above the first copper entry or below the last; two neighbouring copper entries with no entry between them; dielectric entries between the same two copper entries with different `dielectric_kind`; a `dielectric_kind` on an entry that is not a dielectric;
  - `model.stackup-copper` (error): no copper entry, or, when `Board.layers` holds copper layers, copper entries whose names, in order, are not the names of those layers in ordinal order;
  - `model.stackup-value` (error): a negative thickness; a copper or dielectric entry of thickness 0; an `epsilon_r` that is neither empty nor a plain decimal above 0, or a `loss_tangent` that is neither empty nor a plain decimal (digits, an optional point and digits, no sign and no exponent; 0 is accepted for a loss tangent).
- `docs/design-model.md` MUST describe the fields, the helpers and the three findings, and `docs/cli-contract.md` MUST list the findings with the other `model.*` codes.

#### Scenario: Old documents still load
- **GIVEN** a `board.json` written before this change whose board holds a stack-up of three entries
- **WHEN** `canonical.loads` reads it into a `Board`
- **THEN** every entry has `dielectric_kind is None` and `color == ""`, and `impedance_controlled is False`

#### Scenario: A document of 0.2.1 still loads
- **GIVEN** `tests/data/model/v0.2.1/blink_2layer.board.json`, which holds none of the three new keys
- **WHEN** `uv run pytest tests/unit/model/test_stackup.py -k v021` loads it with `canonical.loads` and dumps it again
- **THEN** the dumped text equals the file byte for byte, and `docs/design-model.md` and `CHANGELOG.md` each hold the sentence that release 0.2.x cannot read a model document that carries the new keys

#### Scenario: Thickness, depth and the entries between two layers
- **GIVEN** a stack-up of `F.Mask` 10 000 nm, `F.Cu` 35 000, `dielectric 1` (prepreg) 200 000, `In1.Cu` 17 500, `dielectric 2` (core) 1 200 000, `In2.Cu` 17 500, `dielectric 3` (prepreg) 200 000, `B.Cu` 35 000 and `B.Mask` 10 000
- **WHEN** its helpers are called
- **THEN** `thickness() == 1_725_000`, `depth("In1.Cu") == (245_000, 262_500)`, `between("F.Cu", "In1.Cu")` is the one prepreg entry, and `between("In1.Cu", "F.Cu")` raises `ValueError`

#### Scenario: Copper entries out of table order
- **GIVEN** a board whose layers hold `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu`, and whose stack-up lists its copper entries as `F.Cu`, `In2.Cu`, `In1.Cu`, `B.Cu`
- **WHEN** `design.validate()` runs
- **THEN** it reports one `model.stackup-copper` of severity `error` whose `where` is the stack-up's id

#### Scenario: Mixed gap and a bad decimal
- **GIVEN** a two-layer stack-up with a core and then a prepreg between `F.Cu` and `B.Cu`, the core's `epsilon_r` being `"4,5"`
- **WHEN** `design.validate()` runs
- **THEN** it reports one `model.stackup-order` and one `model.stackup-value`, both of severity `error`

#### Scenario: Schema regenerated
- **WHEN** `uv run python tools/gen_schemas.py --check` runs after this change
- **THEN** it exits 0, and `board.json` lists `dielectric_kind` with the values `core` and `prepreg`, `color` and `impedance_controlled`
