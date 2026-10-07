## Why

At the end of v0.3 every Altium write is still marked `experimental`, because that is how each writer was introduced and nothing defines when the mark comes off. A user sees `experimental` on `build --target altium` whatever the evidence is, and the capability report lists no Altium write kind. The write part of v0.3 has no acceptance block in the roadmap, so nobody can say that the milestone is done.

This is the closing change of the milestone. It defines the rule by which a write kind leaves `experimental`, applies it after the first recorded kit run, states what the write part of v0.3 delivers and what it does not, and removes the texts that the other nine changes made stale.

## What Changes

- **A graduation rule**, written as a requirement and checked by a test: a write kind leaves `experimental` when its own readback holds, RT-A3 holds for it over the corpus, and every hypothesis its claims cell names is release-verified (`ALTIUM-VERIFIED(kit)`, `ORACLE-VERIFIED`, `CORPUS-VERIFIED`).
- **The first kit run recorded** and the rows it settles relabelled; what the run did not settle stays where it is, by name.
- **The v0.3 acceptance run**: one script that builds the acceptance project for both targets, checks it, rewrites it and compares it, and the kit run on top; its results in `docs/evidence/altium-acceptance.md`.
- **Capabilities and notices**: `capabilities` lists the graduated kinds as write kinds; `build --target altium` says `experimental` only for the kinds that still are.
- **Documentation**: `docs/altium.md` "Limits" rewritten from the written scope; the roadmap's Phase 4 and milestone rows; the conformance rows of the matrix.

Size: 3.25 design-days (a size, not time); cut order in the design.

## Capabilities

### New Capabilities
None.

### Modified Capabilities
- `backend-protocol`: ADDED "Graduation of a write kind"; supersedes the sentence of "Evidence matrix rows" that every Altium write kind is experimental.
- `altium-build`: ADDED "Experimental notice per kind", "Altium acceptance project"; supersedes the wording of "Altium build evidence".
- `cli-contract`: ADDED "Altium kinds in capabilities"; supersedes the Altium list of "Experimental features in capabilities".

## Non-goals

- No new writer and no new format fact.
- No graduation by decision: a kind whose evidence is short stays `experimental`, and the change says which evidence is missing.
- No claim about Altium versions other than the one(s) of the recorded runs.
- No conversion command (v0.5a).
- No code or constant from any private project or organisation; test data is authored for Fenolite or fetched from the public rows of the corpus manifest.
- No format fact from a decompiled tool or a transcribed parser: every fact gets a row in `docs/formats/altium/*.md` with a public source of `docs/evidence/sources.md` and a label.

## Evidence level required

- The rule is code and a test; it carries no evidence of its own.
- After graduation, the envelope of `build --target altium` is the lowest level of the kinds it wrote: `ALTIUM-VERIFIED(kit)` at best, never above what the register rows hold.
- The acceptance page records the run with the versions of Fenolite, KiCad and Altium, and the kit run id.

## Impact

- Changed: `backends/altium/claims.py`, `backends/altium/backend.py` (`CAPABILITIES.write_kinds`), `lens/altium.py` (notice), `cli/cmd_capabilities.py`, `backends/base.py` (the graduation check), `tools/gen_evidence_matrix.py`.
- Pages: `docs/altium.md`, `docs/roadmap.md`, `README.md` (the second backend's status line), `docs/evidence/altium-acceptance.md` (new), `docs/evidence/matrix.md` (generated), `agent/SKILL.md` (the target's status).
- Depends on: c0083 to c0091, all archived; a recorded kit run.
