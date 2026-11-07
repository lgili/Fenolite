## Why

The strict conversion of the public kit-dev-coldfire-xilinx_5213 project refuses
exactly two layer-table items: its source omits Eco1.User and Eco2.User, while
Fenolite unconditionally adds those rows. The existing Board.layers model and
native writer already represent the exact table. A reviewed script needs to
express that table instead of requiring an accepted loss.

## What changes

- Add optional Design.board(..., technical_layers=None), a closed set of known
  non-copper layer names. None preserves every existing default.
- Carry explicit technical rows through existing Board.layers; add no persisted
  model/dataclass fields, schema fields or runtime dependencies.
- Emit the option only for supported source tables differing from the default.
- Refuse undeclared layer references, retain exact layer-table equivalence and
  unrelated strict import findings, and teach the option on a focused guide page.

## Non-goals

No new copper/user-layer API, arbitrary layer names, opaque technical metadata,
comparator normalization, lossy allowance, accepted differences, corpus baseline
updates, native GUI acceptance or changes to ordinary board bytes.

## Evidence

Use existing S-0001/S-0021 canonical names and layer-row forms, and the created
row observations already recorded in docs/formats/kicad/board.md. Authored fixture
variations use only declared Fenolite CC0 inputs. Public cached project geometry
remains outside core. Report actual command results and remaining fidelity
limits without promoting application acceptance.
