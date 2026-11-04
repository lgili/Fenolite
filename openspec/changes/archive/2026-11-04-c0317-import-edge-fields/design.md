## Context

The actual strict census on signed `613b6f1b98e1780bb04442afc0f3dbd883b5e644` failed 22 cases and
skipped two heavy inputs. Six are `FEN-7001` import refusals of the same `outline-width` kind:

| row | root items counted by refusal | shape classes |
|---|---:|---|
| kicad-demo-10-0-6-pcb-02 | 4 | lines |
| kicad-demo-10-0-6-pcb-05 | 9 | lines |
| kicad-demo-10-0-6-pcb-08 | 4 | lines |
| kicad-demo-10-0-6-pcb-09 | 4 | lines |
| kicad-demo-10-0-6-pcb-14 | 17 | lines and arcs |
| kicad-demo-9-0-9-1-pcb-01 | 4 | lines |

These are six observations, not six omission classes. Read-only inspection of the SHA-declared cache
confirms one root stroke width per board. No upstream geometry or values become authored test data.
c0277's board-item and footprint-closed-outline requirements cover import preservation; c0278's
level-7 geometry and strict round-trip requirements cover the fidelity result. c0281 correctly reports
the old unsupported width. This change replaces that limitation only when one width is representable.

## Decisions — Decided 2026-11-01

The user delegated recommended implementation decisions. Use one optional uniform outline width,
which covers every observed refusal without inventing a per-edge styling system. A mixed-width source
continues to be reported and refused. A public DSL field is preferable to a post-import text rewrite:
the reviewed script itself must rebuild the preserved native strokes.

`Design.board(..., outline_width=None)` accepts a nonnegative DSL length or `None`. Store it as
`Design.outline_width` and `Outline.stroke_width`, default `None`; default canonical JSON and native
bytes remain unchanged. Zero is an explicit zero width. The setting applies to all generated root
edges, including cut-outs and slots. Footprint edges keep their vendored widths and remain omitted
from duplicate generated root edges as before. Native outline signatures retain their geometry rule.
When an explicit width differs on an otherwise equal existing outline, it is a script-owned outline
change and follows the existing signed/locked replacement policy. A declaration with no explicit width
keeps the old geometry-only equality behavior. This prevents a changed explicit argument being ignored
on a rebuild while retaining the existing policy for a hand-edited outline's geometry.

The importer reads root edge graphics. A single nonnegative width is emitted as `outline_width=`
only when different from the existing default. Multiple widths or a negative width retain the existing
`outline-width` ledger findings; `layer-table` and other losses keep their existing decisions. It must
not remove a finding before the writer has a concrete representation of that content.

## Modules and public API

- `dsl/design.py`, `dsl/convert.py`: `Design.board(..., outline_width=...)` and conversion metadata.
- `model/board.py`: optional `Outline.stroke_width`; generated model schema follows the dataclass.
- `backends/kicad/pcb.py`: generated root line/arc strokes use the optional width, else `OUTLINE_WIDTH`.
- `backends/kicad/outline.py`: explicit width participates in equality before the existing lens decision.
- `importer/emit/design.py`: choose the uniform width and emit it; keep unsupported-width accounting.
- `tests/unit/dsl/test_outline_width.py`, `tests/unit/importer/test_outline_width.py`: authored runtime
  fixtures based only on Fenolite's declared CC0 fixtures, plus explicit strict negative controls.
- Existing DSL/import docs and a tested agent-guide line teach the new argument.

The schematic worker owns source symbol extraction, aliases, powers and per-unit poses. Its future
`source_drawing(..., symbol_defaults=vendored.symbols)` call is independent and must be preserved.

## Validation and limits

Authored tests cover lines, arcs, cut-outs, zero width, footprint-closed outlines, mixed-width refusal,
layer-table refusal, integer validation, repeated deterministic output and absent/default canonical
metadata. Existing example digest checks establish unchanged default bytes. Strict authored project
round trips must compare every available level without tolerances or acceptance. Native application
and full/exact CI proofs remain separate. Historical `observed.json`, ratchets and counts are not edited.

The exact signed source checkpoint is `888ca838fa41b1b9bc16e4039ec55e233400b1e5`. Its scoped six-row
strict measurement still fails six cases (232.69s), after removing the width refusals: one repeated-sheet
footprint-variant build refusal and five unequal comparisons. The value-free results are recorded in
`docs/evidence/fidelity.md` beside the untouched historical census. Current raw-board emission metadata
must be remeasured independently with the existing tool; it is not a full conversion verdict.
That remeasurement completed all 18 rows, including heavy 06/18, on the same signed source. All item
counts and declared input hashes remain unchanged; 12 rows remove only the represented width finding.
The metadata/actual raw-row check passes (6), while the scoped all-level failures above remain unaccepted.
