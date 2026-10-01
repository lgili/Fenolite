## Why

The next four changes (c0009, c0017, c0018, c0010) add 20 rows to `docs/hypotheses.md` and cite them across the tree. Only one test reads that register, to check the hypothesis ids of `tokens.toml`; nothing checks its integrity or the ids cited in text. Two refuted rows still say `INFERRED` (`H-K-SEXPR-NUM-WRITE`, `H-K-TOK-FUTURE`), and two ids cited by archived designs were never registered (`H-K-LIB-DRC`, `H-G-SHAPELY-GC`). The author's earlier write validation of second-backend files is recorded nowhere, and its label must never promote an operation. The licence cell of S-0002 still says "to verify". Split-off changes now start at c0017, which is written nowhere, and ADRs are numbered by allocation, while `docs/adr/README.md` says "in order of creation".

## What Changes

- `src/fenolite/verify/` (new; stdlib only, imports only `core`):
  - `hypotheses.py`: `HypothesisRow`, `load_register`, `load_families`, `parse_level`, `cited_ids`, `proposed_ids`. `parse_level` reads qualified labels such as `KICAD-VERIFIED (9.0.x, 10.0.x)` and `ALTIUM-VERIFIED(author-report; AD 24.x; <date>; no artefact)`.
  - `evidence.py`: `release_verified(level)`, true only for the kit, KiCad, oracle and corpus levels; `is_release_evidence(row)`, false for every refuted row.
- `tests/unit/test_hypotheses_register.py` (new guard) checks:
  - 8 columns, parseable levels and unique ids;
  - a registered successor for every refuted row;
  - every id cited in live text (`docs/`, `openspec/specs/`, active changes, `src/`, `tests/`, `tools/`, top-level `*.md`) is registered.

  Family stems, reserved families, ids proposed by active changes and a per-file allowlist for two synthetic test literals are accepted.
- Register hygiene in `docs/hypotheses.md`:
  - the two refuted rows take the level of the refuting run, and their result becomes `refuted; superseded by …`;
  - `H-K-LIB-DRC` (settled by c0017) and `H-G-SHAPELY-GC` (boolean backends, v0.3) are registered as pending;
  - the header states the id prefixes and gains a reserved-families table.
- Author-report rows: `H-A-WRITE-*`, one per validated file type, and `H-A-PH-*`, one per placeholder or omission choice. They use generic format terms, commit no artefact, and need files and a tool licence the author may use (`LEGAL.md`). If the author's values are missing, the rows are `INFERRED`, `pending (author report)`.
- S-0002 licence cell settled. `openspec/README.md` gains a "Change ids" table (c0009–c0016 plan items, c0017–c0025 split-offs; `tokens.yaml` means `tokens.toml`). `docs/adr/README.md` numbers ADRs by allocation: ADR-0002 is written by c0009, later ADRs take the next free number, and nothing is reserved.

Budget: 3 working days (design, "Budget").

## Capabilities

### New Capabilities
- `verification-evidence`: label grammar, register format and integrity, cited-id guard, release-verified levels, author-report policy and rows, change-id and ADR numbering.

### Modified Capabilities
- (none)

## Non-goals

- The generated evidence matrix and `capabilities` from `# evidence:` markers, with CI failing on undeclared levels (v0.2a).
- Re-running `H-K-00` to `H-K-03`, which c0007 settled.
- `ALTIUM-VERIFIED(kit)` results and the verification kit (v0.4).
- CI matrix, wheel job, DCO check and the history residue scan (c0025).
- Any second-backend code or format page.
- The licence check of the public second-backend library that the project plan names; it moves to the second-backend change (v0.3+).

## Evidence level required

- Parsers, guard and `release_verified`: mechanical (unit tests); no format claim.
- Relabelled rows: the level of the refuting run, already recorded (`KICAD-VERIFIED`).
- `H-A-*` rows: `ALTIUM-VERIFIED(author-report; …)`, never release-verified. `ALTIUM-VERIFIED(kit)` needs the kit (v0.4).
- `H-K-LIB-DRC` and `H-G-SHAPELY-GC`: `INFERRED`, pending.
- The `kicad-9` and `kicad-10` jobs stay green and unchanged.

## Impact

- New package `fenolite.verify`, tests under `tests/unit/verify/`, and the guard.
- Edits to `docs/hypotheses.md`, `docs/evidence/sources.md`, `docs/evidence/README.md`, `openspec/README.md` and `docs/adr/README.md`.
- No runtime dependency and no CLI change; model and schemas unchanged. No `PROVENANCE.md` or `LEGAL-ANNEX.md` row, because no backend or format page is touched.
- Depends on nothing. c0009, c0017, c0018 and c0010 depend on it.
