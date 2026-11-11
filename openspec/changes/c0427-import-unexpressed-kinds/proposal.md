# c0427: import-unexpressed-kinds

## Why

`import --to python` of Altium boards leaves items out as `import.item-unexpressed` and needs
`--allow-lossy` in many cases (S-1860..S-1869, a sweep whose codes and counts reached this change; every
fixture here is authored or public). On the public Altium rows of the corpus manifest, two rows emitted
code that does not build (a negative silk to silk clearance), one gave a board outline KiCad calls invalid
(a board cut-out across the board shape), and two left texts out (CR LF line breaks).

## What changes

- A rule the DSL cannot say (an undeclared class, a selector it cannot write) is kept as written: every
  rule of its constraint kind becomes `design.verbatim("rule/<n>", <text>, target="kicad_dru")` in file
  order, so the precedence of the file holds (`H-K-DRU-ORDER`); the other kinds stay `design.rules` calls.
  A rule `_rule_call` refuses no longer reaches the script, so the import never emits code that does not
  build.
- `design.rules.rule()` takes a negative `min` for `silk_clearance` (`H-K-DRU-NEG-SILK`, KiCad 9.0.9 and
  10.0.6); every other kind still refuses one.
- A net that only a copper graphic names gets a net variable, so a fill or region on a board-only net is
  code with `net=`.
- A drawing may be on `F.Paste` or `B.Paste` (`H-K-PASTE-DRAWING`): an Altium paste region is code.
- The Altium reader turns a text's CR LF into a line feed (`H-A-TEXT-CRLF`), and cuts the board shape by a
  board cut-out that crosses it (`altium.import.cutout-notch`, `H-A-CUTOUT-NOTCH`).
- The Python import preserves truly netless vias and the zero width of curved user drawing arcs.
- The importer and KiCad build preserve boards without a closed boundary and their individual edges.
- The importer carries nets on unnumbered copper pads as instance assignments, without schematic pins.
- A corpus test pins the import result of every public Altium PCB document.

## Not in this change

- c0426 owns the via whose drill equals its diameter (row 02) and the 1 nm pad-position rounding (row 01).
- c0428 owns the zone outlines that come out with fewer than three vertices (`zone-outline`).
- Non-copper unnumbered pads cannot receive a net. The new physical-pad paths are proved with
  authored boards.
