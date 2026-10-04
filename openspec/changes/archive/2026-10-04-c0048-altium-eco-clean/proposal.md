## Why

The maintainer ran "Design » Update PCB Document" in Altium Designer 26.5 on the built
`examples/altium_hier_board` (report of 2026-10-03). Every component and net matches, but the change
order still proposes four groups of changes:

1. remove the net class `PWR` from the board: the schematic declares no net class;
2. add the component classes `driver` and `led`, which Altium derives from the module sheets;
3. add a room per module sheet;
4. add two "Supply Nets" rules, which Altium derives from the power ports.

Item 1 is harmful: a user who executes the change order loses the net class.

## What Changes

- **Net classes in the schematic (Part A).** Each net of a net class gets one Parameter Set directive
  per sheet, on a wire of the net, with a hidden `ClassName` parameter. This is the form Altium's
  documentation describes (S-0310, S-0311) and a public Altium-saved sheet holds (S-0187).
- **Class generation in the project file.**
  - A design with a net class gets a `[PrjClassGen]` section with `NetClassManualEnabled=1`, the
    option "Generate Net Classes" for user-defined classes (S-0310, S-0187, S-0188).
  - A project with module sheets or a PCB document gets three keys per schematic document: component
    classes on, **rooms off**, no sheet net class (S-0187, S-0188, S-0313).
- **Component classes in the board (Part B).** `<name>.PcbDoc` gains one `KIND=1` class per sheet that
  holds a part, with the refs of its components: named after the module for a module sheet, and after
  the sheet for the top or single sheet (S-0172, S-0175, S-0199, S-0200; report of Part E).
- **Documented remaining differences.**
  - Rooms are not written: no permitted source holds a room rule record. The project key turns their
    generation off instead.
  - "Supply Nets" rules are not written: no permitted source holds the record, and an application
    setting of Altium, not a project file, turns the proposal on (S-0185, S-0312). They are additions
    and remove nothing.
- **Samples and protocol.** Part E of `docs/evidence/altium-pcb.md`, and two sample folders for the
  maintainer.

## Capabilities

### Modified Capabilities (no new capability)

- `altium-schematic-writer`: 3 ADDED (net class directives, class generation keys, read back);
  MODIFIED "Project file" and "Project file of a multi-sheet project" (living text).
- `altium-pcb-writer`: 1 ADDED (component class records).
- `altium-build`: 3 ADDED (classes in a build, sample and author report, documentation).

## Non-goals

- No room record, no "Supply Nets" rule, no other rule kind, no super class.
- No blanket, no differential-pair directive, no component `ClassName` parameter.
- No key of the comparator or of the change-order options in the project file.
- No change to the model, the DSL or the KiCad target.
- No reader of Altium classes (c0040 to c0042 own reading).

## Evidence level required

- Everything Altium must accept is `INFERRED` under `H-A-ECO-NETCLASS`, `H-A-ECO-PRJ-KEYS`,
  `H-A-ECO-COMPCLASS`, `H-A-ECO-ROOMS`, `H-A-ECO-SUPPLY` and `H-A-ECO-SHEETCLASS`, until the maintainer
  reports Part E; then
  `ALTIUM-VERIFIED(author-report; AD 26.5; <date>; no artefact)`.
- `kicad-cli` reads no Altium schematic and imports no class, so nothing here is `ORACLE-VERIFIED`.
- The build stays `INFERRED` and experimental.

## Impact

- Code: `backends/altium/` (`layout.py`, `schdoc.py`, `prjpcb.py`, `project.py`, `hierarchy.py`,
  `pcbdoc.py`) and `lens/altium.py`.
- Data: the golden files that hold a net class, module sheets or a board are rebuilt (`blink`,
  `routed`, `hier`); their earlier author reports stay valid for the facts they settled.
- Docs: `docs/formats/altium/schematic-ascii.md`, `project.md`, `pcb-copper.md`, `docs/altium.md` and
  the registers. Sources S-0310 to S-0313; the maintainer's saved project file stays outside the
  repository.
- Order: … → c0037 → c0038 → c0048.
- Size: 4.75 design-days (a size, not time).
