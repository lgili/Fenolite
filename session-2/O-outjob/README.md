# Part O, session 2: the output job with the Gerber settings (change c0138)

Built on 2026-10-07 by Fenolite, branch `c0138-altium-outjob-gerber-settings`, commit `4373dc17` (the one
commit of change c0138 on dev `c69f8c6b`, which holds change c0134). For Altium Designer 26.

The three projects were built a second time from that commit, because c0134 changed the pin texts of the
catalog symbols after the first build: the schematic document and library of `board6/` are new; every other
file has the bytes of the first build.

**Why again.** In session 1 the written job ran, but its Gerber output plotted no layer: the job held no
settings record for it. The jobs here hold the complete record on the Gerber output (44 fields: unit
millimetres, the decimals, the layers to plot) and one more key, `OutputDefault<i>=0`, on every output.

**The steps were written from Altium's documentation.** A menu path or a dialog name may read differently in
version 26. If a step cannot be done as written, say what you saw instead.

**Not in these jobs: the board outline.** No job asks for a plot of the board outline; step O6 asks what
Altium offers for it.

## What to open

| folder | what it is | open |
|---|---|---|
| `blink_routed/` | two copper layers, no preset (4 decimals) | `blink_routed.PrjPcb`, then `blink_routed.OutJob` |
| `board6/` | six copper layers, the third an internal plane on GND | `board6.PrjPcb`, then `board6.OutJob` |
| `blink_routed_p6/` | as `blink_routed/`, built with the preset `precision6.toml` (6 decimals) | `blink_routed.PrjPcb`, then `blink_routed.OutJob` |

`precision6.toml` is the export preset of the third build; it is not opened in Altium.

## Layers each job asks for, in order

- `blink_routed` and `blink_routed_p6` (12): Top Overlay, Top Paste, Top Solder, Top Layer, Bottom Layer,
  Bottom Solder, Bottom Paste, Bottom Overlay, Mechanical 13, Mechanical 14, Mechanical 15, Mechanical 16.
- `board6` (16): Top Overlay, Top Paste, Top Solder, Top Layer, Mid-Layer 1, Internal Plane 1, Mid-Layer 3,
  Mid-Layer 4, Bottom Layer, Bottom Solder, Bottom Paste, Bottom Overlay, Mechanical 13 to 16.

## Steps (one line back for each)

1. **O1** (`blink_routed/`): open the project, then the job. Expected: no message.
   Report: `as expected`, or the message.
2. **O3** (`blink_routed/`): generate the container `fab`, then the container `doc`. This generates all six
   output kinds again (Gerber, NC drill, pick and place, bill of materials, schematic print, PCB print),
   because every output now carries one more key than in session 1. Expected: no error, and Gerber layer
   files this time.
   Report: the extensions of the files in the Gerber folder, as a list; whether the report of the Gerber
   output names layers; whether the five other kinds still appear.
3. **O5** (`blink_routed/`): open the setup of the Gerber output (double-click it, or right-click and
   Configure). Expected: millimetres, 4 decimals, the twelve layers above with their plot switch on.
   Report: the units, the format or decimals, and the layers that are on (or `as expected`).
4. **O6** (`blink_routed/`): in the same setup, look for the board outline in the layer list (the
   documentation names one as the first entry).
   Report: whether it exists, what it is called, whether its plot switch is on. Then turn it on if it exists,
   close with OK, save the job **under another name** in the same folder, generate `fab` again, and report
   whether an outline file is produced and its extension. Leave the saved job in the folder.
5. **O7** (`board6/`): open the project and the job, generate `fab`.
   Report: the extensions of the Gerber files, and whether one file is the internal plane.
6. **O8** (`blink_routed_p6/`): open the project and the job, read units and decimals in the Gerber setup,
   generate `fab`. Expected: millimetres and 6 decimals.
   Report: what the setup shows (a value Altium replaced is a result, not a failure) and whether files appear.

Also to send back: the Altium version as `AD <major>.<minor>` and the date. And one sentence on session 1,
with the minor version: "the Gerber output of the old job produced no layer file" (or what it did); that
settles one row without a new run.

Nothing that Altium writes here goes into the repository.

## SHA-256

```
595be494ec0a3ce8edc084cd041d86b2fe4bab9cd94f05b5a7e557864f44f950  blink_routed/blink_routed.OutJob
6691042bc82ef6250d4944f6b08ab8be16b8aeb83d39f0c6975d42cfc332333a  blink_routed/blink_routed.PcbDoc
640bbcdb207a1dd724d310963f135101f6fb7525b5b59d22516a23ecaa4955ce  blink_routed/blink_routed.PcbLib
99bcc6d91837bf0c0f55876e5be11ae444eca9c11c10bf8c6dbf56c110a8093d  blink_routed/blink_routed.PrjPcb
50a062c3ae03c6dec28e803f42c01d18c1e7c7c39cb439c640135611e4065c14  blink_routed/blink_routed.SchDoc
44e8f59b353162278a631fa533f02197e4df3f40d88de8831cc3f111abe12e22  blink_routed/blink_routed.SchLib
cffaa5da448480a99feba314a4e08a47a4f14dd27f016ad72ec5875c191a50e1  board6/board6.OutJob
c92105d2c9f0b745151e83eca2e783fd30c729f6af1621cebac485e55dba118b  board6/board6.PcbDoc
4a6e40784c51a52705a653ad7410b524790a98d38c16d2dde68fc6b5e2cbbbde  board6/board6.PcbLib
914dc3d485a8d978d5da7d7f6116eedf4d1e1cad2646b05499baff7b59bc8a88  board6/board6.PrjPcb
a0601e61b5bb8985beda3b02dd22e525f4378d0a90e0d407383a22c83e2dd849  board6/board6.SchDoc
b1b5ec08350ce0722e4b230e769fb33bdd51e19aef1c8dcd691dbca3dabe635b  board6/board6.SchLib
bb3e5505a4bc91c07dd894c984e2a8710cd7d485be89de84ced996637236d5e5  blink_routed_p6/blink_routed.OutJob
6691042bc82ef6250d4944f6b08ab8be16b8aeb83d39f0c6975d42cfc332333a  blink_routed_p6/blink_routed.PcbDoc
640bbcdb207a1dd724d310963f135101f6fb7525b5b59d22516a23ecaa4955ce  blink_routed_p6/blink_routed.PcbLib
99bcc6d91837bf0c0f55876e5be11ae444eca9c11c10bf8c6dbf56c110a8093d  blink_routed_p6/blink_routed.PrjPcb
50a062c3ae03c6dec28e803f42c01d18c1e7c7c39cb439c640135611e4065c14  blink_routed_p6/blink_routed.SchDoc
44e8f59b353162278a631fa533f02197e4df3f40d88de8831cc3f111abe12e22  blink_routed_p6/blink_routed.SchLib
```

The five files beside each job of `blink_routed/` are byte-equal to those of session 1: only the job differs.
Each `blink_routed*` folder also holds `.fenolite/`, the build's own record; it is not opened in Altium.
