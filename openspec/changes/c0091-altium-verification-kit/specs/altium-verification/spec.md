## ADDED Requirements

### Requirement: Verification kit contents
`fenolite.verify.kit.build_kit(out, *, seed, timestamp)` SHALL write the verification kit: `kit.json` with the schema `fenolite.altium-kit.v0`, `STEPS.md`, `results/form.json`, and one folder per sample with the Altium project that Fenolite builds from the sample's script under `examples/kit/`.
- `kit.json` MUST hold the kit version, the Fenolite version, every sample with the SHA-256 of each of its files, and every step. `kit_digest` MUST be the SHA-256 of the canonical bytes of `kit.json`.
- Two builds with the same seed and timestamp, on any supported operating system, MUST give equal bytes for every file.
- The kit MUST hold no file that Fenolite did not write, no absolute path and no file from outside this repository's scripts.
- `STEPS.md` MUST be generated from the steps of `kit.json`, so the two cannot differ.

#### Scenario: Deterministic kit
- **WHEN** `fenolite kit build --out a --seed 1 --timestamp 2026-10-06T00:00:00Z --confirm` runs twice into two folders
- **THEN** the two folders hold equal files, and `kit.json` lists five samples

#### Scenario: Nothing foreign
- **WHEN** `uv run pytest tests/unit/verify/kit/test_manifest.py -k contents` walks a built kit
- **THEN** every file is listed in `kit.json` with its digest, and no file holds an absolute path

### Requirement: Kit steps settle hypotheses
`fenolite.verify.kit.steps.STEPS` SHALL be the closed list of the kit's steps. Each step MUST hold an id of the form `K<group>.<n>`, a sample, an instruction of at most two sentences that names Altium's menu path, a result that is either `file` (a path under `results/`) or `form` (a field of `form.json` with its type), the expected value, and the register ids it settles.
- Every step that can end in a file that Altium writes MUST be a `file` step.
- Every hypothesis row whose settling test is a kit step MUST be named by at least one step, and every id a step names MUST be a register row; among them `H-A-WRITE-SCHLIB`, `H-A-WRITE-PCBLIB`, `H-A-WRITE-SCHDOC`, `H-A-WRITE-PCBDOC` and the four `H-A-PH-*` rows.
- The instruction texts MUST NOT quote Altium's documentation beyond menu names.

#### Scenario: Steps and register agree
- **WHEN** `uv run pytest tests/unit/verify/kit/test_steps.py -k register` compares `STEPS` with `docs/hypotheses.md`
- **THEN** every id a step names is registered, and every row that names a kit step as its test is covered

### Requirement: Kit result verification
`fenolite.verify.kit.results.verify_results(folder)` SHALL check a kit folder after a run and SHALL return a verdict per step and per hypothesis, without writing anything.
- The kit's own files MUST match `kit.json`; a changed sample MUST fail every step of that sample.
- `form.json` MUST validate against its schema and MUST name the Altium version as `AD <major>.<minor>`.
- A re-saved document MUST pass RT-A0 and RT-A1, and its import MUST equal the model that the sample was built from at levels 1 to 5 of `equivalent`, within the kit profile, whose every exclusion names its cause. The stages `parity` and `copper.clearance` MUST report on it what they report on Fenolite's own file, except where a step expects otherwise (polygons poured after a repour).
- A `form` value MUST equal its expected value.
- `privacy_scan` MUST list the strings of the result files that look like a home folder path or a login name, with the file and the offset, and the verdict MUST carry the list.
- A hypothesis passes when every step that names it passes; it is marked `form` when any of those steps is a `form` step.

#### Scenario: A simulated run passes
- **GIVEN** a kit whose `results/` were filled by `tests/unit/verify/kit/_simulate.py` (Fenolite's writers standing in for Altium, the record marked synthetic)
- **WHEN** `verify_results` runs
- **THEN** every step passes, and the verdict is marked synthetic

#### Scenario: A lost net is caught
- **GIVEN** the same run with one net removed from the re-saved PCB document
- **WHEN** `verify_results` runs
- **THEN** the step that re-saves that document fails, naming the net, and the hypotheses of that step fail

#### Scenario: A touched sample
- **GIVEN** a kit whose sample file was edited
- **WHEN** `verify_results` runs
- **THEN** every step of that sample fails with the reason that the kit file differs from its manifest

### Requirement: Kit run record
`fenolite.verify.kit.record.run_record` SHALL turn a verdict into a run record with the schema `fenolite.altium-kit-run.v0`: the run id, the kit digest, the Fenolite version, the Altium version, the operating system family, the outcome of each step with its kind (`file` or `form`), the verdict of each hypothesis, and the SHA-256 and size of every result file and of the archive.
- The record MUST hold no path outside the kit, no user name and no machine name.
- A synthetic verdict MUST NOT give a record.
- Committed records live in `docs/evidence/altium-kit/`, one file per run, and are never edited after they are committed.
- `stale_rows(register, records, kit)` MUST return the register rows whose label names a run whose kit digest, for the samples that the row's steps use, differs from the kit that the tree builds.

#### Scenario: Record of a run
- **GIVEN** a verdict with every step passed
- **WHEN** `run_record` runs
- **THEN** the record validates against its schema, names the archive by digest, and holds no absolute path

#### Scenario: A stale run
- **GIVEN** a register row labelled with a run, and a writer change that alters the bytes of that row's sample
- **WHEN** `stale_rows` runs
- **THEN** it returns that row
