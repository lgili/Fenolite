# openspec

Spec-driven development with [OpenSpec](https://github.com/Fission-AI/OpenSpec).

- `specs/<capability>/spec.md` — the current, normative requirements (SHALL/MUST + scenarios).
- `changes/<id>/` — one proposed change: `proposal.md` (why), `design.md` (how), `specs/` (deltas),
  `tasks.md` (≤ 1-day tasks, each with the command that proves it).
- `config.yaml` — project context and artefact rules injected into every change.

No code lands without a change. Archive a change with `openspec archive <id>` once all tasks are done.

## Change ids

Archived changes are under `changes/archive/`; a change in `changes/` is proposed or being implemented. Plan items keep their numbers (c0009–c0016);
split-offs and follow-ups take c0017 and later numbers in implementation order, and a new split-off
takes the next free number. Ids follow the form `cNNNN-<slug>`, a project convention (the `openspec`
CLI accepts any kebab-case name); lettered ids such as `c0009a` are not used. A slug may still change
until its change is proposed. The nine v0.2a changes were allocated together as c0060–c0068 on
2026-10-04, while c0058 was being written, so c0057 stays unused.
The six v0.2b changes were allocated together as c0069–c0074 on 2026-10-05.
The ten changes of the write part of v0.3 were allocated together as c0083–c0092 on 2026-10-06, and
c0093 was taken for the release of v0.2 on the same day.
Since 2026-10-07 (c0136) v0.3 is the whole second backend, its read part and its write part, and v0.4
names the proposals that are written on other branches and are not in this table: c0077–c0081 (the
agent track), c0096, c0097 and c0099 (board authoring) and c0100–c0120 (the complex board). c0095 is
reserved; c0098 is in v0.4 by the maintainer's decision of 2026-10-08 (roadmap, "Open decisions", row 35) and has its row below. `docs/roadmap.md`, “Milestone names”, has the decision; archived changes
keep the names of their day. The changes of v0.4 were gathered on the branch `v04` and are released as
`0.4.0` by c0154; their folders are not all rows of this table. On 2026-10-09 every change whose tasks were all
closed and whose archive order allowed it was moved to `changes/archive/` (c0078–c0080, c0096–c0100,
c0102, c0106, c0111, c0115, c0119, c0120, c0134, c0136, c0140, c0142, c0145, c0153 and c0154); a row of
this table whose folder is still in `changes/` is open, and `docs/release/v0.4.md`, "Archive order", says
what each open change with every task closed waits for. Later on 2026-10-09, after the maintainer's Altium
report of that day closed their last tasks, c0084, c0087, c0088, c0101, c0103, c0113, c0116, c0117, c0118,
c0138, c0141, c0144, c0147 and c0148 were archived too, and after his second report of that day (steps X1
to X7 and X9 to X12 of Part X) c0085. Later still, after the maintainer waived the KiCad oracle of c0086
(task 5.2: `kicad-cli` reads no schematic document), c0086, c0090, c0124, c0127, c0128, c0121, c0155, c0107
and c0104 were archived, in that order, and then c0108, c0109, c0112 and c0110, whose deferred tasks
were closed on 2026-10-09.
The changes of v0.5a were allocated together as c0158–c0162 on 2026-10-09 and proposed on the branch `dev-v05a-proposals`; c0157 is the yardstick change of another branch.
The four changes of the maintainer's capability request "board slots and cut-outs, end to end" were allocated together as c0167–c0170 on 2026-10-15 and proposed on the branch `dev-slots-proposals`; c0164–c0166 were taken on `dev` and on the maintainer's `codex/` branches. The maintainer placed c0167 and c0169 in `0.5.0` on 2026-10-15 and c0168 and c0170 on 2026-10-16 (`docs/roadmap.md`, "Board slots and cut-outs").
On 2026-10-16 the maintainer's requests for native Altium Draftsman documents and for board panels took c0172 and c0173, both placed in `0.5.0`, which he holds until their native parts pass his Altium kits.

| id | slug | roadmap item | parent |
|---|---|---|---|
| c0009 | `kicad-board-backend` | 0009 (part 1) | — |
| c0010 | `kicad-project-file` | 0010 | — |
| c0011 | `dsl-thin-build` | 0011 (part 1) | — |
| c0012 | `sheet-templates-kicad` | 0012 | — |
| c0013 | `kicad-oracle-and-check` | 0013 (part 1) | — |
| c0014 | `verification-evidence` | 0014 | — |
| c0015 | `zone-fill` | 0015 | — |
| c0016 | `routing-plugins` | 0016 | — |
| c0017 | `kicad-board-writer` | split-off | 0009 |
| c0018 | `kicad-rules-footprints` | split-off | 0009 |
| c0019 | `layout-preserve` | split-off | 0011 |
| c0020 | `check-netlist-drc` | split-off | 0013 |
| c0021 | `kicad-libs-cache` | follow-up | c0008 |
| c0022 | `placement-grid` | split-off | 0016 |
| c0023 | `specctra-freerouting` | split-off | 0016 |
| c0024 | `manufacturing-exports` | unowned deliverables | — |
| c0025 | `release-v0-1` | unowned deliverables | — |
| c0026 | `kicad-board-minimums` | dogfood gap | c0010 |
| c0027 | `build-properties-vendoring` | dogfood gap | c0011 |
| c0028 | `board-frame-copper` | dogfood gap | — |
| c0029 | `copper-check` | dogfood gap | — |
| c0030 | `footprint-fields` | dogfood gap | — |
| c0031 | `zone-settings` | dogfood gap | — |
| c0032 | `altium-schematic-writer` | v0.3 write, first item pulled forward | — |
| c0033 | `altium-binary-schematic` | follow-up | c0032 |
| c0034 | `altium-schlib-writer` | v0.3 write item pulled forward | c0032 |
| c0035 | `altium-pcb-writers` | v0.3 write items pulled forward | c0032 |
| c0036 | `no-connect-pins` | follow-up | c0032 |
| c0037 | `altium-hierarchy-harness` | v0.3 write item pulled forward | c0032 |
| c0038 | `altium-pcb-copper` | v0.3 write item pulled forward | c0035 |
| c0039 | `altium-compound-reader` | v0.3 read | — |
| c0040 | `altium-schematic-reader` | v0.3 read | — |
| c0041 | `altium-pcb-reader` | v0.3 read | — |
| c0042 | `altium-project-reader` | v0.3 read | — |
| c0043 | `altium-import` | v0.3 read | — |
| c0044 | `altium-inspect-check-diff` | v0.3 read | — |
| c0045 | `design-equivalence` | v0.3 read | — |
| c0046 | `altium-sheet-template-import` | v0.3 read | — |
| c0047 | `board-analyses` | v0.3 read | — |
| c0048 | `altium-eco-clean` | v0.3 (Altium writer) | c0038 |
| c0049 | `test-speed` | v0.1 | — |
| c0050 | `transform-composition-bound` | v0.1 | — |
| c0051 | `drc-canary-repeatability` | v0.1 | — |
| c0052 | `release-hygiene` | v0.1 | — |
| c0053 | `altium-script-copper` | v0.1 (Altium writer) | c0038 |
| c0054 | `dsl-rule-constructor` | v0.1 | c0011 |
| c0055 | `dsl-footprint-authoring` | dogfood gap / v0.3 write footprint generator | c0011, c0018 |
| c0056 | `dsl-pin-pad-map-slots` | dogfood gap / v0.3 write footprint generator | c0055 |
| c0057 | (unused) | — | — |
| c0058 | `authored-symbols` | follow-up | — |
| c0059 | `shared-footprint-pads` | follow-up | c0055 |
| c0060 | `kicad-schematic-reader` | v0.2a | — |
| c0061 | `kicad-schematic-writer` | v0.2a | — |
| c0062 | `erc-oracle` | v0.2a | — |
| c0063 | `netlist-compare` | v0.2a | — |
| c0064 | `bom-pnp-templates` | v0.2a | — |
| c0065 | `artifact-manifest-states` | v0.2a | — |
| c0066 | `cli-inspection-commands` | v0.2a | — |
| c0067 | `evidence-matrix` | v0.2a | — |
| c0068 | `v01-followups` | v0.2a | c0025, c0028, c0029, c0031 |
| c0069 | `layout-lens-complete` | v0.2b | c0019 |
| c0070 | `schematic-hierarchy-layout` | v0.2b | c0061, c0063 |
| c0071 | `rules-complete` | v0.2b | c0018, c0026, c0054 |
| c0072 | `schematic-board-parity` | v0.2b | c0062 |
| c0073 | `interfaces-quantities` | v0.2b | — |
| c0074 | `drawing-sheets-followups` | v0.2b | c0012, c0068 |
| c0075 | `standard-component-catalog` | dogfood gap: offline common symbols and footprints | c0008, c0058 |
| c0076 | `component-catalog-coverage` | expand offline symbols and standard package footprints across common families | c0055, c0056, c0075 |

| c0082 | `kicad-worksheet-oracle-isolation` | CI correction: isolated worksheet boundary oracle | — |
| c0083 | `altium-repeated-sheets` | v0.3 write | c0043 |
| c0084 | `altium-rule-lowering` | v0.3 write | c0038, c0042 |
| c0085 | `altium-pcb-complete` | v0.3 write | c0035, c0038 |
| c0086 | `altium-schematic-complete` | v0.3 write | c0032 |
| c0087 | `altium-outjob-sheet` | v0.3 write | c0042, c0046 |
| c0088 | `altium-light-drc` | v0.3 write | c0044, c0072 |
| c0089 | `equivalence-level-5` | v0.3 write | c0045 |
| c0090 | `altium-roundtrip-write` | v0.3 write | c0044 |
| c0091 | `altium-verification-kit` | v0.3 write | — |
| c0092 | `altium-write-graduation` | v0.3 write | c0091 |
| c0093 | `release-v0-2` | release of v0.2a and v0.2b as `0.2.0`: release record, guard, version | every v0.2a and v0.2b change |
| c0094 | `bom-dnp-grouping` | correction of v0.2a: a BOM line is all DNP or all fitted | c0064 |
| c0098 | `electrical-readiness` | v0.4 (the maintainer's decision of 2026-10-08): `fenolite ready`, one read-only reply on whether a KiCad project is electrically ready: open nets, KiCad's ERC and DRC, unconnected pins, power nets without a declared width or a zone, parts without a footprint or a value | c0062, c0108 |
| c0121 | `altium-component-bodies` | v0.3 follow-up: the component bodies that c0085 cut, fact rows first | c0085 |
| c0122 | `altium-zone-holes` | correction of v0.3: a zone fill keeps the holes of its poured region | c0043 |
| c0124 | `altium-plane-lines` | correction of v0.3: the Altium import makes no track of a line on an internal plane | c0043, c0088 |
| c0125 | `altium-clearance-scopes` | v0.3 follow-up: more forms of the Clearance record in the Altium rule table | c0084, c0088 |
| c0126 | `footprint-instance-graphics` | v0.3 write: the graphics and texts of a footprint instance and the corner ratio of a pad in the model; closes task 2.2 of c0090 | c0090, c0123 |
| c0127 | `altium-arc-record-values` | v0.3, follow-up (decision of 2026-10-06) | c0090 |
| c0128 | `altium-rewrite-via-drill` | v0.3, follow-up (decision of 2026-10-06) | c0090 |
| c0129 | reserved | v0.3 follow-up of c0121 and c0099: keep the model keys of a component body that was read | c0099, c0121 |
| c0130 | `altium-clearance-matrix-cells` | v0.3 follow-up: a Clearance matrix read as one rule per cell of item kinds | c0125 |
| c0131 | `altium-unit-slack-rule` | v0.3 follow-up: the slack of the copper check on Altium input as a stated rule | c0130 |
| c0132 | `altium-via-inner-pads` | correction of v0.3 (2026-10-07): a via whose record names layers without a pad shape is judged by its hole there | c0088, c0130, c0131 |
| c0133 | `release-0-2-1` | patch release `0.2.1`: the rule for patch releases of the series, the record, the guard, the version | c0093, c0135 |
| c0134 | `catalog-pin-text-legibility` | correction of v0.3: an authored symbol shows a pin name only where it can be read; a measured rule on every authored symbol, no writer changes | c0076, c0086 |
| c0135 | `altium-pin-map-backport` | correction of 0.1.0 and 0.2.0: an Altium build applies `pad_map` to the PCB document and writes it into the schematic | c0056, c0035 |
| c0136 | `milestone-renumbering` | names only: the write side of the second backend is v0.3 (released as `0.3.0`) and the proposals open on other branches form v0.4; no behaviour changes | — |
| c0138 | `altium-outjob-gerber-settings` | correction of v0.3: the Gerber output of a written output job carries the complete settings record, with the plotted layers from the board; fact rows first | c0087 |
| c0143 | `catalog-power-interface-library-case` | correction of 0.2.0 and 0.2.1: a design with catalog parts and a `Power` interface builds for KiCad, the power flag in the catalog's library | c0061, c0075 |
| c0146 | `altium-schematic-fonts-and-part-r` | correction of v0.3 (found in Altium Designer 26 on 2026-10-07): the font table of a written schematic holds each distinct font once; the authored `Repeat` sample is written by the schematic writer | c0087, c0083, c0086 |
| c0148 | `altium-pin-hide-bits` | correction of v0.3 (found in Altium Designer 26 on 2026-10-08): every written pin holds bit 0x20 of `PINCONGLOMERATE`, with 0x08 and 0x10 as show flags; the reader reads the two bits as hide flags on pins without 0x20 | c0032, c0034, c0040 |
| c0149 | `release-0-2-2` | patch release `0.2.2`: the record, the version | c0133, c0143 |
| c0150 | `release-0-3-0` | release of the write part of v0.3 as `0.3.0`: the release record with the verdict of the rule of c0092 per Altium write kind and the maintainer's exception for the kit, its guard, the version and the changelog cut; c0149 is the patch release `0.2.2` on its own branch, and c0151 and c0152 are proposed as the follow-ups the record names | c0083–c0092, c0121–c0148 |
| c0140 | `part-height-rules` | v0.4: part heights as bodies of their footprint, read by one function, and height limits over named rule areas judged by `check`, `place` and `build` | c0099, c0103, c0113 |
| c0152 | `clearance-rounding` | follow-up of c0131 (Altium's rule check of 2026-10-08, S-0616): the copper check on Altium input lowers its clearance rules by Altium's observed tolerance, 3.5 file units in whole nanometres (9 nm), where that is above the unit's slack | c0131, c0132 |
| c0153 | `kicad-cli-per-worker` | correction (two transient failures of the kicad-9 job on 2026-10-08): every `kicad-cli` run gets private temporary, runtime, cache and state folders, so parallel runs share no instance lock file | c0009, c0082 |
| c0154 | `release-0-4-0` | release of v0.4 as `0.4.0`: the release record with the verdict per change, what is deferred to the next release by the maintainer's decision of 2026-10-08 and the follow-ups found that day, its guard, the version and the changelog cut | c0077–c0081, c0096–c0120, c0137, c0140, c0141, c0145, c0152, c0153 |
| c0155 | `altium-bodies-default` | the maintainer's decision of 2026-10-09: an Altium build writes the extruded component bodies by default (`--altium-bodies extruded`; `off` turns it off) | c0121 |
| c0156 | `kicad-cli-docker-user` | correction of c0015 and c0153 (two agents running as root on 2026-10-09): a `docker:<image>` run of `kicad-cli` runs the container as the owner of the run folder, with `HOME` in its state folder, so it can write that folder for any host user | c0015, c0153 |
| c0157 | `yardstick-route-order` | the maintainer's decision of 2026-10-09 (the routing gap of nightly run 37836196244): the yardstick runner runs `route` (Freerouting) before `route-pairs` (KiCadRoutingTools) until the pair is routed as a coupled pair; measured again then | c0119 |
| c0158 | `equivalent-public` | v0.5a: the public `equivalent`: `fenolite.api.equivalent`, the result schema `fenolite.equivalent.v0`, a KiCad schematic as a side, an equal-sized oval equal to a circle | c0045, c0089 |
| c0159 | `convert-command` | v0.5a: `fenolite convert`, the conversion report and its verification by `equivalent`; KiCad to Altium and KiCad to KiCad with today's writers | c0158, c0090 |
| c0160 | `convert-to-altium` | v0.5a: KiCad to Altium without the measured losses; the derived PCB library and the tolerant schematic write that the decisions of 2026-10-06 put in v0.5a | c0159, c0126 |
| c0161 | `convert-to-kicad` | v0.5a: Altium to KiCad, with the refusal of items on layers a KiCad board does not declare | c0159, c0043 |
| c0162 | `kicad-downgrade` | v0.5a: the controlled KiCad downgrade (capability resolver) through `fenolite convert` | c0159, c0007 |
| c0163 | `opaque-net-stored-name` | correction (found while c0162 was written; the maintainer's decision of 2026-10-09): a numbered net reference inside opaque content resolves to the stored name of its net, so a board whose teardrops are on a net stored with `{slash}` (`RoyalBlue54L-Feather`) is written for its own target 9 instead of refused, and named rightly for 10 | c0017, c0061 |
| c0164 | `altium-schematic-layout` | native schematic layout capture through Altium sync, byte-exact replay and conservative source conflicts | c0032, c0040, c0043, c0069 |
| c0164 | `native-altium-template` | duplicate id (found at the 2026-10-15 merge of `dev` into `codex/c0161-c0092-integration`): both branches archived a c0164 on 2026-10-12; this one, archived as `archive/2026-10-12-c0164-native-altium-template`, applies a native binary `.SchDot` sheet template to every generated Altium schematic (`build --altium-template`); dev's c0164 is `altium-schematic-layout` above. Both archived folders are kept unchanged; the maintainer decides the renumbering | c0046 |
| c0165 | `schematic-block-composition` | archived implementation: functional blocks, automatic flow/alignment, bounded wiring and generated-baseline reports/previews; repository gate and native GUI review pending (see archived tasks) | c0164, c0032, c0037, c0086 |
| c0166 | `altium-native-acceptance` | the maintainer's authorization: consolidate the pending native Altium checks (0.2 line through c0160), run them on the licensed Windows PC, record the results and fix the defects found | c0091, c0092, c0160 |
| c0167 | `board-slots` | board slots and cut-outs (milestone to be placed): `OutlineSlot` in the model and `design.slot`, the shared stadium, the union of overlapping cut-outs and slots (`clipper` backend of the `geo` extra), KiCad lowering and read-back | c0102, c0074 |
| c0168 | `altium-slots-cutouts` | board slots and cut-outs: slotted board holes as free slot pads, milled cut-outs and slots as board cut-out regions behind the maintainer's kit, their import and round trips | c0167, c0085 |
| c0169 | `edge-clearance-check` | board slots and cut-outs: copper-to-edge clearance in the copper check, drilled holes in cut-outs and overlapping holes, the creepage of slots | c0167, c0029 |
| c0170 | `convert-slots-obstacles` | board slots and cut-outs: slots and cut-outs in conversions, slotted drills to Altium, generated hole footprints from Altium, slots as placement and routing obstacles | c0167, c0168, c0169, c0159–c0161 |
| c0171 | `release-0-5-0` | release of v0.5a as `0.5.0` with the slot changes c0167 and c0169 (the maintainer's approval of 2026-10-15): the release record with the verdict per change, what is pending on the CI of the release branch and what waits for the maintainer's own tests, its guard, the version, the changelog cut, and the retry of the corpus fetch that the `kicad-10` job needs; since the maintainer's decisions of 2026-10-16 also c0168, c0170, c0172 and c0173, with the release held for the native parts of c0172 and c0173 | c0092, c0155–c0170, c0172, c0173 |
| c0172 | `altium-draftsman` | native Altium Draftsman documents for `0.5.0` (the maintainer's request of 2026-10-16): the reader of `.PCBDwf` (an LZ4-chunked XML document) and its census, a writer behind `draftsman.NATIVE_WRITE` driven by c0117's drawing specification, `build --altium-draftsman` and `--drawing-spec`, the `PCBDrawing` output, kit Part F (F0, FP1 to FP5, F1 to F8); the release waits for its native document | c0087, c0101, c0117, c0138 |
| c0173 | `board-panels` | board panels for `0.5.0` (the maintainer's request of 2026-10-16): the panel script and model, `fenolite panel` with its checks, the KiCad panel board, the flattened Altium panel, the Embedded Board Array behind `pcbdoc.EMBEDDED_ARRAYS` and kit Part Q (Q1 to Q12), the score layer in Gerber exports; the release waits for its native array | c0167, c0118 |
| c0174 | `board-design-guide` | practice pages of the agent guide (board-practice to board-workflow), in `0.5.0` by the decision of 2026-10-25 | c0077 |
| c0175 | `board-engineering-tools` | the board engineering tools: proposed before `0.5.0`, implemented package by package in c0197–c0214, c0223–c0229 and c0241; in `0.6.0` with tasks 0.1, 10.4, 14.1 and 14.3 open | c0174 |
| c0176 | `board-viewer` | `fenolite view`: boards of every backend in 2D and 3D, the project tree, `--serve`, `--export` | c0007, c0043 |
| c0177 | `schematic-viewer` | Altium sheets in the viewer, the Navigator and cross-probing | c0176 |
| c0178 | `native-themes` | KiCad and Altium colours, a user's KiCad theme, KiCad sheets in the viewer | c0176, c0177 |
| c0179 | `libraries-and-units` | libraries, mm and mil, measurement in the viewer | c0176 |
| c0180 | `draftsman-viewer` | Draftsman drawings in the viewer | c0172, c0176 |
| c0181 | `altium-native-layers` | Altium layer names and mask openings in the viewer | c0176 |
| c0182 | `viewer-performance` | scene cache and compact scenes | c0176 |
| c0183 | `board-rule-areas` | keep-outs, dimensions and placement marks in the board view | c0176 |
| c0184 | `visual-diff` | `fenolite view --compare` | c0176 |
| c0185 | `project-nets` | project nets across sheets in the viewer | c0177 |
| c0186 | `variants-view` | assembly variants in the viewer | c0177 |
| c0187 | `review-panels` | filter, Find similar, Components and Nets panels | c0176 |
| c0188 | `check-overlay` | `fenolite view --check` | c0176 |
| c0189 | `review-tools` | edge measure, links, review marks, SVG and print | c0176 |
| c0190 | `documentation-views` | BOM documents, output jobs, Draftsman side views | c0180 |
| c0191 | `viewer-visual-tests` | visual and interaction tests of the viewer page | c0176 |
| c0192 | `guide-room` | a compact generated command page in the agent guide | c0079 |
| c0193 | `viewer-review` | review findings, measurement with snap and embedded 3D models in the viewer | c0176 |
| c0194 | `ci-push-scope` | CI on branch pushes but backups, never on a tag | — |
| c0195 | `mcp-server` | `fenolite mcp`: the commands as tools of an MCP server on stdio | c0079 |
| c0196 | `mcp-design-and-images` | `fenolite edit`, the opt-in `fenolite_edit` and PNG views as images in MCP replies | c0195 |
| c0197 | `router-input` | a board-wide preferred width and a one-sided clearance in the router's design file; `--order` with several globs (package 1 of c0175) | c0107, c0175 |
| c0198 | `ground-ties` | `analyze --kinds ties,domains`: a tie proved by removing its own copper, sense nets, isolation islands (package 2 of c0175) | c0108, c0114, c0175 |
| c0199 | `barrier-crossings` | `analyze --kinds crossings`: the free ways across a cut on each layer, the tracks they fit and the connections that must cross (package 3 of c0175) | c0108, c0175 |
| c0200 | `inferred-hypotheses` | every `INFERRED` evidence names a registered hypothesis, kept by a source test | — |
| c0201 | `file-safety` | `snapshot`, `publish` guarded by receipts, open-session warnings, online-only files, `refs --repoint` (package 9 of c0175) | c0175 |
| c0202 | `return-paths` | `analyze --kinds returns`: tracks across a gap of their plane, vias without a reference via | c0199 |
| c0203 | `fabrication-readback` | `export --readback`: the Gerber, drill and position files read back and compared with the board (task 12.1 of c0175) | c0175 |
| c0204 | `practice-checks` | `analyze --kinds decoupling,connectivity,bodies,relief,dead,coupling`: the copper states and the simulated pour, decoupling distances, copper under bodies, relief widths, dead copper and the coupling screen (package 7 of c0175) | c0175 |
| c0205 | `region-placement` | `place --strategy regions`: each domain of parts (isolation islands or `--group`) in its own region, barrier parts across the boundary, crossings counted | c0022, c0198 |
| c0206 | `python-api` | `fenolite.api.run`: every command in process with the envelope of `--json`; typed reads and analyses; `docs/api.md`, frozen for 1.0 | c0158 |
| c0207 | `diff-gates` | `diff --allow` gates a difference by kind, `diff --three-way` merges KiCad boards by item, Altium resave records left out (task 4.6 of c0175) | c0175 |
| c0208 | `copper-tidy` | `fenolite tidy`: prune dangling copper and chamfer right-angle joints, each edit checked for groups and clearance, `--drc` (package 5 of c0175) | c0175 |
| c0209 | `drc-trials` | `check --exclude` writes a KiCad DRC exclusion in both item orders; `fenolite.api.trial` judges an edit by DRC and gates its items (tasks 12.2 and 12.3 of c0175) | c0175 |
| c0210 | `layout-reuse` | `place --strategy reuse` (`--from`): a block of a reference board copied by a rigid fit over its pads, with `--copper` its tracks and vias pruned and checked, `--drc` (package 4 of c0175) | c0175 |
| c0211 | `region-renders` | `render --region`: one rectangle of the board drawn by Fenolite from the model with net labels, open connections, zones in their state, a grid in board millimetres and a `--cut` overlay of the crossing analysis (task 12.4 of c0175) | c0175 |
| c0212 | `assembly-marks` | `fenolite silk --designators`: text ink measured with `kicad-cli` (glyph-table estimate without it), designators placed clear of pads, holes, silkscreen, courtyards and the edge, each one checked, `--drc` (tasks 9.1 and 9.2 of c0175) | c0175 |
| c0213 | `pour-shapes` | `analyze --kinds necks,loops,balance` and `power --split`: necks, tips and slivers of pours, declared loop areas, the copper of two-pad parts, the share of the current of each path and via (rest of package 7 of c0175) | c0175, c0204 |
| c0214 | `copper-tidy` | `tidy --straighten`: runs on the 0/45/90° lattice by turn costs; T-joint and `--zones` chamfers; `tidy --report --compare`, the style report (tasks 7.2 to 7.5 of c0175) | c0175, c0208 |
| c0215 | `altium-repour` | the maintainer's decision of 2026-10-26 (roadmap, "Open decisions", row 48): Fenolite pours the polygons it writes into a `.PcbDoc` with Altium's rules and algorithm and writes the regions, compared with Altium's own repour in kit group K6 and on the public corpus; supersedes row 23 of c0085 | c0085, c0122, c0130 |
| c0216 | `contract-v1` | v1.0 freeze: the CLI surface written and judged (with `fenolite.dsl` and `fenolite.api`), envelope and error `v1` behind one constant, deprecation, the maintainer's pre-freeze review | — |
| c0217 | `result-schemas-v1` | v1.0 freeze: a result schema for every command and schemas of the public file formats (roadmap, "Open decisions", row 14) | c0216 |
| c0218 | `model-schema-1-0` | v1.0 freeze: model schema version `1.0`, migrators from every `0.x` release, `fenolite migrate`, the pre-freeze review of the model | — |
| c0219 | `conformance-matrix` | v1.0 freeze: format versions in the evidence matrix, the published conformance matrix, the evidence rules on every reply | c0200, c0216 |
| c0220 | `legal-history-1-0` | v1.0 freeze: the residue scan over the whole history in the release and the nightly, the licence inventory, the legal review record | — |
| c0221 | `release-automation` | a pushed tag runs the release: checks, build, PyPI and the GitHub Release with notes and checksums | c0154, c0171 |
| c0222 | `net-roles` | the maintainer's request of 2026-10-28: phase 0 of a router that works from electrical intent. Net roles inferred from parts and topology and confirmed by the user, stored in the model; their checks fed to the analyses of `dev` (c0213 loops, necks and split, power paths, distances, returns, coupling, sense nets) and judged against role limits from public sources, plus the Kelvin and gate-return attachments; three authored reference boards; phases 1 to 4 planned on c0224, c0228, c0225 and c0208 (revised on 2026-10-29 on `1559f1b0`) | c0175, c0202, c0204, c0213, c0224, c0228 |
| c0223 | `library-fidelity` | imported pads get their mask and paste layers and margins, embedded Altium models extracted and placed in the derived library, `fenolite library --diff` (tasks 10.1 to 10.3 of c0175) | c0175, c0193 |
| c0224 | `generated-copper` | `Design.band`, `keepout_ring`, `barrier`, `body_keepout`, `fanout_zone` and `stitch_pieces`: zones, rule areas and vias generated by the build after placement (package 6 of c0175) | c0028, c0175 |
| c0225 | `drc-gate` | `route --gate drc` and `tidy --gate drc`: the edit judged through `fenolite.api.trial(..., gate=True)`, the items that bring new DRC findings dropped and reported (the rest of task 12.2 of c0175) | c0175, c0209 |
| c0226 | `silk-clip` | `fenolite silk --clip`: silkscreen strokes of the board and of its footprints cut at mask openings and pad holes with the project's silkscreen margin, each piece checked, footprints cut alike so `fenolite library` stays in step (task 9.3 of c0175) | c0175, c0212, c0223 |
| c0227 | `layout-reuse` | pads paired by net partition in the fit, zones of a copied block (an outline rebuilt from its fill), and `place --turn`, `--shift` and `--pose-search`: a group moved rigidly with its copper (tasks 8.4 to 8.6 of c0175) | c0175, c0210 |
| c0228 | `octilinear-router` | `route --router octilinear`: a built-in router of short connections in 0°, 45° and 90° segments, five shapes per connection in clearance, rounds that put failed connections first, pairs at their gap, each result judged by the copper check (task 7.6 of c0175) | c0175, c0225 |
| c0229 | `assembly-test-features` | `fenolite testpoints --place`: a probe of `design.test_point` and its track for each net a side does not reach, on a grid site clear of copper, holes, edge, courtyards and silkscreen, checked before write, kept by a rebuild as a board-only footprint (task 9.4 of c0175) | c0118, c0175, c0212 |
| c0241 | `altium-edit-sessions` | edit sessions of Altium documents: hypotheses `H-A-EDIT-*` and `H-A-INTEG-*` and kit Part J measured first, then `fenolite check --stages altium.integrity`, typed and asserted edits with index upkeep and commit gates, each operation gated by its kit case (package 12 of c0175) | c0175, c0092, c0207 |
| c0242 | `release-0-6-0` | release of what `dev` implemented after `0.5.0` as `0.6.0` (the maintainer's decision of 2026-10-29, which holds the v1.0 freeze c0216–c0220): the record `docs/release/v0.6.md` with the verdict per change and the maintainer's tests deferred to v0.7, its guard, the version, the changelog cut, the README, the roadmap (v0.7 to be scoped, v1.0 held) | c0171, c0221 |
| c0243 | `role-copper` | phase 1 of the router that works from electrical intent (c0222's plan): power, switch-node, ground and high-voltage copper generated from the confirmed net roles, sized by current, with per-role pad connections, ground stitching, via arrays by current, keep-outs at the user's distances and pour-free corridors left for phase 2; `design.role_copper()` and `fenolite copper`; generated copper carried to Altium through the in-memory KiCad build; verified by `roles.rules` on the reference boards | c0222, c0224, c0215, c0225 |
| c0244 | `critical-routes` | phase 2 of the router from net roles: `route --router octilinear --roles critical` routes, before any general router and before the power copper, the open connections of confirmed gate loops (the return from the source or Kelvin-source pad, beside the drive, else stacked) and Kelvin pairs (from the inner half of the shunt pads, isolated from power copper and kept off switching copper), judged by `roles.rules` and the DRC gate, locked and fenced by `role.corridor.<group>.<net>` pour keep-outs, every unrouted group reported with a reason and a proposal; the hot loop is phase 1's; Altium output through `convert` | c0222, c0228, c0225, c0243 |

The id c0164 is held by two archived changes (the two c0164 rows of the table). c0215 was written on `dev` as c0196 before PR #20 took that id, then as c0204 before the branch `dev-c0204-c0209` took c0204 to c0209; the five changes of the v1.0 freeze were written as c0198 to c0202 before c0197 to c0203 took those, then as c0205 to c0209. All six were renumbered on 2026-10-28. c0210 to c0214 and c0223 to c0229 were archived on 2026-10-28 with c0204 to c0209; c0223 and c0224 had been written as c0215 (`library-fidelity`) and c0216 (`generated-copper`) on the branch `dev-c0213-c0216`, and c0222 is held by the branch `c0222-net-roles`. The release of `1.0.0` takes a change of its own when it is cut, as `0.5.0` took c0171. Consult the current audit allocation below before choosing another ID. c0241 is `altium-edit-sessions` (package 12 of c0175, 2026-10-29). c0242 is `release-0-6-0` (2026-10-29). c0243 is `role-copper` (phase 1 of c0222's plan) and c0244 is `critical-routes` (phase 2, written in parallel), both 2026-10-29. New changes start at c0245.

Older planning text that says `tokens.yaml` means the token inventory `src/fenolite/backends/kicad/data/tokens.toml`.

## Audit batch allocation — updated 2026-10-29

The maintainer authorized consolidation of these nine changes on current dev, full CI, archival, and a single squash into dev. Prior allocation and proof records remain in each change.

All nine are archived under `changes/archive/2026-10-28-c0232-*` through `2026-10-28-c0240-*` after the implementation CI passed; OpenSpec uses a UTC archive date. Their final revision must pass its own CI before dev advances. The integration proof is in `docs/evidence/adoption-reliability-integration.md`.

| id | change | prior draft ID |
|---|---|---|
| c0232 | `snapshot-consistency` | c0223; c0210, originally c0205 |
| c0233 | `viewer-review-reliability` | c0224; c0211, originally c0206 |
| c0234 | `catalog-visual-browser` | c0225; c0212 |
| c0235 | `viewer-navigation-consistency` | c0226; c0213 |
| c0236 | `documentation-reconciliation` | c0227; c0215, originally c0207 |
| c0237 | `public-presentation` | c0228; c0216, earlier c0208/c0197 |
| c0238 | `write-recovery` | c0229; c0217, earlier c0209/c0204 |
| c0239 | `project-review-status` | c0230; c0218 |
| c0240 | `catalog-selection` | c0231; c0219 |

Fetched refs already reserve c0210-layout-reuse, c0211-region-renders and c0212-assembly-marks; another agent holds c0214. Current dev's c0215–c0221 and remote c0222-net-roles are preserved. A final fetch also found c0223-library-fidelity, c0224-generated-copper and c0225–c0229 (drc-gate, silk-clip, reuse-moves, octilinear-router and testpoint-place) on other agents' branches. Only this batch moved to c0232–c0240. Its implementation CI passed all 13 jobs on 8c2fa270 under the earlier c0223–c0231 identities; those proof records remain aliases. The final archived revision requires its own CI before dev advances. The next free number in these inspected refs is c0241; fetch and inspect active/archive changes before allocating it. Earlier committed collisions remain identified by full slug and commit, including the two archived c0164 changes.
