# Design: c0498

## D1 Stored violations

**Format evidence comes first.** `pcb-records.md` knows only that `T…Violation` storages exist, that they
name primitives by index, and that a public row (`altium-third-party-pcbdoc-01`) holds
`TMinSolderMaskSliverViolation` (S-2090). The layout of a record is unknown. Task 1.1 settles it from two
sources:

1. A census of every `T…Violation` and `WaivedViolations` storage of the public PCB documents of the
   corpus manifest, read with `read.cfb.read_compound`: the storage names, `Header` counts, whether `Data`
   holds property-text records (`|KEY=VALUE|…`, as `Rules6` does) or binary ones, and the keys found.
2. A new kit case (Part D, "native DRC"). An authored board with one planted fault per rule kind of the
   table in D3 is built by Fenolite. Altium runs DRC on it with Create Report File on and saves it. The
   saved document and the `.drc` text report are the kit result. The planted faults, and so the expected
   rows, are known before Altium runs.

The rows go to `docs/formats/altium/pcb-records.md`, "DRC violations". Each key gets its unit, so a
location in mil becomes a fact with a source and not an assumption. Each row is `CORPUS-VERIFIED` or
`ALTIUM-VERIFIED(kit)`. The field board stays out of the evidence.

**Reader.** `read/violations.py`:

```python
@dataclass(frozen=True, slots=True)
class NativeFinding:
    kind: str                    # Altium rule kind, e.g. "Clearance"
    rule: str                    # rule NAME
    primitives: tuple[str, ...]  # model `where` texts of the named primitives, sorted
    at: Point | None             # model frame (nm, Y down), through adapter.units.pcb_point
    message: str                 # the record's description text, as stored
    waived: bool = False
    stale: bool = False          # a named primitive index the document does not hold

def stored_violations(path, design) -> tuple[NativeFinding, ...]
def report_violations(report_path, design) -> tuple[NativeFinding, ...]
```

The primitive indices resolve through the provenance locators that the import already gives each item
(`<Storage>/Data#<index>`, `adapter.copper`). Whether a violation's index counts per storage or over all
primitives is part of task 1.1. A `where` is the one `check` uses for the same item: `REF-PIN` for a pad
and the locator otherwise (`copper.CopperRef.where`). So the two lists compare without a second naming.

## D2 Text report, not HTML

The `.drc` text report is plain text in a form the kit can publish. The 2026-10-14 kit report is kept as
native TXT (`docs/evidence/altium-kit/2026-10-13-87c930fa-publication.md`). The HTML report of that run
holds a personal logo reference and stays outside the publication set, so no HTML sample can be
published. `report_violations` reads the text report's violation lines. They name the rule, its kind and
the primitives by their Altium description (for example `Track (x,y)(x,y) on Top Layer`), not by index.
Those descriptions are matched to model items by kind, layer and the coordinates the line states (in the
report's unit, recorded in task 1.1). A line it cannot match keeps `primitives = ()` and its description
in `message`. Stored violations are preferred: they need no matching.

Not done: the HTML report. A later change may add it with an authored sample.

## D3 Comparison

`checks/native.py` is backend-neutral. It takes the `CheckReport` of the stages that ran and the
`NativeFinding`s of a `NativeDrcSource` (new protocol in `backends/base.py`, like `DesignRulesSource`;
`AltiumBackend` implements it). It matches per kind with this table, declared in `backends/altium`
(`rulemap.NATIVE_CODES`):

| Altium kind | Fenolite codes | stage |
|---|---|---|
| `Clearance` | `copper.clearance`, `copper.hole-clearance`, `copper.keepout-clearance` (keep-out scope) | `copper.clearance` |
| `ShortCircuit` | `copper.short` | `copper.clearance` |
| `BoardOutlineClearance` | `copper.edge-clearance` | `copper.clearance` |
| `Width` | `copper.track-width` | `copper.clearance` |
| `SilkToSilkClearance` | `silk.clearance` | `silk.clearance` |
| `SilkToSolderMaskClearance` | `silk.mask-clearance` | `silk.clearance` |
| `SilkToBoardRegionClearance` | `silk.edge-clearance` | `silk.clearance` |
| any other | none: listed in `unjudged` | — |

Two findings match when their codes map to the same kind and their item sets are equal, unordered. When
an item set is empty (an unmatched report line), they match when the native location lies within 0.1 mm
of the Fenolite finding's `at`. Each finding is used once, and pairs are taken in sorted order, so the
result does not depend on input order. Waived native findings are left out of the pairing and counted.

`result.native`:

```json
{"source": "stored" | "report", "file": "<name>", "matched": 12,
 "by_kind": {"Clearance": {"matched": 10, "fenolite_only": 1, "native_only": 0}, ...},
 "fenolite_only": [<issue>...], "native_only": [<native finding>...],
 "unjudged": {"Height": 3}, "waived": 2, "stale": 0}
```

One `check.native-only` or `check.fenolite-only` warning per unmatched finding. One `check.native-stale`
warning when any violation names a primitive the document lacks: the DRC is older than the document, for
example after an edit session renumbered records. With stale violations the comparison still runs on the
rest. Warnings do not change the exit code. Errors of the stages that ran do, as before.

**CLI.** `--compare-native` takes an optional path. Without a path, the stored violations of the PCB
document are used. With a path ending `.drc`, that report is used. A document without stored violations
and no path gives `check.native-missing` (warning: "run DRC in Altium and save, or pass the report"). The
option needs Altium input, else `FEN-2001`. It adds `altium.native-drc` and `silk.clearance` to the
selected stages, so `--stages` still narrows the rest.

Alternative rejected: running Altium's DRC from Fenolite. That needs the Windows VM and Altium's
automation, which is not a public interface and cannot run in CI.

## D4 Silk rules

The kinds `silk_mask_clearance` (unary: silk against every solder-mask opening) and `silk_edge_clearance`
(unary: silk against the board's edge rings) join `RuleKind`. `read.rules.RULE_KIND_MAP` gains
`SilkToSolderMaskClearance` (key recorded by task 1.2 from the corpus, the rule export S-0297, or the kit
board) and `SilkToBoardRegionClearance`. Both leave `CARRIED_KINDS`. The KiCad backend does not lower them
(`KIND_SUPPORT` is empty for both). A conversion to KiCad keeps reporting them as carried, with the same
reason text as now.

The stage `silk.clearance` reads `DesignRules` for the three silk kinds. It judges, on each silkscreen
side:

- every pair of silk items (tracks, arcs, texts, footprint strokes) closer than `silk_clearance`, except a
  text against the silk of its own component;
- every silk item closer than `silk_mask_clearance` to a mask opening, each pad's copper grown by its own
  mask expansion;
- every silk item closer than `silk_edge_clearance` to an edge ring.

Text boxes, hidden designators and the own-component rule are those of c0493's `altium` model
(`silk.board.gather(model="altium")`). This change adds a whole-board judge, `silk.board.judge_silk`, on
the same obstacles, with no second geometry. Its evidence is `INFERRED` and names `H-A-SILK-DRC-MODEL`
until the kit case of D1 confirms it with planted silk faults.

The stage is opt-in (`OPT_IN_DOCUMENT_STAGES`) until that confirmation, so a board that passed `check`
today does not start to fail on a hypothesis. Making it a default stage is a later, one-line change.

## D5 Cut-outs and keep-outs

1. **Diagnose** (task 1.3) on authored boards. Each has a pour 0.03 mm from a slot under a 0.5 mm
   `BoardOutlineClearance`. The slot is in turn:
   - a free board cut-out;
   - a component's board cut-out;
   - an unplated slotted pad hole;
   - a free board cut-out where the rule is a matrix (`OBJECTCLEARANCES`) or scoped to the pour's net.

   Each case that gives no finding is fixed where it fails (`frame.board_edges`, `ClearanceResolver.edge`,
   the edge matrix of c0462). A slotted hole stays the job of `copper.hole-clearance`, and Altium's
   `BoardOutlineClearance` does not cover holes. Task 1.3 checks that statement with the kit board and
   records the answer.
2. **No silent gap.** When the board has at least one `edge_clearance` rule or a board minimum, and
   `unset_items > 0`, the copper stage adds one `copper.rules-incomplete` (warning, `where` = `edge`)
   naming the count and up to three items, and lowers its evidence to `UNVERIFIED`, as the other
   rules-incomplete cases do.
3. **Keep-out distance.** `pour._keepout_rule` moves to `read/rules.py` as `keepout_clearance_rule`,
   called by the pour and by `AltiumBackend.design_rules`. Its rule (`kind="clearance"`,
   `selector_a = item_kind keepout`) reaches the copper check. `check_copper` judges each copper item
   against each keep-out area of `_Areas` on a shared layer whose rule subject is `keepout`. A gap below the
   rule gives `copper.keepout-clearance` with the area's name, the gap and the rule. An item that a
   keep-out already forbids by overlap keeps its `copper.keepout` and gets no second finding. A board
   cut-out term (`IsBoardCutoutRegion`) is not a keep-out area. It stays the edge's case under
   `BoardOutlineClearance`, as for the pour (I17).
   Keep-out tracks and arcs of the Keep-Out layer that the import keeps as graphics, not as rule areas, are
   not in `_Areas`. c0501 (route on an existing board) gives them restrictions for the router. If c0501
   makes them areas, this check sees them with no further change. Until then the stage counts them in
   `summary.keepout_unjudged` and gives one `copper.rules-incomplete` (`where` = `keepout`).

## Hypotheses registered by this change

| id | statement |
|---|---|
| `H-A-DRC-STORED` | A PCB document saved after a DRC holds one record per violation in a `T<Kind>Violation` storage, naming the rule and its primitives by index and a location; the keys and units are those of `pcb-records.md`, "DRC violations" |
| `H-A-DRC-TXT` | The `.drc` text report lists one line group per violation with the rule's kind and name and a description of each primitive with its layer and coordinates |
| `H-A-SILK-RULES` | `SilkToSolderMaskClearance` measures silk to each pad's mask opening and `SilkToBoardRegionClearance` silk to the board's outline and cut-outs, with the text box of `H-A-SILK-DRC-MODEL` |

## Risks

- The violation record may hold only the primitive indices and the rule name, with no kind. The kind
  then comes from the rule of that name in `Rules6`.
- A record layout that differs between Altium versions. The census records the version of each source
  (the kit runs AD 24.5, the corpus documents state theirs). The reader refuses an unknown layout with
  `altium.read.violations-unknown` instead of guessing.
- Matching by items fails where Fenolite and Altium split one fault differently, for example one pour
  against two tracks. `by_kind` shows it. The pairing does not try to merge.
