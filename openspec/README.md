# openspec

Spec-driven development with [OpenSpec](https://github.com/Fission-AI/OpenSpec).

- `specs/<capability>/spec.md` — the current, normative requirements (SHALL/MUST + scenarios).
- `changes/<id>/` — one proposed change: `proposal.md` (why), `design.md` (how), `specs/` (deltas),
  `tasks.md` (≤ 1-day tasks, each with the command that proves it).
- `config.yaml` — project context and artefact rules injected into every change.

No code lands without a change. Archive a change with `openspec archive <id>` once all tasks are done.

## Change ids

Changes c0001–c0010, c0014, c0017 and c0018 are archived under `changes/archive/`. Plan items keep their numbers (c0009–c0016);
split-offs and follow-ups take c0017 and later numbers in implementation order, and a new split-off
takes the next free number. Ids follow the form `cNNNN-<slug>`, a project convention (the `openspec`
CLI accepts any kebab-case name); lettered ids such as `c0009a` are not used. A slug may still change
until its change is proposed.

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

Older planning text that says `tokens.yaml` means the token inventory `src/fenolite/backends/kicad/data/tokens.toml`.
