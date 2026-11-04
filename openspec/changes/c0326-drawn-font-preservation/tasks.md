## 0. Establish and review the representation

- [x] 0.1 Record the actual font-loss control, source/native render receipts, carrier audit,
  footprint-text and filename boundaries, and validate the complete planning packet.
  Proof: `npx -y @fission-ai/openspec validate c0326-drawn-font-preservation --strict`;
  validate all artifacts and SHA-256 values in the external `level8-diagnosis` receipt.
  Passed 2026-11-02: strict validation without warnings; all 12 declared diagnostic
  artifact hashes and the unchanged clean core/external source checkpoints verified.
  Actual CLI version is 9.0.2; native exports are not GUI saves or exact-version CI.
- [x] 0.2 Record maintainer review of the recommended typed fields, private-bag compatibility,
  complete text scope and replacement final-model-0 plan before production code changes.
  Proof: dated review decision in `design.md`, then
  `npx -y @fission-ai/openspec validate c0326-drawn-font-preservation --strict`.
  Decision recorded 2026-11-02: the coordinator and independent read-only reviewer
  accept the typed plan under the user's standing delegation, with effective native
  styles separate from canonical presence, asymmetric H/W probes, measured missing
  justification and explicit sub-µm rendering behavior. No native observation is
  implied by this review. Implementation is authorized after strict revalidation.
  Passed 2026-11-02: the clarified packet validates strictly without warnings;
  the review is recorded above before any implementation change.

## 1. Represent and serialize fonts

- [x] 1.1 Add `DrawnFont` and the optional field/label/pin/sheet-property carriers. Prove positive
  integer sizes, nonnegative thickness, booleans, names, defaults and invalid/empty style refusal.
  Proof: `uv run pytest tests/unit/model/test_drawn_fonts.py tests/unit/model/test_drawn_value.py -q`.
  Passed 2026-11-02: 37 cases. Exact asymmetric/sub-µm sizes, canonical absent/false/zero,
  frozen/hashable values, invalid dimensions/types/names, optional justification and
  closed unique sheet-property poses pass. This model-only proof claims no codec or
  native style support; later tasks preserve/refuse the actual target effects.
- [x] 1.2 Add closed TOML/schema support and canonical writing. Prove round trips, both axes,
  absence versus false/zero, exact nm, unknown-key refusal and unchanged old drawing bytes.
  Proof: `uv run pytest tests/unit/lens/test_drawn_fonts.py tests/unit/lens/test_drawn_file.py tests/unit/test_schema_drift.py -q`;
  `uv run python tools/gen_schemas.py --check`.
  Passed 2026-11-02: 74 focused codec/legacy/schema cases and the schema generator
  check. Every previous authored canonical drawing keeps its bytes. New font
  properties and sheet-property fields agree with the closed editor schema;
  exact integer/property controls and malformed inputs retain precise locators.
  Native effective-style support is not implied by this serialization checkpoint.
- [x] 1.3 Add versioned private font adapters while preserving every six-part legacy field
  payload. Reject malformed, duplicate, orphan and unknown style records.
  Proof: `uv run pytest tests/unit/backends/kicad/test_drawn_font_ext.py tests/unit/backends/kicad/test_sch_write_drawn.py -q`.
  Passed 2026-11-02: 42 adapter/default-writer cases. Legacy bags retain all six
  original parts/bytes; explicit fonts use separate deterministic integer-only
  versioned records. Malformed, duplicate, orphan, unknown and null/float payloads
  refuse with FormatError. Label/pin adapters retain absent versus explicit centre.
  No native font token or effective-style claim follows from these private records.

- [x] 1.4 Close the independently reproduced noncanonical-justification round-trip gap:
  model and private text adapters reject extra/leading/tab-only spaces consistently
  with TOML, keeping `None` versus `""`. Teach all implemented codec keys honestly.
  Proof: `uv run pytest tests/unit/model/test_drawn_fonts.py tests/unit/lens/test_drawn_fonts.py tests/unit/backends/kicad/test_drawn_font_ext.py tests/consistency/test_drawn_schema.py -q`.
  Passed 2026-11-02: all 16 new whitespace controls failed before the fix; 117
  model/codec/private-adapter/key-census cases pass afterward. Absent and empty
  justification remain distinct. The documentation describes implemented codec
  keys and explicitly leaves native style preservation unclaimed.
- [x] 1.5 Close the independently reproduced Decimal-context unit bug in the shared drawn
  length reader. Prove long fractional-nm literals refuse and exact long literals
  remain exact independently of ambient Decimal precision, without float conversion.
  Proof: `uv run pytest tests/unit/lens/test_drawn_fonts.py tests/unit/lens/test_drawn_file.py -q`.
  Passed 2026-11-02: before the fix, five new long-fraction/low-precision cases fail
  and the default-precision exact case passes. After exact integer-ratio scaling,
  all 56 font/legacy codec cases pass; fractional nm refuse with the same locators
  and exact lengths are unchanged at ambient precisions 1, 2, 6 and 28.

## 2. Preserve actual native effects

- [x] 2.1 Extract/write symbol and power-field fonts, preserving existing code-owned texts,
  hidden references and default names. Prove the original one-resistor size-loss control.
  Proof: `uv run pytest tests/unit/backends/kicad/test_drawn_fonts.py -k 'field or power' tests/unit/importer/test_drawn_fonts.py -q`.
  Passed 2026-11-02: 25 focused cases, plus 121 existing source/schematic/provenance
  regressions. The original small-field control imports through reviewed replay and
  proves all nine levels equal, accepted/differences empty, one actual track matched
  and original source bytes unchanged. Native 9.0.2 field probes establish H/W,
  absent/false and zero-thickness equivalences and missing-font defaults; no 9.0.9/
  10.0.6 or GUI claim follows. Unsupported/inexact/sub-µm typed native fonts refuse.
  Hidden nondefault non-power-reference field fonts retain poses; existing hidden
  power-reference behavior and code-owned texts remain unchanged.
  After that hidden-field extension, the affected extraction/import selection
  passes again (99 cases); the earlier broader 121-case result remains separately
  scoped. No source-input, manual fixture, accepted loss or comparison threshold changed.
- [x] 2.2 Extract/write local/global/hierarchical label and sheet-pin font/justification, plus
  sheet-name/file property poses/effects. Retain unsupported-effect refusals and native slots.
  Cover missing/empty/explicit native justification without confusing omission with
  `None`'s legacy role-selected anchor.
  Proof: `uv run pytest tests/unit/backends/kicad/test_drawn_fonts.py tests/unit/backends/kicad/test_drawn_extract.py tests/unit/backends/kicad/test_sch_write_drawn.py -q`.
  Passed 2026-11-02: 76 focused cases, including native omission→explicit centre,
  role-equivalent defaults, all label kinds, pins and sheet-property font/pose
  round trips on written target9/10 bytes. Native 9.0.2's 84 authored CLI controls
  establish the anchor/size mapping; exact-version CI remains open. Hidden label/
  pin states and visible/custom unrepresented label-property effects refuse.
  The 80 existing importer/source/fidelity regressions and full source type check
  also pass; native original inputs and comparison thresholds remain unchanged.
- [x] 2.3 Preserve new explicit styles through strict importer self-check/review replay; prove
  unrepresentable styles stage no write. Keep footprint-text and filename differences visible.
  Proof: `uv run pytest tests/unit/importer/test_drawn_fonts.py tests/unit/cli/test_verify_source_drawn.py -q`.
  Passed 2026-11-02: 18 cases. Original CC0 target9/10 hierarchies retain every
  typed text surface through strict dry-run, reviewed byte replay and all-nine
  equality with routed copper, no accepted differences and unchanged sources.
  Unknown/hidden label or pin effects refuse before a plan; changed source styles
  invalidate replay with FEN-4002. Independent visible Footprint text and filename
  controls still differ at level 8 with every other level equal and accepted empty.
  This adds no loss flag, native GUI claim, external acceptance or core behavior.
  The later 3.1 renderer guard limits positive full controls to its supported
  size/justification subset. Other native styles retain 1–7/S equality but now
  explicitly refuse a full render proof; their old default-font masks are not
  claimed as faithful style evidence.
- [x] 2.4 Report unsupported Altium style/pose through existing loss policy without changing
  generated defaults or claiming native support.
  Proof: `uv run pytest tests/unit/backends/altium/test_drawn_fonts.py tests/unit/backends/altium/test_drawn_altium.py -q`.
  Passed 2026-11-02: 58 cases, including 22 new strict/explicit-loss checks in both
  native container forms. Each new font/label/pin justification/sheet-property pose
  refuses with existing FEN-7001 before a plan; explicit loss keeps a located
  altium.not-lowered info without a new code or hypothesis. False/zero fonts stay
  explicit. Existing drawn geometry/readback/review controls remain green; absent
  styles do not enter the new guard. All-map bytes are proved separately in 3.4.
  Altium remains unavailable; neither native acceptance nor native style support
  follows from these own-reader tests.

## 3. Compare and measure without concessions

- [x] 3.1 Compare explicit effects in level S and consume supported effects in scenes. Keep
  old default scene bytes, mask thresholds, missing-sheet behavior and junction detection.
  Compare native effective styles rather than canonical presence. Positive 1/499/500nm
  sizes and asymmetric axes must not round to zero and become default TEXT_SIZE.
  Proof: `uv run pytest tests/unit/model/test_drawn_font_compare.py tests/unit/view/test_schematic_fonts.py tests/unit/model/test_drawn_compare.py tests/unit/view/test_fidelity_masks.py -q`.
  Partial S checkpoint 2026-11-02: 68 comparison/source/model cases pass, including
  40 new controls (38 fail before the fix, native-default controls already pass).
  Every typed font member, label/pin centring and sheet-property pose is observed;
  actual written target9/10 extraction normalizes equivalent defaults before S.
  The check remains backend-independent with unchanged result fields and absent-
  style behavior.
  Supplement: 99 API/CLI/import-graph cases pass; the two initially cache-skipped
  public-project cases pass when rerun against the declared offline cache (2/2).
  Completed 2026-11-02: the exact four-group Proof passes 154 cases. All 98 new
  scene controls pass (the first 77 were red), plus 114 legacy source/view proofs.
  Separate height/width and justification use existing scene keys; 1/499/500nm
  refuse, 1µm stays small. Visible explicit nonzero thickness, true bold/italic,
  face or mirror refuses with FEN-3004 before a default-font mask can pass.
  Hidden field styles remain retained/unrendered. Four native style controls
  prove exactly 1–7/S, then require the full proof to refuse unsupported rendering.
  All 22 complete default authored scene maps remain byte-identical (421,823
  bytes); source comparison thresholds, text envelopes, sheet matching and
  junction guards are unchanged. This is not native glyph-raster equivalence.
- [x] 3.2 Add original CC0 all-nine-level controls with routed copper, source-byte preservation,
  planted font/text differences and removed-junction negatives; declare fixture licences/manifest.
  Proof: `uv run pytest tests/fidelity/test_drawn_fonts.py tests/residue/test_library_items.py -q`.
  Passed 2026-11-02: 8 cases, comprising six fidelity controls and two residue
  checks. Both authored target9/10 hierarchies and the native free-text/pin-font
  retention control prove all nine equal with an actual matched track. Each
  planted font/text/junction fault first has a passing full control, then leaves
  1–7 equal and makes S/8 differ with accepted empty and source bytes unchanged.
  The removed 2.54mm endpoint marker is electrically redundant; original needed
  junctions remain. Only original CC0 temporary data is generated, using already
  registered authored inputs; docs/evidence/drawn-fonts.md records provenance and
  why no new versioned-CAD manifest row is required. No manual fixture changes.
- [x] 3.3 Measure supported effect forms with the installed native CLI as a subprocess, using
  own authored inputs and exact SVG/raster/version receipts. Do not infer other versions.
  Include asymmetric H/W on all typed surfaces, native absent/false/true bold/italic,
  thickness zero/absent, and missing/empty/explicit label/pin justification. Unproved
  or unrepresentable native states refuse rather than gaining invented false tokens.
  Proof: `uv run pytest tests/kicad/schematic/test_drawn_fonts_oracle.py -q`;
  record actual `kicad-cli --version` and the export commands/artifact hashes.
  Passed 2026-11-02: 27 native cases / 94 actual SVG exports on CLI 9.0.2, all
  source bytes unchanged, including actual model-font lowering. Own XDG config/
  data/runtime/cache/state isolate every call; --version receipt has empty stderr.
  All eight typed surfaces prove H/W, four label/pin angles distinguish missing/
  empty/left/right justification, and flags/zero-thickness defaults compare by
  full glyph groups/styles with multiplicity preserved. Actual Inkscape 1.4
  rasterisation at150dpi gives 919 differing RGBA pixels for wide/tall controls;
  SVG/PNG/pixel/command/version receipts live outside core. No dependency added.
  Old 15/10/84 probe receipts remain historical; exact 9.0.9/10.0.6 CI, GUI saves
  and general native-glyph/scene agreement are not established by this task.
- [x] 3.4 Prove all 75 existing maps unchanged and compare complete planned maps against the
  immutable entry cut; never refresh the committed byte table for this change.
  Proof: `uv run pytest tests/unit/test_build_bytes.py -q`; record same-seed/timestamp
  full planned-file-map equality against `695dee0f` outside the checkout.
  Passed 2026-11-02: literal pytest Proof 76/76 (75 rows plus coverage), with the
  byte table untouched. Independent actual API captures on immutable 695dee0f
  and signed b548fa46 use the same authored inputs, output paths, seed1 and fixed
  timestamp. All 75 complete row maps match exactly, including every error reply
  and both excluded version files: 65 successful maps / 1,172 files and ten
  existing strict target refusals. No output folder or original input changed;
  source/table hashes and full maps are retained outside the checkout.
- [x] 3.5 Rerun the four external strict import/review/full-proof diagnostics on a signed core
  checkpoint. Preserve original payloads, acceptances and every remaining difference.
  Proof: four recorded `fenolite import --dry-run`, reviewed `--confirm --plan`, and
  `fenolite verify-source --json` invocations with input/core SHAs and per-level results.
  Dependency note 2026-11-02: root is assembling the next clean combined model0
  cut with the contextual source fix and signed font stack. Run the external
  replay on that exact union after publication; it must not delay the independently
  proved checkpoint. Guide/static work proceeds meanwhile under root's instruction.

  Maintainer-host continuation 2026-11-02 on clean signed model-0
  `1918e63214a7d0123e1f5fa8ef095c73fd2e1472`, without a push under the
  maintainer's local-only instruction: all 24 original native input digests
  verified, four real strict dry imports reviewed/confirmed by plan ID and all
  280 confirmed files match their plans. All 958 authoritative board files stay
  byte-identical. Video now passes all 1–8/S levels with no accepted difference.
  ECC83 has one 72-pixel level-8 finding; sonde retains two root-name missing
  panels. Coldfire preserves explicit bold and now refuses an unfaithful
  default-font mask at `in_out_conn.kicad_sch:text[Volt].effects` (exit 3),
  rather than claiming measured levels. No loss/tolerance/accept flag was added.
  Actual raw replies and the external library report retain all outcomes.

## 4. Teach and coordinate the final model boundary

- [x] 4.1 Document the typed fields, text authority, supported effects/defaults and refusals;
  add tested guide examples and regenerate affected public/schema/guide surfaces with owners.
  Proof: `uv run python tools/gen_agent_guide.py --check`;
  `uv run pytest tests/unit/agent/test_pages.py tests/unit/test_schema_drift.py -q`.
  Passed on clean signed `1918e632`: the exact guide/schema selection passes
  120 tests (6.70 s), and the generated guide check passes. Typed properties,
  code-owned text and unsupported-style refusals are documented; final model-0
  recapture and model-1 activation remain task 4.2.
- [x] 4.2 Root recaptures the actual combined final model 0 and redoes the 1.0 transition from
  that surface; retain the immutable 695 capture as history.
  Proof: recorded clean signed source/dataclass/ext/schema/CLI/package/byte receipt and
  focused c0216/c0217/c0218 checks on that exact replacement cut.
  Done 2026-11-04: c0218's `transition-proof.json` recaptured the combined final model 0 at
  7c1789ae, which contains this change's model work: 75 rows, 1137 files, the only difference
  `meta.schema_version` 0 to 1.0, no native or other canonical byte changed; 955 model/migration and
  355 guide/surface/capabilities/schema tests passed. On 2cf0c378 `tools/model_review.py` gives the
  same 175 dataclasses and 1251 fields with identical types and defaults (only reader lists differ);
  the only later model commit is c0218's own migration.
- [ ] 4.3 Run the serialized root-owned full gate and exact-head required 9.0.9/10.0.6 CI jobs.
  Proof: complete successful gate log and required CI job receipts for the recorded commit.
  Local 9.0.2 and CLI exports cannot close this task or any literal GUI-save requirement.

## 5. Close only proved work

- [x] 5.1 Run focused tests, static/format/types, generated checks, strict OpenSpec and residue.
  Reconciliation plan (2026-11-04): bind the unchanged selected sources to the
  retained successful fast22 on signed13ff795e; retain native observations at
  their recorded sources and versions. Run missing generated freshness, strict
  OpenSpec and private-list residue checks only. Do not rerun tests/CAD or close
  the separate final-model transition (4.2), exact-head CI/full gate (4.3), or
  archive this change.
  Proof: affected pytest selectors above; `uv run ruff check .`;
  `uv run ruff format --check .`; `uv run pyright src`;
  `uv run python tools/residue/scan.py`;
  `npx -y @fission-ai/openspec validate c0326-drawn-font-preservation --strict`.
  Integration inspection 2026-11-02: the native-font helper delegates to the
  existing schematic/drawn evidence; the versioned private style helper declares
  owned extension records rather than native syntax. The matrix is regenerated,
  and an unregistered illustrative hypothesis stem in design prose is reworded.
  No evidence level is promoted or native/full/remaining-style task closed.

- [x] 5.2 Update evidence labels and task receipts with exact native versions and remaining
  independent findings; leave unavailable native/manual/full gates open with reasons.
  Proof: `uv run python tools/gen_evidence_matrix.py --check`;
  review evidence statements against recorded subprocess/CI receipts.
- [x] 5.3 Update the single Unreleased entry to describe only implemented/proved behavior.
  Proof: `git diff --check`; verify exactly one c0326 entry and the signed clean commit.

## Maintainer-host native continuation — 2026-11-02

Native KiCad 10.0.6 initially reports two font-oracle failures: direct CLI
export creates a project-local `.kicad_prl`, then the failed baseline sample
leaves a directory that breaks the next parameter. c0319 task 1.22 retains
exact original and copied input hashes, exports an exact copy and records
only the native-created local settings output. All 28 cases pass, including
an independently planted failed-export/retry control. No style or pixel
assertion changes and no GUI or exact-head CI success is inferred.

## Measured field-boundary and documentation follow-up — 2026-11-02

Task 4.2 remains open after its first actual later-source capture: clean de6c6f2f
has 174 dataclasses / 1244 fields / 40 fixed extension keys and 20 active v0
schema digests. All 75 complete example maps (1172 files, ten strict refusals)
match the prior model-0 capture; no byte table changes. Prepared model-1
review deltas explicitly retain fonts and sheet-property carriers, with Step
metadata separately absent in model 0. No model-1 activation is claimed.

Tasks 5.2/5.3 pass: the evidence-matrix freshness check and 52 focused
hypothesis/release-record cases (26.97 s); exactly one c0326 Unreleased entry
records actual behavior. Evidence documentation now distinguishes measured
10.0.6 font exports (28 passed, 45.71 s), newly available Altium with unproved
compile/save gates, and c0330's separate root-identity repair. Labels stay at
their existing scope; no native/general/full-CI promotion. Private-list residue
passes with zero hits in 6397 files and sixteen existing waivers. The complete
fast gate on clean de6c6f2f has two failures: the known Mac byte discrepancy
and the older root-filename witness, now reconciled by 25 focused passing
font/root/fidelity cases. Task 5.1 and complete required gates remain open.


Local gate reconciliation — 2026-11-04: task5.1 is complete in its local
scope on signed13ff795e plus this documentary receipt. The retained exact-source
fast22 passed22616 tests,52 explicitly recorded skips and every Ruff/format/types/
private-residue stage. Its completed quiet collection includes all22 local
pytest modules above; none appears in the complete skip summary. This is coverage
by collection/completion, not individually printed PASSED node receipts. No test
was repeated for this reconciliation. Current runtime/tests/tools/configuration
remain unchanged from that exact source.

Fresh guide, schema and evidence-matrix checks pass without rewriting generated
files; OpenSpec1.3.0 strict and both complete-tree/staged private-list residue
checks pass. The matrix initially stopped for the new dev-only environment's
missing optional pyclipper; frozen dev+geo preparation resolved that environment,
then the unchanged check passed. Retained native9.0.9 observations have32 nominal
font-oracle PASSED cases at985f59a1 (including four later c0337 stroke controls);
font drivers and the listed font/model/codec paths are unchanged through13ff795e.
The historical10.0.6/28-case export receipt remains separately scoped. No native
call, GUI-save claim, evidence promotion or exact-current CI result is inferred.

See local-proof-20261104.json for source, selected-file and retained-log seals.
Tasks4.2 and4.3 remain open, and this change is not archived. The older failed
gates and independent external findings above are preserved as historical facts.
