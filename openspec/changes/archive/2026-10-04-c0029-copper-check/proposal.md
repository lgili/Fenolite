## Why

A dogfood build of a buck converter through Fenolite's public API wrote a GND via touching a VIN track. KiCad loaded the via on VIN silently, its DRC reported no short (only `via_dangling`), and a board KiCad saved afterwards carried the via on VIN. This is reported, not verified (`H-K-VIA-RENET`). c0013 and c0020 judge copper only through KiCad's DRC, so a short that Fenolite itself writes can pass `check`. Fenolite needs its own exact short and clearance check, before writing and inside `check`.

## What Changes

- `geometry/thick.py`: a core (point, segment, polyline or filled ring) swept by a disc; exact touch and closer-than tests with integers and `Fraction` only.
- `checks/clearance.py`: the clearance in force for a pair on a layer: the governing `clearance` rule (c0018's `rule_order`), the net classes and the board minimum, combined as c0026 measures per major.
- `checks/copper.py`: `check_copper` over tracks, arcs, vias, board-frame pads (c0028), zone fills and zone outlines, with c0005's STR index. Each finding names the layer, a point and both items.
- `backends/base.py`: `DesignRules` and the `DesignRulesSource` protocol. `backends/kicad/copperrules.py` applies the project's classes, assignments and floor (c0010) and the rules file (c0018) to a board.
- `check`: stage `copper.clearance` between `erc.lite` and `drc.kicad`, in the default set, without `kicad-cli`; six `copper.*` codes.
- `build`: a guard judges the triad that the build is about to write. `--copper-check refuse` (default: exit 5, nothing written) or `warn`.
- Probes on 9.0.9 and 10.0.6: the re-net (IPC-D-356 via records, DRC JSON, 10.0 re-save), and parity canaries per item kind and clearance source.
- A measurement on the 21 readable demo boards; docs `docs/formats/kicad/copper.md` and `docs/evidence/copper-check.md`; hypotheses `H-K-VIA-RENET` (UNVERIFIED), `H-K-COPPER-SHAPES`, `H-K-COPPER-RESOLVE`, `H-K-COPPER-ZONES`.

Budget: 12 days, with a cut order (design, "Budget").

## Capabilities

### New Capabilities
- `copper-check`: copper items, clearance in force, findings, zone overlaps, supported cases, evidence and performance.

### Modified Capabilities
- `verification-loop`: ADDED the copper stage and its codes; MODIFIED c0020's "Stages added for findings and round trips" (stage order).
- `design-dsl`: ADDED the build's copper guard.
- `backend-protocol`: ADDED the design rules source.
- `geometry-kernel`: ADDED thick shapes and exact gaps.
- `kicad-file-backend`: ADDED design rules for the copper check.
- `kicad-oracle`: ADDED the via re-net probe and the copper parity canaries.

## Non-goals

- Full DRC parity. Hole, edge, mask, silkscreen and courtyard checks; placement legality (c0022).
- Zone fill computation (c0015); typed zone settings (c0031); routing (c0016).
- The zone's own clearance in the copper check: a v0.2a follow-up to c0029.
- Net-tie pad groups, unused-layer removal on vias and pads, graphics and texts on copper layers.
- KiCad project severity overrides and DRC exclusions.
- A `package-layering` change; model, schema or FEN-code changes.

## Evidence level required

- Thick-shape gaps: mechanical (exact unit and property tests against `Fraction` brute force).
- Clearance in force and verdicts on canaries: `KICAD-VERIFIED` on 9.0.9 and 10.0.6 (`H-K-COPPER-RESOLVE`, `H-K-COPPER-SHAPES`); zone fills on 10.0.6 (`H-K-COPPER-ZONES`).
- Stage and guard: the lowest of the board reader's `INFERRED` (`H-K-PCB-READ`), the project and rules readers, c0028's frame and `copper.EVIDENCE`; `UNVERIFIED` when a clearance rule stayed opaque or an item was not checked.
- Re-net: `H-K-VIA-RENET` recorded per major. The guard does not depend on its outcome.

## Impact

- New `geometry/thick.py`, `checks/clearance.py`, `checks/copper.py`, `backends/kicad/copperrules.py`. Extended `backends/base.py`, `backends/kicad/backend.py`, `checks/stages.py`, `checks/codes.py`, `cli/cmd_check.py`, `cli/cmd_build.py`.
- No `package-layering` change: the guard lives in `cli`, and `checks` reaches KiCad only through injected protocols.
- Depends on c0013 and c0020 (archived first, for the MODIFIED delta), c0028 (pads), c0026 (rule, class and minimum tables), c0010, c0011 and c0019.
