## Context

- **Today.** `adapter/netlist.py` recognises `repeat(` in a sheet symbol's designator (`REPEAT`, `SymbolInfo.repeat`), descends once, and emits `altium.import.repeated-sheet` ("one instance is read", "its designators are not annotated"). `adapter/project.py::link` renames a component to the board's `source_designator` only when its unique-id path matches. `read/project.py` classifies `.Annotation` as kind `annotation` and never parses it.
- **Measured on 2026-10-05** (`docs/evidence/altium-roundtrip.md`, `altium-set:02`): 508 common elements, 4 differing, 26 only in the schematic, 217 only in the PCB document; `model.duplicate-ref`. `docs/formats/altium/connectivity.md` records that twelve sheet symbols name one sheet in that set.
- **Public facts available.** Altium's documentation of multi-channel design (the `Repeat` keyword, the channel naming formats `$Component_$ChannelAlpha`, `$Component$ChannelIndex` and the others, the board-level annotation file) is public and already partly cited as S-0185. The corpus project gives the ground truth: its PCB document holds every channel's designator and its unique-id path.
- **Constraints.** Stdlib only; the import stays read-only and bounded; the model spec is additive-only since the end of v0.3, so a channel uses fields the model already has.

## Goals / Non-Goals

**Goals:**
- The imported circuit of a multi-channel project has every channel's components and nets, with the designators of its board.
- The import says which source gave the designators, and what it could not resolve, with a located issue.
- The corpus run on `altium-set:02` has no `model.duplicate-ref`, and its remaining differences are explained one by one.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.

## Decisions

1. **A channel is a module instance.** The path of a component in channel `i` of sheet symbol `S` is `<parent path>/<S name>[<i>]/<designator in the sheet>`; its `Module` carries the sheet symbol's unique id and the index in its extension bag. Two sheet symbols that name one file give two instances with their own names (the `#n` suffix of `altium.import.duplicate-sheet-name` stays for equal names).
2. **Designator sources, in order.** (1) The PCB document: a board component whose unique-id path is `\\<sheet symbol uid>\\<component uid>` for that channel gives its designator (`link` already matches such paths; it now runs per channel). (2) The annotation file: its entry for the same unique-id path. (3) The naming format of the project file applied to the sheet designator, the channel name and the index. `result.channels` reports the count per source. Rejected: inventing `D9_1` without a source, because five naming formats exist and a wrong guess looks right.
3. **Unknown format is an issue, not a guess.** A project whose naming format is not one of the formats in `docs/formats/altium/connectivity.md` gives `altium.import.channel-naming` (warning) and designators `<designator>@<channel name>`, which no Altium format produces, so they cannot be mistaken for real ones.
4. **Nets.** Inside a channel the connectivity of c0043 is unchanged. Across the boundary: a sheet entry `Repeat(NAME)` connects channel `i` to the `i`-th member of the parent's bus `NAME[first..last]`; any other sheet entry connects all channels to one parent net; a net label or power port of global scope is one net for all channels; a local net gets the channel suffix of the naming format. The net identifier scope of the project file ("Net identifier scope") decides global against local as before.
5. **`altium.import.repeated-sheet` becomes an error case.** It is reported when the repeat statement does not parse, when `first > last`, or when the range is larger than `MAX_CHANNELS` (256): then one instance is read, as today. A repeat that is instantiated gives the info `altium.import.channels` with the count.
6. **Pin-to-pad map.** When a component's footprint model on the sheet carries a pin map, the element of a pin in `netlist.assignment_compare` and in level 2 of `equivalent` is the pad it maps to. Without a map the pin number is the pad name, as today.
7. **Cut order.** First the pin-to-pad map (it is independent and can move to a follow-up), then the naming format without board and annotation (source 3), never the instantiation and source 1.

## Found on 2026-10-06 (task 0.1), and what changed

The proposal said that the import reads a repeated sheet once. That is true only of a `Repeat(…)` statement. A sheet that several sheet symbols name was already instantiated once per symbol (c0043), and the board already linked to each instance by its unique-id path. The defect on `altium-set:02` had two other causes:

- `project.link` gave a linked channel component the board's `SOURCEDESIGNATOR`, which is the designator of the sheet (`D9` for all twelve channels), not the designator the board shows (`D9_12`). It now takes the board component's own designator.
- The schematic reading alone, which `netlist.assignment_compare` uses, had no channel names at all. It now applies the project's designator format (`adapter/channels.py`): on the set, all 84 channel components get the board's designators from the format alone.

Consequences for this change:

- **Decision 2, source 3 comes before source 2 in the code**, because the corpus holds a project file with a format and no annotation file. The set's project lists an annotation file that is not a row of the corpus manifest: reading it needs a new corpus row, which needs the maintainer's consent to a download. Task 2.1 waits for that. (Later on 2026-10-06: with the maintainer's consent the file was fetched; it is empty at that commit, 0 bytes, so it teaches nothing and gets no corpus row. The form of a non-empty annotation file stays `UNKNOWN`; Part R, step R4, is now the only planned source.)
- **`altium.import.channels` (info)** is reported for a sheet named by several symbols; **`altium.import.repeated-sheet`** stays for `Repeat(…)`, which is still read as one instance until task 3.1.
- **No corpus project uses `Repeat(…)`**, so tasks 3.1 and 3.3 rest on authored sheets and on S-0452 only; they stay `INFERRED` until Part R.
- **`model.duplicate-ref` on the set does not come from channels**: its PCB document holds twelve components without a designator, and `model.validate` counts the empty reference twelve times. The scenario "Designators from the board" therefore asks that no non-empty reference is held twice. Whether an empty reference should count as a duplicate is a question for the model's validation, outside this change. Decided by the maintainer on 2026-10-06: a component without a reference gets a finding of its own (a warning, one per component) and no longer counts as `model.duplicate-ref`; that is the follow-up change c0095 on `dev` after the 0.2.0 release. Until it lands, `altium-set:02` keeps one `model.duplicate-ref`.

## Found on 2026-10-06 (the rest: tasks 3.1, 3.3, 3.4), and what changed

- **`Repeat` has no public file.** No corpus project holds a `Repeat` statement, so tasks 3.1 and 3.3 are implemented from Altium's two documentation pages (S-0452, read again as S-0520) and from authored sheets. `H-A-IMP-RPT-COUNT` cannot have the criterion of the table below (a count on `altium-set:02`, which repeats by several sheet symbols): its settling test is the unit test on authored sheets and Part R, and it stays `INFERRED`.
- **A `Repeat` statement has one unique id for all its channels.** The native ids of channel `i` name the sheet symbol as `<unique id>[<i>]` (`cmp:\<uid>[<i>]\<component uid>`, `module:\<uid>[<i>]`): a form of this import, said so on the facts page. The documentation writes the board's path as `\ChannelIndex+SheetSymbolUID\SchComponentUID` without an example, so how the two are joined is `UNKNOWN`: no path is tried for a `Repeat` channel. A board component links to such a channel only by designator (its own designator equal to the channel designator of the format, its source designator equal to the sheet's); what does not link is counted by `altium.import.channel-naming`. Part R, step R3, asks for the form.
- **The channel index is in the module name and in the component's path through it** (`CH[1]/R1_CH1`), as the first open question defaults. `Instance` keeps the channel identifier and the index apart (`prefixes`, `indexes`), because the format needs them apart; the fallback designator writes a `Repeat` channel as identifier and index (`R1@CH1`).
- **What a format does not say for a `Repeat` channel is not guessed.** `$ChannelAlpha` is `A` to `Z` for the indexes 1 to 26 (the page says "the channel index expressed as a character" and no more); the mixed room style, a flat style under a `Repeat` higher up (two rooms would get one name) and a format without `$RoomName`, `$ChannelIndex` and `$ChannelAlpha` (two channels would get one designator) give the fallback and `altium.import.channel-naming`.
- **Net names of a channel.** Decision 4 says a local net gets "the channel suffix of the naming format". Measured on `altium-set:02`: its board names the 24 nets without an identifier that lie inside one channel `Net<channel designator>_<pin>`, so the system name is now built on the channel designator (116 nets of the set have the board's name, 92 before; `altium.import.duplicate-net-name` 23 times, 45 before; the partition of the pads did not change). A net label local to a channel is renamed by the format as a designator is (`MID_CH1`) and keeps the label as an alias: that is the reading of the documentation, in no public file, `INFERRED`. A net named by a power port, a port or a sheet entry is not renamed.
- **The channel designators moved into `netlist.resolve`** (`Resolved.refs`, `Resolved.channel_sources`), because the net names need them; `circuit.build_circuit` reads them from there. `channel_designator` stays in `adapter/channels.py` (part 1 put it there, not in `project.py` as "Files and public API" says).
- **The pin-to-pad map was already read** (`parts.PartGroup.pin_pads`, c0043) and applied only by the corpus test's own comparison. It now reaches the model: `Component.pin_pad_map`, which `checks.assignment_compare.model_netlist` already applies, so `netlist.assignment_compare` on Altium documents and level 2 of `equivalent` use it without a change to either.
- **Level 2 of `equivalent` dropped a mapped pin on a design without a board.** `checks/equivalence/levels.py` listed the elements it compares by pin number while `model_netlist` names them by pad, so a pin with a map fell out of the comparison. It now keys them by pad, as `model_netlist` does. No committed design was affected: the path is taken only by a design without footprints whose components carry a map.
- **The model's map is one pad per pin** (`design-model`, "Persist per-component pin-to-pad maps": each source and target unique), and Altium's record lists any number of pads. The requirement's sentence "a pin that the map sends to no pad is left out of the comparison with the reason `unmapped-pin`" cannot be met through the model, which has no way to say "no pad"; and a pin with several pads can give one element only. The requirement is corrected: one pad per pin (its own designator when the record lists it, else the first), the whole record kept in the component's bag (`pin_pads`), and `altium.import.pin-map` (info, a new code) with the count. Changing the model's rule to several pads per pin is a change of `design-model` and of every consumer of the map (the KiCad schematic generator and the DSL build read it as one pad per pin): outside this change. On `altium-set:02` the cost is 4 pads that stay covered by the PCB document only.
- **"Single-channel projects unchanged" is about channels.** A project without a repeat now imports with `pin_pad_map` and `pin_pads` on the components whose footprint model maps a pin; nothing else of its model changes. Of the corpus sets only `altium-set:02` holds such a record (set 01 holds 55 records with an empty pin and the pad text `null`, which name no pin and are left out).
- **The corpus counts of `altium-set:02`** went from 688 common, 13, 37 and 2 to 694, 7, 31 and 2; `docs/evidence/altium-roundtrip.md` lists what remains by cause. The other four rows did not change (set 01 measured with `FENOLITE_HEAVY=1`).
- **Task 1.2, the sample.** The schematic writer cannot write a `Repeat` statement (c0086: one sheet per module, "no writing of repeated sheets"), so the sample is authored with the record builders of the tests (`tests/_altium_records.py`, framed into a compound file by the product's `cfb.write_compound`) from `tests/data/altium/channels/two/author.py`. It holds what the reader needs and no symbol graphics; whether Altium opens it is unknown, and Part R says what to do if it does not.
- **Reused from the frozen branch `codex/board-authoring-gaps` (17536270), file by file.** `adapter/circuit.py`: the idea of its one added line (the imported component takes `pin_pad_map` from `PartGroup.pin_pads`); the line itself is not carried, because it lists several pads for one pin, which the living model spec forbids. `adapter/library.py` (`_selected_map`, a map on `SymbolDef`): read, nothing taken (the model's `SymbolDef` has no such field). `altsym.py`, `schlib.py`, `schdoc.py`, `lens/altium_maps.py` and its four test files: the write side, not read for this change. No allowance of that branch's import-graph, residue or guard tests is carried.
- **"Import issue codes" and "Net identifier scope" are now MODIFIED deltas**, copied from the living text: the first gains `altium.import.channels`, `altium.import.channel-naming` and `altium.import.pin-map`, the second loses its sentence that a repeated sheet gives `altium.import.repeated-sheet`. Part 1 had left both as ADDED text only.

## Files and public API

- `src/fenolite/backends/altium/read/annotation.py`: `read_annotation(data, *, file) -> AnnotationFile` (entries by unique-id path; the text kept byte for byte).
- `src/fenolite/backends/altium/adapter/netlist.py`: `parse_repeat(text) -> Repeat | None`, `repeat_entry(text) -> str | None`, `MAX_CHANNELS`, channel instantiation in the instance builder (`Instance.prefixes`, `indexes`, `position`), `channel_name`, `Resolved.refs` and `Resolved.channel_sources`.
- `src/fenolite/backends/altium/adapter/channels.py`: `channel_designator(format, designator, names, *, style, separator, indexes)`, `room_name`, `channel_alpha`, `KEYWORDS`, `FLAT_STYLES`, `PATH_STYLES`, `NUMERIC_STYLES`, `ALPHA_STYLES` (the proposal's `NAMING_FORMATS` does not exist: a format is free text with keywords).
- `src/fenolite/backends/altium/adapter/circuit.py`: `pin_pad_map(group)`, `CircuitImport.unlinkable`; `adapter/project.py`: `link(…, unlinkable)`.
- `src/fenolite/backends/altium/adapter/codes.py`: `altium.import.channels` (info), `altium.import.channel-naming` (warning), `altium.import.pin-map` (info); `adapter/ids.py`: the bag keys `pin_pads`, `sheet_symbol`, `channel_index`.
- Tests: `tests/unit/backends/altium/adapter/test_channels.py`, `test_repeat.py` and `test_channel_files.py`; the authored sample `tests/data/altium/channels/two/` (written by its `author.py` from `tests/_altium_channels.py`, declared in `tests/data/MANIFEST.toml`); `tests/corpus/test_altium_channels.py`. `tests/unit/backends/altium/read/test_annotation.py` waits for task 2.1.

## Sources registered by this change

- S-0185 (registered): multi-sheet and hierarchical designs.
- New: Altium's public documentation pages on multi-channel design and on the channel naming formats (S-0452 for part 1; read again for the `Repeat` statement, the repeated sheet entry, the keywords of a `Repeat` channel and the unique-id path as S-0520, from the block S-0520 to S-0529 reserved for this change).
- The corpus rows of `altium-set:02` (already in the manifest): the project file, its sheets and its PCB document.

Each new source gets the next free `S-` number in `docs/evidence/sources.md` when its task runs (numbers are not reserved here, because changes that run in parallel would collide), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-IMP-RPT-COUNT | A sheet symbol whose designator is `Repeat(NAME, a, b)` stands for `b - a + 1` channels of its child sheet; a board of the same project holds that many components per component of the child sheet | `tests/unit/backends/altium/adapter/test_repeat.py::test_instances_of_two_channels` on authored sheets; author report, Part R, steps R1 and R3 (corrected on 2026-10-06: no corpus project holds a `Repeat` statement) | Altium shows two channels of the child sheet of the authored project, and its board holds one component per channel and sheet component |
| H-A-IMP-RPT-BOARD | A board component of channel `i` carries the unique-id path of its sheet symbol and of its sheet component, and its designator is the channel designator | `tests/corpus/test_altium_channels.py::test_designators` | every component of every channel is linked to exactly one board component; no `model.duplicate-ref` |
| H-A-IMP-RPT-NETS | A sheet entry `Repeat(NAME)` connects channel `i` to member `i` of the parent bus, and other entries connect all channels to one net | `tests/corpus/test_altium_channels.py::test_nets_of_the_channels_agree_with_the_board` for channels of several sheet symbols; `test_repeat.py -k nets` and Part R, step R3, for `Repeat(NAME)` | `netlist.assignment_compare` between the imported schematic and the PCB document of `altium-set:02` has no pin of a channel on the schematic side only and none on another net than its pad; the board Altium makes of the authored project has `OUT1` and `OUT2` on one channel each |
| H-A-IMP-RPT-FORMAT | The naming formats of the project file give the channel designators that Altium shows, for each documented format | author report, Part R | for each format of the authored project, the designators Altium shows equal `channel_designator` |
| H-A-IMP-RPT-ANNOT | The annotation file of a project maps a unique-id path to the board-level designator | `tests/unit/backends/altium/read/test_annotation.py` and author report, Part R step 4 | the designators read from the file Altium saved equal those of the board |
| H-A-IMP-PINMAP | A footprint model's pin map on the sheet names the pad of each pin, and the board's pads use those names | `tests/corpus/test_altium_channels.py::test_pin_map_never_uncovers_an_element` | on the corpus sets, applying the map never increases the elements on one side only nor the differences, and the page says which elements of `altium-set:02` remain (its 2 differing elements are not of the map) |

All start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06). Registered on 2026-10-06: `-BOARD` (`CORPUS-VERIFIED`), `-FORMAT`, `-COUNT`, `-NETS` and `H-A-IMP-PINMAP` (`INFERRED`); `-ANNOT` is not registered while task 2.1 is open.

## Author report: Part R, channel naming

Needed for everything about a `Repeat` statement (no public file holds one) and for source 3 (no board, no annotation file). Files: the authored two-channel project `tests/data/altium/channels/two/`, copied on 2026-10-06 to `~/fenolite-altium-checks/c0083-part-r/`. The steps as the maintainer runs them, with the expected values and the SHA-256 of the files, are in `docs/evidence/altium-schematic.md`, "Part R"; in short:

1. R1: open the project in Altium Designer and compile it. Expected: no error; the Navigator shows two channels of the child sheet (`H-A-IMP-RPT-COUNT`). The sheets are authored record by record and hold no symbol graphics: if Altium does not open them, draw the same project by hand (the page says what it holds) and go on.
2. R2: for each naming format offered in Project Options » Multi-Channel, and for each room naming style, select it, compile, and write down the designator of the component `R1` in both channels. Expected: the values of the page (`H-A-IMP-RPT-FORMAT`).
3. R3: with the format `$Component_$RoomName`, run Design » Update PCB Document on an empty board and write down the designators on the board, the net names of the two channels, and the form of the unique-id path of one channel component. Expected: the same as R2 for that format; `OUT1`, `OUT2`, `MID_CH1`, `MID_CH2` (`H-A-IMP-RPT-NETS`); the path form is what the board link of a `Repeat` channel waits for.
4. R4: run Tools » Annotation » Annotate Compiled Sheets, rename one channel's `R1`, save, and send only the names of the keys of the `.Annotation` file that changed and the two designators (`H-A-IMP-RPT-ANNOT`).

The maintainer reports one generic outcome per step (`as expected`, or what differed in one sentence), the tool as `AD <major>.<minor>` and the date. No file that Altium wrote is committed. A step that fails refutes the row it names: the row keeps its id and gets a registered successor (`verification-evidence`, "Refuted rows keep their id"). An author report never moves an operation out of `experimental` ("Author reports never promote an operation").

## Size (design-days)

| group | dd |
|---|---|
| entry, facts and sources | 0.5 |
| annotation reader | 0.5 |
| channel instantiation and designators | 1.75 |
| channel nets | 1 |
| pin-to-pad map | 0.75 |
| corpus run, evidence page, docs | 0.75 |
| closing | 0.25 |

Total: 5.5. This is a size, not a calendar estimate.

## Spec deltas and archive order

- `altium-import`, "Hierarchy as modules": its sentence on repeated sheets (one instance, `altium.import.repeated-sheet`) is superseded by "Repeated sheets as channels"; "Import issue codes" gains two codes. Task 0.1 writes both as MODIFIED from the living text.
- `altium-project-reader`, "Project loading": the annotation file joins what `load_project` returns (MODIFIED at task 0.1).
- Archive order: independent of the other v0.4 changes.

## Risks / Trade-offs

- [A project annotated at board level without an annotation file in the repository] → source 1 covers it when the PCB document is present; otherwise source 3 and the issue says so.
- [Nested repeats] → instantiated recursively up to `MAX_CHANNELS` in total; beyond it the error case.
- [The counts of `altium-set:02` do not reach zero] → the page lists every remaining element with its cause; the hypothesis criteria are about the channels, not about zero.

## Migration Plan

- An import of a multi-channel project changes: more components, other references. `altium.import.channels` says so. Single-channel projects are byte-equal in their canonical model (a regression test over the corpus sets 01, 03, 04, 05).
- Rollback: `parse_repeat` returns `None`, which restores the single instance.

## Open Questions

- **Should the channel index be part of `Component.path` or only of the module name?** Default: of the module name, so the path stays a sequence of names.
- **Should source 3 be allowed to run when a board exists but lacks a channel?** Default: yes, with `altium.import.channel-naming` naming the channel.
