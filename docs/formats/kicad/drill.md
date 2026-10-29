# Drill files (KiCad)

What `pcb export drill --format excellon --excellon-units mm --excellon-separate-th --drill-origin absolute`
writes, as Fenolite's read-back reads it (change c0203; `src/fenolite/exports/readback.py`). Each fact was
observed on `kicad-cli` 10.0.7 and confirmed by the job `kicad-9`, on the files of the authored bench `tests/_readbackbench.py`, whose holes are known by
construction.

## Facts

| fact | source | label | hypothesis |
|---|---|---|---|
| The file starts with `M48`; its header holds comment lines starting with `;`, `FMAT,2`, `METRIC` and one tool definition `T<n>C<diameter>` per tool, diameters in millimetres with three decimals, and ends with a line `%` | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-READBACK-SUBSET |
| A comment line `; #@! TF.FileFunction,Plated,1,2,PTH` or `; #@! TF.FileFunction,NonPlated,1,2,NPTH` names the plating of the file's holes | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-READBACK-SUBSET |
| The body is `G90`, `G05`, then per tool a line `T<n>` and its hits `X<x>Y<y>` in decimal millimetres with a decimal point; a slot is one line `X<x>Y<y>G85X<x>Y<y>` from one centre of the stadium to the other, followed by `G05`; the file ends with `M30` | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-READBACK-SUBSET |
| Y is the board's Y negated, X as on the board, with the absolute origin | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-READBACK-SUBSET |
| The position file of `pcb export pos --format csv --units mm` has the header `Ref,Val,Package,PosX,PosY,Rot,Side`, quoted texts, millimetres and degrees with six decimals, Y negated, and the side `top` or `bottom` | S-0020 | KICAD-VERIFIED (9.0.x, 10.0.x) | H-K-READBACK-SUBSET |
