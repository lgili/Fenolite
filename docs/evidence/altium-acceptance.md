# Altium v0.3 acceptance

The authored acceptance tree is prepared and its local readback proofs passed on
2026-10-14. The complete KiCad-import acceptance and native acceptance of this new
project remain pending. No write kind graduates from these results. Evidence remains `INFERRED`: the
local results use Fenolite's own writers and readers, not the external importer.

## Project and scope

`examples/acceptance_v03/design.py` declares six copper layers, a two-level module
tree, three via kinds, board text, a keep-out, a polygon and all eight exact rule
kinds. All dimensions are Fenolite choices. The CC0 drawing sheet is an unchanged
copy of the shipped generic template, retaining its public provenance S-0077 and
S-0078.

The runner adds an authored ranged bus, a free non-plated hole and explicit
extruded bodies through the neutral model and existing writers. These are model
preparation steps, not additional DSL features. KiCad stores its free hole in an
anonymous footprint; Altium stores it as a free pad. Both written holes must be
one non-plated 2 mm drill within the committed triangle tolerance before the triangle's existing unnamed-reference policy
can exclude unpairable references. The Altium scope inventory reads the generated
project and typed keep-out records; it does not rely solely on its model cache.

## Local result, 2026-10-14

| step | result |
|---|---|
| Build KiCad target 10 with reviewed plan | passed |
| Build Altium binary module sheets with reviewed plan | passed |
| Required written scope | passed, all twelve criteria |
| KiCad model validation and same-version roundtrip | passed |
| Altium model validation and RT-A1 | passed |
| Altium project RT-A3 | passed |
| KiCad board versus Altium PCB document, level 5 | passed |
| KiCad importer versus the KiCad board, level 5 | pending CI |
| Probe `acceptance-v03` and frozen outcome | pending measured CI result |
| Native kit correspondence and publication | pending task 3.1 |

The focused acceptance tests passed (5 tests); fixture-manifest and hypothesis/provenance
checks passed (91 tests). The comparison uses the committed
`kicad-import` triangle profile; it adds no new tolerance or exclusion. The checks
above validate model and readback only: this intentionally sparse exercise board
is not a fully routed or DRC-clean production board. Copper short and clearance
acceptance are covered separately by the kit and the roadmap's planted controls.

Fenolite version: `0.5.0.dev0`. KiCad output target: `10`; no `kicad-cli` was
launched for the local proofs. Altium version and kit run id for this new project:
not measured. Existing native kit records are retained separately and are not
reported as a native run of this project.

## Reproduce and finish

Local preparation, into a new output folder:

```console
uv run python tools/acceptance_v03.py --out build/acceptance-v03-prepared --prepare-only
uv run pytest tests/unit/test_acceptance_v03.py -q
```

Full oracle acceptance runs in GitHub CI:

```console
uv run pytest tests/kicad/acceptance/test_v03_acceptance.py -q
```

`summary.json` records each stage, tool versions and an optional reported kit run
id. `acceptance_complete` remains false for preparation, a failed stage or an
exception. Raw command replies stay beside the generated files for diagnosis;
they are not committed, because receipts may contain local paths. An existing
output folder is refused so an earlier result cannot be overwritten. Task 2.1
remains open until the complete oracle proof, probe outcome and evidence update
pass. Archive still requires actual successful CI and the dependency order.
