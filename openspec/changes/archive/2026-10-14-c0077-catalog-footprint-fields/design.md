## Context

- **Milestone.** v0.4, the agent track (c0077 to c0081). Written against `origin/dev` at `9aba2dff`.
- **What exists** (at `9aba2dff`).
  - `cli/cmd_build.py::_catalog_definitions` merges the catalog definitions a design names with the ones the script authored, and passes both as "authored" definitions to the build.
  - `lens/build.py::_resolve` turns each into a definition with slots through `mod.prepare_authored_definition`, (`mod.py`, line 267), whose root slot list is `name`, `description`, `kind`, one slot per pad, per graphic and per model. It holds no `property`.
  - A catalog footprint definition carries no `properties` entry (`catalog/__init__.py`, the `FootprintDef(...)` of line 1067). The `Reference`, `Value` and `Description` entries of line 952 belong to the catalog's symbol definitions and never reach a footprint.
  - `embed._header` walks the emitted footprint and replaces the value atom of a `property` named `Reference` or `Value`. A footprint without those properties is written without them.
  - `mod.write_footprint` writes the same definition into `lib/<nickname>.pretty/`, also without them.
  - `read_board` takes a component's `ref` from the `Reference` property (`""` without one), and the stages of `check` name a pad `<ref>-<number>`.
  - A library footprint of KiCad's own libraries, and of the authored mini library under `tests/data/libs`, carries both properties, so the examples and the acceptance projects never met this path.
- **The second backend.** `build --target altium` takes footprint definitions as the script or the catalog gives them (`lens/altium.py::resolve_footprints`), not through `mod.prepare_authored_definition`, and names each placed component from `Component.ref` and `Component.value` (`backends/altium/lower.py`). The defect and its repair are in the KiCad backend only.
- **Reproduction** (2026-10-05, `dev` at `1882644`, `kicad-cli` 10.0.6, a folder outside the repository): `J1` (`Fenolite:Connector_2`, `Fenolite:Header_1x2_P2.5`), `R1` (`Fenolite:Resistor`, `Fenolite:Chip_0603`), `D1` (`Fenolite:LED`, `Fenolite:Chip_0805`), three nets. `build --confirm` exits 0 with every lib id `builtin`. The board's footprints hold `fenolite.path` as their only property. `check` reports `netlist.assignment-differs` for `-1` and `-2`, and `netlist.uncovered` for `D1-1`, `D1-2`, `J1-1`, `J1-2`, `R1-1` and `R1-2`.
- **Repeated in part** (2026-10-07, `dev` at `a32dcfa4`): a one-part catalog design (`R1`, `Fenolite:Resistor`, `Fenolite:Chip_0603`) builds with exit 0, the board footprint holds `fenolite.path` as its only property, and `lib/Fenolite.pretty/Chip_0603.kicad_mod` holds no property. `check` was not run that day; task 0.1 runs it on the tip of the day.
- **Constraints.** Stdlib only. Integer nanometres. Deterministic output: every uuid derives from a key. No change to a footprint that already has both properties.

## Goals / Non-Goals

**Goals:**
- Every footprint that Fenolite places carries `Reference` and `Value`, whatever the origin of its definition.
- A catalog-only project is a normal KiCad project: its vendored library holds conventional footprints, and KiCad's library check has nothing to say.
- The acceptance of the catalog is "passes `check`", not "builds".

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- A general model of library fields in `FootprintDef`. The two fields are slots of the KiCad backend, as they are for footprints read from a file.

## Decisions

1. **One function gives the default fields.** `embed.default_fields(defn) -> tuple[FieldDefault, FieldDefault]`, with `FieldDefault(name, text, layer, position)`:
   - `box = embed.footprint_extent(defn)` (the `F.CrtYd` box, else the pads' box, else the empty box at the origin), and `cx` the centre of its X range.
   - `Reference`: text `REF**`, layer `F.SilkS`, position `(cx, box.y1 − 1 mm)`.
   - `Value`: text `defn.name`, layer `F.Fab`, position `(cx, box.y2 + 1 mm)`.
   - Both: angle 0, size 1 mm × 1 mm, stroke 0.15 mm, centred, visible. These are the values of the authored mini library and of `fenolite.path` today.
   - `REF**` is the text for every prepared definition, a catalog footprint included: it is what a KiCad library footprint holds, and the reference prefix of a part (`R`, `J`) belongs to its symbol. The catalog's footprint definitions hold no `Reference` entry that could compete with it (Context).
   - Rejected: both fields at the origin (they would lie on the pads of every two-pad part); hidden fields (an assembler needs the reference on the silkscreen, and `Part.field(..., visible=False)` hides one).

2. **Definitions without a file gain the fields when they are prepared.** `mod.prepare_authored_definition` puts two `property` children after `kind` and before the pads, `Reference` first, as opaque slots built from `default_fields`. `FootprintDef.properties` gains `Reference` and `Value` with the same texts, so `defn.reference` and `defn.value` answer as they do for a footprint read from a file. An entry that an authored definition already holds under either name wins over the default text; no definition of the catalog has one.
   - The definitions that the Altium build reads are not prepared, so they gain nothing (Decision 7).
   - A definition that already has slots is returned unchanged, as today.
   - `mod.write_footprint` then writes them into the vendored `.kicad_mod` with no further change. Their uuids in the library file derive from the lib id and the property name.
   - Rejected: adding them only on the board. The vendored library footprint would then differ from the board footprint in two children, and KiCad's library check compares the two.

3. **`place_footprint` guarantees both fields.** After `_header` has set the values, a name that no `property` child carried is added from `default_fields`, with the component's value as its text.
   - This covers a footprint file of another origin that lacks one of them. KiCad's own libraries always have both.
   - The added node is placed before the first existing `property` child, or after `at` when there is none. Its uuid is `placement_uuid(key, "/footprint/property:<name>")`.
   - The node is added before the bottom-side pass, so a bottom part gets `B.SilkS` or `B.Fab` and a mirrored text, by the code that flips library fields.
   - No new return value is needed. The build compares `defn.properties` with the two names before it places a part, and reports `build.field-added` (info) once per definition, naming the lib id and the fields. Prepared definitions never trigger it.

4. **Rebuild over an older board.** A matched footprint that the build keeps stays as a whole node (`docs/lens.md`, "Kept, re-placed and dropped items"), so a board written before this change would keep footprints without the two fields.
   - On a kept footprint, a `Reference` or `Value` field that the board's node lacks is taken from the built copy and added before the node's first field. This is the rule that user properties follow today (`docs/lens.md`, "User properties on kept footprints": "a missing one is the built copy's field"; `lens/preserve.py::_apply_user_properties`). `preserve.py` and `lens/build.py` grew with c0069 after this proposal was first written, so task 0.1 reads both again and names the function that takes the rule.
   - A field the board's node has is never touched by this rule: the precedence of `merge_fields` (c0030) stays.
   - A re-placed footprint is the built copy and needs nothing.
   - The build reports nothing for it: the plan of `--dry-run` lists the board as changed.

5. **`Part.field` needs nothing new.** `read_board` maps the two properties to `FootprintField`s ("Footprint fields on boards"), so a request finds its field. Today such a request ends in `FEN-3004`, because the footprint has no field of that name.

6. **Acceptance fixture.** `tests/_catalog_design.py::catalog_blink()` builds the three-part design in code, with every part placed and three scripted tracks (`design.track`), so no router and no fill take part.
   - Hermetic test: build for targets 9 and 10; `fenolite check --stages model.validate,copper.clearance`; and the comparison of the model with the re-read board through `checks.assignment_compare.compare`, which is the half of the net stage that needs no tool (the other half compares the board with `kicad-cli`'s export).
   - Oracle test: the same project on `kicad-cli` 9.0.9 and 10.0.6; `check` exits 0, and the design-rule report holds no `lib_footprint_issues`, no `lib_footprint_mismatch` and no unconnected item.

7. **The Altium build is left as it is, and a test says so.** The designator and the comment of a placed component come from `Component.ref` and `Component.value`; c0126 (open on `dev`) adds their place from the instance's `Reference` and `Value` fields "where the instance has them", and an instance lowered for Altium from a definition that was not prepared has none.
   - The hermetic test builds the catalog blink with `--target altium` twice, once as the code is and once with the property step of `mod.prepare_authored_definition` patched out: every planned Altium file has the same bytes, and the issue lists are equal.
   - So no kit sample and no recorded kit run (c0091) is invalidated: the kit holds Altium documents.
   - Rejected: giving the Altium PCB library a designator and a comment text from the default fields. That is a change of the Altium writers with its own format facts, and belongs to the Altium follow-ups.

8. **One issue code, explained.** `build.field-added` (info) gets a table in `src/fenolite/cli/data/explain.toml`, because `tests/unit/cli/test_explain_cmd.py` fails for a code without one, and a row in `docs/cli-contract.md`.

9. **Order.** After `0.3.0` is released, on top of c0126 and c0123. c0126 promises byte-equal KiCad outputs from 0.2.0 through 0.3.0; this change is the first one that moves those bytes, and only for footprints from the catalog or from `dsl.Footprint`. The changelog line says so in bold.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/kicad/embed.py` (extended) | `FieldDefault(name, text, layer, position)`; `default_fields(defn) -> tuple[FieldDefault, FieldDefault]`; `FIELD_SIZE`, `FIELD_THICKNESS`, `FIELD_GAP` |
| `src/fenolite/backends/kicad/mod.py` (extended) | `prepare_authored_definition` adds the two properties |
| `src/fenolite/lens/build.py` (extended) | the issue `build.field-added` |
| `src/fenolite/cli/data/explain.toml` (extended) | the table `build.field-added` |
| `src/fenolite/lens/preserve.py` (extended) | a kept footprint gains a missing `Reference` or `Value` field from the built copy |
| `tests/_catalog_design.py` (new) | `catalog_blink() -> dsl.Design` |
| `tests/unit/backends/kicad/test_embed_fields.py`, `tests/unit/cli/test_catalog_only.py` (new) | hermetic, with the Altium byte comparison of Decision 7 |
| `tests/kicad/build/test_catalog_only.py` (new) | oracle, both majors |
| `docs/dsl.md`, `docs/catalog/README.md`, `docs/cli-contract.md` (extended) | the generated fields and where they are placed; the new code |

## Names introduced by this change

Hypothesis `H-K-FP-FIELDS`; issue code `build.field-added`; `embed.FieldDefault`, `embed.default_fields`, `embed.FIELD_GAP`, `embed.FIELD_SIZE`, `embed.FIELD_THICKNESS`; `tests/_catalog_design.py::catalog_blink`. No command-line flag, no result key, no model field, no source id. None of these names is in the tree at `9aba2dff`.

## Sources registered by this change

None. The placement of the generated fields is a Fenolite choice, and the syntax of a `property` child is already recorded in `docs/formats/kicad/` (S-0001).

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-FP-FIELDS | `kicad-cli` 9.0.9 and 10.0.6 load a project whose footprints carry the generated `Reference` and `Value` properties, in the board and in the vendored library; their design-rule check names each pad by its reference, and reports no `lib_footprint_issues` and no `lib_footprint_mismatch` for it | `tests/kicad/build/test_catalog_only.py` | on both majors, `fenolite check` of the catalog blink exits 0 with no item of those two types and no unconnected item |

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Default fields of a prepared definition | mechanical | `test_embed_fields.py` |
| Missing field added at placement | mechanical | `test_embed_fields.py` |
| Nets of a catalog-only board equal the script's | INFERRED (the board read) | `tests/unit/cli/test_catalog_only.py` |
| The project is accepted by KiCad | KICAD-VERIFIED, `H-K-FP-FIELDS` | `tests/kicad/build/test_catalog_only.py` on 9.0.9 and 10.0.6 |
| The Altium documents of the same design do not change | mechanical | `tests/unit/cli/test_catalog_only.py -k altium` |

## Budget (3.5 days)

| work | days |
|---|---|
| entry check (with the list of digests that move) and register | 0.5 |
| default fields and prepared definitions | 0.75 |
| placement guarantee and the build issue | 0.5 |
| rebuild of an older board, `Part.field` on generated fields | 0.5 |
| hermetic and oracle acceptance | 0.75 |
| docs, closing | 0.5 |
| **total** | **3.5** |

Cut order: (1) the `build.field-added` info for library footprints of another origin (the field is still added). Not optional: the two fields on prepared definitions, in the board and in the vendored library, and both acceptance tests.

## Risks / Trade-offs

- [Built projects change once] → two properties per footprint, stated in bold in the changelog; a rebuild writes them and changes nothing else. The change lands after `0.3.0`, so the byte promise of c0126 is kept for the release it was made for.
- [A pinned digest of a built KiCad file moves] → task 0.1 lists them before any code changes; each is regenerated in the commit that moves it.
- [A generated `Reference` overlaps a neighbour on a dense board] → KiCad reports silkscreen overlaps as warnings, which do not fail `check`; the script moves a field with `Part.field`.
- [KiCad's library check compares fields] → the vendored library carries the same properties with library texts; `H-K-FP-FIELDS` measures it on both majors.
- [The catalog grows while this change is open] → c0076 is archived and the catalog holds 100 footprints at `9aba2dff`; a later one goes through the same function, and the hermetic test iterates over every catalog footprint and places each once.

## Migration Plan

- Additive for definitions read from a file: nothing changes for a footprint that has both properties.
- Projects built from catalog or authored footprints gain the properties on the next build, on kept footprints too (Decision 4). `build --dry-run` lists the board and the library files as changed.
- The model document of such a project gains two entries per footprint in a list it already has. No key is new: 0.2.x reads the document, and a document of 0.2.x loads unchanged.
- Altium projects do not change (Decision 7).
- Rollback: remove the two properties from `prepare_authored_definition`; boards written meanwhile stay valid KiCad files.

## Open Questions

- **Should `check` name a footprint without a reference?** A board that Fenolite did not build may hold an empty `Reference`; today the net comparison then reports pads named `-1`. Default: not here. A rule `model.empty-ref` belongs with the model's validation and needs its own change.
- **Should the Altium PCB library of a catalog footprint carry a designator and a comment text at the default places?** Default: not here (Decision 7). The placed components are named from the model today.
