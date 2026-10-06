## Why

Fenolite has two labels for what Altium confirms. `ALTIUM-VERIFIED(author-report)` is the maintainer's word after ordinary use: it is recorded "no artefact", it is not release-verified, and it never promotes an operation. `ALTIUM-VERIFIED(kit)` is the strongest level of the project and is release-verified; the README defines it as "confirmed by a native-tool acceptance run with archived results". No such run exists, and nothing says what the kit is: it is named in the README, in the roadmap and in eight register rows (`H-A-WRITE-*`, `H-A-PH-*`, "kit request (v0.4)") and described nowhere.

So today no Altium write can ever leave `experimental`, whatever the maintainer sees in Altium, and the rows that he confirmed stay author reports. Altium cannot run in CI and Fenolite must not automate it from inside. The kit is the answer the project plan chose: a fixed acceptance run that a person performs in Altium on their own machine, whose results are files that Fenolite can check and that are archived.

## What Changes

- **The kit**: a folder that `fenolite kit build` writes, with sample projects built from committed scripts, a manifest of every file's SHA-256, a numbered checklist, and a result form. It is the same for everyone and reproducible byte for byte.
- **The run**: the user performs the steps in Altium. Each step either ends in a file that Altium writes into `results/` (a document saved under a given name, an exported report) or in a value typed into the form.
- **Machine checks**: `fenolite kit verify DIR` reads the results. The documents that Altium re-saved are read with Fenolite's readers and compared with the model each sample was built from (`equivalent` levels 1 to 5 and the parity and copper checks); the form is checked for completeness; the kit's own files are checked against the manifest.
- **The record**: `fenolite kit record DIR` writes a small result record into the repository (`docs/evidence/altium-kit/<run>.json`: tool version, date, kit digest, outcome per step, verdict per hypothesis, digests of the archived files) and prints the register rows to update. The archive of `results/` is kept outside the repository and named by its digest.
- **The label rule**: when a row becomes `ALTIUM-VERIFIED(kit; …)`, and what a run can and cannot prove.
- **The eight waiting rows** (`H-A-WRITE-*`, `H-A-PH-*`) get kit steps, so the reserved families can be closed.

Size: 6.25 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `altium-verification`: ADDED "Verification kit contents", "Kit steps settle hypotheses", "Kit result verification", "Kit run record".
- `verification-evidence`: ADDED "Kit label rows"; "Reserved id families" loses the two Altium families once their rows are settled.
- `cli-contract`: ADDED "Kit command".

## Non-goals

- No script, extension or automation that runs inside Altium, and no driving of Altium's user interface (see the open decision).
- No Altium file of any third party in the kit: every sample is built by Fenolite from a script in this repository.
- No check of what a person saw without a file: a typed value is recorded as typed and can settle only the rows whose criterion is a typed value; such rows are marked `form` in the record.
- No upload: Fenolite writes local files; where the archive is published is the maintainer's choice.
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- The kit's machinery (build, verify, record) is ordinary code with unit tests; its evidence is the samples' own.
- A register row becomes `ALTIUM-VERIFIED(kit; AD <version>; <date>; <run id>)` only through a recorded run whose steps for that row passed and whose machine checks passed.
- A run proves the samples on one Altium version on one machine. The label carries the version; c0092 decides what that is enough for.

## Open decision for the maintainer

- **Question.** May the kit contain a script that runs inside Altium (to open, compile, export and save without clicks), or is it a checklist plus exported files only?
- **Default written here.** Checklist plus exported files only. The user clicks; Altium writes the result files with its own menus.
- **Alternative.** An authored script (written for Fenolite from Altium's public scripting documentation, nothing copied) that performs the same steps and writes the same result files.
- **To switch.** Add the requirement "Kit script" to this change's `altium-verification` delta (the script is one more kit file with its digest in the manifest; the steps it automates are marked `scripted` in the record; the result files and `kit verify` do not change) and one task with its own source rows. The label rule does not change, because the evidence is the result files either way.

## Impact

- New: `src/fenolite/verify/kit/` (`manifest.py`, `steps.py`, `results.py`, `record.py`), `cli/cmd_kit.py`, `docs/altium-kit.md`, `docs/evidence/altium-kit/README.md`; the kit's sample scripts under `examples/kit/`.
- Changed: `docs/hypotheses.md` (the label of settled rows, the reserved-families table), `README.md` (one sentence that links the kit page), `docs/evidence/README.md`.
- Depends on: c0084, c0085, c0086, c0087 (the samples use what they write); c0088 and c0089 (`kit verify` runs their checks); c0090 (the re-saved documents are compared through the import). The change can be written and unit-tested before them; its first real run needs them.
