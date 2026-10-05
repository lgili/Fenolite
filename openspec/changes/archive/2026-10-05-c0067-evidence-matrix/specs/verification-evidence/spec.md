## ADDED Requirements

### Requirement: Declared levels agree with the register
`fenolite.verify.report_problems(evidence, rows) -> list[str]` SHALL return one message for each hypothesis of `evidence` that has no row in `rows`, whose row is refuted, or whose row has a level weaker than the level of `evidence`. It is the function that `tests/unit/test_capability_evidence.py` defined (`backend-protocol`, "Capability reports"), moved into `fenolite.verify.evidence` with the same behaviour and re-exported from `fenolite.verify`. The package MUST still import only the standard library and `fenolite.core` ("Verification package").
- `tests/unit/test_evidence_register.py` MUST call it, with the rows of `docs/hypotheses.md`, for every constant of every module of every backend package (`fenolite.backends.matrix.module_claims`) and for every cell that is set in every row of `fenolite.backends.matrix.rows()`, and MUST fail when any call returns a message. The failure names the package, the module and the constant, or the row and the operation.
- A declared level MAY be weaker than every row it names: a row states what its test covered, and a declaration states what holds for an arbitrary file.
- The capability report keeps its own test; this requirement extends the same rule from the two constants of that report to every declaration of a backend.

#### Scenario: Live declarations agree
- **WHEN** `uv run pytest tests/unit/test_evidence_register.py -k live` checks every backend constant and every matrix cell against `docs/hypotheses.md`
- **THEN** it finds no problem

#### Scenario: Declaration stronger than its row
- **GIVEN** an evidence of level `KICAD-VERIFIED` that names `H-K-LIB-READ`, and the register, in which that row is `INFERRED`
- **WHEN** `fenolite.verify.report_problems(evidence, rows)` is called
- **THEN** it returns one message naming `H-K-LIB-READ`, `KICAD-VERIFIED` and `INFERRED`

#### Scenario: Weaker declaration is accepted
- **GIVEN** an evidence of level `INFERRED` that names `H-K-PCB-WRITE`, whose row is `KICAD-VERIFIED`
- **WHEN** `report_problems` is called
- **THEN** it returns an empty list

#### Scenario: Function moved, not copied
- **WHEN** `uv run pytest tests/unit/test_capability_evidence.py tests/unit/verify` runs
- **THEN** it passes, and `grep -c 'def report_problems' tests/unit/test_capability_evidence.py` prints `0`

### Requirement: Generated evidence matrix page
`tools/gen_evidence_matrix.py` SHALL render `docs/evidence/matrix.md` from `fenolite.backends.matrix` and `docs/hypotheses.md`, and with `--check` SHALL write nothing and exit 1 when the committed page differs from a fresh rendering, with a message that names the page and the command that regenerates it.
- The page MUST hold, in this order:
  1. a header saying that the page is generated, by which tool and from what, and that it is not edited by hand;
  2. the meaning of the five operations, in the words of `backend-protocol`, "Evidence matrix rows";
  3. **Matrix**: one line per row of `rows()` with the backend, the kind, the five cells and `verified_by`. A cell shows its label, `—` when it is not set, and the mark `(experimental)` when its operation is listed in the row's `experimental`;
  4. **Hypotheses**: one line per id named by any row, sorted, with the level text of its register row as written there, scope included;
  5. **Modules**: for each backend package, one line per module of `module_claims`, with its constants (name, label and ids), or the modules its marker names, or its reason for claiming nothing.
- The rendering MUST be a function of the working tree only: no date, no tool version and no absolute path. Two runs MUST give the same bytes, in UTF-8 with `\n` line endings.
- `tests/unit/test_evidence_matrix_page.py` MUST fail when the committed page is stale, so a change that alters a declaration, a matrix row, or the level text of an id the matrix names has to regenerate the page.
- `docs/evidence/README.md` MUST name the page and its generator.

#### Scenario: Committed page is current
- **WHEN** `uv run python tools/gen_evidence_matrix.py --check` runs on the repository
- **THEN** it exits 0 and writes nothing

#### Scenario: Stale page is reported
- **GIVEN** a copy of the page with one cell changed
- **WHEN** `uv run pytest tests/unit/test_evidence_matrix_page.py -k stale` compares it with a fresh rendering
- **THEN** the comparison fails, and the tool's message names `docs/evidence/matrix.md` and `tools/gen_evidence_matrix.py`

#### Scenario: Rendering is repeatable
- **WHEN** the page is rendered twice in the same working tree
- **THEN** the two texts are equal, and neither holds a date of the run or a path that starts with `/`

#### Scenario: Register level shown next to the id
- **GIVEN** the row of `H-K-PCB-WRITE` in `docs/hypotheses.md`, whose level text names a level and the KiCad versions it was checked on
- **WHEN** the page is rendered
- **THEN** its "Hypotheses" section holds one line with `H-K-PCB-WRITE` and that level text, scope included

#### Scenario: Module without a claim is visible
- **GIVEN** a backend module that carries `# evidence: none, error classes only`
- **WHEN** the page is rendered
- **THEN** its "Modules" section holds one line with the module's name and `error classes only`
