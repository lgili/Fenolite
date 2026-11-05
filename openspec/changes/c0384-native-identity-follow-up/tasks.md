## 0. Carried findings

- [x] 0.1 Record the first finding: the public RoyalBlue replay fails at level 7 with source 289/a562fa79
  versus generated 293/4b439125 and teardrop 263 to 0, with levels 1–6, S and 8 equal. Proof: proposal,
  "Why"; c0355 royal-fresh-project-context-proof.json; docs/evidence/public-replays-20261104.json.
- [ ] 0.4 (from c0355 0.4) Profile numeric netcode structural references and the 331/339 project unknown key
  paths and 10 source PCB Plot numeric occurrences left by ledger v5; author conservative missing, duplicate,
  conflicting, outside and JSON negatives; measure native table-order-only and renumber-only controls before
  any Royal transformation. Each new descriptor needs coordinator approval first.
  - 2026-11-05, bounded closure (coordinator decision, option 1): the ten board `pcbplotparams` numerics and
    the 88 numeric project leaves of the public RoyalBlue source (85 settings plus three section
    `meta/version`) are classified as TEST-ONLY non-reference roles by an authored native10.0.6 renumber
    witness (`test_project_and_plot_numbers_are_not_netcode_references`; docs/formats/kicad/project.md).
    Ledger on RoyalBlue: board unknown numerics 10 to 0, project unknown key paths 331 to 243 of 366, no
    unknown numeric project value, no invalid known role. 0.4 stays OPEN: the 243 remaining keys are
    non-numeric (containers, strings, booleans, arrays) and stay blockers without a documented fact
    each, and the generated-side ledger was not recomputed here. No renumbering is admitted.

- [x] 0.2 Diagnose the four extra generated level-7 regions on the public RoyalBlue board, read-only on the
  inputs, one native refill per input. Proof: `royal-teardrop-diagnosis.json` in this folder. Teardrop
  settings (611 parents, 349 enabled) and project teardrop parameters are equal on both sides. The extras
  are 4 GND regions on F.Cu at pads inside the source's filled GND zone: with `td_on_pad_in_zone` false,
  native generation skips pads inside an existing filled same-net zone, and the source carries 35 ordinary
  fill caches while the generated board carries none. Removing only those caches from a source copy gives
  the generated parent set and count (293). 17 regions still differ (16 teardrop fill only, 1 outline),
  consistent with c0355's measured UUID and track-order dependencies, so identity/order stays necessary.
- [x] 0.3 Coordinator decision on aligning the ordinary fill state before teardrop regeneration (plan sent
  2026-11-05): no code before the decision; c0355's rule against removing, seeding or repairing normal
  fills stands until then.
  - 2026-11-05, decided by the coordinator: option A (B and C stay rejected), with conditions: bind the
    carried caches to every input that can change a fill; drop (never refuse) on any mismatch with the
    reason in the receipt; mark them native carry-over in facts, guide and receipt, never Fenolite-computed
    copper or a Fenolite fill in any proof or level; tests for the round trip, an edit inside the zone and an
    edit elsewhere on the same layer; drop on any copper edit unless a layer is proven unable to matter.
    Implemented (`lens/native_fill_cache.py`): the carrier binds the SHA-256 of the exact emitted board,
    project and custom-rule bytes and the target, a strict superset of the listed inputs (any byte of any
    zone, setting, copper item on any layer, outline, rule or source-derived content drops it; no layer is
    exempted). Proofs: `tests/unit/lens/test_native_fill_cache.py` (round trip exact, every drop reason,
    unreadable carriers dropped, no first match), `tests/unit/importer/test_import_fill_cache.py` (import
    and build round trip carried exactly; a track added inside the zone and a track end moved elsewhere on
    B.Cu each drop with `board-changed`; a missing carrier gives today's board), board.md fact
    (KICAD-VERIFIED 10.0.6), `docs/import.md` "Native ordinary fill caches", guide equivalent-s.md,
    `preserved.native_fill_cache` with `origin: native-carry-over`, `fenolite_computed: false`. No level
    compares zone fills, so the carried caches count in no proof. Fresh public RoyalBlue import on this code:
    35 fills carried; level 7 regenerates 289 regions on both sides (generated was 293); the geometry
    still differs by identity and order (2.1).

## 1. Independent pre-runtime controls

- [x] 1.0 (from c0355 1.0) Author the import-only physical-pad annotation/presence regression, prove the
  existing loss, then implement only the approved vendor callback restoration through the validated
  order-preserving local transform, with every negative and native proof listed in c0355 1.0.
  - 2026-11-05: the restoration (`importer/_pad_annotations.py`, the vendor callback) and its tests already
    landed with c0355 1.2 (commit e5ca7ff4). On 6e923b6d `tests/unit/importer/test_pad_annotations.py` and
    `tests/kicad/board/test_import_pad_annotations.py` pass, 27 tests on kicad-cli 10.0.6: duplicate numbers
    with distinct metadata, variants split/shared, absent versus empty, malformed and changed-identity
    refusals with no pad-number fallback, ambiguous identity, generic library extraction circuit-free,
    real import/build and native load/save. Native 9.0.9 ran in the batch CI of the same code. Fresh
    public RoyalBlue import/build on this head: all 428 physical pads keep their exact annotation
    sequences (389 annotated: 319 pinfunction, 389 pintype; 71 footprints with equal ordered pad
    sequences). Level 7 stays visible as a finding.
- [x] 1.1 (from c0355 1.1) Author native pad/via/track/junction UUID/order controls with complete electrical
  and geometry proofs, and the changed and ambiguous negatives.
  - 2026-11-05 partial: `tests/kicad/board/test_native_identity_controls.py` (native10.0.6) authors two
    0.5 mm pads on two nets 0.3 mm apart with tracks leaving both, the class of the 16 RoyalBlue fill-only
    differences (neighbouring teardrops of different nets whose priority order swaps). Outlines stay equal
    in every case; swapping only two track UUIDs or only two pad UUIDs changes the teardrop fills; one
    repeat is deterministic; reversing track order does not change anything in this geometry; pairing the
    swapped identities back by complete features restores the baseline fills exactly. The test-only
    pairing (`tests/_native_identity_pairing.py`) refuses changed geometry/net, extra or missing objects,
    duplicate signatures, aliases, missing identities, undeclared or contradictory nets and two codes for
    one name (`tests/unit/backends/kicad/test_native_identity_pairing.py`). A second native case, two 0.45 mm
    vias of two nets 0.3 mm apart, shows the same for via UUIDs, and the pairing restores it. Still open:
    an authored track-order (junction) positive, so far observed only on RoyalBlue.
  - 2026-11-05 track-order positive: on a copy of the unfilled public RoyalBlue source, swapping only the
    0.35 mm GND stub from the exposed pad's via pad to a junction with the 1.2 mm track leaving the junction
    to a pin changes one outline; swapping either with the junction's other leaving track does not.
    Authored anew (`test_track_order_at_a_junction_changes_a_teardrop_outline_and_order_preparation_restores_it`,
    native 10.0.6): a 3.6 mm pad with a 0.5 mm through-hole pad inside, the stub to a junction inside the
    large pad and two tracks leaving it down and left to 0.8 x 0.25 mm pins. The small pad's teardrop runs
    along the stub and continues along whichever leaving track comes first in file order: reordering only
    those two moves an outline (3 regions either way), the stub's place does not, one repeat is equal, and
    the order preparation (`identity_pairing`, 2 moved, nothing rewritten) restores the baseline exactly.
    Scratch sweep of four pad sizes and junction offsets, all six orders: the same split every time.
    Negatives: `tests/unit/backends/kicad/test_native_identity_pairing.py` and `test_identity_pairing.py`
    (changed, missing, extra, duplicate and ambiguous objects refuse).
- [x] 1.3 (from c0355 1.3) Prove full object correspondence, no first-match, collision/reference closure and
  unchanged normal-fill/editable field multisets before any private rewrite.
  - 2026-11-05 partial, read-only on the public RoyalBlue source and its fresh generated board: keyed by
    declared net name (codes differ, e.g. 15 versus 1), with the unique pad net child placed by its
    measured-neutral position and quarter-turn footprint angles compared modulo 360, all 943 segments,
    183 vias and 428 pads correspond one-to-one, except one group of two fully identical pads on each side.
    The pairing refuses that group: their exchangeability is not proven, and the new control shows that
    pad UUIDs can change fills. Reference closure (`unreferenced_id_facts` with the project, rules and
    schematic companions): zero external references on both sides; 1554 identity fields each; the source has
    16 aliased pad IDs (one UUID on two pads), the generated board none. The pairing refuses source aliases,
    so a 2.1 rewrite would have to carry them object by object, given zero references: a coordinator
    decision. The rewrite touches only the paired objects' own identity fields (unit test: the paired
    board equals the source), so ordinary fills and editable fields are unchanged by construction.
  - 2026-11-05 closure in code (`identity_pairing.apply`): refused before anything is written, a rewritten
    identity that any other atom of the copy names (reference closure, UUIDs inside longer strings
    included), a written identity the result would name more than once (collision closure), and any change
    of the multiset of root children apart from the own identity fields (every normal fill and editable
    field included). Full correspondence and no first-match stay with `pair` (complete key multisets;
    duplicates refused except the 2.1(c) pair). Proofs: `test_identity_pairing.py` (reference, collision,
    multiset). Read-only on the public boards with this code: RoyalBlue 1522 rewritten, 1125 moved; flat_hierarchy
    625 and 378; on both, zero outside references, zero collisions, multisets equal.
    Found while measuring: as committed in 30da426f the `unconnected_single_pad` rule refused RoyalBlue,
    whose `unconnected-(J1-Pin_3-Pad3)` carries the two physical pads of J1 pin 3 and is spelled alike on
    both sides. The rules now apply only to names not declared verbatim on both boards (a shared name is
    its own key); flat_hierarchy then lists 56 single-pad nets per side and 4 `slash` nets, RoyalBlue none.

- [ ] 1.4 Fidelity finding (not geometry), from the flat_hierarchy replay: the build spells single-pad nets
  `unconnected-(J1-1-Pad1)` where the 9.0.9.1 source has `unconnected-(J1-Pad1)` (the pad's pin name is
  `1`), and writes `/pic_programmer/VPP_ON` as `{slash}pic_programmer{slash}VPP_ON`. Check whether the KiCad
  writer should keep the source's spelling for an imported board, or whether KiCad 9 and 10 name these
  nets differently, citing the public KiCad sources that show it; record the fact in
  `docs/formats/kicad/` with its source and evidence label before any writer change.
  - 2026-11-05 checked (coordinator asked to start): KiCad 9 and 10 name these nets alike; the source's
    spelling is KiCad's own, and the build's board disagrees with KiCad's netlist of the build's own generated
    schematic: `pcb drc --schematic-parity` (10.0.6) on the built flat_hierarchy reports 67 `net_conflict`.
    (a) KiCad's default pin net name carries the pin name only when it is not empty and differs from the pin
    number (S-1490, `eeschema/sch_pin.cpp` at 9.0.9.1 and 10.0.6, read for facts only); new authored probe
    `sch-unconnected-samename` is `absent` (name left out) on 9.0.9 (pinned image) and 10.0.6, while
    `netnames.unconnected_name` writes `J1-1-Pad1`: 56 nets here, exactly the pins named like their number.
    Fact row in `docs/formats/kicad/schematic.md`, probe ledgers, H-K-SCH-UNCONNECTED note. (b) the board
    writer writes every `/` of a created net as `{slash}`, also in a sheet-path name (`/pic_programmer/VPP_ON`)
    that KiCad's netlist of the generated hierarchical sheet keeps with `/` (4 nets, 11 pads). Writer fixes
    (a) and (b) wait for the coordinator's decision; nothing in the writer changed.
  - 2026-11-05 coordinator: both fixes approved as a build bug of their own, change c0408
    (`openspec/changes/archive/2026-11-05-c0408-built-net-spelling/`); this task records the finding and stays open here until
    c0408 lands. The canonical net rules of 1.3 stay: they serve boards built before c0408.

## 2. One focused approved implementation

- [x] 2.1 (from c0355 2.1) Implement only approved private identity/order preparation with complete receipts
  and local refusals; one native run per side, every exact vertex and multiplicity, all old checks retained.
  - 2026-11-05 (coordinator decision: 2.1 shape approved with conditions a, b, c).
    (a) The imported model does not carry source identities into the build: generated tracks, arcs and vias take
    marker `copper_uuid` identities (script-copper ownership), footprints and pads build-derived ones; 0 of
    943 segments, 183 vias, 428 pads and 71 footprints share a source UUID. By design (c0275) identity flows the
    other way: `adopt` gives the source the build's identities. So everything goes to the private preparation.
    (c) `test_fully_identical_pads_exchange_their_identities_without_changing_fills` (native 10.0.6): two
    stacked pads identical but for their UUID, next to a pad of another net that sorts between them;
    exchanging the twins' UUIDs gives byte-identical zones and fills in native order (identities and
    priorities excluded), while exchanging two different pads changes the fills; one repeat is equal. On
    9.0.9 kicad-cli has no `pcb drc --refill-zones` and the level-7 proof refuses any tool but KiCad 10
    (FEN-6002), so no 9 row applies; the test skips there like its neighbours.
    Scratch measurement on the public RoyalBlue copies (not a proof run): with source identities only,
    221/222 parent keys equal the unfilled source (the 16 fill-only differences vanish; carrying the 16
    aliased J1 pad IDs makes no difference); adding source order of tracks and vias gives 222/222; adding
    the source's ordinary fill caches as well gives 289 regions, 219/219 equal to the filled source.
    (b) Implemented for identities (`backends/kicad/identity_pairing.py`, `_derived_cache.identities`):
    side b's private native input copy only, before its one native run; pairing by declared net name and
    complete features, duplicates refused except the (c)-proven pair of two fully identical pads (listed
    in `identical_pairs`); objects whose source identity names several objects keep their own and are
    listed (`source_aliases_kept`, pending the coordinator's confirmation; measured neutral on RoyalBlue);
    `identity_preparation.rewritten` lists every rewritten identity; `label` is "L7 after identity
    preparation" whenever anything was rewritten (docs/fidelity.md). Proofs:
    `tests/unit/backends/kicad/test_identity_pairing.py`, `tests/unit/cli/test_derived_cache_identity.py`.
    Fresh public RoyalBlue on this code with the 0.3 carrier: 1522 identities rewritten (943 segments,
    183 vias, 396 pads), 1 identical pair, 32 aliased J1 pads kept; 289 regions on both sides; geometry
    still differs (0574dd90 versus a562fa79), as the scratch run predicted for the one remaining track-order
    outline. Order preparation waits for the coordinator's decision; 2.1 stays open.
  - 2026-11-05, coordinator: order preparation approved under the same rules, reported as "L7 after identity
    and order preparation", with the reason in fidelity.md and the hypothesis row (by c0275's design a build
    gives copper its own identities and order; no claim that Fenolite keeps them); the aliased source pad
    ids approved as "source alias, not rewritten" with their count. Implemented: `Pairing.moved` (kind,
    side-b identity, old and new position among the root segments, arcs and vias), applied in the copy's
    own slots before the identity rewrite; `identity_preparation.moved`, `source_aliases` (note, count,
    identities) and the label by what was prepared. Proofs: `test_identity_pairing.py` (order in own slots,
    stale order refused), `test_derived_cache_identity.py` (moved receipt, label, alias count). One native
    run per side, complete exact multisets and all old checks unchanged.
- [x] 2.2 (from c0355 2.2) Preserve defaults, source, canonical and native file bytes; add facts, guide or
  result-owner changes only if needed and approved; update CHANGELOG and run focused checks.
  - 2026-11-05: `byte-preservation-proof.json` in this folder: base 1169f10d against 89312d5f, fixed seed and
    timestamp, five public KiCad demos (microwave, pic_programmer, interf_u, complex_hierarchy, RoyalBlue).
    Every source is byte-identical after both runs; import trees are identical except RoyalBlue's new
    `native/fill.cache.json` (the only source with ordinary fills); builds are byte-identical on
    microwave, interf_u and complex_hierarchy, pic_programmer refuses its lossy build (exit 7) on both sides,
    and RoyalBlue's build differs only in the carried fills and the build receipt, and is byte-identical to
    base once the carrier is moved away. The level-7 preparation changes only private proof copies. Facts,
    guide and result changes were the approved ones of 0.3 and 2.1 (CHANGELOG per part). Focused checks
    (ruff, format, `pyright src`, the touched and neighbouring unit folders through the lock, native 10.0.6
    identity and teardrop tests): pass on 52bacc41, after the missing explain entry was added.
- [x] 2.3 (from c0355 2.3) Fresh production Royal/native public and authored neighbours with full inputs and
  context, exact raw and qualified observations, no normal-cache removal or acceptance waiver.
  - 2026-11-05 Royal part: fresh public RoyalBlue import and `verify-source` on this code (kicad-cli
    10.0.6, full inputs and project context, no acceptance): all nine levels equal; level 7 labelled "L7
    after identity and order preparation", 289/a562fa79 on both sides (raw 263 versus 0 stays visible),
    35 ordinary fills carried as native carry-over, no normal cache removed. Receipt
    `royal-prepared-proof.json`. Still open: the public and authored neighbours on this code.
  - 2026-11-05 neighbours on 89312d5f (fresh import and `verify-source`, kicad-cli 10.0.6, no acceptance):
    complex_hierarchy, interf_u, pic_programmer and tiny_tapeout pass all nine levels (tiny_tapeout writes a
    fill carrier; complex_hierarchy, equal unprepared before, now reads "L7 after identity and order
    preparation", 529 rewritten, 364 moved, 16b255c6 on both sides). flat_hierarchy (9.0.9.1 demo, board
    4bd316f0) still differed at level 7 (6c67e319 versus 37277939): the pairing refused because the build
    spells 92 objects' nets differently (finding 1.4). The coordinator approved two canonical net rules
    (`slash`, `unconnected_single_pad`, receipted in `canonical_nets`).
  - 2026-11-05 flat_hierarchy on 30da426f, one `verify-source` run (`flat-hierarchy-prepared-proof.json`): all
    nine levels equal, level 7 "L7 after identity and order preparation", 625 rewritten, 378 moved, 6c67e319
    on both sides (raw 176 versus 0 stays visible); canonical nets: 4 `slash` on side b, 77
    `unconnected_single_pad` per side, 56 of them spelled differently. Authored neighbours: the import fill
    round-trip project and the native derived-teardrop, duplicate-identity, pad-field-order and identity
    controls pass on this code (focused runs above). No normal cache removed, no acceptance.
  - 2026-11-05 rerun on 41cf1ed8 (closure checks and the shared-name exemption), one `verify-source` run per
    board through the heavy-run lock, kicad-cli 10.0.6 (`rerun_41cf1ed8` in both proof files): RoyalBlue all
    nine levels equal, "L7 after identity and order preparation", 1522 rewritten, 1125 moved, 32 source
    aliases, no canonical net, 289/a562fa79 on both sides; flat_hierarchy all nine levels equal on the same
    label, 625 rewritten, 378 moved, receipt rows 4 `slash` and 112 `unconnected_single_pad` (the 56
    differing single-pad nets of each side), 178/6c67e319 on both sides.

## 3. Closure

- [ ] 3.1 (from c0355 3.1) Root-owned combined fast and exact-head native CI, source/format/surface review and
  all linked literal gates. Never archive because a private diagnostic improved.
- [x] 4.4 (from c0355 4.4) After coordinator review, the approved original Royal comparison with the complete
  old acceptance gates passes at level 7, or its failure is retained.
  - 2026-11-05: the comparison passes on the approved label (see 2.3 and `royal-prepared-proof.json`);
    left for the coordinator's review.
  - 2026-11-05: approved by the coordinator 2026-11-05 under the label "L7 after identity and order
    preparation"; plain L7 is not claimed.
