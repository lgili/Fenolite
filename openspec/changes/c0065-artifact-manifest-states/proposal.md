## Why

`fenolite-artifacts.json` says today which fabrication files one `export` run made from which board (c0024). It does not say whether that board was ever checked, it does not list the design files themselves, and it is replaced by every run. An agent that hands a folder to a fabricator, or a person who receives one, cannot tell from the manifest which files were verified, by what, and whether they still are the files that were verified.

The plan gives v0.2a the "complete `fenolite-artifacts.json` (`generated | checked | roundtrip-ok | oracle-verified | native-verified`)", with the acceptance "manifest with sha256 and state on every artefact", and a `manifest` command.

## What Changes

- The manifest entry gains `state`, `stale`, `from` (the hash of the source the file was made from) and `tool`; the manifest gains `project`, `check` and `states`. Schema id unchanged (`fenolite.artifacts.v0`), fields added only.
- Five states, in order: `generated`, `checked`, `roundtrip-ok`, `oracle-verified`, `native-verified`, each with a rule per kind of file. A file reaches a state only with every lower rung that applies to it.
- `--manifest` merges: `export`, `render`, `bom` and `pnp` add their files to the manifest of their output folder instead of replacing it, each entry `generated`.
- `fenolite manifest PATH` (new): lists the design files of a project and the artefacts of the folders it is given, hashes every file again, runs the stages of `check`, assigns the states and writes the project manifest. `--no-check` records hashes only; `--verify` compares an existing manifest with the files on disk and writes nothing.
- A manifest written by v0.1 stays readable: an entry without `state` is `generated`.

Size: 5 design-days; cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `manufacturing-exports`: MODIFIED "Artefact manifest"; ADDED "Artefact states", "Manifest merging", "Project manifest".
- `cli-contract`: ADDED "Manifest command", "Manifest option of producing commands".

## Non-goals

- No new check: the states are read from the stages `check` already has (c0013, c0020, c0029, c0062).
- No rule assigns `oracle-verified` in v0.2a. It is reserved for an independent tool that is neither the producer of a file nor its format's own application (the nightly oracles of v0.3); the manifest can carry it, and nothing here produces it.
- No signature, no timestamp authority, no upload. The manifest is a statement Fenolite makes about files on one machine.
- No state for a file that `kicad-cli` produced beyond `checked`: nothing judged that file itself.
- No re-export: a stale artefact is reported, not regenerated.

## Evidence level required

- The states are definitions, checked by unit tests: mechanical.
- A state never claims more than the stage it comes from: `native-verified` requires that stage's own evidence to be `KICAD-VERIFIED`; with a lower level the file stays one rung below.
- The envelope of `manifest` carries the evidence of the stages it ran, as `check` does; with `--no-check` it is `UNVERIFIED`.
- One oracle test on both majors: the built and routed example reaches `native-verified` for its board and schematic, and an unrouted one does not.

## Impact

- Changed: `src/fenolite/exports/manifest.py`, `schemas/fenolite.artifacts.v0.json`, `cli/cmd_export.py`, `cli/cmd_render.py`, `cli/cmd_bom.py`, `cli/cmd_pnp.py`, `docs/exports.md`, `docs/cli-contract.md`.
- New: `src/fenolite/exports/states.py`, `cli/cmd_manifest.py`.
- No model change, no new dependency, no new format fact.
- Depends on c0062 (the ERC stage gives the schematic's state) and on c0064 for the `--manifest` option of `bom` and `pnp`; both can be cut without the rest.
