## Context

- **What exists.** The model, its canonical JSON and `Design.validate()` (c0004); c0008's `LibraryResolver`, `read_lib_table` and the CC0 mini library; c0009's `read_board` and `KicadCli` runner; c0017's `write_board`, `embed.place_footprint`, `embed.footprint_extent`, `layers.created_layers`, `drc.read_drc_report` and the probe module (archived 2026-10-02). The rest of the batch adds c0018's `lower_rules`, `RulesLossError` and canary helpers; c0010's `triad.write_triad` and `pro.py`. Nothing builds a model from a script, and no command writes a project.
- **Plan item 0011, part 1.** Plan day 18 asks for the D10 DSL API without `moved()`, `fenolite build design.py --out DIR` with `--dry-run`/`--confirm`, `--seed` and `--timestamp`, "uuid plus `fenolite.path` on footprints", and the acceptance "triad generated; build run twice gives identical output". Part 2 (preservation, `moved()`) is c0019.
- **Ids today.** The living `design-model` "Identifier derivation" gives created objects `uuid4` from a seeded generator and, since c0017 was archived, placed copies a third case, keyed by the caller. A seeded id depends on creation order: inserting one part shifts every later id, and c0017 derives KiCad uuids from ids (c0017 Decision 9).
- **Dispatcher.** `src/fenolite/cli/main.py` writes every planned file under `--confirm` and counts error issues afterwards, so exit 5 alone does not stop a write. An exception gives an envelope with an empty `issues` list. `from_exception` keeps a registered `cli_code`, maps any other `FormatError` to `FEN-3004` with `where` = `<file>:<locator>`, and maps the rest to `FEN-1001`. `GeometryError` has no `cli_code`, so it maps to `FEN-1001` today. `PlannedWrite.path` is relative to the working directory.
- **KiCad project facts.**
  - Project library tables sit next to the project and name folders through `${KIPRJMOD}` (S-0045, S-0046).
  - The 9.0.9 official tables have no version line and bare atoms (S-0042, S-0043). c0008's 10.0 fixture `tests/data/libs/project/fp-lib-table` starts with `(version 7)` and quotes every atom (S-0046).
  - Footprints carry user properties that can be hidden (S-0010, S-0038). The `Datasheet` property of the `Mini_v9` footprints and of 10.0.6-written demo boards has the form `(property "…" "…" (at 0 0 0) (layer "F.Fab") (hide yes) (uuid …) (effects (font (size 1 1) (thickness 0.15))))` (S-0058).
  - A 10.0.6 re-save removes a footprint's `Footprint` property (`H-K-UUID-KEEP-2`), so the survival of a new user property is not assumed.
  - `pcb drc` checks placed footprints against the library a project `fp-lib-table` names on 10.0.6 (`H-K-LIB-DRC`; open on 9.0.9). The DRC JSON keeps `unconnected_items` apart from `violations` (S-0055, S-0056).
- **Mini library.** `tests/data/libs/Mini_v9.kicad_sym` (`20241209`) holds `Mini_GND` (empty `Footprint` property) and `Mini_QFP32_IC`, whose pins 9 `VDD` and 10 `GND` are adjacent and whose `Footprint` property is `Mini:Mini_QFP-32_7x7mm_P0.8mm`. `Mini_R` (pins `1`, `2`, no names) and `Mini_LED` (`1` = `K`, `2` = `A`) exist only in the 10.0 file `Mini.kicad_sym`, with 10-only tokens. `Mini.pretty` is `20260206`, which 9.0.9 cannot load; c0017 adds 9-format `Mini_LED_THT_3mm` and `Mini_QFP-32_7x7mm_P0.8mm` to `Mini_v9.pretty`, beside c0008's `Mini_R_0603`.
- **Python facts.** `runpy.run_path` runs a file as a module and returns its globals (S-0070). `sys.dont_write_bytecode`, `sys.path`, `sys.modules` and `sys.argv` control bytecode, imports, module caches and arguments (S-0071). `PYTHONHASHSEED` changes string hashing and so set order (S-0072). `repr` of a float is its shortest round-trip form (S-0073). `contextlib.redirect_stdout` and `redirect_stderr` capture output (S-0074).
- **Layering.** `package-layering` already lists `dsl` → `model` and `lens` → `model`, `backends`, and `tests/unit/test_import_graph.py` `ALLOWED` has both. Neither package exists yet.
- **Working tree on 2026-10-02.** c0009, c0014 and c0017 are archived (c0017 by commit `7d973f1`), so `embed.py`, `drc.py`, `layers.py` and `Context.kicad_target`/`allow_lossy` are living code and specs. c0018 and c0010 are being implemented: `backends/kicad/` has no `triad.py`, `lowering.py` or `pro.py` yet. Their committed proposals are the contract; divergences are listed in Open Questions.
- **Environment.** KiCad 10.0.6 is installed locally. The `kicad-10` job (10.0.6) and the `kicad-9` job (9.0.9) run `tests/kicad`; the `kicad-9` job has no corpus, so every 9.0.9 proof uses authored CC0 data.
- **Constraints.** Stdlib only. No model entity, field, schema or id prefix changes. Budget 8.5 working days (roadmap line 6.5).

## Goals / Non-Goals

**Goals:**
- A thin, stdlib-only DSL that records a design and refuses ambiguous values (bare numbers as lengths, duplicate names).
- One command that turns `design.py` into a self-contained KiCad 9.0 or 10.0 project, writing nothing when the design has an error.
- Ids and KiCad uuids keyed by names and paths, so builds are byte-identical whatever the seed, and an inserted part moves no other uuid.
- No silent loss of work done in KiCad: an edited output is refused until c0019 preserves it.
- The built blink proved by `kicad-cli` 9.0.9 and 10.0.6: load, positions, clean DRC with a canary, an enforced net class, the vendored table and the path property.

**Non-Goals:**
- Everything listed under Non-goals in the proposal.
- A placer (staging is a fixed row), routing, fill, title blocks, schematics and `sym-lib-table` files in built projects.
- KiCad-side connectivity attribution (`unconnected_items` per net, IPC-D-356 assignment compare): c0020. This change checks connectivity hermetically (readback).
- Removing stale vendored files after a part is removed (the mutation protocol never deletes; c0019 may prune).

## Decisions

1. **Three layers, no layering change.** `dsl` (stdlib, `core` and `model`) describes. `cli/cmd_build.py` runs the script, calls `dsl.to_model` and `dsl.placements`, builds the resolver, checks existing outputs and returns the plan. `lens/build.py` (`model` and `backends` only) resolves, places and produces the file texts.
   - Geometric work stays in c0017's `embed`. `lens` reads the `footprint_extent` box by attribute and never imports `geometry`, which answers c0005's question "may `lens` import `geometry`" with no delta.
   - Rejected: orchestration inside `dsl` (it cannot import backends). Rejected: a new `build` package (not in the layering table, so it would need a `package-layering` delta).

2. **The DSL is a recorder, not a resolver.** It stores lib ids as strings and returns a model `Design` without footprints, plus `placements(design)`.
   - `lens.build.PlacementRequest` is a `Protocol` with `at`, `rotation`, `side` and `locked`, so `lens` takes the DSL's `Placement` objects without importing `dsl`.
   - Rejected: pad-less `FootprintInstance` stubs as placement requests (an invalid model state that a writer could emit). Rejected: a DSL type crossing into `lens` (a forbidden import). Rejected: a second intermediate document (another schema).

3. **Thin API from D10, explicit membership.** `Design`, `Module`, `Part`, `Net`, `connect()`, `Part.place()`, `Design.board()`, `d.rules.netclass()`, `Interface`, `Power`, `DiffPair`.
   - Objects join a design only through `add()`. A net joins when it is added, given to a class or interface, or connected to a pin of an added part.
   - `moved()` arrives with c0019. Custom rules, `quantity.py` and part pickers come later.
   - Rejected: an implicit "current design" context (global state, surprising in agents' scripts). Rejected: a `d.rules.rule()` constructor (beyond the plan's API; an empty `RuleSet` still exercises `lower_rules`).

4. **Name clash.** The DSL `Design` lives in `fenolite.dsl` and the model `Design` in `fenolite.model`. Inside `dsl` the model class is imported as `ModelDesign`. The root package re-exports neither.
   - Rejected: renaming the DSL class (`Board`, `Project`): the plan's API names it `Design`.

5. **Lengths always carry a unit.** A length is a `Length` (exact integer nm) from `mm()`, `mil()`, `inch()` or `nm()`, or a string with a unit (`"2.54mm"`) read by `core.units.parse_length` with no default unit.
   - A bare `int`, `float` or `bool`, or a string without a unit, raises `DslError` naming the argument.
   - The helpers take `int`, `str` or `float`. A float is converted exactly from `repr(x)` (S-0073); a value that is not a whole number of nm raises. So `mm(0.1) == nm(100_000)` and `mm(1/3)` raises.
   - `Length` is a frozen value with `==`, `hash`, `+`, `-`, unary `-`, and `*` and `//` by an `int`.
   - Angles are degrees: an `int`, a string (`"30.5"`, `"30.5deg"`, read by `parse_angle` with default unit `deg`) or a float through `repr`; whole microdegrees, normalised to [0°, 360°).
   - Rejected: bare ints as nanometres (`place(10, 5)` would silently mean 10 nm, and nothing downstream catches it). Rejected: `round()` of floats (silent precision loss). Rejected: refusing every float (forces strings for every decimal).

6. **Names, paths and checks at definition time.** `DslError` is raised at the offending call, so the script's traceback points at the line.
   - A design name matches `^[A-Za-z0-9][A-Za-z0-9_.-]*$` (it becomes the KiCad file stem). Module names and refs match `[A-Za-z0-9_.+-]+`.
   - `Module.path` is the name at the top and `<parent path>/<name>` below. A component path is `<module path>/<ref>`, or `<ref>` at the top.
   - Net names are global and literal; a module-local net is named by the script (`Net(f"{m.path}/FB")`).
   - Errors: a duplicate component or module path; a duplicate net, class or interface name; two distinct `Net` objects with one name; a net in two classes; a second `place()` or `board()`; `copper` other than 2 or 4; one designator connected to two nets; an unknown `side`; an invalid name.
   - Equal refs in different modules are left to `Design.validate()` (`model.duplicate-ref`, exit 5), the model's own rule.
   - Rejected: per-module net namespaces (hidden renaming that KiCad users would not recognise).

7. **Ids from names and paths, never from the seed** (MODIFIED `design-model` "Identifier derivation"). Every object that `to_model` or the build creates gets `derived_id(prefix, "dsl", "<kind>:<key>")` from the closed key table `dsl.KEYS` (design header `design`, board `board`, outline `outline`, rule set `rules`, manifest `manifest`, module `module:<path>`, component `component:<path>`, pin `pin:<path>:<number>`, net `net:<name>`, net class `netclass:<name>`, interface `interface:<kind>:<name>`, layer `layer:<KiCad name>`).
   - Footprints and pads take c0017's embed key, the component path (c0017's third case). The build re-keys `layers.created_layers(copper)` by layer name.
   - `--seed` changes nothing in a build, and `--timestamp` is accepted and unused, because a build writes no date (no command generates a title-block date; `TitleBlock.date` is set by the user, c0012).
   - The living `cli-contract` "Determinism flags" says that commands generating ids or dates take them from these flags. The delta MODIFIES it, with its full text and scenario kept: keyed ids (third and fourth cases) are not generated and do not depend on `--seed`, and a command that writes no date ignores `--timestamp`. No other open change modifies that requirement.
   - The delta's full text is the living requirement, which holds c0017's version since c0017 was archived on 2026-10-02; it keeps its four scenarios and adds the fourth case with three scenarios.
   - Rejected: seeded `uuid4` (the commitment "ids from the ctx seed"): one insertion shifts every later id and KiCad uuid, and builds without `--seed` differ. Byte identity across different `--seed` and `PYTHONHASHSEED` values is stronger than same-seed equality. Rejected: copying the KiCad reader's id strings into `dsl` (backend knowledge across the layering; c0019 and c0020 compare by keys).

8. **Frame.** DSL coordinates are board-relative: origin at the outline's top-left corner, Y down. The board is written at `BOARD_ORIGIN = Point(100 mm, 100 mm)`, a Fenolite choice recorded in `docs/dsl.md`.
   - `rot` is the model rotation, which is the stored footprint angle on both sides (c0017 Decision 14).
   - Rejected: (0, 0), which puts the board under the drawing-sheet border in the GUI. Rejected: centring on the paper, because positions would move when c0012 changes the paper, which would defeat c0019's preservation.

9. **DSL to model.** `to_model(design)` speaks model types only.
   - **Circuit.** One `Component` per added part with `ref`, `value`, `lib_symbol_ref`, `lib_footprint_ref` (empty when `footprint=None`), empty `pins` and `path`, and `properties == {"fenolite.path": <component path>}`. Nets whose `PinRef.pin` holds the designator as written; net classes with `Net.netclass_id`; interfaces; one model `Module` per DSL module.
   - **Board.** A keyed `Board` without layers or footprints, with the outline rectangle from `BOARD_ORIGIN` to `BOARD_ORIGIN + (width, height)`, or no outline without `board()`.
   - **Other layers.** An empty keyed `RuleSet`, a keyed `Manifest` and a keyed header named after the design.
   - Every object has `provenance = None`, so no absolute user path reaches `.fenolite/`. `to_model` does not validate, resolve or change the DSL design.
   - `Component.path` keeps c0009's meaning (the KiCad schematic path of a footprint) and stays empty: no footprint `path`, `sheetname` or `sheetfile` is written before schematics (v0.2a). The DSL path lives in `properties["fenolite.path"]` and in the `Module` tree.
   - `Power(hv, lv)` becomes `Interface(kind="power", members={"hv": …, "lv": …})` and `DiffPair(p, n)` `Interface(kind="diff_pair", members={"p": …, "n": …})`; the default name is `<first net>/<second net>`. Nothing is lowered to KiCad (`build.interface-not-lowered`, info, per `diff_pair`).
   - Rejected: the component path in `Component.path` (c0009 maps the footprint `(path …)` atom there, and c0017's projection check needs the built component to equal what `read_board` gives back).

10. **Scripts run in-process, isolated as far as Python allows, output captured.** `cli/_script.py::run_design_script(path) -> ScriptRun(design, output)`:
    - `runpy.run_path(path, run_name="__fenolite_build__")` (S-0070) with `sys.dont_write_bytecode = True`, `sys.argv = [path]` and the script folder first on `sys.path` (S-0071);
    - afterwards `sys.dont_write_bytecode`, `sys.argv` and `sys.path` are restored, and every `sys.modules` entry that the run added and whose `__file__` lies in the script folder is removed, so no `__pycache__` appears and a second in-process build runs edited sibling modules. Entries present before the run stay: the packaged `_minimal.py` lives in `src/fenolite/dsl/`, and removing `fenolite.dsl` modules would make the returned `design` an instance of a stale class;
    - stdout and stderr are captured with `redirect_stdout`/`redirect_stderr` (S-0074) into `result.script_output`, at most `SCRIPT_OUTPUT_LIMIT = 4000` characters, truncated with the marker `…[truncated]`, so stdout stays one JSON document;
    - the script binds a module-level `design` that is a `dsl.Design`;
    - any exception of the script (`SystemExit` and `DslError` included) and a missing or wrong `design` become `DesignScriptError(FormatError)` (`FEN-3004`, exit 3) with `file` = the script and `locator` = `line:<n>` of the deepest traceback frame inside the script, or no locator; `KeyboardInterrupt` propagates after the state is restored.
    - `to_model` and `placements` run in `cmd_build` after the runner has returned, so no script frame exists: `cmd_build` turns their `DslError` into `DesignScriptError` with `file` = the script and no locator.
    - `docs/dsl.md` and `fenolite build --help` say that `build` executes `design.py` as the user's own code and must never be run on an untrusted script. No sandbox (proposal Non-goals).
    - Rejected: `importlib` import (writes bytecode and caches the module across builds). Rejected: a subprocess (slower, no real isolation from the user's own code, loses typed errors). Rejected: scanning globals for any `Design` (ambiguous with two). Rejected: letting the script print to stdout (breaks the one-document contract).

11. **Validate fully, then write; a plan with errors carries no files.** `build_design` runs in this order:
    1. resolve every `lib_symbol_ref` and `lib_footprint_ref` (Decision 12);
    2. fill `Component.pins` and resolve net members (Decision 13);
    3. place and stage parts (Decisions 15, 16), set `Board.layers` from `created_layers(copper)` re-keyed by name, and assign pad nets;
    4. run the build checks and `Design.validate()`; any issue of severity `error` returns a `BuildOutput` with its issues and no files;
    5. call c0010's `triad.write_triad(design, name=name, target=target, existing_project=None, allow_lossy=allow_lossy, issues=…)`, which lowers the empty `RuleSet` through c0018 (`(version 1)`) and net classes through c0010; a writer refusal propagates (`LossyWriteError`, `RulesLossError`, `FEN-7001`);
    6. add vendored footprints, `fp-lib-table`, the six `.fenolite/` texts and `.fenolite/build.json` (Decisions 17, 19);
    7. combine evidence (Decision 24).
    - This keeps c0010 Decision 6 ("callers validate first; `build` stops on `model.unknown-netclass` with exit 5") and extends it to every error.
    - Rejected: writing partial outputs. Rejected: relying on exit 5, because the dispatcher writes before it counts issues (Context).

12. **Library resolution during build.** One `LibraryResolver(LibraryConfig(target_major=ctx.kicad_target, project_dir=<script folder>))` per build, with the process environment and the user's configuration folder.
    - Project tables next to `design.py` are the recommended source. Global and template tables follow c0008. Official library variables come only from an `env` or `install` source of the target major, so a 10.0 install is never used for target 9 (living `kicad-library-resolution` "Library sources").
    - Every `LibraryError` is collected; then `UnresolvedLibrariesError(LibraryError)` (`FEN-3001`, the first error's hint) is raised with one `kicad.lib.*` issue per failure.
    - `Part.footprint=None` falls back to the symbol's `Footprint` property, and `build.no-footprint` (error) is given when both are empty. `value=""` falls back to the symbol's `Value` property.
    - `result.libraries` maps each lib id to its row origin (`project`, `global`, `template`).
    - Rejected: a Fenolite `project.toml` listing libraries (the plan's wording): KiCad's own project tables already say it, and the roadmap asks for `${KIPRJMOD}` uris.

13. **Pins to pads by number.**
    - `Component.pins` is the flattened symbol: `SymbolDef.pins_of(unit, body_style=1)` for `unit` in 1 … `unit_count`, keeping the first occurrence of each pin number, with keyed pin ids.
    - A designator is a pin number first. Otherwise it names every pin with that name (`U1["GND"]` joins all `GND` pins). Neither: `build.unknown-pin` (error). A number that is also another pin's name: `build.pin-ambiguous` (warning), and the number wins.
    - After resolution, one pin on two nets: `build.pin-on-two-nets` (error).
    - Every pad whose number equals a pin number gets that pin's net, every pad of a repeated number included. A connected pin without a pad: `build.pin-without-pad` (error). An unconnected pin without a pad: `build.unused-pin-without-pad` (warning). A numbered pad without a pin: `build.pad-without-pin` (info). Pads with an empty number are ignored.
    - Hidden and power pins create no implicit nets (a Fenolite choice). After the build, `Net.members` hold pin numbers.
    - Rejected: designators by unique name only (one `connect` per `GND` pin). Rejected: implicit power-pin nets (names and outcome would depend on call order).

14. **Letter case: always refuse.** Net names, or class names, that differ only in letter case give `build.name-case-collision` (error), whatever c0018's `H-K-DRU-COND` measures (c0018 Open Questions leave the check to this change).
    - Rejected: a check conditional on the measurement (a design valid today could become invalid when a probe file changes).

15. **Path property through an additive function.** `embed.with_property(defn, *, name, value) -> FootprintDef` (new, in c0017's `backends/kicad/embed.py`) appends one hidden property after the definition's last `property` child, in the form of the `Mini_v9` `Datasheet` property and of 10.0.6-written boards (S-0058, recorded in `board.md`), and adds the entry to the copy's `properties`. `embed.PATH_PROPERTY = "fenolite.path"`.
    - A placed part is `place_footprint(with_property(defn, name=PATH_PROPERTY, value=<path>), component=…, at=…, rotation=…, side=…, locked=…, key=<path>, copper=<copper names>)`. `place_footprint` needs no change for the property: it gives the node a uuid from the key and locator, and flips its layer to `B.Fab` on the bottom.
    - **Copper names (MODIFIED `kicad-file-backend` "Footprint embedding").** Archived c0017 code gives `place_footprint` a keyword `copper: Sequence[str] = ("F.Cu", "B.Cu")`, the board's copper layer names for `*.Cu` pad layers, but the living requirement does not name it. Every build call, staged parts included, passes the copper names of `created_layers(copper)` in table order. The delta documents the keyword with the full living text, one bullet and two scenarios; no code changes. No other open change modifies that requirement.
    - Without the keyword on a `copper=4` board, the instance's `*.Cu` pads hold only `F.Cu` and `B.Cu`, and `write_board` refuses the board with `LossyWriteError` (`kicad.board.projection-read-only` per wildcard pad; observed on the archived code, 2026-10-02). With it, pad `1` of `Mini_LED_THT_3mm` reads back on `F.Cu`, `In1.Cu`, `In2.Cu` and `B.Cu` for targets 9 and 10, on both sides.
    - Rejected: relying on an undocumented keyword (a SHALL of `design-dsl` would rest on it).
    - Locator indices count earlier siblings with the same head (living `kicad-sexpr`), so a property appended last moves no other locator and no other placement uuid.
    - Every token is an 8.0-floor name, so the emit check is clean for targets 9 and 10.
    - `Component.properties` is set to exactly what `read_board` projects from the written footprint (the definition's properties plus `fenolite.path`), so c0017's "Projected fields on write" passes.
    - Gated on `H-K-BUILD-PATHPROP`, probed first (Decision 25). c0019 reads it as its secondary match key.
    - Rejected: a `properties=` argument on `place_footprint` (changes a committed interface while another agent implements it). Rejected: the DSL path in KiCad's `(path …)` (reserved for schematic uuid paths, v0.2a).

16. **Staging, not placing.** Unplaced parts go in one row, in component-path order. The row starts `STAGING_OFFSET = 5_000_000` nm right of the outline's bounding box and is top-aligned with it. Each `footprint_extent` box is left-aligned on the cursor (position = cursor − box minimum), and the cursor then advances by the box width plus `STAGING_GAP = 2_000_000` nm. Staged parts are on the top side at 0° and unlocked, and each gives one `layout.unplaced` warning.
    - The baseline probe (Decision 25) records what DRC says about a part outside the outline; nothing is claimed.
    - Rejected: placing inside the outline (c0022's grid placer).

17. **Self-contained output: vendored footprints and a per-target table.**
    - Every footprint resolved through a project-table row is copied byte for byte from `Location.item_path` to `DIR/lib/<nickname>.pretty/<entry>.kicad_mod`.
    - `DIR/fp-lib-table` holds one row per vendored nickname, sorted by nickname, with type `KiCad`, uri `${KIPRJMOD}/lib/<nickname>.pretty` and empty options and description, written by the new `libs.write_lib_table(table, *, target)`: `(version 7)` and every atom quoted for target 10 (S-0046, c0008's fixture); no version child and bare atoms for target 9, the 9.0.9 official-table form (S-0042, S-0043). Tab indentation and a final newline are Fenolite choices.
    - Footprints from global or template rows are neither vendored nor named in the table (`build.global-library`, info). A vendored file whose header version is newer than the target's newest footprint format gives `build.library-too-new` (warning); the board itself is still gated by c0017's emit check.
    - No `sym-lib-table` and no symbol files: there is no schematic until v0.2a, and pcbnew reads none.
    - `--out` resolving to the script folder is a usage error (exit 2, `FEN-2001`), so the design's own tables are never overwritten. The built folder can be moved or copied whole, which c0013's copy set needs ("every `${KIPRJMOD}` library folder they name", inside the project folder).
    - Rejected: copying the user's tables verbatim, or rewriting rows to `${KIPRJMOD}/../…`: they break when the folder moves, escape the folder c0013 copies (c0009's runner refuses `..` in copy names), and mix the 9.0.9 and 10.0 syntaxes. Rejected: absolute uris (machine-specific; residue `abs-user-path`). Rejected: vendoring global libraries (size, and the official libraries' licence is the user's business). Rejected: a `sym-lib-table`.

18. **One library set for both targets in the example.** `examples/blink_2layer` resolves from the 9-format `Mini_v9.pretty` and `Mini_v9.kicad_sym` for both targets: 10.0.6 reads 9-format libraries, and c0017 writes the target-10 board at `20260206`. `H-K-BUILD-LIBTABLE` checks library parity of those placements on 10.0.6.
    - `Mini_v9.kicad_sym` gains 9-format `Mini_R` and `Mini_LED`: copies of the 10.0 symbols with header `20241209`, `generator_version "9.0"` and every 10-only token removed (checked with `check_emittable(…, 9)`), passing c0008's `test_mini_oracle.py` on both majors, with pins equal to the 10.0 copies.
    - Rejected: a second, 10-format example (doubles the oracle runs, and `Mini.pretty` cannot serve target 9).

19. **Outputs and build record.**
    - Layout under `--out`: `<name>.kicad_pcb`, `<name>.kicad_pro`, `<name>.kicad_dru`, `fp-lib-table`, `lib/<nickname>.pretty/<entry>.kicad_mod`, `.fenolite/{meta,circuit,board,rules,manufacturing,findings}.json` and `.fenolite/build.json`. The stem is the design name.
    - The six layer texts come from the new `model.canonical.dump_texts(design) -> dict[str, str]`, which `dump_dir` now uses (same bytes), so the dispatcher writes them through the mutation protocol. `findings.json` is empty; no `FootprintDef`, no `native/`, never `.kicad_prl`. `meta.json` holds `fenolite_version`, as `dump_dir` writes it today, so bytes are identical for one Fenolite version.
    - `.fenolite/build.json` is `{"design": <name>, "files": {<path>: <sha256>, …}, "schema": "fenolite.build-record.v0", "target": <9|10>}`: paths relative to `--out` in POSIX form, every file outside `.fenolite/` that the build writes, `json.dumps(…, sort_keys=True, indent=2, ensure_ascii=False)` plus a newline, and no date (Fenolite choices).
    - `build.json` is regenerable like the layer files and marks a built project. It is not a layer file: `load_dir` reads only the six layer files.
    - Rejected: a date or the script's absolute path in the record (breaks byte identity and leaks a user path).

20. **Edited outputs: refuse by recorded hashes until c0019.** `lens.build.check_existing(out_dir, files, *, record, discard_layout)` runs in `cmd_build` before the plan is returned, so `--dry-run` refuses too. For each planned file outside `.fenolite/` that already exists:
    - bytes equal to the planned bytes: an identical rewrite, allowed;
    - SHA-256 equal to the one in `build.json`: untouched since the last build, allowed, so a DSL edit never needs `--discard-layout`;
    - otherwise (edited, for example in KiCad, or found without a record): `LayoutExistsError` (`cli_code = "FEN-7001"`, exit 7) with one `build.layout-exists` issue per file and the hint "re-run with --discard-layout to replace them (backups are kept), or build into another --out folder".
    - `lens.build.read_record(out_dir) -> Mapping[str, str] | None` returns the recorded hashes, or `None` when `build.json` is missing, unreadable, not JSON or of another schema; without a record only identical bytes pass, which errs on the safe side.
    - `--discard-layout` skips the check, and the mutation protocol keeps `.bak` files unless `--no-backup`. `--allow-lossy` never skips it.
    - c0019 replaces this path with preservation.
    - Rejected: comparing only with the planned bytes, the roadmap's literal rule: every DSL edit would need `--discard-layout`, which teaches agents to pass it by reflex and discard GUI work. Rejected: a silent overwrite with `.bak`. Rejected: a new `FEN-7xxx` code (dead once c0019 preserves layouts).

21. **Build issue codes are a closed table** (`lens.build.BUILD_ISSUE_CODES: Mapping[str, Severity]`). Writer codes (`kicad.board.*`, `kicad.project.*`, `rules.*`), resolver codes (`kicad.lib.*`) and `Design.validate()` codes (`model.*`) pass through unchanged.

    | code | severity | when |
    |---|---|---|
    | `build.unknown-pin` | error | a designator is neither a pin number nor a pin name |
    | `build.pin-on-two-nets` | error | a resolved pin is on two nets |
    | `build.pin-without-pad` | error | a connected pin has no pad of its number |
    | `build.no-footprint` | error | neither the part nor the symbol names a footprint |
    | `build.no-board` | error | the design has no `board()` |
    | `build.name-case-collision` | error | net or class names differ only in letter case |
    | `build.layout-exists` | error | an output changed since the last build (carried by `LayoutExistsError`) |
    | `build.pin-ambiguous` | warning | a pin number is also another pin's name |
    | `build.unused-pin-without-pad` | warning | an unconnected pin has no pad of its number |
    | `build.library-too-new` | warning | a vendored file is newer than the target's newest format |
    | `layout.unplaced` | warning | a part was staged beside the outline |
    | `build.pad-without-pin` | info | a numbered pad has no pin of its number |
    | `build.global-library` | info | a footprint came from a global or template row and is not vendored |
    | `build.interface-not-lowered` | info | a `diff_pair` interface is kept in the model only |

    - `layout.unplaced` keeps the roadmap's name, which c0022's placer reuses.

22. **CLI codes and refusals that carry their issues.**
    - `GeometryError.cli_code = "FEN-3005"`; registry row "geometry in the input cannot be represented", exit 3, hint "the message names the geometry code and the points"; listed in `docs/cli-contract.md`. `build` is the first command that can surface geometry from user input, through `embed`. This is the change's only new code.
    - `DslError` never reaches the dispatcher: the runner, or `cmd_build` for `to_model` and `placements`, wraps it in `DesignScriptError` (`FEN-3004`). `LibraryError` and `UnresolvedLibrariesError` keep `FEN-3001` (pinned by "Library issue codes"; the error's own hint replaces the registry hint). `FutureFormatError` keeps `FEN-3002`. `LossyWriteError`, `RulesLossError` and `LayoutExistsError` map to `FEN-7001`. `--out` equal to the script folder is `FEN-2001` (exit 2). Findings exit 5.
    - **Refusals carry their issues** (ADDED `cli-contract` requirement): when a command raises a `FenoliteError` whose `issues` attribute is a non-empty sequence of `Issue`, `_dispatch` puts them in the envelope's `issues`. Today an exception gives an empty list, so exit 3 or 7 would hide which lib ids, nets or files were refused.
    - Rejected: a new code for `LibraryError` (c0008's proposed `FEN-3004` collides with c0007's).

23. **Command surface.** `fenolite build DESIGN.py --out DIR [--discard-layout]` (`cli/cmd_build.py`, mutating, schema `fenolite.build.v0`) with the global `--dry-run`/`--confirm`, `--seed`, `--timestamp`, `--no-backup`, `--kicad-version 9|10` and `--allow-lossy`. `--out` is required.
    - `input` is the script path and its SHA-256, kind `fenolite-dsl`.
    - Planned writes are `<out>/<relative path>`, sorted by path, with kinds `kicad_pcb`, `kicad_pro`, `kicad_dru`, `fp-lib-table`, `kicad_mod` and `fenolite` (the files under `.fenolite/`).
    - `result` keys: `design`, `target`, `out`, `files`, `components`, `nets`, `placed`, `staged`, `vendored`, `libraries`, `script_output`, plus the dispatcher's `plan`.
    - `example_args` (with `--dry-run`) and `mutation_example_args` use the packaged `src/fenolite/dsl/_minimal.py` (Apache-2.0 header; a board with one net class and no parts), located through `fenolite.dsl.__file__`, so the consistency suite is hermetic from any working directory.
    - Rejected: `--out` defaulting to `build/` next to the script (an agent would write into the source tree without saying so).

24. **Evidence is honest.** The envelope combines, with `Evidence.combine` (lowest wins), `lens.build.BUILD_EVIDENCE` (`INFERRED`; `H-K-BUILD-TRIAD`, `H-K-BUILD-CLASS`, `H-K-BUILD-LIBTABLE`, `H-K-BUILD-PATHPROP`), `sym.EVIDENCE` and `mod.EVIDENCE` (`H-K-LIB-READ`), `pcb.WRITE_EVIDENCE` (`H-K-PCB-WRITE`), `pro.EVIDENCE` (`H-K-PRO-PATTERNS`), `lowering.EVIDENCE` and, when a part is on the bottom side, `embed.EVIDENCE`. The result is `INFERRED`.
    - `KICAD-VERIFIED` applies to the blink example only, through the oracle suite.
    - Rejected: reporting `KICAD-VERIFIED` because blink passed: arbitrary designs reach forms the oracle has not run.

25. **Probes first, with stop rules fixed now.** Before any DSL code (task group 2), boards made by `tests/kicad/build/_probe_boards.py` run on copies through c0009's runner with an empty `KICAD_CONFIG_HOME`, as `build-*` probes of c0017's `tests/kicad/_probes.py`. Each outcome is one value of c0017's closed set, and the probe files hold nothing else.
    - `_probe_boards.py::probe_board(target, *, offboard=False) -> Design` lays out the blink's three parts and four nets as `examples/blink_2layer` will, unrouted, through the model API with `layers.created_layers(2)` and `embed.place_footprint`, from `Mini_v9.pretty` for both targets. `offboard=True` moves `R1` 10 mm right of the outline. c0017's `tests/kicad/board/_triad.py` does not fit: it is routed (tracks and a `B.Cu` zone), places `U1` at 30° and reads `Mini.pretty` for target 10.
    1. `build-pathprop-t9` (majors 9 and 10), `build-pathprop-t10` (major 10) (`H-K-BUILD-PATHPROP`): a hidden `fenolite.path` property on every footprint, inserted by text in the form of Decision 15. Outcome: `reject` when the board does not load; on major 9, `load` when it loads; on major 10, `present` when, after `pcb upgrade --force`, `read_board` gives every footprint its value and each node keeps `(hide yes)`, and `absent` otherwise. **Stop rule:** a `reject` or `absent` outcome of either probe refutes the row → the build writes no property, `with_property` stays as a tested helper, and c0019 matches by uuid only (cut 4 of "Budget" applies).
    2. `build-libtable-t9`, `build-libtable-t10` (`H-K-BUILD-LIBTABLE`): the board with copies of the used files under `lib/Mini.pretty/` and a table authored in each target's syntax (row `Mini` → `${KIPRJMOD}/lib/Mini.pretty`). Outcome: `equal` when the run with the table gives no `lib_footprint_issues` and no `lib_footprint_mismatch` and the same copy without the table gives `lib_footprint_issues`; `different` when the table is read (no `lib_footprint_issues`) but a `lib_footprint_mismatch` appears; `absent` when `lib_footprint_issues` appear with the table; `inconclusive` when the copy without the table gives none either; `reject` when the board does not load. **Stop rule** (10.0.6 outcomes only; 9.0.9 outcomes are recorded while `H-K-LIB-DRC` is open there): `different` makes parity recorded data, not acceptance; `absent` or `inconclusive` stops the change until the table form, or the reading of `H-K-LIB-DRC`, is corrected.
    3. `build-baseline-t9`, `build-baseline-t10` (part of `H-K-BUILD-TRIAD`): the clean board; outcome `absent` when its report holds no violation of severity `error`, `present` otherwise. `build-offboard-t9`, `build-offboard-t10`: the `offboard` variant; outcome `present` when its report holds a violation type that the clean board lacks, `absent` otherwise (data for staging, Decision 16; nothing is claimed). Every violation type, its severity and the `unconnected_items` count of both boards per major go to fact rows of `docs/formats/kicad/drc.md` (c0017's page) with `H-K-BUILD-TRIAD`, never to the probe files. **Stop rule:** for a `present` baseline, an error-severity type that a clean placement cannot avoid is named below with its probe outcome and excluded by name from the acceptance, never by severity or count.

    **Baseline exceptions:** none recorded yet. Task 2.2 replaces this line with each excluded type and its probe outcome, or "none".
    - Rejected: writing the DSL first and probing at the end (a refuted property or table form would change public behaviour late).

26. **Oracle method** (c0017 Decision 17, c0018 Decision 1). Every verdict comes from the DRC JSON report, never the exit code. A pure judge, `tests/_build_judge.py`, turns reports into outcomes of c0017's closed set (`canary_outcome`, `class_outcome`, `libtable_outcome`, `baseline_outcome`) and `assert_loaded(outcome, case)` fails an `inconclusive` case with "rules file not loaded"; the hermetic `tests/unit/test_build_judge.py` proves every `inconclusive` and `different` path on authored report texts, as c0010 does with `judge` and `assert_loaded`.
    - **Load and positions.** The target-9 blink loads on 9.0.9 and 10.0.6, the target-10 blink on 10.0.6; `pcb export pos` gives each part's DSL position plus `BOARD_ORIGIN`, its rotation and side, compared through c0009's `tests/kicad/board/_frame.py`.
    - **Clean DRC with a canary.** No violation of severity `error` other than the named baseline exceptions; `unconnected_items` are a separate list and allowed, because the blink is unrouted. c0018's canary rule is unconditional and flags every close pair, so it runs on its own copy, whose `.kicad_dru` gets the canary inserted right after `(version 1)` by `tests/kicad/rules/_bench.py::with_canary` (c0018; placed last instead on a major where `H-K-DRU-ORDER` says the earlier rule governs). `canary_outcome(plain, canary)` gives `present` when the copy holds a `clearance` violation absent from the plain run, and `inconclusive` otherwise, which fails.
    - **Departure from c0018.** Its requirement "Rules proofs carry a canary" puts the canary pair `CANARY_A`/`CANARY_B` on its own bench, and `require_canary(report, bench)` looks for that pair's violation. The blink holds no such pair, so this change judges the canary with its own criterion above. The rest of c0018's rule holds: the canary must fire in every case that loads the rules file, and the test never passes or skips without it.
    - **Violated class, three ways.** A variant with `PWR` at 2 mm clearance gives a `clearance` violation whose items are the uuids of the adjacent `U1` pads 9 (`VIN`) and 10 (`GND`); the same set without `blink.kicad_pro` gives none for those pads, and the as-built blink gives none. The variant's violation, present with the project and absent without it on the same copy, is the positive control that the project file was read, so this case carries no canary. `class_outcome` gives `present` when all three hold, `absent` when the variant gives no violation for those pads, and `different` for any other mix; an item uuid that is no pad uuid makes it `different`, recorded as data for c0020.
    - **Vendored table.** On 10.0.6, for targets 9 and 10, no `lib_footprint_issues` and no `lib_footprint_mismatch` with the table, and `lib_footprint_issues` on the same copy without it (`libtable_outcome` gives `equal`; the other outcomes as in Decision 25). On 9.0.9 the outcomes are recorded, never asserted, while `H-K-LIB-DRC` is open there.
    - **Path property.** After `pcb upgrade --force` on 10.0.6, `read_board` gives `properties["fenolite.path"]` equal to the component path for all three footprints, and each property node still holds `(hide yes)`.
    - Outcomes are pinned as `build-canary-t<M>` and `build-class-t<M>` probes besides the group-2 ids, in `docs/evidence/kicad/probes/9.0.9.json` and `10.0.6.json`.
    - Rejected: judging by `--exit-code-violations`. Rejected: the canary inside the class run (it would fire on the class pads too). Rejected: a ratsnest-count hypothesis here (overlaps c0020's DRC item attribution and assignment compare).

27. **Determinism and readback are hermetic.**
    - `tests/unit/lens/test_build_determinism.py` builds the blink for targets 9 and 10 twice in-process and twice by subprocess with `PYTHONHASHSEED=1`/`--seed 1` and `PYTHONHASHSEED=2`/`--seed 2` (S-0072); every file under `--out`, `.fenolite/` included and `.bak` excluded, is byte-identical; the script folder keeps its file list and SHA-256 values, with no `__pycache__`; deleting `.fenolite/` and rebuilding restores identical bytes.
    - Every output collection is sorted by name or path, table uris are `${KIPRJMOD}`-relative and no date is written.
    - Objects made by `to_model` and each placed `FootprintInstance` have `provenance = None`. The pads and graphics of a placed copy keep the provenance that `read_board` gives the in-memory copy inside `place_footprint` (backend `kicad`, an empty file name, the SHA-256 of the in-memory text and a locator); c0017's writer reads that locator, so it is kept. It is deterministic and holds no path, and a hermetic check asserts that no `.fenolite/` text holds the absolute path of the script or output folder.
    - `tests/unit/lens/test_build_readback.py` reads the written board with c0009's `read_board` and compares by keys (reference, pad number, net name), because ids differ by design (`kicad` and `dsl` keys): equal pad nets, equal `properties`, empty `Component.path`, equal positions, rotations, sides and locks. RT1 of the built board is c0013's roundtrip stage; the model-to-board comparison by keys belongs to c0019 (components, positions, properties) and c0020 (pad nets).

28. **Examples.**
    - `examples/blink_2layer/` (CC0): `design.py` with `U1` `Mini:Mini_QFP32_IC` locked on the top; `R1` `Mini:Mini_R` with `Mini:Mini_R_0603`; `D1` `Mini:Mini_LED` with `Mini:Mini_LED_THT_3mm` on the bottom; nets `VIN` (`U1` pin 9), `GND` (`U1` pin 10 and `D1` pin 1), `LED_DRV` (a `U1` port pin to `R1` pin 1) and `LED_A` (`R1` pin 2 to `D1` pin 2); `Power(VIN, GND)`; class `PWR` (0.2 mm clearance, 0.5 mm track) on `VIN` and `GND`; a 50 mm × 30 mm two-layer board; every part placed with courtyards at least 2 mm apart. Its `fp-lib-table` and `sym-lib-table` hold rows to `${KIPRJMOD}/../../tests/data/libs/Mini_v9.*`, used for both targets; only Fenolite's resolver reads them, and built output is vendored.
    - `examples/blink_official/design.py`: the same circuit on official libraries (an `MCU_ST_STM32G4` symbol, `Device:R`, `Device:LED`). DSL source only, built only by `tests/libs/test_build_official.py` (`needs_libs`) into `tmp_path`; nothing generated from it is committed (living `ip-hygiene` and the official-library residue test).
    - Every new file is declared in `tests/data/MANIFEST.toml` (`origin = "authored"`), with rows in `PROVENANCE.md` and `LEGAL-ANNEX.md`.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/dsl/__init__.py` (new) | re-exports `Design`, `Module`, `Part`, `Net`, `connect`, `Interface`, `Power`, `DiffPair`, `Length`, `mm`, `mil`, `inch`, `nm`, `Placement`, `BOARD_ORIGIN`, `to_model`, `placements`, `KEYS`, `DSL_BACKEND`, `DslError` |
| `src/fenolite/dsl/errors.py` (new) | `class DslError(ValueError)` |
| `src/fenolite/dsl/units.py` (new) | `@dataclass(frozen=True, slots=True) class Length(nm: int)` with `+`, `-`, unary `-`, `* int`, `// int`; `mm(value: int \| str \| float) -> Length`; `mil(value: int \| str \| float) -> Length`; `inch(value: int \| str \| float) -> Length`; `nm(value: int) -> Length`; `as_nm(value: object, *, name: str) -> Nm`; `as_udeg(value: object, *, name: str) -> Udeg` (normalised to [0, 360°)) |
| `src/fenolite/dsl/design.py` (new) | `class Design(name: str)`: `add(*objs: Part \| Module \| Net \| Interface) -> None`, `board(width: Length \| str, height: Length \| str, copper: int = 2) -> None`, `rules: Rules`, `name: str`, `copper: int`; `class Rules`: `netclass(name: str, *, clearance: Length \| str \| None = None, track_width: … = None, via_diameter: … = None, via_drill: … = None, nets: Iterable[Net] = ()) -> None` |
| `src/fenolite/dsl/module.py` (new) | `class Module(name: str)`: `add(*objs: Part \| Module \| Net \| Interface) -> None`, `path: str` |
| `src/fenolite/dsl/part.py` (new) | `class Part(ref: str, lib_id: str, footprint: str \| None = None, value: str = "")`: `__getitem__(designator: str \| int) -> PinHandle`, `place(x: Length \| str, y: Length \| str, rot: int \| str \| float = 0, side: str = "top", locked: bool = False) -> None`, `path: str`; `@dataclass(frozen=True) class PinHandle(part: Part, designator: str)`; `class Net(name: str)`; `connect(net: Net, *pins: PinHandle) -> Net`; `@dataclass(frozen=True, slots=True) class Placement(at: Point, rotation: Udeg, side: Side, locked: bool)` |
| `src/fenolite/dsl/interfaces.py` (new) | `class Interface(name: str, kind: str, members: Mapping[str, Net])`; `class Power(Interface)` with `Power(hv: Net, lv: Net, *, name: str \| None = None)`; `class DiffPair(Interface)` with `DiffPair(p: Net, n: Net, *, name: str \| None = None)` |
| `src/fenolite/dsl/convert.py` (new) | `to_model(design: Design) -> fenolite.model.Design`; `placements(design: Design) -> Mapping[str, Placement]`; `KEYS: Mapping[str, tuple[str, str]]` (object → id prefix and key form, Decision 7); `BOARD_ORIGIN = Point(100_000_000, 100_000_000)`; `DSL_BACKEND = "dsl"` |
| `src/fenolite/dsl/_minimal.py` (new) | packaged hermetic example (Apache-2.0 header): a board with one net class and no parts |
| `src/fenolite/lens/__init__.py` (new) | package docstring only |
| `src/fenolite/lens/build.py` (new) | `build_design(design: Design, placements: Mapping[str, PlacementRequest], *, name: str, copper: Literal[2, 4], resolver: LibraryResolver, target: int = DEFAULT_TARGET, allow_lossy: bool = False) -> BuildOutput`; `@dataclass(frozen=True) class BuildOutput(design: Design, files: Mapping[str, bytes], issues: tuple[Issue, ...], evidence: Evidence, summary: Mapping[str, object])`; `class PlacementRequest(Protocol)` (`at: Point`, `rotation: Udeg`, `side: Side`, `locked: bool`); `check_existing(out_dir: Path, files: Mapping[str, bytes], *, record: Mapping[str, str] \| None, discard_layout: bool) -> None`; `read_record(out_dir: Path) -> Mapping[str, str] \| None`; `class LayoutExistsError(FenoliteError)` (`cli_code = "FEN-7001"`, `issues`, `hint`); `class UnresolvedLibrariesError(LibraryError)` (`issues`); `BUILD_ISSUE_CODES: Mapping[str, Severity]`; `BUILD_EVIDENCE: Evidence`; `RECORD_FILE = ".fenolite/build.json"`; `RECORD_SCHEMA = "fenolite.build-record.v0"`; `STAGING_OFFSET = 5_000_000`; `STAGING_GAP = 2_000_000` |
| `src/fenolite/backends/kicad/embed.py` (c0017; extended) | `with_property(defn: FootprintDef, *, name: str, value: str) -> FootprintDef`; `PATH_PROPERTY = "fenolite.path"`; `place_footprint(…, copper: Sequence[str] = ("F.Cu", "B.Cu"))` documented, code unchanged |
| `src/fenolite/backends/kicad/libs.py` (c0008; extended) | `write_lib_table(table: LibTable, *, target: int = DEFAULT_TARGET) -> str` |
| `src/fenolite/model/canonical.py` (extended) | `dump_texts(design: Design) -> dict[str, str]`; `dump_dir` writes its texts (bytes unchanged) |
| `src/fenolite/geometry/errors.py` (extended) | `GeometryError.cli_code = "FEN-3005"` |
| `src/fenolite/cli/errors.py` (extended) | `ErrorSpec("FEN-3005", ExitCode.INPUT, "geometry in the input cannot be represented", "the message names the geometry code and the points")` |
| `src/fenolite/cli/main.py` (extended) | `_dispatch` puts the `issues` of a raised `FenoliteError` into the envelope |
| `src/fenolite/cli/_script.py` (new) | `run_design_script(path: Path) -> ScriptRun`; `@dataclass(frozen=True) class ScriptRun(design: fenolite.dsl.Design, output: str)`; `class DesignScriptError(FormatError)`; `SCRIPT_OUTPUT_LIMIT = 4000` |
| `src/fenolite/cli/cmd_build.py` (new) | `COMMAND = Command(name="build", mutates=True, …)`: positional `design`, `--out DIR` (required), `--discard-layout`; schema `fenolite.build.v0` |
| `src/fenolite/backends/kicad/PROVENANCE.md` | rows for the path-property form, written tables and vendoring |
| `docs/dsl.md` (new) | API, units, key table, frame and `BOARD_ORIGIN`, script rules and the security note, determinism, output layout, edited-output rule, stale vendored files |
| `docs/design-model.md`, `docs/cli-contract.md` | keyed DSL ids; `build`, `FEN-3005`, refusals with issues |
| `docs/formats/kicad/board.md`, `docs/formats/kicad/libraries.md`, `docs/formats/kicad/drc.md` (c0017's page) | fact rows: hidden user property form; written table syntax per target, vendoring; violation types, severities and `unconnected_items` counts of the baseline and offboard probes |
| `docs/evidence/kicad/probes/9.0.9.json`, `10.0.6.json` | `build-*` outcomes |
| `tests/data/libs/Mini_v9.kicad_sym` | authored 9-format `Mini_R` and `Mini_LED` |
| `examples/blink_2layer/{design.py,fp-lib-table,sym-lib-table}`, `examples/blink_official/design.py`, `examples/README.md` | CC0 examples |
| `tests/unit/dsl/test_units.py`, `test_structure.py`, `test_connect.py`, `test_to_model.py`, `test_ids.py`, `test_interfaces.py` | hermetic DSL tests (new) |
| `tests/unit/lens/test_build_resolve.py`, `test_build_pins.py`, `test_build_place.py`, `test_build_files.py`, `test_build_existing.py`, `test_build_issues.py`, `test_build_determinism.py`, `test_build_readback.py` | hermetic build tests (new) |
| `tests/unit/cli/test_script.py`, `test_build_command.py`, `test_build_errors.py`; `tests/unit/cli/test_library_errors.py` (extended) | runner, command flow, error mapping, `FEN-3005`, refusals with issues; a sibling fixture of `run_raising` that also returns stdout, so the envelope's `issues` can be read (`run_raising` itself is unchanged) |
| `tests/unit/backends/kicad/test_embed_property.py`, `test_embed_copper.py`, `test_lib_table_write.py`, `test_mini_v9_pins.py`; `tests/unit/model/test_dump_texts.py` | hermetic (new) |
| `tests/kicad/build/test_build_probes.py`, `test_build_oracle.py`; `tests/kicad/_probes.py` (c0017; extended) | `needs_kicad`, major-aware; `build-*` probe entries |
| `tests/kicad/build/_probe_boards.py` (new) | `probe_board(target: int, *, offboard: bool = False) -> Design`: the unrouted blink layout through the model API, from `Mini_v9.pretty` (Decision 25) |
| `tests/_build_judge.py` (new) | `canary_outcome(plain: DrcReport, canary: DrcReport \| None) -> str`; `class_outcome(variant: DrcReport, noproject: DrcReport, asbuilt: DrcReport, *, pads: tuple[str, str]) -> str`; `libtable_outcome(with_table: DrcReport \| None, without_table: DrcReport \| None) -> str`; `baseline_outcome(report: DrcReport \| None) -> str`; `assert_loaded(outcome: str, case: str) -> None` (`pytest.fail` with "rules file not loaded") |
| `tests/unit/test_build_judge.py` (new) | hermetic: every outcome of the judge on authored report texts |
| `tests/libs/test_build_official.py` | `needs_libs` |

Layering: `dsl` imports `core` and `model`; `lens` imports `core`, `model` and `backends` (`backends.base`, `backends.kicad.{libs,embed,layers,pcb,triad,pro,lowering,sym,mod,versions}`); `backends.kicad.embed` and `libs` keep their c0017 and c0008 edges; `cli` imports any package. All edges are in `package-layering`, so `ALLOWED` in `tests/unit/test_import_graph.py` is unchanged.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0070 | https://docs.python.org/3/library/runpy.html | PSF License Version 2, as stated in the page footer (to verify on the page) | `runpy.run_path`: running a file as a module with a given `run_name` and returning its globals |
| S-0071 | https://docs.python.org/3/library/sys.html | PSF License Version 2, as stated in the page footer (to verify on the page) | `sys.dont_write_bytecode`, `sys.path`, `sys.modules`, `sys.argv` |
| S-0072 | https://docs.python.org/3/using/cmdline.html#envvar-PYTHONHASHSEED | PSF License Version 2, as stated in the page footer (to verify on the page) | hash randomisation and its effect on set order (determinism test) |
| S-0073 | https://docs.python.org/3/tutorial/floatingpoint.html | PSF License Version 2, as stated in the page footer (to verify on the page) | `repr` of a float is the shortest string that round-trips (exact float conversion in `units.py`) |
| S-0074 | https://docs.python.org/3/library/contextlib.html#contextlib.redirect_stdout | PSF License Version 2, as stated in the page footer (to verify on the page) | `redirect_stdout` and `redirect_stderr` (script output capture) |

Extended "used for" cells, with no new id:
- **S-0010** and **S-0038** (9.0 and 10.0 board editor pages): footprint user properties and their visibility.
- **S-0042** and **S-0043** (official library trees at 9.0.9): the 9.0.9 table form that `write_lib_table` writes for target 9.
- **S-0045** (KiCad manual): `KIPRJMOD` in vendored table rows.
- **S-0046** (schematic editor manual): project tables beside the project, and the 10.0 table form.
- **S-0058** (demo files): the hidden-property form of 10.0.6-written boards.

Rows of other changes cited here: S-0022 and S-0037 (`pcb drc`, `pcb export pos`, `pcb upgrade`), S-0055 and S-0056 (DRC report keys). Only facts are taken from the Python pages; no text or code is copied. No KiCad source file is read. If a URL above is already registered when this change is implemented, the existing id is cited and the row is not duplicated.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-BUILD-TRIAD | A project that `fenolite build` writes for target M from the CC0 mini library loads on `kicad-cli` M (a target-9 project also on 10.0.6); `pcb export pos` gives each part's DSL position plus `BOARD_ORIGIN`, its rotation and side; its DRC JSON holds no `violations` entry of severity `error` (`unconnected_items` are a separate list; a type named by the baseline probe excepted by name); and with c0018's canary inserted by `with_canary` into a copy of its `.kicad_dru`, a `clearance` violation absent from the plain run appears (S-0010, S-0022, S-0038, S-0055, S-0056) | `tests/kicad/build/test_build_oracle.py::test_blink_builds_clean` | on 9.0.9 (target 9) and 10.0.6 (targets 9 and 10) all four hold; a missing canary is `inconclusive` and fails |
| H-K-BUILD-CLASS | A net class declared with `d.rules.netclass` is enforced through the built `.kicad_pro` (S-0010, S-0046; builds on `H-K-PRO-NETCLASS`) | `tests/kicad/build/test_build_oracle.py::test_violated_class` | on 9.0.9 (target 9) and 10.0.6 (targets 9 and 10): the variant with `PWR` at 2 mm clearance gives a `clearance` violation whose items are the uuids of `U1` pads 9 and 10; the same set without `blink.kicad_pro` gives none for those pads; the as-built blink gives none; an item uuid that is no pad uuid makes the probe `different` |
| H-K-BUILD-LIBTABLE | An `fp-lib-table` written by `libs.write_lib_table` for target M, whose rows name footprints vendored under `${KIPRJMOD}/lib/`, is read by `kicad-cli`, and 9-format definitions placed in a target-10 board match their library (S-0042, S-0043, S-0045, S-0046; depends on `H-K-LIB-DRC`) | `tests/kicad/build/test_build_oracle.py::test_vendored_table` (probe in group 2) | on 10.0.6, for targets 9 and 10: no `lib_footprint_issues` and no `lib_footprint_mismatch` with the table, and `lib_footprint_issues` on the same copy without it (else `inconclusive`); on 9.0.9 the outcomes are recorded, never asserted |
| H-K-BUILD-PATHPROP | A hidden user property `fenolite.path` written by `embed.with_property` on a board footprint loads on both majors and keeps its value through a 10.0.6 re-save (S-0038, S-0058; motivated by `H-K-UUID-KEEP-2`) | `tests/kicad/build/test_build_oracle.py::test_path_property` (probe in group 2) | the built blink loads on 9.0.9 and 10.0.6; after `pcb upgrade --force` on 10.0.6, `read_board` gives `properties["fenolite.path"]` equal to the component path for all 3 footprints, and each property node still holds `(hide yes)` |

Cited, not settled here: `H-K-LIB-READ` (symbol half; the envelope cites it), `H-K-PCB-WRITE`, `H-K-PRO-PATTERNS`, `H-K-PRO-NETCLASS` (a second, built design supports it), `H-K-LIB-DRC` (more 9.0.9 records), `H-K-UUID-KEEP-2`, and the three `H-G-*` flip rows through `embed.EVIDENCE`. `H-K-DRU-COND` (letter case) is only recorded, because the build refuses case collisions whatever it measures. No build behaviour depends on an open row except through the stop rules of Decision 25.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| DSL API, units, names, definition-time errors | mechanical (unit tests) | `tests/unit/dsl` |
| Keyed ids, insertion and order independence, seed independence | mechanical (unit tests) | `tests/unit/dsl/test_ids.py` |
| `to_model`, `placements`, interfaces | mechanical (unit tests) | `tests/unit/dsl/test_to_model.py`, `test_interfaces.py` |
| Script runner, output capture, error locators | mechanical (unit tests) | `tests/unit/cli/test_script.py`, `test_build_errors.py` |
| Resolution, pins and pads, staging, issue codes, edited-output check, record | mechanical (unit tests); library reading `INFERRED` (`H-K-LIB-READ`) | `tests/unit/lens` |
| Byte-identical builds across `--seed`, `PYTHONHASHSEED` and processes | mechanical | `tests/unit/lens/test_build_determinism.py` |
| Readback connectivity, properties and placements | mechanical (c0009 reader) | `tests/unit/lens/test_build_readback.py` |
| `FEN-3005`, refusals carry their issues | mechanical (unit tests) | `tests/unit/cli/test_library_errors.py`, `test_build_errors.py` |
| `dump_texts` equal to `dump_dir` | mechanical (unit tests) | `tests/unit/model/test_dump_texts.py` |
| 9-format `Mini_R` and `Mini_LED` | KICAD-VERIFIED (9.0.x, 10.0.x) | `tests/kicad/libs/test_mini_oracle.py` in both jobs |
| Built blink loads, sits where the DSL says, clean DRC with a firing canary (`H-K-BUILD-TRIAD`) | KICAD-VERIFIED on 9.0.9 (`kicad-9`, target 9) and 10.0.6 (local and `kicad-10`, targets 9 and 10) | `test_build_oracle.py::test_blink_builds_clean` |
| Violated class enforced, with no-project control (`H-K-BUILD-CLASS`) | KICAD-VERIFIED (9.0.x, 10.0.x) | `test_build_oracle.py::test_violated_class` |
| Vendored table read and library parity (`H-K-BUILD-LIBTABLE`) | KICAD-VERIFIED (10.0.x); 9.0.9 recorded; `INFERRED` on 9.0 while `H-K-LIB-DRC` is open there | `test_build_oracle.py::test_vendored_table` |
| `fenolite.path` loads and survives a re-save (`H-K-BUILD-PATHPROP`) | KICAD-VERIFIED for load (9.0.x, 10.0.x) and re-save (10.0.x) | `test_build_oracle.py::test_path_property` |
| `write_lib_table` text per target | mechanical; KiCad reading it through `H-K-BUILD-LIBTABLE` | `test_lib_table_write.py` |
| `place_footprint` `copper` keyword, four-layer wildcard pads | mechanical (c0009 reader, c0017 writer) | `test_embed_copper.py`, `test_build_place.py` |
| The `build` envelope for an arbitrary design | INFERRED (Decision 24) | `BUILD_EVIDENCE` |

`lens.build.BUILD_EVIDENCE` stays `INFERRED` after this change, even when the four `H-K-BUILD-*` rows are `KICAD-VERIFIED`: they cover the blink, not every design. The level is lowered further by any combined constant below it.

## Budget (about 1.75 weeks; the plan line was day 18, shared with c0019)

| work | days |
|---|---|
| 1. registers, provenance, format rows, `docs/dsl.md` skeleton | 0.5 |
| 2. probes first | 0.5 |
| 3. `Mini_v9` symbols and their oracle | 0.5 |
| 4. DSL API, units, names, errors | 1.0 |
| 5. examples | 0.25 |
| 6. `to_model`, `placements`, keyed ids, `dump_texts` | 0.5 |
| 7. `embed.with_property`, `libs.write_lib_table` | 0.5 |
| 8. `lens/build.py`: resolution, pins and pads, placement, staging, checks, vendoring, triad, `.fenolite/`, record, edited-output check, evidence | 1.75 |
| 9. script runner, `cmd_build`, `FEN-3005`, refusals with issues, minimal example, consistency | 1.0 |
| 10. determinism and readback suites, official example | 0.5 |
| 11. oracle suite on both majors, probe files | 1.0 |
| 12. closing | 0.5 |
| **total** | **8.5** |

The roadmap gives 6.5 days, and the plan line "dsl/preserve 1.5 weeks" is shared with c0019. This change is re-baselined at 8.5 working days, stated here and in the proposal. Cut order, to 7.25: (1) the `blink_official` `needs_libs` build test, DSL source kept (−0.25); (2) the recorded-hash rule falls back to the roadmap's strict byte comparison, no `build.json` (−0.25); (3) the `pcb export pos` check, hermetic positions kept (−0.25); (4) `fenolite.path` and `H-K-BUILD-PATHPROP` move to c0019 (−0.5). Not optional: the DSL, keyed ids, validate-before-write, the runner with output capture, `lens/build.py`, vendoring and tables, the edited-output refusal, `FEN-3005`, determinism, and the load, canary and class oracle on both majors.

## Risks / Trade-offs

- [`build` executes the user's `design.py` in-process] → It is the user's own code, documented in `docs/dsl.md` and `--help`, never to be run on untrusted input. Output is captured. `check` (c0013) never runs scripts. Isolation is out of scope.
- [Hidden nondeterminism: set iteration, dict order, float formatting, absolute paths, module caches] → Every output is sorted by name or path, no provenance holds a file path (`None` for `to_model` objects and footprint instances, an empty file name and an in-memory hash for placed pads and graphics), table uris are `${KIPRJMOD}`-relative and no date is written. The determinism suite varies `PYTHONHASHSEED` and `--seed`, runs in-process and in subprocesses, and checks that the script folder is unchanged.
- [The blink DRC shows an unavoidable error-severity type, such as a courtyard overlap or solder-mask bridging in the mini QFP] → The baseline probe records types before the example is laid out; placements keep 2 mm courtyard margins; an unavoidable type is named in Decision 25 with its probe outcome, never allowed silently.
- [c0017's projection check rejects built footprints whose `Component.properties` differ from the fragments] → The build sets `properties` to `read_board`'s projection, and the readback test compares them.
- [9-format footprints differ from their library in a target-10 board, or a table form is not read (`H-K-BUILD-LIBTABLE`)] → Probed first with stop rules; parity becomes recorded data; placement parity is already proved by c0017.
- [`kicad-cli` drops or rewrites the property on re-save (`H-K-BUILD-PATHPROP`)] → Probed first; the property is then not written, and c0019 matches by uuid (`H-K-UUID-KEEP-2`).
- [Builds depend on the user's global library table] → Tests use an empty `KICAD_CONFIG_HOME`; `docs/dsl.md` recommends project tables; `result.libraries` lists each lib id's origin, and global footprints give `build.global-library`.
- [Stale vendored files stay in `DIR/lib/` after a part is removed] → Harmless to KiCad (the table names folders, the board names footprints); `docs/dsl.md` says so; c0019 may prune.
- [The runner removes a module the user expected to stay cached] → Only modules added by the run and loaded from the script folder are removed; a design that keeps state across builds is unsupported and documented.
- [c0010 or c0018 names drift while they are implemented] → The committed proposals are the contract; task 1.1 re-checks every consumed name and records any divergence in the pull request. c0017 is archived, so its names are living specs and code.
- [Overrun; c0008 took about three times its line] → The cut order of "Budget".

## Migration Plan

- Additive: new packages `dsl` and `lens`, new modules `cli/_script.py` and `cli/cmd_build.py`, new functions in `embed.py`, `libs.py` and `canonical.py`, one registered code (`FEN-3005`), one dispatcher rule, new CC0 data and examples. The model and the schemas are unchanged. To roll back, remove them, the `FEN-3005` row and the dispatcher rule; built projects stay valid KiCad projects.

## Open Questions

- **Edited-output rule.** The roadmap refuses an existing board "with different content". This design refuses only files changed since Fenolite last wrote them (recorded hashes in `.fenolite/build.json`), so a DSL edit never needs `--discard-layout`. The default is the recorded-hash rule; the strict rule is cut 2.
- **Vendoring.** The default copies project-table footprints into `DIR/lib/` and writes a per-target `fp-lib-table`; global and template libraries are neither vendored nor named, and built projects carry no `sym-lib-table` before schematics (v0.2a).
- **Ownership of `fenolite.path`.** The roadmap entry does not name it; plan item 0011 does, and c0019 matches by it. The default: this change writes it behind its probe, and c0019 only reads it; cut 4 moves it to c0019.
- **`BOARD_ORIGIN`.** `(100 mm, 100 mm)` is a Fenolite choice. Should c0012 centre boards on the chosen paper instead? The default keeps it fixed, because moving every footprint when the paper changes would defeat c0019.
- **Custom rules in the DSL.** c0018 expected this change to feed `lower_rules` from the DSL; the plan's API has only `d.rules.netclass`. The default: an empty `RuleSet` in v0.1, and a rule constructor over c0018's selectors in v0.2a (or c0025 if the agent loop needs it).
- **Drawing sheet from the DSL (settled by c0011 and c0012).** c0012's proposal lists "DSL sheet keywords and `build` writing the sheet (not v0.1; follow-up, see design)" among its non-goals, and its Open Questions take the same default as this change. Built boards keep c0017's `(paper "A4")`; a `Design.sheet(…)` keyword and its lowering are a follow-up after c0012 archives (with c0019, which reworks `build`, or in v0.2a). v0.1 sets `Board.sheet` only through the model API; acceptance item 4 passes a `.kicad_wks` on the command line.
- **RT1 of a built design (settled).** Ids (`dsl` against `kicad` keys), `lib_symbol_ref`, pin names and pin types are not in the board, so a model-to-board comparison must go by keys (reference, pad number, net name). c0013's roundtrip stage runs RT1 (c0009's same-version rebuild) on the built board and declines the key comparison (its Open Questions). That comparison goes to c0019's lens (components, positions, properties) and c0020's `netlist.assignment_compare` (pad nets); until then this change's hermetic readback test covers the build.
- **Built-project marker for c0013 (settled).** c0013's `verification-loop` treats a folder as built when `<root>/.fenolite/meta.json` or `<root>/.fenolite/build.json` exists, and rejects `build.json` alone as the marker. This change writes both files into every built project, and only `build` writes `build.json`. Nothing is left to decide.
- **Example tables.** The CC0 example's own tables reach `tests/data/libs` through `${KIPRJMOD}/../../tests/data/libs/…`; only Fenolite's resolver reads them, and built output is vendored. The default: no duplicate CC0 copies under `examples/`.
- **Budget.** 8.5 working days against the roadmap's 6.5 (and a plan line of 1.5 weeks shared with c0019's 5). The default: accept the re-baseline and the cut order of "Budget".
- **Divergence check against the working tree (2026-10-02, settled for c0017).** c0017 is archived (`7d973f1`): `Context` has `kicad_target` (default 10) and `allow_lossy`, and `place_footprint` keeps its `copper` keyword, which the living "Footprint embedding" lacks. This change documents it (MODIFIED, Decision 15) and the build always passes the copper names of `created_layers(copper)` (task 8.2). `layers.created_layers` keys layer ids by name (backend `kicad`), and the build re-keys them for `dsl` (Decision 7). `triad.py`, `lowering.py` and `pro.py` (c0010, c0018) do not exist yet. c0009, c0014 and c0017 are archived, so `kicad-file-backend` and `verification-evidence` are living capabilities, and no requirement name used here collides. Task 1.1 re-checks every name consumed from c0018 and c0010.
- **MODIFIED "Identifier derivation" (settled).** c0017 MODIFIED this requirement and was archived on 2026-10-02, so its version is now the living text in `openspec/specs/design-model/spec.md`. The delta copies that living text (both paragraphs, placed copies as the third case, its four scenarios) and adds the fourth case and three scenarios. Task 6.1 re-checks the delta against the living spec.
