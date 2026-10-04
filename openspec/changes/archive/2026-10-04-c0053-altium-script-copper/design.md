## Context

- c0038 (archived) wrote the copper of the experimental `<name>.PcbDoc` and three routes into it: the
  model, a `CopperSource` of origin `script`, and a `CopperSource` of origin `board` (`--copper-from`).
- Its design, "Interface for c0028", gave c0028 one task: in `cmd_build._run_altium`, build the KiCad
  model in memory with the script's intents and pass it as the script source. c0028 (archived) has no
  such task. The origin `script` is used only by unit tests (`tests/unit/lens/test_altium_copper_source.py`).
- Measured on `main` (a2ec22b): `fenolite build examples/blink_routed/design.py --target altium
  --dry-run --json` gives `result.copper` with `"source": "none"`, 0 tracks and 0 vias, and no issue about
  the four intents. The copper is dropped silently.
- What a script can declare today (`design-dsl`): `Design.track` (pad ends, points, via steps),
  `Design.via`, `Design.stitch` (c0028), and `Design.zone` (c0031). The DSL has no arc, no keep-out and no
  blind via. Zones already reach the Altium document as the model source.
- A prototype of the hand-over on `main` gave 11 tracks and 7 vias from the routed blink, and the same
  `blink_routed.PcbDoc` bytes as `--copper-from` of the KiCad build of the same script.

## Goals / Non-Goals

**Goals**

- `--target altium` writes the copper that the script declares, through c0038's script source.
- A defined rule when the script and `--copper-from` both supply copper.
- Nothing dropped silently: an intent that cannot be resolved refuses the build; an intent that creates
  nothing is reported.
- An oracle that compares the imported document with what the script declared.

**Non-Goals**

- New records or format facts; new issue codes; a copper guard for the Altium target; new DSL items;
  the roadmap text.

## Decisions

1. **The hand-over lives in `cmd_build._run_altium`, as c0038 designed it.** The lens keeps receiving a
   model, so `lens.altium` needs no intent type and "Altium build issue codes" (the closed table of the
   lens) is untouched: the KiCad issues join at the CLI, as the reader's issues do with `--copper-from`.
   - Rejected: a `copper_intents` keyword on `build_altium`. Cleaner for the refusal, but it makes the
     lens report `kicad.*` and `build.*` codes, against its closed table.
2. **The in-memory build is the plain KiCad build of the script.** `build_design(model, requested,
   name=…, copper=…, resolver=…, target=ctx.kicad_target, copper_intents=intents)`: no `prepared` layout,
   no `record`, no `fields`. The Altium output folder holds no KiCad board, and a board of an earlier
   KiCad build is the business of `--copper-from`.
   - The resolver is created whenever intents exist, since `build_design` needs one.
   - `UnresolvedLibrariesError` leaves as it does for the KiCad target.
3. **Any error of the in-memory build refuses.** c0038 named `kicad.copper.*` and `kicad.frame.*`; a
   build that returns no files for another reason (`build.no-board`, an unresolved pin) gives no model to
   hand over either. The errors pass unchanged.
4. **Which non-errors pass.** Codes starting with `kicad.copper.` or `kicad.frame.`, and
   `layout.unplaced`. The source's placements win (c0038), so a part that the KiCad build staged is
   placed at its staging position and the lens gives no `altium.pcb-staged`; `layout.unplaced` says it
   instead. Vendoring and library infos concern files that are not written and would mislead.
   `model.*` warnings are reported by the Altium build itself.
5. **Script and `--copper-from` together: the board wins, with one info.** The living spec already
   rules it ("`--copper-from` wins over any other source"), c0038's design says "the board wins, and
   c0028 reports that once", and the zones follow the same rule since c0031.
   - It is also the normal flow: build the KiCad project from a script with intents, route the rest in
     KiCad, then pass that board. The board holds the script copper that the KiCad build wrote.
   - Rejected: a usage error (exit 2). It would forbid that flow for every script with intents.
   - The info reuses `altium.not-lowered` ("a design item has no place in the written files", one issue
     per kind) with the kind "copper intents" and `where` = the path. No row is added to the table.
6. **Zones travel with the script source.** `build_altium` takes one source and raises `ValueError` for a
   source plus copper in `design.board`. `build_design` keeps `Board.zones`, so the source holds them;
   `cmd_build` strips them from the model, exactly as the `--copper-from` branch does. Without intents
   nothing changes: zones stay the model source.
7. **Refused output.** `lens.altium.refused_altium` returns the `BuildOutput` of a refused Altium build
   (no file, `summary["copper"]` and `["pcb_document"]` `None`), so `cmd_build` builds its result the
   same way for both outcomes. It wraps the private `_summary`.
8. **No `intents` key in `result.copper`.** c0038 allowed one; the counts of what is written and the
   pass-through issues say enough, and the key set of "Copper in an Altium build" stays closed.
9. **Example.** `examples/blink_routed` shows it; no example is added.

## Files and public API

| file | change |
|---|---|
| `src/fenolite/lens/altium.py` | `refused_altium(design, *, name, issues, project_exists=False, form=DEFAULT_FORM, sheets=DEFAULT_SHEETS) -> BuildOutput`, exported |
| `src/fenolite/cli/cmd_build.py` | `_run_altium(…, intents)`: the in-memory build, the pass-through, the refusal, the `altium.not-lowered` info with `--copper-from`, the evidence; `SCRIPT_COPPER_CODES` |
| `tests/unit/cli/test_build_altium_script_copper.py` | new: the scenarios of "Script copper in an Altium build" that run the CLI, the records read back with `tests/_altium_pcb_read.py`, and the protocol check |
| `tests/unit/lens/test_altium_copper_source.py` | one test of `refused_altium` |
| `tests/kicad/altium/test_script_copper_oracle.py` | new: "Script copper oracle" |
| `docs/altium.md`, `docs/cli-contract.md`, `docs/evidence/altium-pcb.md`, `CHANGELOG.md` | text |

## Sources registered by this change

None. Cited: S-0161, S-0166 (`kicad-cli pcb import --format altium`, from 10.0).

## Hypotheses registered by this change

None. The oracle is a further proof of `H-A-PCB-CU-KICAD`; step C7 names `H-A-PCB-CU-TRACK` and
`H-A-PCB-CU-VIA`.

## Evidence level per behaviour (before merge)

| behaviour | level |
|---|---|
| script copper resolved (c0028) | `INFERRED` (`H-G-FRAME-UUID`, `H-G-FRAME-ROUTE`) |
| the records written (c0038) | `INFERRED` (`PCB_BUILD_EVIDENCE`); the build is experimental |
| imported copper equals the script's | `ORACLE-VERIFIED(kicad-cli)` on 10.0.6, under `H-A-PCB-CU-KICAD` |
| the document in Altium Designer (C7) | pending author report; never claimed here |

## Size (design-days)

| part | days |
|---|---|
| proposal and deltas | 0.25 |
| hand-over, refusal, pass-through, unit tests | 0.5 |
| oracle | 0.25 |
| docs, C7, sample | 0.25 |
| **total** | **1.25** |

c0038 sized the hand-over alone at 0.25.

## Spec deltas and archive order

- `altium-build` "Script copper in an Altium build": MODIFIED, full text copied from
  `openspec/specs/altium-build/spec.md`. No active change modifies it.
- `design-dsl` "Zones in a build": MODIFIED, full text copied from `openspec/specs/design-dsl/spec.md`.
  No active change modifies it (checked: c0016, c0023, c0025, c0039–c0047).
- Two ADDED requirements in `altium-build` with new names.
- No archive-order dependency.

## Risks / Trade-offs

- **A build that passed now fails.** A script whose intents do not resolve built an Altium project
  before (without its copper). It is now refused. That is the intent of the change.
- **Double work.** The KiCad build runs in memory for every Altium build with intents: libraries are
  resolved twice. The blink takes well under a second.
- **No clearance check.** The copper guard does not run for the Altium target, so script copper with a
  short reaches the document, as copper of `--copper-from` does today. Noted as an open question.
- **Staged parts.** With a script source a staged part sits at the KiCad staging position and is named by
  `layout.unplaced`, not `altium.pcb-staged`.

## Migration Plan

None. No file format, record or result key changes.

## Open Questions

1. **Board wins, or refuse, when both are given?** Default: the board wins with one info (Decision 5).
   The maintainer may prefer a refusal.
2. **Copper guard for the Altium target?** Default: no (non-goal); a later change may run
   `checks.copper.check_copper` on the in-memory triad.
3. **`docs/roadmap.md`, Phase 4:** "c0028 (script copper) … feed this writer; until they land …" is
   true again after this change but still worded as future. Default: left to the release change.
