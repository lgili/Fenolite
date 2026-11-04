## Context and measured boundary

Entry source is clean model-0 cut `695dee0f1bdf2cff066edad0220c63cf064ae0a2`.
The external four-conversion diagnostic checkpoint is `4932137d`; all four fresh
imports and reviewed confirmations succeed, levels 1–7 and S are equal, accepted
differences are zero, and level 8 still fails. Neither those external payloads nor
the entry source is changed by this proposal.

Read-only diagnostics of 2026-11-02 distinguish three causes:

1. An original CC0 one-resistor project with no power symbol and identical source
   and written field text changes font size from 250,000 nm to 1,270,000 nm. Its
   actual strict import/confirm/build proof reports 1–7/S equal, 8 different,
   1,248 extra mask pixels and no acceptance. It isolates font loss.
2. A public conversion has 25 changed visible text primitives. Production masks
   have 24,831 extra pixels; a power-only diagnostic subset has 488. The latter
   comes from visible power-field size, not hidden reference metadata. Renaming
   nine hidden power references changes no mask row. Native 9.0.2 exports of source
   and built scratch copies load successfully; installed Inkscape 1.4 rasterizes
   both at 150 dpi, with 20,991 raw differing pixels. These are native CLI exports,
   not a GUI save or the production mask renderer's exact glyph oracle.
3. One public root file contains a space while its emitted design name uses an
   underscore. Actual level 8 reports two missing scenes. Directly pairing those
   masks for diagnosis still finds 3,202 source-only and 870 built-only pixels;
   filename matching alone would not make the conversion pass. No scene-identity
   normalization is proposed here.

Detailed scripts, hashes, scenes, SVGs, rasters and receipts stay outside the core
checkout under the validation receipt named `level8-diagnosis`. The original CC0
counterexample may become a core fixture after review. Public-derived artifacts
retain their source licence and never become core test material.

## Existing carriers and the actual omission

`model.drawn.DrawnField` holds name, point, rotation, justification and hide only.
`DrawnLabel` and `DrawnPin` lack both font and justification. `DrawnSheetRef` lacks
poses for `Sheetname` and `Sheetfile`. Power poses already carry `DrawnField` values;
adding another reference field to `DrawnPower` would not fix this failure.

`FootprintField` and `Text` are board entities with ids, layers and board semantics.
`presentation.SheetText` is a worksheet item, with its own position and text. None
is a genuine reusable font value. `core.coords.Size` is already the correct pure
width/height carrier. New typed model content is therefore necessary.

`backends.kicad.drawn._field_ext` lowers fields through private `sch.FieldPose`.
The `drawn` extension bag contains repeated `field` pairs whose string payload has
six U+001F-separated parts: name, x, y, rotation, justification, hide-as-0-or-1.
The writer's `_property` calls `_font`, which always writes `TEXT_SIZE` on both
axes. Native `symbol_field_poses` does not read the source font. Fixing only the
TOML codec, the renderer, or hidden power names leaves this loss intact.

## Decisions — 2026-11-02

### Real optional fields, with one shared font value

Decided 2026-11-02 under the user's delegated recommended decisions, after the
coordinator's review and independent read-only review of `d76d6ffc`: add frozen,
hashable `DrawnFont` in
`fenolite.model.drawn`, containing the following optional fields in this order:

| field | type | validation and meaning |
|---|---|---|
| `size` | `Size \| None` | Both axes are positive integer nm; `w` is native WIDTH and `h` native HEIGHT. Native `(size H W)` maps to `Size(w=W, h=H)` and writes `(size h w)`, with asymmetric schematic probes on every surface. |
| `thickness` | `Nm \| None` | Nonnegative integer nm. Canonical data preserves zero separately from absence; native effective semantics require an authored schematic probe before support is claimed. |
| `bold` | `bool \| None` | Canonical/TOML preserve absent, explicit false and true; integers are not booleans. The native target need not represent three states. |
| `italic` | `bool \| None` | Same canonical presence rules as bold, with target-probed native effective behavior. |
| `face` | `str \| None` | Nonempty font name without control characters; never a font path, binary font or an instruction to fetch one. |

Each subfield defaults to `None`. Reject an entirely empty `DrawnFont`, so the
single absence representation is `font=None`. An omitted subfield retains the
existing created-writer default for that attribute. Explicit `False` and zero are
not removed from canonical/TOML as though absent. This presence contract does not
promise three native states or justify inventing `(bold no)`/`(italic no)` tokens.
Native writing, extraction and level-S readback use the effective style established
by a probe for the target, or refuse when it cannot be represented. Test omitted,
false and true separately against the same source defaults. Probe thickness zero
versus omitted thickness on schematics before selecting its effective mapping.
No float, implicit decimal rounding or bool-as-nm is accepted. Existing rotation
restrictions and integer microdegrees remain.

Native continuation, Decided 2026-11-02 from actual 9.0.2 subprocess observations:
canonical false/zero stay explicit in TOML, while native omitted/false flags and
zero/omitted thickness share an effective default. Missing/empty font/effects do
not inherit the changed library Value style in the authored field controls. Keep
unsupported positive sub-µm native fonts as explicit refusals rather than a
default-size fallback. These version-scoped measurements do not close exact CI.

Append `font: DrawnFont | None = None` to `DrawnField`, `DrawnLabel` and `DrawnPin`.
Append `justify: str | None = None` to labels and pins. `None` preserves their
existing writer-selected anchor; an explicit empty string means centred. Reuse
the existing justification vocabulary and reject unsupported combinations when
the native target cannot carry them. An omitted native `justify` must not simply
extract to `None`: the scene reader currently treats omission as centred, while
created labels select a role-dependent left/right anchor. Establish the native
meaning with asymmetric label/pin probes and map it to explicit centring or the
proved equivalent. Cover missing native justification, explicit empty/centred
justification, and explicit words on local/global/hierarchical labels and pins.
Do not replace the existing field `justify`/`hide` properties or their defaults.

Actual anchor continuation, Decided 2026-11-02: all 84 original 9.0.2 controls
support the same rule on local/global/hierarchical labels, four pin angles and
sheet properties: missing native justification equals explicit centring, and
differs from left/right. Extract omission as `""`; extract an explicit native
anchor matching the legacy role as `None`. This retains old default drawing
bytes while preserving authored native centring. Asymmetric size probes confirm
the H/W order on each surface. No native GUI action or other version is implied.

Append `fields: tuple[DrawnField, ...] = ()` to `DrawnSheetRef`, restricted to the
unique names `Sheetname` and `Sheetfile`. It carries their source pose, font,
justification and hide state, but no text. With no poses the current above/below
anchors and fonts remain byte-identical. An absent pose for one mandatory sheet
property retains that property's existing default.

### Scope across every text-bearing drawn item

| surface | c0326 treatment |
|---|---|
| Normal and per-unit symbol properties | Preserve existing pose/hide/justification plus the typed font. Text remains code-owned. |
| Power-symbol visible fields | Use the same field path; retain the existing hidden-reference and generated-name behavior. |
| Local, global and hierarchical labels | Preserve both font axes, thickness/style and explicit justification. Text and electrical meaning remain unchanged. |
| Sheet pins | Preserve the same font and explicit justification independently of connection angle/point. |
| Sheet name/file properties | Preserve field poses/effects; text comes from the existing sheet reference and resolved output filename. |
| Free text, graphic symbols, native library text and pin name/number effects | Existing native slots already preserve these. Add retention/round-trip controls; do not invent a second typed projection or store font data in opaque placeholders. |
| Title-block and worksheet text | Existing worksheet model/writer; no unrelated change. |

Parse only publicly documented and authored-probed effect forms. A source
attribute outside the supported set, a repeated conflicting effect, non-integral
size or an unavailable target form must produce the existing closed
extraction/import loss/refusal route with a precise locator before any plan is
staged. In particular, label/pin hiding, unknown font children, embedded-font
payload requirements or unsupported text-variable behavior cannot silently turn
into ordinary visible stroke text. Do not add a loss-acceptance switch or a new
FEN code unless the existing error contracts prove inadequate.

The scene reader currently consumes only one size axis and creates a default
stroke-font primitive. Audit and test both axes, thickness, bold, italic and face
at that boundary. Preserve the existing default scene bytes. Carry supported
style accurately; when the renderer cannot represent a requested style, retain
an explicit unsupported-render diagnostic rather than reporting a faithful mask
from a default-font substitute. In particular, `_num` rounds integer nm to scene
µm and the current `_effects` fallback replaces a rounded zero with `TEXT_SIZE`.
Positive sub-µm sizes must never become 1.27 mm. Either retain an honestly proved
representation at the existing boundary or report/refuse unsupported rendering
before a mask is accepted; include 1 nm, 499 nm, 500 nm and axis-asymmetric
controls. The model remains exact even if a renderer has a coarser limit. Do not
redefine mask dilation, pixel limits, sheet identity, glyph acceptance or junction
geometry to obtain equality.

Renderer boundary, Decided 2026-11-02 under the reviewed delegated recommendations:
use the existing `sz`/`gw` primitives for separate height/width and existing text
justification. Preserve all old default scene maps. The present stroke renderer
and envelope masks cannot faithfully express visible explicit nonzero thickness,
true bold/italic, font faces or text mirroring; refuse them with existing
FormatError/FEN-3004 before any default-font mask is accepted. Retain hidden-field
native effects without drawing them. This is an honest implementation limit,
not a loss acceptance or native glyph-identity claim. Original CC0 positive full
controls use the supported size/justification subset. Separate controls retain
each other native style, prove exactly levels 1–7/S, then require the full proof
to refuse rendering. No command flag, reply field or comparison threshold changes.

### Code-owned text and the footprint disagreement

Reference and Value always come from the component and lock. `DrawnField` gains
no string value and cannot override either. Power display text continues through
the existing net/symbol rules. Sheet name/file text comes from their existing
typed fields, not a style payload.

The inspected original public PCB already has a logical
`Component.lib_footprint_ref` different from the visible schematic Footprint
property; `Component.footprint_definition_ref` is empty. The rebuilt circuit
retains that same logical ref. The importer correctly uses the separate
definition ref only when its vendored lookup differs. Thus this is an actual
source PCB/schematic disagreement, not proof that a definition selector was
mistakenly printed. Do not put a reserved Footprint value into generic properties
or add a generic text override to hide it. This font-only packet retains the
code selector and the fidelity finding. A separate semantic decision and
authored counterexample are required before preserving conflicting visible
Footprint text; c0326 does not promise all four public proofs will become equal.

### Canonical and private-bag compatibility

Keep schema id `fenolite.drawn-schematic.v0` during model 0. Extend its closed key
sets deliberately: `font = { size = [width, height], thickness = ..., bold = ...,
italic = ..., face = ... }`, with only present members written, exact shortest
decimal millimetres and deterministic member order. Labels/pins gain optional
`justify`; sheet references gain `fields` using the existing field-table shape.
Old readers correctly refuse unknown fields rather than discarding them.

An old canonical drawing with no font/new poses must read and write the exact
old bytes. Dataclass additions are appended with defaults; canonical JSON omits
`None` and the empty sheet-field tuple through the existing default-omission
rule. Do not change that rule, other keys, type coercions or id derivation.
Every one of the 75 committed example/target maps in `tests/data/build_bytes.json`
must pass unchanged; do not remeasure the table for this default-preserving fix.
Also compare complete planned-file maps against the immutable entry source so
the guard's existing version-file exclusions do not conceal a writer change.

Extend private `FieldPose` with the optional font at the end. Continue to emit
every legacy `field` payload in its exact six-part form and original order.
When all fonts are `None`, the entire old extension bag is identical. For an
explicit font, append a separate `field-font-v1` pair under the existing `drawn`
namespace: a deterministic compact JSON object containing its field name and
present typed font members, with integer nm. The legacy pose payload is not
lengthened. For labels and pins, use the corresponding versioned font payload
on their existing entity bag; their explicit justification also gets a separate
versioned pair. Sheet-property poses use the same field-pose adapter.

The adapter reads old bags and new versioned records, attaches fonts only to
matching poses, and rejects malformed JSON, unknown members, duplicate/conflicting
records, orphan field styles and invalid units. New keys are backend lowering
adapters for actual typed fields, not an alternative public storage format or an
opaque string workaround. Default generated symbols, labels, sheet pins and
properties retain their existing names, ids, ordering, `TEXT_SIZE` and bytes.

### Evidence, Altium and model-version coordination

Reuse S-0001/S-0367 and the public facts already recorded in
`docs/formats/kicad/{board,schematic}.md`. The common font vocabulary is not proof
that every backend serializes it identically. Add original schematic effect
controls and measure each supported native form through the process boundary;
never inspect/copy vendor parser code or import GPL bindings. Register only
actually observed facts, retaining actual tool version and evidence labels.

KiCad extraction/writing is the implementation target. Altium must report each
new explicit font/pose it cannot faithfully lower using its existing
`altium.not-lowered` loss machinery, and strict conversion must continue to
refuse that loss. Existing default Altium bytes stay unchanged. Reuse the
existing `H-A-DRAWN-WRITE` boundary; add no new Altium hypothesis stem and no native Altium
or paid/manual proof. The maintainer reported no licensed Altium environment on
2026-11-01. CLI exports and authored text fixtures are not GUI-save evidence.

This genuinely changes the model surface before 1.0. Coordinate with c0216,
c0217 and c0218 owners before generated schema/public-surface updates. No CLI
payload addition is planned. Preserve the immutable 695 model-0 receipt as
history; root must make a new actual final-0 dataclass/ext/schema inventory and
byte capture after the combined change, then redo the 1.0 transition from that
real surface. Do not edit private v1 trees or bless a stale capture.

## Files and public API

| files | planned responsibility |
|---|---|
| `src/fenolite/model/drawn.py` | Public `DrawnFont`; optional fields above and validation. |
| `model/_drawn_text.py`, `lens/drawn.py`, `schemas/fenolite.drawn-schematic.v0.json` | Closed, deterministic codec/schema; default omission. |
| `backends/kicad/sch.py`, `backends/kicad/drawn.py` | Native effects extraction, versioned private adapters, complete created-sheet emission. |
| `checks/equivalence/drawn.py` | Compare explicit font/effects as actual drawn content at level S. |
| `view/kicad_schematic.py` and directly required view helpers | Consume supported native effects honestly without changing mask acceptance. |
| `importer` source/drawn integration only where needed | Preserve effects before strict self-check; refuse unrepresentable effects before staging. |
| `backends/altium/drawn.py` | Existing explicit loss boundary for unsupported new style. |
| Authored tests in model/lens/backend/importer/view/equivalence plus native schematic tests | Original CC0 controls, manifest declarations and strict positive/negative round trips. |
| `docs/drawn-schematic.md`, `docs/design-model.md`, format/evidence docs and a focused tested guide page | Teach supported fields, defaults, refusals and actual proof boundaries. |

Public API names remain under `fenolite.model.drawn`; no new `fenolite.dsl` helper
is necessary. Generated schemas/guide/public surfaces are regenerated from the
implementation after owner coordination, never hand-edited to force a match.

## Validation and risks

Independent checkpoint review follow-up — Decided 2026-11-02: reject noncanonical
justification whitespace in the model/private text adapter consistently with the
existing TOML reader. An accepted typed value must round-trip through its own
canonical text. This closes leading/repeated/tab whitespace without changing
`None`'s legacy anchor or explicit empty-string centring. Document the codec keys
already implemented while native lowering remains a separate pending task.

Independent exact-unit follow-up — Decided 2026-11-02: the shared drawn length
reader must scale decimal input by an exact integer ratio, independently of the
ambient Decimal precision. Multiplying before checking integrality had rounded a
long fractional-nm literal into an accepted integer; new font keys reused that
old helper. Reject the actual remainder, retain exact positive/negative lengths
and source locators, and add long-decimal/low-context controls before changing it.

Run focused model/codec tests before one writer surface at a time. Require the
CC0 size counterexample to pass all nine levels with actual copper, zero
acceptances and unchanged source bytes. Plant changed sizes/styles, mismatched
text and a redundant removed junction; they must still be findings. Compare
actual native SVG/raster outputs where tooling exists, recording exact commands
and versions independently from deterministic production-mask tests.

Public four-board reruns use scratch output and external source/provenance only;
record every remaining level-8 text/scene difference without promotion. Required
9.0.9/10.0.6 jobs, any literal GUI save, root-owned full gate and final model-0
recapture remain open until actually performed. Core dependencies remain empty.
The coordinator explicitly authorized implementation after these four review
clarifications are documented and strict validation passes. This records delegated
review, not a personal maintainer read-through, a native save or an application
measurement. Implementation proceeds in task order with signed module checkpoints.
