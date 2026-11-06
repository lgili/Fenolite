# c0462: every Altium rule scope and rule record that governs copper is read

## Why

v0.7 must read an Altium board's rules the way Altium does. If it reads them differently, nothing built on it
holds: check, route, the computed pour (c0463) and the round trip through KiCad. On `cac/lote-29` (249ea7ba7),
the 8 public Altium rows of `tests/corpus/test_altium_pour_census.py` show the reader still stops short.
Counts are from the coordinating session's survey of 2026-11-06 (S-2210):

- **Scopes outside the closed grammar.** `parse_scope` refuses mixed operators without parentheses, and
  every function it does not name. The reason was that no permitted source gave the precedence (S-0296).
  Altium's public Query Language page now gives it (S-2211).
  - These scopes are out of the grammar, per kind: Clearance 3 of 34, ComponentClearance 7 of 20,
    DiffPairsRouting 3 of 18, HoleSize 2 of 18, MatchedLengths 8 of 30, PolygonConnect 6 of 36,
    RoutingVias 3 of 24, Width 1 of 22, FanoutControl 32 of 80.
  - These functions are used and not read: `IsSOIC`, `IsLCC`, `IsBGA` (8 each), `InxSignalClass` 7,
    `OnBottomLayer` 5, `InDifferentialPairClass` 5, `HasFootprint` 4, `WithinRoom` 4, `IsComponent` 4,
    `IsNamedPolygon` 2, `IsNetTieComponent` 2, `InAnyDifferentialPair` 2, `InDrillLayerPair` 2,
    `IsDifferentialPair` 1, `InNamedUnion` 1, `OnTopLayer` 1. The comparisons of `HoleDiameter` and
    `PadIsPlated` are not read either.
- **Records whose keys are not read.**
  - RoutingVias via templates: 5.
  - Width impedance and per-layer widths: 3.
  - A Clearance `OBJECTCLEARANCES` matrix of differing cells: 3.
  - A BoardOutlineClearance matrix: 3.
  - DiffPairsRouting per-layer gaps: 3.
- **Refused scopes, by kind.** ComponentClearance 4, Clearance 3 (`HasFootprint`), HoleSize 2
  (`HoleDiameter`), Width 1 (`IsDifferentialPair`).
- **An `OnMid` Clearance on a board with no internal layer** is counted unmapped (1), though it applies to
  no object.
- **Records with no counterpart:** 40 kinds. Some govern copper: MatchedLengths 15, PolygonConnect 18,
  SolderMaskExpansion 11, PasteMaskExpansion 8, PlaneConnect 9, PlaneClearance 8. The rest are DRC
  switches and placement or fabrication rules.
- **The pour pays for each gap.** Its census counts `rule-scope` 18, `rule-unmapped` 9 and
  `connect-scope` 5. Those then refuse `depends-on-refused` 32. Pouring through an unread scope gives
  copper Altium would not pour (S-2160), so the refusals are right. The cure is reading the scopes.

## What Changes

- **Altium's precedence.** `parse_scope` follows Altium's table: brackets, then `Not`, then
  `^ * / Div Mod And`, then `+ - Or Xor`, then the comparisons, then `&& ||`. Ambiguities resolve left to
  right (S-2211). The parse is typed. A query whose typed reading is not well formed is refused, naming
  the operator, and is never re-bracketed. One case is `HoleDiameter > 1 And IsPad`, which Altium reads
  as `HoleDiameter > (1 And IsPad)`.
- **Functions onto the neutral selectors that exist.** Each mapping is exact:
  - `OnLayer`, `OnTopLayer`, `OnBottomLayer`, `OnMid` and `ExistsOnLayer` map to `layer`.
  - `WithinRoom` maps to `area`. Rooms are read as rule areas.
  - The differential pair functions map to `diff_pair`.
  - `InxSignal`, `InxSignalClass` and `InDifferentialPairClass` map to the nets and pairs that the
    document defines for them.
  - `HasFootprint`, `IsComponent`, `IsNetTieComponent`, `IsSOIC`, `IsBGA`, `IsLCC` and `InNamedUnion`
    map to the components they select in the document. The package checks use Altium's documented
    pad-grid definitions.
  - `InNet` values may hold glob characters; they are escaped.
- **Three additive neutral leaves.** They are added through the model version process (`model-versions`,
  `tools/model_review.py`):
  - `zone` (a polygon by name), for `IsNamedPolygon` and `InNamedPolygon`;
  - `hole` (a closed interval of finished hole diameters), for `HoleDiameter`, `HoleSize` and `Hole`
    comparisons;
  - `pad_type` (`smd`, `th`, `npth`), for `PadIsPlated` and the pad attribute checks the public
    reference names (S-2212), and for the matrix cells that tell the pad kinds apart.
  - The KiCad target writes each leaf as the expression its public custom-rule documentation gives.
- **Record keys.**
  - Width and DiffPairsRouting per-layer values become one neutral rule per layer.
  - Width impedance-driven widths are read where the record holds them.
  - A RoutingVias via template is read where the record or the document holds its sizes.
  - A Clearance or BoardOutlineClearance `OBJECTCLEARANCES` matrix becomes one neutral rule per distinct
    cell value, scoped by the object kinds of its cells.
- **Kinds that govern copper.**
  - MatchedLengths becomes `skew` and `length`.
  - An unscoped SolderMaskExpansion or PasteMaskExpansion becomes the board's margins (c0445). A scoped
    one becomes per-pad margins.
  - PlaneClearance and PlaneConnect are read by the plane layers' reading.
  - PolygonConnect stays read by the pour (`connectstyle`), now through the full grammar.
- **A closed table for every other kind.** `docs/formats/altium/rule-file.md` gains "Rule kinds and their
  reading". It lists each of the 40 kinds the corpus holds as neutral, read by a backend part, checked by
  Fenolite's own check, or carried only (c0434). A carried-only kind must not change check, route or pour.
- **`OnMid` with no internal layer** is a rule that applies to no object. It gives the info
  `altium.rules.applies-to-nothing`, not `Unmapped`.

## Impact

- Capabilities:
  - `altium-project-reader`: the closed scope grammar is modified, and scope functions, record keys and
    the kind table are added;
  - `rules-model`: three leaves are added;
  - `imported-rules`: rooms become rule areas;
  - `kicad-file-backend`: the new leaves are written.
- Code:
  - `backends/altium/read/scope.py`, `read/rules.py` and `connectstyle.py`;
  - room reading in `backends/altium/read/`;
  - `model/rules.py`;
  - `backends/kicad/rulemap.py`;
  - `checks/` (the new leaves in `RuleSubject`);
  - `fenolite.dsl.select`, for the new leaves;
  - schemas, the agent guide and the evidence matrix.
- The model gains three selector ops: an additive minor version, approved through `tools/model_review.py`.
- Tests:
  - the pour and conversion censuses are repinned;
  - an Altium kit oracle compares, for each distinct scope of the public rows, the objects Altium's PCB
    filter selects with the objects Fenolite's selector selects (`ALTIUM-VERIFIED(kit)`).
- c0463 (the pour without Repour) depends on this change.
