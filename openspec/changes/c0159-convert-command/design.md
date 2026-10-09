## Context

**Scope.** Milestone v0.5a (`docs/roadmap.md`, Phase 5, first item: "conversion between KiCad and the second backend, with a report of what is kept or lost"; Open decisions row 38). This change builds the conversion itself: the package, the report, the check of every conversion, the command, and the two directions that today's writers already make. c0160 closes the losses of KiCad to Altium that the report measures, c0161 adds Altium to KiCad, c0162 adds the KiCad downgrade; all three register as directions of this change. It needs c0158 (`fenolite.api.equivalent`).

**What exists** (checked on `origin/dev` at `f802b60`, 2026-10-09):

| where | what |
|---|---|
| `src/fenolite/lens/altium.py:2309` `write_model` | a KiCad board's model as an Altium project: `fpitems.with_footprint_items` (the drawings and corner ratios kept in KiCad's slots), then `lower.write_design` |
| `src/fenolite/backends/altium/lower.py:1440` `write_design` | the PCB document, and the schematic, libraries and project file when the schematic writer takes the circuit; `LossyWriteError` (`FEN-7001`) for a loss of `LOSS_KINDS` without `allow_lossy` |
| `lower.py:267` `_Account` | per kind, the ids not written and **one** reason, the first (`self.reasons.setdefault(kind, reason)`); `issues()` gives one `altium.not-lowered` per kind |
| `lower.py:66`, `:84`, `:131` | `KINDS` (13), `MORE_KINDS` (19), `LOSS_KINDS` |
| `src/fenolite/backends/kicad/pcb.py:3189` `write_board` | a board of the model for target 9 or 10; a board read from a file keeps its opaque content; a target older than the source's major raises `DowngradeRefusedError` |
| `src/fenolite/backends/kicad/triad.py:29` `write_triad` | the board, project and rules files of a design, always together |
| `src/fenolite/backends/base.py:836`, `backends/kicad/backend.py:155` | `design_rules(design, project)`: the net classes, the class of each net and the custom rules that a KiCad project's files hold; `read_board` alone gives none |
| `src/fenolite/cli/main.py:97`, `:100` | the global `--kicad-version {9,10}` and `--allow-lossy` reach every command as `Context.kicad_target` and `Context.allow_lossy` |
| `tests/unit/test_import_graph.py:47` | `convert` → `model`, `geometry`, `backends*`: reserved, no package yet |
| `docs/roadmap.md`, `docs/altium.md:1545`, `docs/evidence/altium-roundtrip.md:462` | the decisions of 2026-10-06 that put "a tolerant schematic write for circuits that were read" and "a PCB library derived from an imported model" in v0.5a, with `convert` (c0160 takes both) |

**Measured on 2026-10-09** (the probe scripts are kept with the change's working notes and are not committed; task 1.2 turns them into a corpus test). Each of the 18 KiCad 10.0.6 demo boards of the corpus was read with the KiCad backend (board only, without its project files), written with `write_model(design, allow_lossy=True)`, the PCB document read back with the Altium backend and compared with `compare_designs` at the highest level, frame `relative`, tolerances 10 nm and 20 ppm:

| board | footprints | not written, by kind (count) | level | differences, by kind |
|---|---|---|---|---|
| `CM5_MINIMA_3` | 112 | pad 30, text 149, graphic 31, footprint-graphic 33, zone-fill 13, outline 1, stackup 1 | 5 | dnp 2, pin-missing 6, pad-missing 15 |
| `complex_hierarchy` | 68 | text 2, zone-fill 1, stackup 1 | 5 | pad-shape 40 |
| `ecc83-pp` | 15 | footprint-graphic 4, zone-fill 1, stackup 1 | 5 | pad-shape 4 |
| `ecc83-pp_v2` | 15 | pad 10, footprint-graphic 4, zone-fill 1, stackup 1 | 5 | pin-missing 9, pad-missing 10, pad-shape 9 |
| `interf_u` | 25 | pad 62, text 6, dimension 2, zone-fill 1, stackup 1 | 5 | pin-missing 62, pad-missing 62, pad-shape 144 |
| `jetson-agx-thor-baseboard` | — | not written: `CompoundTooLarge`, 119 FAT sectors, more than the 109 of a file without DIFAT sectors | — | — |
| `kit-dev-coldfire-xilinx_5213` | 160 | pad 5, text 5, zone-fill 3, stackup 1 | 5 | pin-missing 3, pad-missing 5, pad-shape 180 |
| `microwave` | 4 | footprint-copper 4, graphic 3 | 4 | ref-ambiguous 1 |
| `multichannel_mixer` | 114 | pad 35, footprint-graphic 32, keep-out 4, text 2, zone-fill 2 | 5 | pin-missing 19, pad-missing 19 |
| `multichannel_mixer-unrouted` | 114 | the same, zone-fill 1 | 5 | the same |
| `One-Air-Max` | 210 | pad 23, footprint-graphic 29, zone-fill 34, text 25, outline 20, footprint-copper 3, copper-shape 2, graphic 2, net-tie 2, stackup 1 | 5 | dnp 11, pin-missing 17, pad-missing 20, ref-ambiguous 1 |
| `pic_programmer` | 63 | pad 11, text 19, footprint-graphic 6, zone-fill 1, stackup 1 | 5 | pin-missing 2, pad-missing 10 |
| `RoyalBlue54L-Feather` | 71 | pad 67, outline 4, footprint-graphic 4, zone 2, zone-fill 2, footprint-text 2, footprint-copper 1, text 1, net-tie 1, stackup 1 | 5 | dnp 22, pin-missing 25, pad-missing 35, pad-shape 23, route-connectivity 2 |
| `RoyalBlue54L-NFC-Antenna` | 2 | footprint-graphic 11, copper-shape 4, outline 1 | 5 | none |
| `sonde xilinx` | 25 | text 8, footprint-graphic 2, footprint-text 2, dimension 1, zone-fill 1, stackup 1 | 5 | pad-shape 21 |
| `tinytapeout-demo` | 309 | text 224, pad 27, footprint-copper 25, footprint-graphic 19, dimension 6, net-tie 9, outline 1, zone-fill 2, graphic 2, footprint-text 1, stackup 1 | 5 | dnp 11, pad-shape 96, pad-missing 24, pin-missing 4, ref-ambiguous 4, route-connectivity 1 |
| `video` | 189 | pad 144, graphic 14, dimension 2, text 1, zone-fill 2, stackup 1 | 5 | pin-missing 120, pad-missing 128, pad-shape 85 |
| `vme-wren` | — | not written: `CompoundTooLarge`, 181 FAT sectors | — | — |

What the table says for this change:

1. Most differences have a declared cause: a lost pad gives `pad-missing` and `pin-missing` at its `REF-PIN`; lost zones and pads give `route-connectivity` on their nets. Nothing joins the two today, so nobody can tell an explained difference from a fault.
2. Two causes are not declared at all: `pad-shape` `oval`/`circle` for equal-sized ovals (the same copper; c0158 fixes the comparison) and the **do-not-populate flag**: 22, 11 and 11 components on three boards lose it with no issue (`dnp` `true`/`false`). The Altium writers hold no such flag; Altium keeps "not fitted" in variants, which are after 1.0.
3. The reasons per kind are first reasons: for `pad` the probe saw "per-layer padstack", "shape custom", "connector pad (kind connect)" and "the pad number '' is empty", one per board. A count per reason is what a user acts on.
4. Two boards are not written at all (`CompoundTooLarge`); c0160 writes DIFAT sectors.
5. 16 boards written in 0.4 s to 11.8 s each, read back included.

## Goals / Non-Goals

**Goals**
- One command that converts a project and says, per kind and per reason, what it kept, changed and lost.
- A conversion whose written project differs from the source only where the report says so, checked on every run.
- Exit 7 for a loss the user did not accept, exit 5 for a difference nobody declared.

**Non-Goals**
- Closing the losses of the table (c0160), Altium to KiCad (c0161), the downgrade (c0162).

## Decisions

1. **The package `fenolite.convert`** (layering: `model`, `geometry`, `backends*`; no new row). `convert_project(source: Path, *, to: Literal["kicad", "altium"], kicad_version: int = 10, allow_lossy: bool = False, bodies: str = "extruded", name: str | None = None) -> Conversion`, where `Conversion(files: Mapping[str, bytes], report: ConversionReport, source: SourceProject, target: str, evidence: Evidence)`. It reads, chooses a `Direction` from a registry of directions (`DIRECTIONS`, keyed `(source backend, target backend)`), writes in memory and returns. It writes no file and runs no tool.
   - **Sources.** A KiCad source is a `.kicad_pro`, a `.kicad_pcb` or a folder, resolved as `check` resolves it; the design is `read_board` completed by `KicadBackend.design_rules` with the project's files (net classes, the class of each net, custom rules). An Altium source is a `.PrjPcb`, a `.PcbDoc` or a folder, read by the Altium backend (circuit from the schematics, board from the document). Anything else exits 2 (`FEN-2001`).
   - Rejected: a command that calls `lens.altium.write_model`: `convert` may not import `lens`, and the projection is two calls of backends (`fpitems.with_footprint_items`, `lower.write_design`), which the direction makes itself. `write_model` stays for its callers.
2. **One vocabulary of kinds.** `convert.report.KINDS` is a closed table, one row per kind: `name`, `group` (`circuit`, `footprint`, `copper`, `board`, `presentation`, `project`), and `loss` (`refuse` or `report`): a lost item of a `refuse` kind needs `allow_lossy`. The rows are the Altium write's `KINDS` and `MORE_KINDS`, the kind `dnp`, and the KiCad kinds that c0161 and c0162 add (each of those changes adds its rows). A writer's own issues map onto the table by a function per direction; a kind a writer names that the table lacks fails a unit test, not a run. `refuse` holds every kind of `lower.LOSS_KINDS` and `dnp`.
   - Rejected: the two writers' vocabularies side by side: one report per direction would make a user learn two.
3. **`ConversionReport`.** `rows`: one `ReportRow(kind, source, written, changed, lost, reasons)` per kind the source holds or the write touches, in table order; `reasons` is `((reason, count, ids), …)` sorted by count, then reason. `lossy` is true when any `lost` is non-zero; `refused` names the `refuse` kinds with losses. `to_json()` is `result.report` of the command; `ids` are left out of the JSON unless `--report-ids` is given (a large board would give thousands).
   - **Per reason, not first reason.** `lower._Account.skip` keeps every reason per id (`AltiumInputs.lost: Mapping[str, Mapping[str, tuple[str, ...]]]`, kind → reason → ids); `reasons` and `not_lowered` stay as derived views, so the `altium.not-lowered` issues keep their text.
   - **`changed`** counts what is written in another form that `equivalent` sees as the same (an arc of an outline written as two edges is a loss, a polygon written unpoured is `changed`: Altium repours it, decision of 2026-10-06, row 23). Each direction lists its changes; c0159 has two: `zone-fill` (unpoured) and `schematic` (generated from the circuit on one sheet with generic symbols).
4. **The do-not-populate flag.** `lower.from_design` counts each component with `dnp` set under the kind `dnp` with the reason "the Altium documents hold no fitted flag outside variants" and an `altium.not-lowered` **info**. `LOSS_KINDS` does not gain it, so `AltiumBackend.write` and `build --target altium` change by one info only. In the conversion report `dnp` is a `refuse` kind: a bill of materials from the converted project would list the part. Rejected: writing a variant (after 1.0). Rejected: a silent loss, which is today's state.
5. **Verification.** `fenolite.api.convert(source, *, to, …, verify=True) -> ConversionResult` calls `convert_project`, writes the files into a private temporary folder, reads the written project with the target backend, and compares source and reading with `fenolite.api.equivalent` at `max_level`, under the direction's profile (`src/fenolite/convert/data/profiles.toml`, the exclusion format of c0045: frame, tolerances and the rules for known, explained differences, each with a hypothesis). Then each difference that no rule excludes is matched against the report: a difference whose `where` is the `REF` of a lost footprint, the `REF-PIN` of a lost pad, or the net of a lost track, arc, via or zone is **explained** and listed under `result.equivalence.explained` with the kind; any other is `convert.unexplained` (error). With an unexplained difference the command plans no write and exits 5.
   - The profile of KiCad to Altium: frame `relative` (the writer moves the board's corner), `tolerance_nm` 3 (the document holds 1/10 000 mil, 2.54 nm, and RT-A2 holds within 2 nm per coordinate after the reader's rounding; task 1.2 measures the largest difference and the profile takes it), `tolerance_ppm` 20 (as the triangle's).
   - `--no-verify` skips the step; the reply then says `equivalence: null` and the evidence drops to `UNVERIFIED`. Rejected: verification as a separate command (`convert` then `equivalent`): a report that nobody checks is the problem of item 1 above. Rejected: verification inside `fenolite.convert`: the package may not import `checks`, and `api` may.
6. **The command.** `fenolite convert SRC --to {kicad,altium} --out DIR [--name NAME] [--altium-bodies {extruded,off}] [--report-ids] [--no-verify]`, with the global `--kicad-version` and `--allow-lossy`. It is mutating: `--dry-run` gives `result.plan` with every file under `DIR`, `--confirm` writes them all or none (`cli-contract`, "All-or-nothing writes"). `DIR` must not be the source's folder or hold it (`FEN-2001`): a conversion never writes over its source. `result` holds `source` (`path`, `backend`, `kind`, `format_version`), `target` (`backend`, `major` for KiCad), `files` (names and sizes), `report`, `equivalence` (the reply of c0158 with `explained`), and `experimental` (true for a direction that writes Altium). Schema `schemas/fenolite.convert.v0.json`.
   - Exit codes: 0; 2 usage; 3 a source that does not read; 4 confirmation; 5 `convert.unexplained`; 7 `FEN-7001` for a `refuse` loss without `--allow-lossy`, the report's lost rows as the error's issues (`cli-contract`, "Refusals carry their issues").
   - Rejected: `fenolite build --from <project>`: `build` runs a script and keeps a layout; a conversion has no script.
7. **Two directions in this change.**
   - **KiCad to Altium:** `fpitems.with_footprint_items`, `lower.write_design(…, bodies=…)`; `experimental` true, evidence the Altium writers' (`INFERRED`).
   - **KiCad to KiCad,** for a target major not older than the source's: `write_triad` with the board read (opaque content kept, as RT1 keeps it), the project file updated from the source's (`pro.update_project`), the rules file re-written for the target, and the schematic files copied byte for byte when the source's major equals the target (a schematic re-target is c0162's). An older target raises `DowngradeRefusedError` until c0162. Evidence `KICAD-VERIFIED` once `H-K-CONV-RETARGET` holds.
   - Altium to KiCad exits 2 with `convert.direction-unsupported`'s message until c0161 registers its direction; the reply of `capabilities` lists only registered directions.
8. **Codes.** `convert.unexplained` (error), `convert.lossy` (warning, one per `refuse` kind with losses, under `--allow-lossy`), `convert.changed` (info, one per kind with changes), `convert.no-verify` (warning). The registry is `convert.codes.ISSUE_CODES`; `explain` knows each.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/convert/__init__.py` (new) | `convert_project`, `Conversion`, `SourceProject`, `DIRECTIONS`, `EVIDENCE` |
| `src/fenolite/convert/report.py` (new) | `KINDS`, `KindRow`, `ReportRow`, `ConversionReport`, `merge` |
| `src/fenolite/convert/sources.py` (new) | `read_source(path) -> SourceProject` for KiCad and Altium inputs |
| `src/fenolite/convert/to_altium.py`, `to_kicad.py` (new) | the two directions of this change; `to_kicad.py` is extended by c0161 and c0162 |
| `src/fenolite/convert/codes.py`, `data/profiles.toml` (new) | the codes; the verification profiles per direction |
| `src/fenolite/api/conversion.py` (new) | `convert(...) -> ConversionResult`, the read-back and the matching of differences to the report |
| `src/fenolite/cli/cmd_convert.py` (new), `schemas/fenolite.convert.v0.json` (new) | the command and its result schema |
| `src/fenolite/backends/altium/lower.py` | `AltiumInputs.lost`, every reason kept; the kind `dnp` |
| `src/fenolite/cli/cmd_capabilities.py` | `conversions` |
| `tests/unit/convert/` (new), `tests/unit/api/test_conversion_api.py`, `tests/unit/cli/test_convert_cmd.py` (new) | the scenarios |
| `tests/corpus/test_convert_census.py` (new) | `H-G-CONV-LEDGER` over the KiCad demo boards |
| `tests/kicad/convert/test_triangle.py`, `test_retarget.py` (new) | `H-K-CONV-TRIANGLE`, `H-K-CONV-RETARGET` |
| `docs/conversion.md` (new), `docs/cli-contract.md`, `docs/altium.md`, agent guide page `files` | the command, the report, the kinds table, the profiles |

## Sources registered by this change

None. The facts rest on S-0020 and S-0029 (the pinned `kicad-cli` images), S-0058 (the KiCad demo boards) and the Altium format rows already registered for the writers. S-0740 to S-0759 stay reserved for v0.5a.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-G-CONV-LEDGER | For every KiCad 10.0.6 demo board of the corpus that a direction writes, every difference that `equivalent` finds between the source and the reading of the written project is excluded by the direction's profile or explained by a lost item of the report (S-0058) | `tests/corpus/test_convert_census.py` | no `convert.unexplained` on any written board; the table of the design measured again, per kind and reason, in `docs/evidence/conversion.md` |
| H-K-CONV-TRIANGLE | `kicad-cli pcb import` (10.0.6) of the PCB document that `convert --to altium` writes from a KiCad board equals that board at level 5 under the profile `kicad-import`, apart from the items the report names as lost (S-0029, S-0058) | `tests/kicad/convert/test_triangle.py` | probe `convert-triangle` `equal` on the samples and on the demo boards the census writes |
| H-K-CONV-RETARGET | A KiCad project of major 9 converted to KiCad 10 loads in `kicad-cli` 10.0.6, and its DRC and ERC report the same violation types as the source's in 9.0.9 (S-0020, S-0029) | `tests/kicad/convert/test_retarget.py` | probe `convert-retarget` `equal` on the two examples and the demo projects of format 9 |

All three start `INFERRED`. Ids used without changing their level: `H-A-VER-RTA2-3`, `H-A-VER-RTA3`, `H-K-PCB-WRITE`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| the report: kinds, reasons, counts | mechanical | `tests/unit/convert` |
| verification and the matching of differences | mechanical; `CORPUS-VERIFIED` over the demo boards (`H-G-CONV-LEDGER`) | `tests/unit/api/test_conversion_api.py`, `test_convert_census.py` |
| KiCad to Altium | `INFERRED`, experimental; `ORACLE-VERIFIED(kicad-cli)` for the triangle (`H-K-CONV-TRIANGLE`) | `test_triangle.py` in the pinned 10.0.6 image |
| KiCad to KiCad, same or newer major | `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-CONV-RETARGET`) | `test_retarget.py` in both pinned images |
| exit codes, plan, schema | mechanical | `tests/unit/cli/test_convert_cmd.py`, `tests/consistency` |

The level of a reply is the lowest of the source's read, the direction's writer and the read-back; the Altium direction stays experimental until c0092's rule lets its write kinds leave that state, which needs the kit run (`ALTIUM-VERIFIED(kit)`), not an author report.

## Risks / Trade-offs

- **Matching by `where` explains too much.** A lost pad explains every difference at its `REF-PIN`, also one the loss did not cause. Mitigation: a lost pad explains only `pad-missing`, `pin-missing` and level-5 kinds of its net; the table of which difference kinds a lost kind explains is closed and tested.
- **The read-back doubles the time.** Measured: 0.4 s to 11.8 s per demo board with the read-back. `--no-verify` exists for large boards, at the cost of the label.
- **A user takes the report for Altium's view.** The report is Fenolite's: what Altium Designer does with the files is the kit's and the author reports' (c0160's maintainer steps).
- **`dnp` as a refusal** makes `--allow-lossy` necessary on boards with do-not-populate parts: 3 of 16 demo boards. That is the point: the converted bill of materials differs.

## Migration Plan

- A new command and a new package; no existing output changes, except one `altium.not-lowered` info of kind `dnp` in `build --target altium` and `AltiumBackend.write` of a design with do-not-populate parts.
- `AltiumInputs` gains `lost`; `not_lowered` and `reasons` keep their meaning.

## Budget (6.75 days)

| part | days |
|---|---|
| entry check, hypotheses, the census test from the measurement | 0.75 |
| the report: kinds table, rows, reasons per item in `lower`, `dnp` | 1.25 |
| sources (KiCad with its project files, Altium) and the directions registry | 0.75 |
| KiCad to Altium and KiCad to KiCad | 0.75 |
| verification: read-back, profile, matching of differences | 1.25 |
| the command, plan, exit codes, schema, capabilities | 1.0 |
| oracles: triangle and re-target | 0.5 |
| documentation, guide, closing | 0.5 |
| **total** | **6.75** |

Cut order: (1) `--report-ids`; (2) the KiCad to KiCad direction (c0162 then adds it with the downgrade); (3) the `changed` column (counted as nothing changed, every change a loss). Not cut: the report per reason, `dnp`, the verification, exit 7 and 5.

## Open questions

1. **Is a lost do-not-populate flag a refusal (exit 7 without `--allow-lossy`)?** Recommended: yes; the converted bill of materials lists a part that the source does not fit.
2. **Verify by default?** Recommended: yes, with `--no-verify` dropping the label to `UNVERIFIED`; the read-back costs at most twice the conversion on the measured boards.
3. **May `--out` be an existing folder with files?** Recommended: yes, with `.bak` of overwritten files as every write does, but never the source's folder or a folder that holds it.
4. **Name of the command: `convert`?** Recommended: yes, the word of the roadmap and of the reserved package.
