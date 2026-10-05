## Why

After c0043, Fenolite reads one board through two backends, and nothing says whether the readings
agree. The roadmap answers with `fenolite equivalent A B --level N`; levels 1 to 4 belong to v0.3.

The command also gives the Altium import an independent judge: `kicad-cli pcb import --format altium`
(10.0 only, `H-K-00`) reads a PCB document without any Fenolite code. `H-A-UNIT` has named this test
since c0004.

## What Changes

- **Comparison.** A new package `fenolite.checks.equivalence` compares two `Design`s level by level
  and returns located differences: `REF` for components and placement, `REF-PIN` for nets and pads.
  Level 2 reuses c0020's partition comparison (`checks.assignment_compare.compare`, `PadNetList`) and
  its code `netlist.assignment-differs`.
- **Tolerances, defined exactly.** Lengths are integer nanometres, compared per coordinate. Angles are
  integer microdegrees, compared on the circle. A pad's rotation is compared modulo its shape's
  symmetry. Sides are compared exactly. The defaults are 0 nm and 0 µdeg.
- **Frame.** `--frame relative` removes one translation per pair (the per-axis median), because
  KiCad's importer moves the board on its sheet.
- **Command.** `fenolite equivalent A [B] --level N` reads each side through the backend registry: a
  KiCad board, project file or folder, an Altium document or project, or a built design (a
  `.fenolite/` folder). It is read-only. Exit 0 means equivalent up to level N; exit 5 means located
  differences.
- **Exclusion lists.** A TOML file of rules (level, kind, field, `where` glob, reason, attribution)
  marks known differences. Excluded differences stay in the output and never fail the command.
- **Triangle oracle.** `fenolite equivalent A.PcbDoc --against kicad-import` converts A with
  `KicadCli.import_board` (new), reads the result with the KiCad backend and compares it with
  Fenolite's Altium import. The differences that KiCad's importer introduces are recorded per
  `kicad-cli` version in `src/fenolite/backends/kicad/data/altium_import_exclusions.toml`. Each rule
  has a reason, a hypothesis and the corpus rows that show it.
- **Evidence.** `docs/evidence/equivalence-triangle.md` records the counts per corpus document and
  level.

## Capabilities

### New Capabilities

- `design-equivalence`: the comparison levels 1 to 4, tolerances and frames, exclusion lists, the
  `equivalent` command, the board import runner, the triangle oracle and its evidence.

### Modified Capabilities

None. Every requirement is ADDED in the new capability.

## Non-goals

- Levels 5 to 8 (routing, rules, geometry XOR, presentation): v0.4, v0.6 and later.
- Conversion between backends and the public equivalence report of v0.5a.
- Comparing net names, net classes, properties other than the value, 3D bodies, mask and paste
  layers, custom pad outlines, zones, tracks or graphics.
- A whole-board rotation or mirror between the two sides; only a translation is removed.
- Schematic documents through a `kicad-cli` import, and library files.
- Any change to c0020's stages or to `check`.
- An exclusion for a difference that Fenolite causes: that is a bug, fixed in the adapter.

## Evidence level required

- The comparison is exact integer arithmetic on the model, proved by unit tests. It adds no label;
  an output carries the lowest label of the two reads.
- Triangle, per level: `ORACLE-VERIFIED(kicad-cli)` (10.0.x) for Fenolite's import of the public
  Altium-written documents of the corpus (c0041's seven `altium-pcbdoc` rows), once levels 1
  to 4 show no difference outside the exclusion list (`H-G-EQ-L1` to `H-G-EQ-L4`).
- A rule attributed `undecided` keeps its level `INFERRED` for the rows it touches. The label says
  what KiCad's importer reads, never what Altium does.

## Impact

- Code: `src/fenolite/checks/equivalence/`, `backends/kicad/cli.py`,
  `backends/kicad/altium_import.py`, `cli/cmd_equivalent.py`, one data file.
- Docs: `docs/equivalence.md`, `docs/cli-contract.md`, `docs/roadmap.md`, the evidence page, the
  registers.
- Order: after c0043 and c0020. No corpus document is committed.
- Size: 9 design-days.
