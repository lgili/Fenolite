## Context

- **Scope.** Plan v0.2a: "complete `fenolite-artifacts.json` (`generated | checked | roundtrip-ok | oracle-verified | native-verified`)", acceptance "manifest with sha256 and state on every artefact"; plan D8 lists the command `manifest` for v0.2a; plan appendix A, item 16: "machine-readable reports + manifest". c0024 left "a state per artefact and a complete project manifest" to v0.2a.
- **What exists.**
  - `exports/manifest.py`: `Manifest(schema, fenolite, generated, board, tool, artifacts)` and `ArtifactEntry(path, kind, layer, bytes, sha256, content_sha256, evidence)`, written by `export --manifest` into the output folder; the schema is generated from the dataclasses; `content_sha256` ignores date-bearing lines.
  - `render` writes views and no manifest. c0064 adds `bom` and `pnp`, each writing one file with `--out`.
  - `check` is read-only by requirement, so it cannot write a manifest.
  - `.fenolite/build.json` records the SHA-256 of every file a build wrote.
  - The evidence labels: `KICAD-VERIFIED` means that `kicad-cli` accepted a file and confirmed the claim; `ORACLE-VERIFIED(<tool>)` means that an independent tool agreed, and never applies to the producer of an artefact.
- **Constraints.** No absolute path, no user name and no temporary path in a manifest. Stdlib only. `--timestamp` makes the output reproducible.

## Goals / Non-Goals

**Goals:**
- One file per project that lists every file that matters, with its hash and what was verified about it.
- States that cannot overclaim: each is tied to a stage result and to the hash that stage saw.
- A cheap answer to "is this folder still what was verified?".

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- A history. The manifest describes the files as they are now; the mutation protocol keeps the previous manifest as `.bak`.

## Decisions

1. **The five states are a ladder.** In rising order: `generated`, `checked`, `roundtrip-ok`, `oracle-verified`, `native-verified`. `state` is the highest rung a file reaches with every lower rung that applies to its kind.
   - `generated`: Fenolite, or a tool it ran, wrote the file and its hash is recorded. Every entry starts here. A design file that Fenolite did not write is listed with this state too: the manifest then only records its hash.
   - `checked`: the stages `model.validate` and `copper.clearance` ran on the project with status `ok`, and the file is current (Decision 3).
   - `roundtrip-ok`: applies to boards and schematic sheets only. The board's `roundtrip` stage is `ok`; a sheet passes `sch.roundtrip_schematic` (c0060).
   - `oracle-verified`: reserved. An independent tool, neither the file's producer nor its format's own application, agreed with it. No rule of v0.2a assigns it; a kind without a rule skips the rung.
   - `native-verified`: the format's own tool judged the project without an error. Board: `drc.kicad` is `ok` and its stage evidence is `KICAD-VERIFIED`. Sheets: `erc.kicad` is `ok` with `KICAD-VERIFIED`. The project file, the rules file, the library tables and the vendored libraries reach it together with the board, because they are what KiCad loaded to judge it.
   - A derived artefact (fabrication file, table, view) stops at `checked`: it is `checked` when the sources named by its `from` are current and at least `checked`. KiCad produced it; nothing judged it.
   - Rejected: independent flags instead of one state. The plan asks for one state per artefact, and a reader wants one word; the stage results behind it are in `check`.
   - Rejected: `native-verified` for a Gerber because KiCad wrote it. The producer of a file does not verify it (the rule for `ORACLE-VERIFIED`).

2. **Entry and manifest fields** (added; nothing is removed, so a v0.1 manifest still validates after its missing fields take defaults when read):
   - entry: `state`; `stale` (true when a source named by `from` has another hash now); `from` (`{"board": <sha256>}`, `{"schematic": <sha256>}` or both; empty for a design file); `tool` (`kicad-cli <version>`, `fenolite <version>`, or `null` for a file neither wrote).
   - manifest: `project` (`board` and `schematic`, each `{path, sha256, format_version}` or `null`); `check` (`null`, or `{stages: [{name, status, level, oracle}], tool_version}`); `states` (the number of entries per state). `board` and `tool` stay, as c0024 wrote them.
   - Kinds: c0024's `gerbers`, `drill`, `pos`, `ipcd356`; `bom`, `pnp`, `render`; and for design files the file kind (`kicad_pcb`, `kicad_sch`, `kicad_pro`, `kicad_dru`, `kicad_mod`, `kicad_sym`, `kicad_wks`, `lib-table`).

3. **Current files.** An entry is current when its file exists with the listed `sha256` and every hash in its `from` equals the present hash of that source. `fenolite manifest` hashes every file again; a derived entry whose source changed is `stale` and `generated`.

4. **`--manifest` merges.** `manifest.merge(existing, entries, …)` replaces entries by `path` and keeps the others as they are. `export`, `render`, `bom` and `pnp` read `DIR/fenolite-artifacts.json` when it exists (`DIR` is the output folder, or the folder of `--out FILE`), merge their entries with state `generated`, `from` set to the hashes of the board and schematic they read, and `tool` set, and plan the merged file as one write.
   - A manifest that cannot be read or has another schema id is refused (`manifest.unreadable`, error): the command plans nothing rather than overwrite a file it does not understand.
   - Rejected: one manifest per command. Four files in one folder would each describe a part, and none the whole.

5. **`fenolite manifest PATH`** (`cli/cmd_manifest.py`, `mutates=True`). Flags: `--artifacts DIR` (repeatable), `--stages`, `--no-check`, `--verify`, `--out FILE` (default `<root>/fenolite-artifacts.json`), `--kicad-cli`, `--timeout`.
   - **Design files.** The files of `projectset.project_set` (board, project, rules, tables, vendored libraries, the schematic and its sheets). A file whose hash equals the build record's has `tool` `fenolite <version of the record's writer, or the running version>`; any other design file has `tool` `null`.
   - **Artefact folders.** Each `--artifacts DIR` must lie inside `<root>`. The entries of `DIR/fenolite-artifacts.json` are taken with their kind, layer, `from` and `tool`; a file under `DIR` that no entry lists gets `manifest.unlisted` (info) and is not listed; an entry whose file is gone is dropped with `manifest.missing` (warning). Paths are relative to the manifest's folder.
   - **Check.** Unless `--no-check`, the command runs `run_checks` with `--stages` (default `DEFAULT_STAGES`) exactly as `check` does, pre-flight included, and passes the report to `states.assign`. The issues of the check are the command's issues, so the exit code is 5 when the project has an error; the manifest is planned all the same, with the states that hold.
   - **`--verify`.** Reads the existing manifest, hashes every listed file, and reports `manifest.missing` and `manifest.changed` (errors), `manifest.stale` (warning) and `manifest.unlisted` (info). It plans no write, runs no check and no tool.
   - `result`: `manifest` (the path), `project`, `states`, `artifacts` (`path`, `kind`, `state`, `stale`), `check` (the stage list) or, with `--verify`, `verified` and `differences`.
   - Rejected: letting `check` write the manifest. `check` is read-only, and that guarantee is worth more than one command fewer.

6. **`states.assign(entries, *, stages, sheets_ok, current) -> tuple[ArtifactEntry, ...]`** in `exports/states.py`, pure: it takes the entries, a mapping of stage name to `(status, evidence level)` (empty when no check ran), the RT1 verdict of each sheet and the present hashes, and returns the entries with `state` and `stale`. `exports` may not import `checks` (its layering row allows `model`, `geometry` and backends), so the command builds the mapping from the `CheckReport`.

7. **Determinism.** With `--timestamp`, two runs on unchanged files give byte-identical manifests. Entries are sorted by path; `states` and `check.stages` have fixed orders. A date-bearing artefact keeps its `content_sha256` for comparison across exports.

8. **No hypothesis.** Nothing here claims a fact about a tool or a format. The stage results carry their own evidence; this change copies none above its source.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/exports/manifest.py` (extended) | `ArtifactEntry` with `state`, `stale`, `from_`, `tool`; `Manifest` with `project`, `check`, `states`; `STATES`; `load(text) -> Manifest`; `merge(existing, entries, *, board, tool, timestamp) -> Manifest`; `design_kind(path) -> str` |
| `src/fenolite/exports/states.py` (new) | `assign(entries, *, stages, sheets_ok, current) -> tuple[ArtifactEntry, ...]`; `RULES`; `rank(state) -> int` |
| `schemas/fenolite.artifacts.v0.json` (regenerated) | the added fields; `state` is one of `STATES` |
| `src/fenolite/cli/cmd_manifest.py` (new) | `COMMAND` (`manifest`, `mutates=True`) |
| `src/fenolite/cli/cmd_export.py`, `cmd_render.py`, `cmd_bom.py`, `cmd_pnp.py` (extended) | `--manifest` merges; `render`, `bom` and `pnp` gain the option |
| `src/fenolite/exports/codes.py` (extended) | `manifest.unreadable`, `manifest.missing`, `manifest.changed`, `manifest.stale`, `manifest.unlisted` |
| `tests/unit/exports/test_manifest.py`, `tests/unit/cli/test_export_cmd.py`, `test_render_cmd.py` (extended); `tests/unit/exports/test_states.py`, `tests/unit/cli/test_manifest_cmd.py` (new) | hermetic |
| `tests/kicad/export/test_manifest_oracle.py` (new) | the states of the examples on both majors |
| `docs/exports.md`, `docs/cli-contract.md` (extended) | the states with their rules, the command, the codes |

## Sources registered by this change

None. No format fact and no tool behaviour is added. S-0345 to S-0349 stay unused.

## Hypotheses registered by this change

None. The states are definitions of Fenolite, proved by unit tests. Ids used without changing their level: `H-K-EXPORT-FILES`, `H-K-EXPORT-REPEAT`, `H-K-DRC-JSON`, `H-K-ERC-JSON`, `H-K-SCH-RT1`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| State rules, ladder, staleness | mechanical | `test_states.py` |
| Merge, schema, v0.1 manifests still read | mechanical | `test_manifest.py` |
| `manifest` command, `--verify` | mechanical with the fake | `test_manifest_cmd.py` |
| States of real projects | the level of the stages that ran | `test_manifest_oracle.py` on 9.0.9 and 10.0.6 |

## Budget (5 days)

| work | days |
|---|---|
| entry and manifest fields, schema, loader | 0.75 |
| state rules | 0.75 |
| merge, `--manifest` on the four producers | 0.75 |
| `manifest` command with the check and `--verify` | 1.5 |
| oracle test on both majors | 0.5 |
| docs, closing | 0.75 |
| **total** | **5.0** |

Cut order: (1) `--manifest` on `bom` and `pnp` (their files are then `manifest.unlisted`); (2) `--verify`; (3) `--manifest` on `render`. Not optional: the state on every entry, the ladder with its rules, the `manifest` command with the check, v0.1 manifests still readable.

## Risks / Trade-offs

- [A state read as a guarantee] → `docs/exports.md` states each rule in one line and says what a state does not mean; `native-verified` says "KiCad reported no error", not "the board works".
- [A stale `checked` state after an edit] → states are assigned only by `fenolite manifest`, which hashes again; a producing command always writes `generated`; `--verify` catches a later edit.
- [Two commands merge into one manifest at once] → the mutation protocol's atomic write means the last one wins; each merge reads the file again when it runs.
- [An unrouted example never reaches `native-verified`] → correct: its DRC reports unconnected items. The oracle test uses the routed example for the top rung.
- [A reserved state nobody assigns] → kept because the plan names it and v0.3's oracles need it; the schema allows it and the docs say it is unused.

## Migration Plan

- `export --manifest` on a folder that holds a v0.1 manifest merges into it; entries without the new fields take `generated`, not stale, no `from`, no `tool`.
- The schema gains optional fields with defaults, so v0.1 manifests validate; new manifests always write them.
- Rollback: producers write whole manifests again and the command is removed; manifests written meanwhile stay valid.

## Open Questions

- **Should `build` write the project manifest itself?** Default: no; `build` writes its record, and `manifest` is the one writer of states.
- **Should `manifest` exit 0 when the project has errors but the manifest was written?** Default: exit 5, as for any command that reports an error issue; the receipt still lists the manifest.
- **Artefact folders outside the project folder.** Default: refused; a relative path with `..` would break when the folder moves.

## Corrections during implementation (2026-10-05)

The spec was written before c0060, c0064 and c0066 landed and with c0062 as a dependency. What the code
is today changed these points; the delta specs say the same.

1. **No ERC stage, so no `native-verified` on the schematic side.** c0062 is not started and `check` has
   no `erc.kicad`. `states.RULES` holds no `native-verified` rule for a sheet; `states.PENDING` names the
   rung and the stage, and `assign` ignores an `erc.kicad` entry in `stages`: a rule that no stage can
   exercise would be an untested claim. A sheet stops at `roundtrip-ok`. c0062 moves the entry of
   `PENDING` into `RULES`.
2. **Symbol libraries and `sym-lib-table` follow the schematic, not the board.** The draft gave them
   `native-verified` "exactly when the board does". KiCad's DRC does not load them: the copy set of the
   DRC run (`projectset.project_set`) holds the footprint table and the footprint libraries only. A state
   that the DRC cannot support is not written; they stop at `checked` and wait for the ERC with the
   sheets.
3. **`held`.** Each entry says why it is not one rung higher (`native-verified: drc.kicad reported
   errors`, `native-verified: erc.kicad is not a stage of this version of Fenolite`). Without it a
   reader cannot tell a schematic that failed from one that nothing could judge. It is one more optional
   field of the entry; `""` at the top of the ladder of the kind.
4. **A derived entry without `from` stays `generated`.** Entries of a v0.1 manifest have no `from`; the
   rule "the sources its `from` names are `checked`" would be true of nothing and give `checked` to a
   file of unknown origin.
5. **`manifest.changed` and `manifest.missing` have two severities.** When `fenolite manifest` writes,
   a listed artefact that is gone is left out, and one whose bytes changed is listed as it is now,
   without `tool` and `from` (so it stays `generated`): both are warnings, the manifest that is written
   is true. Under `--verify` both are errors. The draft had `manifest.changed` as an error only and did
   not say what the writing command does with an edited artefact; listing its new hash with the old
   `from` would have made it `checked`.
6. **Paths are relative to the project folder.** The draft said "relative to the manifest's folder" in
   one place and "inside `<root>`" in another. They are the same with the default `--out`; with another
   `--out` (the command's own example writes into the working directory) the project folder is the one
   that makes sense: it is where `--verify PATH` finds the files.
7. **The design files are more than `project_set`.** `project_set` is the copy set of a DRC run and holds
   neither the schematic nor the symbol table. The command adds `<stem>.kicad_sch`, the sheets it names
   below the project folder, `sym-lib-table` and the `${KIPRJMOD}` symbol libraries it names.
8. **`tool` of the manifest** names the tool of the run: `kicad-cli` when one ran, else `fenolite` (a
   `bom` or `pnp` merge, `manifest --no-check`). c0024 always had `kicad-cli` there.
9. **`evidence` of a design entry is `UNVERIFIED`.** The field is the level of the entry's own claim
   (c0024: the file set and the hashes of an export). A design entry claims a hash; what was verified is
   its `state`, and the levels behind it are in `check`.
10. **`tools/gen_schemas.py`** learned the field metadata `name`, because `from` is a Python keyword.
11. **Kind `file`.** A library folder is listed file by file and may hold a file that is no KiCad design
    file (a 3D model). `design_kind` gives it the kind `file`, which stops at `checked`: KiCad's DRC is
    not known to load it. A hidden file (a name that starts with `.`) is not listed.
12. **An export with a preset** (c0074, merged while this change was implemented) has the envelope
    level `INFERRED`. Its manifest entries take that level instead of `exports.EVIDENCE`'s: an entry
    claims no more than the run that wrote it.
