# Enclosures: the board for its box, and the box for its board

Status: **research, nothing here is implemented**. Date: 2026-10-30. Not legal advice; the licence and
copyright readings are INFERRED from the texts cited at the end.

The maintainer asked whether Fenolite should also produce the product's case: a 3D model good enough to

- (a) check the fit in Altium and KiCad;
- (b) send to a 3D-printing, CNC or moulding service;
- (c) choose a real off-the-shelf box first, and design the board to fit it from the start: outline,
  mounting holes, height limits, connector cutouts.

The short answer:

- **(c) is the most useful part and the cheapest.** It needs data and checks, not a CAD kernel, and most
  of the board-side machinery already exists.
- **(a) works today** with a small workaround in KiCad and a manual import in Altium.
- **(b) is realistic for 3D printing and for drilling panels of a purchased box.** A "mould-ready"
  design is not realistic for us. We can deliver a STEP that passed design-for-manufacture (DFM)
  checks, and the moulder finishes it.

## 1. Where Fenolite stands

What already helps:

- **Board shape.** `design.board(outline=…)`, `cutout()` and `slot()` describe any outline
  (`docs/dsl.md`, "Board").
- **Holes.** `hole()` and `tooling_hole()` make mounting holes. `Hole.intent` can carry
  `MechanicalIntent`: a key, a tolerance, a source and a status (`measured`, `estimated`, `proposed`)
  (c0096, `docs/design-model.md`).
- **Height limits.** `RuleSet.heights` holds `HeightLimit(area, max)` over named rule areas.
  `outward_height()` gives a part's height from its bodies, and `judge_heights` checks them (c0140).
  A box's "lid zone" is exactly this.
- **Placement frames.** `GroupRegion`, edge gaps, keep-outs per face and `MechanicalReservation` exist in
  the constrained placer (`docs/placement.md`).
- **3D output.** `fenolite export --step` runs `kicad-cli pcb export step --subst-models` and writes the
  board with the bodies of the parts whose models were found (`docs/exports.md`). `fenolite render
  --png` runs `kicad-cli pcb render`. `kicad-cli` 9 can also export GLB, STL, BREP, XAO, PLY and VRML.
- **A CAD-capable tool is already optional.** The viewer meshes STEP body models with `gmsh`, run as a
  separate program (c0193, `docs/viewer.md`). gmsh has an OpenCASCADE (OCCT) geometry kernel.

What is missing:

- No enclosure concept, no 3D geometry engine, no STEP writer.
- The Altium writer drops 3D model links (`altium.footprint-extras-dropped`, `docs/altium.md`).
- **Rules that apply:**
  - the core imports only the standard library;
  - extras are permissive and lazily imported;
  - copyleft code is used only across a process boundary (ADR-0004);
  - clean-room: nothing from vendors' files is copied in.

## 2. Prior art

| Tool | Licence | What it does | What it can't |
|---|---|---|---|
| **KiCad StepUp** (FreeCAD workbench) | AGPL-3.0 | Loads a KiCad board and parts into FreeCAD, exports STEP. Pulls the board edge into the FreeCAD Sketcher and pushes it back, so the outline can be drawn against an enclosure. | Interference checking is listed as "in progress" on the FreeCAD wiki. Needs FreeCAD and a GUI. The enclosure itself is modelled by hand. |
| **KiCad / `kicad-cli`** | GPL (tool) | `pcb export step\|glb\|stl\|brep\|xao\|ply\|vrml`, with `--board-only`, `--no-components`, `--component-filter`, `--include-tracks`, `--fuse-shapes`, `--min-distance` and more. KiCad 9 can embed 3D models in footprints and boards. | No enclosure object and no 3D collision check. To show an enclosure in KiCad, users attach its STEP to a dummy footprint (forum practice, INFERRED as the usual way). |
| **Altium Designer** | proprietary | Imports a STEP as a 3D Body in the PCB editor, embedded or linked (a linked file updates when the MCAD file changes). "Define Board Shape from 3D body" takes the outline from an imported enclosure. The Component Clearance rule uses 3D bodies, and Altium describes "component-to-housing" collisions found in real time. MCAD CoDesigner syncs with SOLIDWORKS, Creo, Inventor and Fusion. | Proprietary. Whether the Component Clearance rule checks *free* 3D bodies (the enclosure) is not stated plainly in the docs (UNKNOWN). |
| **Fusion (electronics)** | proprietary | "Push to 3D PCB", then insert the 3D board into the enclosure design. Or derive the board from a sketch of the enclosure. | No two-way update of the 3D PCB. Autodesk's documented workaround for the circular dependency is a third document holding the outline. |
| **tscircuit** | MIT | `<enclosure.fdm.box />`: a two-part printable box (base and lid with a friction lip) sized from the board plus clearances, with openings for the apertures the parts declare. Package `@tscircuit/create-fdm-enclosure`, version 0.0.7 (August 2026). | Very young. Only FDM, and no library of purchasable boxes found. |
| **atopile** | MIT | Nothing found about enclosures (UNKNOWN). | — |
| **JITX** | proprietary | Imports mechanical data (DXF, IDF, IDX…) to set a board outline, attaches STEP models to parts; full-board STEP export is UI-only in py-jitx 4.2.x (per its published agent skills). | No enclosure generation found (UNKNOWN). |
| **YAPP_Box** (OpenSCAD) | MIT | The best-known "box around a PCB" generator: PCB size, standoffs, cutouts per face, snap joints, labels. | OpenSCAD only gives meshes (no STEP). Settings are written by hand. |
| **Ultimate Box Maker** (Thingiverse 1264391) | CC BY-NC per a mirror of the page (INFERRED; the original page refused our fetch) | A parametric OpenSCAD box with front and back panels. | Non-commercial: **we cannot reuse anything from it**. |
| **SBC Case Builder + SBC Model Framework** | GPL-3.0 | Cases for single-board computers from a database of board models: shell, panel, stacked and tray styles, vents, fans; checks the board fits. | GPL, OpenSCAD, SBCs only. A good example of "board data → case". |
| **BOSL2** | BSD-2-Clause | A large OpenSCAD library (rounding, threading, attachments). | A library, not a box generator. OpenSCAD runtime. |
| **Protocase Designer** | free download, proprietary | 3D CAD from templates for Protocase's sheet-metal and machined enclosures, quoting and ordering. | Locked to the service. |
| **Front Panel Designer** (Schaeffer / Front Panel Express) | free download, proprietary | Front panels, enclosure parts and milled parts, ordered from the vendor; DXF export reported. | Locked to the service. |

What we take from this:

- Every serious ECAD tool does the **fit check** by importing a STEP.
- Two tools (Altium, StepUp) let **the enclosure drive the outline**.
- Nobody offers a **curated library of purchasable boxes as data** that drives the board, with a check
  (INFERRED: not found in this search).
- Generators (YAPP_Box, tscircuit, SBC Case Builder) only cover **printed boxes**.

## 3. Geometry engines

| Path | Licence | Fit with our rules | Notes |
|---|---|---|---|
| **CadQuery** | Apache-2.0 | extra, lazy | Pulls `cadquery-ocp`, `casadi`, `ezdxf`. Exports STEP, STL, 3MF, AMF, VRML, glTF. |
| **build123d** | Apache-2.0 | extra, lazy | 0.13.0, Python 3.11–3.14. Pulls `cadquery-ocp-novtk` plus scipy, sympy, ipython, requests, lib3mf and more. Exports STEP, STL, 3MF, BREP, glTF. |
| **OCP** (bindings under both) | bindings Apache-2.0; **bundles OCCT, LGPL-2.1 with the Open CASCADE exception** | **conflicts with ADR-0004 as written**: extras must be "permissive licences only", and LGPL is weak copyleft | Wheels for Windows, macOS and Linux on cp311–cp314. 47 MB (Windows) to 67 MB (macOS x86) per wheel (PyPI, measured 2026-10-30). |
| **gmsh** (subprocess) | GPL | **already allowed**: an optional external tool, run as a separate program | Its OCCT kernel does Box, Cylinder, Extrude, Boolean union, difference and intersection, Fillet and Chamfer. It reads STEP, BREP and IGES, and writes STEP via OCCT (the docs list the option `Geometry.OCCSTEPDescription`; INFERRED until tried). |
| **OpenSCAD** (subprocess) | GPL-2.0 (CGAL exception) | allowed across a process boundary | CLI exports STL, OFF, AMF, 3MF, DXF, SVG, VRML, CSG… **no STEP**. Not enough for the Altium or KiCad fit check. |
| **FreeCAD `freecadcmd`** (subprocess) | LGPL-2.1+ | allowed across a process boundary | Complete, but a large install. Scripting it means writing FreeCAD Python that runs in its interpreter. |
| **Our own STEP writer** (stdlib) | ours | core | See below. |
| **STL / 3MF writer** (stdlib) | ours | core | STL is trivial. 3MF is a ZIP of XML; the 3MF core specification is free and BSD-2-licensed (3MF Consortium, `spec_core`). Only for meshes we already have. |

### Writing STEP ourselves

STEP files are ISO 10303-21 text. They are encoded against an EXPRESS schema (AP214 or AP242).

- **Access to the standard:**
  - the ISO parts are sold, not free;
  - the schemas can be read as HTML in the STEP Tools "Merged AP Library";
  - the MBx Interoperability Forum (formerly CAx-IF) publishes recommended practices;
  - NIST's STEP File Analyzer and Viewer checks files for conformance and is free (NIST open licence).
- **What is feasible without a kernel** (INFERRED):
  - a multi-solid file of **extruded prisms**: polygons with straight and arc edges, with inner holes;
  - each prism is a closed shell of planar faces plus cylindrical faces for the arcs;
  - each solid is written separately, with no booleans and no fillets.
- That covers a **"fit model" of a purchased box**: walls, floor, lid, bosses and card guides as separate
  solids that touch. It is enough for a fit check in KiCad and Altium and for an interference test.
- **What is not feasible:** booleans, fillets, shells, draft and blends. Those need a kernel.
- **Proof:** read the file back through two independent readers:
  - `kicad-cli pcb export step` with the model on a dummy footprint (OCCT inside KiCad);
  - gmsh `ShapeFromFile`.
  - That gives `ORACLE-VERIFIED(kicad-cli)` and `ORACLE-VERIFIED(gmsh)`.
- **Clean-room:**
  - format facts go to `docs/formats/step/*.md` with sources and labels;
  - no parser or writer code is copied;
  - the schema files are read, never vendored.

### Recommendation

- **Core (stdlib only):**
  - the enclosure data model;
  - the 2D and 2.5D checks;
  - panel drilling templates;
  - a small STEP writer for extruded prisms;
  - an STL and 3MF writer for the same solids.
- **Kernel work** (booleans, fillets, generated enclosures, true 3D interference) goes through **gmsh as a
  subprocess**:
  - it is already an optional tool reported by `fenolite capabilities`;
  - it needs no new dependency and respects ADR-0004.
- **If gmsh's `.geo` language proves too weak** for generated enclosures, the next option is build123d.
  It must not become an ordinary extra. It runs as a **worker process in its own environment**, the way
  ADR-0004 already treats copyleft oracles. Making it an ordinary extra would need an ADR amendment for
  LGPL-licensed binaries; that is the maintainer's decision.
- OpenSCAD is not recommended. It cannot write STEP, and YAPP_Box already serves OpenSCAD users.

## 4. Off-the-shelf catalogues and their terms

| Maker | What is public | CAD files | Terms found |
|---|---|---|---|
| **Hammond** (1591, 1590, 1555…) | Dimensioned PDF drawings per part. Distributor text says 1591 boxes have card guides for 1.5 mm (0.062 in) boards and M3 lid screws into brass bushings (some variants use plastic tapped holes). | STEP and IGES from hammfg.com (forum reports; some by request to the factory). | Our fetches of the terms page were refused (403): **UNKNOWN**. |
| **Bud Industries** | PDF drawings, DXF for standard products (Digi-Key). | STEP on product pages or on request, with contact details (forum, Bud blog). | **UNKNOWN**. |
| **Takachi** | Drawings on the site. | STEP after registration and login; also through a CADENAS PARTcommunity portal. | Page carries "All Rights Reserved"; licence terms not visible before login: **UNKNOWN**. |
| **Polycase** | Product pages list wall thickness and a 2D drawing (PDF/DWG). | "3D Model" STEP in each product's Downloads. | Terms page refused our fetch (403): **UNKNOWN**. |
| **OKW** | Drawings per product. The PCB finder gives PCB length and width "as an aid to orientation… cutouts of pillars are not taken into consideration". | 2D PDF/DWG/DXF and 3D PDF, Parasolid (x_t), STEP, SAT. | Legal notice: all photos, graphics, texts and other components are OKW's copyright and "**no contents of any kind may be used commercially without the prior permission**". |
| **Serpac** | Distributor listings. | Not found. | **UNKNOWN**. |
| **Gainta** | Distributor listings with outer dimensions (for example G1039B, 138 × 217 × 82.2 mm). | No official download found. | **UNKNOWN**. |
| **Multicomp** (Farnell house brand) | Distributor datasheets. | Not researched in depth. | **UNKNOWN**. |
| **AliExpress-style project boxes** | A drawing in the listing photos, with no maker identity, revision or tolerance. | Rarely. | No rights holder to ask; dimensions vary between sellers (INFERRED). |

### What this means for `lgili/fenolite-library`

- **Vendor STEP files: never stored, only linked.** No maker grants redistribution in what we found, and
  OKW explicitly forbids commercial use of any content. "Each item keeps its licence" does not help when
  the licence is "all rights reserved".
- **Dimensions are facts.** US copyright does not protect facts (Feist v. Rural, 1991). Meshwerks v.
  Toyota (10th Cir. 2008) held that faithful digital wireframes of real objects lacked originality.
  Brazil's Lei 9.610/98, art. 8, excludes ideas and data from protection (INFERRED reading).
- **Two limits on that:**
  - the EU database right (Directive 96/9/EC) protects a *substantial part* of a database whose making
    needed substantial investment. Copying a whole catalogue table could infringe even when each number
    is a fact;
  - the drawings themselves (PDF, images) are copyrighted, and so are vendor STEP files.
- **So the library may hold:**
  - **box models authored by Fenolite** from a public datasheet, one box at a time, never a scraped
    catalogue;
  - each with `PROVENANCE.json`: datasheet URL, document revision, date read, who entered it, and the
    evidence label per field;
  - a Fenolite licence for our own model (CC0 like our fixtures, or CC-BY-4.0);
  - generated geometry (our STEP or 3MF) is fine, because it comes from our own model.
- **Not in the library:**
  - vendor STEP, PDF drawings, photos;
  - box shapes copied from a vendor file (for example rounded corners measured in their STEP);
  - maker logos;
  - wording that suggests endorsement. Write "fits Hammond 1591B (per datasheet rev. X)", not "Hammond
    1591B model".
- **Evidence.** A field read from a drawing is `INFERRED`, because drawings carry tolerances and draft.
  Two ways to raise it:
  - **a physical sample** measured by the author, recorded as an `author-report`;
  - **a local comparison against the vendor STEP.** The user downloads it under the vendor's own terms,
    keeps it locally, and Fenolite measures it against our model on that machine. Only the result
    (distances, pass or fail) is stored, never the file. This needs the maintainer's decision, because
    it touches vendor files.
- **Courtesy:** ask Hammond and Takachi whether they object. A written permission would let us link
  their STEP more directly; we still would not mirror it.

## 5. Board fits box

### 5.1 What a box model needs

All values are integer nm. The frame has its origin at the inside floor centre, with Z up.

| Field | Content |
|---|---|
| identity | maker, series, part numbers (colour and flange variants), material, link to the datasheet |
| outer and inner | outer L × W × H; inner cavity L × W × H at floor and at rim (draft makes them differ); corner radii |
| parts | base and lid, split height, lid recess, gasket channel if any |
| PCB mounts | one or more *mount options*, each with the PCB bottom Z and either **bosses** (x, y, outer diameter, height, pilot hole, screw: M3, M2.5, #4 self-tapping, length) or **card guides** (slot width, Z, span, which walls) or **floor** (adhesive, with no holes) |
| usable PCB area | a polygon per mount option: cavity at PCB height, minus boss envelopes, guide ribs and the lid's screw columns, minus a clearance |
| height zones | polygons with the maximum part height above the PCB top (to the lid underside, lid ribs and screw columns) and below the PCB bottom (to the floor) |
| faces | front, back, left, right, top, bottom: plane, wall thickness, flat usable panel rectangle (excluding radii and ribs), material for drilling |
| tolerances | per field: the drawing's tolerance; Fenolite adds a fit clearance |
| evidence | label per field, provenance record |

Most of the work is the **usable area** and the **height zones**. The datasheet rarely states them
directly; they are derived from boss positions, rib positions and lid geometry.

### 5.2 How it drives the board

A call such as `design.fit(box, mount="bosses")` (name not decided) would generate only things the DSL
already knows:

- **Outline.** The usable-area polygon, minus a board-to-wall clearance, with notches around bosses. The
  user can choose a smaller board inside it; the check then says so.
- **Mounting holes.** `hole()` at each boss, drill from the screw, keep-out ring from the screw head or
  washer. `Hole.intent` carries `MechanicalIntent` (source: the box model, status `measured` or
  `estimated`, tolerance).
- **Height zones.** `rule_area()` plus `HeightLimit` per zone (c0140). The existing `judge_heights`
  checks every part's `outward_height`. The bottom side needs the same for parts under the board,
  which c0140 may not cover yet (to check).
- **Faces for connectors.** For each face, a placement constraint: a part tagged `panel="front"` must have
  its mating face within a set distance of the wall. An `Aperture` on the part's body (a profile in the
  part's frame plus a clearance) becomes the cutout. That ties into the `GroupRegion` and edge-gap
  machinery of the constrained placer.
- **Board thickness and stack.** The PCB bottom Z plus thickness sets the top-face height used by the
  zones. A card-guide box fixes the thickness (1.5–1.6 mm for the Hammond 1591).

### 5.3 The check

A new check stage, `enclosure.fit`, at three levels:

1. **2D (core):**
   - the outline is inside the usable area;
   - the holes sit on the bosses within tolerance;
   - no courtyard over a boss envelope;
   - panel parts touch their face.
2. **2.5D (core):**
   - the heights of every part against the zones, top and bottom;
   - each aperture lies inside the flat usable rectangle of its face;
   - the apertures keep a minimum web to each other and to the edges.
   - `outward_height` is already the single source of part height. Parts without bodies are reported as
     unknown, never as passing.
3. **3D (gmsh, optional):**
   - export the board with `kicad-cli pcb export step`;
   - write the box fit model as STEP;
   - let gmsh intersect the two and report the overlapping volumes, with the parts named.
   - This catches what 2.5D misses (tilted parts, overhangs, a connector body inside a wall).
   - Label `ORACLE-VERIFIED(gmsh)`. It depends on 3D models being present: without them, parts fall back
     to their extruded bodies.

## 6. Generated enclosures

### 6.1 A parametric box around the board

The input is what the board already knows: outline, holes, part bodies and heights, and the apertures
of panel parts (USB, barrel jack, terminal blocks, LEDs, buttons, displays). The generator builds:

- base and lid with a chosen wall thickness and corner radius;
- bosses at the board's holes, for self-tapping screws or heat-set inserts;
- a lip or snap-fits between the two parts;
- cutouts from the apertures, light-pipe or LED holes, button holes, a display window;
- optional vents and wall-mount ears.

Output: STEP for fit and services, 3MF/STL for printing. It needs booleans and fillets, so a kernel
(gmsh). YAPP_Box and tscircuit show the scope is achievable.

### 6.2 Manufacturing realism

- **FDM 3D printing (easy, recommended target).** Public guides disagree on the numbers, so these become
  parameters, not facts:
  - minimum wall about 0.75–1.0 mm, 1.5 mm or more for snaps and fasteners;
  - clearance between mating parts 0.2–0.5 mm;
  - general tolerance about ±0.5 %.
  - A **tolerance test print** (lip, boss, holes) helps more than any rule.
- **Panels of a purchased box (easy, very useful).** A 1:1 drilling template per face (SVG/PDF to print
  and tape on, DXF for a CNC or laser service) from the apertures. It needs no kernel and gives immediate
  value. Front Panel Express and Protocase accept DXF and STEP; their own tools stay theirs.
- **CNC-machined or sheet-metal enclosures (medium, not ours).** Sheet metal needs bend allowances,
  flat patterns and hardware (PEM inserts). Protocase-type services do this from a STEP or with their
  own designer. Fenolite should stop at a STEP of the cavity and cutouts.
- **Injection moulding (hard, stop early).** A part needs:
  - draft on every face in the pull direction: Protolabs advises at least 0.5°, 1–2° for most designs,
    about 1° per inch of depth, and 3° or 5° or more for textured finishes;
  - uniform walls (1–4 mm typical);
  - ribs at about 50–60 % of the wall thickness;
  - bosses tied to walls by ribs rather than merged into them.
  - A real mould then also needs a parting line, gates, ejector pins, shrinkage compensation, venting and
    side actions. That is the mould designer's work, done in their own CAD with the tooling quote.
  - **What we could honestly deliver:** a STEP with draft applied, and a DFM report:
    - wall thickness range;
    - missing draft;
    - rib and boss ratios;
    - undercuts against one pull direction.
  - Call it **"DFM-checked for moulding"**, never "mould-ready". Even the draft and wall analysis is
    real kernel work (face normals against the pull direction, thickness sampling). It belongs at the
    end, if ever.

## 7. Exchange and evidence

- **KiCad:**
  - `kicad-cli pcb export step` writes board plus parts. The box appears in KiCad if its STEP is attached
    to a footprint without pads (excluded from BOM and position files) at a pose Fenolite computes
    from the mount option;
  - KiCad 9 can embed the model in the footprint. That is fine for a user's project, but never for
    files we publish, if the STEP is a vendor's;
  - `kicad-cli pcb export step` then writes **one combined assembly STEP**, and `pcb render` shows the
    box in a PNG.
  - **What we can verify:**
    - the export succeeds, and the combined STEP contains the box solid (read back by gmsh): `KICAD-VERIFIED`;
    - the interference result from gmsh: `ORACLE-VERIFIED(gmsh)`.
  - **What we cannot verify** in CI is that the box *looks right* to a human: that stays a render for
    review.
  - `--component-filter` can produce the board without the box when needed.
- **Altium:**
  - the user places the box STEP as a 3D Body (Place » 3D Body), linked or embedded, at the pose
    Fenolite reports;
  - Altium can define the board shape from it, and its Component Clearance rule uses 3D bodies;
  - Fenolite's Altium writer does not write 3D links today. Embedding a STEP into a PcbDoc is a separate
    and harder change (binary format; not proposed).
  - **Evidence:** `ALTIUM-VERIFIED(author-report)` after the maintainer follows a written checklist, as
    for the schematic kit.
- **Services:**
  - STEP for CNC, sheet metal and moulding quotes;
  - 3MF/STL for printing;
  - DXF/PDF for panels.
  - Polycase lists STEP as its preferred 3D format for machining files.
  - No service confirms the fit: a first article does.

## 8. Verdict and staged plan

**Worth it, in stages, if the order is right.** The order is: box data and board-side checks first, a
fit model second, generation third, moulding never as a promise.

| Stage | What the user gets | Needs | Effort |
|---|---|---|---|
| 0. Fit check with a STEP you already have | `fenolite enclosure place BOX.step --pose …`: a no-pad footprint carries the user's STEP; `export --step` gives the combined assembly; `render --png` shows it; an Altium checklist | existing pipeline | S (1–2 weeks) |
| 1. Board fits box (data + checks) | `fenolite.enclosure.v0` box model; `design.fit()` drives outline, holes, height zones and face constraints; `enclosure.fit` 2D/2.5D check; panel drilling templates (SVG/PDF/DXF) | core only | M (4–6 weeks) |
| 2. A box library | 15–25 popular boxes authored from datasheets (Hammond 1591/1590, Takachi, a Gainta G-series and one generic AliExpress size class) in `fenolite-library/enclosures/`, with provenance; vendor STEP only linked | stage 1 | M (3–4 weeks), then ongoing |
| 3. Fit models and 3D interference | stdlib STEP and 3MF writer for prism solids; the box fit model drawn from the box data; gmsh interference against the KiCad STEP | stage 1, gmsh for the check | M–L (5–8 weeks) |
| 4. Generated printable enclosure | a parametric two-part box around the board, apertures from parts, FDM DFM checks, tolerance test print, STEP + 3MF | gmsh (or a build123d worker) | L (8–12 weeks) |
| 5. Moulding DFM (optional, late) | draft applied, wall and draft analysis, report | kernel | L+ (research first) |

Effort (one developer with an agent) is INFERRED from comparable changes.

**Risks:**

- **Data quality.** Datasheets omit the usable area and lid ribs. A wrong box model gives a confident,
  wrong board. Mitigations: an evidence label per field, physical-sample reports, and a "first board"
  warning until a box has an author report.
- **Vendor terms.** If makers object even to dimension-derived models, stage 2 shrinks to boxes we have
  measured ourselves. Ask first.
- **Part 3D models.** 2.5D and 3D checks are only as good as part bodies. Parts without models must
  read as unknown, never as passing.
- **gmsh limits.** The `.geo` OCCT subset may make fillets, shells or snap-fits fragile. The fallback
  (a build123d worker in its own environment) costs an ADR discussion.
- **Byte stability.** OCCT-written STEP carries dates and is not byte-stable. The exports already
  document STEP as "no hashes compare". Our own stdlib writer can be byte-stable with `--timestamp`.
- **Scope creep** into general MCAD: Fenolite models the box *for the board*, never the product's look.

## 9. Candidate OpenSpec changes (ids not assigned)

**`enclosure-fit-step`** (stage 0). A new command, `fenolite enclosure place`. It attaches a user-supplied
STEP to a generated no-pad footprint at a computed or given pose. The footprint is excluded from BOM,
position files and DRC courtyards. `export --step` and `render --png` include it. It also adds an Altium
checklist to `docs/` for importing the same STEP as a 3D Body at the same pose. Proof:
`kicad-cli pcb export step` on a fixture box authored for Fenolite, read back by gmsh. Nothing is
committed from a vendor.

**`enclosure-model`** (stage 1). The `fenolite.enclosure.v0` canonical JSON: identity, cavity, parts,
mount options (bosses, card guides, floor), usable area, height zones top and bottom, faces, tolerances,
and per-field evidence. Integer nm, strict reader, schema in `schemas/`. Derivation helpers compute
usable area and zones from bosses, ribs and lid geometry. Fixture boxes are authored for Fenolite (CC0).
Documented in `docs/design-model.md`.

**`board-fits-enclosure`** (stage 1). The DSL entry (`design.fit(box, mount=…)` or similar). It generates
the outline, `hole()` with `MechanicalIntent`, rule areas with `HeightLimit`, bottom-side height limits
if c0140 lacks them, and per-face placement constraints for parts tagged with a panel. It adds an
`Aperture` field on part bodies. Agent-guide lines for each new public name.

**`enclosure-fit-check`** (stage 1, then stage 3). The `enclosure.fit` check stage. Its 2D and 2.5D
findings: outline outside the usable area, hole off a boss, part too tall in a zone, aperture off the
flat panel, web too thin, part without a body (unknown). New `FEN-` codes and tests. Stage 3 adds a 3D
interference finding through gmsh, labelled `ORACLE-VERIFIED(gmsh)`.

**`panel-templates`** (stage 1). `fenolite export --panels` writes one drilling template per box face:
SVG and PDF at 1:1 with a scale bar, and DXF in mm. Each template holds the cutouts from the apertures,
the hole sizes and a datum corner. Byte-stable. It needs no kernel. This is probably the single most
useful hobbyist feature in this document.

**`enclosure-library`** (stage 2). An `enclosures/` area in `lgili/fenolite-library`:

- one folder per box, holding our box model, a `PROVENANCE.json` (datasheet URL, revision, date, author,
  evidence per field, optional physical-sample report) and a link to the vendor page and vendor STEP;
- no vendor files;
- a CI check that every model validates, and that a generated fit model loads in `kicad-cli`;
- an AGENTS.md sentence about vendor files (maintainer decision).

**`step-writer`** (stage 3). A stdlib writer of ISO 10303-21 AP214 (or AP242) files for multi-solid
extruded prisms with arcs and holes. Format facts go to `docs/formats/step/` with sources. Tests read the
files back with `kicad-cli` and gmsh; NIST SFA is optional, as a conformance oracle outside CI.
Deterministic output with `--timestamp`. Includes an STL and 3MF writer for the same solids.

**`enclosure-generate`** (stage 4). A parametric two-part FDM enclosure around a board through gmsh
`.geo` scripts:

- walls, radii, bosses for screws or inserts, a lip or snaps;
- apertures from parts;
- vents and ears;
- FDM DFM findings (wall, clearance, overhang);
- a tolerance test print.

Writes STEP and 3MF through the usual dry-run and confirm protocol. It starts with a spike to confirm
that gmsh's OCCT subset handles fillets and shells reliably.

**`moulding-dfm`** (stage 5, research). Draft application and analysis against a pull direction, wall
thickness sampling, and rib and boss ratio checks, as a report. It explicitly does not produce mould
tooling. Only after stage 4 has users.

## 10. Questions for the maintainer

1. **Vendor STEP files:** link only, never stored, not even in `fenolite-library`? Recommended: yes.
2. **Box models from datasheet dimensions:** may Fenolite author them one box at a time, with provenance,
   and should we ask Hammond and Takachi first? Recommended: yes and yes.
3. **Licence of our box models:** CC0 like other fixtures, or CC-BY-4.0? Recommended: CC0, so users can
   embed them anywhere.
4. **Kernel:** gmsh as a subprocess first, and a build123d worker in its own environment only if needed;
   no LGPL extra without an ADR amendment? Recommended: yes.
5. **Local comparison against a user's vendor STEP** (results stored, file never): allowed?
   Recommended: yes, as an opt-in that runs on the user's machine.
6. **Moulding:** promise only "DFM-checked for moulding", never "mould-ready"? Recommended: yes.
7. **Order:** stages 0 and 1 (with panel templates) first, before any 3D generation? Recommended: yes.

## Sources

Fenolite (in this repository): `docs/design-model.md` (c0096 mechanical intent, c0140 height limits),
`docs/dsl.md` (board, holes), `docs/placement.md`, `docs/exports.md` (`--step`), `docs/cli-contract.md`
(`render`), `docs/viewer.md` (gmsh), `docs/altium.md` (3D links dropped), `docs/adr/0004-licence-apache-2.0.md`,
`pyproject.toml` (extras).

Prior art:
- KiCad StepUp: https://wiki.freecad.org/KicadStepUp_Workbench ; licence in README of https://github.com/easyw/kicadStepUpMod
- KiCad CLI 9 (STEP/GLB/STL/BREP/XAO/PLY/VRML export options): https://docs.kicad.org/9.0/en/cli/cli.html
- KiCad 9 embedded files: https://www.cnx-software.com/2025/02/21/kicad-9-release/ ; https://forum.kicad.info/t/embed-all-footprints-models-at-once/60905
- Enclosure-as-footprint practice: https://forum.kicad.info/t/proper-way-to-do-it-fit-in-an-enclosure/9824/5 ; https://forum.pedalpcb.com/threads/playing-pcb-tetrix.22744
- Altium STEP import and 3D bodies: https://www.altium.com/documentation/altium-designer/step-export-import ; https://www.altium.com/documentation/altium-designer/3d-bodies
- Altium board shape from 3D body: https://www.altium.com/documentation/altium-designer/defining-board-shape
- Altium Component Clearance and 3D height: https://www.altium.com/documentation/knowledge-base/altium-designer/understanding-component-height-vs-3d-body-height-in-altium-designer ; https://altium.com/kr/documentation/altium-designer/pcb-placement-rule-component-clearance
- Altium MCAD CoDesigner: https://go.altium.com/rs/817-SFW-071/images/ACD21-CoDesigner-Fact-Sheet-051921-1.pdf
- Fusion 3D PCB: https://www.autodesk.com/products/fusion-360/blog/3d-pcb-fusion-360-tutorial/ ; https://www.autodesk.com/products/fusion-360/blog/fusion-360-electronics-ecad-mcad-made-easy/
- tscircuit enclosure package: https://registry.npmjs.org/@tscircuit/create-fdm-enclosure ; https://github.com/tscircuit/create-fdm-enclosure ; element doc copy https://tscircuit.com/techmannih/usbc-charger/blob/.claude/skills/tscircuit/elements/enclosurefdmbox.md
- JITX mechanical skill: https://www.claudepluginhub.com/skills/jitx-inc-jitx-skills/jitx-mechanical
- YAPP_Box: https://github.com/mrWheel/YAPP_Box (LICENSE: MIT) ; https://openscad.org/libraries.html
- Ultimate Box Maker: https://www.thingiverse.com/thing:1264391 ; mirror with licence https://3dgo.app/models/thingiverse/1264391 ; https://hackspace.raspberrypi.com/articles/ultimate-box-maker
- SBC Case Builder: https://github.com/hominoids/SBC_Case_Builder (LICENSE: GPL-3.0) ; https://www.cnx-software.com/2022/04/30/diy-sbc-cases-and-sbc-case-builder-tool-based-on-openscad/
- BOSL2: https://github.com/BelfrySCAD/BOSL2 (LICENSE: BSD-2-Clause)
- Protocase Designer: https://www.protocase.com/design/protocase-designer.php ; https://www.protocasedesigner.com/FAQ
- Front Panel Designer: https://www.schaeffer-ag.de/en/front-panel-designer ; https://docs.schaeffer-ag.de/en/frontpanel_designer.html

Geometry engines and formats:
- CadQuery: https://github.com/CadQuery/cadquery (LICENSE, setup.py) ; formats https://cadquery.readthedocs.io/en/latest/importexport.html
- build123d: https://github.com/gumyr/build123d (LICENSE, pyproject.toml) ; https://pypi.org/project/build123d/ ; formats https://build123d.readthedocs.io/en/latest/import_export.html
- OCP bindings: https://github.com/CadQuery/OCP (LICENSE) ; wheels https://pypi.org/project/cadquery-ocp-novtk/8.0.1/
- OCCT licence: https://github.com/Open-Cascade-SAS/OCCT (README, OCCT_LGPL_EXCEPTION.txt)
- gmsh reference manual (OCC kernel, booleans, fillet, STEP import/export options, GPL): https://gmsh.info/doc/texinfo/gmsh.html
- OpenSCAD licence: https://github.com/openscad/openscad/blob/master/COPYING ; CLI export formats: https://en.wikibooks.org/wiki/OpenSCAD_User_Manual/Using_OpenSCAD_in_a_command_line_environment
- ISO 10303-21 overview: https://en.wikipedia.org/wiki/ISO_10303-21 ; https://www.loc.gov/preservation/digital/formats/fdd/fdd000448.shtml
- ISO electronic inserts and licence: https://standards.iso.org/iso/10303/
- STEP Tools merged AP schema (HTML): https://www.steptools.com/stds/stp_aim/html/
- MBx-IF recommended practices: https://www.mbx-if.org (CAx recommended practices page)
- NIST STEP File Analyzer and Viewer: https://www.nist.gov/node/413991 ; https://github.com/usnistgov/SFA ; https://catalog.data.gov/dataset/step-file-analyzer-and-viewer-software
- 3MF: https://3mf.io/spec/ ; https://github.com/3MFConsortium/spec_core (LICENSE: BSD-2-Clause) ; https://github.com/3MFConsortium/lib3mf

Enclosure makers:
- Hammond: https://forum.digikey.com/t/how-to-find-3d-cad-models-for-hammond-manufacturing-part-s/11583 ; https://www.mikrocontroller.net/topic/367643 ; https://static6.arrow.com/aropdfconversion/13d504e8f908d1fbf76780a0e8bca5967a02e44b/1555nfpl.pdf ; 1591 features: https://uk.rs-online.com/web/p/general-purpose-enclosures/2256389 ; terms page (fetch refused): https://www.hammfg.com/terms
- Bud: https://forum.digikey.com/t/bud-mod-enclosures/39649 ; https://www.digikey.com/en/supplier-centers/b/bud-industries/custom-enclosures
- Takachi: https://takachi-enclosure.com/news/32 ; https://digitalpr.jp/r/66127
- Polycase: https://www.polycase.com/tf-3315tx-g ; https://www.polycase.com/media/wysiwyg/Machining_Formats_2025.pdf ; terms page (fetch refused): https://www.polycase.com/terms-of-use
- OKW: https://blog.okw.com/en/blog/how-to-download-drawings ; legal notice https://www.okw.com/en/About-OKW/Legal-notice
- Serpac: https://forum.digikey.com/t/serpac-modified-enclosures/39753
- Gainta (distributor data): https://www.tme.com/us/en-us/details/g1039b/multipurpose-enclosures/gainta/

Law (not legal advice; pages not all fetched):
- Feist v. Rural, 499 U.S. 340 (1991): https://supreme.justia.com/cases/federal/us/499/340/
- Meshwerks v. Toyota, 528 F.3d 1258 (10th Cir. 2008): https://law.justia.com/cases/federal/appellate-courts/F3/528/1258/565208/
- EU Database Directive 96/9/EC: https://eur-lex.europa.eu/eli/dir/1996/9/oj
- Brazil, Lei 9.610/98 (art. 8): https://www.planalto.gov.br/ccivil_03/leis/l9610.htm

Manufacturing:
- FDM guidelines: https://xometry.pro/en/?p=22061 ; https://jlc3dp.com/help/article/3D-Printing-Design-Guideline ; https://www.wevolver.com/article/fdm-3d-printing-design-tips-best-practices-and-techniques-for-stronger-prints
- Injection moulding draft: https://www.protolabs.com/resources/design-tips/improving-part-moldability-with-draft/
- Injection moulding walls and ribs: https://www.protolabs.com/en-gb/resources/guides-and-trend-reports/a-beginner-s-guide-to-injection-moulding/ ; https://www.protolabs.com/resources/guides-and-trend-reports/designing-for-moldability-fundamental-elements/
- Bosses: https://proleantech.com/injection-molding-design-guide/
