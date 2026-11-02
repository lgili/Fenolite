# Validation — 2026-11-02

The signed implementation checkpoint is
`fbec5cd9e711cc9b50f9b8d393ab8bb1cda48556`, directly based on published
`697cdf02b39c570b7827bd2b7b5419dfcf6bdea6`. Its source stayed fixed throughout the
measurements. No persisted model/dataclass/schema fields, runtime dependencies,
lock file or existing build-byte entries changed.

The representation/undeclared-layer proof passes 23 cases, alongside 64 import
layering contracts (87 total). Nineteen strict importer/outline/equivalence cases
pass, including the authored short-table project's all-nine-level equality with
no accepted differences. Repeated imports and builds agree. Unknown row names,
User.n gaps, absent Edge.Cuts, mixed widths and referenced omitted layers retain
strict refusals. Modeled image references are non-droppable even with a lossy
write request. All 93 guide checks and all 76 existing build-byte guards pass.
Source typing, style, generated guide/schema, residue and strict OpenSpec checks
pass; no native application result is inferred from these authored proofs.

## Current source emission

The existing production-reader/full-emitter measurement tool actually processed
all 18 declared public board inputs, including heavy rows 06 and 18. The stored
observation binds the signed source, tool SHA-256, input SHA-256 and observation
hashes. Only row `kicad-demo-10-0-6-pcb-07` changes: its two layer-table findings
become none. Every input hash and source-item count remains unchanged.

Collection SHA-256:
`c40ba136c8ee4da2d3c3a0fe25cbc1e4d43f857f19860329fcf89db5330c41fd`.

These are emission-only observations. They do not repeat or replace historical
full conversions, equivalence verdicts, elapsed conversion times or native byte
measurements. The historical conversion table retains SHA-256
`63b107b962134bcde1ab8c032128bb7c5361d2e53c6c705b6ab110aaa38422f1`.
Eight focused guards pass: authored complete-CLI agreements, no-rebuild negative,
observation hashes/input bindings, historical-table identity, public row-03/07
complete-CLI agreements and the original row-03 full-conversion assertion. Full
corpus conversions remain the independent exact-head CI proof.

## Actual strict public project replay

The cached kit-dev-coldfire-xilinx_5213 project's board input SHA-256 is
`392cf6bf4b9b62beb435f965ccd7671a46decb17f947b74bfde482acd2132a5e`.
A fresh scratch copy was replayed with the existing strict import/build/all-level
helper, without lossy, acceptance, tolerance or level-subset flags. The import
self-check now passes the former layer-table gate but refuses with exit 5,
FEN-5001 and one import.unequal finding from the written schematic's pin
partition. That finding reports one pin difference and 51 more. This is an
import-stage refusal, not an unequal completed all-level comparison.

The measured attempt took 27.193 seconds. Both the original five-file input set
and the copied original retain their exact byte hashes. No converted code was
written; explicit build and all-level verification could not be reached. The
schematic resolver owner received the external negative control. Task 3.1 stays
open; no source content, geometry, acceptance or ratchet baseline was added.

Root owns the serial combined gate and required exact published-head CI. Neither
those gates nor native Altium/application acceptance is claimed here.

## Completed explicit replay on the integrated source

The later signed source `ea762411cbb24bc5f9ba5a16d8b372ae7c720568` includes the
drawn-bus prerequisite. A new scratch replay on that exact clean source reaches
the explicit build and full verification; it does not overwrite the earlier
`fbec5cd9` refusal recorded above. All five original native file hashes, including
the board SHA-256 already listed, remain unchanged in both cached and copied
inputs. No third-party CAD or derived script is added to this repository.

| Actual phase | CLI exit | Seconds | Observed result |
| --- | --- | --- | --- |
| Strict import dry run | 0 | 28.366 | Self-check equal; no unexpressed items; 113 new planned files. |
| Reviewed import confirmation | 0 | 1.799 | All 113 files match their reviewed SHA-256 values. |
| Separate explicit build dry run | 0 | 18.309 | 119 new planned files; no error finding. |
| Reviewed build confirmation | 0 | 2.175 | All 119 files match their reviewed SHA-256 values. |
| Full verify-source | 5 | 60.280 | Levels 1-7 and S equal; three level-8 render-pixels findings; zero acceptances. |

Actual CLI arguments below are relative to a fresh scratch folder. `PLAN_IMPORT`
and `PLAN_BUILD` stand for the recorded, reviewed ids; they are not a request to
recompute either operation at confirmation.

```sh
fenolite import upstream/demos/kit-dev-coldfire-xilinx_5213/kit-dev-coldfire-xilinx_5213.kicad_pro --to python --out out --licence CC-BY-SA-4.0 --source https://gitlab.com/kicad/code/kicad/-/tree/97acc80c223d75520c03fc44cab63cd9a3202c42/demos/kit-dev-coldfire-xilinx_5213 --revision 97acc80c223d75520c03fc44cab63cd9a3202c42 --timestamp 2026-10-31T00:00:00Z --dry-run --json
fenolite import upstream/demos/kit-dev-coldfire-xilinx_5213/kit-dev-coldfire-xilinx_5213.kicad_pro --to python --out out --licence CC-BY-SA-4.0 --source https://gitlab.com/kicad/code/kicad/-/tree/97acc80c223d75520c03fc44cab63cd9a3202c42/demos/kit-dev-coldfire-xilinx_5213 --revision 97acc80c223d75520c03fc44cab63cd9a3202c42 --timestamp 2026-10-31T00:00:00Z --confirm --plan PLAN_IMPORT --json
fenolite build out/design.py --out built --lock build.lock --kicad-version 9 --seed 0 --timestamp 2026-11-02T00:00:00Z --dry-run --json
fenolite build out/design.py --out built --lock build.lock --kicad-version 9 --seed 0 --timestamp 2026-11-02T00:00:00Z --confirm --plan PLAN_BUILD --json
fenolite verify-source out/design.py --against upstream/demos/kit-dev-coldfire-xilinx_5213/kit-dev-coldfire-xilinx_5213.kicad_pro --provenance out/PROVENANCE.json --timestamp 2026-11-02T00:00:00Z --json
```

The external `c0324-ea-replay/PROOF.json` receipt has SHA-256
`65953af83b4f0b7e5866073fb83634794afeba9f05a9c7981ff0b8a2d347124f`.
It binds the actual source, raw replies, input invariants, complete argument
lists, all five CLI exits and the reviewed file hashes. The source stayed clean
before and after execution. Normal Python bytecode behavior was used.

Copy provenance selects the existing default copper mode `warn`; no override
flag was passed. The guard ran and reports zero shorts, clearance and
edge-clearance findings. The build retains four pad-without-pin notices, one
text-unchecked notice, 132 drawn-net naming notices, one class-shadowed notice
and six outside-outline notices. The import retains 67 footprint-variant
notices, one sheet-renamed notice and one provenance-missing notice; no upstream
copyright holder was invented. Full verification retains two unjudged-routing
notices. None of these is silently treated as native application approval.

The overall full-fidelity command still fails at presentation on all three
schematic sheets. Hidden-reference summary text is not a measured explanation
of the differing pixels. Font preservation and any other presentation findings
remain separate work, with no changed acceptance or mask threshold. Task 3.1's
actual replay is proved; task 3.2 and full fidelity remain open. The successful
local fast gate on this source does not establish successful required CI.
