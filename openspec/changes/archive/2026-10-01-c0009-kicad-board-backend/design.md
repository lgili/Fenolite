## Context

- **Boards.** A `.kicad_pcb` file is one `(kicad_pcb …)` list (S-0021). Its children are:
  - the header `version`, `generator`, `generator_version`;
  - `general`, `paper`, `title_block`, `layers` and `setup` (which holds the stack-up and the plot parameters);
  - in 8.0 and 9.0, the numbered net table `(net N "name")`;
  - `footprint`, `gr_*` graphics, `gr_text`, `segment`, `arc`, `via`, `zone`, `group`, `dimension` and newer heads (S-0001, S-0021, S-0030, S-0039).

  Lengths are millimetres with 1 nm resolution (S-0001). KiCad rejects unknown tokens at top level and in `setup`, `segment`, `footprint` and `pad` (`H-K-TOK-STRICT`, KICAD-VERIFIED on both majors). A reader that drops or invents a child therefore breaks the file.
- **Versions.** The board constants are 8.0 `20240108`, 9.0 `20241229` and 10.0 `20260206` (c0007, S-0030). The development header `20241030` maps to 9 (`H-K-TOK-DEV`). Version 9.0 renumbered layers: `B.Cu` went from 31 to 2 and `Edge.Cuts` from 44 to 25 (S-0030). Both numberings appear in authored fixtures (`tests/data/kicad/tokens/old/old.kicad_pcb`, `tests/kicad/test_geometry_frame.py`).
- **Nets.** Up to 9.0, nets are a numbered table, and items refer to them by number. From `20251028` (form row `net-by-name`), 10.0 refers to nets by name. 9.0.9 rejects the name form and 10.0.6 still reads the numbered table (`H-K-TOK-NETNAME`, `H-K-TOK-OBSOLETE`, both KICAD-VERIFIED).
- **Frame.** Two facts are KICAD-VERIFIED on both majors (c0005):
  - the rotation direction (`H-G-ROT-DIR`);
  - absolute = `at + R(θ)·stored` for a bottom footprint, with no further mirror (`H-G-BOTTOM-PLACE`).

  Three are still INFERRED: `H-G-BOTTOM-STORE`, `H-G-FLIP` and `H-G-PAD-ANGLE-ABS`. For the last one, pads stored at the footprint angle export as `R270` at 90° (S-0019).
- **Zones.** A zone holds `polygon` outlines and one `filled_polygon` per filled area and layer (S-0001). A `pts` list may hold `(arc …)` (`H-G-PTS-ARC`, KICAD-VERIFIED). The island flag is the bare `(island)` in 8.0 and 9.0, and `(island yes|no)` from `20250801` (S-0030; inventory rows `island-yes`, `island-no`). Rule areas are zones with a `keepout` child; 9.0 adds placement rule areas (row `zone-placement`, `20241009`).
- **Corpus.** Non-heavy demo boards:
  - 16 at 10.0.6: 13 at `20241229`, and one each at `20260206`, `20250513` and `20241030`;
  - 5 at 9.0.9.1, all at `20241229`, plus `kicad-demo-9-0-9-1-pcb-04`, which is published malformed.

  The three third-party boards are `20221018` (×2) and `20171130`, below the read floor (`docs/formats/kicad/corpus.md`). `pcb upgrade` exists on 10.0 only (S-0022, S-0037; `docs/formats/kicad/sexpr.md`, `H-K-FMT-RESAVE`).
- **Census of the cached corpus today (count-only, not normative)** over the 21 readable 8.0+ boards:
  - 1 674 footprints, all with a `uuid`;
  - `attr` atoms are `smd`, `through_hole`, `board_only`, `exclude_from_pos_files`, `exclude_from_bom`, `dnp`, `allow_missing_courtyard` and `allow_soldermask_bridges`;
  - `pintype` values are 11 of the twelve `PinType` values (no `open_emitter`) plus 8 forms `<type>+no_connect`;
  - via types: through and `blind` only;
  - 693 zones: 610 carry `attr` (teardrops) and 12 are rule areas. 2 have `pts` arcs, and none has several `polygon` children;
  - numbers with more than 6 decimals occur only in 3D model offsets and scales, pad corner ratios and one dimension text angle;
  - non-canonical spellings such as `0.000000` occur only in 3D model and plot-parameter children;
  - pad angles are stored in [0°, 360°), footprint angles may be negative, and zero angles are not written;
  - the copper rows of `layers` come first, in stack order;
  - 180 footprints with pads have references longer than 6 characters (4 boards), 6 pads have numbers longer than 4 characters, and 15 boards repeat a (reference, pad number) key; these widths matter for IPC-D-356 (Decision 17).
- **`pcb export pos` on 10.0.6 (observed during review, not normative; S-0020, S-0022).** Run on temporary copies of three non-heavy demo boards:
  - `--side` takes `front`, `back` or `both`, and the default unit is inches; `--units mm` prints 6 decimals of mm;
  - without `--use-drill-file-origin`, `PosX` is the stored `at` x and `PosY` is minus the stored y (file origin, Y up); bottom X is not negated without `--bottom-negate-x`;
  - `Rot` equals the stored footprint angle modulo 360° on both sides (301 bottom placements, all multiples of 90°); 270° prints as `-90.000000`.
- **Oracle code today.** `kicad-cli` is located three times, in `cli/cmd_capabilities.py`, `tests/_resources.py` and `tools/kicad_token_fuzz.py`. Three runners exist: the fuzz tool's, `tests/_kicad.py` (`run_raw`, `run`, `loads`; used by the existing tests under `tests/kicad` and by `tests/residue/test_derived_corpus.py`) and `tests/_libs.py` (`isolated_kicad_env`, `kicad`; c0008's library oracle tests). The IPC-D-356 parsing lives inside `tests/kicad/test_geometry_frame.py` (`RECORD`, `_export`).
  - The two test helpers stay for the existing tests. The `kicad-oracle` rule binds oracle tests added from this change on, which use `KicadCli`; moving the existing tests is out of scope.
- **Upstream changes.**
  - c0005 provides `Transform.placement`.
  - c0006 provides `sexpr` (`Atom`, `Node`, `parse`, `parse_bytes`, `dumps`, `tree_equal`, `walk`) and `slots` (`split`, `rebuild`, `SlotSource`, `to_ext`, `from_ext`). It also provides `_Original`, the only `SlotSource`, in `tests/corpus/test_rt0.py`.
  - c0007 provides `versions`: `inspect`, `require_readable`, `require_editable`, `version_issues`, `min_version`, `FORMAT_VERSIONS` and `UPGRADE_HINTS`.
  - c0008 provides `mod.py`. Its private `_pad`, `_drill`, `_padstack`, `_graphic` and `_Ids` hard-code `_ROOT = ("footprint",)`. It also provides `_libread.Context`, whose `kept_opaque` always reports `kicad.lib.kept-opaque`.
  - c0014 provides the machine-checked hypothesis register and its cited-id guard.
- **Layering.** `package-layering` lets `backends` top-level modules (`base`, `registry`) import `model`, `geometry` and any `backends.<x>`, and `backends.<x>` import `model`, `geometry` and `backends.base`. `tests/unit/test_import_graph.py::_pattern` returns `backends.base` and `backends.registry` as keys of their own, which `ALLOWED` does not have. So the test reports them as "not in the layering table" although the spec allows them.
- **Environment.** KiCad 10.0.6 is installed locally. The `kicad-10` job runs `tests/kicad` and `tests/corpus` with the corpus. The `kicad-9` job runs `tests/kicad` with 9.0.9 and no corpus. Stdlib only, no runtime dependency.

## Goals / Non-Goals

**Goals:**
- One backend-neutral protocol and registry, so `checks`, `placement` and the CLI reach backends only through `backends.base`.
- One `kicad-cli` runner in `src` that works on copies in an isolated environment. Every later oracle proof and command uses it.
- A typed `.kicad_pcb` reader for 8.0 and newer. It loses nothing (slots), is strict on what it models, never rounds, and models only what a named v0.1 consumer needs.
- A same-version rebuild that is tree-equal to the source, so the field emitters c0017 reuses are proved before any re-targeting.
- Placements and pads confirmed by KiCad's own exports, not only by parsing.

**Non-Goals:**
- Everything listed under Non-goals in the proposal.
- Writing anything at a target, and created content (c0017). `rebuild_board` reproduces a read board only.
- Interpreting `setup`, design settings or the stack-up. `Board.stackup` stays `None` on import.
- Assembling the board outline from Edge.Cuts graphics (c0022).

## Decisions

1. **The backend protocol is backend-neutral and lives in `backends/base.py`.** It holds `Backend`, `ReadResult` and `CapabilityReport`, and imports only `core` and `model`.
   - `Backend` is a `Protocol` with `name`, `detect(path) -> bool`, `read(path, *, issues=None) -> ReadResult` and `capabilities() -> CapabilityReport`. Later changes add operations: `write` (c0017), `lower` (c0018, c0010), validation and the `Oracle` protocol (c0013).
   - `ReadResult(content, issues, evidence)`. `content` is a `Design` for a board, and a `Library` for a footprint file or a symbol library. The property `design` returns it when it is a `Design` and raises `TypeError` otherwise. `issues` are the reader's issues followed by `design.validate()` for a board.
   - `CapabilityReport(name, read_kinds, write_kinds, targets, default_target, downgrade, operations, evidence)`.
     - `operations` lists what the backend implements, from `detect`, `read`, `write`, `lower` and `validate`.
     - In this change KiCad reports `operations == ("detect", "read")`, `read_kinds == ("kicad_pcb", "kicad_mod", "kicad_sym")`, `write_kinds == ()`, `targets == ()`, `default_target = None` and `downgrade = "unsupported"`.
     - So write, lower and validate show as unavailable until c0017, c0018/c0010 and c0013 land.
     - The spec (`backend-protocol` "Capability reports") states invariants, not these values: each field lists what is implemented, and an empty `write_kinds` means no `write`, empty `targets` and no `default_target`. Only the task 2.2 tests pin this change's exact tuples; c0017, c0018 and c0010 update those tests when they extend the report, and need no delta of the requirement.
   - `backends/registry.py` provides `register`, `get`, `all_backends` and `for_path`. The built-in KiCad backend (`backends/kicad/backend.py::KicadBackend`) is imported inside a function on first use, so `import fenolite.cli.main` stays cheap.
   - `KicadBackend.detect` decides by name only: `versions.kind_for_suffix` gives a board, footprint or symbol-library kind, or the path is a `.kicad_symdir` folder. `read` dispatches on that kind to `read_board`, `read_footprint` or `read_symbol_library`.
   - Rejected: entry-point discovery of backends (no third-party backend in v0.1). Rejected: a backend base class (a `Protocol` keeps backends independent of each other). Rejected: a field named `design` that holds a `Library` (misleading); the brief's `design` name survives as the property.

2. **One `kicad-cli` runner in `src`, always on copies.** It lives in `backends/kicad/cli.py`.
   - `find_kicad_cli(explicit=None) -> Path | None` tries, in order: the explicit path, `FENOLITE_KICAD_CLI`, `kicad-cli` on `PATH`, the macOS bundle `/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli`. An explicit path or `FENOLITE_KICAD_CLI` naming a missing file gives `None`, as `tests/_resources.kicad_cli()` does today. `cmd_capabilities` and `tests/_resources.kicad_cli()` use it.
   - `KicadCli(path, *, timeout=120)` has `version()` (the first line of `kicad-cli version`) and `major()`.
   - `run(args, *, files, env=None) -> CliRun`:
     1. It creates a fresh directory with `tempfile.mkdtemp()`.
     2. It copies each `files` entry (relative name → source file or folder) into that directory.
     3. It runs `kicad-cli` there, with `cwd` set to the directory and `args` naming the copies by relative path.
     4. The environment is the caller's, minus every variable whose name starts with `KICAD`, plus `KICAD_CONFIG_HOME=<tmp>/config` (an empty folder), `LANG=C`, `LC_ALL=C` and the explicit `env` entries.
     5. `CliRun(outcome, returncode, stdout, stderr, outputs)`: `outcome` is `exit` or `timeout`; a timed-out process is killed and has `returncode = None`. `outputs` maps the relative name of every file the run created or changed (a copy whose SHA-256 differs after the run), other than the configuration folder, to its bytes.
     6. In `stdout` and `stderr`, the temporary path becomes `<tmp>` and the home directory becomes `~`.
     7. The directory is removed afterwards. The caller's files are only ever read.
   - Helpers:
     - `load_board_svg(board)` runs the board load check of `kicad-oracle` (`pcb export svg -l Edge.Cuts --mode-single`) and returns the `CliRun`.
     - `export_pos_csv(board) -> str` runs `pcb export pos --format csv --side both --units mm`, because the default unit is inches.
     - `export_ipcd356(board) -> str` runs `pcb export ipcd356`.
     - `upgrade_board(board) -> bytes` runs `pcb upgrade --force`, which re-saves its input in place (its 10.0.6 help lists no output option), and returns the re-saved copy from `outputs`. A board already at the current format comes back byte-identical (observed on 10.0.6 for a `20260206` demo during review), so it has no `outputs` entry, and the helper returns the copy's unchanged bytes. It is 10.0-only.
     - A helper raises `KicadCliError`, which carries the `CliRun`, on a non-zero exit or a timeout. A 10.0-only helper raises `KicadCliVersionError` (`cli_code = "FEN-6002"`) on major 9.
   - `tools/kicad_token_fuzz.py` keeps its own runner, because its committed results files pin that runner's behaviour.
   - Rejected: running in place and deleting `.kicad_prl` afterwards. That races with other runs and clobbers the user's own file. Rejected: moving the fuzz tool onto the package runner now, which would change pinned results.

3. **Same-version RT1 is the acceptance of this change.** For a board file `f` with text `t`, RT1 holds when:
   - (a) `tree_equal(rebuild_board(read_board(t)), parse(t))`;
   - (b) the canonical JSON of `read_board(dumps(rebuild_board(read_board(t))))` equals that of `read_board(t)`, after every `provenance` is set to `None`. Provenance carries the SHA-256 of the bytes read, and `dumps` re-prints the layout, so the hash legitimately differs. Both sides are read from text, because `read_board` takes `header.name` from a path's stem and gives `""` for text;
   - (c) `opaque_count` and `opaque_digests` are equal.

   `rebuild_board` writes the source header unchanged. It refuses an entity without a slot list, raising `ValueError` naming the entity id: created content and canonical insertion orders are c0017's.
   - Rejected: a reader-only change judged by RT0, which cannot test the emitters.

4. **Default to opaque.** A field is modelled only when a named v0.1 consumer needs it:
   - footprints, pads and nets: c0011, c0013, c0016, c0020;
   - tracks, arcs and vias: c0016, c0019;
   - zones and fills: c0015;
   - rule areas and Edge.Cuts graphics: c0022, c0023.

   `gr_text` comes with the `gr_*` family at no extra cost. A *projected* child is an `Opaque` slot whose representable value is also copied into a model field (c0008 Decision 5). The classification per head:

   | head | modelled | projected | opaque (examples) |
   |---|---|---|---|
   | `kicad_pcb` | `version`, `generator`, `generator_version` (values in `Board.ext["kicad"]`), `layers`, net rows N ≥ 1, `footprint`, `segment`, `arc`, `via`, `zone` (not teardrop), `gr_line`, `gr_arc`, `gr_circle`, `gr_rect`, `gr_poly`, `gr_text` | — | `general`, `paper`, `title_block`, `setup`, `(net 0 "")`, teardrop zones, `group`, `dimension`, `generated`, `image`, `table`, `barcode`, `point`, `target`, `embedded_fonts`, `embedded_files`, `variants`, unknown heads |
   | `footprint` | name → `lib_ref`, `layer` → `side`, `at` → `position` and `rotation`, `uuid`, `attr` → `attributes`, `pad`, `path` → `Component.path` | `property` → `Component.ref`, `value` and `properties`; `locked` (atom or list) → `locked` | `descr`, `tags`, `sheetname`, `sheetfile`, `fp_*`, `fp_text`, `model`, `zone`, `group`, `units`, `point`, clearances, `net_tie_pad_groups`, `embedded_*` |
   | `pad` | number, type, shape, `at` (Decision 5), `size`, `layers` without wildcards, `drill` with one diameter, `uuid`, `net` | `layers` with wildcards, `padstack`, offset drill, `pinfunction` and `pintype` (into `Component.pins`) | `roundrect_rratio`, `chamfer*`, margins, `tenting`, `teardrops`, `primitives`, `options`, `zone_connect`, `remove_unused_layers` |
   | `segment`, `arc` | `start`, `mid`, `end`, `width`, `layer`, `net`, `uuid` | — | `locked`, unknown heads |
   | `via` | type atom, `at`, `size`, `drill`, `layers`, `net`, `uuid` | — | `locked`, `free`, `remove_unused_layers`, `tenting`, `padstack`, backdrill rows, `teardrops` |
   | `zone` | `net`, `layer` or `layers`, `uuid`, `name`, `priority`, one points-only `polygon`, `filled_polygon`, `keepout` (rule areas) | `layers` with wildcards | `net_name`, `hatch`, `connect_pads`, `min_thickness`, `filled_areas_thickness`, `fill`, `placement`, `locked` |
   | `filled_polygon` | `layer`, `island`, points-only `pts` | — | unknown heads |
   | `gr_*` | as `fp_*` in c0008, via `_fpmap` | `stroke` (width) | hatch fills, `net`, `locked` |
   | `gr_text` | text atom, `at`, `layer` with one atom, `uuid` | `effects` (font size and thickness) | `render_cache`, `locked` |

   - Rejected: modelling text effects, fill settings, the stack-up or design settings now. No v0.1 consumer reads them, and each would churn the model (D1.7 allows changes until v0.3).

5. **Pad frame.** (The brief's Decision 5; c0017 cites it by this number.)
   - `FootprintInstance.position` and `FootprintInstance.rotation` are the stored `at` values, on both sides. A bottom rotation is not converted, because the flip rule is open (`H-G-FLIP`, c0017).
   - `Pad.position` is footprint-local, such that absolute = `instance.position + R(instance.rotation)·pad.position`, with no further mirror (`H-G-BOTTOM-PLACE`, `H-G-ROT-DIR`, both KICAD-VERIFIED). Bottom footprints therefore keep KiCad's stored, mirrored coordinates.
   - `Pad.layers` are the actual board layers.
     - `*.Cu` expands to every copper row of the board's `layers`.
     - `*.X` expands to `F.X` and `B.X`, and `F&B.X` also to `F.X` and `B.X`.
     - A `layers` child with a wildcard is projected.
     - The expansion rule is documented with S-0001 and labelled INFERRED.
   - `Pad.rotation = pad_angle_from_board(stored, footprint) = (stored − footprint) mod 360°`.
   - `pad_angle_to_board(relative, footprint) = (relative + footprint) mod 360°`, in [0°, 360°). The emitter omits a zero angle, as the census observed.
   - `pcb.py` exports this one function pair. c0017's embedding reuses it, so a refuted `H-G-PAD-ANGLE-ABS` changes the pair and its tests, not the schema.
   - Rejected: the library frame (unmirrored children plus a flip flag). It would make absolute geometry and the `by_layer` index depend on the unverified flip rule.

6. **Edge.Cuts graphics are authoritative.** (The brief's Decision 6; c0017 cites it by this number.) `Board.outline` is `None` on import, and the reader never assembles outlines. Edge.Cuts items are ordinary `Graphic`s on layer `Edge.Cuts`. c0017 lowers a non-empty `Board.outline` and refuses a board that has both an outline and edge graphics.
   - Rejected: filling both, which would duplicate data that can disagree.

7. **Modelled means reproducible.** After mapping an item, the reader re-emits every modelled child that maps to values (not to nested entities, which are checked recursively) through `model_source`, and compares it with the original child.
   - If they are not tree-equal, the slot becomes an `Opaque` projected slot, and the value stays in the model. The reader adds the info `kicad.board.kept-opaque`, naming the reason, and the census counts it.
   - Causes include spellings such as `12.000000`, a written zero angle, an extra atom such as `knockout`, and an unquoted string.
   - RT1 (a) therefore holds by construction, and every read exercises the emitters c0017 will reuse. The census above found non-canonical spellings only in children kept opaque anyway.
   - Rejected: spelling hints in `ext`, which would be a second encoding beside slots. Rejected: comparing trees modulo number spelling, which hides emitter bugs.

8. **Zones and rule areas.**
   - A `zone` with a `keepout` child becomes a `Keepout`. Its five `keepout` settings (`tracks`, `vias`, `pads`, `copperpour`, `footprints`, `not_allowed` → true) are modelled. Any other zone becomes a `Zone`, except teardrop zones (`attr` with `teardrop`), which stay opaque root children.
   - One points-only `polygon` is modelled as the outline.
   - Arcs in `pts` (`H-G-PTS-ARC`), or several `polygon` children, set `outline = ()` on the `Zone` or `Keepout`. The `polygon` children then stay opaque slots, with the info `kicad.board.zone-outline-opaque`, and they are counted (`H-K-PCB-ZONE`).
   - Each `filled_polygon` becomes one `ZoneFill(layer, polygon, island)`, in file order. Several fills per layer are allowed. `island` is true for the bare `(island)` and for `(island yes)`, and false for `(island no)` or no flag.
   - `Zone.name` comes from `name`, and `Zone.priority` from `priority`.
   - `Zone.layers` and `Keepout.layers` expand wildcards as pads do (Decision 5), for example a rule area on `*.Cu`; a wildcard `layers` child is projected.
   - Rejected: polygonising arcs, which loses data. Rejected: a mixed contour model before a geometry consumer exists (v0.2).

9. **Nets in both forms.** The form is read per reference from its first atom: a number means the numbered form, and a string means the name form.
   - **Numbered form.** Each table row `(net N "name")` with N ≥ 1 becomes a `Net`, in table order, and N is kept in `Net.ext["kicad"]` as the pair `("number", "<N>")` (bag payloads are string pairs). Row 0 stays an opaque root slot. Pads write `(net N "name")`; segments, arcs, vias and zones write `(net N)`. A zone's `net_name` stays opaque.
   - **Name form.** References are `(net "name")`. Nets are created in the order of their first reference.
   - Net 0 and the empty name give `net_id = None`. A number missing from the table gives the warning `kicad.board.unknown-net`, `net_id = None`, and an opaque reference.
   - `Net.netclass_id` stays `None` until c0010.
   - Rejected: renumbering on read, which breaks same-version identity. Rejected: keying nets by number, because KiCad renumbers on save.

10. **Numbers.**
    - Lengths go through `Atom.to_nm(exact=True)` and angles through `core.units.parse_angle`.
    - A value that is not a whole number of nm or µdeg is never rounded. The smallest item that the model can still build without it stays opaque: the child for an optional field, or the whole item for a required one (a pad within its footprint, a root item within the board). The reader adds the info `kicad.board.inexact-length` or `kicad.board.inexact-angle`, and the census counts it by context (`H-K-UNIT`, `H-G-ANGLE`, `H-K-SEXPR-NUM-CORPUS`).
    - Rejected: rounding to the nearest nm or µdeg, which would make RT1 depend on luck.

11. **Ids.** Every entity id is a Fenolite id derived from KiCad data (`core.ids`):

    | entity | id |
    |---|---|
    | footprint | `derived_id("fp", "kicad", <fp uuid>)` |
    | component | `derived_id("cmp", "kicad", "fp:<fp uuid>")` |
    | pin | `derived_id("pin", "kicad", "<fp uuid>:pin:<number>")` |
    | pad | `derived_id("pad", "kicad", "<fp uuid>:<pad uuid>")` |
    | padstack | `derived_id("pst", "kicad", "<fp uuid>:<pad uuid>:padstack")` |
    | net | `derived_id("net", "kicad", "net:<name>")` |
    | layer | `derived_id("lay", "kicad", "layer:<canonical name>")` |
    | track, arc, via, zone, keepout, graphic, text | `derived_id(<prefix>, "kicad", <uuid>)` with `trk`, `arc`, `via`, `zon`, `kpo`, `gfx`, `txt` |
    | design header, board | `derived_id("dsn" or "brd", "kicad", "kicad_pcb")` |
    | item without a uuid | `content_id(<prefix>, "kicad", "kicad_pcb", <head>, content_hash(<compact text>, <occurrence>))` |

    - A uuid already seen in the file uses c0008's occurrence suffix (`"<uuid>:<k>"`), and the reader adds the warning `kicad.board.duplicate-uuid` (`H-K-PCB-UUID`). KiCad uuids are kept in `native_ids["kicad"]`.
    - Boards have no root uuid, so the header and board ids are constants. Ids are unique per design; nothing compares ids across designs.
    - Rejected: ids from the item index, which shift when an item is inserted. Rejected: ids from the file hash (forbidden by `design-model`).

12. **A circuit is synthesised from the board.** KiCad boards carry no schematic, but `FootprintInstance.component_id` is required, and c0011, c0013 and c0020 compare nets by component and pin.
    - **Components.** There is one `Component` per footprint:
      - `ref` and `value` come from the `Reference` and `Value` properties, and `properties` holds every property;
      - `lib_footprint_ref` is the footprint name, and `path` comes from `path`;
      - `dnp` is true when `attributes` contains `dnp`.
    - **Pins.** `Component.pins` holds one `Pin` per distinct non-empty pad number, in file order. `name` is the `pinfunction` of the first such pad. `etype` maps `pintype` through a closed table: each of the twelve `PinType` values maps to itself. Any other text, such as `passive+no_connect`, gives `unspecified` and is kept in `Pin.ext["kicad"]` as the pair `("pintype", <text>)`.
    - **Nets.** Each `Net` has members `PinRef(component id, pad number)` for every pad on it that has a number, in file order and without duplicates.
    - **Validation.** `Design.validate()` reports `model.duplicate-ref` as a warning instead of an error in two cases: when every component sharing the reference is placed only by footprints whose `attributes` contain `board_only`, and when the reference ends in `**`. These are KiCad's unannotated and board-only items, such as logos and mounting holes (S-0038).
    - Two corpus boards hold duplicates outside both cases (review census): `kicad-demo-10-0-6-pcb-08` has 4 through-hole footprints sharing one reference, and `kicad-demo-10-0-6-pcb-11` has 6 footprints with an empty reference. They stay `model.duplicate-ref` errors: they are design faults that KiCad saves, not read failures. So the read criterion counts only the reader's issues (Decision 20), and the census records `validate()` findings per board. The rule is not widened without a consumer that needs it.
    - Rejected: board imports without components, which break every consumer that keys on components.

13. **Layers.**
    - `backends/kicad/layers.py` maps a canonical KiCad layer name to a `LayerKind`:
      - `F.Cu`, `B.Cu` and `In<n>.Cu` → `copper`
      - `*.SilkS` → `silkscreen`, `*.Mask` → `soldermask`, `*.Paste` → `solderpaste`
      - `*.CrtYd` → `courtyard`, `*.Fab` → `fabrication`
      - `Edge.Cuts` → `edge`
      - `Margin` and `*.Adhes` → `mechanical`
      - `Dwgs.User`, `Cmts.User`, `Eco1.User`, `Eco2.User` and `User.<n>` → `user`
    - A name outside the table takes `copper` when its row type is `signal`, `power`, `mixed` or `jumper`, and `user` otherwise.
    - `is_canonical(name)` is true only for names the table matches, without the fallback. c0018 uses it for rule layers (`rules.unsupported-layer`).
    - The `*.Adhes` row and the fallback are Fenolite choices, labelled so in `board.md`. c0017 extends the module with the layer tables of created boards.
    - The `layers` child is one modelled field. Each row `(N "name" type ["user name"])` becomes a `Layer(name, kind, ordinal)`:
      - `ordinal` is the row index, which is the stack position for copper because copper rows come first, in stack order;
      - N, the type and the user name are kept in `Layer.ext["kicad"]` as the pairs `number`, `type` and `user_name`.
    - Layer names in items stay canonical KiCad names (`F.Cu`), like library definitions (c0008).
    - Rejected: renaming layers to neutral names on read, which every writer would have to undo.

14. **`opaque_count` and opaque digests.** `opaque_count(design)` is the number of `Opaque` slots across all `ext["kicad"]` bags of a design read from KiCad, that is the payload keys `slot:<rel>:opaque[@N]`. `opaque_digests(design)` is the `Counter` of the SHA-256 hex digests of their fragments. RT1 compares both, and c0013 and c0020 report them.

15. **Closed read-issue table.** `read_board` reports only these codes, plus the `kicad.version.*` codes of `kicad-version-gating`. `pcb.ISSUE_CODES` holds the table; c0017 keeps its write codes in a separate table, `pcb.WRITE_ISSUE_CODES`. A board's `ReadResult.issues` also hold the `model.*` codes of `Design.validate()` (Decision 1), which are model findings, not reader codes.

    | code | severity | when |
    |---|---|---|
    | `kicad.board.inexact-length` | info | a length that is not a whole number of nm (Decision 10) |
    | `kicad.board.inexact-angle` | info | an angle that is not a whole number of µdeg (Decision 10) |
    | `kicad.board.zone-outline-opaque` | info | a zone or rule-area outline with `pts` arcs or several `polygon` children |
    | `kicad.board.duplicate-uuid` | warning | a uuid already used by another item of the file |
    | `kicad.board.unknown-net` | warning | a numbered net reference that is absent from the table |
    | `kicad.board.kept-opaque` | info | a modelled or projected child that loses modelled meaning (oval drill, padstack extras, stroke type, unknown `attr` atom) or that fails the emitter check (Decision 7) |

    The shared footprint mapping reports `kicad.board.kept-opaque` on boards and `kicad.lib.kept-opaque` in library files. `_libread.Context` gains `kept_code`, which defaults to the library code.

16. **Upgraded copies keep their origin.** A `pcb upgrade --force` copy of a manifest row counts as that row's origin for `CORPUS-VERIFIED`.
    - The copy is made by the runner on 10.0.6, kept only in memory or `tmp_path`, and never committed. Its tests carry `kicad_min_major(10)` and `needs_corpus`.
    - This gives the second 8.0+ origin: the third-party rows are KiCad 5 and 7 files below the read floor.
    - The upgrade set is the 16 non-heavy 10.0.6 demos and the 3 third-party boards. The 5 readable 9.0.9.1 demos and the malformed row are not upgraded.
    - The census also runs on the third-party copies, as origin `third-party`. So the census-based labels (`H-K-UNIT`, `H-K-PCB-UUID`, `H-K-PCB-ZONE`) have counts from two origins, and each becomes `CORPUS-VERIFIED` only when both origins give 0.
    - Fallback: a 0.5-day search for native permissive 8.0+ boards. It would register a new source (S-0051 is held for it) and rows with `embeddable = false`.

17. **Cross-check with KiCad's exports.** `tests/kicad/board/_frame.py` holds the comparison.
    - **Placements.** Each row of `export_pos_csv` must match the model's footprints by reference: x equal to `PosX` and y equal to minus `PosY` at the printed precision (1 nm with `--units mm`), side, and rotation modulo 360° on both sides, as the brief asks. Duplicate references are compared as multisets. Footprints with `exclude_from_pos_files` are skipped. Bottom rotations are also recorded as data for `H-G-FLIP`; a non-orthogonal bottom angle is first seen on the authored `D1` (30°). The export frame (origin, Y direction, units, angle range) is recorded as a fact in `board.md`.
    - **Pads.** `pcb export ipcd356` writes `317` through-hole and `327` surface records (S-0019). On 10.0.6, review observed on scratch copies of two demos that the `317` records also hold every via (reference `VIA`, no pin), and that the first record can be a via. The reference field holds 6 characters and the pin field 4, so longer values are truncated (`Ipcd356Record.ref` and `pin` are these export values). Some `327` records have a blank pin, and (reference, pin) keys repeat (Context census). The comparison therefore:
      - skips via records and counts them;
      - matches every other record on the key (reference cut to 6 characters, pad number cut to 4); when several records or pads share a key, each record takes a distinct pad of that key, the nearest one within the bound;
      - compares positions relative to a reference pad, the first record whose key is unique in the export and in the model, within ±2 export units per axis (±5 080 nm), the bound of `tests/kicad/test_geometry_frame.py`: each exported value is quantised to 2 540 nm and the origin is not known (S-0019);
      - requires that pads the export puts on one net are on one model net, and the reverse (a partition test, so truncated IPC net names do not matter);
      - records for the census the counts of via records, truncated keys and ambiguous keys, and the `R` field as data for `H-G-PAD-ANGLE-ABS`, not asserted.
    - Rejected: comparing absolute positions against an assumed origin. Rejected: the file's first record as origin, because it can be a via.

18. **The shared footprint mapping moves to `_fpmap.py`.** `_pad`, `_drill`, `_padstack`, `_graphic`, `_unrepresentable`, `_Ids` and the field maps move out of `mod.py`. They are parameterised by:
    - the root chain, `("footprint",)` or `("kicad_pcb", "footprint")`, so that inventory rows are matched with the file kind and the full chain of the file (`kicad_pcb/footprint/pad/…` on boards). No anchored row sits inside a footprint today (`pad-padstack` is unanchored), so the chain keeps the match correct for future rows;
    - the graphic head map, `fp_*` or `gr_*`;
    - the kept-opaque code.

    `_fpmap.py` also holds their emitters (`emit_pad`, `emit_graphic`, `angle_atom`), which c0018's footprint writer reuses. `mod.py` keeps its behaviour, and c0008's unchanged tests guard the move.

19. **Authored CC0 board `tests/data/kicad/board/two_layer.kicad_pcb`.** It has the header `20241229`, the generator `fenolite-tests` and the generator version `"9.0"`. It uses the 9.0 layer numbering (S-0030), synthetic geometry and authored uuids, and contains:

    | item | content |
    |---|---|
    | layers | `F.Cu` and `B.Cu` as the first two rows, then paste, silkscreen, mask, `Edge.Cuts`, courtyard and fabrication rows |
    | net table | `0 ""`, `1 "GND"`, `2 "VCC"`, `3 "LED_A"` |
    | `R1` | `Fenolite_Test:R_0603`, `F.Cu`, at (20 mm, 15 mm), 90°, `(attr smd)`. Pads `"1"` (VCC) and `"2"` (LED_A) are rect 0.8 × 0.95 mm at local (∓0.8 mm, 0), stored at 90°, on `F.Cu F.Paste F.Mask`, with `pintype "passive"` |
    | `D1` | `Fenolite_Test:LED_THT_3mm`, `B.Cu`, at (35 mm, 15 mm), 30°, `(attr through_hole)`. Pads `"1"` (GND, `pinfunction "K"`) at (0, 0) and `"2"` (LED_A, `pinfunction "A"`) stored at (2.54 mm, −1 mm), the library position (2.54 mm, 1 mm) mirrored about local X. Both are circle 1.5 mm, drill 0.8 mm, on `"*.Cu" "*.Mask"`, stored at 30°, with `pintype "passive"` |
    | copper | two `segment`s and one `arc` on `F.Cu` (LED_A, VCC), one `segment` on `B.Cu` (GND), one through `via` on GND |
    | zone | `GND_B` on `B.Cu`, net GND, priority 0, rectangular outline, two `filled_polygon`s on `B.Cu`, the second with the bare `(island)` |
    | rule area | on `F.Cu`, `tracks` and `vias` `not_allowed`, the rest `allowed` |
    | graphics | four `gr_line`s on `Edge.Cuts` (50 × 30 mm), one `gr_circle` on `F.SilkS`, one `gr_poly` on `F.Fab` |
    | text | `gr_text "FENOLITE"` on `F.SilkS` |

    It is declared `origin = "authored"` in `tests/data/MANIFEST.toml`. `kicad-cli` 9.0.9 and 10.0.6 must load it.
    - Rejected: trimming a demo board, which is CC-BY-SA and would trip `tests/residue/test_derived_corpus.py`.

20. **Reader evidence.**
    - `KICAD-VERIFIED`: only placements, pad nets and relative pad positions that `pos` and IPC-D-356 confirm (Decision 17, `H-K-PCB-POS`).
    - `CORPUS-VERIFIED`: a read with no error issue from `read_board` and RT1 over two origins (`H-K-PCB-READ`). `Design.validate()` findings are counted, not judged. Census-based labels need counts from both origins (Decision 16).
    - Everything else: `INFERRED`.
    - `pcb.EVIDENCE = Evidence(Level.INFERRED, hypotheses=("H-K-PCB-READ",))` stays `INFERRED`: lossless reading does not prove what each field means. Every `Provenance` the reader creates carries it, and so does `ReadResult.evidence`.

21. **ADR-0002 "KiCad file backend"** records the decisions later changes rely on:
    - slots and opaque by default;
    - reading 8.0 and newer, and writing targets 9 and 10, with 8.0 read-only;
    - downgrade refused;
    - `kicad-cli` only as a subprocess oracle, through the package runner;
    - the pad frame of Decision 5.

    It takes the number allocated by c0001 (c0014's numbering note) and the MADR-lite sections that `tests/unit/test_adrs.py` checks. That test's `REQUIRED` list gains it.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/base.py` | `BackendOperation = Literal["detect", "read", "write", "lower", "validate"]`; `@dataclass(frozen=True, slots=True) class ReadResult(content: Design \| Library, issues: tuple[Issue, ...] = (), evidence: Evidence = Evidence())` with property `design -> Design`; `class CapabilityReport(name: str, read_kinds: tuple[str, ...], write_kinds: tuple[str, ...] = (), targets: tuple[int, ...] = (), default_target: int \| None = None, downgrade: Literal["unsupported", "supported"] = "unsupported", operations: tuple[BackendOperation, ...] = ("detect", "read"), evidence: Evidence = Evidence())` with `to_json() -> dict[str, Any]`; `class Backend(Protocol)`: `name: str`, `detect(path: Path) -> bool`, `read(path: Path, *, issues: list[Issue] \| None = None) -> ReadResult`, `capabilities() -> CapabilityReport` |
| `src/fenolite/backends/registry.py` | `register(backend: Backend) -> None` (`ValueError` on a duplicate name); `get(name: str) -> Backend` (`KeyError` naming the known backends); `all_backends() -> tuple[Backend, ...]` (sorted by name); `for_path(path: Path) -> Backend \| None` |
| `src/fenolite/backends/kicad/backend.py` | `class KicadBackend` (`name = "kicad"`, `detect`, `read`, `capabilities`); `CAPABILITIES: CapabilityReport` |
| `src/fenolite/backends/kicad/cli.py` | `MACOS_KICAD_CLI: Path`; `find_kicad_cli(explicit: str \| os.PathLike[str] \| None = None) -> Path \| None`; `@dataclass(frozen=True) class CliRun(outcome: Literal["exit", "timeout"], returncode: int \| None, stdout: str, stderr: str, outputs: Mapping[str, bytes])`; `class KicadCli(path: Path, *, timeout: float = 120)` with `version() -> str`, `major() -> int`, `run(args: Sequence[str], *, files: Mapping[str, Path], env: Mapping[str, str] \| None = None) -> CliRun`, `load_board_svg(board: Path) -> CliRun`, `export_pos_csv(board: Path) -> str`, `export_ipcd356(board: Path) -> str`, `upgrade_board(board: Path) -> bytes`; `class KicadCliError(FenoliteError)` (`run: CliRun`); `class KicadCliVersionError(KicadCliError)` (`cli_code = "FEN-6002"`) |
| `src/fenolite/backends/kicad/ipcd356.py` | `@dataclass(frozen=True, slots=True) class Ipcd356Record(code: str, net: str, ref: str, pin: str, x: int, y: int, rotation: int \| None, side: str)` (x and y in export units, Y up); `class Ipcd356(unit_nm: int, records: tuple[Ipcd356Record, ...])`; `read_ipcd356(text: str) -> Ipcd356` (`FormatError` on a missing `UNITS` line) |
| `src/fenolite/backends/kicad/layers.py` | `LAYER_KINDS` (the table of Decision 13); `layer_kind(name: str, row_type: str = "user") -> LayerKind`; `is_canonical(name: str) -> bool`; `expand_layers(names: Sequence[str], copper: Sequence[str]) -> tuple[str, ...]` |
| `src/fenolite/backends/kicad/_fpmap.py` (private, shared with `mod.py`) | `PAD_FIELDS`, `PAD_POSITIONAL`, `GRAPHIC_FIELDS`, `FP_GRAPHIC_HEADS`, `GR_GRAPHIC_HEADS`; `read_pad(ctx, node, loc, ids, *, root: tuple[str, ...]) -> Pad`; `read_graphic(…)`; `unrepresentable(node, kind) -> str \| None`; `Ids`; `emit_pad(pad: Pad, net: Node \| None) -> dict[str, list[Node \| Atom]]`; `emit_graphic(graphic: Graphic, head: str) -> dict[str, list[Node \| Atom]]`; `angle_atom(udeg: int) -> Atom` (field emitters return items per field; `pcb.ModelSource` wraps them, so `_fpmap` never imports `pcb`) |
| `src/fenolite/backends/kicad/_libread.py` | `Context.kept_code: str = "kicad.lib.kept-opaque"` |
| `src/fenolite/backends/kicad/mod.py` | unchanged public API; imports `_fpmap` |
| `src/fenolite/backends/kicad/pcb.py` | `read_board(source: str \| os.PathLike[str] \| Node, *, file: str = "", issues: list[Issue] \| None = None) -> Design`; `rebuild_board(design: Design) -> Node`; `opaque_count(design: Design) -> int`; `opaque_digests(design: Design) -> Counter[str]`; `pad_angle_from_board(stored: Udeg, footprint: Udeg) -> Udeg`; `pad_angle_to_board(relative: Udeg, footprint: Udeg) -> Udeg`; `class ModelSource` (implements `slots.SlotSource`; built from `Mapping[str, Sequence[Node \| Atom]]`); `@dataclass(frozen=True) class EmitContext(design: Design, net_form: Literal["numbered", "named"], net_numbers: Mapping[str, int])`; `model_source(entity: Entity, ctx: EmitContext) -> ModelSource`; `PIN_TYPES: Mapping[str, PinType]`; `ISSUE_CODES: Mapping[str, Severity]`; `ROOT_FIELDS`, `FOOTPRINT_FIELDS`, `TRACK_FIELDS`, `VIA_FIELDS`, `ZONE_FIELDS`, `TEXT_FIELDS` (slot maps); `EVIDENCE: Evidence` |
| `src/fenolite/backends/kicad/__init__.py` | re-exports `read_board`, `rebuild_board`, `opaque_count`, `KicadCli`, `find_kicad_cli` |
| `src/fenolite/model/board.py` | `FootprintAttribute` (8 literals); `FootprintInstance.attributes: tuple[FootprintAttribute, ...] = field(default=(), metadata=ORDERED)`; `ViaType = Literal["through", "blind", "buried", "micro"]`; `Via.via_type: ViaType = "through"`; `ZoneFill.island: bool = False`; `Zone.name: str = ""` |
| `src/fenolite/model/design.py` | `validate()` reference rule of Decision 12 |
| `src/fenolite/cli/cmd_capabilities.py` | `result.backends` from `registry.all_backends()`; `kicad-cli` path from `find_kicad_cli()` |
| `schemas/fenolite.model.v0/board.json` | regenerated |
| `tests/_resources.py` | `kicad_cli()` calls `find_kicad_cli()` |
| `tests/unit/test_import_graph.py` | `_pattern` maps `backends.base` and `backends.registry` to the `backends` row |
| `tests/unit/test_adrs.py` | `REQUIRED` gains `0002-kicad-file-backend.md` |
| `tests/kicad/test_geometry_frame.py` | parses with `read_ipcd356` |
| `tests/unit/backends/test_registry.py`, `tests/unit/backends/kicad/test_cli_runner.py`, `test_ipcd356.py`, `test_layers.py`, `test_pcb_read.py`, `test_pcb_nets.py`, `test_pcb_footprints.py`, `test_pcb_items.py`, `test_pcb_numbers.py`, `test_pcb_rebuild.py`, `tests/unit/model/test_board_import.py`, `tests/unit/cli/test_capabilities_backends.py` | hermetic tests (the runner tests use a fake `kicad-cli` script in `tmp_path`) |
| `tests/corpus/test_board_read.py`, `test_board_rt1.py`, `test_board_census.py` | `needs_corpus`; the census writes only to `FENOLITE_CENSUS_OUT` |
| `tests/kicad/board/_frame.py`, `test_board_loads.py`, `test_board_frame.py`, `test_board_upgraded.py` | `needs_kicad`; the upgraded tests also carry `kicad_min_major(10)` and `needs_corpus` |
| `tests/data/kicad/board/two_layer.kicad_pcb` | authored fixture (Decision 19) |
| `docs/formats/kicad/board.md` | fact table: modelled, projected and opaque content per head, nets, layers, pad frame, zones, numbers, oracle exports |
| `docs/adr/0002-kicad-file-backend.md`, `docs/adr/README.md` | ADR and index row |
| `docs/design-model.md`, `docs/cli-contract.md` | section "Boards read from a backend"; backend entries under "Discovery" |
| `docs/evidence/kicad-board-read.md` | census results (counts per origin and context, no content) |
| `tests/unit/cli/test_capabilities.py` | patches `cli.MACOS_KICAD_CLI` instead of the removed `cmd_capabilities._MACOS_KICAD_CLI` (task 3.1) |
| `tests/data/MANIFEST.toml` | declares the fixture `origin = "authored"` (task 5.2) |
| `src/fenolite/backends/kicad/PROVENANCE.md`, `LEGAL-ANNEX.md` | provenance rows and session rows (tasks 1.2, 9.1) |
| `docs/evidence/sources.md`, `docs/hypotheses.md` | S-0050, the widened rows S-0010, S-0022, S-0037 and S-0038, the hypothesis rows and their results (tasks 1.1, 9.2) |
| `CHANGELOG.md` | entry under Unreleased (task 9.3) |

Layering: `backends.base` imports `core` and `model`. `backends.registry` imports `backends.base` and, inside a function, `backends.kicad.backend`. `backends.kicad.*` imports `core`, `model` and `backends.base`; `pcb` imports `_fpmap`, and `_fpmap` never imports `pcb`. Tests use `geometry.Transform`. `cli.cmd_capabilities` imports `backends.registry` and `backends.kicad.cli`. All edges stay within `package-layering`. The test fix only makes `tests/unit/test_import_graph.py` match that spec.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0050 | https://www.kicad.org/blog/2025/02/Version-9.0.0-Released/ | CC-BY-3.0-or-later or GPL-3.0-or-later (site notice stated on the page) | dating the 9.0 board features this change keeps opaque or reads: pad stacks, via tenting, embedded files, zone manager, component classes |

Extended rows (same id, wider "used for" cell, no new row):
- **S-0022 and S-0037** (`kicad-cli` 10.0 and 9.0): `pcb export pos` (`--format csv`, `--side both`), `pcb export ipcd356` and `pcb upgrade --force`.
- **S-0038**: the whole pcbnew 10.0 manual page, not only `#custom_rule_syntax`. It covers footprint attributes (board only, exclude from position files and BOM, DNP), layer types and user names, rule areas and zone properties.
- **S-0010** (pcbnew 9.0 manual): footprint attributes, layer types and rule areas, beside its current cell.

Rows of other changes cited here:
- S-0001 (common syntax);
- S-0019 (IPC-D-356 observations);
- S-0020 (observed `kicad-cli` behaviour);
- S-0021 (board file structure);
- S-0024 (demo files);
- S-0030 (board version history: layer renumbering, net form, island flag);
- S-0033 (single board names at a tag);
- S-0039 (placement of tokens in KiCad-written boards).

If a URL above is already registered when this change is implemented, the existing id is cited and the row is not duplicated. Ids S-0051 to S-0054 stay unused, except S-0051 if the fallback of Decision 16 runs. No KiCad source file is read except S-0030 (version constants and dated feature notes) and S-0033 (single keyword names), for facts only; nothing is copied.

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-PCB-READ | Every readable 8.0+ corpus board reads with no error issue from `read_board` and passes RT1 (Decision 3, both sides read from text). The boards are the 21 readable non-heavy demos (16 at 10.0.6, 5 at 9.0.9.1; the malformed row excluded) and the `pcb upgrade --force` copies, made on 10.0.6, of the upgrade set: the 16 non-heavy 10.0.6 demos and the 3 third-party boards (S-0021, S-0024) | `tests/corpus/test_board_rt1.py::test_rt1`; `tests/kicad/board/test_board_upgraded.py::test_upgraded_read_rt1` | 0 error issues from `read_board` (`Design.validate()` findings counted, not judged) and RT1 (a), (b), (c) on every board of both origins; target `CORPUS-VERIFIED` |
| H-K-PCB-POS | Model placements equal `pcb export pos` (reference, x, y, side, and rotation modulo 360° on both sides), and model pad positions and pad nets agree with `pcb export ipcd356` (S-0019, S-0020, S-0022, S-0037) | `tests/kicad/board/test_board_frame.py::test_pos`; `tests/kicad/board/test_board_frame.py::test_ipcd356` | every `pos` row matches, and every non-via IPC-D-356 record matches a distinct pad within ±2 export units per axis relative to the reference pad, with equal net partitions (Decision 17); on 10.0.6 for the 21 readable non-heavy demos and the authored board, and on 9.0.9 for the authored board |
| H-K-PCB-UUID | `uuid` values are unique within one board file (S-0021) | `tests/corpus/test_board_census.py::test_uuid_repeats`; `tests/kicad/board/test_board_upgraded.py::test_upgraded_census` | counts per origin (native demos; upgraded third-party copies); `CORPUS-VERIFIED` only when both give 0, otherwise each repeat counted per board and head |
| H-K-PCB-ZONE | Zone and rule-area outlines with `pts` arcs or several `polygon` children are rare and keep opaque outlines (S-0021, S-0024; arcs in `pts`: `H-G-PTS-ARC`) | `tests/corpus/test_board_census.py::test_zone_outlines`; `tests/kicad/board/test_board_upgraded.py::test_upgraded_census` | counts recorded per origin (native demos; upgraded third-party copies); every such zone has `outline == ()` and an opaque `polygon` slot |
| H-K-UUID-KEEP | KiCad keeps every `uuid` of a board when it re-saves it (S-0020, S-0022) | demo half: `tests/kicad/board/test_board_upgraded.py::test_uuid_keep`; Fenolite-written half: placeholder `tests/kicad/board/test_uuid_keep_written.py::test_uuid_keep_written` (c0017) | on 10.0.6, the unmasked `uuid` multiset of each of the 16 non-heavy 10.0.6 demos equals that of its `pcb upgrade --force` copy |

Rows already registered that this change settles or feeds:
- `H-K-UNIT` becomes `CORPUS-VERIFIED` if no length context is inexact in either origin (native demos; upgraded third-party copies). Otherwise it is refuted, and a successor row with the suffix `-2`, limited to length contexts and carrying the counts, is registered by task 9.2.
- `H-G-ANGLE` gets the census of non-representable angles.
- `H-K-SEXPR-NUM-CORPUS` gets its over-precise atoms classified by context.
- `H-G-BOTTOM-PLACE` and `H-G-PAD-ANGLE-ABS` get IPC-D-356 positions and `R` fields over the pads of the 21 readable non-heavy demos, as supporting data.
- `H-G-FLIP` gets the bottom-rotation rule observed in `pos`, as supporting data.
- `H-K-TOK-CONSTANTS` (board 9) gets the header census of the 9.0.9.1 demos.

The reader's behaviour does not depend on these outcomes, except the pad-angle pair (Decision 5), whose settlement belongs to c0017.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Lossless read and same-version rebuild (RT1) | CORPUS-VERIFIED (`H-K-PCB-READ`): the 21 readable demos at 10.0.6 and 9.0.9.1, plus upgraded copies of the 16 10.0.6 demos and the 3 third-party boards on 10.0.6 | `tests/corpus/test_board_rt1.py`, `tests/kicad/board/test_board_upgraded.py` |
| Footprint placement (reference, position, side, rotation on both sides) | KICAD-VERIFIED (`H-K-PCB-POS`) on 10.0.6 (local and `kicad-10`: demos and fixture) and 9.0.9 (`kicad-9`: fixture) | `tests/kicad/board/test_board_frame.py::test_pos` |
| Pad positions relative to a reference pad, and the pad-net partition | KICAD-VERIFIED (`H-K-PCB-POS`) on 10.0.6 (demos and fixture) and 9.0.9 (fixture) | `test_board_frame.py::test_ipcd356` |
| Rebuilt boards load | KICAD-VERIFIED on 10.0.6 (corpus and fixture) and 9.0.9 (fixture) | `tests/kicad/board/test_board_loads.py` |
| Pad-angle convention (relative to the footprint) | INFERRED (`H-G-PAD-ANGLE-ABS`) until c0017; `R` fields recorded | unit tests, census |
| Bottom rotation reported by `pos` | part of `H-K-PCB-POS` above; also supporting data for `H-G-FLIP` (recorded) | `test_pos` |
| uuids kept by `pcb upgrade` (demo half) | KICAD-VERIFIED (10.0.x) (`H-K-UUID-KEEP`) | `test_board_upgraded.py::test_uuid_keep` |
| uuid uniqueness, zone outlines | CORPUS-VERIFIED when both origins (native demos; upgraded third-party copies) give 0, otherwise INFERRED with counts recorded (`H-K-PCB-UUID`, `H-K-PCB-ZONE`) | `tests/corpus/test_board_census.py`, `test_board_upgraded.py::test_upgraded_census` |
| Exact lengths in length contexts | CORPUS-VERIFIED (`H-K-UNIT`) when both origins give 0, or refuted with a successor and counts | census on both origins |
| Meaning of tracks, vias, zones, fills, rule areas, graphics, texts, layer kinds, pin types, circuit synthesis | INFERRED (`H-K-PCB-READ`; S-0001, S-0021, S-0038) | unit tests on the fixture and inline boards |
| Version policy, vocabulary errors, issue codes, ids | mechanical (unit tests) | `test_pcb_read.py`, `test_pcb_numbers.py` |
| Runner (copies, isolation, timeout, sanitising) | mechanical (fake `kicad-cli`) | `tests/unit/backends/kicad/test_cli_runner.py` |
| IPC-D-356 parser | INFERRED format (S-0019, S-0020); exercised against 9.0.9 and 10.0.6 exports | `test_ipcd356.py`, `tests/kicad/test_geometry_frame.py`, `test_board_frame.py` |
| Protocol, registry, `capabilities` | mechanical (unit and consistency tests) | `tests/unit/backends/test_registry.py`, `tests/consistency` |

`pcb.EVIDENCE` and `KicadBackend.capabilities().evidence` are `INFERRED` (`H-K-PCB-READ`), and they stay so after this change.

## Budget (about 1.5 weeks; plan item 0009, part 1 of 3)

| work | days |
|---|---|
| registers and `board.md` | 0.75 |
| `base`, `registry`, `capabilities`, import-graph fix, ADR | 0.75 |
| runner and the IPC-D-356 move | 0.75 |
| model deltas and schemas | 0.75 |
| `_fpmap`, layers, board pads and frame, authored board | 0.75 |
| board-level heads (nets, tracks, vias, zones, rule areas, graphics, texts) | 1.25 |
| circuit, ids and number policy | 0.5 |
| `ModelSource`, emitter check and rebuild | 0.75 |
| corpus read, RT1, upgraded copies, frame check and census | 1.0 |
| closing | 0.5 |
| **total** | **7.75** |

The plan's 3.0-week line for 0009 covers this change, c0017 and c0018. This part takes 7.75 days. If it overruns, the `H-K-TOK-CONSTANTS` census and the `gr_text` mapping are cut first (`gr_text` stays opaque). The runner, the model deltas, RT1 and the frame cross-check are not optional. `inspect --summary` moved to c0013, and the throughput, path census and byte identity to c0020, to make room for the runner.

## Risks / Trade-offs

- [Model churn from KiCad detail] → Opaque by default, with a named consumer for every modelled field. D1.7 allows model changes until v0.3.
- [The pad-angle convention is refuted in c0017] → The reader and embedding share one conversion pair, so a refutation changes that pair and its tests, not the schema.
- [Pure-Python speed on large boards, made worse by the emitter check] → Heavy boards stay opt-in. The check emits small nodes only, and c0020 measures throughput. If the check doubles read time on the non-heavy corpus, it becomes a flag for tests only, and RT1 (a) still guards the result.
- [Review rejects upgraded copies as an origin] → An explicit corpus-policy requirement with its rationale, and the time-boxed search for native 8.0+ boards (Decision 16).
- [`pcb export pos` reports a bottom rotation other than the stored angle, for example on 9.0.9 or at the authored 30°] → 10.0.6 showed equality on 301 bottom placements (Context). A failure refutes `H-K-PCB-POS` for bottom rotation only, with a successor row (suffix `-2`) recording the observed rule; the model keeps the stored angle, and c0017 settles `H-G-FLIP` with three independent outputs.
- [Projected children cannot be edited without reconciliation] → c0017 owns reconciliation. Children kept opaque only by the emitter check are pure spellings of one field, which c0017 may re-emit when the value changes (Open Questions).
- [Overrun, as in c0006–c0008] → The first cuts are named in "Budget".

## Migration Plan

- Additive. New modules, four model fields with defaults (documents written before this change still load), one warning rule in `validate()`, and a regenerated `board.json`. `mod.py` keeps its behaviour, and the fuzz tool keeps its runner. To roll back, remove the new modules and fields, restore `mod.py` and `capabilities`, and regenerate the schemas.

## Open Questions

- **(User.)** Do upgraded copies count as the second origin? `pcb upgrade --force` copies of the third-party boards, made in a temporary folder on 10.0.6 and never committed, would count for `CORPUS-VERIFIED`. The alternative is to require native permissive 8.0+ boards from a new origin, which needs a search with an uncertain outcome. The default is yes, with the 0.5-day search as fallback (Decision 16).
- **(User.)** Is the re-baselined budget accepted? It is about 31 working days for this batch and about 102 to v0.1, against about 36 left in the plan's lines. The proposed cut order is c0023 to v0.2a first, then c0021, then c0020's measurement-only items. The default is yes. This change's own first cuts are named in "Budget".
- **c0014's cited-id guard** scans active changes. This design cites `H-K-PCB-*` and `H-K-UUID-KEEP` before task 1.1 registers them. c0014 Decision 8 accepts, inside an active change, the ids listed under "Hypotheses registered by this change", and requires them registered everywhere else. So task 1.1 is the first commit of the implementation. Conditional successor rows are named only by suffix here, because they are not proposed ids.
- **Brief corrections** (proved against the repository):
  - RT1 (b) compares canonical JSON without provenance, because `Provenance.file_sha256` hashes the bytes read and `dumps` changes the layout.
  - The IPC-D-356 bound is ±2 export units on positions relative to a reference pad record, not ±1 270 nm absolute, because the export origin is unknown (S-0019, `tests/kicad/test_geometry_frame.py`).
  - Board reads add a sixth code, `kicad.board.kept-opaque`, because the moved footprint mapping reports kept-opaque children (`_libread.Context.kept_opaque`).
  - `ReadResult.content` replaces the field name `design`, because the backend also reads library files (`read_kinds` includes `kicad_mod` and `kicad_sym`).
  - `KicadCli.run` gains an optional `env` argument for c0021's probes.
  - `export_pos_csv` adds `--units mm` to the brief's command, because `pcb export pos` defaults to inches (observed on 10.0.6, Context); millimetres with 6 decimals compare at 1 nm.
  - `*.Adhes` layers, which the brief's table omits, map to `mechanical`.
  - `CapabilityReport` gains `operations`, the field through which write, lower and validate show as unavailable (brief Decision 1).
  - The draft's decision order changed during review; Decisions 5 (pad frame) and 6 (Edge.Cuts) keep the brief's numbers, which c0017 cites.
  - RT1 (b) reads both sides from the file text. `read_board` names the design after a path's stem and gives `""` for text, so the brief's `read_board(f)` against a re-read of text would differ in `header.name` (`DesignHeader.name`, review 2026-10-01).
  - The IPC-D-356 comparison skips via records, matches on the truncated reference (6 characters) and pin (4), pairs repeated keys by nearest position, and takes its origin from a pad record, because the export's first record can be a via (observed on 10.0.6 during review; Decision 17).
  - "Read with 0 errors" counts the reader's issues only. Two 10.0.6 demos hold duplicate references that `Design.validate()` reports as errors (Decision 12).
  - Census-based labels (`H-K-UNIT`, `H-K-PCB-UUID`, `H-K-PCB-ZONE`) need counts from two origins, as `CORPUS-VERIFIED` does for `H-K-PCB-READ`. So the census also runs on the upgraded third-party copies (Decision 16).
  - The 9.0.9 runs of `tests/kicad/board` are the `kicad-9` job: the pinned 9.0.9 image has Python 3.11 but no `pytest`, so a local `docker run` of these tests is not available.
- **Cross-change notes for c0017** (this is the earlier text):
  - c0017 Decision 18 asks for absolute pad positions within ±1 270 nm through this parser. Unless c0017 first establishes the export origin, it should use the matching of Decision 17 (via records skipped, truncated keys, ±2 export units relative to a reference pad record).
  - c0017 should add `write` to `operations` when it sets `write_kinds`, and its `H-K-UUID-KEEP` test id is the placeholder cited in the hypothesis table above.
- **Should `<type>+no_connect` pin types map to `<type>`?** They are frequent in the demos. The default is `unspecified`, with the text kept in `Pin.ext["kicad"]`, as the brief says. A later change can map them once a consumer needs the flag.
- **Re-emitting spelling projections.** Children kept opaque only by the emitter check (Decision 7) are spellings of a single modelled value. Should c0017 re-emit them from the model when the value changes, instead of raising `kicad.board.projection-read-only`? The default is that c0017 decides; the corpus census reports how many there are.
