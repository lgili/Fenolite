## Why

Stage 1 of the enclosure line (`docs/research/enclosures.md`, sections 5.3, 8 and 9). c0308 derives a board
from a box and records the fit, but the board then changes: parts move, a connector is swapped, the outline
is trimmed, a taller capacitor arrives. Without a check, the first sign of a wrong fit is a board that does
not close in its box. The research's 2D and 2.5D levels need no 3D kernel: the outline against the usable
area, holes against bosses, courtyards against boss envelopes, part heights against zones, and apertures
against the flat panel of their faces.

## What Changes

- **A new check stage, `enclosure.fit`,** after `placement.rules` and before `roles.rules`, in both check
  pipelines. It reads the fit record `.fenolite/enclosure.json` (c0308), or the record that
  `fenolite check --enclosure FILE` names for a native board, and is skipped with `no-enclosure`
  without one. Like `roles.rules`, `checks` receives the judge injected (`fenolite.enclosure.judge`) and
  stays free of the `enclosure` package.
- **2D findings:** outline outside the usable area (error) or smaller than it (info, with margins); a boss
  without a hole within tolerance (error); a hole drill that does not suit the screw (warning); a
  courtyard over a boss or screw-head envelope (error); a generated zone area missing (warning).
- **2.5D findings:** a part taller than its zone's limit, top and bottom (error); a face part too far from
  its wall or reaching into it beyond `protrude` (error); an aperture outside its face's flat rectangle
  (error); a web between apertures or to the rectangle's edge below the minimum (warning); a board
  thickness that differs from the record's or from a guide's range (error).
- **Heights from bodies, then from 3D models.** A part's height is `outward_height` (bodies). Without a
  known body, a conservative top is read from its STEP model's points, circles and spheres
  (`fenolite.enclosure.bounds`, stdlib, no kernel). A model top can prove a fit, never a failure:
  above the limit it is `enclosure.height-unproved` (warning). A part with neither is
  `enclosure.height-unknown` (warning), never a pass.
- **First-board warning.** A box with no field measured from a sample or a local STEP gives
  `enclosure.model-unverified` (warning). The stage's evidence is the lower of its own and the box's
  weakest field.
- **Build guard.** `build`'s placement guard runs the same judge and reports at most warnings.
- **Codes** in `checks/codes.py`, `explain.toml` and `docs/cli-contract.md`; `check.enclosure-unreadable`
  for a broken record.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `verification-loop`: ADDED "Enclosure fit stage" and "Enclosure fit issue codes".
- `enclosure-fit`: ADDED "Enclosure judge", "Heights for the enclosure judge", "Conservative model top"
  and "Enclosure judge in the build guard".

## Non-goals

- No 3D interference, no gmsh, no fit model STEP (stage 3, Decided).
- No vendor STEP read by CI; a user's local comparison is a later opt-in that stores only results.
- No automatic fix: findings carry hints, nothing moves.
- No through-hole lead protrusion below the board (open question).

## Evidence level required

- The stage: `INFERRED` (`H-G-ENCL-FIT-CHECK`, seeded good and bad fixtures), combined with the box's
  weakest field (never above `INFERRED` in v0).
- Model tops: `INFERRED` until `H-K-ENCL-MODEL-TOP` is measured against KiCad's VRML export of the same
  models (`ORACLE-VERIFIED(kicad-cli)` for the measured set).

## Impact

- New: `src/fenolite/checks/enclosure.py`, `src/fenolite/enclosure/judge.py`,
  `src/fenolite/enclosure/bounds.py`, fixtures under `tests/data/enclosure/fit/`, tests under
  `tests/unit/checks/`, `tests/unit/enclosure/`, `tests/kicad/enclosure/`.
- Changed: `checks/stages.py`, `checks/codes.py`, `cli/cmd_check.py` (`--enclosure`, the judge, model
  tops), `cli/cmd_build.py` (guard), `explain.toml`, `docs/cli-contract.md`, `docs/enclosures.md`,
  `docs/formats/step/`, agent guide (`checks.md`), registers, `openspec/README.md`, `CHANGELOG.md`.
- Sources: S-0954 and S-0959 (STEP entities), S-0960 (B-spline control-point bounds).
- Depends on c0307 and c0308.
- Size: about 6 design-days.
