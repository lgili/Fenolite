## Why

On Monday the maintainer starts a real board in Altium Designer from a Fenolite design. `fenolite build` writes only KiCad projects (c0011). Altium saves and opens schematics in an ASCII form (S-0133), and creates the PCB from a compiled project through its engineering change order (S-0141). A clean-room, experimental writer of the project file and the ASCII schematic opens that route. It pulls the first item of v0.4 forward; v0.3 and the rest of v0.4 stay as planned.

## What Changes

- `fenolite build DESIGN.py --out DIR --target altium` (default `kicad`, unchanged) writes `<name>.PrjPcb`, an ASCII `<name>.SchDoc`, the `.fenolite/` layer texts and `build.json`. The project file is written once and then kept, because Altium rewrites it when a PCB document is added.
- `src/fenolite/backends/altium/` (new; a writer, not a registered backend):
  - one component per part: a generic body with the pins the design uses (designator and name as written), the designator, the value as comment, the library link from `lib_id` (`<library>:<name>`) and the footprint link from `footprint`;
  - a wire stub per pin, carrying a net label, or ended by a power port for nets of `Power` interfaces;
  - a deterministic grid layout on the smallest ISO sheet that fits;
  - unique ids keyed by component path, so rebuilds keep the links to the PCB.
- `src/fenolite/lens/altium.py` (new): `build_altium` checks link forms, text, letter case and ids (closed `altium.*` table), validates, writes, and reuses c0011's build record and edited-output refusal. Board, placements, net classes and diff pairs are reported as not lowered.
- `fenolite capabilities` lists this writer under a new `result.experimental`.
- CC0 `examples/altium_sample/` with its committed outputs and two check variants; `docs/altium.md`; fact pages under `docs/formats/altium/`; sources S-0130 … S-0144; hypotheses `H-A-SCH-*` and `H-A-PRJ-*`; a check protocol for the maintainer, whose results are author reports.
- Size: 5.75 design-days.

## Capabilities

### New Capabilities
- `altium-schematic-writer`: the ASCII schematic and project writer.
- `altium-build`: `--target altium`, its outputs, issue codes, edited outputs, determinism, evidence, sample, author reports and documentation.

### Modified Capabilities
- `cli-contract`: ADDED "Experimental features in capabilities".

## Non-goals

- PcbDoc, binary SchDoc, SchLib and PcbLib writers; reading any Altium file (v0.3).
- Hierarchy and multi-sheet designs, buses, harnesses, variants, rules and net classes, output jobs, stackups, title blocks beyond a plain sheet, and c0012's sheet templates.
- Real symbol graphics, pins taken from a library, and connectivity after a full "Tools » Update From Libraries" when the library's pins sit elsewhere.
- Library files copied into the project.
- A registered Altium backend, and any `kicad-cli` oracle: `kicad-cli` cannot read `.SchDoc` (S-0132).
- Any change to KiCad builds, the DSL, the model or c0011's `build` requirements.

## Evidence level required

- Records, bodies, links, layout, unique ids, determinism, issue codes and CLI: mechanical (unit tests, golden files and a readback of Fenolite's own records). Format facts are `INFERRED` from public sources.
- The sample opens, compiles into its six nets, and shows its links, line ends and unique ids as written: `ALTIUM-VERIFIED(author-report; AD …; <date>; no artefact)`, reported by the maintainer on the committed bytes before Monday. Change order, relink and library update: author reports on a design and libraries the maintainer may use, with generic outcomes only.
- The `build --target altium` envelope stays `INFERRED`; nothing is release-verified.

## Impact

- Extended: `cmd_build.py`, `cmd_capabilities.py`, `test_format_facts.py`; new `.gitattributes`.
- No runtime dependency, model, schema, layering or FEN-code change.
- Archive order: before c0019, c0021 and c0027, which modify "Build command"; their KiCad steps apply to `--target kicad` only.
