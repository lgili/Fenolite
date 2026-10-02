## Context

- **Origin.** A testing agent built a real board only through Fenolite's public API: the dogfood buck board, 29 parts. Two of its findings concern c0011's build (B1 and B2 of its report):
  - **B1.** A component cannot carry a user property, such as a part number or a supplier code, onto its placed footprint. A model-API component with one is refused by c0017's writer (`kicad.board.projection-read-only`), or loses it in c0011's build.
  - **B2.** Footprints of the official (global) libraries gave 29 `lib_footprint_issues`, because `kicad-cli` runs with an empty configuration and c0011 vendors only project-row footprints.
- **c0011 (archived on 2026-10-02, commit 5d9b209; it was being implemented when this change was written).** Its archived text, now the living `design-dsl` spec, is the contract; its code (`src/fenolite/dsl/`, `src/fenolite/lens/build.py`, `src/fenolite/cli/cmd_build.py`) and test helpers (`tests/_buildhelp.py`, `tests/_build_judge.py`, `tests/kicad/build/`) give the real names. Relevant decisions:
  - Decision 9: `to_model` sets `Component.properties == {"fenolite.path": <component path>}`. The DSL `Part(ref, lib_id, footprint=None, value="")` has no properties.
  - Decision 15: `embed.with_property(defn, *, name, value)` appends one hidden property after the definition's last `property` child, in the form `(property "<name>" "<value>" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid …) (effects (font (size 1 1) (thickness 0.15))))` (S-0058). The build places `with_property(defn, name=PATH_PROPERTY, value=<path>)` and sets `Component.properties` to what `read_board` projects. Rejected there: a `properties=` argument on `place_footprint`.
  - In the working tree, `build_design` sets each component's `properties` to the extended definition's properties plus `Reference` and `Value`. Any other entry of the incoming `Component.properties` is dropped without an issue.
  - Decision 17: every footprint of a project-table row is copied to `lib/<nickname>.pretty/<entry>.kicad_mod`, with one `${KIPRJMOD}` row per nickname written by `libs.write_lib_table`. Footprints of global or template rows are not vendored (`build.global-library`, info). Rejected there: "vendoring global libraries (size, and the official libraries' licence is the user's business)".
  - Decision 20: `check_existing` replaces an output only when its bytes are planned unchanged or its SHA-256 equals the last record (`.fenolite/build.json`); otherwise `build.layout-exists`.
  - Its probes are pinned in the working tree's probe files (2026-10-02): `build-pathprop-t9` and `-t10` are `present` on 10.0.6 and `build-pathprop-t9` is `load` on 9.0.9, so the property form holds; `build-libtable-t9` and `-t10` are `equal` on both majors, so the vendored table form holds. c0011's commit is the contract, and task 1.1 re-checks these outcomes.
- **Writer (living `kicad-file-backend`, c0017).** "Projected fields on write" rewrites only the value atoms of `Reference` and `Value`; any other property of the model that differs from, or is absent from, the footprint's fragments gives `kicad.board.projection-read-only`. The brief keeps it strict; c0030 owns it.
- **Isolated `kicad-cli`.** c0009's runner gives every run an empty `KICAD_CONFIG_HOME`. c0013's `check` keeps that isolation and copies every `${KIPRJMOD}` library folder inside the project (its copy set). c0013 handed a library pass-through to c0021, and c0021 Decision 14 declines it. So nothing in the plan lets `kicad-cli` see a built project's global footprints, except vendoring. c0021 adds a `cache` source and a `scan` row origin to the resolver.
- **Library facts.**
  - Project tables beside the project, global tables in the configuration folder, project-over-global precedence (S-0045, S-0046).
  - `H-K-LIB-DRC` is `KICAD-VERIFIED (9.0.x, 10.0.x)` since c0017: DRC checks placed footprints against the library that a project `fp-lib-table` names. c0011's design still calls it open on 9.0.9.
  - The official libraries are CC-BY-SA 4.0 with an exception for designs; redistributing the collection is not covered (S-0048). `ip-hygiene` forbids committing them, and the plan's resolution of the official-library question keeps CI on the CC0 mini library, with official variants committed as DSL source only.
- **Property facts.**
  - Every `Mini_v9` footprint holds `Reference`, `Value`, `Datasheet` and `Description` properties, and the boards built from them in the pre-proposal runs kept all four. Board files also carry KiCad's own `ki_fp_filters` (S-0024, `H-K-PCB-READ`).
  - A 10.0.6 re-save removes a footprint's `Footprint` property (`H-K-UUID-KEEP-2`).
  - `Atom.string` escapes `"`, `\`, LF and CR, and KiCad 9.0.9 and 10.0.6 decode them (`H-K-SEXPR-ESCAPES`, `KICAD-VERIFIED (9.0.x, 10.0.x)`).
- **Pre-proposal runs (2026-10-02, scratch folders outside the repository).** c0011's in-tree `build_design` built the blink circuit with every symbol and footprint served by a fake global table: `<D>/<M>.0/fp-lib-table` and `sym-lib-table` in a configuration folder `D`, naming a temporary copy of the CC0 `Mini_v9` library. Variants were then written beside that output. `kicad-cli pcb drc --format json --severity-all` ran on 10.0.6 (local; targets 9 and 10) and on the pinned 9.0.9 image (target 9; S-0020, S-0029). Counts are `lib_footprint_issues` / `lib_footprint_mismatch`. Every run also had three `unconnected_items` (unrouted) and no other violation type, and the two majors gave the same counts:

  | run | configuration | counts |
  |---|---|---|
  | c0011 output, not vendored | empty | 3 / 0 |
  | used footprints copied to `lib/Mini.pretty/`, one project row | empty | 0 / 0 |
  | the same, with user properties (one value holding `"`, `\` and `µ`; one part on the bottom side) | empty | 0 / 0 |
  | not vendored | `D` | 0 / 0 (the global table is read) |
  | not vendored | `D_alt`: `Mini_R_0603` pad 1 moved 0.05 mm | 0 / 1 (control) |
  | vendored | `D_alt` | 0 / 0 (the project row wins) |
  | vendored without `Mini_LED_THT_3mm` | empty | 1 / 0 |
  | vendored without `Mini_LED_THT_3mm` | `D` | 1 / 0 (no per-item fallback) |

  - With user properties, c0011's writer raised nothing, and `D1`'s properties were written on `B.Fab` with a mirrored text.
  - A 10.0.6 re-save (`pcb upgrade --force`) of the property boards (targets 9 and 10) kept every user property's name, decoded value and `(hide yes)`, and kept `fenolite.path`.
  - A user `Datasheet` appended after the library's `Datasheet` gave a clean DRC. The re-save merged it into the field: one node was left, holding the appended value. `datasheet` and `reference` (other letter case) were kept as separate properties.
  - c0011's official-library blink, built from the local 10.0.6 install (template rows), gave 3 / 0 without vendoring and 0 / 0 with it. Only counts were recorded; no library content was kept.
- **Corrections to the brief.** c0021 gives the resolver a cache, `kicad_common.json` variables and `scan` rows; it does not give `kicad-cli` the global tables. c0012 writes drawing sheets, not schematics; schematics come with v0.2a.
- **Order.** c0010 → c0026 → c0011 → **c0027** → c0013 → c0019 → c0020 → c0021 → c0012 → … This change MODIFIES six requirements that c0011 ADDs (Decision 17), so c0011 archives first.
- **Environment.** KiCad 10.0.6 is installed locally (macOS); 9.0.9 runs from the pinned image, locally and in the `kicad-9` job.
- **Constraints.** Stdlib only; no model entity, field, schema, id-prefix or layering change; `dsl` imports only `core` and `model`, `lens` only `model` and `backends`.

## Goals / Non-Goals

**Goals:**
- A part's user properties reach its placed footprint and read back unchanged, while the writer stays strict.
- Every name that would collide with KiCad's own fields, or with Fenolite's, is refused at the script line.
- A built project needs no global or template table: it gives the same library check on another machine and in an isolated `kicad-cli`.
- Builds stay byte-identical for unchanged libraries, and a library change is reported.

**Non-Goals:**
- Everything listed under Non-goals in the proposal.
- A user-chosen nickname, prefix or library folder for vendored copies.
- Notices or licence files written into `lib/`.

## Decisions

1. **The build embeds user properties; the writer stays strict.** For each component, the build appends every user property to the footprint definition with c0011's `embed.with_property` before `place_footprint`. It then sets `Component.properties` to the projection of the extended definition, as c0011 does for `fenolite.path`. Every property of the model is then a fragment of the footprint, so "Projected fields on write" passes unchanged, and a model edit that bypasses the build is still refused.
   - c0011's rejection of `properties=` concerned `place_footprint`; this change keeps it and adds the keyword to the DSL `Part`, a layer above.
   - Rejected: relaxing "Projected fields on write" (c0030 owns it; it would let any model edit through). Rejected: a new embed helper taking a mapping (one `with_property` call per property already gives the order and the uuids). Rejected: keeping c0011's silent drop of model-API properties.

2. **DSL surface: one keyword, checked at the call.** `Part(ref, lib_id, footprint=None, value="", *, properties=None)`. `Part.properties` is a read-only mapping in code-point order.
   - Checks raise `DslError` at the call, so the traceback points at the script line: a non-mapping or a non-`str` key or value; an empty name; surrounding whitespace in a name; a name or value that fails `str.isprintable()` (S-0105); two names equal after `str.casefold()` (S-0105); a reserved name or prefix (Decision 3).
   - The sets are `dsl.part.RESERVED_PROPERTIES` and `RESERVED_PREFIXES`. They are not re-exported, so "DSL package" needs no delta, and a unit test pins them equal to those of `lens.build` (`dsl` cannot import `lens`).
   - Rejected: a setter or a mutable mapping (two places to check). Rejected: properties on `Module` or `Design` inherited by parts (hidden defaults, and a BOM needs per-part values anyway). Rejected: numbers converted to text, because the DSL refuses bare numbers elsewhere and `{"Qty": 2}` is more likely a mistake than a field.

3. **Reserved names and prefixes, compared after `casefold`.**
   - Reserved names: `Reference`, `Value`, `Footprint`, `Datasheet` and `Description`. `Reference` and `Value` come from `ref` and `value`. `Datasheet` and `Description` are footprint fields that every mini footprint and the observed boards carry, and the observed re-save merges a duplicate `Datasheet` into the field (Context; `H-K-VENDOR-DUPNAME`). A 10.0.6 re-save removes `Footprint` (`H-K-UUID-KEEP-2`).
   - Reserved prefixes: `fenolite.`, Fenolite's namespace, whose `fenolite.path` carries the component path; and `ki_`, KiCad's own names (`ki_fp_filters`, S-0024).
   - Comparing after `casefold` is a Fenolite choice. KiCad keeps `datasheet` apart from `Datasheet` (observed), but BOM columns and agents would read them as one field.
   - Rejected: letting `Datasheet` or `Description` override the library value (a rewrite of a library fragment, which is field editing, c0030, or schematic sync, v0.2a). Rejected: exact-case reservation only.

4. **Text rules.** Values may be empty and hold any printable character. Names must also be non-empty and carry no surrounding whitespace. Two names equal after `casefold` are refused, as c0011 refuses net names that differ only in case (its Decision 14). The writer's escapes are settled for `"` and `\` (`H-K-SEXPR-ESCAPES`), and the `vendor-props` probe holds such a value.
   - Rejected: control characters through octal escapes. KiCad would read them (`H-K-SEXPR-ESCAPES`), but a multi-line part number is a mistake, and v0.2a's CSV exports would have to quote it.

5. **Form, layer and visibility: c0011's form, unchanged.** Hidden, on `F.Fab` at `(at 0 0 0)`, with a 1 mm font and 0.15 mm stroke. `place_footprint` moves it to `B.Fab` with `mirror` for a bottom part. Hidden fields add no silkscreen or fabrication text that could overlap (the dogfood board's 25 silkscreen warnings came from visible field texts left where the library put them, A1). Position, layer, visibility and size are c0030's typed fields.
   - Rejected: visible text. Rejected: per-property visibility in the DSL (c0030).

6. **Order: library properties, `fenolite.path`, user properties in code-point order.** `with_property` appends after the last `property` child, so the calls give this order directly.
   - Locator indices count earlier siblings with the same head (`kicad-sexpr`). So adding a user property moves no uuid of the library properties or of `fenolite.path`, which c0019 reads. A design without user properties gives c0011's bytes.
   - Rejected: script order (the model sorts mappings, so it would be lost on the first round trip). Rejected: user properties before `fenolite.path` (adding one would move `fenolite.path`'s locator and uuid).

7. **Build-side checks for model-API components.** `build_design` takes any model `Design`, not only one from `to_model`. Every entry of `Component.properties` other than `fenolite.path` is a user property. The build checks run before any file is written:
   - `build.property-reserved` (error): Decision 3.
   - `build.property-invalid` (error): Decision 4.
   - `build.property-conflict` (error): the resolved footprint definition already holds a property whose name is equal after `casefold`, unless name and value are identical, in which case nothing is appended. This is the only check that a DSL script can reach, because the DSL reads no library.
   - The sets live in `lens.build` (`RESERVED_PROPERTIES`, `RESERVED_PREFIXES`).
   - Rejected: appending a second node of the same name (Context: KiCad merges or keeps both, and the reader keeps the last). Rejected: silently preferring the library or the script value.

8. **Vendor every placed footprint by default, whatever the row origin.** `build_design(..., vendor="all")` copies each placed footprint from `Location.item_path`. This covers `global`, `template`, c0021's later `scan` and any future origin, because the rule names `project` only for the opt-out. `vendor="project"` keeps c0011's rule and its `build.global-library` infos; `fenolite build --vendor project` sets it.
   - This answers B2, the coordinator's recommendation. A built project then opens with the same library check on any machine and in every isolated `kicad-cli` run (c0013, c0020). The pre-proposal runs went from three `lib_footprint_issues` to none, on both majors and for the official-library blink.
   - Rejected: keeping c0011's rule (29 issues on the dogfood board, and `check` cannot judge library parity for official footprints). Rejected: vendoring only when no global table exists (output would depend on the machine). Rejected: passing the user's global tables to `kicad-cli` (c0021 Decision 14; machine-dependent). Rejected: no opt-out (some users manage libraries centrally or do not want copies in shared projects).

9. **Nickname policy: same nickname, lib ids unchanged.** A footprint of global row `N` goes to `lib/N.pretty/`, with a project row `N`. The board, `Component.lib_footprint_ref` and `.fenolite/` keep `N:<entry>`, as the design wrote it.
   - In KiCad's library check, the project row then wins over a global row `N` and hides the global library's other items (both observed on both majors; `H-K-VENDOR-SHADOW`). The project is checked against its own copies. The footprint chooser of the GUI is expected to use the same tables, so items that were not vendored would not be offered under `N`; this is not probed. `docs/dsl.md` states both, and `--vendor project` avoids them.
   - Rejected: a distinct nickname with rewritten lib ids. The model, BOM grouping and the future schematic `Footprint` fields would carry a packaging name, every id would change when the opt-out is used, and a reserved nickname prefix would be needed against user tables.

10. **Only placed items: no whole libraries, no 3D models, no symbols.**
    - Whole libraries: rejected for size, and because copying a library collection is what the licence exception does not cover (S-0048).
    - 3D models: left at their `${KICAD…_3DMODEL_DIR}` paths. The 3D viewer may lack them on another machine; the library check of the pre-proposal runs passed without copying them.
    - Symbols: deferred. Built projects have no schematic before v0.2a, and pcbnew and `kicad-cli pcb drc` read no symbol library. The schematic writer applies the same rule to `sym-lib-table` (Open Questions).

11. **Unsafe names are refused.** The dispatcher writes every planned path as given (`atomic_write(ctx.cwd / path)`). A nickname comes from a table that may lie outside the project, so a nickname holding `/` or `\` could place a copy outside `lib/`. A nickname with a non-printable character, or two vendored paths equal after `casefold`, would also break the folder on another file system. All of these give `build.vendor-unsafe-name` (error) with the build checks, for project rows too.
    - Rejected: escaping or renaming such nicknames (the project row must keep the design's nickname, Decision 9).

12. **Determinism and library changes.** Vendored bytes are the source bytes, so two builds with the same libraries are identical ("Reproducible builds").
    - Every build re-reads the source library, places from it and copies it again, so the board and its vendored library always agree.
    - When the last record (`read_record`, passed by `cmd_build` as `record`) holds another SHA-256 for a vendored path, the build gives `build.library-changed` (warning). A library update then shows in the `--dry-run` plan before `--confirm` changes the board's footprints.
    - The old copy is replaced when it is untouched since the last build. A copy edited by the user is protected by c0011's `build.layout-exists`.
    - Stale copies of removed parts stay in `lib/` (c0011; c0019 may prune).
    - Rejected: pinning the first vendored copy (the build would read its own output, and the board would diverge from the libraries the script names). Rejected: refusing a changed library until `--discard-layout` (library updates are normal).

13. **Licence: copies go only where the user writes.**
    - Vendored files are written into `--out` only. Tests use the CC0 mini library as a fake global or template library (`tests/_libs.make_install`, `isolated_kicad_env`, authored configuration folders).
    - The official-library blink is built only into `tmp_path` (`needs_libs`), and the residue test keeps official items out of the repository.
    - `docs/dsl.md` and `fenolite build --help` say that the copies keep their library's licence (S-0048: CC-BY-SA 4.0 with an exception for designs, the collection not covered), give no legal advice, and name `--vendor project`.
    - Rejected: a notice file in `lib/` (wording a licence notice is legal advice, which Fenolite does not give; the facts are in `docs/dsl.md`).

14. **No overlap with c0021 or c0013.** This change changes neither the resolver's sources, tables or variables, nor `kicad-cli`'s configuration. It changes only what the build copies.
    - c0021 widens where the build's resolver finds libraries (`cache`, `scan`, `kicad_common.json`); whatever it finds is vendored by Decision 8, and c0021 changes no build output.
    - c0013's copy set already includes `${KIPRJMOD}/lib/…` folders, and its 256 MiB limit is far above a few placed footprints.
    - The `vendor-shadow` and `vendor-hide` probes need `kicad-cli` to read a global table from `KICAD_CONFIG_HOME` (c0021's `H-K-LIB-CONFIGHOME`). Each carries its own control, so this change settles nothing of c0021's.
    - Rejected: settling `H-K-LIB-CONFIGHOME` here (c0021's row and probes; this change needs only a control per probe). Rejected: a resolver option that skips global tables during `build` (the user's own tables are a legitimate source; vendoring makes their use portable).

15. **Evidence constants that apply only when used.**
    - `lens.build.PROPERTY_EVIDENCE` (`INFERRED`; `H-K-VENDOR-PROPS`, `H-K-VENDOR-DUPNAME`) joins the envelope when a user property is written.
    - `lens.build.VENDOR_EVIDENCE` (`INFERRED`; `H-K-VENDOR-GLOBAL`, `H-K-VENDOR-SHADOW`) joins it when a footprint of a non-project row is vendored.
    - This follows c0011's `embed.EVIDENCE`, which joins only for bottom parts. Both stay `INFERRED` after their rows are settled: the oracle covers the blink and its variants, not every design.
    - Rejected: adding the rows to `BUILD_EVIDENCE` (every envelope would cite behaviour it did not use).

16. **Probes first, on boards made without this change's code.** Task group 2 runs before the code of groups 3 to 5. `tests/kicad/build/_vendorcases.py` makes the fake libraries and builds the boards:
    - The fake libraries come from copies of `Mini_v9.pretty` and `Mini_v9.kicad_sym` in a temporary folder: `D` and `D_alt` (Context).
    - The plain and vendored boards come from c0011's `build_design` plus file copies, as in the pre-proposal runs.
    - The property board is laid out through the model API like c0011's `tests/kicad/build/_probe_boards.py::probe_board`, with `embed.with_property` applied before `place_footprint`, and written with `triad.write_triad`.
    - Outcomes use c0017's closed set (`kicad-oracle`, "Vendored projects and user properties pass the oracle").
    - **Stop rules:** `vendor-global` other than `equal` stops the vendoring half (tasks 5.1 and 5.2 and the vendoring cases of task 6.1). `vendor-props` other than `equal` stops the property half (groups 3 and 4 and the property cases of task 6.1). Each stays stopped until its form is corrected. The other probes only feed the docs.
    - Since `H-K-LIB-DRC` is settled on both majors, `vendor-global` is asserted on 9.0.9 as well, unlike c0011's 9.0.9 libtable outcomes.
    - Rejected: probing after the code (a refuted table form or property form would change public behaviour late).

17. **Requirement deltas and archive order.**
    - **MODIFIED** (each a copy of c0011's ADDED text, edited): "DSL to model", "Placement of built parts", "Built project files", "Build command", "Build issue codes", "Build evidence".
      - `openspec validate --strict` accepts them now. `openspec archive` succeeds only after c0011 has archived, so c0011 archives first.
      - c0019 also MODIFIES "Built project files", "Build command", "Build issue codes" and "Build evidence" (and "DSL package" and "Edited outputs are not overwritten", which this change leaves alone). c0019 archives after this change, and its copies of those four start from these texts (rebased 2026-10-02).
      - If c0011's text changes before it archives, task 1.1 copies it again.
    - **ADDED** where nothing of c0011 is contradicted: "User properties in the DSL" (so "Design structure and names" keeps its text), "User properties on built footprints", "Footprints of every row origin are vendored", and `kicad-oracle` "Vendored projects and user properties pass the oracle".
    - **Unchanged:**
      - "DSL package" (nothing new is re-exported);
      - "Edited outputs are not overwritten" (vendored files are already planned files under its rule);
      - "Built boards read back with the same connectivity" (it already compares `properties`);
      - "Reproducible builds";
      - every `kicad-file-backend` and `kicad-library-resolution` requirement.
    - Rejected: amending c0011 (it was being implemented when this change was written, and is archived now).

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/dsl/part.py` (c0011; extended) | `Part(ref: str, lib_id: str, footprint: str \| None = None, value: str = "", *, properties: Mapping[str, str] \| None = None)`; `Part.properties: Mapping[str, str]` (read-only, code-point order); `RESERVED_PROPERTIES: frozenset[str] = frozenset({"Reference", "Value", "Footprint", "Datasheet", "Description"})`; `RESERVED_PREFIXES: tuple[str, ...] = ("fenolite.", "ki_")`; not re-exported |
| `src/fenolite/dsl/convert.py` (c0011; extended) | `to_model` puts `Part.properties` into `Component.properties` beside `fenolite.path`, keys in code-point order |
| `src/fenolite/lens/build.py` (c0011; extended) | `build_design(…, vendor: Literal["all", "project"] = "all", record: Mapping[str, str] \| None = None) -> BuildOutput`; `VENDOR_MODES = ("all", "project")`; `RESERVED_PROPERTIES`; `RESERVED_PREFIXES`; `PROPERTY_EVIDENCE: Evidence`; `VENDOR_EVIDENCE: Evidence`; `BUILD_ISSUE_CODES` gains `build.property-reserved`, `build.property-invalid`, `build.property-conflict`, `build.vendor-unsafe-name` (errors) and `build.library-changed` (warning) |
| `src/fenolite/cli/cmd_build.py` (c0011; extended) | option `--vendor {all,project}` (default `all`) with its licence note; `read_record(out)` read once and passed to `build_design` and `check_existing` |
| `src/fenolite/backends/kicad/embed.py`, `pcb.py`, `libs.py` | unchanged (`with_property`, the writer and `write_lib_table` are used as they are) |
| `src/fenolite/backends/kicad/PROVENANCE.md` | rows: user-property form and order; vendoring of every row origin with the project-over-global rule; oracle runs |
| `docs/dsl.md` (c0011; extended) | sections "User properties" and "Vendored libraries" (policy, nickname rule and its GUI effect, only placed items, library changes, stale files, licence note, `--vendor project`) |
| `docs/formats/kicad/board.md`, `docs/formats/kicad/libraries.md` | fact rows with `H-K-VENDOR-PROPS`, `-DUPNAME` (board) and `-GLOBAL`, `-SHADOW` (libraries) |
| `docs/cli-contract.md` | `build --vendor` |
| `docs/evidence/kicad/probes/9.0.9.json`, `10.0.6.json` | `vendor-*` outcomes |
| `tests/unit/dsl/test_properties.py` (new); `tests/unit/dsl/test_to_model.py` (extended) | DSL checks, reserved sets pinned against `lens.build`, model properties |
| `tests/unit/lens/test_build_properties.py`, `test_build_vendor.py` (new); `test_build_files.py`, `test_build_issues.py`, `test_build_place.py`, `test_build_readback.py` (extended) | hermetic build tests |
| `tests/unit/cli/test_build_command.py` (extended) | `--vendor`, record passing, envelope evidence |
| `tests/kicad/build/_vendorcases.py`, `test_vendor_probes.py`, `test_vendor_oracle.py` (new); `tests/kicad/_probes.py` (extended) | `needs_kicad`, major-aware; `vendor-*` probes |
| `tests/libs/test_build_official.py` (c0011; extended) | `needs_libs` (and `needs_kicad` for DRC): the official blink vendored into `tmp_path` |

Layering: `dsl` keeps `core` and `model`; `lens` keeps `model` and `backends`; tests import both. `ALLOWED` in `tests/unit/test_import_graph.py` is unchanged.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0105 | https://docs.python.org/3/library/stdtypes.html#str.isprintable (also `#str.casefold`) | PSF License Version 2, as stated in the page footer (to verify on the page) | `str.isprintable` (which characters are printable) and `str.casefold` (caseless matching) for property names and values |

S-0106 … S-0109 stay unused. Extended "used for" cells, with no new id:
- **S-0020** (`kicad-cli` 10.0.6 as an oracle): vendored global footprints, project-over-global rows, hidden items, user properties through a re-save, the duplicate field merge.
- **S-0029** (the pinned 9.0.9 image): the same runs on 9.0.9.
- **S-0046** (library tables): the project-over-global precedence, now probed for footprint tables.
- **S-0048** (library licence): copies of placed footprints in built projects.
- **S-0024** (demo files): `ki_` property names on board footprints.

Rows of other changes cited here: S-0022 and S-0037 (`pcb drc`; `pcb upgrade` in 10.0 only), S-0038 (DRC library checks), S-0045 (`KICAD_CONFIG_HOME`), S-0058 (the hidden-property form). Only facts are taken. No KiCad source file is read, and no library content is kept: the runs record counts and outcomes only. If S-0105's URL is already registered when this change is implemented, the existing id is cited and S-0105 stays unused.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-VENDOR-GLOBAL | A project built from footprints of global or template rows, with the placed footprints vendored under `${KIPRJMOD}/lib/<nickname>.pretty` and one project row per nickname, gives no `lib_footprint_issues` and no `lib_footprint_mismatch` from `kicad-cli pcb drc` with an empty configuration folder, while the same build without vendoring gives one `lib_footprint_issues` per footprint (S-0038, S-0046; builds on `H-K-LIB-DRC` and `H-K-BUILD-LIBTABLE`) | `tests/kicad/build/test_vendor_oracle.py::test_global_vendored` (probes `vendor-global-t9`, `-t10`) | `equal` on 9.0.9 (target 9) and 10.0.6 (targets 9 and 10) |
| H-K-VENDOR-SHADOW | When a project row and a global row share a nickname, `kicad-cli pcb drc` checks placed footprints against the project row's library only: no `lib_footprint_mismatch` for a footprint equal to the vendored copy and different from the global one, and `lib_footprint_issues` for a footprint missing from the project library even when the global library holds it (S-0046) | `test_vendor_oracle.py::test_shadow`, `::test_hidden_items` (probes `vendor-shadow-*`, `vendor-hide-*`) | `present` for both probes on 9.0.9 (target 9) and 10.0.6 (targets 9 and 10), each with its control holding |
| H-K-VENDOR-PROPS | Hidden user properties appended by `embed.with_property` after `fenolite.path` load on both majors and add no `lib_footprint_mismatch`; a 10.0.6 re-save keeps their names, decoded values and `(hide yes)` (S-0038, S-0058; builds on `H-K-BUILD-PATHPROP` and `H-K-SEXPR-ESCAPES`) | `test_vendor_oracle.py::test_user_properties` (probes `vendor-props-*`, `vendor-resave-*`) | `equal` on 9.0.9 (target 9) and 10.0.6 (targets 9 and 10); `present` for the re-save on 10.0.6 (targets 9 and 10) |
| H-K-VENDOR-DUPNAME | A 10.0.6 re-save merges a second property node named like a footprint field (`Datasheet`) into that field, keeping one node with the later value, and keeps names that differ from a field only in letter case as separate properties (S-0020; motivates the reserved names) | `test_vendor_oracle.py::test_duplicate_field_name` (probe `vendor-dupname-t10`) | `present` on 10.0.6 |

Cited, not settled here: `H-K-LIB-DRC`, `H-K-BUILD-LIBTABLE`, `H-K-BUILD-PATHPROP` (a refuted row moves the user properties after the definition's last property), `H-K-SEXPR-ESCAPES`, `H-K-UUID-KEEP-2` (the reserved `Footprint`), `H-K-PCB-READ` (`ki_` names), and c0021's `H-K-LIB-CONFIGHOME`, to which the controls of the shadow probes give supporting data only.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| DSL property checks, reserved sets, `to_model` | mechanical (unit tests) | `tests/unit/dsl/test_properties.py`, `test_to_model.py` |
| Build property checks, order, form, projection, readback | mechanical (c0009 reader, c0017 writer) | `tests/unit/lens/test_build_properties.py`, `test_build_readback.py` |
| Vendoring per origin, opt-out, unsafe names, library changes, moved folder | mechanical (unit tests) | `tests/unit/lens/test_build_vendor.py`, `test_build_files.py` |
| Byte-identical rebuilds with vendored global footprints | mechanical | `tests/unit/lens/test_build_vendor.py`, `test_build_determinism.py` |
| `--vendor`, record passing, conditional evidence | mechanical | `tests/unit/cli/test_build_command.py` |
| Vendored global footprints pass the library check (`H-K-VENDOR-GLOBAL`) | KICAD-VERIFIED on 9.0.9 (target 9) and 10.0.6 (targets 9 and 10) | `test_vendor_oracle.py::test_global_vendored` |
| A project row hides a global row and its items (`H-K-VENDOR-SHADOW`) | KICAD-VERIFIED (9.0.x, 10.0.x) | `::test_shadow`, `::test_hidden_items` |
| User properties load without library mismatch, survive a re-save (`H-K-VENDOR-PROPS`) | KICAD-VERIFIED (9.0.x load; 10.0.x load and re-save) | `::test_user_properties` |
| Duplicate field name merged on re-save (`H-K-VENDOR-DUPNAME`) | KICAD-VERIFIED (10.0.x) | `::test_duplicate_field_name` |
| Official-library blink vendored, no library violation | supporting data (local, `needs_libs`; one origin) | `tests/libs/test_build_official.py` |
| The `build` envelope | INFERRED | `BUILD_EVIDENCE`, `PROPERTY_EVIDENCE`, `VENDOR_EVIDENCE` |

## Budget (5.25 working days; no roadmap line, the change comes from the dogfood report)

| work | days |
|---|---|
| 1. registers, provenance, format rows, `docs/dsl.md` skeleton | 0.5 |
| 2. probe bench and the `vendor-*` probes on both majors, stop rules | 1.0 |
| 3. DSL properties and `to_model` | 0.5 |
| 4. build: user-property checks, order, form, evidence | 0.75 |
| 5. build: vendoring of every origin, unsafe names, library changes, `--vendor` | 1.0 |
| 6. oracle suite and the official-library build | 0.75 |
| 7. `docs/dsl.md` and `cli-contract.md` | 0.25 |
| 8. closing | 0.5 |
| **total** | **5.25** |

c0008 took about three times its plan line; this estimate is a design-style count of the tasks below, and it assumes c0011's helpers exist as committed. Cut order, to 4.5: (1) `build.library-changed` and the `record` keyword (−0.25); (2) the `vendor-dupname` probe and test, the fact staying `INFERRED` from the pre-proposal run (−0.25); (3) the `needs_libs` DRC check of the official blink, its hermetic build kept (−0.25). Not optional: the DSL keyword and its checks, the build-side checks and order, vendoring of every origin with the opt-out, unsafe names, and the `vendor-global` and `vendor-props` oracle on both majors.

## Risks / Trade-offs

- [c0011's names or texts change while it is implemented] → Its committed proposal is the contract; task 1.1 re-checks every consumed name against the tree and re-copies the six MODIFIED texts if c0011's ADDED text changed.
- [The vendored row hides the rest of a global library of the same nickname] → Observed for DRC on both majors and expected, not probed, for the GUI chooser; stated in `docs/dsl.md`; `--vendor project` avoids it; a later change may offer whole-library vendoring on request.
- [Users share built projects holding copies of official footprints] → The licence note in `docs/dsl.md` and `--help` (S-0048), copies only in `--out`, the opt-out, and no copy in the repository (`ip-hygiene` residue test).
- [After c0019, a footprint kept from the board would keep the board's properties, so a property edited in the script would not reach it] → Before c0019 every build re-places from the library, so the script always wins. c0019's Decision 22 keeps that rule for kept footprints: their user properties take the script's values.
- [A library update changes footprints under a preserved layout] → `build.library-changed` names each changed copy. With c0019's kept footprints, c0020's DRC then shows `lib_footprint_mismatch`, KiCad's own signal for a changed library.
- [KiCad reads a property differently than Fenolite writes it] → The probes run first with stop rules, and the writer form is c0011's, probed by `H-K-BUILD-PATHPROP`.
- [The shadow probes depend on `kicad-cli` reading `KICAD_CONFIG_HOME`] → Each has a control that fires only when the global table was read; otherwise the outcome is `inconclusive`.
- [Overrun] → The cut order of "Budget".

## Migration Plan

- API changes are additive: a keyword-only `properties` on `Part`, keywords `vendor` and `record` with defaults on `build_design`, one option on `build`, five issue codes and two evidence constants.
- One behaviour changes by default. Footprints of global and template rows are now vendored, and their `build.global-library` infos disappear; `--vendor project` restores c0011's output.
- Rebuilding a project that c0011 built adds files under `lib/` and rows to `fp-lib-table`. The old table is untouched since its record, so c0011's rule allows the rewrite.
- Rollback: remove the keyword, the option, the codes and the constants. Projects built meanwhile stay valid KiCad projects; their extra `lib/` folders are harmless.

## Open Questions

- **Default vendoring.** Default: `all`, as the coordinator recommends, with `--vendor project` as the opt-out. A team that manages libraries centrally may prefer the opposite default.
- **Nickname policy.** Default: same nickname, lib ids unchanged (Decision 9). The alternative (distinct nickname, rewritten ids) stays rejected unless the GUI effect of hiding proves a problem in use.
- **Script properties on footprints kept by c0019.** Decided in c0019 (Decision 22 and "Kept and re-placed footprints"): the script owns user properties, as it owns `ref` and `value`. The lens updates the value of a kept node's property slot in place and appends missing ones, so "Projected fields on write" stays unchanged. A property that the script no longer names stays on a kept footprint.
- **Symbols.** Default: deferred; the schematic writer (v0.2a) vendors symbols of every origin by the same rule and writes the `sym-lib-table`. The brief placed schematics in c0012, which writes drawing sheets only.
- **`Datasheet` and `Description` from the script.** Default: refused (reserved); a typed field may come with c0030 or with the v0.2a schematic sync.
- **3D models.** Default: not vendored. A request from a real board would reopen it, with size limits.
- **Budget.** Default: 5.25 working days with the cut order above; the batch budget question to the user covers this change too.
