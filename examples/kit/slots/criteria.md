## Part S: slots and cut-outs

Change c0168; pending, no Altium verification is claimed. Fenolite writes a **drilled** slot (a hole with
a length, `design.hole(..., length=...)`) as a free pad with a slotted hole, and a **milled** slot or a
cut-out (`design.slot`, `design.cutout`) as a board cut-out region. KiCad's importer reads both
(`H-A-SLOT-PAD`, `H-A-CUTOUT-REGION`); this part asks what Altium Designer does with them
(`H-A-SLOT-KIT`). Releases write no cut-out region until S3, S4 and S5 pass (`pcbdoc.CUTOUT_REGIONS`).

**Files.** Built outside the repository by `FENOLITE_ALTIUM_PART_S=~/fenolite-altium-checks/session-4/S-slots
uv run pytest tests/unit/backends/altium/test_part_s.py` (needs `fenolite[geo]`): `regions/`, `clearance/`
and `gate-off/`, each an Altium project `slots.PrjPcb` with its `slots.PcbDoc`; `expected.md` (the place
and size of every slot, hole and cut-out, read back from the files); this text as `README.md`; and
`SHA256SUMS`. The board is 60 × 40 mm. Coordinates below are millimetres from its lower-left corner, which
is the document's origin.

| item | where | what it is |
|---|---|---|
| `D1` | (27, 7), turned 30° | drilled slot 12 × 2 mm, alone |
| `D2`, `D3` | (38, 13) and (43, 8), turned 90° | drilled slots 10 × 2 mm whose holes overlap in an L |
| `H1` | (52, 8) | round hole 3.2 mm |
| `S1` | (15, 30), turned 30° | milled slot 12 × 2 mm, alone |
| `S2` + `S3` | (40, 30) and (45, 25) | two milled slots 12 × 2 mm merged into one L-shaped cut-out |
| `cut-out 1` | 8 … 20 × 8 … 16 | rectangular cut-out with 1 mm round corners |
| `TP1`, `TP2` (only `clearance/`) | (38, 28.3) and (36, 14.7) | 1 mm round pads on net `GND`, 0.2 mm from `S2` and from `D2` |

`clearance/` also holds a `GND` polygon on the Top Layer over the whole board and two rules: Board Outline
Clearance 0.5 mm and Hole To Hole Clearance 0.25 mm.

Work on a copy of the folder. For each case report `as expected` or what differed, in one sentence.

1. **S1** Open `regions/slots.PrjPcb` and its PCB. Double-click `D1`. Expected: the document opens with no
   repair message; `D1` is a pad on Multi-Layer with no designator, Hole shape Slot, Hole Size 2 mm,
   Length 12 mm, not plated, and no copper ring around the hole. Note the solder mask and paste openings
   shown at `D1` (Fenolite leaves both "from the rules"). Then **File » Fabrication Outputs » NC Drill
   Files** (defaults) and **Drill Drawings**. Expected: `D1` is a slot in the non-plated drill file and in
   the drill drawing.
2. **S2** Open `clearance/slots.PcbDoc`, run **Tools » Design Rule Check** (Run Design Rule Check).
   Expected: Hole To Hole Clearance reports the pair `D2` – `D3` (their holes overlap).
3. **S3** In `regions/slots.PcbDoc` press `1` (Board Planning Mode) and `3` (3D Layout Mode), then `2` to
   return. Expected: the board shape has the openings of `S1` and of `cut-out 1` in 2D and in 3D. The NC
   drill files of S1 hold no hit for `S1`, `S2`, `S3` or `cut-out 1`.
4. **S4** In `regions/slots.PcbDoc` click the L-shaped opening of `S2` + `S3`. Expected: one Region whose
   Kind is Board Cutout (not two), with a round end at each of the three free ends.
5. **S5** In the DRC report of S2. Expected: Board Outline Clearance flags `TP1` (0.2 mm from the cut-out
   edge) and does not flag `TP2` (0.2 mm from the drilled slot `D2`, which is a hole, not an edge).
6. **S6** In `clearance/slots.PcbDoc` run **Tools » Polygon Pours » Repour All**. Expected: the polygon
   pours without a message and leaves no copper inside `S1`, the L of `S2` + `S3` or `cut-out 1`.
7. **S7** Save `regions/slots.PcbDoc` with **File » Save As** to `regions/slots-saved.PcbDoc`, then run
   `FENOLITE_ALTIUM_S7=<that file> uv run pytest tests/unit/backends/altium/test_part_s.py -k s7` in the
   repository. Expected: the test passes (the same four holes and three cut-outs within 1 µm).
8. **S8** Open `gate-off/slots.PcbDoc` and `gate-off/build-report.json`. Expected: the board has no
   cut-out region (only the four holes), and the report names each cut-out: `slot/S1`, `slot/S2+slot/S3`
   and `cutout/1`.

Send the Altium Designer version (`AD <major>.<minor>`), the date, the SHA-256 of `regions/slots.PcbDoc`
from `SHA256SUMS`, and one outcome per case, in the form of the native acceptance inventory (date, version,
case, file hash, step, expected and observed outcome). S1 to S8 settle `H-A-SLOT-KIT`; S3, S4 and S5 decide
the gate.


Formal mapping: K5.6=S1, K5.7=S2, K5.8=S3, K5.9=S4, K5.10=S5, K5.11=S6, K5.12=S7, K5.13=S8. Work inside the slots sample folder; use the actual single Altium version in the run form. Historical outcomes on another version are not outcomes of this run.
