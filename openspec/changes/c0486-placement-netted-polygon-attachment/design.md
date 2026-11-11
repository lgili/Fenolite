# Design: c0486

## D1 Project the graphic nets first

`fpitems.with_graphic_nets` already gives a copper graphic the net its KiCad slot names (c0412, c0454).
The equivalence check and the Altium writer use it through `model.graphicnets.with_graphic_nets`. `propose`
calls it once on the design it reads, before `backend.board_pads` and `inspect_attachments`. A graphic
whose slot names no net of the circuit keeps `net_id=None`.

The KiCad reader is not changed. It keeps the net in the slots so a rewrite gives the same bytes.

## D2 A netted graphic is a copper piece

`inspect_attachments` today sets `unsupported` for any graphic on a copper layer. After this change:

- A copper graphic with a `net_id` of kind `polygon`, `rect` or `circle` is a piece of its net: its
  filled interior when `filled`, and its stroke of `width` in every case. `line` and `arc` give their
  stroke. The piece goes into the `copper` list that `joined_at` tests, as a saved fill does.
- A copper graphic with no `net_id` stays unsupported, as netless tracks and fills are.
- A graphic whose shape fails (`GeometryError`, `ValueError`) is unsupported.

The shapes reuse the helpers of `tidy.graph` (`_fill_piece` for an interior, `Thick` for a stroke). The
pieces are built in `placement_protection`, so tidy's own projection is unchanged.

## D3 The move frame in words

The frame of `--move` is the frame of `place()`: origin at the top-left corner of the box of the outline,
X to the right, Y down. The help text says it with a direction: "a larger Y moves the part down; a part
above the corner has a negative Y". `placement.md` says the same and adds that Altium shows Y up, so a
position read in Altium needs its sign changed. The `--region` help gets the same words.

The test moves a part by `+1mm` in Y and checks that its file `y` grows by 1 mm.
