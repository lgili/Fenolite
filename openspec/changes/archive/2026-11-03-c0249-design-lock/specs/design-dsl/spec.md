## ADDED Requirements

### Requirement: Parts without a ref
`Part(ref=None, lib_id=None, footprint=None, value="", *, device=None, name=None, prefix=None, ...)`, `Design.part` and `Module.part` SHALL accept a part without a ref. The key of a part, the last segment of its path, MUST be `name` when given, else the explicit ref, else its reference prefix. A key that is already the path of an unnamed part in the same container MUST raise `DslError` at the call, asking for `name=`.

#### Scenario: Key from the prefix
- **GIVEN** `buck = Module("buck")` added to a design
- **WHEN** `u = buck.part(device="Example:BUCK_6V_2A")` is called
- **THEN** `u.path` is `"buck/U"` and `u.ref` is `None` until the build assigns it

#### Scenario: A second unnamed part
- **GIVEN** `buck.part(device="Fenolite:C_0805")` already called
- **WHEN** `buck.part(device="Fenolite:C_0805")` is called again
- **THEN** `DslError` is raised naming `buck/C` and `name=`, and the first part keeps the path `buck/C`

#### Scenario: Name and explicit ref
- **WHEN** `design.part("R5", name="pull_sda", device="Fenolite:R_0603")` is called
- **THEN** the part's path is `"pull_sda"` and its ref is `"R5"`

### Requirement: Reference prefixes
The prefix of a part without a ref SHALL be, in order: `prefix=` (matching `[A-Z][A-Z_]*`), the device's `ref_prefix`, or the `reference` of a `Fenolite:` catalog symbol. A part without a ref and without any of these MUST raise `DslError` at the call ("give a ref, a prefix or a device").

#### Scenario: Prefix from the catalog symbol
- **WHEN** `design.part(lib_id="Fenolite:Inductor", footprint="Fenolite:Chip_0805")` is called
- **THEN** the part's path is `"L"`

#### Scenario: No prefix known
- **WHEN** `design.part(lib_id="Device:Crystal", footprint="Crystal:HC49")` is called
- **THEN** `DslError` is raised, saying "give a ref, a prefix or a device"

### Requirement: Automatic reference designators
`fenolite.dsl.lock.assign_refs(design, lock, *, moves) -> RefAssignment` SHALL be pure and return `refs` (path → ref), the new `lock`, `changes` and `issues`. Explicit refs MUST be kept. A lock entry of a part MUST keep its ref unless that ref is another part's explicit ref (`taken`) or does not start with the part's prefix (`prefix-changed`). Each part still without a ref MUST get, per prefix in natural path order, the lowest `n ≥ 1` with `<prefix><n>` unused.

#### Scenario: First assignment
- **GIVEN** a design with unnamed device parts at `ch10/R`, `ch2/R` and an explicit `R1`, and no lock
- **WHEN** `assign_refs` runs
- **THEN** `ch2/R` gets `R2` and `ch10/R` gets `R3`, and `R1` is kept

#### Scenario: Locked refs are kept
- **GIVEN** a lock holding `"ch10/R" = "R7"`
- **WHEN** a part `ch3/R` is added and `assign_refs` runs
- **THEN** `ch10/R` keeps `R7`, and `ch3/R` gets the lowest free number

#### Scenario: Explicit ref takes a locked number
- **GIVEN** a lock holding `"ch2/R" = "R2"` and a new part with the explicit ref `R2`
- **WHEN** `assign_refs` runs
- **THEN** the explicit part keeps `R2`, `ch2/R` gets a new ref, and `issues` holds `lock.ref-taken` naming `ch2/R`

### Requirement: Natural path order
New refs SHALL be given in natural path order. A path is split into maximal runs of digits and non-digits. Runs are compared in turn: two digit runs by integer value and then by length, two non-digit runs by code point, and a digit run before a non-digit run. The order MUST NOT depend on statement order, `--seed` or `PYTHONHASHSEED`.

#### Scenario: Order independent of the script
- **GIVEN** two scripts that create the same unnamed parts in opposite statement orders
- **WHEN** `uv run pytest tests/unit/dsl/test_lock.py -k order` assigns refs in two processes with `PYTHONHASHSEED=1` and `2`
- **THEN** the four assignments are equal

### Requirement: Refs reach the model
`to_model(design, *, refs=None)` SHALL give each component the ref of `refs` for its path. Without `refs`, it MUST assign against an empty lock. Ids MUST stay derived from paths, so assigning or changing a ref changes no id. A design whose parts all have explicit refs MUST give the same model bytes as before this requirement.

#### Scenario: Ids do not follow refs
- **GIVEN** a design lowered with `refs={"buck/U": "U1"}` and again with `refs={"buck/U": "U4"}`
- **WHEN** the two models are compared
- **THEN** only `Component.ref` of `buck/U` differs, and every id is equal

### Requirement: Design lock file
The design lock SHALL be the file `<script stem>.lock` beside the design script, or the file named by `--lock FILE`, in canonical TOML of schema `fenolite.lock.v0`. It holds `schema`, `design` (the design name) and the sections `refs` (path → ref), `picks` and `pins`. `fenolite.dsl.lock.lock_text(lock)` MUST give a header comment, `schema`, `design`, then the non-empty sections in that order, with keys sorted by code point, LF line ends, one final newline, and no date or absolute path.

#### Scenario: Canonical bytes
- **WHEN** a lock is read from a hand-formatted file and written with `lock_text` twice
- **THEN** both writes give identical bytes, with the keys of `[refs]` in code-point order and no empty section

### Requirement: Lock reading
`fenolite.dsl.lock.read_lock(text, *, file) -> Lock` SHALL read a lock with `tomllib`. An unknown top-level key, a value of the wrong type, a ref that is not a valid name, or two paths with one ref MUST raise `FormatError` (`FEN-3004`) naming the file and the key. A `design` other than the script's design name MUST give `lock.design-renamed` (info), and the lock is rewritten. Hand edits that are valid MUST be honoured.

#### Scenario: Two paths with one ref
- **WHEN** a lock holding `"a/R" = "R1"` and `"b/R" = "R1"` is read
- **THEN** `FormatError` with code `FEN-3004` is raised, naming both paths

#### Scenario: A hand edit renumbers
- **GIVEN** a lock edited by hand to `"buck/c_out" = "C7"`, and `C7` free
- **WHEN** the design is built with `--dry-run --json`
- **THEN** the component `buck/c_out` has the ref `C7`, and `result.lock.changes` is empty

### Requirement: Reserved lock sections
A lock schema newer than `fenolite.lock.v0`, or a non-empty `picks` or `pins` section, SHALL raise `FormatError` mapped to `FEN-3002`, until the change that defines the section (c0254 for `picks`, c0257 for `pins`) registers its `LockSection`. The read, compare, alias, release, write and freeze steps MUST work on every section through `LockSection(name, resolve)`.

#### Scenario: Picks before c0254
- **WHEN** a lock holding `[picks."buck/c_in"]` with `device = "Fenolite:C_0805"` is read
- **THEN** `FormatError` with code `FEN-3002` is raised, naming `picks`

### Requirement: Design lock in a build
`cmd_build` SHALL read the lock file when it exists, call `assign_refs` with `dsl.moves(design)`, pass `refs` to `to_model`, and plan one write of kind `lock` when the canonical text of the new lock differs from the file's bytes. A lock MUST exist only for a design with a part without an explicit ref, or one that already has a lock file. An error finding plans no lock write. This step is added under "Build command".

#### Scenario: First build writes the lock
- **GIVEN** `examples/lock/design.py`, which has unnamed device parts, and no `design.lock`
- **WHEN** `fenolite build examples/lock/design.py --out B --confirm --json` runs
- **THEN** the exit code is 0, `receipt.written` lists `examples/lock/design.lock` with its SHA-256, and `result.lock.written` is `true`

#### Scenario: Rebuild leaves the lock alone
- **WHEN** the same build runs again with `--confirm`
- **THEN** no write of kind `lock` is planned, `result.lock.written` is `false`, and the lock's SHA-256 is unchanged

#### Scenario: Explicit refs get no lock
- **WHEN** the blink is built with `--confirm`
- **THEN** no file `design.lock` is created, and `result.lock` is `null`

### Requirement: Lock entries follow path aliases
Each alias new → old of `dsl.moves(design)` SHALL carry the lock entries whose key is `old`, or starts with `old/`, to `new`, in every section, with `lock.ref-moved` (info). A lock entry whose path is no part of the design, and that no alias carries, MUST be dropped with `lock.ref-released` (warning) naming the path and the ref.

#### Scenario: Module renamed with moved()
- **GIVEN** a lock holding `"buck/U" = "U1"`, and the script renaming the module to `reg` with `design.moved("buck", "reg")`
- **WHEN** the design is built with `--dry-run --json`
- **THEN** the part `reg/U` has the ref `U1`, `issues` holds `lock.ref-moved`, and the planned lock holds `"reg/U" = "U1"` and no `buck/U`

#### Scenario: Renamed without moved()
- **GIVEN** the same lock and the module renamed to `reg` without an alias
- **WHEN** the design is built with `--dry-run --json`
- **THEN** `issues` holds `lock.ref-released` naming `buck/U` and `U1`

### Requirement: Lock issue codes
The build SHALL report the lock codes `lock.ref-released` (warning), `lock.ref-taken` (warning), `lock.ref-moved` (info), `lock.ref-explicit` (info), `lock.ref-prefix-changed` (info), `lock.design-renamed` (info) and, under `--frozen` only, `lock.changed` (error), which join "Build issue codes". A new ref MUST be listed in `result.lock.changes` with reason `assigned` and give no issue.

#### Scenario: First build is quiet
- **WHEN** `examples/lock/design.py` is built for the first time with `--dry-run --json`
- **THEN** `issues` holds no `lock.*` code, and every entry of `result.lock.changes` has reason `assigned`

### Requirement: Lock in the build result
`result.lock` SHALL be `null` for a design that needs no lock, and otherwise hold `file` (relative to the script folder), `exists`, `written`, `frozen` and `changes`. Each change MUST hold `section`, `key`, `before`, `after` and `reason` (`assigned`, `released`, `moved`, `explicit`, `taken`, `prefix-changed` or `design-renamed`), sorted by section and key. This key is added under "Build command".

#### Scenario: Changes listed
- **GIVEN** a lock holding `"old/R" = "R9"` for a part that the script no longer has
- **WHEN** the design is built with `--dry-run --json`
- **THEN** `result.lock.changes` holds `{"section": "refs", "key": "old/R", "before": "R9", "after": null, "reason": "released"}`

## MODIFIED Requirements

### Requirement: Design structure and names
`Design(name)`, `Module(name)` and `Part(ref=None, lib_id=None, footprint=None, value="", *, device=None, name=None, prefix=None, ...)` SHALL build a tree whose paths name every component, and SHALL raise `DslError` at the offending call for every structural error of this list.
- A design name MUST match `^[A-Za-z0-9][A-Za-z0-9_.-]*$`, because it becomes the stem of the KiCad files. Module names, part names, refs and keys MUST match `[A-Za-z0-9_.+-]+`.
- `Design.add(*objs)` and `Module.add(*objs)` attach parts, modules, nets and interfaces; `Design.part(...)` and `Module.part(...)` create a part and attach it. `Module.path` is the module name at the top and `<parent path>/<name>` below. A component path is `<module path>/<key>` (`power/ldo/C1`), or `<key>` at the top, where the key is the part's `name`, else its explicit ref, else its reference prefix ("Parts without a ref").
- Net names are global and literal. A module-local net is named by the script, for example `Net(f"{m.path}/FB")`.
- `DslError` MUST be raised for: a duplicate component or module path; a second unnamed part with one prefix in one container; a part with neither `lib_id` nor `device`, or with both; a part without a ref whose prefix is unknown; a duplicate net, net-class or interface name; two distinct `Net` objects with one name; a net in two classes; a second `place()` or `board()`; a `copper` that is not an `int` of `COPPER_COUNTS` (2, 4, 6 and 8, "Board and placements in the DSL"); one designator connected to two nets; a `side` other than `top` and `bottom`; an invalid name, key or ref.
- Equal refs in different modules are not a DSL error. They are left to `Design.validate()` (`model.duplicate-ref`, exit 5 from `build`). Automatic refs are never equal to each other or to an explicit ref ("Automatic reference designators").

#### Scenario: Paths from modules
- **GIVEN** `Module("power")` holding `Module("ldo")` holding `Part("C1", "Mini:Mini_R")`, added to a design
- **WHEN** `part.path` is read
- **THEN** it is `"power/ldo/C1"`

#### Scenario: Two nets with one name
- **WHEN** `Net("GND")` and a second `Net("GND")` are both added to one design
- **THEN** `DslError` is raised at the second `add()` naming `GND`

#### Scenario: Placed twice
- **WHEN** `r1.place(mm(1), mm(1))` is called twice
- **THEN** the second call raises `DslError`

#### Scenario: Duplicate refs in two modules
- **GIVEN** a blink variant with modules `a` and `b`, each holding a part `R1` of `Mini:Mini_R`
- **WHEN** the design is built with `fenolite build ... --dry-run`
- **THEN** the exit code is 5 and `issues` holds `model.duplicate-ref`

#### Scenario: Invalid design name
- **WHEN** `Design("my board")` is called
- **THEN** `DslError` is raised naming the pattern

#### Scenario: Path from a name
- **GIVEN** `Module("sensor")` added to a design
- **WHEN** `sensor.part(name="R_pull_sda", device="Fenolite:R_0603")` is called
- **THEN** the part's path is `"sensor/R_pull_sda"`

### Requirement: Reproducible builds
Two builds of the same script for the same target SHALL give byte-identical files under `--out`, `.fenolite/` included and `.bak` files excluded, whatever the values of `--seed`, `--timestamp` and `PYTHONHASHSEED` (S-0072). The design lock beside the script SHALL be byte-identical too.
- Every output collection MUST be sorted by name or path. Library table uris MUST be `${KIPRJMOD}`-relative. Outputs MUST hold no date and no absolute path.
- `--seed` changes nothing, because DSL ids are keyed (`design-model`, "Identifier derivation") and automatic refs follow natural path order ("Natural path order"). `--timestamp` is accepted and unused, because a build writes no date (no command generates a title-block date; `TitleBlock.date` is set by the user, c0012). Both follow the MODIFIED `cli-contract` "Determinism flags".
- A build MUST leave the script folder unchanged — the same file list, the same SHA-256 values and no `__pycache__` — except for the design lock, which a build writes only when its content changes ("Design lock in a build"). A second build of an unchanged script MUST leave the script folder unchanged, the lock included.
- Deleting `.fenolite/` and building again MUST restore identical bytes, and MUST NOT change the lock.

#### Scenario: Twice in-process and twice by subprocess
- **WHEN** `uv run pytest tests/unit/lens/test_build_determinism.py` builds the blink for targets 9 and 10 twice in-process, and twice by subprocess with `PYTHONHASHSEED=1` and `--seed 1`, then `PYTHONHASHSEED=2` and `--seed 2`
- **THEN** for each target every file under `--out` is byte-identical across the four builds

#### Scenario: Script folder unchanged
- **WHEN** the blink is built with `--confirm`
- **THEN** `examples/blink_2layer/` holds the same files with the same SHA-256 values as before, and no `__pycache__`

#### Scenario: Cache regenerated
- **GIVEN** a confirmed blink build whose `.fenolite/` folder is deleted
- **WHEN** the build runs again with `--confirm`
- **THEN** `.fenolite/` holds the same seven files with the same bytes as before

#### Scenario: Lock reproducible
- **WHEN** `uv run pytest tests/unit/lens/test_build_determinism.py -k lock` builds `examples/lock/design.py` from a copy without a lock, in two processes with `PYTHONHASHSEED=1` and `--seed 1`, then `PYTHONHASHSEED=2` and `--seed 2`
- **THEN** the two written locks are byte-identical, and a third build of each copy leaves its script folder unchanged
