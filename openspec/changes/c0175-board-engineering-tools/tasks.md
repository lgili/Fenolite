## 0. Entry check

- [ ] 0.1 Read `openspec list` and the living specs this change touches (`specctra-dsn`, `cli-contract`, `routing`, `board-analyses`, `design-dsl`, `assembly-test-features`, `design-conversion`, `manufacturing-exports`, `kicad-oracle`). Write under this task, with the date: which open change holds a delta of "Routing rules in design files", "Route command budget and tiers" or "Analyze command" (regenerate the MODIFIED blocks from the living text if one was archived); the maintainer's answers to the three open questions of `design.md`; and which packages the maintainer splits into their own changes, with their ids. Proof: `openspec validate c0175-board-engineering-tools --strict --no-interactive`.

## 1. Router input fidelity (package 1)

Moved on 2026-10-26 to change c0197 (`openspec/changes/archive/2026-10-27-c0197-router-input/`), with its tasks 1.1 to 1.4 and its
deltas of `specctra-dsn` and `cli-contract`, by the maintainer's choice to start the package alone.

## 2. Ground ties (package 2)

Moved on 2026-10-26 to change c0198 (`openspec/changes/archive/2026-10-27-c0198-ground-ties/`), with its tasks 2.1 to 2.3 and its
two ADDED requirements of `board-analyses` ("Ground ties", "Sense nets and isolation islands"), by the
maintainer's choice to take the packages one at a time. The options of `ties` and `domains` in this change's
MODIFIED "Analyze command" are those c0198 adds. `analysis.sense-entry` is left out there (c0198's design,
decision 5).

## 3. Barrier crossings (package 3)

Moved on 2026-10-26 to change c0199 (`openspec/changes/archive/2026-10-27-c0199-barrier-crossings/`), with its tasks 3.1 and 3.2
and its ADDED requirement "Barrier crossings" of `board-analyses`, by the maintainer's choice to take the
packages one at a time. `--render` is left out there, because `analyze` is read-only (c0199's design,
decision 5); this change's MODIFIED "Analyze command" still lists it with `--width`.

## 4. File safety (package 9)

Tasks 4.1 to 4.5 moved on 2026-10-26 to change c0201 (`openspec/changes/archive/2026-10-27-c0201-file-safety/`), with the
requirements "Stable snapshot", "Publish guarded by receipts", "Open sessions and placeholders" and
"Project references" of `file-safety`, by the maintainer's choice of 2026-10-26 to do file safety first.
Moved on 2026-10-28 to change c0207 (`openspec/changes/c0207-diff-gates/`), with task 4.6 and the
requirement "Gated and three-way differences" of `file-safety`, split there into "Gated differences",
"Three-way difference of KiCad boards", "Three-way conflicts" and "Resave differences of Altium
documents". `--three-way` covers KiCad boards; the other formats are non-goals of c0207.

## 5. Practice checks (package 7)

Moved on 2026-10-28 to change c0204 (`openspec/changes/c0204-practice-checks/`), with its tasks 5.1 to 5.4, 5.8
and the kind `relief` of 5.5, its ADDED requirement "Coupling screen" and the six kinds `decoupling`,
`connectivity`, `bodies`, `relief`, `dead` and `coupling` of its ADDED requirement "Practice checks", by the
maintainer's choice of 2026-10-28 to take the package as its own change. The simulated pour there is a raster
(c0204's design, decision 2). The kinds `necks`, `loops` and `balance`, the tables `[[neck]]` and `[[loop]]`
and `--kinds power --split` stayed here, under the requirement "Pour shape checks". They moved on 2026-10-28 to
change c0213 (`openspec/changes/c0213-pour-shapes/`), with its tasks 5.5 (but `relief`), 5.6 and 5.7 and its
ADDED requirement "Pour shape checks", split there into "Neck kind", "Tips and slivers", "Loop kind", "Balance
kind", "Current split" and "Pour shape tables", by the maintainer's choice of 2026-10-28 to finish the
package. The widths there are measured on the raster of c0204 (c0213's design, decision 1).

## 6. Native Altium edit sessions (package 12)

Moved on 2026-10-29 to change c0241 (`openspec/changes/c0241-altium-edit-sessions/`), with its tasks 6.1 to 6.7
(renumbered there 1.1, 1.2, 2.1 and 3.1 to 3.4) and the whole `altium-edit` delta, whose requirements "Edit
session on an Altium document" and "Integrity check" were over 500 characters and are split there into
"Edit session on an Altium document", "Asserted edits", "Records cloned from the document", "Index upkeep",
"Operations gated by their hypotheses", "Integrity check", "Integrity rules of indices" and "Integrity rules
of parameters, models and layers". c0241 adds "Kit cases for edit sessions" (Part J of
`docs/evidence/altium-edit.md`) and the phase B tasks of its kit. This change no longer holds a delta of
`altium-edit`.

## 7. Copper tidy (package 5)

Moved on 2026-10-28 to change c0208 (`openspec/changes/c0208-copper-tidy/`): task 7.1, the right-angle part of
task 7.3 and the command part of task 7.5, with the requirements "Prune dangling copper", "Chamfer joints"
(for two tracks at 90°, as "Chamfer right-angle joints" and "Chamfers are checked") and "Tidy command" (for
`--prune`, `--chamfer`, `--leg` and `--drc`) of `copper-tidy`. The rest stays here, narrowed in this change's
`copper-tidy` delta to "Straighten runs", "Chamfer T-joints and zone outlines", "Style report" and "Tidy
straighten and report options". Tasks 7.2 to 7.5 moved on 2026-10-28 to change c0214
(`openspec/changes/c0214-tidy-straighten/`), with that whole `copper-tidy` delta. Moved on 2026-10-28 to
change c0228 (`openspec/changes/c0228-octilinear-router/`): task 7.6, the routing plugin `octilinear` with
pairs, with the requirement "Octilinear router plugin" of this change's `routing` delta, split there into
"Octilinear router plugin", "Octilinear connections", "Octilinear shapes", "Octilinear acceptance",
"Octilinear length limit", "Octilinear rounds", "Octilinear pairs", "Octilinear copper check" and
"Octilinear codes". The plugin places no via, and the command hands it the clearance in force and the
copper check through the job's extras (c0228's design, decisions 3 and 4). This change no longer holds a
delta of `routing`.

## 8. Layout reuse (package 4)

Moved on 2026-10-28 to change c0210 (`openspec/changes/c0210-layout-reuse/`): tasks 8.1, 8.2 (tracks, arcs
and vias) and 8.3, with the requirements "Block copy by pad fit" (pads with unique numbers), "Copper of a
copied block" (without zones) and "Reuse command", which c0210 delivers as `place --strategy reuse` with
`--drc` on request. Moved on 2026-10-28 to change c0227 (`openspec/changes/c0227-reuse-moves/`): tasks 8.4,
8.5 and 8.6, with the requirements "Pads matched by net partition", "Zones of a copied block" and "Group
moves" of this change's `layout-reuse` delta, split there into "Pads matched by net partition", "Zones of a
copied block", "A zone read without its outline", "Group moves", "Copper of a moved group", "Pose search"
and "Group move codes". Copper that a group's parts "own" is dropped there: copper moves with a group when
every pad it joins moves (c0227's design, decision 5). This change no longer holds a delta of
`layout-reuse`.

## 9. Assembly marks (package 8)

Moved on 2026-10-28 to change c0212 (`openspec/changes/c0212-assembly-marks/`): tasks 9.1 and 9.2 whole (the
ink extents with their cache and estimate, and `fenolite silk --designators` with `--keep`), with the
requirements "Text ink extents" and "Designator placement" of `silkscreen-layout`. The placement record
`silk-placements.toml` is dropped there (a rebuild keeps a board's fields). Tasks 9.3 (`--clip`) and 9.4
(`testpoints --place`) stay here, outside c0212 by its non-goals of 2026-10-28: clipping cuts the
footprints' own silkscreen, which needs the library made from a board (task 10.3) to keep the library in
step; placing test points adds parts and copper to a board that its design script lacks, so it needs the
copper clearance of each new probe and track and a way back into the script (`sync`), with a bench of its own.
Moved on 2026-10-28 to change c0226 (`openspec/changes/c0226-silk-clip/`): task 9.3 whole (`fenolite silk
--clip`), with the requirement "Silkscreen clipping" of `silkscreen-layout`, narrowed there: the margin
defaults to the project's `silk_clearance` rule (what KiCad's DRC applies between silkscreen and pads), texts
and filled shapes are not cut, and `silk` writes the board only, pointing to `fenolite library` (c0223) for
the library. This change no longer holds a delta of `silkscreen-layout`.
Moved on 2026-10-28 to change c0229 (`openspec/changes/c0229-testpoint-place/`): task 9.4 whole (`fenolite
testpoints --place`), with the requirement "Test-point placement" of `assembly-test-features`, split there into
"Test-point placement", "Probe sites", "Placed test points checked", "Placed test points kept by a rebuild" and
"Test-point placement codes". The probes are board-only footprints, which a rebuild keeps, so `sync` is not
changed; c0175's `--pitch` is `--grid` there, and the codes keep the prefix `testpoint.` (c0229's design,
decisions 1, 3 and 9). This change no longer holds a delta of `assembly-test-features`.

## 10. Library fidelity (package 10)

Tasks 10.1 to 10.3 moved on 2026-10-28 to change c0223 (`openspec/changes/c0223-library-fidelity/`), with the
three ADDED requirements of this change's `design-conversion` delta ("Mask and paste of imported pads",
"Model placement of imported footprints" and "Library made from a board"), narrowed there: the paste
`Enabled` switch and the solder `Tented` option are not read (unknowns U1 and U2 of
`docs/formats/altium/pcb-library.md`), models of bottom-side parts and models turned about X or Y are
reported as losses, and `fenolite library` reads KiCad boards. This change no longer holds a delta of
`design-conversion`. Task 10.4 stays here:

- [ ] 10.4 Add body copy by pad fit, with one model-store entry per rotation (Altium, behind the gates of c0241), and a coverage report against a house library that the user names. Proof: `uv run pytest tests/unit/reuse/test_bodies.py tests/unit/catalog/test_coverage.py -q`.

## 11. Generated copper (package 6)

Moved on 2026-10-28 to change c0224 (`openspec/changes/c0224-generated-copper/`), with its tasks 11.1 to 11.3
and its ADDED requirement "Generated copper and keep-outs" of `design-dsl`, split there into "Generated
copper calls", "Power band", "Keep-out ring around holes", "Class barrier", "Body keep-out", "Fan-out to a
zone", "Stitching of zone pieces" and "Generated copper codes", with "Generated copper passes the oracle" of
`kicad-oracle`. A spine that leaves the board and a barrier in pieces are errors of the build there, not
`DslError` (c0224's design, decision 1). Stitching counted by current and the free-area fill of the survey's
additions stay here, without a task until a package takes them.

## 12. Release checks (package 11)

Task 12.1 moved on 2026-10-27 to change c0203 (`openspec/changes/archive/2026-10-27-c0203-fabrication-readback/`), with the
requirement "Fabrication read-back" of `manufacturing-exports`, by the maintainer's order of 2026-10-26
(item 5 of the consolidation list).

Moved on 2026-10-28 to change c0209 (`openspec/changes/c0209-drc-trials/`): task 12.3 whole (`check
--exclude`, written in both item orders, and the stored exclusions judged as accepted exceptions, with the
requirement "DRC exclusions written" of `kicad-oracle`), and of task 12.2 the library call
`fenolite.api.trial` with its gate (`gate=True`), with the requirement "Trial edits gated by DRC". The rest
of task 12.2, the `--gate drc` option of the writing commands, moved on 2026-10-28 to change c0225
(`openspec/changes/c0225-drc-gate/`), with the requirement "DRC gate on writing commands" of `kicad-oracle`,
split there into "DRC gate on writing commands", "DRC gate report" and "DRC gate units". `route` and `tidy`
take the option there; `place --strategy reuse` keeps its `--drc` (c0225's design, decision 1).

Moved on 2026-10-28 to change c0211 (`openspec/changes/c0211-region-renders/`): task 12.4 whole (`render
--region`, drawn by Fenolite from the model, with `--nets`, `--open`, `--grid` and the `--cut` overlay of the
crossing analysis), with the requirement "Region renders" of `manufacturing-exports`.

## 13. Teaching

- [ ] 13.1 Add a tested line for each new command and DSL name to the closest page of the agent guide. Point the practice pages of c0174 to the commands that now answer their checks. Run `tools/gen_agent_guide.py`. Proof: `uv run pytest tests/unit/agent -q`; `uv run python tools/gen_agent_guide.py --check`.

## 14. Closing

- [ ] 14.1 Run the tests and the residue scan. Proof: `make check-fast`, then the CI jobs of the branch.
- [ ] 14.2 Update the evidence labels: the hypotheses of packages 1, 2 and 7 in `docs/hypotheses.md` (package 12's are c0241's), and the matrix. Proof: `uv run python tools/gen_evidence_matrix.py --check`; `uv run pytest tests/unit/test_hypotheses_register.py -q`.
- [ ] 14.3 Add an entry to `CHANGELOG.md` under `## [Unreleased]` once the maintainer has opened the version after 0.5.0. Proof: `uv run pytest tests/unit -k "release_record or changelog" -q`.
