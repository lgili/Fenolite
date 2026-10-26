## Context

**Scope.** Milestone v0.5a (`docs/roadmap.md`, Phase 5: "conversion between KiCad and the second backend, with a report of what is kept or lost; controlled KiCad downgrade (capability resolver); public `equivalent`"; Open decisions row 38, 2026-10-09: the next release, `0.5.0`, is v0.5a alone). This change is the third item. It comes first in the order of v0.5a because the conversion (c0159, c0160, c0161) and the downgrade (c0162) prove each written project with it. Levels 6 and 7 moved after 1.0 (row 3), so "public" here means levels 1 to 5, reachable from the library and from every side a conversion produces, with a published reply.

**What exists** (checked on `origin/dev` at `f802b60`, 2026-10-09):

| where | what |
|---|---|
| `src/fenolite/checks/equivalence/__init__.py` | `compare_designs`, `max_level`, `difference_issues`, `Tolerances`, `Profile`, `load_profiles`, `select_profile` and the rest of the re-export list of "Equivalence package": pure, two `Design` values in, an `EquivalenceReport` out |
| `src/fenolite/cli/cmd_equivalent.py:126` `_side` | reads one side: a `.fenolite/` folder (`load_dir`), a `.kicad_pro` or a folder (`projectset.resolve_board`, so always the board), else `registry.for_path(path).read(path)`; a library is refused |
| `cmd_equivalent.py:145` `_preflight`, `:167` `_imported` | the triangle's `kicad-cli` 10 check and `altium_import.import_design` |
| `cmd_equivalent.py:260` `_result` | the `result` object; its keys are listed in `docs/cli-contract.md`, "equivalent", and in the living requirement "Equivalent command" |
| `src/fenolite/cli/api.py:136` | every command names the schema `fenolite.<name>.v0`; `schemas/` holds `fenolite.envelope.v0.json`, `fenolite.error.v0.json`, `fenolite.artifacts.v0.json`, `fenolite.placement-request.v0.json` and the model folder, no schema of a command's `result` |
| `tests/consistency/test_cli_consistency.py:70` | every reply is validated against the envelope schema only |
| `src/fenolite/backends/kicad/sch_netlist.py:432` `own_netlist` | Fenolite's netlist of the sheets it generates; it refuses sheets outside its grammar (`kicad.sch.netlist-unsupported`) |
| `src/fenolite/backends/kicad/oracle.py:159` `export_schematic_netlist` | `kicad-cli sch export netlist` of a project, read into a `KicadNetlist` (`NetComponent(ref, value, footprint, properties)`) |
| `src/fenolite/checks/equivalence/levels.py:249` | `pad-shape` compares `Pad.shape` exactly |
| `tests/unit/test_import_graph.py:27` `ALLOWED` | no `api` row; `root` and `cli` may import anything |

**Measured on 2026-10-09** (no tool; the probe scripts are kept with the change's working notes and are not committed; task 1.2 turns the count into a test):

1. *Equal-sized ovals.* The KiCad 10.0.6 demo board `complex_hierarchy.kicad_pcb` holds 40 `oval` pads whose two sizes are equal (and 54 `circle`, 21 unequal `oval`). Written to Altium with `lens.altium.write_model` and read back, every one of them is a `circle`; `compare_designs` at level 3 reports `pad-shape` `oval`/`circle` for each: 40 on that board, 180 on `kit-dev-coldfire-xilinx_5213`, 85 on `video`, 23 on `RoyalBlue54L-Feather`. Nothing else of those pads differs. Equivalence already removes the rotation of such a pad ("Pad rotation by shape"), so the rule knows the pad is a disc and still calls the shape different.
2. *Schematic sides.* `fenolite equivalent proj.kicad_sch other.PrjPcb` exits 2 (`FEN-2001`, "equivalent does not read proj.kicad_sch"): the KiCad backend's `read_kinds` hold `kicad_pcb`, `kicad_mod` and `kicad_sym` only.

## Goals / Non-Goals

**Goals**
- One function that a script, the CLI and `convert` call to compare two designs given as paths or models.
- A published, tested schema of the reply.
- Circuit-level equivalence between a KiCad schematic and any other side.
- No difference reported for copper that is the same.

**Non-Goals**
- Everything under "Non-goals" in the proposal.
- Changing what levels 1 to 5 compare beyond the one shape rule.

## Decisions

1. **A sub-package `fenolite.api`.** `fenolite.api.equivalent(a, b, *, level=None, tolerances=None, frame=None, ignore_refs=(), profile=None, against=None, kicad_cli=None, timeout=300.0) -> EquivalenceResult`, where `a` and `b` are each a `Path`, a `str` path or a `Design`. It holds the side reading of today's command (moved, not copied) in `api/sides.py`. The command parses its arguments, calls it and turns the result into its reply. The layering row: `api` → `model`, `geometry`, `backends*`, `checks`, `analysis`, `convert`, `lens`; `cli` keeps `ANY`; nothing below `api` imports it. c0159 adds `fenolite.api.convert` to the same package.
   - Rejected: a root module `fenolite/equivalence.py`, which the layering would class as `root` (any import) and which `import fenolite` users would read as part of the package root; one name per root file does not scale to `convert`.
   - Rejected: declaring `fenolite.checks.equivalence` alone public: it may not import `backends` beyond `backends.base`, so it cannot read a path.
   - Rejected: re-exporting from `fenolite/__init__.py`: `import fenolite` stays free of the readers (`package-layering`, "Bare import succeeds without extras").
2. **`EquivalenceResult`** is a frozen dataclass: `report` (`EquivalenceReport`), `a` and `b` (`Side(name, sha256, backend, kind, netlist_source, components, footprints, tool_version)`), `profile`, `issues` (the command's issue order) and `evidence`. `to_json()` returns exactly the command's `result`. A `Design` given directly is a side with `backend` `model`, `sha256` `null` and the evidence `INFERRED`, as a built folder is today.
3. **The schema.** `schemas/fenolite.equivalent.v0.json` (JSON Schema draft 2020-12, as the envelope's) describes `result`: every key of the living "Equivalent command", the kinds as an enum generated from `EQUIVALENCE_CODES`, and `additionalProperties: false` at every level. `tests/consistency` validates the `result` of every command that has a file `schemas/fenolite.<name>.v0.json`; `equivalent` is the first. Rejected: waiting for the v1.0 freeze (the roadmap's place for result schemas): the conversion of c0159 embeds an equivalence reply, and an agent needs its shape now. The maintainer decided on 2026-10-09 (open question 1) that `equivalent` and `convert` publish their result schemas now, as `v0`, and the other commands at the freeze.
4. **A KiCad schematic side.** A path ending in `.kicad_sch` is read with its sheet tree (the files beside it, as `projectset` finds them) and turned into a circuit-only `Design`: one component per reference with its value, one net per netlist net with its `REF-PIN` members. The netlist is `sch_netlist.own_netlist` when `grammar_issues` is empty, else `oracle.export_schematic_netlist` through `kicad-cli` (`--kicad-cli`, exit 6 `FEN-6001` without one). `max_level` is then 2; `netlist_source` is `schematic`. The do-not-populate flag comes from the netlist field `dnp` when the export holds it (task 1.1 checks the field name on both majors and records `H-K-EQ-SCHSIDE`); else every component is fitted and the side gives the info `equiv.dnp-unknown`, and level 1 compares no `dnp` for it. Task 1.1 (2026-10-09) found the field on both majors: a `comp` of a do-not-populate symbol holds `(property (name "dnp"))`, without a value, on 9.0.9 and 10.0.6, so the fallback and `equiv.dnp-unknown` are not built; the own netlist takes the flag from the symbol's `dnp` attribute, which KiCad exports as that property.
   - Rejected: reading `.kicad_sch` through the backend registry as a design: a schematic reader that builds a circuit from wires and labels is KiCad's connection graph, which plan D9 leaves to KiCad (`sch_netlist.py`, docstring).
   - Rejected: resolving a `.kicad_pro` to its schematic: the project keeps meaning its board, as `check` resolves it.
5. **Equal-sized ovals are circles.** In `norm.py`, `shape_class(pad, tolerances)` returns `circle` for an `oval` whose two sizes are equal within `length_nm`, else `pad.shape`; `pad-shape` compares the classes. A `roundrect` whose corner reaches half the shorter side is not touched (the model holds no corner ratio, c0126). Rejected: changing the Altium reader to give `oval`: Altium's round pad is the same copper, and the reader is right to call it a circle. Rejected: an exclusion profile for the conversion: a rule would hide a true shape change of the same `REF-PIN`.
6. **Discovery.** The `equivalent` entry of `capabilities.commands` gains `levels` (`[1, 2, 3, 4, 5]`) and `sides` (`fenolite_model`, `kicad_pcb`, `kicad_pro`, `kicad_sch`, `altium_pcbdoc`, `altium_schdoc`, `altium_prjpcb`); an agent no longer learns the side kinds from an error. The page `checks` of the agent guide gains one `fenolite-cmd` line with a schematic side.

## Files and public API

| file | content |
|---|---|
| `src/fenolite/api/__init__.py` (new) | re-exports `equivalent`, `EquivalenceResult`, `Side` |
| `src/fenolite/api/equivalence.py` (new) | `equivalent(...)`, `EquivalenceResult`, `Side`, `EVIDENCE_MODEL` |
| `src/fenolite/api/sides.py` (new) | `read_side(path_or_design, *, kicad_cli=None, timeout=300.0) -> ReadSide`; the triangle's import; the schematic side |
| `src/fenolite/cli/cmd_equivalent.py` | arguments, the call, the reply; `_side`, `_preflight`, `_imported` move to `api/sides.py` |
| `src/fenolite/checks/equivalence/norm.py`, `levels.py`, `codes.py` | `shape_class` (no `equiv.dnp-unknown`: task 1.1 found the flag's field on both majors) |
| `schemas/fenolite.equivalent.v0.json` (new) | the result schema |
| `tests/consistency/test_cli_consistency.py`, `tests/consistency/_schema.py` | result schemas validated when the file exists |
| `tests/unit/api/test_equivalence_api.py` (new), `tests/unit/cli/test_equivalent_cmd.py`, `tests/unit/checks/equivalence/test_norm.py` | the scenarios |
| `tests/kicad/equivalence/test_schematic_side.py` (new) | `H-K-EQ-SCHSIDE` on both majors |
| `tests/kicad/equivalence/test_oval_disc.py` (new) | `H-K-EQ-OVAL` on both majors |
| `tests/unit/test_import_graph.py`, `openspec/specs/package-layering` (by archive) | the `api` row |
| `docs/equivalence.md`, `docs/cli-contract.md`, `src/fenolite/agent/skill/references/checks.md` | the API, the side, the shape rule, the schema |

## Sources registered by this change

None expected. The KiCad facts rest on S-0020 and S-0029 (the two pinned `kicad-cli` images) and S-0058 (the demo boards). The block S-0740 to S-0759 is reserved for the changes of v0.5a (c0157, written by another session, may register sources after S-0727); this change uses none of it unless task 1.1 needs a public page for the netlist field.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-EQ-SCHSIDE | `kicad-cli sch export netlist` of 9.0.9 and 10.0.6 gives, for the generated example projects and the demo schematics of the corpus, the same components (reference, value) and the same `REF-PIN` partition as Fenolite's own netlist where that applies, and names the do-not-populate flag in a field whose name the test records (S-0020, S-0029) | `tests/kicad/equivalence/test_schematic_side.py` | probe `equiv-schside` `equal` on both majors; the field name recorded |
| H-K-EQ-OVAL | An `oval` pad whose two sizes are equal is drawn by KiCad 9.0.9 and 10.0.6 as the same copper as a `circle` pad of that size: the two Gerber or SVG outputs of the pad are equal (S-0020, S-0029) | `tests/kicad/equivalence/test_oval_disc.py` | probe `equiv-oval-disc` `equal` on both majors |

Both start `INFERRED`. Ids used without changing their level: `H-K-NETLIST-OWN`, `H-A-IMP-NETLIST`.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| `fenolite.api.equivalent` gives the command's reply | mechanical | `tests/unit/api/test_equivalence_api.py -k same_as_cli` |
| the result schema | mechanical | `tests/consistency` |
| a schematic side through the own netlist | `KICAD-VERIFIED` (the netlist's own row) | `test_schematic_side.py` |
| a schematic side through `kicad-cli` | `ORACLE-VERIFIED(kicad-cli)` | `test_schematic_side.py` |
| equal-sized ovals as circles | `KICAD-VERIFIED (9.0.x, 10.0.x)` (`H-K-EQ-OVAL`) | `test_oval_disc.py` |

The KiCad tests run in the pinned images `kicad/kicad:9.0.9@sha256:e638b79b…` and `kicad/kicad:10.0.6@sha256:18693567…` (S-0029), by the `kicad-9` and `kicad-10` jobs of CI or locally with docker.

## Risks / Trade-offs

- **Moving `_side` changes the command's behaviour by accident.** Mitigation: task 2.1 moves it first, with the existing command tests unchanged and green, before any new side.
- **A schema with `additionalProperties: false` breaks on every new key.** That is its purpose: a key added later needs the schema in the same commit, and the consistency suite says so.
- **The `kicad-cli` netlist of a hand-drawn schematic holds what the circuit of an Altium project does not** (power symbols as components, hidden power pins). Level 1 would report them. Mitigation: the netlist's components without a footprint field and with the power flag are left out and counted in `summary.power_symbols`; task 1.1 measures the demos first and the requirement says what is left out. Task 1.1 (2026-10-09): KiCad's export holds no `comp` for a power symbol on either major (`H-K-NETLIST-SHAPE`), so nothing is left out of the export; `power_symbols` counts the `#` references of the sheets.
- **The shape rule hides a real change** from a disc to an equal-sized oval in one file. It is the same copper; the rotation rule already treats it so.

## Migration Plan

- `fenolite equivalent` keeps its options, keys and exit codes; it gains a side kind.
- Comparisons that reported `pad-shape` `oval`/`circle` for equal-sized pads no longer do. `CHANGELOG.md` says so.
- Scripts may import `fenolite.api.equivalent`; `fenolite.checks.equivalence` keeps its names.

## Budget (4.5 days)

| part | days |
|---|---|
| entry check, the measurement test, the two hypotheses | 0.5 |
| `fenolite.api`, sides moved, the command as a caller, the layering row | 1.25 |
| the result schema and its consistency check | 0.75 |
| the schematic side (own netlist, `kicad-cli` netlist, dnp, power symbols) and its oracle | 1.25 |
| the shape rule and its oracle | 0.25 |
| capabilities, guide, docs, closing | 0.5 |
| **total** | **4.5** |

Cut order: (1) the `kicad-cli` path of the schematic side (generated schematics keep working through the own netlist); (2) `levels` and `sides` in capabilities. Not cut: the API, the schema, the shape rule.

## Open questions

All answered on 2026-10-09: the maintainer accepted every recommended answer (`docs/roadmap.md`, Open decisions row 40).

1. **Publish result schemas before the v1.0 freeze?** Recommended: yes for `equivalent` and `convert` only (c0159), as `v0`, and the rest at the freeze. Without them an agent learns the reply of the two commands that v0.5a adds from prose. Decided by the maintainer on 2026-10-09: yes, for `equivalent` and `convert` only (c0159), as `v0`; the rest at the freeze.
2. **Should `fenolite.api` be the one public Python surface for 1.0?** Recommended: yes; this change and c0159 put two functions there, and the freeze lists it with the CLI and the schemas. Decided by the maintainer on 2026-10-09: yes; the freeze lists `fenolite.api` with the CLI and the schemas.
3. **A `.kicad_pro` side meaning the schematic?** Recommended: no; a project keeps meaning its board, as in `check`, and the schematic is named by its file. Decided by the maintainer on 2026-10-09: no; a `.kicad_pro` side keeps meaning its board, and a schematic is named by its file.
