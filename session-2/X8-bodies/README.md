# Step X8: component bodies (Fenolite change c0121)

Two builds of the sample `body2` with `--altium-bodies extruded`, for Altium Designer 26. The steps
are in Part X of `docs/evidence/altium-pcb.md` of the repository (step X8); a menu path or a dialog
name may read differently in version 26. Nothing in these files was opened in Altium before.

- `saved/`: each body holds the 35 keys of a body that Altium saved, with two stand-in values
  (`MODELID` derived by Fenolite, `MODEL.CHECKSUM=0`). This is the form the option writes.
- `short/`: each body holds the first 21 keys only, without any model key. Built for this step
  only.

## What to open

1. `saved/body2.PrjPcb`, then `body2.PcbDoc` (X8.1 to X8.4, and X8.6).
2. `short/body2.PrjPcb`, then `body2.PcbDoc` (X8.5).
3. `saved/body2.PcbLib`, the footprint of `U1` (X8.7).

## What to look at

- On opening: a repair prompt, or a message in the Messages panel.
- The PCB panel in the mode "3D Models" (or select each body in 2D): three bodies, each owned by
  the footprint of the table.
- The properties of each body: identifier, board side, layer, overall height, standoff height.
- The 3D view: three solids at the heights of the table; body 2 below the board.

| body | footprint | board side | layer | overall height | standoff height | identifier |
|---|---|---|---|---|---|---|
| 1 | U1 | Top | Mechanical 13 | 2.5 mm | 0 mm | (empty) |
| 2 | D1 | Bottom | Mechanical 14 | 1 mm | 0 mm | LED |
| 3 | R1 | Top | Mechanical 13 | 4 mm | 0.5 mm | STANDOFF |

A fourth body of the model names a 3D model; Fenolite does not write it, so the document holds
three.

## What to report (one line each)

The tool as `AD <major>.<minor>`, the date, and per step `as expected` or what differed in one
sentence: X8.1, X8.2, X8.3, X8.4, X8.5 (the same four on `short/`), X8.6 (the printed counts),
X8.7. Do not send a file that Altium wrote.

## SHA-256

- `saved/body2.PcbDoc`: `bee5811bc7a1b43c589722a5b95d1bf1a784aa78f38a5abad8e035156fded2f2`
- `saved/body2.PcbLib`: `9432b8ab5f7801c7c9399a9e943dd272d4b02d2fbfa0586cc34c53e3666b991d`
- `saved/body2.PrjPcb`: `e0b2cca3f3635c5ec50edca85d6dbae0d527a03d3e94447945e874a607769591`
- `saved/body2.SchDoc`: `cfea41d60f7c34fe5ee9ee620ea25acee8d130ac0d2c1dccc2b26ecc030629ab`
- `saved/body2.SchLib`: `53cc1b8f2b0bd2f79bf51f7d4b3e6c011f296ac77e13b39c1669f5dbfc500b07`
- `short/body2.PcbDoc`: `6becb1923051aa3b312cc97eaf8230fab0a50b30d7187253c55411ebe3e8175f`
- `short/body2.PcbLib`: `9432b8ab5f7801c7c9399a9e943dd272d4b02d2fbfa0586cc34c53e3666b991d`
- `short/body2.PrjPcb`: `e0b2cca3f3635c5ec50edca85d6dbae0d527a03d3e94447945e874a607769591`
- `short/body2.SchDoc`: `cfea41d60f7c34fe5ee9ee620ea25acee8d130ac0d2c1dccc2b26ecc030629ab`
- `short/body2.SchLib`: `53cc1b8f2b0bd2f79bf51f7d4b3e6c011f296ac77e13b39c1669f5dbfc500b07`
