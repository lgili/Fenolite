# Names of packages authored by Fenolite

Change c0260, design decision 14. This is Fenolite's own convention: it only has to be unique, readable and
checkable against the numbers of a package record. It is not taken from IPC's naming pattern nor from KiCad's
library conventions. Label: `INFERRED` (Fenolite-authored).

```
<FAMILY><pins>_B<L>x<W>[x<H>]_P<pitch>[_EP<x>x<y>][_<variant>]    generic, from a registered outline
<FAMILY><pins>_<Maker>_<drawing id>                                 the manufacturer's own drawing
```

| field | meaning |
|---|---|
| `FAMILY` | upper case: `CHIP`, `SOD`, `SMA`, `SOIC`, `SSOP`, `TSSOP`, `MSOP`, `QFP`, `SOT`, `QFN`, `DFN`, `SON`, `BGA`, `TO`, `DIP`, `HDR`, `CONN` |
| `pins` | the number of pins (`rows x columns` for a header, `HDR2x5`); for `CHIP` the size code (`CHIP0603`) |
| `B<L>x<W>` | the nominal body in mm without trailing zeros: `L` along the pin rows, `W` across them; for a two-terminal part `L` is along its terminals |
| `x<H>` | the nominal height, only when two packages differ by height only |
| `P<pitch>` | the nominal pitch in mm |
| `EP<x>x<y>` | the nominal exposed pad, `x` across the rows and `y` along them |
| `variant` | a tab, a row pattern or an orientation (`RA` right angle, `SMD`) |

Examples: `SOIC8_B4.9x3.9_P1.27`, `QFN16_B3x3_P0.5_EP1.68x1.68`, `SOT5_B2.9x1.6_P0.95`, `HDR1x2_P2.54`,
`BGA12_B2x2.5_P0.5`, `CHIP0603_B1.6x0.8`. The names of the 0.6 catalog (`SOIC14_TI_D0014A`, `Chip_0402`) stay.
A name is never reused for other numbers: an interface change makes a new id (c0259).

## The check

A name is generic when it holds a `_B<L>x<W>` or a `_P<pitch>` field. Each field it holds is compared with
the record's nominal numbers; a field that disagrees is the error `package.name-mismatch` naming the field,
and no footprint is drawn. The pin count is checked when the family has pins (not for `chip`, `molded` and
`grid`). Other names are not checked. A connector series names each position count by its `name_pattern`
(`{series}`, `{n}`, `{pitch}`).

## Grid arrays

Rows are lettered from `A` at the top in the top view, columns numbered from 1 at the left; `A1` is the
top-left ball. The letters `I`, `O`, `Q`, `S`, `X` and `Z` are skipped, then the rows continue `AA`, `AB`, ...
Evidence: the Texas Instruments ZXH0080A grid (S-0988) letters its nine rows `A` to `J` without `I`, which
confirms the skipped `I` (`CORPUS-VERIFIED` is not claimed: one public drawing). The other skipped letters
follow the same rule of leaving out letters that read like digits or like one another, and are `INFERRED`.
