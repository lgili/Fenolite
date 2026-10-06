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

## Files and public API

- `src/fenolite/backends/altium/read/annotation.py`: `read_annotation(data, *, file) -> AnnotationFile` (entries by unique-id path; the text kept byte for byte).
- `src/fenolite/backends/altium/adapter/netlist.py`: `parse_repeat(text) -> Repeat | None`, `MAX_CHANNELS`, channel instantiation in the instance builder.
- `src/fenolite/backends/altium/adapter/project.py`: `link` per channel; `channel_designator(format, designator, channel)`; `NAMING_FORMATS`.
- `src/fenolite/backends/altium/adapter/codes.py`: `altium.import.channels` (info), `altium.import.channel-naming` (warning).
- Tests: `tests/unit/backends/altium/adapter/test_channels.py`, `tests/unit/backends/altium/read/test_annotation.py`, authored fixtures under `tests/data/altium/channels/` (built with Fenolite's own record writers from a script, declared in `tests/data/MANIFEST.toml`); `tests/corpus/test_altium_channels.py`.

## Sources registered by this change

- S-0185 (registered): multi-sheet and hierarchical designs.
- New: Altium's public documentation pages on multi-channel design, on the channel naming formats and on board-level annotation (read for facts).
- The corpus rows of `altium-set:02` (already in the manifest): the project file, its sheets and its PCB document.

Each new source gets the next free `S-` number in `docs/evidence/sources.md` when its task runs (numbers are not reserved here, because changes that run in parallel would collide), with its licence and what was read. Sources under a copyleft or an all-rights-reserved licence are read for facts only; nothing is transcribed.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-A-IMP-RPT-COUNT | A sheet symbol whose designator is `Repeat(NAME, a, b)` stands for `b - a + 1` channels of its child sheet; a board of the same project holds that many components per component of the child sheet | `tests/corpus/test_altium_channels.py::test_count` | on `altium-set:02`, for every repeated sheet symbol, the number of board components per sheet component equals the channel count |
| H-A-IMP-RPT-BOARD | A board component of channel `i` carries the unique-id path of its sheet symbol and of its sheet component, and its designator is the channel designator | `tests/corpus/test_altium_channels.py::test_designators` | every component of every channel is linked to exactly one board component; no `model.duplicate-ref` |
| H-A-IMP-RPT-NETS | A sheet entry `Repeat(NAME)` connects channel `i` to member `i` of the parent bus, and other entries connect all channels to one net | `tests/corpus/test_altium_channels.py::test_nets` | `netlist.assignment_compare` between the imported schematic and the PCB document of `altium-set:02` has no element on one side only among the channels' pins |
| H-A-IMP-RPT-FORMAT | The naming formats of the project file give the channel designators that Altium shows, for each documented format | author report, Part R | for each format of the authored project, the designators Altium shows equal `channel_designator` |
| H-A-IMP-RPT-ANNOT | The annotation file of a project maps a unique-id path to the board-level designator | `tests/unit/backends/altium/read/test_annotation.py` and author report, Part R step 4 | the designators read from the file Altium saved equal those of the board |
| H-A-IMP-PINMAP | A footprint model's pin map on the sheet names the pad of each pin, and the board's pads use those names | `tests/corpus/test_altium_channels.py::test_pin_map` | on the corpus sets, applying the map never increases the elements on one side only, and removes the 4 differing elements of `altium-set:02` or says which remain |

All start `INFERRED`. No id above is in `docs/hypotheses.md` or in another active change (checked 2026-10-06).

## Author report: Part R, channel naming

Needed only for source 3 (no board, no annotation file). Files: an authored two-channel project that Fenolite builds from records (`tests/data/altium/channels/`), outside the repository.

1. R1: open the project in Altium Designer and compile it. Expected: no error; the Navigator shows two channels of the child sheet.
2. R2: for each naming format offered in Project Options » Multi-Channel, select it, compile, and write down the designator of the component `R1` in both channels. Expected: the table of `docs/formats/altium/connectivity.md` (`H-A-IMP-RPT-FORMAT`).
3. R3: with the default format, run Design » Update PCB Document on an empty board and write down the designators on the board. Expected: the same as R2 for that format.
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
