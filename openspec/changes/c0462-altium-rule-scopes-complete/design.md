# Design: c0462

## Sources

| id | what | used for |
|---|---|---|
| S-2210 | The coordinating session's survey of the 8 public Altium rows of `tests/corpus/test_altium_pour_census.py` on `cac/lote-29` 249ea7ba7, 2026-11-06: out-of-grammar scopes per kind, functions used, `Unmapped` per kind and reason, pour refusals per reason. Counts only; the script is not kept. | the targets of this change |
| S-2211 | Altium, "Working with the Query Language", <https://www.altium.com/documentation/altium-designer/query-language> (page dated 2026-11-02, read 2026-11-06). Its PCB section gives the order of precedence and says that ambiguities resolve left to right. | D1 |
| S-2212 | Altium, PCB query functions: <https://www.altium.com/documentation/altium-designer/pcb/query-functions> with its subpages `attribute-checks`, `fields`, `layer-checks`, `membership-checks` and `object-type-checks` (read 2026-11-06). Each function's syntax and the objects it returns. `IsSOIC`, `IsBGA` and `IsLCC` are defined by pad rows, columns and counts of surface-mount pads. | D2, D3 |
| S-2213 | KiCad, custom design rules documentation (the public page of the KiCad version the target pins): the expression for a pad's type, a hole's size and a zone's name. | D4 |
| S-2214 | Altium kit run of task 5.1: for each distinct scope of the public rows, the objects Altium's PCB filter selects, per object kind. | acceptance, `ALTIUM-VERIFIED(kit)` |
| S-2215 to S-2219 | reserved for the tasks' records | |

Implementers record each fact in `docs/formats/altium/rule-file.md` and give it an evidence label. A
paraphrase of the reference is fine; text copied from it is not. A function the reference does not define
stays outside the grammar.

## D1: the grammar follows Altium's precedence

The table, from tightest to loosest (S-2211):

1. brackets;
2. `Not`;
3. `^ * / Div Mod And`;
4. `+ - Or Xor`;
5. `= <> < > <= >=` (and `Between … And …`, `Like` when the reference defines them);
6. `&& ||`.

Equal levels resolve left to right. The parser is a precedence-climbing parser over typed values:
boolean, number with a unit, string. It returns a `Selector` only when the typed tree is well formed and
every leaf maps exactly (D2 to D4).

- `And` binds tighter than a comparison. So `HoleDiameter > 1 And IsPad` is
  `HoleDiameter > (1 And IsPad)`, a number compared with a boolean. It is refused with the reason
  `type`, naming the operator. Re-bracketing it to what the author probably meant would be approximating.
- `&&` and `||` sit below the comparisons. So `HoleDiameter > 1 && IsPad` reads as written.
- `Xor` becomes `or(and(a, not b), and(not a, b))`. `x = True` and `x = 'True'` are the boolean `x`.
  `x = False` is `not x`. A function written `Name : Boolean/Boolean_String` takes these forms (S-2212).
- A number takes the document's unit, unless `AsMils(…)` or `AsMM(…)` gives one. The neutral value is
  nanometres. A number with no unit and no known document unit is refused (`unit`).

Two existing refusals stay:

- `All` below the top level;
- any text left over.

One existing refusal goes: the mixed-operator refusal (S-0296), which now has a source.

## D2: functions onto the selectors that exist

| function | selector | note |
|---|---|---|
| `OnLayer('L')`, `OnTopLayer`, `OnBottomLayer` | `layer <copper name>`; implemented as `and(layer…, not(MULTI_LAYER))` for the `On…` checks and `or(layer L, MULTI_LAYER)` for `OnLayer`, because S-2212's `OnOutside` returns no Multi-Layer object (`H-A-RD-PRJ-SCOPE-MULTI`) | through `copper_layers_of`. A multi-layer object matches only when the layer is named (S-2212). The subject of a through-hole pad on a layer is that layer: as now, for `ExistsOnLayer`. |
| `OnMid` | `or(layer In1.Cu, …)` | with no internal signal layer it is a rule of no object: the info `altium.rule.applies-to-nothing` in place of `altium.rule.unmapped`; the record stays `Unmapped` with `no-layer` (`NOT_APPLYING`), so a conversion keeps it (c0424) |
| `ExistsOnLayer('L')`, `InAnyNet` | as now | |
| `WithinRoom('R1', …)` | refused | rooms are read as named rule areas that restrict nothing (task 2.3, `read.rooms`); the record stays a kept record (c0434), so an Altium write gives it back as read. A pad or via is in a room by its centre, any other object only wholly inside (S-2212), while the neutral `area` leaf selects an object whose copper touches the area (`H-K-AREA-COND`): a room the document holds is refused `room-membership`, one it does not hold `undefined`. `RuleSubject.areas` and the `area` leaf keep their meaning. |
| `InDifferentialPair('P')`, `InAnyDifferentialPair`, `IsDifferentialPair` | `diff_pair P` or `diff_pair *`; implemented as the `net` leaves of the pairs' nets, since the subjects of primitives do not carry `diff_pair` | through the pairs the document defines (`model.pairs`) |
| `InDifferentialPairClass('C')`, `InxSignalClass('C')`, `InxSignal('X')` | `or` of `diff_pair` or `net` leaves | expanded from the document's class or xSignal definitions. Undefined: refused, `undefined` |
| `HasFootprint('P')`, `IsComponent`, `IsNetTieComponent`, `IsSOIC`, `IsBGA`, `IsLCC`, `InNamedUnion('U')` | `or(ref R1, …)`, or `not(all)` when none match | expanded at read time over the document's components. For the package checks, the pad-grid definition of S-2212 is evaluated on the component's surface-mount pads. `InNamedUnion` of primitives other than components is refused (`union-kind`). |
| `InDrillLayerPair('A - B')` | `and(item_kind via, …)` | exact only when the pair is the whole stack and the document has no other pair. Otherwise refused, `drill-pair`, until the model holds via spans. |

**Expansion is a read-time fact.** An expanded selector is exact for the document read. A later edit
that adds a component or a net does not re-run the query. Two things guard that:

1. the rule keeps its `origin` text, and the carrier (c0434, c0457) writes the source record back to
   Altium as read;
2. `fenolite.dsl` prints an expanded rule with a comment that names the source function, so a reader
   sees it is a frozen list.

A rule written from Fenolite's own model is never expanded.

## D3: the package checks

`IsSOIC`, `IsBGA` and `IsLCC` are geometric definitions over a component's surface-mount pads (S-2212):

- rows and columns of pad centres, on a tolerance of the pad pitch;
- pad counts;
- the row and column difference.

`read/packages.py` evaluates them, with one unit test per definition built on authored footprints.

The definitions come from documentation and have not been confirmed by Altium. So the check carries
`INFERRED` until the kit oracle of task 5.1 agrees on every component of the public rows; then it carries
`ALTIUM-VERIFIED(kit)`. On a disagreement the function stays refused (`package-check`). It is never
guessed.

## D4: three additive leaves

`SelectorOp` gains `zone`, `hole` and `pad_type`. The model is frozen at 1.0 (c0218), so adding them is a
minor version: `SCHEMA_VERSION` is `1.1`, with the identity migration step `1.0 -> 1.1`. The writer always
stamps the current version, so every document is written as `1.1`, whether or not it uses a new op; a
document that uses one therefore says it needs a 1.1 reader, and a 1.0 reader refuses every 1.1 document
with `FEN-3002`.

- The model review records the widening of `Selector.op` with its own approval (`model0-approved.json`,
  the field's new `type`, its `widened_from` and `approved`: approved 2026-11-06, c0462, coordinator under
  maintainer delegation, the form c0465 uses too); the freeze tests accept only such a recorded widening,
  and only when every approved value is kept: the schema drift test puts the old values back and then
  finds no other change.
- `gen_schemas` is regenerated.
- `RuleSubject` gains `zone: str | None`, `hole: int | None` (finished diameter, nm) and
  `pad_type: str | None`. A subject that does not set them still evaluates every old selector the same
  way.

The leaves' values:

- `zone` holds a glob over the zone's name, compared with letter case, as `area` is.
- `hole` holds `lo..hi` in nanometres, either side open (`..hi`, `lo..`). It matches a subject whose
  `hole` lies in the closed interval. A comparison becomes the interval:
  - `>` uses `lo + 1`;
  - `=` uses `v..v`;
  - `<>` uses `not`.
- `pad_type` is one of `smd`, `th`, `npth`. `PadIsPlated` is `pad_type th`; with `= False` it is
  `pad_type npth`. A via has `pad_type None`.

The KiCad writer prints each leaf as the expression S-2213 gives. A leaf with no KiCad expression makes
the KiCad rule a reported loss of that rule only (`rulemap.KIND_SUPPORT`), never a broader rule.

`fenolite.dsl.select` gains `zone()`, `hole(lo=…, hi=…)` and `pad_type()`. Each is taught by the agent
guide (AGENTS.md rule 6).

## D5: record keys

- **Per-layer values** (Width `TOPLAYER_*`, `MIDLAYER<n>_*`, `BOTTOMLAYER_*`; DiffPairsRouting
  `<LAYER>_MAXGAP`, `_PREFGAP`) become one neutral rule per copper layer: `and(scope, layer L)`, with the
  record's name and a layer suffix.
  - A layer value equal to the record's general value gives no extra rule.
  - A layer name the board does not hold is ignored, with the info `altium.rules.layer-absent`.
- **Width impedance keys** (`FAVIMP`, `MAXIMP`, `MINIMP` and the per-layer widths the record holds): the
  record's per-layer widths are read as above. When widths derive from an impedance profile that the
  record does not store, the record stays `Unmapped` (`impedance-profile`) and is carried.
  Fenolite's impedance targets (c0105) are not inferred from it.
- **RoutingVias templates** (`USEVIATEMPLATES`, `VIATEMPLATEGUID#n`, `VIATEMPLATENAME#n`): the sizes come
  from the template the document holds (its via-template storage, if c0450 carries one). They then give
  `via_diameter` and `via_drill`, as the record's own sizes do. A template the document does not hold
  stays `Unmapped` (`template`).
- **`OBJECTCLEARANCES` matrices** (Clearance, BoardOutlineClearance): cells are pairs of object kinds.
  - Each distinct cell value other than the rule's general gap becomes one neutral rule. Its scope is
    `and(scope, kind A)` against `and(scope, kind B)`.
  - Whatever ranks and priorities the rules take, the result must hold: the neutral rules give every
    pair of object kinds exactly its cell's gap. A unit test proves this for every cell of the three
    corpus matrices, and for an authored matrix with cells above and below the general gap.
  - The kinds map: track and arc to `item_kind track` or `arc`; SMD pad to `pad_type smd`; TH pad to
    `pad_type th`; via to `item_kind via`; polygon to `item_kind zone`; fill and region to their item
    kinds; hole to `hole ..`; text to `item_kind text`.
  - The cell rules sit at the record's place in Altium's priority order, so no rule of another record
    changes rank.
  - A cell whose object kind has no neutral kind is refused (`matrix-kind`), naming the cell.

## D6: kinds that govern copper

| kind | reading |
|---|---|
| MatchedLengths | `skew` over the selected nets (tolerance → limit), and `length` when the record holds a target length |
| SolderMaskExpansion, PasteMaskExpansion | unscoped: `Board.mask_margin` (c0445) and its paste twin, when the target holds one. Scoped: per-pad margins on the pads the scope selects. Otherwise carried. |
| PlaneClearance, PlaneConnect | read by the internal planes' reading (c0461 counts split planes lost). Carried and listed as read by that part. |
| PolygonConnect | read by `connectstyle` with the full grammar. `connect-scope` goes away with it. |
| ShortCircuit, UnRoutedNet, NetAntennae, UnpouredPolygon | `fenolite check` performs these checks by itself. The record is carried. A record that relaxes one (for example `ALLOWED=TRUE` on ShortCircuit) is reported `altium.rules.check-relaxed` and honoured by `check`. |
| the rest (fanout, routing corners/topology/priority, layer pairs, test points, height, silk, sliver, orientations, SMD to corner/plane, acute angle, vias under SMD) | carried only (c0434), listed in the table with the reason that none governs copper geometry |

The table in `rule-file.md`, "Rule kinds and their reading", is closed. A test fails when a corpus kind
is absent from it.

## Acceptance

On the 8 public rows:

- `map_rules` gives no `Unmapped` with the reasons `scope`, `keys` or `no-layer`, except the refusals D1
  to D5 name. Each such refusal is pinned by count in the census test, and each has a task-5 record that
  says why it is exact to refuse.
- The pour census holds no `rule-scope`, `rule-unmapped` or `connect-scope`. The `depends-on-refused`
  cascades that remain are c0463's.
- For each distinct mapped scope, the objects selected equal the objects Altium's filter selects
  (task 5.1, S-2214).

Follow-up for `WithinRoom` (coordinator, 2026-11-06): the exact mapping needs a neutral room membership,
such as a defaulted `Keepout` field (`touch` or `room`) that the copper check and the pour honour and the
KiCad writer reports as a loss. It waits for a kit sample or a public row that holds a room: no public
document holds one, the four `WithinRoom` scopes of rows 04 and 07 name a room their board does not hold,
and the record keys of a document's room are `INFERRED` from the public rule file (`H-A-RD-ROOM`).

## Risks

- **The neutral model grows by three ops.** The rule ranks of `selector_rank` gain entries: `zone` 1,
  `hole` 1, `pad_type` 1. A KiCad round trip of old models is unchanged; a unit test pins that.
- **An expanded rule can grow large:** `IsComponent` on a board of 500 parts is 500 `ref` leaves. The
  KiCad writer prints refs as one `A.Reference` glob set when every ref shares a prefix pattern.
  Otherwise it prints them as is. A size test is pinned on the largest public row.
- **The package definitions may disagree with Altium.** The kit oracle decides; the function then stays
  refused.
