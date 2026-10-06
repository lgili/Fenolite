## Why

Fenolite states an evidence level for everything it reads and writes, but the statement is scattered. Of the 60 modules under `src/fenolite/backends/`, 27 hold an `EVIDENCE` constant and 33 hold none, and the only summary, the capability report, carries one level for a whole backend. An agent cannot ask "can I round-trip a drawing sheet, and how well is that verified", and a reviewer cannot see that a new module claims nothing. A table written by hand would go stale, which is the failure the plan warns about: a writer that was validated while its documents said the opposite.

Plan D13 and D8 give v0.2a the remedy: the matrix `detect / read / write / roundtrip_exact / roundtrip_modified / verified_by` and `capabilities` are generated from the declarations in the code, and CI fails when a backend module declares no level.

## What Changes

- **Matrix rows.** `MatrixRow` in `backends.base`: one row per backend package and file kind, one cell per operation. Each cell is an evidence constant of a module of that package, never a literal. Each package places its constants in `claims.py`; `fenolite.backends.matrix.rows()` collects them.
- **`capabilities`.** `result.matrix` lists the rows: a level label or `null` per operation, `verified_by` (the hypothesis ids behind the row) and `experimental` (the operations that may change in any release).
- **Every backend module declares.** A module holds evidence constants, or one marker comment: `# evidence: see <module>` for a helper covered by another module, `# evidence: none, <reason>` for a module that states nothing about a format or a tool. A unit test fails for a module with neither. The audit adds the 33 missing declarations.
- **Declared levels agree with the register.** Every constant of a backend module passes the rule the capability report passes today (`report_problems`, which moves into `fenolite.verify`). An `INFERRED` level names a hypothesis. An `UNVERIFIED` cell is allowed only as experimental.
- **Generated page.** `tools/gen_evidence_matrix.py` writes `docs/evidence/matrix.md`: the matrix, the register level of each id it names, and each module's declaration. A drift test fails when the page is stale.

Size: 5 design-days.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `backend-protocol`: ADDED "Evidence matrix rows", "Backend modules declare their evidence".
- `altium-schematic-reader`: MODIFIED "Schematic reader entry points" (`read.sch.EVIDENCE` names no refuted row).
- `cli-contract`: ADDED "Evidence matrix in capabilities".
- `verification-evidence`: ADDED "Declared levels agree with the register", "Generated evidence matrix page".

## Non-goals

- No level is raised or lowered: the audit declares what the code already claims. Raising a level needs its own evidence.
- No version dimension (format × version × operation): that is the conformance matrix of v1.0.
- No rows for tool reports (DRC and ERC JSON, IPC-D-356, netlist export, plots): their modules appear in the page's module list.
- No guard outside `backends/`: `checks`, `lens`, `exports` and the routing plug-ins keep their constants unchecked.
- No change to `result.backends`, to `result.experimental` or to `CapabilityReport`.
- No reading of `docs/hypotheses.md` at run time: the register is joined on the page only.

## Evidence level required

Mechanical. The matrix repeats levels that modules declare and adds none, so the proof is by unit tests and no oracle runs. The page shows, next to each id, the level its register row holds.

## Impact

- New: `backends/matrix.py`; `backends/{kicad,altium,specctra}/claims.py`; `tools/gen_evidence_matrix.py`; `docs/evidence/matrix.md`; four test modules.
- Changed: `backends/base.py`; `verify/evidence.py`; `cli/cmd_capabilities.py`; `docs/cli-contract.md`; `docs/evidence/README.md`; one declaration in each backend module that has none.
- Order: best last among the v0.2a changes, so that its audit covers their new modules. If it lands earlier, each later module meets the guard when it lands, and the test says what to add.
