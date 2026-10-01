## Why

Fenolite will write KiCad files for two targets, 9.0 and 10.0. KiCad rejects unknown tokens almost everywhere, yet `kicad-cli` 10.0.6 loads a board whose header version is newer than its own without complaint (`H-K-TOK-FUTURE`). A writer could thus produce files the user's KiCad refuses, or carry 10.0-only structures into a 9.0 project. The backend needs one sourced answer to "which KiCad reads this token?", a policy for unknown versions, and proof from `kicad-cli` of both majors.

## What Changes

- `backends/kicad/versions.py`: `FileKind`; format-version constants per kind and major 8/9/10 (S-0030, S-0031, S-0032, S-0010, S-0038); detection, development versions (e.g. `20250513`) mapped to the release that reads them; policy: never emit a token newer than the target; downgrade refused (`FEN-7002`, exit 7); newer than known is read-only (`FEN-3002`); older than 8.0 refused with an upgrade hint (`FEN-3003`); `min_version`, `min_major`, `check_emittable`; custom-rules text helpers.
- `backends/kicad/data/tokens.toml` (read with `tomllib`): board/footprint tokens introduced after 8.0 or no longer written by 10.0, the worksheet vocabulary (frozen, S-0032) and the custom-rules vocabulary (gated by major although the header stays `(version 1)`, S-0038); each row has a minimum major and public sources. Value-form changes a path cannot express (nets referenced by name) are form rows. The residue check allows exactly this file name.
- `tools/kicad_token_fuzz.py`: builds minimal files from authored CC0 skeletons, examples and controls, asks `kicad-cli` (native or Docker, isolated from user settings) whether each loads, and writes or checks committed results.
- A `kicad_min_major` test marker, so 10.0-only oracle tests skip on 9.0; CI job `kicad-9` (`kicad/kicad:9.0.9`, pinned digest), which also records c0006's 9.0 results.
- Hypotheses `H-K-00` … `H-K-03` settled by tests: `pcb import` in 10.0; `pcb drc --refill-zones --save-board` in 9.0; Docker images usable; per-layer padstack grammar in pads.
- `docs/formats/kicad/versions.md`, generated `docs/formats/kicad/tokens.md`; sources S-0030 … S-0039; hypotheses `H-K-TOK-*`.

## Capabilities

### New Capabilities
- `kicad-version-gating`: constants, detection, classification, targets, downgrade, rules text, emit check.
- `kicad-token-inventory`: schema, provenance, matching, examples, expectations, results, generated page.
- `kicad-oracle`: per-kind load checks, natively or in Docker; major-aware tests; `H-K-00` … `H-K-03`.

### Modified Capabilities
- `cli-contract`: library format-version and parse errors map to registered codes (`FEN-3002`, `FEN-3003`, `FEN-3004`, `FEN-7002`).
- `ci-baseline`: adds the `kicad-9` job; the token fuzz check runs in both KiCad jobs.
- `residue-scan`: the public format inventory is not a token list.

## Non-goals

- Typed board/footprint readers and writers, the `--kicad-version` flag, the backend capability report: board backend change.
- An exhaustive list of tokens 8.0 already read; the corpus census of observed paths moves to the board backend change.
- Schematic and symbol-library inventories (their version constants only); project and `.kicad_prl` files.
- Downgrade by dropping or rewriting tokens; checking that tokens survive a KiCad re-save.
- A custom-rules reader; KiCad 11; nightly images.

## Evidence level required

- Rows introduced in 10.0, obsolete rows, worksheet rows and form rows: `KICAD-VERIFIED` on 9.0.9 and 10.0.6 from committed fuzz results before merge; rows introduced in 9.0 load on both. A row no load can decide stays `INFERRED` and names a `H-K-TOK-*` hypothesis.
- Version constants: `KICAD-VERIFIED` where a `kicad-cli` command writes or bounds them, else `INFERRED` (`H-K-TOK-CONSTANTS`).
- Gating policy and `check_emittable`: mechanical unit tests; no oracle applies.

## Impact

- New module and data file under `backends/kicad/`, `PROVENANCE.md` and `LEGAL-ANNEX.md` rows, three CLI error codes, tests, CC0 skeletons under `tests/data/kicad/tokens/`, one CI job, one test marker.
- Depends on c0006 (`sexpr`, the `backends/kicad/` package, `kicad-10` job, required-resource mode, its oracle tests). c0008 may use `inspect`/`require_readable`.
- No runtime dependency; model and schemas unchanged.
