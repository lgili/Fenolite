# Design: Expand Fenolite's standard component catalog

## Shape

Continue the pure-data `fenolite.catalog` architecture from c0075. Add definitions as small,
reviewable family packs with stable `Fenolite:` IDs. Each symbol expresses a generic electrical
role; each footprint expresses a reusable package shape. Catalog metadata records family, package
category where applicable, a concise summary, evidence label and registered public source IDs.

Initial coverage for this change includes:

- **Passives:** resistor, capacitor (ceramic, electrolytic and film/polarized forms), inductor/choke,
  and ferrite bead symbols; retain and extend standard chip lands.
- **Discrete and optoelectronic semiconductors:** generic diode, Zener diode, LED, bridge rectifier
  and optocoupler symbols where a source supports the pin identities.
- **Protection:** fuse, varistor/MOV and surge-suppressor symbols, plus reusable standard package
  geometry where public mechanical data supports it.
- **Power and control ICs:** generic operational amplifier/comparator, linear regulator,
  offline-switching power controller, microcontroller, and power-module symbols. Pin maps are
  generic only when the source defines a generic standard; part-specific pin maps remain distinct
  sourced definitions or project-authored symbols.
- **Electromechanical interfaces:** connector and terminal symbols, including pin-header,
  quick-connect tab and ring-terminal package styles, with reusable footprints where public
  mechanical data supports the geometry.

The corresponding footprint pack covers the common standard body styles required by these families:
chip passives, small-outline and leaded ICs, transistor and diode packages, through-hole passive and
protection parts, and common pin-header/terminal styles. Exact variants are added only where their
dimensions, pad numbering, pitch, drill and relevant graphics can be represented by existing model
primitives and supported by public sources. A footprint that needs a bespoke mechanical interface,
unusual pad stack, formed-lead pattern or custom high-power module geometry stays project-authored
unless a separate generic package specification is justified.

No private board file, BOM row, designator, value, MPN or copied CAD definition is a catalog source.
Board usage is a coverage checklist only; catalog facts and geometry are independently authored and
publicly sourced. This keeps the implementation reusable and preserves the clean-room boundary.

## Resolution and compatibility

Definitions remain compatible with c0075's API, `Fenolite:` namespace, stable sorting, CLI display,
offline build resolution and exact-ID project override. Prefer adding new entries over changing an
existing ID's meaning. Correcting an existing definition requires an evidence note and focused
regression test. The catalog remains standard-library-only and does not invoke KiCad or another CAD
application to obtain library data.

Footprint selection remains explicit on the part. A generic symbol does not silently choose a
package, and electrical pin-to-pad maps stay explicit and validated by the existing build path.
Library entries describe geometry and generic symbol semantics; they do not assert component
qualification, package interchangeability, thermal performance or fabrication suitability.

## Evidence and validation

- Register every public source in `docs/evidence/sources.md` and map source IDs to catalog facts in
  `docs/catalog/sources.md`.
- Cite pin identity, polarity and package dimensions only to sources that state those facts.
- Mark package lands `INFERRED` when their dimensions are not explicitly recommended by the cited
  source, and preserve that label across serialization and readback.
- Test every entry for stable IDs, source registration, evidence metadata and deterministic order.
- Test representative symbol and footprint serialization/readback and offline builds for each
  supported package geometry family.
- Keep build evidence separate from physical-design qualification.
- Check a manufacturer land-pattern drawing for every shipped footprint before assigning pad
  rectangles. Use the package's top-view pin numbering and orient each pad's long axis toward its
  lead. Keep different-number copper separated, make the courtyard enclose all copper, and put the
  body drawing on fabrication rather than running silkscreen through pads. A split same-number pad
  for SOT89's tab and center lead forms one terminal and is documented as an inferred approximation.
- Author schematic graphics as restrained functional drawings: consistent 0.254 mm body strokes,
  centered shapes, aligned connection points and enough space for pin labels. The pin vector from
  its connection point points inward and touches the body or terminal graphic. Generic passive pin
  names may be hidden where numbers and polarity marks convey the same information. Diodes use
  anode/cathode names, polarized capacitors identify the positive side, and amplifiers distinguish
  non-inverting/inverting inputs and positive/negative supplies. Conceptual IC blocks retain their
  explicit non-device-pinout scope. Visual geometry is Fenolite-authored; public drawing conventions
  and component functional facts are guidance, not source files to copy.

The generic resistor uses the familiar zigzag variant selected by the user. Its first and last
vertices meet the pin stems at the two ends. The Zener cathode graphic is a connected bent path:
the vertical center section stops where each angled terminal begins, so no redundant straight bar
continues behind the hooks. Pin numbers, names, polarity and evidence level remain unchanged.

The optocoupler has a legible conventional LED silhouette on its input side, two light-direction
arrows across an empty isolation gap, and a phototransistor on its output side. Internal wire paths
join the A/K and C/E pin stems without an overlapping barrier or false electrical connection across
the optical gap. Generic header symbols use separate square outline contacts with one lead per
contact. The single-circuit terminal symbol remains its own circular terminal form. Polarized and
electrolytic capacitors retain the marked positive plate and draw the opposite plate thicker; the
weight contrast is a user-selected visual convention, not a package or construction claim.

## Coherent symbol gallery review

The user supplied schematic page images as visual feedback. They guide broad presentation choices
only; no proprietary circuit fact, exact vector coordinates, private artifact, or component-specific
pinout enters the catalog. A complete review spans all 26 shipped symbols through their shared
 family drawing paths. Retain the user's later explicit preferences where sample images differ:
the resistor remains zigzag and the optocoupler retains a recognizable internal LED.

Use a compact common visual grammar: passives with centered strokes and clear lead junctions;
smooth coil and fuse contours using the existing line primitive; protection marks that do not
obscure the leads; a grouped connector housing with one inset square contact and one exterior pin
stem per circuit; and conceptual IC rectangles without decorative internal signal drawings. Keep
functional pin labels as the information inside IC blocks, with enough space around them. The
single terminal is a square socket form. Amplifier supply stems meet the triangle boundary, with
small input polarity signs inside. All changes remain independently authored and `INFERRED`.

The full image review also exposed three missing generic symbol roles: a two-winding common-mode
choke, a bidirectional two-electrode gas discharge tube, and a common-cathode dual LED. The choke
has two electrically separate winding paths with a magnetic-core cue. The discharge tube has two
separated opposing electrodes inside an enclosure. The dual LED has two individually driven anodes
and one visibly shared cathode. Public manufacturer documents support only the functional topology;
Fenolite authors all graphics, symbolic pin numbers are conceptual, and no package or footprint is
inferred. The common-cathode variant does not stand in for common-anode or antiparallel dual LEDs.

## Target of 100 footprint variants

The inventory in `docs/catalog/target-100-footprints.md` is the c0076 completion target. It
contains exactly 100 distinct variant slots, including the 14 definitions already shipped on
this branch. A fixed public-board snapshot provides an observable usage proxy; the selection adds
package variants that make those frequently observed families reusable across ordinary designs.
This is a curated coverage target, not a universal market ranking. The source sample and
normalization limits are documented alongside the inventory. Do not use its footprint geometry,
names as CAD definitions, private-board facts, or third-party library files.

Resolve each provisional slot to an unambiguous final `Fenolite:` ID only after checking an
official package drawing. In particular, pin count alone does not fix body width, lead span,
pitch, exposed pad, mounting tabs or drill details. Treat aliases with identical lands as one
footprint, and use separate IDs where those dimensions differ. A manufacturer-specific connector
gets a part/series-qualified ID; a generic header can use pitch and circuit count. Preserve exact
lookup and explicit assignment; a catalog symbol never selects a footprint implicitly.

Implement in small family batches. Each entry needs a source row, body and suggested-land facts,
numbering and orientation, copper/mask/paste/drill geometry, fabrication and courtyard outlines,
clearance checks, KiCad readback and a visual preview. If an official source supplies only body
dimensions, author a conservative land pattern with `INFERRED` evidence and state that limitation.
If the model/writer lacks a necessary primitive, specify and implement that capability before
shipping the affected entry. No footprint may be counted complete merely because an ID appears in
the inventory. The 100-entry goal is complete only when all entries are discoverable and pass
their focused proofs and the repository checks required before merge.

## Additional 20 symbol drawings

The expansion inventory in `docs/catalog/target-20-symbols.md` defines exact names, conceptual
pin roles and public references. All coordinates and arrowhead vertices are authored by Fenolite
in integer nanometres; no CAD definition is copied. Numbering is deliberately independent of
manufacturer package numbers and footprints remain unassigned. Use the existing line, polygon,
rectangle and circle primitives, including outline arrowheads. No new graphics model is required.

NPN/PNP differ by the emitter arrow. Enhancement MOSFETs have three separate channel segments,
an isolated gate, a source/body connection, and oppositely oriented body diodes for N/P devices.
The generic IGBT does not assert an integrated diode. SCR and TRIAC gates enter the cathode/MT1
side. Schottky hooks form one continuous cathode, and TVS terminals are non-polar.

Use the selected zigzag resistor path for potentiometer and thermistor motifs. The wiper ends
on that path. Vector coefficient marks distinguish NTC and PTC without adding text primitives.
Contacts show the unactuated state: SPST and pushbutton open, SPDT/relay COM connected to NC
and separated from NO. The four-terminal pushbutton exposes two common pairs, supporting explicit
mapping to the two catalog tact-switch variants. Transformer windings remain electrically
separate; phase dots are explicitly conceptual. Photodetector light arrows point inward.

A deterministic native SVG review tool renders the actual model, preserves background-filled polygons,
shows role names where useful and splits the gallery into review pages. Focused tests cover
all 49 symbols, family-specific topology, offline discovery and an explicit device pin-map build.
Keep evidence `INFERRED` for independently authored generic geometry and numbering.

## Dependencies

This change builds on the completed catalog and graphics path (c0075), authored footprint and
symbol definitions and KiCad writers (c0055, c0056, c0008). No new backend or CLI dependency is
required. If a requested package needs unsupported geometry, split that geometry support into its
own OpenSpec change instead of approximating or silently omitting it.

## Budget

Estimate: 10 design-days for the first complete family pack, source register and tests. Any package
geometry outside the existing model/writer subset is a separately estimated follow-up.

The micro-B candidate is resolved to Würth 629105150521 with its public readable drawing; it is not an alias for the provisional Amphenol part. The existing c0056 slot/NPTH model supports its mixed mounting features without a new geometry primitive.

## Local dev integration and closure

On 2026-10-05 the maintainer authorized one local squash commit on `dev`, including the archive and normative specification update, without a GitHub push. Preserve the current dev changes, including normalized CLI output paths. Validate the combined tree with focused catalog/build proofs and `make check-fast`; the maintainer defers the full suite to a later batch of CI. This explicit instruction replaces the earlier premerge/full-suite task for this closure. No successful full-suite CI run is claimed by the archive.
