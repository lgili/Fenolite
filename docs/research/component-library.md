# A large component library for Fenolite: sources, licences and how to build it

Status: **research, nothing here is implemented**. The formats below are design sketches for OpenSpec
changes; names may change. Date: 2026-10-29. Not legal advice.

The goal is that a user can place a real manufacturer part (symbol, footprint, 3D body, pin map, ratings,
datasheet) without drawing anything. This page answers three questions:

1. what may be used, and how (licences and terms);
2. how the best libraries are organised and generated;
3. how Fenolite can reach tens of thousands of parts without breaking its rules (clean-room, no runtime
   dependency, deterministic outputs, evidence labels).

It builds on `docs/research/circuit-as-code.md` and the device and lock changes c0248, c0249 and c0254.

## The short answer

**Generate the library from facts, and import on demand what the user downloads.** Do not copy anyone's
library.

- Footprints and 3D bodies come from **per-family generators** fed by authored dimension files. Each
  dimension is cited to a public datasheet or a JEDEC outline. KiCad's own library is at least 78 %
  generated this way.
- Symbols come from **pin tables** through a layout rule.
- Passives come from **ordering-code grammars**. One series description expands into thousands of exact
  part numbers, lazily.
- Everything else is **imported locally** from files the user downloaded (SnapMagic, Ultra Librarian,
  manufacturer CAD), or **proposed** by a supplier lookup with the user's own API key.
- The shipped data lives in a **separate, versioned, CC0 data repository**, pinned by the design lock.
  The core package stays code only.

## 1. What may be used, and how

Five ways to use a source: **(a)** ship it in the package, **(b)** ship it in a separate data repository,
**(c)** fetch at run time with the user's own key (optional extra), **(d)** the user downloads and Fenolite
imports locally, **(e)** avoid.

| Source | What it has | Key terms | Use |
|---|---|---|---|
| KiCad official libraries (MEASURED 2026-10-28: 15 468 footprints, 22 911 symbols, 7 256 STEP) | everything | CC-BY-SA 4.0; the exception covers *designs* made with the library, not redistribution of the library | **(d)**: read the user's install, as today. AGENTS.md forbids committing these files |
| Horizon EDA pool | everything | same CC-BY-SA 4.0 + exception | (d) |
| LibrePCB libraries | symbols, packages, 3D, devices | **CC0-1.0** | could be (a)/(b), but our catalog spec forbids copying from another CAD library: maintainer decision |
| CERN KiCad library (17 000+ items, announced 2026-05) | symbols, footprints | "open source licence": exact licence UNVERIFIED | check before any use |
| Wikidata | facts (manufacturers, identifiers) | CC0 | (a)/(b) for facts |
| SnapMagic (SnapEDA) | millions of models | no scraping; ≤ 10 design files to one location; no distribution "within any other software" | **(d)** |
| Ultra Librarian (Cadence), SamacSys / Component Search Engine | models for most manufacturers | no automated access; "own use, not for transfer"; some manufacturer terms forbid "translate" | **(d)**: import runs locally on the user's own files |
| Manufacturer CAD and STEP (TI, ADI, ST, Infineon, ...) | models | usually own use, no transfer; TI's site terms: non-commercial, no scraping | **(d)** |
| DigiKey Product Information v4 | parameters, datasheet links, prices | personal licence; no bulk download; may not build a database; attribution; 1 000 requests a day | **(c)**, no persistent cache |
| Mouser Search API | parameters, prices | may not create a database; attribution (terms page read second-hand: UNVERIFIED) | **(c)** |
| Nexar / Octopart | parameters, prices | cache at most 24 h; no competing product; attribution | **(c)**, 24 h cache |
| Farnell / element14 | parameters, prices | no caching at all; no aggregation with third-party content | **(c)**, no cache |
| JLCPCB official API | parts, stock | approval required | (c) with the user's approved credentials |
| EasyEDA / LCSC content | symbols, footprints | non-commercial only; no scraping; no AI training | **(e)** |

Sources:
- https://www.kicad.org/libraries/license/
- https://librepcb.org/license/
- https://www.snapeda.com/about/terms/ (§3.1, §5.1)
- https://www.ultralibrarian.com/legal
- https://developer.digikey.com/api-user-agreement (§3.2, §5.1)
- https://nexar.com/api/legal (§1.2)
- https://partner.element14.com/terms (§4)
- https://easyeda.com/legal (§VII)
- https://www.ti.com/legal/terms-conditions/terms-of-use.html

**Law, in one paragraph each.**
- **United States:** facts are not protected (*Feist*, 499 U.S. 340). Pin numbers, pad sizes and package
  outlines are facts. A drawn symbol, a STEP mesh or a datasheet may carry thin copyright. Terms of use
  you accepted bind regardless.
- **European Union:** Directive 96/9/EC, art. 7, gives a database maker a right against extraction of a
  *substantial part*, including repeated small extractions (*Directmedia*, C-304/07). Investment in
  *creating* the data does not count (*BHB v William Hill*, C-203/02). So a bulk crawl of a distributor or
  aggregator into a Fenolite data repository is very likely infringing, while one user looking up one
  part is not.
- **Brazil:** Lei 9.610/98 protects a database's original *structure* (art. 7 XIII, art. 87), not the data
  itself (art. 7 §2). There is no EU-style right in the contents, but contracts still apply.

Consequences for Fenolite:
1. Ship only data we author from public facts, or data that is explicitly CC0.
2. Never build a merged parts database from API answers.
3. Every item carries its own licence and source fields.

## 2. How the best libraries are organised

| Library | Model | What to learn |
|---|---|---|
| KiCad | symbol, footprint, 3D in separate libraries; 54 % of symbols are *derived* (`extends`) | per-family generators with parameter files (78 %+ of footprints); a rules document (KLC) with an automated checker, rendered previews and an old/new visual diff in CI, then human review |
| LibrePCB | symbol → component (signals) → package → **device** (component + package + pad map); categories as tag trees | ids never reused: an element's interface never changes, a change makes a new element and deprecates the old; semantic versions, highest wins; a **stable-id cache** keyed by (kind, name, pin) so regenerating keeps ids |
| Horizon EDA | unit (pins) → entity (gates) → symbol (draws only) → padstack (parametric) → package → **part** (MPN, datasheet) | **part inheritance** for packaging and grade variants; parametric padstacks; a part wizard from CSV pin tables, splitting large parts into gates |
| Altium 365 | component type is a parameter; **templates** define required parameters; lifecycle states; **part choices** rank manufacturer parts | supply data changes do not bump the component revision; "outdated" and "invalid" flags against the template |
| SnapMagic / Ultra Librarian | IPC-7351B-style land calculator by default, manufacturer pattern when given; multi-step verification | land patterns computed from package dimensions, not drawn |

**What the standards give us.**
- IPC-7351B is paywalled. Its *concepts* are widely documented: three density levels, toe/heel/side
  solder goals, courtyard excess, and the naming pattern `SOIC127P600X175-8N`. Its tables and calculator
  are not public. Fenolite needs its **own authored constants**, labelled `INFERRED`.
- JEDEC JEP95 registered outlines (TO, DO, MO) are a free download with registration: legitimate,
  citable inputs for body and lead dimensions. Cite them; do not bundle the PDFs.
- The **manufacturer's recommended land pattern** in the datasheet takes priority. KiCad's KLC F4.1 and the
  Horizon convention agree. It is a citable per-part fact.

**What AI can and cannot do here** (SFgen, arXiv 2607.19767; JITX blog 2024):
- **Pin tables extract well.** JITX got a 95-row table right from an 820-page datasheet.
- **Mechanical drawings do not.** SFgen reports 86 % of symbols and 80 % of footprints right on 1 000
  parts, but pin and pad count accuracy falls to 0 % on dense packages.
- **The fix both sources reached:** the model proposes *parameters*, and a deterministic generator draws
  the part, where cross-checks catch errors (pin count, depopulated balls, body against span).

## 3. Where Fenolite is today

- **Catalog:** 100 footprints and 49 generic symbols, written as Python tuples with an if/elif dispatch.
  All are `INFERRED`, none has a 3D body, none has a part number. The generators for SOIC, QFN, QFP, DFN,
  DIP and chip parts exist but are private.
- **Authoring:** `Footprint` and `Symbol` builders (c0055, c0058). They are single-unit and cannot set
  bodies or models, although the model already has `bodies`, `models` and `placements`.
- **KiCad libraries:** resolved from the user's install or a pinned cache, never committed; used items are
  vendored into `lib/`.
- **Altium libraries:** `.SchLib` and `.PcbLib` are read; `.IntLib` is not.
- **Import:** there is no import of a third-party footprint, symbol or STEP into the catalog.
- **Library checks:** there is no library lint (roadmap: planned).
- **Proposed already:**
  - c0248: device records, 10 generic devices, no real MPN;
  - c0254: parametric families and a supplier proposal hook, no plugin, no network.

## 4. The proposed library, layer by layer

### 4.1 Five records, data files, stable ids

The model follows LibrePCB and Horizon: a symbol draws pins it does not define, and a device joins
everything.

```
pins (pin table) ──▶ symbol (drawing, generated)
package (dimensions) ──▶ footprint + 3D body (generated)
device = pins + symbol + package + pin→pad map + ratings + datasheet   (c0248)
part   = device + MPN + manufacturer + ordering code + lifecycle        (orderable)
family = a grammar that expands into many parts (passives)               (c0254)
```

Every record is a TOML file in a data tree, never Python. Each has:
- a stable id derived from `(kind, canonical name)` (a UUIDv5-style hash, so regeneration keeps it);
- a semantic version;
- `licence`, `sources`, `evidence` and `reviewed_by` fields.

An interface change (pins, pad numbers) makes a **new id** and deprecates the old one, never an edit in
place.

### 4.2 Footprints and 3D from package families

One file per package, one generator per family: chip two-terminal, molded two-terminal, gull-wing (SOIC,
SSOP, TSSOP, QFP, SOT), no-lead (QFN, DFN, SON), grid array, TO, DIP, pin headers, and connector series.

```toml
# packages/soic/SOIC-8_3.9x4.9mm_P1.27mm.toml   (illustrative; numbers from the cited outline)
schema = "fenolite.package.v0"
family = "gullwing"
name = "SOIC-8_3.9x4.9mm_P1.27mm"
pins = 8
pitch = "1.27mm"
body = { length = "4.80mm..5.00mm", width = "3.80mm..4.00mm", height = "1.75mm max" }
span = "5.80mm..6.20mm"                 # lead tip to lead tip
lead = { length = "0.40mm..1.27mm", width = "0.31mm..0.51mm" }
sources = ["S-0xxx JEDEC MS-012 outline", "S-0yyy manufacturer package drawing"]
evidence = "INFERRED"
licence = "CC0-1.0"

[land]                                  # optional: the manufacturer's pattern wins over the calculator
source = "S-0yyy figure 12"
pad = { width = "0.60mm", length = "1.55mm" }
row_spacing = "5.40mm"
```

```python
# what the generator does (sketch): authored constants, documented in docs/formats/library/lands.md
fp = footprints.gullwing(pkg, density="N")  # land from body/lead ranges + Fenolite goals, or pkg.land
fp.courtyard  # nominal body ∪ lands + class clearance
fp.body  # extruded 3D body from the same numbers -> STEP export
```

Ranges use c0246's exact `Range`. The land calculator's goals and courtyard clearances are
**Fenolite-authored** constants in `docs/formats/library/lands.md`, labelled `INFERRED`, never copied from
IPC tables.

### 4.3 Symbols from pin tables

```toml
# devices/example/EXB6202/pins.toml   (illustrative device)
schema = "fenolite.pins.v0"
[[pin]]
number = "5"
name = "VIN"
type = "power_in"
group = "supply"
[[pin]]
number = "2"
name = "GND"
type = "power_in"
group = "ground"
[[pin]]
number = "4"
name = "EN"
type = "input"
group = "control"
[[pin]]
number = "6"
name = "SW"
type = "power_out"
group = "output"
```

The layout rule:
- supply on top and ground at the bottom;
- inputs and control on the left, outputs on the right;
- buses kept together;
- units split above about 100 pins.

It is applied deterministically, for KiCad and Altium. Variants of the same graphic become derived
symbols (`extends`).

### 4.4 Devices and parts (c0248, extended)

```toml
# devices/example/EXB6202/device.toml
schema = "fenolite.device.v0"
id = "Example:EXB6202"
manufacturer = "Example Semi"
mpn = "EXB6202"
datasheet = "https://example.invalid/exb6202.pdf"
pins = "pins.toml"
package = "SOIC-8_3.9x4.9mm_P1.27mm"
ratings = { vin = "6V max", iout = "2A max", temperature = "-40degC..125degC" }
evidence = "UNVERIFIED"                 # raised to CORPUS-VERIFIED by a recorded review
licence = "CC0-1.0"
sources = ["S-0zzz datasheet rev C, tables 1 and 6"]

[[part]]                                # orderable variants inherit everything else
mpn = "EXB6202DR"
packing = "reel 2500"
[[part]]
mpn = "EXB6202DT"
packing = "tube"
```

### 4.5 Passives from ordering-code grammars (feeds c0254)

A series is described once, from its public datasheet: the fields, their codes, and the validity matrix
(which value exists at which size and voltage). Parts are expanded **lazily**: nothing stores millions of
rows.

```toml
# families/example_mlcc.toml   (illustrative grammar, authored for Fenolite)
schema = "fenolite.family.v1"
kind = "capacitor"
manufacturer = "Example Passive"
pattern = "EX{size}{dielectric}{value}{tolerance}{voltage}{packing}"
sources = ["S-0aaa series datasheet, ordering code table"]
evidence = "INFERRED"

[fields.size]
"03" = { case = "0603", package = "C_0603" }
"05" = { case = "0805", package = "C_0805" }

[fields.dielectric]
"R" = "X7R"
"C" = "C0G"

[fields.value]
code = "eia3"                           # 104 = 100 nF

[fields.tolerance]
"K" = "10%"
"J" = "5%"

[fields.voltage]
"A" = "25V"
"B" = "50V"

[[valid]]                               # the validity matrix, row by row
size = "03"
dielectric = "R"
voltage = "A"
value = "100pF..1uF"
```

```python
c = design.part(capacitor(farad("100n"), rating=volt(25), case="0603", dielectric="X7R"))
# c0254 resolves the query against the families -> EX03R104KA..., recorded in design.lock
```

### 4.6 Import of what the user downloaded

```
fenolite library import ~/Downloads/EXB6202.zip --into devices/ --dry-run
fenolite library import ~/Downloads/EXB6202.zip --into devices/ --confirm --plan <id>
```

- **Input:** `.kicad_sym`, `.kicad_mod`, `.SchLib`/`.PcbLib` (later `.IntLib`), and STEP.
- **Output:** device, package and pins files in the **user's project** with:
  - `licence = "see source terms"`;
  - the origin and the file SHA-256;
  - evidence `UNVERIFIED`.
- **Limits:** nothing is uploaded, nothing enters the shipped library, and the import runs locally on the
  user's own files.
- **Cross-check:** the imported footprint is compared with the generator's output for its family. A
  mismatch beyond tolerance is a finding, which is a cheap way to catch broken downloads.

### 4.7 Datasheet to device, with review

```
fenolite library propose --datasheet exb6202.pdf --out devices/proposed/   # agent: proposes pins + package params
fenolite library check devices/proposed/EXB6202                             # generators + rules + renders
fenolite library review devices/proposed/EXB6202 --accept                   # human; evidence -> CORPUS-VERIFIED
```

1. The agent proposes **parameters and a pin table only**, never geometry.
2. The deterministic generators draw the part.
3. The checks run: pin count against pad count, pin-1 position, courtyard, body against span, depopulated
   balls, and the land against the manufacturer pattern.
4. A rendered review sheet is the evidence of the human review.

This is how the library grows to thousands of parts without lowering trust.

### 4.8 Supplier data, per user (extends c0254's hook)

`fenolite[suppliers]` is an optional extra. The user supplies their own DigiKey, Mouser, Nexar, Farnell or
JLC credentials. It only *proposes*: stock, price, lifecycle and alternates are shown with the required
attribution and written nowhere persistent. The cache follows each source's terms (none for Farnell,
24 h for Nexar, the session only for DigiKey and Mouser). It never feeds a shared corpus.

### 4.9 Distribution

- **The `fenolite-library` repository (separate):**
  - holds data only (TOML, review sheets, no code), under CC0-1.0;
  - its CI regenerates every footprint, symbol and body, runs the library rules, renders previews and an
    old/new visual diff;
  - publishes versioned releases.
- **How the core gets it:** the core package stays code only, plus the small generic catalog it has
  today. The data comes either as an extra (`fenolite[devices]`) or as `fenolite library fetch` of a
  pinned release. The version is recorded in the design lock (c0249), so a build is byte-identical.
- **Contributions:** by pull request. A manufacturer can contribute its own parts under CC0, a source that
  is explicitly allowed.

### 4.10 Coverage order

| Step | What | Why |
|---|---|---|
| 1 | chip R, C, L, ferrite (0201–2512), tantalum, via families (4.5) | 80–90 % of the parts on a typical BOM are passives |
| 2 | SOD, SOT, SC-70, SOIC, TSSOP, MSOP, QFN, DFN, QFP generic packages | most ICs sit on these packages |
| 3 | power parts for our niche: MOSFETs (TO-220, D2PAK, PowerPAK-style), gate drivers, shunts, regulators | net roles and the router (c0222, c0243, c0244) |
| 4 | pin headers, common terminal blocks, USB-C, JST- and Molex-style series (generated, cited) | connectors are on every board |
| 5 | MCUs and dense parts through the datasheet pipeline (4.7) | needs review |
| 6 | BGA, large connectors | hardest, last |

## 5. Proposed changes (each becomes an OpenSpec change)

| Id | Change | Depends on | Size |
|---|---|---|---|
| c0259 | `library-data-format`: package, pins, device and part records as TOML; stable ids, versions, licence and source per item; the current Python catalog moves to data, byte-identical | c0248 | M |
| c0260 | `footprint-generators`: public per-family generators, land calculator with Fenolite-authored constants and manufacturer override, courtyard, extruded 3D bodies and STEP | c0259, c0246 | L |
| c0261 | `symbol-generator`: pin table to symbol with the layout rule, multi-unit, derived symbols, KiCad and Altium | c0259 | M |
| c0262 | `library-rules`: `fenolite library check` with `library.*` codes, rendered sheets, old/new visual diff, the review record that raises evidence | c0260, c0261 | M |
| c0263 | `passive-families`: ordering-code grammars with validity matrices, lazy expansion, used by c0254 | c0254, c0259 | M |
| c0264 | `library-import`: local import of user-downloaded KiCad, Altium and STEP files into project devices, with origin, licence and cross-check against the family generator | c0259, c0260 | M |
| c0265 | `datasheet-proposals`: agent proposes pin tables and package parameters; generators draw; checks and review | c0260–c0262 | M |
| c0266 | `device-packs`: the separate CC0 data repository, its CI, releases, `fenolite library fetch`, version pinned in the lock | c0249, c0262 | M |
| c0267 | `supplier-lookup`: the optional extra with per-user keys, per-source cache limits and attribution; proposals only | c0254 | S |

## 6. Questions for the maintainer

1. **LibrePCB's CC0 library:** may it seed the data repository? Today the catalog spec forbids copying from
   another CAD library, whatever the licence. Recommended: no for geometry, which we regenerate from
   facts. Possibly yes as a *coverage checklist* of which parts to do first.
2. **CERN library:** verify its licence before deciding anything. Recommended: same answer as LibrePCB.
3. **Name of the data repository and its licence.** Recommended: `fenolite-library`, CC0-1.0, with DCO
   sign-off like the main repository.
4. **Land-calculator defaults.** Recommended: ship one documented density (nominal) as `INFERRED`, and let
   the manufacturer pattern override per part.
5. **Real MPNs in the shipped data.** c0248 ships none. Recommended: real MPNs only in the data repository,
   each with a cited datasheet and a review record.
