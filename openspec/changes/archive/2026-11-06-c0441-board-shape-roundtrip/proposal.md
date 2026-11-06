# c0441: an Altium board through KiCad and back keeps its shape and its connections

## Why

Altium DRC on a public-class board taken Altium → KiCad → Altium shows two rule groups that are 0 on the
source (S-2000 to S-2009): board-outline clearance (tracks, pads and vias near the edge) and net antennae
(tracks with a loose end). Measured on the eight public PcbDoc of the corpus:

- **Outline.** The KiCad → Altium write gives each arc of the board ring as two straight edges through its
  mid (`OUTLINE_ARC`, counted under `outline`): BMS loses 8 arcs, NG6011 4, DM6010_R2M2E2 2. Copper near a
  rounded corner is then too close to, or outside, the written edge.
- **Antennae, vias.** The write leaves out a via whose hole equals its diameter ("the drill is not below the
  diameter"): 48 of 242 vias of foc.PcbDoc, each in a pad on the other side, so the track ends on them hang.
  A document that Altium saved holds such vias (`H-A-PCBX-VIA-FULL`); only a rewrite of a read document
  wrote them (change c0128).
- **Antennae, pads.** The Altium → KiCad write leaves the corner ratio out of a created board pad
  (`roundrect_rratio`, kept only beside a chamfer since c0277). Read back, the pad has no ratio, and the
  Altium write leaves it out: 69 of 385 pads of PCB1.PcbDoc (U1, U2, A1), and the track ends on them hang.
- **Antennae, regions.** A free copper region of a net is read as a filled copper graphic with its net; the
  KiCad write keeps `(net …)`, but the KiCad → Altium conversion does not project it into `net_id` (a build
  does, `fpitems.with_graphic_nets`, c0412), so the 45 netted regions of BMS.PcbDoc come back with No Net
  and Altium reports the vias on them as antennae (altium-rounds, AD 24.5, 0 → 398).
- **Rounding.** The write moves a converted board so that its corner lies at (1000 mil, 1000 mil). The
  corner is any nanometre, so each coordinate rounds apart, by 1 to 3 nm: the round trip is no exact
  translation, and an exact comparison of the shape cannot hold.
- `equivalent` compares level 7 in the absolute frame only, so a board moved by the round trip differs in
  every edge, and a flattened arc cannot be told from the move.

## What Changes

- The Altium writer writes an outline arc as one arc vertex (`KIND=1`, centre, radius, start and end angle
  of the counter-clockwise sweep), from the three points of a model arc (`PcbDocSpec.outline_arcs`); the
  `outline` loss of an arc is gone.
- `lower.write_design` and `from_design` take `full_drill`: a via whose hole equals its diameter is written,
  without the rest of a rewrite. A conversion sets it; a build does not.
- The KiCad board writer writes the corner ratio of every created pad that has one.
- The KiCad → Altium conversion projects the net of each copper graphic (`fpitems.with_graphic_nets`).
- A conversion to Altium moves the board by whole document units (`Frame.on_units`: its corner out to a
  multiple of 254 nm), so a coordinate read from a document comes back to the nanometre after the move.
- Level 7 of `equivalent` moves side b's board shape (its outline, cut-outs, slots and `Edge.Cuts`
  drawings) back by level 4's translation: in the relative frame the board shape compares exactly.

## Impact

- `backends/altium/docboard.py`, `pcbdoc.py`, `lower.py`; `backends/kicad/pcb.py`; `convert/to_altium.py`;
  `checks/equivalence/shapes.py`, `levels.py`.
- Bytes: a KiCad → Altium conversion of a board with outline arcs, full-drill vias, or a corner off the
  254 nm grid; an Altium → KiCad conversion of a board with rounded-rectangle pads. A build is unchanged.
- Altium's reading of the written arc vertex is confirmed by the altium-rounds kit, not by this change.
