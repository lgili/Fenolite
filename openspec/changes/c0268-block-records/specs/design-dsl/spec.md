## ADDED Requirements

### Requirement: Block records in the DSL
`block` SHALL take the keyword-only arguments `id`, `version`, `summary`, `category`, `licence`, `evidence`, `sources`, `replaces` and `deprecated`, which give the block a record ("Block record fields" of `block-library`). `id` and `name` MUST NOT both be given. `@block` and `@block(name=...)` without `id` SHALL keep c0251's behaviour and give a project block without a record, version or lock entry.

#### Scenario: Project block unchanged
- **GIVEN** `examples/blocks/design.py` of c0251, whose blocks have no id
- **WHEN** `canonical.dump_texts(to_model(design))` is computed before and after this change
- **THEN** the texts are equal and the design gets no `[blocks]` lock section

#### Scenario: Name and id together
- **WHEN** `@block(name="div", id="Acme:div", version="1.0.0", summary="d", licence="MIT")` decorates a function
- **THEN** `DslError` is raised naming `name` and `id`

### Requirement: Block parameter metadata
`fenolite.dsl` SHALL export `param(default=REQUIRED, *, doc="", unit=None, min=None, max=None, choices=None)`, used as a block parameter's default. `@block` MUST check that the default is recordable, matches `unit`, lies within `min` and `max` (both ends of a range) and is one of `choices`. `use` MUST raise `DslError` before the function runs for a value of another unit, outside the limits or not a choice.

#### Scenario: Value outside the range
- **GIVEN** the authored divider whose `current` is `param(ua(100), min=ua(1), max=ma(10))`
- **WHEN** `design.use(divider, "d1", current=ma(20))` is called
- **THEN** `DslError` is raised naming `current`, `20mA` and the range `1uA` to `10mA`, and the function is not called

#### Scenario: Wrong unit
- **WHEN** `design.use(divider, "d1", current=volt(1))` is called
- **THEN** `DslError` is raised naming `current`, `volt` and `amp`

#### Scenario: Default not a choice
- **WHEN** `@block` decorates a block with `series=param("E12", choices=("E24", "E96"))`
- **THEN** `DslError` is raised at decoration naming `series` and the choices

### Requirement: Port documentation
The builder's `port` SHALL take the keyword `doc` (at most 200 characters, no newline), kept for `describe` and pages and not written to the model.

#### Scenario: Port doc in the record
- **GIVEN** a block with `b.port("HI", Rail, direction="in", doc="input")`
- **WHEN** it is described and `to_model` runs on a design that uses it
- **THEN** the record's port `HI` has the doc `input`, and the model's `Port` has no doc field

### Requirement: Block identity in a design
For a block with a record, the c0251 block name SHALL be its id. The model `Module` of each instance MUST hold `block = <id>` and `block_version = <version>`, and the KiCad sheet name MUST be `<instance name> (<id>)`. Two different functions with one id in one design MUST raise `DslError` at the second `use`.

#### Scenario: Version in the model
- **GIVEN** a design that uses the authored `Acme:divider` 1.0.0 as `sense_a`
- **WHEN** `to_model` runs
- **THEN** the module `sense_a` has `block == "Acme:divider"` and `block_version == "1.0.0"`

### Requirement: Block versions in the design lock
c0249's lock SHALL hold the section `[blocks]`, registered as a `LockSection`, mapping each instance path of a block with a record, at any depth, to `<id>@<version>`. A design with such an instance SHALL have a lock, and a design without one MUST get no section. Entries MUST follow `design.moved()` aliases as c0249's entries do.

#### Scenario: First build pins the versions
- **GIVEN** a design with two instances `sense_a` and `sense_b` of `Acme:divider` 1.0.0 and no lock
- **WHEN** `fenolite build design.py --dry-run --json` runs
- **THEN** the plan holds the lock with `[blocks]` entries `sense_a` and `sense_b` = `Acme:divider@1.0.0`, and `result.lock.changes` holds two changes of reason `block-locked`

#### Scenario: Moved instance keeps its entry
- **GIVEN** a locked design in which `sense_a` is renamed `adc_a` with `design.moved("sense_a", "adc_a")`
- **WHEN** it is built
- **THEN** the lock maps `adc_a` to the old entry and holds no `sense_a`

### Requirement: Locked block versions in a build
A build SHALL compare each instance with its `[blocks]` entry. Another version of the same id MUST give `lock.block-version` (error) naming the path and both versions, and nothing is written. Another id MUST replace the entry with `lock.block-replaced` (info). An entry whose path is no instance with a record MUST be dropped with `lock.block-released` (info). Under `--frozen`, any change MUST exit 7 with `FEN-7004`.

#### Scenario: Newer block version is not taken
- **GIVEN** a lock with `"sense_a" = "Acme:divider@1.0.0"` and the block now at version `1.1.0`
- **WHEN** `fenolite build design.py --confirm --json` runs
- **THEN** the exit code is 5, `issues` hold `lock.block-version` naming `sense_a`, `1.0.0` and `1.1.0`, and no file is written

#### Scenario: Frozen build and a first pin
- **GIVEN** a design that starts using a block with a record and a lock without `[blocks]`
- **WHEN** `fenolite build design.py --frozen --json` runs
- **THEN** it exits 7 with `FEN-7004`, and `issues` hold a `lock.changed` for section `blocks`

### Requirement: Deprecated blocks in a build
A build that uses a block whose record has `deprecated` SHALL succeed and SHALL report `block.deprecated` (warning) once per id, naming the id and the replacement.

#### Scenario: Deprecated block used twice
- **GIVEN** two instances of an authored block with `deprecated = {"by": "Acme:div2", "since": "1.1.0", "reason": "port renamed"}`
- **WHEN** the design is built
- **THEN** the build succeeds and `issues` hold one `block.deprecated` naming `Acme:div2`
