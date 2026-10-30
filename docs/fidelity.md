# Fidelity proof: does the code rebuild the original?

`fenolite verify-source SCRIPT --against ORIGINAL` proves that a design script rebuilds an original project
(change c0278). It is the proof behind the board library (`docs/research/board-library.md`, section 4.4): a
converted board is worth something only while its code still rebuilds the original, so a regression in a
reader, the DSL or a writer shows up as a failed board. The command line, the result keys, the codes and the
exit codes are in `docs/cli-contract.md`, "verify-source"; the levels are those of `docs/equivalence.md`.

```
fenolite verify-source boards/sensor/design.py --against upstream/sensor/ --json
fenolite verify-source boards/sensor/design.py --against upstream/sensor/ \
    --record --timestamp 2026-11-01T00:00:00Z --dry-run
fenolite verify-source ... --record --timestamp 2026-11-01T00:00:00Z --confirm --plan <plan_id>
```

## What it does

1. **Build.** The script runs as `fenolite build` runs it (no sandbox: run only scripts you trust), for the
   KiCad major of the original's board (9 or 10) or `--target`, into a fresh temporary folder. The planned
   files are written there without the confirmation step; a write outside it (a design lock beside the
   script) is left out. The folder is removed on every exit, and no temporary path reaches the reply. A
   build that writes no file gives `fidelity.build-failed` with the build's errors, and no level runs.
2. **Read.** The original (a KiCad project folder or `.kicad_pro`, or an Altium `.PrjPcb`) and the build are
   read as `fenolite equivalent` reads its sides. A KiCad board older than 9.0 is refused (`FEN-3003`, exit
   3) unless `--upgrade` upgrades a copy with `kicad-cli pcb upgrade`, which `fidelity.input-upgraded`
   records with the tool version and both SHA-256.
3. **Compare.** Levels 1 to 7, level 5 with its strict rule (every track, arc and via item by item), then
   level S, then level 8. `--levels 1-7,8` runs a subset. A level a side cannot reach is `skipped` with
   `fidelity.level-skipped` and its reason, never passed silently.

| reason | when |
|---|---|
| `no-footprints` | a side has no footprint: levels 3, 4, 6 and 7 |
| `no-copper` | a side has no track, arc or via: level 5 |
| `no-board` | a side has no board: level 8 |
| `no-schematic` | a side has no `.kicad_sch`: level S |
| `drawn-unavailable` | both sides have sheets, but a side's sheets are not read or not extracted: level S |
| `altium-drawing-unread` | an Altium original: the Altium reader keeps no wire geometry: level S |
| `build-failed` | the build wrote no file: every level |

Level S reads the sheets of both sides, extracts their drawings (`docs/drawn-schematic.md`) and compares
them with `compare_drawn` (`docs/equivalence.md`, "Level S: schematic"). The two sides are joined by
reference, as levels 1 and 2 join them: each reference names the `fenolite.path` of its component in the
build, so a repeated sheet of the original is one drawn sheet when the script's modules make it one. A
symbol that names no component of the build is kept as an opaque item and compared as one; the level's
`summary.extraction_issues` counts such issues of both extractions. Level S is `INFERRED`
(`H-K-DRAWN-CONNECT`, `H-K-DRAWN-WRITE`) until the KiCad job measures the extraction.

Level 8 renders the board of both sides, layer by layer, and each schematic sheet that both sides hold
under the same path, with the viewer's scene builders (`docs/equivalence.md`, "Level 8: presentation").

## Tolerances

Lengths 0 nm, angles 0 µdeg, routed lengths 0 ppm, the `absolute` frame, 1000 ppm of differing pixels and a
pixel pitch of 50 µm, unless the provenance file's `fidelity.tolerances` (`length_nm`, `angle_udeg`,
`length_ppm`, `pixel_ppm`) or an option says otherwise; an option on the command line wins. The tolerances
used are in `result.tolerances`.

## The provenance file: `fidelity.accepted` and `fidelity.proof`

`PROVENANCE.json` beside the script (or `--provenance FILE`) is created by the board-to-code import
(c0275); the library (c0279) owns its other members. This change owns the member `fidelity`:

```json
{
  "schema": "fenolite.provenance.v0",
  "fidelity": {
    "tolerances": {"length_nm": 0, "angle_udeg": 0, "length_ppm": 0, "pixel_ppm": 1000},
    "accepted": [
      {
        "id": "A001",
        "level": 7,
        "kind": "text-field",
        "where": "board:Cmts.User:*",
        "field": "size",
        "reason": "Comment-layer text uses a font the DSL does not name yet (c0277).",
        "attribution": "fenolite",
        "decided": "2026-11-01"
      }
    ],
    "proof": {
      "fenolite": "0.7.0",
      "date": "2026-11-01T00:00:00Z",
      "script_sha256": "…",
      "against": {"sensor.kicad_pcb": "…", "sensor.kicad_sch": "…"},
      "tolerances": {"length_nm": 0, "angle_udeg": 0, "length_ppm": 0, "pixel_ppm": 1000,
                     "render_pitch_um": 50, "frame": "absolute"},
      "levels": {"1": "equal", "5": "equal", "7": "accepted", "8": "equal", "S": "skipped"}
    }
  }
}
```

- **Accepted differences.** Each entry of `fidelity.accepted` names one understood difference: `level`
  (1 to 8 or `S`), `kind` (a kind of that level), `where` (a glob over the difference's `where`), optional
  `field`, `reason`, `attribution` and `decided`. `checks.equivalence.accepted_rules` turns the entries into
  exclusion rules of the equivalence package, so a matched difference is `accepted`, listed under
  `result.accepted` with the entry's id, and fails nothing. A malformed entry, or a kind of another level,
  exits 3 with `FEN-3004` naming the entry's id.
- **Attribution.** `fenolite` (a Fenolite limit, normally a hole that c0277 closes), `upstream` (the
  original holds something odd, such as a duplicated track), `tool` (a behaviour of the original's tool) or
  `undecided`.
- **Unused entries.** An entry that matches nothing in a level that ran gives `fidelity.accepted-unused`
  (warning), so acceptances are removed as Fenolite improves. An entry of a skipped level gives nothing.
- **Recording.** `--record` plans one write of the provenance file, through `--dry-run` and `--confirm
  --plan`, with `fidelity.proof`: the Fenolite version, the date of `--timestamp`, the SHA-256 of the script
  and of each file of the original, the tolerances and each level's status. Every other member keeps its
  value; the file is written as canonical JSON (sorted keys, two spaces, a final newline). A run with an
  error plans no write.
- **Accepting.** `--accept <level>:<kind>:<where> --reason TEXT` names a difference of this run (copy the
  key from `result.differences`); the new entry, attributed `undecided`, is listed under
  `result.new_accepted` and written by `--record`. In the library, entries are written only through a
  reviewed pull request.

## Reading a failed level

Read `result.levels` first: the level whose `status` is `differs`, then its differences in
`result.differences` (or the `equiv.*` issues, located by `where`). `fenolite explain equiv.<kind>` says
what a kind means. A `render-pixels` difference names the layer and the box of the largest changed region;
its issue's hint names the primitives that the visual diff found moved, added or removed. Fix the script (or
Fenolite), or accept the difference with a reason.

## Round-trip tests

`tests/fidelity/` will read each authored KiCad project of `tests/data/fidelity/`, emit its code with
`fenolite import --to python` (c0275), build it and verify it, hermetically; `tests/kicad/fidelity/` runs the
same round trip on the corpus rows of the use `rtf` with a ratchet of allowed counts. Both wait for c0275.
Until then the authored script `tests/data/fidelity/sensor_code/design.py` is proved against the project
`tests/data/fidelity/sensor/`, a text fixture that stands in for a project saved by the KiCad GUI.

## Evidence

Levels 5 strict, 6 and 7 are `INFERRED`: unit tests with planted edits and the authored fixture. Level 8 is
`INFERRED` because one renderer draws both sides (`H-K-FID-PLOT-AGREE`). That KiCad keeps zone outlines when
it refills and saves a board is `H-K-FID-ZONE-OUTLINE`, `INFERRED` until the KiCad CI job measures it.
