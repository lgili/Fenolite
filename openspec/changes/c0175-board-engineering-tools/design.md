## Context

- **Request.** On 2026-10-24 the maintainer asked for a specification of the tools that the maintainer's board work had to write around Fenolite and that any user of the library would need. The survey grouped about sixty scripts into families. This design keeps the generic ones. It describes each tool by its behaviour, never by the code it came from. Each algorithm below is either a textbook method or a procedure written out here. No code, value, geometry or name of any organisation's design enters Fenolite.
- **What exists** on `release-0.5.0` at `a979b412`:
  - **Analyses** (`analysis/`): current capacity, power paths with their narrowest section, clearance on a layer, creepage on the surface with grooves, insulation between layers, net length, and per-net views (`net`, `region`, `neighbors`, `pads`).
  - **Copper check** (`checks/copper.py`) with rule areas, the edge and holes.
  - **Placement:** `place --move`, grid placement, constrained placement, `sync --to-source`.
  - **Routing:** the plugin protocol with `direct`, `freerouting` and KiCadRoutingTools, tiers, a time budget, plane fan-out (`backends/kicad/fanout.py`), and scripted copper (`track`, `via`, `stitch`, `zone`, `rule_area`).
  - **Assembly:** test-point authoring and the test-point report, fiducials, tooling holes, `fields.place_outside`.
  - **Files:** the mutation protocol with plans, receipts and `restore`; `manifest`.
  - **KiCad oracle:** DRC and ERC, with stored exclusions read and judged.
  - **Conversion:** Altium to KiCad with a loss report.
- **What failed in use.** Each package below starts from one of these failures, written without any design's details:
  - a block copied by part positions came out mirrored;
  - an autorouter closed one connection in six, because of two defects in its input file;
  - a ground tie test removed more copper than the tie, and so tested another board;
  - many routes failed before anyone counted the ways across a barrier;
  - designators overlapped after small moves;
  - pads read from Altium had no mask or paste openings;
  - a "copy what changed" overwrote ten files that the owner had just saved;
  - a model that ignored pour cut-outs showed a pin connected that was open on the board.

## Goals / Non-Goals

**Goals**
- Each package gives an agent a command or a DSL call that replaces a script it would otherwise write. The reply is JSON, with issues, evidence and a reviewed plan for every write.
- Every write passes the copper check before it is planned, and passes `kicad-cli` DRC on the written board before the package is `KICAD-VERIFIED`.
- Every analysis is read-only, runs no tool, and judges only against the user's requirements.

**Non-Goals**
- See the proposal. In addition:
  - no optimiser that places a whole board;
  - no autorouter of Fenolite's own beyond short critical connections;
  - no simulation of electromagnetic fields (the coupling screen ranks pairs; it computes no voltage).

## Decisions

### 1. Router input fidelity (`specctra-dsn`, `routing`)

- **Width.** A `track_width` rule whose selector is `all` and that has an `opt` sets the width only of classes that hold no width of their own. A class width inside `[min, max]` is kept; one outside is clamped into it. One `specctra.rule-widened` (info) names the rule and the classes it did not change.
  - **Why.** A board-wide width rule with a large preferred value is a limit, not a wish. Written into every class, it routed every net at that width, and little fitted.
  - A width rule that names classes keeps today's behaviour.
- **One-sided clearance.** A `clearance` rule with one side a class (or an `or` of classes) and the other side `all` or absent is written as one `class_class` pair per other written class. It no longer raises the class's own clearance.
  - The class's clearance against itself comes only from rules that name that class on both sides, combined by the rule order of the board: a later rule wins, as KiCad resolves it.
  - A multi-class rule that includes a class paired with itself writes that self-pair only when no later rule gives the same pair.
  - **Why.** Raising the class's own clearance closed dense regions of that class that KiCad's DRC accepts.
- **Tiers.** `--order` takes a comma-separated list of globs per tier, and stays repeatable: `--order "GATE_*,SENSE_*" --order "*"`. One glob per tier stays valid.
- **Evidence.** `INFERRED` for the file. A bench measures the routed share and the DRC findings before and after the change on an authored dense board; task 1.4 registers the two hypotheses (width of an `all` rule, one-sided clearance) in `docs/hypotheses.md` with their ids when it measures them.

### 2. Ground ties (`board-analyses`, `analysis/ties.py`)

- **Input.** `--kinds ties` with `--tie REF` (a net-tie part) or `--tie-item ID` (a copper item: track, arc, via, or a zone of a net), repeatable. With `--domains A=GLOB,B=GLOB`, two named groups of pads.
- **Method.**
  1. Take the copper graph of the net (pads, tracks, arcs, vias, filled zones; items join when their copper overlaps).
  2. Remove exactly the tie items: their own ids, never items found by area.
  3. Compute the connected groups.
- **Result.** One row per tie: the groups, with each group's pads (`REF-PIN`), and `split` (true when the removal leaves two or more groups).
  - With `--domains`, a pad of domain A found in the group of domain B is a finding: `analysis.tie-extra` (error), naming the pad and the path that joins it.
  - A tie whose removal splits nothing means a second tie exists: `analysis.tie-parallel` (error), with the shortest other path between the two sides, given as items.
- **Sense nets.** `--kinds ties --sense NET_A,NET_B` checks that each sense net touches its element only at that element's pads, and shares no copper item with another net through a net tie. Copper of a sense net that overlaps the copper of a power net on the same layer is `analysis.sense-shared` (error).
- **Isolation islands** (schematic level, no copper). `--kinds domains --barrier REF,...` removes the barrier parts (isolators, transformers, earth parts) from the net graph. It reports the islands of nets that remain, so that a domain plan can be compared with the circuit.
- **Evidence.** `INFERRED`, on authored benches: a single tie; a parallel tie through a via; a tie test that removes by area, shown wrong; a sense net that leaves from a pour.

### 3. Barrier crossings (`board-analyses`, `analysis/crossings.py`)

- **Input.** `--kinds crossings --cut X1,Y1,X2,Y2` (a segment with units, repeatable), and optionally `--width LENGTH` (the track width to fit; default the narrowest class width).
- **Method.** On each copper layer, intersect the cut with the obstacles:
  - each item's copper, grown by the clearance in force against a track of the given width;
  - the board edge and the cut-outs;
  - rule areas that forbid tracks;
  - drills.

  The free intervals along the cut are the ways. A way fits `floor((length + clearance) / (width + clearance))` tracks. A via is not allowed where a rule area forbids vias or the via would break a clearance.
- **Demand.** The open connections of the board whose straight line crosses the cut, and the routed connections whose copper crosses it, listed per net.
- **Result.** Per layer: the ways and the number of tracks each fits. Then the demand, and `analysis.crossings-short` (warning) when the demand exceeds the supply. `--render FILE.svg` draws the cut, the free intervals and the obstacles, as a plan.
- **Evidence.** `INFERRED`, on benches with hand-counted ways.

### 4. Layout reuse (`layout-reuse`, `src/fenolite/reuse/`)

The fit over pads with unique numbers, the copy of the placement and of the tracks, arcs and vias, and the
command moved on 2026-10-28 to change c0210 (`openspec/changes/c0210-layout-reuse/`), whose design records
how they are proved; the command became the strategy `place --strategy reuse` (`--from`), and DRC runs there
with `--drc` only. Pads matched by net partition, zones and group moves moved on 2026-10-28 to change
c0227 (`openspec/changes/c0227-reuse-moves/`), whose design records how they are proved.

- **Command.** `fenolite reuse TARGET --from REFERENCE --parts REF[,REF...] [--anchor REF] [--map REF=REF ...] [--copper] --dry-run|--confirm`. TARGET is a KiCad board. REFERENCE is any board that a backend reads.
- **Method.**
  1. Fit one rigid transform on the anchor's pads: four quarter turns, a side, and a translation. Fit by least squares on pads matched by number, within `--tolerance` (default 0.05 mm).
  2. Place each part by fitting its own pads onto its reference part's pads. The side is decided by the fit, never assumed, so a mirrored reference is found, not copied.
  3. With `--copper`, copy the reference copper of the block's nets:
     - map each reference net to the target net of the matched pads;
     - drop branches that end on no matched pad (free ends first, then vias joined on one layer only);
     - keep an island only when it joins two or more matched pads of one target net;
     - rebuild a zone whose outline the reader did not give, from its fill.
  4. Run the copper check on the result. A copied item that adds a finding is left out and reported.
- **Result.** The transform, per part the matched pads and the residual, the copied items, the dropped items with reasons, and `reuse.mirror-suspected` (warning) when the best fit of a part needs the other side from its reference.
- **Group rotation.** `fenolite place --turn REF[,REF...] --about X,Y --angle 90` turns parts with their scripted and locked copper as one rigid group. Each part's new angle comes from its pads, which is correct on both sides.
- **Evidence.** `KICAD-VERIFIED` (DRC on the written board), on an authored reference and target pair that holds one mirrored case.

### 5. Copper tidy (`copper-tidy`, `src/fenolite/tidy/`, `routing/octilinear.py`)

Prune, the right-angle chamfer and the command with `--prune`, `--chamfer`, `--leg` and `--drc` moved on
2026-10-28 to change c0208 (`openspec/changes/c0208-copper-tidy/`), whose design records how they are proved;
DRC runs there with `--drc` only. Straighten, T-joint and zone chamfers and the report moved on the same day to
change c0214 (`openspec/changes/c0214-tidy-straighten/`), whose design narrows the search to a list of
shapes of at most three segments. The router moved on 2026-10-28 to change c0228
(`openspec/changes/c0228-octilinear-router/`), whose design records how it is checked and proved.

- **Command.** `fenolite tidy BOARD [--nets GLOB] [--keep-locked] [--prune] [--straighten] [--chamfer] --dry-run|--confirm`. `fenolite tidy BOARD --report` writes nothing and reports the style.
- **Prune.** Remove, again and again until nothing changes, the unlocked copper with a free end, and the vias joined on fewer than two layers. Locked and scripted copper are never touched.
- **Straighten.**
  1. Split each net's routed copper into single-layer runs between fixed points: pads, vias, joins, locked items.
  2. Search each run for a shorter shape on the 0/45/90° lattice, with costs per turn: 45° cheaper than 90°, acute angles forbidden, turns inside the run's own pads free.
  3. Accept a shape only when it keeps the clearance in force to every other item, the edge, slots and drills, and has fewer weighted turns.
  4. Process the runs in order, each against the copper of the earlier ones.
  5. Never touch a run whose net is in a pair, has a length rule, or is locked.
- **Chamfer.** Replace a 90° joint of two tracks of one net, layer and width by a 45° segment, shortened on short legs. Turn a T-join into a 45° entry. Validate each chamfer with the copper check; a chamfer that adds a finding is undone.
- **Report.** Per net class and layer:
  - the histogram of joint angles (45, 90, acute);
  - jogs (runs shorter than three widths between two turns);
  - widths;
  - via counts;
  - acute joints as `tidy.acute` (warning) with places.

  `--compare REFERENCE` gives the same table for a reference board, so an agent can match a house style by measurement.
- **Octilinear router** (routing plugin `octilinear`). It routes short connections between named pads:
  - it tries a few octilinear shapes per leg (straight; 45° then straight; straight then 45°; L), in clearance;
  - it rips up and retries for a few rounds;
  - it accepts the result only when the copper check finds nothing new.

  It is for gate loops, sense pairs and the like, not for whole boards. The capabilities reply lists it with the feature `short`.
- **Evidence.**
  - `KICAD-VERIFIED` for written boards (DRC finds nothing new).
  - The style report is `INFERRED`, on benches with known angle counts.

### 6. Generated copper and keep-outs (`design-dsl`, `src/fenolite/dsl/generate.py`)

Moved on 2026-10-28 to change c0224 (`openspec/changes/c0224-generated-copper/`), whose design records
how the calls are resolved by the build and proved; the text below is the plan it started from.

Calls of a design script. Each one records ordinary zones and rule areas, so builds, checks and conversions need nothing new.
- **`design.band(net, spine, *, width, max_width=None, layers, clearance=None)`.** A power band along a spine path.
  - Each side widens on its own up to `max_width`, in steps that keep `clearance` from other nets' copper.
  - Steps are 45° chamfers, and outer corners are bevelled.
  - A short jog widens by at most one step, so edges stay straight.
  - The band is refused (`DslError`) when the spine leaves the board.
- **`design.keepout_ring(hole_or_ref, *, setback, layers, forbid)`.** A polygon around a hole whose edges stay outside the true circle (each vertex pushed out by `1/cos(π/N)`).
- **`design.barrier(netclass, *, setback, layers=("F.Cu","B.Cu"), forbid=("tracks","vias","zones"))`.** A band around all copper of a class on any layer, projected onto every listed layer. It is refused when it comes out in several pieces or with holes, unless `pieces=True`.
- **`design.body_keepout(ref, *, setback, layers)`.** The plan view of a part's body volume (`component-body-volumes`), grown by `setback`.
- **`design.fanout_zone(zone_net, *, refs=None, via=...)`.** It joins the SMD pads of a net on one face to its zone on the other face, with vias placed by the rules of plane fan-out. A via never sits on any pad's copper or on another drill.
- **`design.stitch_pieces(net, *, layers, min_vias=2, pitch=...)`.** It joins the pieces of a net's pour with at least `min_vias` vias in each overlap of two pieces.
- **Evidence.** `KICAD-VERIFIED` (fill and DRC on both majors), on authored scripts.

### 7. Practice checks (`board-analyses`, `analysis/practice.py`, `analysis/coupling.py`)

New kinds of `analyze`. Each reports facts, and is a finding only against the user's requirements file (new optional tables, all without defaults).
- **`decoupling`.** For each supply pin of a part whose pin type is power input, the nearest capacitor on the same net and its return pad. The distance along copper and the area of the loop (pin to capacitor to return) are reported. Rows `[[decoupling]]` give `max_distance_nm` per part glob.
- **`connectivity`.** It computes the copper connectivity from the filled zones with every cut-out, keep-out and rule area applied. It reports each net that falls into more than one group, and each pad that is no longer joined. For an Altium board whose pours are older than their outlines (stale), it simulates the pour:
  - start from the outline;
  - remove other nets' copper grown by the rule in force;
  - remove earlier pours, cut-outs and keep-outs;
  - drop the dead copper;
  - say so in the row.
- **`bodies`.** The copper of each selected net class inside the plan view of selected part bodies, per layer. Rows `[[body_copper]]` name the class, the parts (glob) and the forbidden layers. This is the rule "no high voltage under a can".
- **`relief`.** For each pad joined to a zone by thermal relief, the copper that crosses a ring at the pad's edge. Its width is reported against the current of the pad's net (from `[[current]]`).
- **`dead`.** Zone islands joined to no pad, and copper further than a given distance from any pad of its net.
- **`coupling`.** For pairs of aggressor and victim nets (`--aggressor GLOB`, `--victim GLOB`):
  - the parallel length on the same layer, and the narrowest gap;
  - the score `Σ length / (1 + (s/h)²)`, with `h` the height to the nearest plane of the stack-up;
  - the broadside overlap on the other layer;
  - for each victim, the share of its length that has its return plane directly under it.

  The score ranks pairs. It is not a voltage, and the page says so.
- **Evidence.** `INFERRED`, on authored benches. `connectivity` is bracketed by KiCad's unconnected items on KiCad boards.

### 8. Assembly marks (`silkscreen-layout`, `assembly-test-features`)

The text extents and `fenolite silk --designators` moved on 2026-10-28 to change c0212
(`openspec/changes/c0212-assembly-marks/`), whose design records how they are measured and proved; it writes
no placement record, and replaces the sweeps by a repair. `--clip` moved on 2026-10-28 to change c0226
(`openspec/changes/c0226-silk-clip/`), whose design records the openings, the margin and how the library
stays in step. `testpoints --place` moved on 2026-10-28 to change c0229
(`openspec/changes/c0229-testpoint-place/`), whose design records the sites, the obstacles and why a
rebuild keeps the probes without `sync`.

- **Text extents.** `src/fenolite/silk/extents.py` measures the ink box of a stroke text. It renders the text once with `kicad-cli pcb export svg` on a scratch board, caches the result per font, size and string, and adds half the stroke on each side. With no `kicad-cli`, it uses a stated estimate, labelled `INFERRED`.
- **`fenolite silk BOARD --designators [--keep] --dry-run|--confirm`.**
  - **Obstacles per silk side:** pads with their mask margin, drills, other silk, part bodies, the edge and slots.
  - **Candidates:** around each part, at two angles and two sizes.
  - **Cost:** distance to the own part, nearness to a foreign part, angle against the part's axis, and size.
  - **Search:** a greedy start, then best-response sweeps.
  - **Alignment:** rows and columns of similar parts are aligned.
  - `--keep` moves only blocked designators.
  - The result is recorded in a placement file beside the board, so a rebuild keeps it.
- **`fenolite silk BOARD --clip`** cuts silkscreen strokes at every mask opening, with a margin. The footprint's own graphics are cut too, so the change must be carried to the library (package 10, "library from a board").
- **`fenolite testpoints BOARD --place --side bottom --pitch 2.54mm --reach 5mm`.** For each net without access on the given side, it searches the nearest clear site on a grid, within reach of the net's copper:
  - a site keeps the clearance in force, misses bodies and drills, and stays outside rule areas that forbid parts;
  - the probe is joined with a short track or by sitting on the net's copper;
  - probes spread to the fixture grid so that their joins do not cross.

  The coverage after placement is reported (`Report.coverage`).
- **Evidence.** `KICAD-VERIFIED` for the writes (DRC silk and copper rules).

### 9. File safety (`file-safety`, `src/fenolite/safety/`)

- **`fenolite snapshot PATH --out DIR`.** It copies a board or a project with its companion files (project, rules, library tables, sheets). It accepts the copy only when every source hash is equal before and after the copy. A file that keeps changing is `safety.unstable` (exit 3).
- **`fenolite publish SRC --to DST --receipt RECEIPT --dry-run|--confirm`.** It replaces each file of DST only when its current hash equals the hash that RECEIPT recorded when Fenolite last wrote it. Any other file is left alone and reported (`safety.changed-since-receipt`, error). New files are added. Every replaced file is backed up.
- **Open sessions.** `fenolite doctor --sessions PATH` lists lock files that CAD tools leave beside an open file. For KiCad, the lock file name is documented. For another tool, a lock file is listed only when its pattern is recorded with a public source. Every write command reports `safety.open-session` (warning) when the target has one.
- **Cloud placeholders.** A file that a sync client keeps online only (an offline or dataless attribute) is reported before it is read (`safety.placeholder`, exit 3), instead of blocking the read.
- **References.** `fenolite refs PROJECT [--repoint OLD=NEW]` lists every path that a project's documents hold (sheets, libraries, drawing documents, output jobs, as the readers give them). With `--repoint`, it rewrites those that start with OLD, through the reviewed-plan protocol. A document whose format Fenolite cannot rewrite is reported, not touched.
- **Evidence.** `INFERRED` for detection. The writes follow the mutation protocol, with receipts.

### 10. Library fidelity (`design-conversion`, KiCad footprint writer)

The three items below moved on 2026-10-28 to change c0223 (`openspec/changes/c0223-library-fidelity/`), whose
design narrows them; the body copy and the coverage report of "Additions from the survey" stay here.

- **Mask and paste of imported pads.** A pad read from Altium takes its mask and paste layers from its kind:
  - a surface pad gets its side's copper, paste and mask;
  - a plated through-hole pad gets both masks and no paste;
  - an unplated hole gets both masks.

  The expansion of each pad (rule-based or per pad) is kept as the pad's mask and paste margins when the model can hold it, and listed as a loss otherwise. This closes the defect that `docs/conversion.md` records.
- **Model placement.** The model of a footprint holds, for each 3D model, its path, offset, rotation and scale. The KiCad footprint writer writes them for a footprint read from another format. The Altium reader gives an embedded model as an extracted file beside the output, with its placement, and lists it.
- **Library from a board.** `fenolite library BOARD --out LIB` writes each footprint as placed on the board, brought back to its own origin and side, into a library. Each name is kept, or made unique with a suffix when two placed instances differ. `--diff LIB` reports, per footprint, how the library differs from the board's instances: pads, silkscreen, courtyard, models. This is the drift report.
- **Evidence.** `KICAD-VERIFIED` for KiCad libraries (footprints load, and the board's DRC finds no library mismatch). The Altium direction stays experimental.

### 11. Release checks (`manufacturing-exports`, `kicad-oracle`)

- **Read-back.** `fenolite export ... --readback` parses the Gerber and Excellon files that were written, with Fenolite's own minimal readers for the subset `kicad-cli` writes, and checks them:
  - the outline closes into `1 + cut-outs` contours whose boxes match the board's rings;
  - each drill hit or slot matches a board hole in position, diameter and plating;
  - each position row matches its footprint;
  - each copper layer has its file, with a file function;
  - no used layer is empty.

  A finding is `export.readback-*`, an error.
- **Trial edits.** `fenolite.api.trial(board, edit) -> TrialResult`:
  1. apply an edit to a copy;
  2. refill the zones;
  3. run DRC;
  4. compare the findings with those of the unedited copy;
  5. map each new finding to the ids of the edit's items.

  A command that writes copper may pass `--gate drc` to drop the items that bring new findings, and report them.
- **Exclusions.** `fenolite check BOARD --exclude CODE:ITEM_A:ITEM_B --reason TEXT --confirm` stores a DRC exclusion in the project, written in both item orders, because KiCad does not keep their order.
- **Moved.** On 2026-10-28 the exclusions and the library call `fenolite.api.trial` with its gate moved to
  change c0209 (`openspec/changes/c0209-drc-trials/`), and the `--gate drc` option of the writing commands
  to change c0225 (`openspec/changes/c0225-drc-gate/`).
- **Region renders.** `fenolite render BOARD --region X1,Y1,X2,Y2 --nets --open` draws one region with pad net names, tracks, vias, slots, filled zones and the open connections, on a grid labelled in board coordinates.
  Moved on 2026-10-28 to change c0211 (`openspec/changes/c0211-region-renders/`).
- **Evidence.** `KICAD-VERIFIED` (`kicad-cli` writes the files, and DRC is the oracle).

### 12. Native Altium edit sessions (`altium-edit`, `src/fenolite/backends/altium/edit/`)

In the maintainer's work, every change to an Altium board that the owner kept editing in Altium went through record-level edits of the saved document. About one hundred and fifty scripts did this. Six kinds of offline edit made the tool crash on open or save. Fenolite reads these documents losslessly and writes compound files, but it has no edit session.
- **Edit session.** `altium.edit.open(path) -> Session`, then:
  - typed operations: `delete`, `move`, `rotate`, `flip(ref)`, `set_property`, `clone(item, **changes)`, `add_component(from_doc, ref)`, `remap_layer(old, new)`, `set_rule`;
  - `commit(out) -> Receipt`.

  The session keeps every index table of the document consistent with the primitive streams: the per-primitive GUID table, the pad and via cache, the unique-id table, the polygon indices, the wide-string table, the primitive parameter groups and the model store. It clones full-length records from records that the tool itself saved, rather than writing short forms beside them.
- **Asserted edits.** Each operation names the item by its geometry and net, and asserts exactly one hit. Each operation states the old value that it expects; a mismatch refuses the commit.
- **Gates.**
  - The commit re-reads the written file strictly.
  - It compares the decoded result with the input, and refuses changes outside the declared set (`altium.edit.unexpected-change`).
  - It refuses a connectivity change unless the session declares one.
  - The schematic session (`SchDoc`) checks that the net signature of each sheet is unchanged, unless a change is declared.
- **Integrity check.** `fenolite check DOC --stages altium.integrity` reports, without writing, the faults that make the tool refuse or crash a document:
  - gaps in per-polygon sub-indices;
  - duplicate pour indices;
  - duplicate GUIDs;
  - parameter groups whose count disagrees with their records;
  - orphan parameter records of removed components;
  - model-store entries that no body uses, or bodies without one;
  - two layer fields of one primitive that disagree.

  Each rule is a hypothesis of `docs/hypotheses.md`, measured by the maintainer's kit on files authored for Fenolite. No rule is stated here as a format fact.
- **Repointing companion documents.** Drawing documents and output jobs store their source paths. `fenolite refs` of package 9 rewrites them through this session, once the drawing writer of c0172 graduates.
- **Format knowledge.** Every field this package writes comes from public sources or from the maintainer's kit runs (`ALTIUM-VERIFIED(kit)`), as the Altium format pages require. The kit cases list the questions to measure:
  - which of two layer fields the tool reads;
  - how a body rotation selects its model entry;
  - what a resave rewrites.

  The answers are recorded only when measured.
- **Evidence.**
  - Experimental.
  - Each operation needs a kit case: the document opens, is saved and is reopened in Altium, and the decoded content is equal.
  - Until then, the session refuses to write over a document that the user names as a master (`--master`).
- **Moved.** On 2026-10-29 the whole package, with tasks 6.1 to 6.7 and the `altium-edit` delta, moved to
  change c0241 (`openspec/changes/c0241-altium-edit-sessions/`), which registers the hypotheses `H-A-EDIT-*`
  and `H-A-INTEG-*` and holds kit Part J (`docs/evidence/altium-edit.md`).

### Additions from the survey to packages 4 to 11

- **Package 4:**
  - a rigid move of a block with every primitive it owns (copper, zones, texts, bodies);
  - a free-space map;
  - a pose search, which tries the four turns and a grid of shifts and scores the routing demand of each.
- **Package 5:**
  - the router also works on the neutral model of a read Altium board, and writes through package 12;
  - sense pairs are routed as pairs, from the inner pad edges;
  - the chamfer applies to polygon outlines too, keeping the pour's contact with its pads and its clearance.
- **Package 6:**
  - stitching vias placed for current sharing, counted by the current of the net;
  - a free-area fill, which only removes copper when it smooths.
- **Package 7, more kinds:**
  - `necks` (necks, slivers and acute tips of pours);
  - `loops` (the area of a declared loop, compared between two versions);
  - `balance` (the copper of the two pads of a two-pad SMD part, for tombstoning);
  - `--kinds power --split`, the share of a net's current in each parallel path and in each via, from a resistive field solve on a raster of the copper.

  Each kind keeps the three copper states apart (outline, saved fill, simulated pour), and says which one a row used.
- **Package 9:**
  - `fenolite diff --allow KINDS` exits 5 when the difference holds a change outside the allowed kinds;
  - `--three-way BASE` ports the changes of a parallel copy onto the current file, and refuses on conflict;
  - for Altium documents, the bytes that a plain resave rewrites are classified as `resave` and kept out of the semantic difference.
- **Package 10:**
  - 3D bodies are copied between boards by pad fit;
  - the model store gets one entry per rotation variant;
  - library consolidation keeps a signature per footprint and symbol;
  - a coverage report compares a design's parts with a house library that the user names.
- **Package 11:** a stored DRC report is reconciled with the accepted exceptions. A finding that is neither new nor accepted is listed.

### Cut order

| order | package | days | why first |
|---|---|---|---|
| 1 | 1 router input fidelity | 2 | a defect; every routed board pays for it |
| 2 | 2 ground ties | 2 | the most costly fault that no check sees |
| 3 | 3 barrier crossings | 2 | it saves hours of failed routing |
| 4 | 9 file safety | 4 | lost work is the most costly failure of all |
| 5 | 7 practice checks | 8 | the practice pages refer to them |
| 6 | 12 native Altium edit sessions | 10 | most edits of a board kept in Altium need it; gated by the kit |
| 7 | 5 copper tidy | 6 | every router output needs it |
| 8 | 4 layout reuse | 6 | reference blocks are common in power boards |
| 9 | 8 assembly marks | 6 | reviews reject boards for marks |
| 10 | 10 library fidelity | 6 | every Altium user meets the mask defect |
| 11 | 6 generated copper | 4 | it builds on 7 and 5 |
| 12 | 11 release checks | 4 | last, before a fabrication release |

Each package may be split into its own change with the next free id when its turn comes. Its tasks below move with it.

## Risks / Trade-offs

- **Scope.** Eleven packages are a release's worth of work. The cut order lets the maintainer stop after any package.
- **Heuristics as rules.** Straightening, designator placement and test-point placement are heuristics. Each writes only through a reviewed plan, and each write is gated by the copper check and DRC.
- **Altium writes stay experimental.** Packages 4, 5, 6 and 8 write KiCad first. For Altium, where the write exists, it follows the graduation rule of c0092.
- **Lock-file patterns.** Only patterns with a public source are listed; an unknown tool gives no warning. The page says so.

## Open questions

1. Should `tidy` and `silk` be subcommands of one `fenolite edit`, or stay separate commands? The recommendation is to keep them separate, one subject each, as the existing commands are.
2. Should the rows `[[decoupling]]` and `[[body_copper]]` of the requirements file get a schema version step, or stay optional keys of `fenolite.requirements.v0`, as c0115 did? The recommendation is optional keys.
3. Should package 9's lock-file listing include tools other than KiCad in this change, or only once a public source for each pattern is registered? The recommendation is the latter.
