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
   **Copy mode** (change c0281): when the provenance file holds an import record (`fenolite import`, or a
   library record holding it as `import`) whose `copy` is not `false`, the design is a copy of someone
   else's finished board, and the build's copper guard runs in `warn`: its findings stay in `issues` as
   warnings and the levels run. Otherwise it refuses as `fenolite build` does. `--copper-check refuse|warn`
   overrides both; `result.build` reports `copper_check` and `copy`.
2. **Read.** The original (a KiCad project folder, `.kicad_pro` or `.kicad_pcb`, or an Altium `.PrjPcb`) and the build are
   read as `fenolite equivalent` reads its sides. A `.kicad_pro` (or a folder of one project) names one
   project: only its `.kicad_pro`, the board and `.kicad_dru` of its stem and the sheet tree of its root
   sheet are read, recorded and rendered, never a second project of the same folder. A KiCad board older than 9.0 is refused (`FEN-3003`, exit
   3) unless `--upgrade` upgrades a copy with `kicad-cli pcb upgrade`, which `fidelity.input-upgraded`
   records with the tool version and both SHA-256.
3. **Compare.** Levels 1 to 7, level 5 with its strict rule (every track, arc and via item by item), then
   level S, then level 8. Level 7 also counts the opaque root items of each side by kind (teardrops,
   groups, generated items, images) and reports `opaque-count` for a kind whose counts differ, so a board
   whose import left copper out cannot pass unless the difference is accepted. `--levels 1-7,8` runs a subset. A level a side cannot reach is `skipped` with
   `fidelity.level-skipped` and its reason, never passed silently.

For fully qualified native **padvia derived caches only**, verify-source can
prove their regenerated result with one KiCad10 tool/version/options on both
private input copies. Both sides must retain enabled same-net/layer parents,
exact numbered-pad partition bindings and matching supported project settings;
existing editable model levels still compare strictly. Only qualified derived
cache nodes are stripped from the copies, then native refill must save output.
The complete regenerated polygon/fill/settings multisets compare exactly,
including rational vertices, holes, layers and duplicate multiplicity. Native
non-simple rings retain every crossing and vertex; proper crossing counts are
exposed and no geometry-validity certificate is claimed. Only
native identifiers and derived priority ordinals are normalized; normal zone
priorities and pure `equivalent` remain strict. No tolerance or glyph mask is
used for this copper proof.

The `derived_cache` summary/proof has closed known fields. Only unjudged native rule delta `a`/`b` leaves carry uninterpreted canonical wire JSON: null, bool, integer, string and recursive arrays; numbers are rational integer triples and mappings are key/value arrays. Raw objects, floats/nonfinite values and unsupported Python values are not this canonical shape. This metadata does not prove rule or geometry equality.

Level7 `summary.derived_cache` and recorded proof retain raw counts/hashes,
stripped native-input hashes, tool/version/command/outcome, regenerated counts
and geometry hashes. A raw165→167 change remains visible: regenerated equality
does not assert original cache equality. Missing tool requires installation
(`FEN-6001`); native9 refuses this feature (`FEN-6002`). Unknown/unqualified
caches retain the ordinary opaque comparison. Failed native execution, changed
configuration or unequal complete regenerated geometry cannot qualify equality.
The summary explicitly lists unjudged native project setting/rule deltas:
only the existing supported five minima, max_error and teardrop settings are
judged here; whole project JSON/rule-file equality and a safety DRC gate are not claimed.
Rule-file syntax is checked before native regeneration: KiCad may otherwise
report exit0 while ignoring a malformed custom rule file.

Native teardrop generation orders neighbouring teardrops of different nets by the identities of their
pads, tracks and vias, and one RoyalBlue teardrop outline depends on track order. By c0275's design a
build gives copper its own identities and order, so before its one native run, side b's private native
input copy takes the identity of each feature-equal side-a segment, arc, via and pad and the side-a file
order of its root segments, arcs and vias, in the slots they occupy
(`summary.derived_cache.identity_preparation`, c0384). Objects pair by their complete non-identity content
with nets by declared name, under two canonical rules listed in `canonical_nets` with each old and new
spelling: a stored `{slash}` reads as the `/` of its label text (`slash`), and an `unconnected-(` net that
carries exactly one pad and whose name KiCad derives from that pad is keyed by the pad's reference and
number (`unconnected_single_pad`); such a net on no pad or several pads, a name that does not derive from
its pad, or two nets under one key refuse. Changed, missing, extra or duplicated objects refuse the
preparation (status `refused`, side b unprepared), except one proven case: exactly two pads identical
apart from their identity, listed in `identical_pairs`. An object whose side-a identity names several
objects keeps its own; `source_aliases` lists them with their count as "source alias, not rewritten". The
receipt lists every rewritten identity (`rewritten`) and every moved object with its old and new position
(`moved`). The result is labelled by what was prepared (`label`: "L7 after identity and order
preparation", or identity or order alone), never plain level 7: it measures geometry once identity and
order are aligned and does not claim that Fenolite keeps the source's identities or order. The editable
model, the sources and every written file stay untouched. A generated board never shares the source's
identities, so a board with teardrops always gets the prepared label, even one that was equal unprepared
(the public complex_hierarchy demo): one native run per side leaves no unprepared run to report.

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

`--record` writes the reason of each skipped level to `fidelity.proof.skipped`. The library's gate (c0279)
accepts a skipped level only with such a reason, never `build-failed`; `drawn-unavailable` now means that
a side's sheets could not be read.

Level 8 renders the board of both sides, layer by layer, and each schematic sheet that both sides hold
under the same path, with the viewer's scene builders (`docs/equivalence.md`, "Level 8: presentation").
The explicitly resolved project-root sheets also pair when import makes the
root filename safe, using the original root's panel identity. Every primitive
is still compared. Child filenames keep their exact identities; a root spelling
that collides with a distinct child panel refuses instead of overwriting it.
Missing roots are not invented and no pixel tolerance or acceptance is added
by this pairing (c0330).

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
it refills and saves a board is `H-K-FID-ZONE-OUTLINE`, `KICAD-VERIFIED (10.0.x)` since the kicad-10 CI job of
2026-11-05 measured it; 9.0.x has no `pcb upgrade` and is out of scope.

## Round-trip test categories

`make fidelity` runs the authored sensor, hierarchy, bus and Repeat projects through the actual importer,
explicit build and every `verify-source` level (1–7, S and 8), alongside the ratchet and corpus contract
tests. `make check-fast` includes this category. The shared `roundtrip` helper reads native project
bytes into a fresh temporary folder, uses strict copper matching and the default zero geometry
tolerances, accepts no difference automatically and starts no external process.

The generated hierarchy, bus and Repeat originals include a small authored copper stub so strict
level 5 is reached. The sensor also compares its actual tracks, arcs and vias. These are authored text
stand-ins; the literal KiCad GUI-save task remains open.

`make fidelity-corpus` uses only the allow-listed `rtf` descriptors in the public corpus manifest. The
helper copies the declared project, board, rules and child sheets into the test temporary folder and
checks their SHA-256 before import. No fetched board, schematic or derived code belongs in this repository.
The count-only `tests/kicad/fidelity/accepted.toml` ratchet fails when a count grows and when it shrinks;
improvements require lowering the reviewed entry. Pending rows have no reviewed baseline and are
reported as skips; they grant no passing corpus proof. See `docs/evidence/fidelity.md` for their exact state.

The planted-junction test first requires the unmodified all-level round trip to pass, then removes one
electrically redundant endpoint junction in the writer and requires exactly one `item-missing` at S.
A connectivity-critical deletion still belongs to the build's earlier byte-connectivity guard.
