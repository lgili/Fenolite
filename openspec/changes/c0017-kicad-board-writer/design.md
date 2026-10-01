## Context

- **Who needs a writer.** `build` (c0011), fill (c0015), routing (c0016), layout preservation (c0019), the rules proofs (c0018) and the project proofs (c0010) all write `.kicad_pcb` files for KiCad 9.0 or 10.0. c0009 only rebuilds a board at its own version (RT1).
- **Header.** The board constants are `20241229` (9.0) and `20260206` (10.0) (`FORMAT_VERSIONS`, S-0030, c0007). `versions.GENERATOR` is `"fenolite"`. KiCad-written boards carry `(generator_version "9.0")` or `"10.0"`, and nightly builds write `"8.99"`/`"9.99"` (S-0039, S-0024; `docs/formats/kicad/versions.md`). What other `generator_version` values do is unknown (`H-K-GENVER`, registered here).
- **Net forms.** From `20251028`, items reference nets by name (form row `net-by-name`, S-0030, S-0024). 9.0.9 rejects named nets under a 9.0 header, and 10.0.6 loads them (`H-K-TOK-NETNAME`, `KICAD-VERIFIED`). 10.0.6 still reads the numbered net table, zone `net_name` and `filled_areas_thickness`, and the plot rows `hpglpennumber`, `hpglpenspeed`, `hpglpendiameter` and `plotinvisibletext`, but no longer writes them (`H-K-TOK-OBSOLETE`; inventory rows with `until_major = 9`). `check_emittable` ignores form rows (c0007 Decision 10), so the net form is a writer duty.
- **Net 0.** c0009 keeps the root row `(net 0 "")` as an opaque root slot, models rows N ≥ 1 only, and reads net 0 or the empty name as `net_id = None` (c0009 Decision 9). KiCad 9 writes `(net 0)` and `(net_name "")` on unconnected zones and rule areas: the `20241229` demos `multichannel_mixer`, `One-Air-Max` and `RoyalBlue54L-Feather` hold 4, 3 and 2 of them (S-0058). The 10.0.6-written `pic_programmer` holds none, and a `pcb upgrade --force` copy of `RoyalBlue54L-Feather` made with 10.0.6 while revising this design (2026-10-01) has neither a net table nor any `net` or `net_name` child on those two zones (S-0020, observed; `INFERRED` until the 9 → 10 demo test of Decision 23 loads such boards).
- **Layer numbers.** KiCad 8.0 numbers `B.Cu` 31 and `Edge.Cuts` 44; 9.0 numbers them 2 and 25 (S-0030). c0007's authored fixtures show both: `tests/data/kicad/tokens/old/old.kicad_pcb` (`20240108`) and `tests/data/kicad/tokens/skeleton.kicad_pcb` (`20241229`). Layer numbers also appear inside content Fenolite keeps opaque, such as the `pcbplotparams` `layerselection` masks of the skeleton.
- **Skeleton.** The skeleton holds `version`, `generator`, `generator_version`, `general` (`thickness`, `legacy_teardrops`), `paper`, `layers`, `setup`, the net table and a few items. It loads on 9.0.9, and re-headed to `20260206` on 10.0.6 (`H-K-TOK-OBSOLETE`).
- **Frame.** Absolute = `at + R(θ)·stored`, with no further mirror for bottom footprints (`H-G-ROT-DIR`, `H-G-BOTTOM-PLACE`, `KICAD-VERIFIED` on 9.0.x and 10.0.x). Three rows are `INFERRED` from one footprint of one board (S-0019):
  - `H-G-BOTTOM-STORE`: stored bottom children equal the library footprint mirrored about local X;
  - `H-G-FLIP`: how a library angle maps to a stored bottom angle. The GUI's flip axis is the user option "Flip board items L/R" (S-0010), which the file does not record;
  - `H-G-PAD-ANGLE-ABS`: stored pad angles are absolute.

  c0009's model keeps footprints in the stored frame (`FootprintInstance.rotation` is the stored angle, and `Pad.rotation` is the stored angle minus the footprint angle, through `pad_angle_from_board`/`pad_angle_to_board`).
- **Library parity in DRC.** 10.0.6 demo projects list the rule-severity keys `lib_footprint_mismatch` and `lib_footprint_issues` (S-0058, observed). Whether `kicad-cli` 9.0.9 runs this check is unknown (`H-K-LIB-DRC`, registered by c0014).
- **DRC JSON.** The schema `drc.v1.json` exists at tags 10.0.6 (S-0055) and 9.0.9.1 (S-0056):
  - required top-level keys: `source`, `date`, `kicad_version`, `violations`, `unconnected_items`, `schematic_parity`, `coordinate_units`;
  - optional keys: `included_severities`, and `ignored_checks` at 10.0.6 only;
  - a violation has `type`, `description`, `severity`, `items`, `excluded` and `comment`; an item has `uuid`, `description` and `pos {x, y}`;
  - `type` has no enumeration, and no numeric field holds a measured distance;
  - `coordinate_units` is one of `mm`, `mils`, `in`;
  - the schema file itself has a trailing comma at both tags, so it is not strict JSON (S-0057).

  `pcb drc` takes `--format json`, `--severity-all` and `--exit-code-violations` (S-0022, S-0037). `--exit-code-violations` is unusable on minimal boards, which always carry some violation (c0006 Decision 12).
- **Mini library.** `tests/data/libs/Mini.pretty` is `20260206`, which 9.0.9 cannot load. `Mini_v9.pretty` holds only `Mini_R_0603` (c0008). `check_emittable(…, 9)` on today's 10.0 files reports one 10-only token in each footprint, `duplicate_pad_numbers_are_jumpers`, plus the header. The QFP's pads 9–16 and 25–32 have library angle 90°.
- **Licence.** Demo boards and projects are CC-BY-SA-4.0 (S-0023). They are read for facts and run as oracles in `tmp_path`, never committed. `drc.v1.json` is in KiCad's GPL tree: only key names are recorded, as for S-0033, and the file is never vendored or read at runtime.
- **Upstream changes.**
  - c0006: `sexpr` (`Atom.from_nm`, `Atom.string`, `dumps`, `parse_fragment`, `walk`, `tree_equal`) and `slots` (`split`, `rebuild` with `canonical`, `opaque_child`, `to_ext`/`from_ext`).
  - c0007: `versions` (`FORMAT_VERSIONS`, `TARGET_MAJORS`, `DEFAULT_TARGET`, `GENERATOR`, `major_for`, `inspect`, `require_editable`, `check_target`, `check_emittable`, `DowngradeRefusedError`), the token inventory and both CI jobs.
  - c0008: `FootprintDef`, `read_footprint`, the mini library and `tests/kicad/libs/test_mini_oracle.py`.
  - c0009: `backends/base.py` (`ReadResult`, `CapabilityReport`), `registry.py`, `pcb.py` (`read_board`, `rebuild_board`, `ModelSource`, `opaque_count`, `opaque_digests`), `_fpmap.py` (pad and graphic mapping parameterised by root chain), `layers.py`, `cli.py` (`KicadCli`, `CliRun`, `load_board_svg`, `export_pos_csv`, `export_ipcd356`, `upgrade_board`), `ipcd356.py`, the pad-angle pair, `FootprintInstance.attributes`, `Via.via_type`, the fixture `tests/data/kicad/board/two_layer.kicad_pcb`, and the demo half of `H-K-UUID-KEEP`.
  - c0014: the `H-K-LIB-DRC` row (pending, placeholder `tests/kicad/board/test_flip_oracle.py::test_lib_drc`) and the register guard `tests/unit/test_hypotheses_register.py`.
- **Environment.** KiCad 10.0.6 is installed locally. The `kicad-10` job runs `tests/kicad` and `tests/corpus` with the non-heavy `rt0` corpus. The `kicad-9` job runs `tests/kicad` with no corpus, so every 9.0.9 proof uses authored CC0 data.
- **Constraints.** Stdlib only. `backends.kicad` imports `model`, `geometry` and `backends.base`; `cli` imports anything. Budget 7.75 working days.

## Goals / Non-Goals

**Goals:**
- One writer that turns a read or created design into a board KiCad 9.0 or 10.0 loads, and refuses or reports every loss.
- Library footprints placed on either side, with uuids and ids that do not depend on a seed.
- The three `INFERRED` frame rows settled by KiCad's own library-parity check, with negative controls, and checked for consistency by pos and IPC-D-356 on both majors.
- DRC verdicts read from the JSON report into neutral types.
- Oracle outcomes pinned per `kicad-cli` version, so an image bump that changes behaviour fails loudly.

**Non-Goals:**
- Everything listed under Non-goals in the proposal.
- Byte identity with KiCad's printer, KiCad's sort of pads and graphics on save, and the 9.0 atom wrap (c0020 measures them).
- A mixed line/arc outline (v0.2), `path`/`sheetname`/`sheetfile` links to a schematic (c0011, v0.2a), and the 3D frame of footprint models.

## Decisions

1. **Target policy.** `write_board(design, *, target=DEFAULT_TARGET, allow_lossy=False)` accepts `target` in `TARGET_MAJORS = (9, 10)`.
   - A design read from a file carries its source header in the board's `kicad` bag (c0009). `pcb.source_info(design)` returns its `FormatInfo`, or `None` for a created design.
   - For a read design, `require_editable(info)` runs first (future → `FutureFormatError`, `FEN-3002`), then `check_target(info, target)` (downgrade → `DowngradeRefusedError`, `FEN-7002`).
   - Sources of major 9 are written at target 9 or 10, and sources of major 10 at 10. Majors come from `major_for`, so the development header `20241030` counts as 9.
   - A created design may be written at either target.
   - Rejected: writing a downgrade by dropping 10-only content (the capability resolver, v0.5a).

2. **KiCad 8 boards are read-only.** When `major_for(FileKind.BOARD, info.version) == 8`, `write_board` raises `LegacyEditRefusedError` (`cli_code = "FEN-7003"`, exit 7) for every target. `read_board` keeps reading them.
   - Reason: 9.0 renumbered layers (S-0030), and numbers also live in opaque content such as plot layer masks, which Fenolite does not model.
   - Hint: "convert the board with 'kicad-cli pcb upgrade' (KiCad 10.0) or re-save it in KiCad 9.0, then edit the converted copy".
   - Rejected: renumbering layers inside opaque fragments. It needs a model of every mask and layer-number field, and the exhaustive 8.0 vocabulary is not needed while 8.0 is read-only.

3. **Created boards.** A design without a source header is *created*. Its root gets exactly the head set of c0007's skeleton:
   - `version`, `generator` and `generator_version` (Decision 4);
   - `(general (thickness T) (legacy_teardrops no))`, where T is the sum of `Board.stackup` thicknesses, else 1.6 mm (the skeleton's value, a Fenolite default);
   - `(paper "A4")` (c0012 writes paper and title block later);
   - `layers`, from `Board.layers`;
   - `(setup (pad_to_mask_clearance 0))`, without `pcbplotparams`;
   - for target 9 only, the net table (Decision 5).

   Then the content, in the order of Decision 8.
   - `layers.created_layers(copper: Literal[2, 4]) -> tuple[Layer, ...]` builds the two layer sets. Each `Layer.ext["kicad"]` holds the KiCad number, type and user name exactly as c0009's reader stores them, so read and created layers share one emitter.
   - Numbers follow the 9.0 scheme of the skeleton (`F.Cu` 0, `B.Cu` 2, `In1.Cu` 4, `In2.Cu` 6, `Edge.Cuts` 25), which both majors load. The full tables (copper plus `F`/`B` `Adhes`, `Paste`, `SilkS`, `Mask`, `CrtYd`, `Fab`, the user drawing layers, `Edge.Cuts` and `Margin`, with user names) are recorded in `board.md` from 10.0.6-written demo boards (S-0058). The triad (2 copper layers) and the created test board (4 copper layers, Decision 19) load them on both majors.
   - Every head and field name the writer can create must match an inventory row, appear in the skeleton, or be listed in `pcb.FLOOR_HEADS`. The skeleton lacks several created names (`arc`, `mid`, `gr_line`, `gr_arc`, `gr_circle`, `center`, `gr_poly`, `gr_text`, `filled_polygon`, `keepout`, `locked`), and the inventory has no row for them, because its scope is names introduced after 8.0 (c0007 Decision 7 (a); header of `data/tokens.toml`). `FLOOR_HEADS` is the closed tuple of those 8.0-format names, each recorded in `board.md` with S-0021 (board format page) and S-0033 at tag 8.0.0 (single names), and each written by the created test board (Decision 19), which `test_triad.py` loads on 9.0.9 and 10.0.6. A unit test checks the union. So the writer never creates a post-8.0 name that the inventory lacks (c0007 commitment "every token a typed writer emits needs an inventory row"), and every floor name it creates is loaded by both majors.
   - Rejected: synthesising a full `setup` with plot parameters like the GUI. Nothing in v0.1 needs it, and its obsolete rows would need converting.

4. **Header.** The root starts with `(version FORMAT_VERSIONS[BOARD][target])`, `(generator "fenolite")` and `(generator_version "<target>.0")`, for read and created boards alike.
   - KiCad may apply format-level fixups by generator version, and `"<target>.0"` is what a release of that major writes (S-0039, S-0024). `H-K-GENVER` records what absent, `"9.0"`, `"10.0"` and `"fenolite-x"` do on both majors.
   - Rejected: Fenolite's own version string as `generator_version`. An unknown value could trigger or skip fixups.

5. **Net form is a writer duty over the whole tree.** The form row applies to every node headed `net`.
   - **Target 9.** The root gets `(net 0 "")`, then `(net i "<name>")` for the model's nets sorted by name in code-point order, i = 1 … n. Pads write `(net i "<name>")`; tracks, arcs, vias and zones write `(net i)`; zones also write `(net_name "<name>")`. These are the skeleton's forms. On a read board the table takes the place of the source's table, and its row 0 replaces the source's opaque `(net 0 "")` slot, so the text holds exactly one row 0.
   - **Target 10.** No net table, so the source's opaque row 0 is removed with the rows N ≥ 1. Every reference is `(net "<name>")`, and zones write no `net_name`.
   - **Net 0 means no net, in both directions.** For target 9, a zone or rule area with no net writes `(net 0)` and `(net_name "")`, KiCad 9's form (Context), and other items with no net carry no `net` child. For target 10, nothing with no net carries a `net` child, as 10.0.6 writes (Context). Inside opaque content, `(net 0)`, `(net 0 "")` and `(net "")` are kept as `(net 0)` for target 9 and removed for target 10; they are never an `opaque-net-ref`, and their removal adds no issue.
   - **Opaque content.** Every `net` node inside an opaque fragment is rewritten too. A numbered reference is resolved through the source net table that `read_board` keeps, a named one by its name, and both are re-emitted in the target's form.
   - A `net` node that matches none of `(net N)`, `(net N "name")` and `(net "name")`, or whose number N ≥ 1 is not in the source table, gives `kicad.board.opaque-net-ref` (error, never droppable).
   - A 9 → 9 write renumbers nets by name. Equality is judged on the model, never on net numbers.
   - `check_emittable(node, FileKind.BOARD, t)` must return nothing at t = 9 and t = 10: a unit test checks the created test board (Decision 19), and `test_triad.py` checks the triad before running `kicad-cli`.
   - Rejected: keeping the source numbering for 9 → 9. Created nets need numbers anyway, and two rules would coexist.
   - Rejected: leaving opaque `net` nodes untouched. A 9 source written for 10 would mix forms, which nothing has proved KiCad reads.

6. **Obsolete rows for target 10.** For target 10, every node matched by an inventory row with `until_major = 9` is converted or dropped: the net table is replaced (Decision 5), zone `net_name` is dropped (the name moves into `net`), and zone `filled_areas_thickness` and the plot rows `hpglpennumber`, `hpglpenspeed`, `hpglpendiameter` and `plotinvisibletext` are dropped.
   - The rows come from the inventory, not from a list in code, so a later `until_major` row is handled the same way.
   - Each row id whose nodes are removed adds one `kicad.board.obsolete-dropped` info with the count of nodes. Converted rows count too, because their nodes leave the text (the net table and zone `net_name`); `skeleton.kicad_pcb` gives seven infos.
   - Rejected: keeping them. `check_emittable` warns, and the triad acceptance needs a clean check.

7. **Gating is total and token-based.** After the transforms, `check_emittable(root, FileKind.BOARD, target)` runs once.
   - A `kicad.token.too-new` error inside an opaque slot raises `LossyWriteError` listing every such issue, with `droppable = True` and the hint "re-run with --allow-lossy to drop them".
   - With `allow_lossy=True`, the innermost opaque slot holding each such token is removed, one `kicad.board.dropped-too-new` warning (locator, row id) is added per slot, and the check runs again; it must then return no error.
   - A too-new token in modelled content (for example `Via.via_type = "buried"` for target 9) raises `LossyWriteError` with `droppable = False`, even with `allow_lossy`. Dropping modelled content is a model edit, not a write option.
   - A slot's `min_version` is not the gate. For a head without an inventory row it holds the file version (`kicad-slots`, "Opaque minimum version"), so a 10.0 definition embedded for target 9 would be refused whole, although its only 10-only token is `duplicate_pad_numbers_are_jumpers`. `kicad-version-gating` "Emit check" treats unmatched board paths as floor tokens, because the inventory lists every post-8.0 board and footprint name. Future content never reaches the gate: `require_editable` refuses it first.
   - Rejected: silently stripping fragments. The user would lose data without being told.

8. **Canonical insertion order.** `pcb.CANONICAL_ORDER: Mapping[str, tuple[str, ...]]` gives, for each head the writer can create, its positional fields and then its child fields in the order KiCad 10.0.6 writes them.
   - Item heads: `kicad_pcb`, `footprint`, `pad`, `segment`, `arc`, `via`, `zone`, `gr_line`, `gr_arc`, `gr_circle`, `gr_rect`, `gr_poly` and `gr_text`; rule areas use the `zone` order.
   - Sub-list heads, because a created entity's sub-lists follow their own head's order and a head without an entry raises `ValueError` (`kicad-slots`): `polygon`, `filled_polygon` and `keepout` (modelled by c0009 for zones and rule areas), `pts`, `stroke`, `property`, `effects` and `font`, and every other sub-list a created entity holds. The created test board (Decision 19) writes each of them, so a missing entry fails its unit tests.
   - Each order is observed in 10.0.6-written demo boards (S-0058) and `pcb upgrade` output (S-0020), and recorded as a fact row with its source in `board.md`. None is taken from source code.
   - Created entities are rebuilt with no slots and that order (the `kicad-slots` delta). Read entities keep their slot order, and a field new to a read entity follows the existing "Canonical insertion of new fields" rule.
   - The same order is used for target 9. The created test board (Decision 19), holding one created entity of every head and the 4-copper table, and the triad, holding the 2-copper table, are loaded on 9.0.9 and 10.0.6 by `test_triad.py`, so every created head and both layer tables are loaded by both majors.
   - Rejected: reading the order from KiCad's writer source (clean-room).

9. **KiCad uuids.** An entity with `native_ids["kicad"]` keeps it. A created entity gets `uuid5(FENOLITE_NS, "kicad-out:" + entity.id)`. A part without its own id, such as an outline edge, uses `"kicad-out:<owner id>:<part>"`.
   - The uuid depends only on the Fenolite id. Two writes of one design are byte-identical, and c0011's path-keyed ids give stable uuids.
   - Placed copies get their uuids from embedding (Decision 13), stored in `native_ids`, so the writer reuses them.
   - Rejected: uuid4 at write time (not reproducible).

10. **Projection reconciliation.** Readers project parts of opaque children into model fields (c0008 Decision 5). Before re-emitting a fragment, the writer projects it again with the reader's own function and compares the result with the model:
    - `Component.ref` or `.value` differs: only the value atom of the opaque `(property "Reference" …)` or `(property "Value" …)` fragment is rewritten. Its position, layer, effects and uuid stay as they are.
    - **Spelling-only projections.** c0009 Decision 7 keeps a modelled child as an `Opaque` projected slot when its re-emission differs from the source, for example `12.000000` or a written zero angle. When the model value of such a slot differs from its re-projection, the writer emits the slot's field from the model if the fragment differs from the emitter's output for the *old* value only in spelling: the same heads and atom count, numbers equal as decimals, strings equal as text, or a zero angle written in one and omitted in the other. The new child is then a modelled child. Otherwise, for example an extra atom such as `knockout`, it is `kicad.board.projection-read-only`. An unchanged value always keeps its fragment. This answers c0009's open question "Re-emitting spelling projections": layout edits in c0019 and c0022 move such footprints and tracks.
    - Any other projection differs (`Component.properties` except Reference and Value, `Graphic.width` from `stroke`, `Pad.padstack`, and any later projection): `kicad.board.projection-read-only` (error), naming the field and the locator.
    - Rejected: turning an edited fragment into a modelled slot in general. It needs a full model of property effects (v0.2a). Rejected: refusing every edit of a spelling-only slot, which would block moving a footprint whose `at` KiCad wrote as `(at 10.000000 5 0)`.

11. **Outline lowering.** `Board.outline` is `None` on import (c0009 Decision 6). For a non-empty `Board.outline.points`, on a created board or on a read board whose caller set an outline, the writer emits on `Edge.Cuts` one `gr_line` per edge of the outer ring and of each cutout, closing every ring.
    - Stroke `(stroke (width 0.1) (type solid))`, the skeleton's Edge.Cuts stroke (a Fenolite choice).
    - Uuids by Decision 9, with parts `outline:<ring>:<k>`.
    - `Outline` holds points only (`model/board.py`), so no `gr_arc` is emitted. Arcs wait for the mixed contour model (v0.2).
    - A board with both a non-empty outline and a graphic on a layer of kind `edge` gives `kicad.board.outline-conflict` (error). Edge.Cuts graphics are authoritative (c0009 Decision 6), and writing both would duplicate the contour.
    - Rejected: merging the two contours (which one wins is a user decision).

12. **Writer issues and exceptions.** The closed issue set of the writer and of embedding:

    | code | severity | when |
    |---|---|---|
    | `kicad.board.dropped-too-new` | warning | `allow_lossy` removed an opaque slot holding a token the target cannot read |
    | `kicad.board.obsolete-dropped` | info | target 10: nodes of an `until_major = 9` row removed or converted (one per row id, with the count) |
    | `kicad.board.opaque-net-ref` | error | a `net` node in opaque content matches no form, or names a number absent from the source table |
    | `kicad.board.projection-read-only` | error | a projection other than Reference or Value differs from its fragment |
    | `kicad.board.outline-conflict` | error | a non-empty outline and edge graphics on one board |
    | `kicad.board.flip-unsupported` | error | `place_footprint` on the bottom meets a head outside the mirror table (Decision 14) |

    - Errors raise `LossyWriteError` (`cli_code = "FEN-7001"`, exit 7) with `issues` (every error of the call) and `droppable` (True only when every error is a too-new token in opaque content). Its hint names `--allow-lossy` only when `droppable` is True; otherwise it says the issue codes name what cannot be written.
    - The other exceptions are `FutureFormatError` (`FEN-3002`), `DowngradeRefusedError` (`FEN-7002`) and `LegacyEditRefusedError` (`FEN-7003`).
    - `WriteResult.issues` holds warnings and infos only.
    - `LossyWriteError` and `LegacyEditRefusedError` live in `versions.py`, next to `DowngradeRefusedError`, so c0018's footprint and rules writers raise the same type.
    - Rejected: returning errors inside `WriteResult`. A caller could write a broken file.

13. **Embedding is a backend operation.** Flip, layer naming and uuids are KiCad facts, so `place_footprint` lives in `backends/kicad/embed.py`. `lens` never needs `geometry`, which answers c0005's open question.
    1. `require_editable` on the definition's source format, from its `kicad` bag. A definition read from a future file raises `FutureFormatError`.
    2. The definition is emitted as a footprint node by `_fpmap.emit_footprint(defn, root_chain=("footprint",))`, the footprint emitter that c0018 reuses. It needs the definition-level field map and the `descr`, `tags`, `attr` and `property` emission, which live in `mod.py` today (`FOOTPRINT_FIELDS`, `_attr`). `_fpmap` cannot import `mod`, because `mod` imports `_fpmap`, so task 5.1 moves them to `_fpmap` (`_fpmap.DEF_FIELDS`); `mod.FOOTPRINT_FIELDS` stays as an alias, and c0008's tests guard the move as in c0009 Decision 18.
    3. The library header children `version`, `generator` and `generator_version` are dropped. The root name becomes `defn.lib_id`; `(layer "F.Cu")` or `(layer "B.Cu")`, `(uuid U)` and `(at x y θ)` are set in canonical position; the value atoms of Reference and Value come from `component`; `locked` is written in the form observed in 10.0.6 boards (`board.md`).
    4. Uuids: the footprint and every node that carries a `uuid` child get `uuid5(FENOLITE_NS, f"kicad-place:{key}:{locator}")`, where `locator` is the bare locator of the node in the emitted definition (`/footprint`, `/footprint/pad[3]`, …).
    5. On the bottom side, Decision 14.
    6. The node is mapped by c0009's board-footprint mapping in `pcb.py` (its `FOOTPRINT_FIELDS` slot map, with `_fpmap`'s pad and graphic readers under the root chain `("kicad_pcb", "footprint")`) to a `FootprintInstance` whose pads, slots and ids are exactly those `read_board` gives for the written board. `component_id` and `attributes` (from `kind` and `flags`) are then set.
    - `key` is the caller's stable name for the placement: the component path in c0011. Inserting a part shifts no other uuid.
    - Rejected: seeded uuid4 for placed copies. One inserted part would shift every later uuid, and c0019 matches footprints by uuid.

14. **Bottom side.** The rule below is `INFERRED` (`H-G-BOTTOM-STORE`, `H-G-FLIP`, `H-G-PAD-ANGLE-ABS`) until Decision 18 settles it.
    - **Angle of the footprint.** `rotation` is the model rotation, which is the stored footprint angle on both sides (c0009 Decision 5).
    - **Layers.** `layers.flip_layer(name)` maps `F.<x>` to `B.<x>` and back, for `Cu`, `Adhes`, `Paste`, `SilkS`, `Mask`, `CrtYd` and `Fab`. Every other name is unchanged: inner copper, wildcards such as `*.Cu` and `*.Mask`, `Edge.Cuts` and user layers. It applies to every `layer` and `layers` atom in the node.
    - **Coordinates.** Every node whose head is in `embed.MIRROR_HEADS` (`at`, `start`, `mid`, `end`, `center`, `xy` and the drill `offset`) has its Y negated, which mirrors it about local X. `pts` lists and custom-pad primitives are covered through these heads. The 3D `model` subtree is unchanged.
    - **Child angles.** The angle atom of every child `at` (pads, texts and properties) becomes (−φ) mod 360°, the mirrored library angle.
    - **Texts.** The `justify` of every text on a flipped layer gains or loses `mirror`, as 10.0.6 demo boards show (S-0058; `INFERRED`).
    - **Unsupported geometry.** Heads that carry geometry the table does not cover (`rect_delta`, `dimension` and `image`; a closed list in `board.md`) give one `kicad.board.flip-unsupported` issue per node, and `place_footprint` raises `LossyWriteError` (`droppable = False`) carrying all of them, because it returns an instance and has no issue list. Top placements copy them unchanged.
    - **Both sides.** Child angles are then made absolute through c0009's `pad_angle_to_board` (+θ), the rule of `H-G-PAD-ANGLE-ABS`.
    - Rejected: a viewed-angle argument converted by 180° − r (a left/right flip). It would make the argument differ from `FootprintInstance.rotation`, and the flip axis is a user preference the file does not record (S-0010).

15. **Footprint extent.** `footprint_extent(defn) -> BBox` works in the definition's frame:
    - the box of the modelled graphics on `F.CrtYd` (`defn.graphics_on("F.CrtYd")`, with arcs and circles boxed by c0005's shapes);
    - else the union of the pad boxes: each pad's size rotated by `Pad.rotation` about `Pad.position`, rounded outward with `Transform.apply_bbox`;
    - else `BBox(0, 0, 0, 0)`.

    Courtyard pieces kept opaque (an `arc` inside `pts`) are not counted, and `board.md` says so. Consumers: c0011's staging row and c0022's grid placer.

16. **DRC report reading.** `drc.read_drc_report(text, *, file="") -> DrcReport`.
    - JSON is parsed with numbers kept as text (`parse_float`/`parse_int` hooks), and `NaN` or `Infinity` raises `FormatError` (strict JSON, S-0057). No float is ever created.
    - A missing required key (S-0055, S-0056) raises `FormatError` naming the key. Unknown keys are ignored. `ignored_checks` (10.0.6 only) is tolerated and kept as its `key` strings.
    - Positions are converted to nm from `coordinate_units` (`mm`, `mils`, `in`) with exact rational arithmetic and rounded half to even when not exact. They are report positions, not model geometry. An unknown unit raises `FormatError`.
    - `type` stays KiCad's string, because the schema has no enumeration. Violations keep file order.
    - The neutral types `DrcItem`, `DrcViolation` and `DrcReport` live in `backends/base.py`, so `checks` can receive them by injection later (c0013) without importing a backend (`package-layering`).
    - `KicadCli.drc(board, *, files=None) -> DrcRun` runs `pcb drc --format json --severity-all -o <out> <board>` through c0009's runner, on a copy in a fresh temporary directory. Every helper of c0009 (`load_board_svg`, `export_pos_csv`, `export_ipcd356`, `upgrade_board`) gains the same optional `files` mapping, because the oracles need a `{}` project file, and the flip bench an `fp-lib-table` and a library folder, next to the board; one signature style serves all helpers. `DrcRun.report` is `None` when no report was written.
    - Rejected: validating against `drc.v1.json`. It is a GPL file, never vendored, and not strict JSON at either tag.

17. **DRC verdicts come from the JSON report.** Tests and commands read every DRC verdict from the report. The exit code of `pcb drc` is only a load signal, and `--exit-code-violations` is never passed.
    - A clean report is never evidence that a library table or custom rules loaded. Every library-parity proof carries the missing-table control, and rules proofs carry the canary (c0018).
    - A run whose control does not fire is `inconclusive`, never passed.

18. **Flip and pad-angle proof.** Three independent KiCad outputs:
    - `pcb export pos --format csv --side both`: side and rotation per placement, compared through c0009's pos comparison (both majors);
    - `pcb export ipcd356`: pad positions taken relative to the file's first record, equal to `at + R(θ)·stored` relative to that record's model pad within ±2 export units per axis (±5 080 nm), through c0009's comparison in `tests/kicad/board/_frame.py` (both majors). Each exported value is quantised to 2 540 nm and the export origin is unknown (S-0019, c0009 Decision 17), so no absolute bound is claimed;
    - `pcb drc`: `lib_footprint_mismatch` from the library-parity check (10.0.6; the 9.0.9 outcome is recorded).

    Setup:
    - `Mini_R_0603`, `Mini_LED_THT_3mm` and `Mini_QFP-32_7x7mm_P0.8mm` are placed at 0°, 30°, 90° and 180° on the top and the bottom: 24 placements on one board in `tmp_path`;
    - with a `{}` project file and a project `fp-lib-table` whose row `Mini` points at `${KIPRJMOD}/Mini.pretty` (10.0.6) or at `${KIPRJMOD}/Mini_v9.pretty` in 9.0 table syntax (9.0.9);
    - with every definition read by `read_footprint(path, library="Mini")` on both majors, as c0008's `test_mini_oracle.py` does. Without it a definition from `Mini_v9.pretty` would get the folder stem as library (`mod.py`) and the `lib_id` `Mini_v9:<name>`, a nickname the table lacks;
    - with an empty `KICAD_CONFIG_HOME` (c0009 runner).

    Negative controls, each a board with one bottom QFP at 30°, must each give exactly one `lib_footprint_mismatch`:
    1. unmirrored bottom children;
    2. relative pad angles (θ not added);
    3. wrong flip angle: the footprint written at −θ with every child unchanged.

    The missing-table control is an exact placement with no `fp-lib-table`; on 10.0.6 it must give `lib_footprint_issues`, and if it does not, the run is `inconclusive` and fails. On 9.0.9 every DRC outcome, this control's included, is recorded under `pcb-libdrc-*` and never fails the test (`H-K-LIB-DRC` is open there).
    - The three `H-G-*` rows are settled from these outcomes. The corpus comparison planned in c0005 becomes optional supporting data for c0021.

19. **Triad.** `tests/kicad/board/_triad.py` builds the design through the model API:
    - a created board with `created_layers(2)` and a 50 × 30 mm outline;
    - `R1` (`Mini_R_0603`, top, 0°), `D1` (`Mini_LED_THT_3mm`, bottom, 90°) and `U1` (`Mini_QFP-32_7x7mm_P0.8mm`, top, 30°), placed by `place_footprint` with keys `R1`, `D1` and `U1`;
    - three nets, tracks between pads, and one zone on `B.Cu`;
    - definitions from `Mini.pretty` for target 10 and from `Mini_v9.pretty` for target 9, both read with `library="Mini"`, so every placement is named `Mini:<name>`;
    - a `{}` project file next to the written board.

    The product command that writes triads is c0011's `build`.

    **Created test board.** `tests/_boards.py::created_board(copper: Literal[2, 4] = 2) -> Design` builds a board through the model API with no library definition, so the writer's unit tests (group 3) do not wait for embedding or the `Mini_v9` copies. It holds `created_layers(copper)`, a 50 × 30 mm outline, the nets `GND`, `LED_A` and `VIN`, and one created entity of every `CANONICAL_ORDER` head: a footprint with two pads, a segment, an arc, a through via, a zone with one fill, a rule area, one `gr_line`, `gr_arc`, `gr_circle`, `gr_rect` and `gr_poly` on `F.SilkS`, and a `gr_text`. The triad oracle also loads it (Decision 8).

20. **Probe results per version.**
    - `tests/kicad/_probes.py` defines the closed dict `PROBES` (probe id → function and majors) and `run(probe_id) -> str`, memoised per session. Outcomes are one of `load`, `reject`, `present`, `absent`, `equal`, `different`, `inconclusive` and `timeout`.
    - Oracle tests assert on `run(…)`. `tests/kicad/test_probe_results.py` runs every probe of the running major (cache hits when the oracle tests ran first) and compares the outcomes with `docs/evidence/kicad/probes/<version>.json`.
    - `<version>` is named as for the fuzz results: the first line of `kicad-cli version`, restricted to `[0-9A-Za-z.+-]`.
    - `FENOLITE_PROBES_WRITE=1` writes the file instead. A missing file for the running version fails, naming the variable.
    - Both KiCad jobs run the comparison. The file holds the version, probe ids and outcomes only, so the residue scan passes.
    - Probe ids of this change: `pcb-write-*` (triad and created-test-board loads, `pcb-write-heads-9` and `-10` included, and the 9.0.9 rejection of the target-10 text), `pcb-genver-*` (`H-K-GENVER`), `pcb-libdrc-*` (library-parity bench, the three negative controls and the missing-table control) and `pcb-drc-ignored-checks` (`H-K-DRC-JSON`).
    - c0018's rules oracles record through the same module, under `dru-*` and `fp-write-*`.
    - Rejected: collecting outcomes from other tests by pytest order (fragile).

21. **Flags, errors and capabilities.**
    - `_add_global_options` gains `--kicad-version {9,10}` (an integer, default 10) and `--allow-lossy`. They become `Context.kicad_target: int = 10` and `Context.allow_lossy: bool = False`. An invalid value is a usage error (`FEN-2001`, exit 2). The first command that reads them is c0011's `build`.
    - The registry gains `FEN-7003`, "input from KiCad 8.0 is read-only; writing needs a KiCad 9.0 or newer source", exit 7.
    - `docs/cli-contract.md` lists `FEN-7001` (`LossyWriteError`), `FEN-7003` (`LegacyEditRefusedError`) and both flags. The registered `FEN-7001` hint, "re-run with --allow-lossy to accept the loss", becomes true.
    - `CAPABILITIES` in `backends/kicad/backend.py` (c0009) gains `write_kinds = ("kicad_pcb",)`, `targets = (9, 10)`, `default_target = 10` and `downgrade = "unsupported"`, and `operations` becomes `("detect", "read", "write")`, as c0009 Decision 1 plans. The spec and tests check that `write_kinds` contains `kicad_pcb`, not that it equals it, because c0018 adds `kicad_mod` to the same tuple.
    - `KicadBackend.write(design, *, target=None, allow_lossy=False) -> WriteResult` calls `write_board` (`target=None` means `default_target`). The `Backend` protocol is unchanged: `write` is advertised through `operations`, and a backend that lists it must provide the method (`backend-protocol`). `lower` and `validate` stay unlisted (c0018/c0010, c0013).
    - These values replace c0009's pre-writer ones (`write_kinds == ()`, `operations == ("detect", "read")`). c0009's tests `tests/unit/backends/test_registry.py` and `tests/unit/cli/test_capabilities_backends.py` pin those values, so task 3.3 updates them in the same commit. The capability change lands with `write_board` (task 3.3), not with the flags (task 2.2), so `operations` never lists an operation that is not implemented.

22. **Authored 9.0-format mini footprints.** `tests/data/libs/Mini_v9.pretty/Mini_LED_THT_3mm.kicad_mod` and `Mini_QFP-32_7x7mm_P0.8mm.kicad_mod` are CC0 copies of the 10.0 files. They carry header `20241229` and `generator_version "9.0"`, and drop `duplicate_pad_numbers_are_jumpers`, the only 10-only token they hold. They keep every other child, uuids included.
    - They are declared `origin = "authored"` in `tests/data/MANIFEST.toml`.
    - c0008's `test_mini_oracle.py` loads `Mini_v9.pretty` on 9.0.9 and re-reads it after `fp upgrade --force`. Both new files must pass it before any oracle uses them.

23. **Cross-version and preservation proofs.**
    - **9 → 10 on the demos.** Every non-heavy demo board whose header maps to major 9 is read and written for target 10. It loads on 10.0.6 (`needs_corpus`, `kicad_min_major(10)`). A target-10 write removes whole opaque slots (Decisions 5 and 6: the root `(net 0 "")`, `(net 0)` references, zone `net_name` and `filled_areas_thickness`), so the test first removes those slots from the source's `kicad` bags. The re-read's `opaque_count` equals the source's minus the removed slots. Its canonical JSON equals the source's after the removal, apart from the board's header bag, net numbers and opaque fragments, because net nodes and obsolete rows inside fragments (the plot rows inside `setup`, net references inside teardrop zones) change. Every source fragment holding no `net` node and no `until_major = 9` node keeps its digest. Exact `opaque_count` equality is kept for same-target writes only.
    - **Refusals.** The triad written for 10, read back and written for 9 raises `DowngradeRefusedError`. `old.kicad_pcb` raises `LegacyEditRefusedError`.
    - **Lossy embedding.** A 10.0 `Mini_R_0603` placed for target 9 raises `LossyWriteError` naming `duplicate_pad_numbers_are_jumpers`. With `allow_lossy=True` the write succeeds with a warning and loads on 9.0.9.
    - **`H-K-UUID-KEEP`, Fenolite-written half** (`tests/kicad/board/test_uuid_keep_written.py::test_uuid_keep_written`, the placeholder in the test column of the `H-K-UUID-KEEP` row of `docs/hypotheses.md`). On 10.0.6, the written triad and its `pcb upgrade --force` copy have equal unmasked uuid multisets.
    - **`H-K-GENVER`.** The triad texts with the four `generator_version` variants are loaded on each major.
    - **Unknown child survives.** The authored CC0 fixture `tests/data/kicad/board/dimension.kicad_pcb` (header `20241229`) holds one `dimension` between other items; c0009 keeps it opaque. A segment is moved in the model and the board is written for 9 and for 10. The `dimension` reappears tree-equal, at its index for target 9 and between the same neighbouring items for target 10 (whose root loses the net table rows, so root indices shift). `opaque_count` is equal for target 9 and lowered by the removed slots for target 10, and each text loads on its major.

## Files and public API

| file | public API |
|---|---|
| `src/fenolite/backends/base.py` (c0009; extended) | `@dataclass(frozen=True, slots=True) class WriteResult(text: str, issues: tuple[Issue, ...] = ())`; `class DrcItem(uuid: str, description: str, position: Point)`; `class DrcViolation(type: str, description: str, severity: str, items: tuple[DrcItem, ...] = (), excluded: bool = False, comment: str = "")`; `class DrcReport(source: str, date: str, kicad_version: str, coordinate_units: str, violations: tuple[DrcViolation, ...] = (), unconnected_items: tuple[DrcViolation, ...] = (), schematic_parity: tuple[DrcViolation, ...] = (), ignored_checks: tuple[str, ...] = (), included_severities: tuple[str, ...] = ())` with `of_type(type: str) -> tuple[DrcViolation, ...]` |
| `src/fenolite/backends/kicad/versions.py` (extended) | `class LossyWriteError(FenoliteError)`: `cli_code = "FEN-7001"`, `issues: tuple[Issue, ...]`, `droppable: bool`, `hint: str`; `class LegacyEditRefusedError(FenoliteError)`: `cli_code = "FEN-7003"`, `kind: FileKind`, `version: int`, `hint: str` |
| `src/fenolite/backends/kicad/pcb.py` (c0009; extended) | `write_board(design: Design, *, target: int = DEFAULT_TARGET, allow_lossy: bool = False) -> WriteResult`; `source_info(design: Design) -> FormatInfo \| None`; `CANONICAL_ORDER: Mapping[str, tuple[str, ...]]`; `CREATED_ROOT_HEADS: tuple[str, ...]`; `FLOOR_HEADS: tuple[str, ...]`; `WRITE_ISSUE_CODES: Mapping[str, Severity]` (Decision 12); `kicad_uuid(entity: Entity, part: str = "") -> str`; `WRITE_EVIDENCE: Evidence` (`INFERRED`, `H-K-PCB-WRITE`) |
| `src/fenolite/backends/kicad/layers.py` (c0009; extended) | `created_layers(copper: Literal[2, 4]) -> tuple[Layer, ...]`; `flip_layer(name: str) -> str` |
| `src/fenolite/backends/kicad/_fpmap.py` (c0009; extended) | `emit_footprint(defn: FootprintDef, *, root_chain: tuple[str, ...] = ("footprint",)) -> Node` (reused by c0018); `DEF_FIELDS` and the `attr` emission, moved from `mod.py` |
| `src/fenolite/backends/kicad/mod.py` (c0008) | unchanged public API; `FOOTPRINT_FIELDS` becomes an alias of `_fpmap.DEF_FIELDS` |
| `src/fenolite/backends/kicad/embed.py` (new) | `place_footprint(defn: FootprintDef, *, component: Component, at: Point, rotation: Udeg = 0, side: Side = "top", locked: bool = False, key: str) -> FootprintInstance`; `footprint_extent(defn: FootprintDef) -> BBox`; `placement_uuid(key: str, locator: str) -> str`; `PLACE_PREFIX = "kicad-place"`; `MIRROR_HEADS: frozenset[str]`; `FLIP_UNSUPPORTED: frozenset[str]`; `EVIDENCE: Evidence` (`INFERRED`, the three `H-G-*` rows) |
| `src/fenolite/backends/kicad/drc.py` (new) | `read_drc_report(text: str, *, file: str = "") -> DrcReport`; `REQUIRED_KEYS: tuple[str, ...]`; `LIB_FOOTPRINT_MISMATCH = "lib_footprint_mismatch"`; `LIB_FOOTPRINT_ISSUES = "lib_footprint_issues"`; `EVIDENCE: Evidence` (`INFERRED`, `H-K-DRC-JSON`) |
| `src/fenolite/backends/kicad/cli.py` (c0009; extended) | `load_board_svg`, `export_pos_csv`, `export_ipcd356` and `upgrade_board` gain `*, files: Mapping[str, Path] \| None = None` (extra files copied next to the board: project file, `fp-lib-table`, library folders); `KicadCli.drc(board: Path, *, files: Mapping[str, Path] \| None = None) -> DrcRun`; `@dataclass(frozen=True) class DrcRun(run: CliRun, report: DrcReport \| None)`; `KicadCli.export_stats(board: Path, *, files: Mapping[str, Path] \| None = None) -> dict[str, object]` (10.0 only, `KicadCliVersionError` on 9.0 like `upgrade_board`) |
| `src/fenolite/backends/kicad/__init__.py` | re-exports `write_board`, `place_footprint`, `footprint_extent`, `read_drc_report`, `LossyWriteError`, `LegacyEditRefusedError` |
| `src/fenolite/backends/kicad/backend.py` (c0009; extended) | `CAPABILITIES` with `write_kinds=("kicad_pcb",)`, `targets=(9, 10)`, `default_target=10`, `downgrade="unsupported"`, `operations=("detect", "read", "write")`; `KicadBackend.write(design: Design, *, target: int \| None = None, allow_lossy: bool = False) -> WriteResult` |
| `src/fenolite/cli/api.py` | `Context.kicad_target: int = 10`, `Context.allow_lossy: bool = False` |
| `src/fenolite/cli/main.py` | global options `--kicad-version {9,10}` and `--allow-lossy` |
| `src/fenolite/cli/errors.py` | `ErrorSpec("FEN-7003", ExitCode.LOSSY, …)` |
| `src/fenolite/backends/kicad/PROVENANCE.md` | rows for the writer facts, embedding, the DRC report and the flags |
| `docs/cli-contract.md` | `FEN-7001` and `FEN-7003` rows; the two global flags |
| `docs/formats/kicad/board.md` (c0009; extended) | writer facts: created head set, layer tables, canonical order per head, net forms, obsolete rows, `generator_version`, the KiCad 8 refusal, the mirror table, `locked` form |
| `docs/formats/kicad/drc.md` (new) | DRC report structure in Fenolite's own words, key names only |
| `docs/design-model.md` | section "Placed copies" linking the `design-model` delta |
| `docs/evidence/kicad/probes/9.0.9.json`, `10.0.6.json` (new) | probe outcomes per version |
| `tests/data/libs/Mini_v9.pretty/Mini_LED_THT_3mm.kicad_mod`, `Mini_QFP-32_7x7mm_P0.8mm.kicad_mod` | authored CC0 (Decision 22) |
| `tests/data/kicad/board/dimension.kicad_pcb` | authored CC0 (Decision 23) |
| `tests/data/kicad/drc/report_mm.json`, `report_mils.json` | authored CC0 reports for unit tests (key names from S-0055/S-0056) |
| `tests/_boards.py` (new) | `created_board(copper: Literal[2, 4] = 2) -> Design`, the created test board (Decision 19) |
| `tests/unit/backends/kicad/test_write_errors.py`, `test_pcb_write.py`, `test_pcb_write_nets.py`, `test_pcb_write_lossy.py`, `test_pcb_write_projections.py`, `test_embed.py`, `test_embed_bottom.py`, `test_drc.py`; `tests/unit/backends/test_base_types.py`; `tests/unit/cli/test_kicad_flags.py` | hermetic tests (new) |
| `tests/unit/backends/kicad/test_cli_runner.py` (c0009; extended) | fake-runner scenarios of `KicadCli.drc`, `export_stats` and the `files` argument of the helpers |
| `tests/unit/backends/test_registry.py`, `tests/unit/cli/test_capabilities_backends.py` (c0009; updated) | the KiCad capability values of Decision 21 replace c0009's pre-writer values |
| `tests/unit/cli/test_library_errors.py` (extended) | the three exit-7 scenarios of `cli-contract` "Legacy board edits are refused", through its `run_raising` fixture |
| `tests/consistency/test_cli_consistency.py` (extended) | every command's `--help` lists `--kicad-version` and `--allow-lossy` |
| `tests/kicad/_probes.py`, `tests/kicad/test_probe_results.py`; `tests/unit/test_kicad_probes.py` | probe registry and drift test; `pytester` check of compare, write and missing-file modes |
| `tests/kicad/board/_triad.py`, `test_triad.py`, `test_net_forms.py`, `test_drc_report.py`, `test_flip_oracle.py`, `test_cross_version.py`, `test_uuid_keep_written.py`, `test_genver.py`, `test_unknown_child.py` | `needs_kicad`, major-aware |

Layering: `backends.base` imports `core` and `model` (as in c0009), never a `backends.<x>` module. `backends.kicad.{pcb,embed,drc,layers,_fpmap,cli,versions}` import `core`, `model`, `geometry`, `backends.base` and other `backends.kicad` modules. `cli` imports `backends`. All edges stay within `package-layering`.

## Sources registered by this change

| id | URL | licence of source | used for |
|---|---|---|---|
| S-0055 | https://gitlab.com/kicad/code/kicad/-/raw/10.0.6/resources/schemas/drc.v1.json | GPL-3.0-or-later (key names only, never vendored or read at runtime) | DRC report keys at 10.0.6: required and optional top-level keys, `ignored_checks`, violation and item keys, unit values; not strict JSON |
| S-0056 | https://gitlab.com/kicad/code/kicad/-/raw/9.0.9.1/resources/schemas/drc.v1.json | GPL-3.0-or-later (key names only, never vendored or read at runtime) | DRC report keys at 9.0.9.1; absence of `ignored_checks`; not strict JSON |
| S-0057 | https://www.rfc-editor.org/rfc/rfc8259 | to verify on the page | strict JSON grammar: no trailing comma, no `NaN` or `Infinity` (`H-K-DRC-JSON`) |
| S-0058 | https://gitlab.com/kicad/code/kicad/-/raw/<tag>/demos/<path>; tags 10.0.6 and 9.0.9.1 (the demo board and project files the corpus fetches) | CC-BY-SA-4.0 (notice S-0023, per-folder variants S-0025); read for facts only, never committed | canonical child order and layer tables of 10.0.6-written boards; the rule-severity keys `lib_footprint_mismatch` and `lib_footprint_issues` in 10.0.6 demo projects; back-layer text mirroring; `(net 0)` and `(net_name "")` on unconnected zones and rule areas of `20241229` boards |

Extended "used for" cells, with no new id:
- **S-0022** (10.0 CLI): `pcb drc` with `--format json`, `--severity-all` and `-o`, and `pcb export stats --format json`.
- **S-0037** (9.0 CLI): `pcb drc` with `--format json` and `--severity-all`, and no `pcb export stats`.

Rows of other changes cited here:
- S-0010 (flip option);
- S-0019 (bottom observation), S-0020 (observed `kicad-cli` 10.0.6), S-0021 (board format page, for `FLOOR_HEADS`), S-0023 and S-0025 (demo licence);
- S-0024 (demo file metadata, cited only for facts that `versions.md` already records from it);
- S-0030 (version history, layer renumbering, nets by name), S-0033 (single names, at tag 8.0.0 for `FLOOR_HEADS`), S-0039 (KiCad-written files);
- S-0038 (c0009 extends it to the whole 10.0 board editor page; task 1.1 checks whether it documents the library-parity check).

The `drc.v1.json` rows S-0055 and S-0056 come from the KiCad tree and are read for key names only, like S-0033. If a URL above is already registered when this change is implemented, the existing id is cited and the row is not duplicated. S-0059 stays unused. Facts read from the contents of demo files cite S-0058, not S-0024, whose URL and licence cells cover API metadata only (file lists, sizes and SHA-256).

## Hypotheses registered by this change

| id | statement | settling test | criterion |
|---|---|---|---|
| H-K-PCB-WRITE | A board written by `write_board` for target 9 loads on 9.0.9, one written for target 10 loads on 10.0.6, and `kicad-cli` counts the model's footprints and pads (S-0022, S-0037) | `tests/kicad/board/test_triad.py` | both triads load; `pcb export pos --side both` lists 3 footprints with the model's positions, rotations and sides; on 10.0.6 `pcb export stats` footprint and pad counts equal the model; 9.0.9 rejects the target-10 text with exit 3 |
| H-K-GENVER | Board headers with `generator_version` absent, `"9.0"`, `"10.0"` or `"fenolite-x"` load on both majors (S-0030, S-0039) | `tests/kicad/board/test_genver.py::test_generator_version_variants` | each variant of the target-9 text loads on 9.0.9; each variant of both texts loads on 10.0.6; outcomes recorded per probe |
| H-K-DRC-JSON | `pcb drc --format json` writes strict JSON holding every top-level key the schema requires, although the schema file is not strict JSON (S-0055, S-0056, S-0057) | `tests/kicad/board/test_drc_report.py::test_drc_json_strict` | on 9.0.9 and 10.0.6, the report parses with `NaN`/`Infinity` rejected, holds the 7 required keys, and `read_drc_report` accepts it; whether `ignored_checks` is present is recorded per major |

Rows registered by other changes and settled or re-pointed here:

| id | settling test (new) | criterion |
|---|---|---|
| H-G-BOTTOM-STORE | `tests/kicad/board/test_flip_oracle.py::test_bottom_store` | on 10.0.6, no `lib_footprint_mismatch` for the 12 bottom placements and exactly one for the unmirrored control; on both majors every IPC-D-356 pad, relative to the first record, within ±2 export units per axis of `at + R(θ)·stored` (c0009's `_frame.py`) |
| H-G-FLIP | `test_flip_oracle.py::test_flip_angle` | on both majors, pos side and rotation equal the model for all 24 placements; on 10.0.6, exactly one `lib_footprint_mismatch` for the wrong-flip-angle control |
| H-G-PAD-ANGLE-ABS | `test_flip_oracle.py::test_pad_angles` | on 10.0.6, no mismatch with absolute pad angles and exactly one for the relative-angle control; the IPC-D-356 `R` field is recorded |
| H-K-LIB-DRC (c0014) | `test_flip_oracle.py::test_lib_drc` | on 10.0.6 with a project `fp-lib-table` and an empty `KICAD_CONFIG_HOME`: `lib_footprint_mismatch` for an altered placement, none for an exact one, `lib_footprint_issues` without the table; the 9.0.9 outcome is recorded; a run whose missing-table control does not fire is `inconclusive` |
| H-K-UUID-KEEP (c0009) | `tests/kicad/board/test_uuid_keep_written.py::test_uuid_keep_written` (the placeholder already in the register row) | on 10.0.6, the written triad and its `pcb upgrade --force` copy have equal unmasked uuid multisets |

Target levels for the three `H-G-*` rows: `KICAD-VERIFIED (10.0.x)` from DRC library parity and its negative controls, with pos and IPC-D-356 as consistency checks. The `(9.0.x)` scope is added only if `H-K-LIB-DRC` holds on 9.0.9. Pos and IPC-D-356 alone cannot settle these rows: pos compares the stored angle with itself (`H-K-PCB-POS`), IPC-D-356 compares pads with `at + R(θ)·stored` for the values Fenolite wrote (`H-G-BOTTOM-PLACE`), and none of the three negative controls changes either comparison. Without the 9.0.9 parity check, the 9.0.9 pos and IPC-D-356 results are recorded as supporting data in the result column. A refuted row keeps its id, takes the level of the refuting run, and gets a successor with suffix `-2`. If the pad-angle convention is refuted, only the shared pair `pad_angle_from_board`/`pad_angle_to_board` and its tests change.

## Evidence level per behaviour (before merge)

| behaviour | level required | proof |
|---|---|---|
| Triad written for 9 and for 10 loads and counts | KICAD-VERIFIED on 10.0.6 (local and `kicad-10`) and 9.0.9 (`kicad-9`) (`H-K-PCB-WRITE`) | `tests/kicad/board/test_triad.py` |
| Writing arbitrary designs | INFERRED (`H-K-PCB-WRITE`); `WRITE_EVIDENCE` | unit tests, triad as supporting data |
| Net form per target, obsolete rows | KICAD-VERIFIED on 9.0.9 and 10.0.6 for the triad and `two_layer.kicad_pcb` (`H-K-TOK-NETNAME`, `H-K-TOK-OBSOLETE`) | `test_net_forms.py`, `test_pcb_write_nets.py` |
| Net 0 on unconnected zones and rule areas | INFERRED from corpus and `pcb upgrade` observations (S-0058, S-0020); load of the 10.0 form KICAD-VERIFIED (10.0.x) through the demo boards that hold it | `test_pcb_write_nets.py`, `test_cross_version.py` |
| Created head set and layer tables | KICAD-VERIFIED (9.0.x, 10.0.x) for load: the triad (2 copper) and the created test board (4 copper) | `test_triad.py`, `test_pcb_write.py` |
| Canonical order and `FLOOR_HEADS` | KICAD-VERIFIED (9.0.x, 10.0.x) for load of one created entity of every head (created test board); byte identity not claimed | `test_triad.py` |
| `generator_version` | KICAD-VERIFIED for the emitted value; other values as `H-K-GENVER` records | `test_genver.py` |
| Bottom placement, flip, pad angles | KICAD-VERIFIED (10.0.x) from DRC library parity and its controls, with pos and IPC-D-356 as consistency checks; the (9.0.x) scope only if `H-K-LIB-DRC` holds on 9.0.9, otherwise 9.0.9 pos and IPC-D-356 results are supporting data; refuted rows get successors | `test_flip_oracle.py` |
| Library parity check as an oracle | KICAD-VERIFIED (10.0.x) if `H-K-LIB-DRC` holds; 9.0.9 recorded | `test_flip_oracle.py::test_lib_drc` |
| DRC report reading | KICAD-VERIFIED on both majors (`H-K-DRC-JSON`) | `test_drc_report.py`, `test_drc.py` |
| 9 → 10 conversion of demo boards | KICAD-VERIFIED (10.0.x) for load; model equality mechanical | `test_cross_version.py` |
| Unknown child survives a write | KICAD-VERIFIED on 9.0.9 and 10.0.6 for `dimension.kicad_pcb` | `test_unknown_child.py` |
| uuids kept by KiCad on written boards | KICAD-VERIFIED (10.0.x) (`H-K-UUID-KEEP`, Fenolite-written half) | `test_uuid_keep_written.py::test_uuid_keep_written` |
| Refusals, lossy gate, flags, error codes, capability fields, uuid and id derivation, projections (spelling-only included), outline lowering, footprint extent | mechanical (unit tests) | unit tests |

`pcb.WRITE_EVIDENCE` stays `INFERRED` (`H-K-PCB-WRITE`) after this change: only the triad's shape is verified, so c0011's `build` reports `INFERRED`. `embed.EVIDENCE` names the three `H-G-*` rows and takes their settled level.

## Budget (about 1.5 weeks; the plan line was day 15)

| work | days |
|---|---|
| registers, writer facts in `board.md`, `drc.md` | 0.75 |
| flags, errors, capabilities | 0.5 |
| writer core: header, created head set, layer tables, order, uuids, outline, target policy, net form, obsolete rows, gate | 1.5 |
| projection reconciliation | 0.25 |
| `Mini_v9` copies | 0.5 |
| `embed.py` | 1.0 |
| `drc.py` and base types | 0.5 |
| triad oracle | 0.5 |
| flip, `H-K-LIB-DRC` and probe results | 1.0 |
| cross-version, `H-K-UUID-KEEP`, `H-K-GENVER`, unknown child | 0.75 |
| closing | 0.5 |
| **total** | **7.75** |

The plan gives one day to the target writer. This change is estimated at 7.75 working days, stated here and in the proposal. First cuts: the `H-K-GENVER` variants beyond the emitted value, then the corpus half of the cross-version RT1 (to c0020). Not optional: the writer, the gate, the net form, embedding, the triad, and the flip oracle on 10.0.6.

## Risks / Trade-offs

- [`kicad-cli` 9.0.9 does not run the library-parity check] → The three `H-G-*` rows stay `KICAD-VERIFIED (10.0.x)` only. The 9.0.9 pos and IPC-D-356 results are supporting data: they check the frame of what Fenolite wrote, not the flip convention. Both majors read the same `20241229` text, so the 10.0.6 parity check on target-9 placements is the strongest evidence available.
- [A negative control does not fire, for example because KiCad compares pads by shape] → The control is recorded `inconclusive`, never passed. Each control changes a pad angle by at least 30° or moves pad 1, so a rectangular pad differs in geometry.
- [The canonical order is wrong for a rare head] → It only affects created fields. The triad and cross-version tests load the output on both majors. Byte identity is not required.
- [Hand-authored `Mini_v9` copies differ from what 9.0 writes] → c0008's oracle requires `fp upgrade --force` on 9.0.9 to re-read them equal before any oracle uses them.
- [Renumbering nets on a 9 → 9 write changes the text of an unchanged board] → Equality is judged on the model. c0019 matches footprints by uuid, never by net number.
- [Text angles or mirroring on the bottom differ from KiCad's] → Labelled `INFERRED` in `board.md`. The parity check and the 9.0.9 load cover what they compare; anything else stays a recorded observation.
- [The mirror table misses a geometry head] → Heads listed in `FLIP_UNSUPPORTED` are refused on the bottom side, and the list grows when a fixture shows a new head.
- [Overrun] → Cut first: the `H-K-GENVER` variants beyond the emitted one, then the corpus half of the cross-version RT1 (to c0020). Not optional: writer, gate, net form, embedding, triad, and the flip oracle on 10.0.6.

## Migration Plan

- Additive: new modules `embed.py` and `drc.py`, new functions in existing modules, two exception classes, one registered code, two global flags with defaults, and new fixtures. The model and the schemas are unchanged. To roll back, remove them and the `FEN-7003` row.

## Corrections to the brief

- **IPC-D-356 bound.** The brief asks for absolute pad positions within ±1270 nm. The repository records that the export origin is unknown and that each value is quantised to 2 540 nm (S-0019; `tests/kicad/test_geometry_frame.py`; c0009 Decision 17, which rejects an assumed origin), and c0009 asks this change to use its relative bound unless it establishes the origin first. Nothing here establishes the origin, so Decision 18 compares positions relative to the first record within ±2 export units per axis.

- **Scope of the flip rows on 9.0.** The brief grants `KICAD-VERIFIED (9.0.x)` to `H-G-BOTTOM-STORE`, `H-G-FLIP` and `H-G-PAD-ANGLE-ABS` from pos and IPC-D-356. Both outputs compare Fenolite's written values with themselves (`H-K-PCB-POS`, `H-G-BOTTOM-PLACE`), and none of the negative controls changes them, so they cannot tell a correct flip convention from a wrong one. The `(9.0.x)` scope therefore needs `H-K-LIB-DRC` to hold on 9.0.9; otherwise the 9.0.9 results are supporting data.

## Open Questions

- **From the batch plan.** Do you accept the re-baselined budget (about 31 working days for the batch and about 102 to v0.1) and the cut order (c0023, then c0021, then c0020's measurement-only items)? The default for this change is 7.75 days with the cuts named in "Budget".
- **Source ids.** The brief pinned the two `drc.v1.json` rows as S-0060 and S-0061. This change uses its own block, S-0055 and S-0056, so it cannot collide with the ids c0018 takes from S-0060 on. The default is S-0055 … S-0058; S-0059 stays unused.
- **Outline arcs.** The brief lowers outlines to `gr_line`/`gr_arc`. `Outline` holds points only (`src/fenolite/model/board.py`), so only `gr_line` is emitted. The default is to add `gr_arc` with the mixed contour model (v0.2).
- **Registration of `H-K-UUID-KEEP`.** c0009's implementation already added the row to `docs/hypotheses.md` (uncommitted in the working tree on 2026-10-01). Its test column names `tests/kicad/board/test_uuid_keep_written.py::test_uuid_keep_written` for this change's half, as c0009's design table now does; a reviewer saw an earlier c0009 draft naming `test_cross_version.py::test_uuid_keep_written`. This change cites the register row. The default: task 1.1 checks the row and re-points its test column to that node id if it names any other path; it registers the row with c0009's columns only if the row is missing.
- **Floor names and c0007 Decision 7.** c0007 asks typed writers to add an inventory row for every token they emit, while its inventory scope is names introduced after 8.0. Rows with `since_major = 8` would gate nothing and would need token-fuzz results to compute their levels. The default is `pcb.FLOOR_HEADS`, recorded in `board.md` with sources and loaded by both majors (Decision 3); if review prefers rows, task 1.3 adds them instead and the unit test is unchanged.
- **c0014's register guard and active changes.** c0014's scan covers active changes, but this change's new ids (`H-K-PCB-WRITE`, `H-K-GENVER`, `H-K-DRC-JSON`) are registered only by task 1.1. The default: the guard accepts ids listed in an active change's "Hypotheses registered by this change" table as pending, or task 1.1 lands in the same pull request as the proposal.
- **c0009's pinned pre-writer capabilities.** c0009's `backend-protocol` "Capability reports" ("In this change the KiCad report MUST have … `write_kinds == ()` … `operations == ("detect", "read")`", scenarios "KiCad capability report" and "Unavailable operations are visible") and `cli-contract` "Backends in capabilities" (scenario "KiCad backend listed": `write_kinds` is `[]`) contradict this change's "Write capability fields" once both are archived. Those requirements are not living yet, so this change cannot MODIFY them. The default: c0009 scopes those values to "until a writer change lands" before it archives; if it archives unchanged, this change adds MODIFIED deltas of both requirements before its own archive. c0009's tests are updated by task 3.3 either way.
- **MODIFIED "Identifier derivation".** Resolved: the draft left this to c0011, which is outside this batch, so the living spec would have kept two conflicting MUSTs ("uuid4 from an injectable seeded generator" for created objects, "never from the seeded generator" for placed copies). This change carries the MODIFIED delta: the full text and its three scenarios are kept, and placed copies are named as a third case with one new scenario.
- **"Verbatim" in `design-model` "Slots for lossless round-trip".** Resolved: the draft claimed "verbatim" still held for same-target writes, which is false, because a 9 → 9 write renumbers nets by name inside opaque fragments too (Decision 5). This change carries a MODIFIED delta of that requirement: the original text and scenario are kept, and a sentence restricts write-time changes to opaque children to those a backend requirement names, which `kicad-slots` "Slot source for model entities" lists for KiCad.
- **Development headers before the 9.0 layer renumbering.** A nightly board with a header between `20240108` and the version that renumbered layers would carry 8.0 numbers while `major_for` maps it to 9. Task 1.3 records that version from S-0030 in `board.md`. The default keeps the refusal keyed on major 8, as agreed; if a corpus board falls in that range, the refusal is extended to it.
- **c0009's "Re-emitting spelling projections".** Answered in Decision 10: spelling-only projected slots are re-emitted from the model when the value changes; anything more than spelling stays read-only. The default stays unless c0009's census finds a cause this rule misclassifies.
- **Bottom rotation in pos.** If `pcb export pos` reports a bottom rotation other than the stored angle, c0009's pos comparison already applies the observed rule, and `H-G-FLIP` cites it. The default is that the model rotation stays the stored angle.
- **Units of the DRC run.** `KicadCli.drc` does not pass `--units`; positions are converted from `coordinate_units`. The default stays until a report shows rounding that matters.
