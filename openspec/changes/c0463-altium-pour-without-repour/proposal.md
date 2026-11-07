# c0463: the computed pour is Altium's pour, with no Repour

## Why

`convert --to altium` pours by default (`--altium-pour computed`, c0215, c0436), but the pour is still
experimental:

- every computed pour carries `INFERRED`;
- `altium.zones-poured` tells the user to run "Tools » Polygon Pours » Repour All";
- any polygon the pour cannot prove keeps its outline only.

A document is not ready until someone opens Altium and repours it. Anything built on the pour then
rests on copper Altium may change: a check of the written document, the board view, a later edit.

On `cac/lote-29` the census of the 8 public rows (S-2210) refuses these, by reason:

| reason | count |
|---|---|
| `depends-on-refused` | 32 |
| `rule-scope` | 18 |
| `outline-arc` | 12 |
| `rule-unmapped` | 9 |
| `connect-scope` | 5 |
| `outline` | 2 |

- `rule-scope`, `rule-unmapped` and `connect-scope` go with c0462.
- `outline-arc` and `outline` are the pour's own.
- `depends-on-refused` follows from the others.

Every polygon the census pours passes M1 against the regions the document saves.

The maintainer's own board shows the same picture (counts only, S-2220). Flow B wrote 28 polygons
unpoured on lote-28. Altium's Repour All fills all 28.

## What Changes

- **Outline arcs.** A polygon outline with arc vertices is poured.
  - The arc becomes chords within the polygon's `ARCRESOLUTION`, by the same rule as pad and track
    arcs.
  - The written regions keep the outline's arcs as Altium saves them. The pour regions are chords, as
    Altium saves them (S-2221).
  - `outline-arc` stays a reason only for an arc the reader cannot read.
  - A conversion or a rewrite never drops an arc polygon. KiCad and the model carry its outline
    chorded by `ARCRESOLUTION`. The way back writes the source's arcs while the outline still matches
    them, else the chords, reported `changed` (task 1.3, D1a).
- **Outlines that are not simple rings.** Self-touching outlines and repeated vertices are made simple by
  the rule the saved pours of the corpus show (S-2222). A self-crossing outline still refuses `outline`,
  unless the corpus or a kit sample shows Altium's handling.
- **Every remaining reason is either poured or exact.**
  - `shelved` and `plane-layer` are exact: Altium pours neither. They are reported as such, not as
    refusals.
  - `hatched` polygons are poured as Altium's hatch: tracks of `TRACKWIDTH` at `GRIDSIZE`, in the
    directions of `HATCHSTYLE`, clipped by the solid pour. Kit sample `pour-hatched` (S-2223) proves
    it.
  - `unshaped-copper` (stroke and TrueType texts, graphics on copper) and `unshaped-pad` are shaped by
    the text and pad geometry the writer already holds, through c0460's text references.
  - `threshold` and `pour-over` read every value the public reference defines.
- **No cascade by default.** `depends-on-refused` remains only for a polygon whose reach meets a polygon
  refused for a reason still in `pour.REASONS`. The census pins it at zero.
- **Altium as the oracle.** A new kit step (S-2224) opens each converted public row and runs Repour All.
  It saves the regions Altium pours. `compare_pours` compares Fenolite's computed pour with Altium's
  repour by M1 to M4. The comparison is with the saved pours of the source and with Altium's own
  repour, because a saved pour can be stale.
- **Graduation.** When the K6 round passes the samples `pour`, `pour4` and `pour-hatched`, and the
  Repour oracle passes every polygon of the public rows, the computed pour carries
  `ALTIUM-VERIFIED(kit)`. `altium.zones-poured` then stops naming Repour All. A polygon refused after
  graduation still gives `altium.zone-unpoured`, and that one names Repour All.

## Impact

- Capabilities: `altium-pour`. "Computed pours are experimental" becomes "Computed pours graduate";
  outline arcs, outlines and hatch are added.
- Code:
  - `backends/altium/pour.py`, the pour engine and `pourcompare.py`;
  - `cli/_kit.py`, for the Repour step;
  - `convert/to_altium.py`, for the messages.
- Tests:
  - `tests/corpus/test_altium_pour_census.py` is repinned to no refusals;
  - a kit record of Altium's repour regions per public row, declared in `tests/data/MANIFEST.toml`.
- This change depends on c0462.
