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
| c0032 | `altium-schematic-writer` | v0.4, first item pulled forward | — |
| c0033 | `altium-binary-schematic` | follow-up | c0032 |
| c0034 | `altium-schlib-writer` | v0.4 item pulled forward | c0032 |
| c0035 | `altium-pcb-writers` | v0.4 items pulled forward | c0032 |
| c0036 | `no-connect-pins` | follow-up | c0032 |
| c0037 | `altium-hierarchy-harness` | v0.4 item pulled forward | c0032 |
| c0038 | `altium-pcb-copper` | v0.4 item pulled forward | c0035 |
| c0039 | `altium-compound-reader` | v0.3 | — |
| c0040 | `altium-schematic-reader` | v0.3 | — |
| c0041 | `altium-pcb-reader` | v0.3 | — |
| c0042 | `altium-project-reader` | v0.3 | — |
| c0043 | `altium-import` | v0.3 | — |
| c0044 | `altium-inspect-check-diff` | v0.3 | — |
| c0045 | `design-equivalence` | v0.3 | — |
| c0046 | `altium-sheet-template-import` | v0.3 | — |
| c0047 | `board-analyses` | v0.3 | — |
| c0048 | `altium-eco-clean` | v0.3 (Altium writer) | c0038 |
| c0049 | `test-speed` | v0.1 | — |
| c0050 | `transform-composition-bound` | v0.1 | — |
| c0051 | `drc-canary-repeatability` | v0.1 | — |
| c0052 | `release-hygiene` | v0.1 | — |
| c0053 | `altium-script-copper` | v0.1 (Altium writer) | c0038 |
| c0054 | `dsl-rule-constructor` | v0.1 | c0011 |
| c0055 | `dsl-footprint-authoring` | dogfood gap / v0.4 footprint generator | c0011, c0018 |
| c0056 | `dsl-pin-pad-map-slots` | dogfood gap / v0.4 footprint generator | c0055 |
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

Older planning text that says `tokens.yaml` means the token inventory `src/fenolite/backends/kicad/data/tokens.toml`.
