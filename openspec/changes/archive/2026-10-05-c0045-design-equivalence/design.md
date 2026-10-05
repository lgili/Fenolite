## Context

- **Scope.** Roadmap, Phase 4, v0.3: "`equivalent`, levels 1–4", and the table "Equivalence levels" (components, netlist as `REF-PIN`, footprints and pads, placement). Levels 5 to 8 belong to v0.4 and later.
- **Where the model stands.**
  - `Design.circuit.components` holds `ref`, `value`, `dnp` and pins. A board read without a schematic gets one synthesised component per footprint (`docs/design-model.md`, "Synthesised circuit").
  - `FootprintInstance` holds `component_id`, `lib_ref`, `position`, `rotation`, `side` and `pads`. `Pad.position` and `Pad.rotation` are footprint-local, with no further mirror on the bottom side ("Pad frame").
  - `Pad.layers` are backend layer names. `Board.layers` gives each name a `kind` and an `ordinal`, which is the only neutral way to say "top copper".
  - Lengths are integer nanometres and angles integer microdegrees. The model holds no float.
- **What c0020 already gives.** `backends.base.PadAssignment`, `Uncovered` and `PadNetList`; `checks.assignment_compare.board_netlist`, `model_netlist` and `compare`, which compares two sources as partitions of `REF-PIN` elements and locates the moved element (c0020 Decisions 7 and 8); the code `netlist.assignment-differs`. This change reuses all of them.
- **What the KiCad importer does, as far as it is known.**
  - `kicad-cli pcb import [--output F] [--format auto|pads|altium|eagle|cadstar|fabmaster|pcad|solidworks] [--report-format none|json|text] [--report-file F] INPUT` exists in 10.0 and not in 9.0 (S-0022, re-read 2026-10-03; S-0037; S-0166; `H-K-00`, `KICAD-VERIFIED`). The local 10.0.6 help text agrees.
  - One binary length unit is 2.54 nm, and the importer turns the Y axis (S-0002). A coordinate therefore rounds to an integer nanometre in each reader.
  - KiCad moves an imported board to the middle of its sheet, so an import keeps relative positions only, and it reports some faults only on standard output (`docs/formats/altium/pcb-document.md`, `ORACLE-VERIFIED(kicad-cli)` on 10.0.6; `H-A-PCB-KICAD-DOC`).
  - c0035's `tests/kicad/altium/test_pcbdoc_oracle.py` already compares a Fenolite-written document with its import, relative to the first component and within 10 nm, with its own `subprocess` call.
  - `H-A-UNIT` (c0004, `INFERRED`, pending) names this comparison as its test.
- **Upstream names.**
  - c0043 (being proposed): `fenolite.backends.altium.adapter`, and an `AltiumBackend` registered for reading. This change reaches it only through `backends.registry.for_path(path).read(path)`, so it depends on no other name of c0043.
  - c0041 (proposed): seven rows with the use `altium-pcbdoc` in `tests/corpus/manifest.toml`, ids `altium-third-party-pcbdoc-NN` (the documents of S-0172, S-0174, S-0175, S-0176, S-0188, S-0199 and S-0200). Its `tests/kicad/altium/test_pcbdoc_read_oracle.py` compares the reader's records with the same import, within 2 nm after one translation, lists "What KiCad does not import" in `docs/formats/altium/pcb-read.md`, and records its figure in `H-A-UNIT`.
  - c0020: see above. c0013: `Command`, `Result`, `InputRef`, `EXAMPLE_BOARD`, `resolve_board`, `find_kicad_cli`, `tests/_fakecli.py`, `tests/_projects.py::authored_project`. c0009: `KicadCli`, `_require_ten`, `pcb.read_board`.
- **Layering.** `checks` may import `core`, `model`, `geometry` and `backends.base`. `verify` may import only the standard library and `core` (living `verification-evidence`, "Verification package"). `backends.<x>` may import `model`, `geometry` and `backends.base`. `cli` may import anything.
- **Order.** Implementation and archive: after c0020 (its helpers) and after c0043 (the Altium read). c0044 is independent of this change.
- **Constraints.** Standard library only. No corpus file is committed. No private or vendor name in public text beyond the file-format names the repository already uses.

## Goals / Non-Goals

**Goals:**
- One pure function that says, level by level, whether two designs are equivalent, with every difference located at `REF` or `REF-PIN`.
- Tolerances and normalisations defined without a float and without a case left to the implementer.
- A command that reads any two designs the registry reads.
- The triangle: Fenolite's Altium import judged by `kicad-cli`'s import, with the importer's own changes written down per version.

**Non-Goals:**
- Everything under "Non-goals" in the proposal.
- A new `check` stage. `equivalent` is a command of its own.
- A refactoring of c0035's oracle tests onto `KicadCli.import_board`.
- An `ImportOracle` protocol in `backends.base`: one importer exists, and the command may name it.

## Decisions

1. **The comparison lives in `fenolite.checks.equivalence`.** It needs only `model`, `core` and c0020's helpers in `checks` and `backends.base`, which is exactly the `checks` row of the layering table. No `ALLOWED` entry changes.
   - Rejected: `fenolite.verify`. Its living requirement allows only the standard library and `core`, and forbids loading `fenolite.model`.
   - Rejected: `fenolite.convert`. It is the v0.5a conversion package and may import every backend; a comparison that can import a backend will name one sooner or later.
   - Rejected: a new top-level package `equivalence`. It would need a MODIFIED delta of "Allowed import edges" for no gain.

2. **Levels are cumulative, and each fault is reported once.** `--level N` runs levels 1 to N. A component that level 1 reports as missing or ambiguous is left out of the later levels, and a component placed on one side only is reported once at level 3.
   - Rejected: independent levels (`--level 3` runs only level 3). The roadmap's levels are ordered; an agent would have to run four commands to learn where two designs diverge.
   - Rejected: reporting the pads and the placement of a missing component again. One missing part would give dozens of differences.

3. **Components are keyed by reference.** The roadmap's level 2 is `REF-PIN`, so `REF` is the key at every level. Model ids are not comparable across backends: each backend derives them from its own native ids.
   - A reference held twice on one side, or empty, cannot be paired. It gives one `ref-ambiguous` difference and takes no further part. `--ignore-ref GLOB` removes such parts (mounting holes named `REF**`) on request.
   - Rejected: pairing duplicates by position. Position is level 4; level 1 must not depend on it.
   - Rejected: ignoring references that end in `**` by default. The user must see that parts were left out.

4. **Level 2 is c0020's partition comparison.** `board_netlist` gives the pads of a side that has footprints, `model_netlist` the pins of a side that has only a circuit, and `assignment_compare.compare(a, b, min_pins=1)` compares them. Net names are never compared: a renamed net is counted as `renamed`, not reported.
   - One difference from c0020: an element that only one side holds is a difference here (`pin-missing`), where c0020 reports coverage (`netlist.uncovered`). Two designs with different pin sets are not equivalent.
   - The code of a `net` difference is c0020's `netlist.assignment-differs`, built by `checks.codes.issue`. c0020's `ISSUE_CODES` table is not extended: the other codes live in `EQUIVALENCE_CODES`.
   - c0020's `_names` and `_net` helpers in `assignment_compare.py` are made public as `net_names` and `net_text` so that both callers word a net the same way. No behaviour of c0020 changes.
   - Rejected: a second partition algorithm, or comparing sorted `REF-PIN` sets per net name (names differ between backends; an export may shorten them).
   - Rejected: a per-side option to choose the netlist source. The rule "board when it has footprints, else circuit" is deterministic; a design's circuit against its own board is c0020's stage.

5. **Level 3 compares in the footprint's frame.** `Pad.position` and `Pad.rotation` are footprint-local by the model's contract, so level 3 does not depend on placement, and level 4 adds exactly the placement.
   - Pads are paired by number, then by sorted local position inside a number. Several pads may share a number.
   - Compared: `kind`, `shape`, `size`, `drill`, `position`, `rotation`, copper span. Not compared: padstacks per layer, mask and paste, custom outlines, graphics, attributes, 3D models (levels 7 and 8).
   - The copper span comes from `Board.layers`: lowest copper ordinal `top`, highest `bottom`, others `inner`. A layer name the board does not declare makes the span unknown: it is counted, never guessed.
   - Rejected: pads in the board frame. A moved footprint would give a difference for every pad at level 3 and again at level 4.
   - Rejected: comparing `Pad.layers` as strings. `F.Cu` and `Top Layer` are the same layer.
   - **Fallback decided now.** If `H-G-EQ-ROT` shows that the importer stores a bottom component in another local frame than the adapter, level 3 gains a rule kind in the profile, `frame = "board"`, under which pad centres are compared in the board frame after the translation (+0.5 day, from the reserve). It is not built before the measurement asks for it.

6. **Tolerances are two integers, and every rule is written out.** `Tolerances(length_nm, angle_udeg)`, both 0 by default, because the model is exact and two reads of one KiCad file must be identical.
   - Lengths: per coordinate, `|a − b| ≤ length_nm`. No Euclidean distance, which would need a square root or a squared tolerance.
   - Angles: on the circle, `min(d, period − d) ≤ angle_udeg` with `d = (a − b) mod period`.
   - Pad rotation by symmetry: none for a round pad; period 180° for `rect`, `oval` and `roundrect`, with the quarter-turn form (`w×h` at θ equals `h×w` at θ ± 90°) accepted as equal; period 360° for `trapezoid` and `custom`.
   - Side: exact.
   - Text: exact. The footprint name is the part of `lib_ref` after the last `:`, because a library nickname is a property of a library table, not of the board.
   - Rejected: a default tolerance above 0. It would hide a 1 nm fault of a KiCad round trip. The triangle's tolerance comes from its profile.
   - Rejected: one tolerance per field. Two numbers cover lengths and angles; nothing else is numeric.
   - Rejected: canonicalising a pad to `w ≥ h` before comparing. Near a square pad, a tolerance would flip the canonical form on one side only.

7. **One translation, by the lower median.** `--frame relative` subtracts `(median_low(dx), median_low(dy))` over the compared footprints. The median is an integer of the data, is not moved by rounding noise, and stays right while fewer than half of the parts moved.
   - Rejected: an anchor component (c0035's test uses the first one). If the anchor is the part that moved, every other part is reported.
   - Rejected: the most common vector. Rounding gives several vectors one nanometre apart, and the mode becomes arbitrary.
   - Rejected: removing a rotation or a mirror too. No reader or importer is known to turn a board; a flipped Y axis would be an adapter bug that must stay visible.

8. **Differences are data; exclusions never hide them.** A `Difference` holds the level, the kind, `where`, the field and both values as exact strings. A matching rule moves it to `excluded`, still listed with the rule id. The exit code looks only at what is not excluded.
   - Rejected: dropping excluded differences. A reader of the output could not tell "equal" from "known to differ".
   - Rejected: rules that match on values with a pattern language. Level, kind, field and a `where` glob are enough for an importer behaviour; a rule narrower than that is a per-board waiver, which the user may write in their own file with a narrow glob.

9. **The exclusion format belongs to the comparison; the importer data belongs to the KiCad backend.** `checks/equivalence/exclusions.py` parses TOML with `tomllib` and knows no tool. `backends/kicad/data/altium_import_exclusions.toml` holds the profiles `kicad-import` per version line, and `backends/kicad/altium_import.py` returns its text. The command joins them.
   - A rule is attributed `importer` or `undecided`. `undecided` is for a difference where no public source says which reader is right; it keeps the level `INFERRED` for the rows it touches. A difference Fenolite causes gets no rule.
   - A profile also sets the frame (`relative`) and the tolerances, so the triangle's numbers are data with a measured justification, not constants in code.
   - A version line without a profile runs with no rule and a warning. A new KiCad minor therefore fails loudly in the corpus test instead of inheriting old rules.
   - Rejected: the data file in `checks`. `checks` names no backend (c0020 Decision 5).
   - Rejected: exclusions only in tests. The agent that runs `equivalent --against kicad-import` on its own board needs the same list.

10. **The import runner is a method of `KicadCli`.** `import_board` uses the runner's temporary folder, time limit and 10.0 guard, like `upgrade_board`. `altium_import.import_design` reads the result with `pcb.read_board` and sanitises messages.
    - Both the JSON report and standard output are kept: KiCad reports some faults only on standard output (c0035's finding).
    - Rejected: calling `subprocess` from the command, as c0035's test does. Isolation and sanitising would be written twice.

11. **The triangle is a mode of the command.** `equivalent A --against kicad-import` needs no second path. It refuses anything but a PCB document, needs `kicad-cli` 10, and reports `evidence.oracle = "kicad-cli"`.
    - Rejected: a separate command `triangle`. It is the same comparison with one side made by a tool.
    - Rejected: a test-only harness. See Decision 9.

12. **Sides are read through the registry, plus two Fenolite forms.** A `.fenolite/` folder is a built design (`load_dir`). A `.kicad_pro` or a folder resolves to its board with c0013's `resolve_board`. Everything else is `registry.for_path(path).read(path)`.
    - The command names no Altium module. Whatever c0043's backend detects is readable, including a project file if c0043 reads one.
    - Rejected: reading a KiCad project's `.fenolite/` automatically. `equivalent proj/.fenolite proj` says what is compared; hidden inputs do not.

13. **Measure before writing rules.** Task group 5 runs the triangle on the committed document and on the corpus with an empty profile first, records every difference by kind in the evidence page, and only then writes rules. Each hypothesis below has its fallback: a refuted row keeps its id, gets a successor, and the behaviour becomes a rule or an adapter fix.
    - Rejected: writing the rules from the importer's source. The source is GPL and is read for facts only; the measurement is the evidence.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/checks/equivalence/__init__.py` | re-exports listed in the requirement "Equivalence package" |
| `src/fenolite/checks/equivalence/model.py` | `LEVELS`, `LEVEL_NAMES`, `Frame`, `Tolerances`, `Difference`, `Excluded`, `LevelResult`, `EquivalenceReport` (`levels`, `tolerances`, `frame`, `translation`, `equivalent`) |
| `src/fenolite/checks/equivalence/norm.py` | `normalise(angle)`, `angle_distance(a, b, period)`, `lengths_equal`, `points_equal`, `sizes_equal`, `footprint_name(lib_ref)`, `pad_symmetry(pad, tolerances)`, `pads_equal_turned(a, b, tolerances)`, `copper_span(pad, board)`, `translation(pairs)` |
| `src/fenolite/checks/equivalence/levels.py` | `KINDS`, `level_components`, `level_netlist`, `level_footprints`, `level_placement`, `max_level(a, b)`, `compare_designs(a, b, *, level, tolerances, frame, ignore_refs, rules)` |
| `src/fenolite/checks/equivalence/exclusions.py` | `Rule`, `Profile`, `load_profiles(text, *, file="")`, `select_profile(profiles, name, tool_version)`, `apply_rules(result, rules)` |
| `src/fenolite/checks/equivalence/codes.py` | `EQUIVALENCE_CODES`, `difference_issues(report)` |
| `src/fenolite/checks/assignment_compare.py` | `net_names`, `net_text` (c0020's private helpers, made public) |
| `src/fenolite/backends/kicad/cli.py` | `KicadCli.import_board(source, *, format="altium") -> ImportRun`, `ImportRun(run, board, report)` |
| `src/fenolite/backends/kicad/altium_import.py` | `ImportedDesign(read, messages, tool_version)`, `import_design(cli, source)`, `exclusions_text()`, `IMPORT_EVIDENCE` |
| `src/fenolite/backends/kicad/data/altium_import_exclusions.toml` | the `kicad-import` profiles per version line |
| `src/fenolite/cli/cmd_equivalent.py` | `COMMAND` (`equivalent`, `mutates=False`) |
| `tests/unit/checks/equivalence/` | `test_package.py`, `test_norm.py`, `test_levels.py`, `test_exclusions.py`, `test_codes.py`, `test_exclusion_data.py`, `_cases.py` (designs changed with `dataclasses.replace`) |
| `tests/unit/cli/test_equivalent_cmd.py`, `tests/unit/backends/kicad/test_import_board.py` | the command and the runner against `tests/_fakecli.py` |
| `tests/kicad/equivalence/` | `test_import_runner.py`, `test_triangle_blink.py`, `test_triangle_corpus.py` |
| `docs/equivalence.md`, `docs/evidence/equivalence-triangle.md` | the user page and the measurement record |

## Sources registered by this change

No new source. S-0253 to S-0260 stay free. Task 1.1 widens the "used for" cells of these rows:

| id | used for (added) |
|---|---|
| S-0022 | `pcb import`: `--output`, `--format` with its values, `--report-format none\|json\|text`, `--report-file` (re-read 2026-10-03) |
| S-0002 | the triangle: 2.54 nm per binary unit and the turned Y axis, as the reason for a rounding tolerance |
| S-0166 | `pcb import` as the triangle's converter (10.0 only) |
| S-0172, S-0174, S-0175, S-0176, S-0188, S-0199, S-0200 | documents of the corpus triangle (c0045), fetched and never committed |

## Hypotheses registered by this change

| id | statement | test | criterion |
|---|---|---|---|
| `H-G-EQ-L1` | Fenolite's import of an Altium-written PCB document and `kicad-cli`'s import of it hold the same components: references, values and fitted state | `tests/kicad/equivalence/test_triangle_corpus.py -k level1` | no level-1 difference outside the profile's rules on every corpus row and on the committed document |
| `H-G-EQ-L2` | Both imports give the same partition of `REF-PIN` elements into nets, pads on no net included | the same file, `-k level2` | no level-2 difference outside the rules |
| `H-G-EQ-L3` | Both imports give the same pads per footprint: kind, shape, size, drill, local position, local rotation and copper span | the same file, `-k level3` | no level-3 difference outside the rules |
| `H-G-EQ-L4` | Both imports give the same side, rotation and, after one translation, position per component | the same file, `-k level4` | no level-4 difference outside the rules |
| `H-G-EQ-SHIFT` | KiCad's importer moves a board by one vector: after the median translation every component agrees within the profile's tolerance | `test_triangle_corpus.py -k translation` | one translation per document; the largest remaining difference is recorded and is at most the profile's `tolerance_nm` |
| `H-G-EQ-ROUND` | The two readers round 2.54 nm units independently, so positions and sizes differ by at most 4 nm after the translation (S-0002) | `test_triangle_corpus.py -k rounding` | measured maximum at most 4 nm; the profile's tolerance is 10 nm |
| `H-G-EQ-REF` | The importer keeps component designators and pad designators verbatim, so `REF` and `REF-PIN` pair without mapping | `test_triangle_corpus.py -k keys` | no `component-missing`, `ref-ambiguous` or `pin-missing` difference that only a renamed key explains |
| `H-G-EQ-FPNAME` | The importer names each footprint by the document's pattern name, so the names after the last `:` are equal | `test_triangle_corpus.py -k footprint_name` | no `footprint-name` difference, or one rule that covers every such difference |
| `H-G-EQ-VALUE` | The importer fills the footprint's value from the same field as the adapter's `Component.value` | `test_triangle_corpus.py -k value` | no `value` difference, or one rule with the field the importer uses |
| `H-G-EQ-ROT` | For top and bottom components the importer's rotation and local pad frame equal the model's, modulo 360° | `test_triangle_corpus.py -k rotation`; `test_triangle_blink.py` (`D1` is on the bottom) | no `rotation`, `pad-position` or `pad-rotation` difference on bottom components that top components lack |
| `H-G-EQ-PADSHAPE` | The importer maps the round, rectangular and rounded-rectangle pads to `circle` or `oval`, `rect` and `roundrect`; an octagonal pad becomes another shape (S-0002 lists the four shapes) | `test_triangle_corpus.py -k pad_shape` | no `pad-shape` difference for the first three; the octagonal case is one `importer` rule or absent from the corpus (then recorded as not observed) |
| `H-G-EQ-FREE` | Pads and holes that belong to no component are imported as footprints with generated references, so they appear on side `b` only | `test_triangle_corpus.py -k free_pads` | every `component-missing` on side `a` names a generated reference and is covered by one `importer` rule, or none occurs |

Backend column: `altium` for `H-G-EQ-L1` to `-L4`, `kicad` for the others. Each row starts `INFERRED` with result `pending`. `H-A-UNIT` is not re-registered: task 5.4 records its result.

## Evidence level per behaviour (before merge)

| behaviour | level | proved by |
|---|---|---|
| Normalisation, tolerances, frame, levels 1 to 4, exclusions | none of its own (exact rules on the model) | `tests/unit/checks/equivalence/` |
| `equivalent A B` output | the lowest of the two reads | `tests/unit/cli/test_equivalent_cmd.py` |
| `KicadCli.import_board` | `KICAD-VERIFIED (10.0.x)` (`H-K-00`) | `tests/kicad/equivalence/test_import_runner.py` |
| Triangle on the committed document | `ORACLE-VERIFIED(kicad-cli)` (10.0.x), for what KiCad's importer reads of a Fenolite-written file | `test_triangle_blink.py` |
| Triangle on Altium-written documents, per level | `ORACLE-VERIFIED(kicad-cli)` (10.0.x) when the row's criterion holds with no `undecided` rule at that level or below; `INFERRED` otherwise | `test_triangle_corpus.py`, `docs/evidence/equivalence-triangle.md` |
| Importer rules | `ORACLE-VERIFIED(kicad-cli)` per version line when observed on a named row | `test_triangle_corpus.py -k rules_are_live` |
| Anything about Altium Designer itself | not claimed | — |

## Size (design-days)

| part | days |
|---|---|
| Registers, fact rows, corpus check | 0.5 |
| `model.py`, `norm.py` and their tests | 1.0 |
| Levels 1 to 4 and their tests | 1.5 |
| Exclusion format, application, codes | 0.75 |
| `equivalent` command, sides, result, consistency | 1.0 |
| Import runner and `altium_import` | 0.5 |
| Triangle mode and the committed document | 0.5 |
| Corpus measurement, rules, evidence page | 1.25 |
| Reserve: adapter fixes the triangle finds, Decision 5's fallback | 1.0 |
| Documentation and closing | 1.0 |
| **Total** | **9.0** |

The reserve is used only on a measured fault. If the triangle finds faults larger than the reserve, they are recorded as `undecided` rules with an open row, and the level's label stays `INFERRED`.

## Overlaps with other active changes

- **c0020.** Reused, not modified: `compare`, `board_netlist`, `model_netlist`, `PadNetList`, `netlist.assignment-differs`. Two private helpers become public. c0020 must be implemented first; it already is.
- **c0041.** Its oracle compares reader records with `kicad-cli`'s import at record level (nets, footprints, pads, vias, tracks), with its own exclusions for records KiCad does not import. This change compares models, level by level, after the adapter, so it also judges c0043. The corpus rows and the use `altium-pcbdoc` are c0041's; this change adds no row and no use. A rule of this change's data file that restates a c0041 exclusion cites that page in its `reason`.
- **c0043.** Reached only through the registry. A fault found in the adapter is fixed in `backends/altium/adapter` with a regression test, inside the reserve.
- **c0044.** `diff` lists exact differences of one format; `equivalent` gives a verdict per level across formats. No shared code and no shared requirement.
- **c0035.** `tests/kicad/altium/test_pcbdoc_oracle.py` keeps its own comparison.
- **ci-baseline.** Not modified. `test_triangle_blink.py` needs no corpus and runs in `kicad-10`. `test_triangle_corpus.py` runs wherever the `altium-pcbdoc` rows are fetched (Open Questions, 2).

## Risks / Trade-offs

- **c0043 is not written yet.** Its `Component.value`, footprint name and bottom-side frame are unknown here. → The comparison depends only on the model's contract; the hypotheses `H-G-EQ-VALUE`, `-FPNAME` and `-ROT` measure the three points, each with a rule or a fix as outcome.
- **The importer and the adapter may share a mistake.** Both could read a field the same wrong way, and the triangle would pass. → The label is `ORACLE-VERIFIED(kicad-cli)`, which says only that two independent readers agree; Altium rows are never settled by it.
- **A long exclusion list would empty the oracle.** → Every rule needs a hypothesis, a reason and a live match; the evidence page prints excluded counts next to compared counts, per level.
- **The median fails when most parts moved.** → Then most parts are reported, which is the truth; `--frame absolute` gives the plain comparison.
- **Large outputs.** A wrong frame gives one difference per part. → `--fields levels` keeps the counts only; the differences are sorted and stable.
- **Corpus documents may hold duplicate designators.** → They give `ref-ambiguous`, recorded per row in the evidence page; they are a property of the document and get no rule, and the corpus test passes `--ignore-ref` only for the references the page lists.

## Migration Plan

Additive. A new command, a new package under `checks`, one new method and one module in the KiCad backend, one data file. No file format, schema or existing output changes. Rollback: remove the command module; nothing else imports the new code.

## Open Questions

1. **Default level.** Default: the highest level both sides support (`max_level`), so `equivalent A B` is the strongest statement available. Alternative: require `--level`.
2. **Corpus triangle in CI.** The living `kicad-10` job fetches only `--uses rt0`, and c0041's rows carry no `rt0`. Default: the corpus triangle is a local run on 10.0.6, recorded in the evidence page like the other local confirmations, and the committed-document triangle is the CI proof. If an earlier change makes `kicad-10` fetch the `altium-pcbdoc` rows, the corpus triangle runs there with no change here. This change does not modify `ci-baseline`. Task 1.3 records which case holds.
3. **Value at level 1.** Default: `Component.value` is compared exactly. If `H-G-EQ-VALUE` shows that the two readers take the value from different fields, the default becomes an `importer` or `undecided` rule, not a weaker comparison.
4. **`--against` for other importers.** Default: only `kicad-import`. The option takes a name so that a later oracle needs no new flag.
5. **A schematic-only side.** Default: levels 1 and 2 only, from the circuit. Level 2 between a schematic's circuit and a board is allowed and uses `model_netlist` for the schematic side.
6. **Maintainer question.** May the committed `tests/data/altium/blink/blink.PcbDoc` serve as the CI triangle? Default: yes; it is built from the authored CC0 library and is already committed.

## Implementation notes

Recorded while implementing (2026-10-05), on `origin/dev` with c0020, c0041, c0043 and c0066 on the branch.

**Names re-checked against the code found.**

1. **No name of this change was taken.** c0066 added `diff`, `roundtrip`, `fmt`, `explain`, `restore`,
   `net`, `region`, `neighbors` and `pads`; `equivalent` and `fenolite.checks.equivalence` were free.
   `checks/diff.py` (c0066) and `checks/assignment_compare.py` (c0020) each hold a class of their own for
   a difference; this change's `Difference` lives in `checks/equivalence/model.py` and is not exported by
   `fenolite.checks`.
2. **A built design is recognised differently by `diff`.** `diff` takes the project folder that holds
   `.fenolite/meta.json`; `equivalent` takes the `.fenolite/` folder itself, as the requirement states, and
   resolves a project folder to its board. Both stay as they are.
3. **`fenolite explain`.** c0066's test finds issue-code tables by a module-level name that ends in
   `ISSUE_CODES`. `codes.py` therefore also binds `ISSUE_CODES = EQUIVALENCE_CODES`; the table is listed in
   `cli.explain.TABLES`, and `cli/data/explain.toml` explains every `equiv.*` code. Spec amended.
4. **No requirement is modified.** The delta holds only added requirements, so no living text had to be
   re-read for a `MODIFIED` block. `KicadCli.import_board` adds to `kicad-oracle` without changing a
   requirement of it.
5. **The corpus triangle runs in CI.** The `kicad-10` job already fetches the `altium-pcbdoc` rows and runs
   `tests/kicad` with `FENOLITE_REQUIRE=kicad,corpus` (Open Question 2 expected a local run only). The
   corpus test reuses the `KNOWN_IMPORT_FAILURES` pattern of c0041's reader oracle for the row that the
   Linux build of `kicad-cli` 10.0.6 cannot import, and `rules_are_live` does not judge a rule on a row
   that was not imported. No workflow file and no corpus use changed.

**Deviations from the text of the design, each with its reason.**

6. **`KINDS` is defined in `model.py`** and re-exported by `levels.py`: `exclusions.py` needs it to check a
   rule's kind, and `levels.py` needs `apply_rules`.
7. **`Excluded` has a third field, `reason`.** `difference_issues(report)` must give the rule's reason and
   receives only the report. Spec amended.
8. **The level functions return what the next level needs.** `level_components` returns its result and the
   compared references, `level_footprints` its result and the footprint pairs, `level_placement` its
   result and the translation.
9. **Cases the requirement left open, now written down.** Two pads of different shapes: the smaller
   rotation period applies. A component with several footprints: the first by position. A component
   placed on neither side: not compared at level 3. Spec amended.
10. **`--against` refuses `--exclusions`.** The triangle's profile is the importer's own; a second rule
    file would have to be merged with it, which no requirement defines. Spec amended.
11. **A failed import still returns a result** (`level` 0, no level, `sides.b` `null`), so that the
    envelope keeps its shape. Side `b` of a triangle has no `sha256`: the converted board holds
    identifiers that change between runs. Spec amended.
12. **The proof of task 2.2** counted `def compare` lines; c0020's `compare_runs` and this change's own
    `compare_designs` match too. The proof now counts `def compare(`. Task amended.

**What the measurement changed (task group 5).**

13. **`H-G-EQ-REF` found a fault of the adapter, fixed in c0043's code.** The first run gave 88
    `component-missing` and 5 `ref-ambiguous` differences on one row: `adapter/board.py` took a component's
    reference from the source designator, which the 84 components of a repeated sheet share (the model
    then held seven duplicate references, `model.duplicate-ref`) and which 2 renamed components had left
    behind. The reference is now the designator text, and the source designator only without one. This
    changes one line of c0043's adapter and one sentence of its delta (`altium-import`, "Circuit
    synthesised from a board"), and `docs/formats/altium/import.md`; c0043's unit, corpus and oracle tests
    pass unchanged. The project import links by `SOURCEUNIQUEID` and by the record's source designator,
    not by `Component.ref`, and is not affected.
14. **`H-G-EQ-ROUND` is refuted; successor `H-G-EQ-ROUND-2`.** The largest difference is 9 nm, not 4 nm:
    KiCad holds a converted length in steps of 10 nm (c0041's fact). The profile's tolerance is 10 nm, as
    the row's criterion already said.
15. **`H-G-EQ-FREE` is refuted; successor `H-G-EQ-FREE-2`.** KiCad gives the footprint of a free pad no
    generated reference. Both reads hold it without a reference, so the empty reference is
    `ref-ambiguous` on four rows. As "Risks" says for duplicate designators, these get no rule; the corpus
    test leaves them out by name and the evidence page lists them.
16. **Two `undecided` rules keep the four level rows `INFERRED`.** One component of one row has an empty
    value in KiCad's board (no cause found in a public source), and two octagonal pads of another row are
    `roundrect` in KiCad's board and `custom` in the import (the model has no octagon). `H-G-EQ-PADSHAPE`'s
    criterion expected an `importer` rule for the octagon; it is `undecided`, because neither reading is
    the reference. Five rows and the committed document hold at all four levels with no `undecided` match.
17. **Rules that name pads.** A rule cannot select a pad by its layer or shape. The two paste-pad rules
    and the octagon rule name the pads of the rows they were observed on (`U6-7_[12]`, `D[34]-2`); the same
    behaviour on another board shows as a difference. Decision 8 rejected value matching, and this change
    keeps that decision. Spec amended.
18. **Decision 5's fallback was not needed.** No `rotation`, `pad-position` or `pad-rotation` difference
    occurs on 146 bottom-side footprints, so no `frame = "board"` rule kind was built.
