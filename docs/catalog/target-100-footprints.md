# C0076 target: 100 reusable footprint variants

## Selection and limits

This is a **curated target informed by observed use**, not a worldwide top-100 ranking. Fenolite
counted the `raw.kicad_pcb` files in the public PCBench snapshot
`dec3be75cbdef74787625f9043c7391cd473bb64` (S-0348): 1,182 board files, 76,615
`footprint`/`module` blocks and 7,819 distinct raw identifiers. A case-insensitive family-token
count found 0603 in 11,763 placements across 469 boards, 0805 in 8,943 across 517, 0402 in
4,178 across 143, SOT in 2,052 across 541, SOD in 1,366 across 244, header/JST-like names
in 2,983 across 649, and mounting-hole names in 1,197 across 296. Token counts overlap,
can include custom names, and do not identify an exact physical land pattern. The corpus is
open-hardware work, not a representative sample of all commercial PCBs.

To reproduce the proxy, scan each `PCBs/*/raw.kicad_pcb` file at this commit for line-start
`(footprint ...)` or `(module ...)` records, accepting both quoted and unquoted identifiers.
Count each record once. For a family, match its case-insensitive token in the identifier (for
size tokens, require non-digit boundaries); count placements and boards containing a match.
No board is deduplicated by project or revision, and no footprint geometry is parsed or reused.

Fenolite selected reusable variants within these observed families, plus common IC, LED, switch,
THT and mechanical patterns. IPC-7351B's public contents (S-0349) guides family coverage; TI's
package index (S-0350) shows why pin count, pitch and body dimensions must be resolved together.
JST (S-0351) and Amphenol (S-0352) identify the connector candidates. These sources justify
priority and taxonomy only. **None authorizes copying CAD geometry or shipping an unsourced land.**

The names below are *target slots*. The 14 entries marked `existing` are already in the catalog;
the other 86 are `planned` and cannot be used yet. A provisional name is not a final lib ID:
the exact manufacturer's body, pitch, lead span, exposed pad and mounting variant must be chosen
from an official drawing first. If two slots resolve to the same lands, keep one definition and
replace the duplicate slot so the final catalog still contains 100 distinct patterns.

## Inventory

| # | Target slot | Family | State |
|---:|---|---|---|
| 1 | `Chip_0201` | Chip passives / MELF | planned |
| 2 | `Chip_0402` | Chip passives / MELF | existing |
| 3 | `Chip_0603` | Chip passives / MELF | existing |
| 4 | `Chip_0805` | Chip passives / MELF | existing |
| 5 | `Chip_1206` | Chip passives / MELF | existing |
| 6 | `Chip_1210` | Chip passives / MELF | planned |
| 7 | `Chip_1812` | Chip passives / MELF | planned |
| 8 | `Chip_2010` | Chip passives / MELF | planned |
| 9 | `Chip_2512` | Chip passives / MELF | planned |
| 10 | `MELF_0102` | Chip passives / MELF | planned |
| 11 | `DO214AC` | Diodes, transistors and power discretes | existing |
| 12 | `DO214AA` | Diodes, transistors and power discretes | planned |
| 13 | `DO214AB` | Diodes, transistors and power discretes | planned |
| 14 | `SOD123` | Diodes, transistors and power discretes | planned |
| 15 | `SOD123F` | Diodes, transistors and power discretes | planned |
| 16 | `SOD323` | Diodes, transistors and power discretes | planned |
| 17 | `SOD523` | Diodes, transistors and power discretes | planned |
| 18 | `SOD128` | Diodes, transistors and power discretes | planned |
| 19 | `DO35_P10.16` | Diodes, transistors and power discretes | planned |
| 20 | `DO41_P10.16` | Diodes, transistors and power discretes | planned |
| 21 | `SOT23_3` | Diodes, transistors and power discretes | existing |
| 22 | `SOT23_5` | Diodes, transistors and power discretes | existing |
| 23 | `SOT23_6` | Diodes, transistors and power discretes | planned |
| 24 | `SOT89_3` | Diodes, transistors and power discretes | existing |
| 25 | `SOT143_4` | Diodes, transistors and power discretes | planned |
| 26 | `SOT223_3` | Diodes, transistors and power discretes | planned |
| 27 | `SOT323_3` | Diodes, transistors and power discretes | planned |
| 28 | `SOT523_3` | Diodes, transistors and power discretes | planned |
| 29 | `SOT563_6` | Diodes, transistors and power discretes | planned |
| 30 | `SOT883_3` | Diodes, transistors and power discretes | planned |
| 31 | `SC70_5` | Diodes, transistors and power discretes | existing |
| 32 | `SC70_6` | Diodes, transistors and power discretes | planned |
| 33 | `TO252_3` | Diodes, transistors and power discretes | planned |
| 34 | `TO263_3` | Diodes, transistors and power discretes | planned |
| 35 | `TO220_3` | Diodes, transistors and power discretes | planned |
| 36 | `SOIC_8` | Integrated circuits | existing |
| 37 | `SOIC_14` | Integrated circuits | planned |
| 38 | `SOIC_16` | Integrated circuits | planned |
| 39 | `SOIC_20` | Integrated circuits | planned |
| 40 | `SOIC_24` | Integrated circuits | planned |
| 41 | `SOIC_28` | Integrated circuits | planned |
| 42 | `TSSOP_8` | Integrated circuits | planned |
| 43 | `TSSOP_14` | Integrated circuits | planned |
| 44 | `TSSOP_16` | Integrated circuits | planned |
| 45 | `TSSOP_20` | Integrated circuits | planned |
| 46 | `TSSOP_24` | Integrated circuits | planned |
| 47 | `TSSOP_28` | Integrated circuits | planned |
| 48 | `MSOP_8` | Integrated circuits | planned |
| 49 | `MSOP_10` | Integrated circuits | planned |
| 50 | `SSOP_16` | Integrated circuits | planned |
| 51 | `QFN_16` | Integrated circuits | planned |
| 52 | `QFN_20` | Integrated circuits | planned |
| 53 | `QFN_24` | Integrated circuits | planned |
| 54 | `QFN_28` | Integrated circuits | planned |
| 55 | `QFN_32` | Integrated circuits | planned |
| 56 | `QFN_48` | Integrated circuits | planned |
| 57 | `DFN_6` | Integrated circuits | planned |
| 58 | `DFN_8` | Integrated circuits | planned |
| 59 | `LQFP32_P0.8` | Integrated circuits | existing |
| 60 | `LQFP_44` | Integrated circuits | planned |
| 61 | `LQFP_48` | Integrated circuits | planned |
| 62 | `LQFP_64` | Integrated circuits | planned |
| 63 | `LQFP_100` | Integrated circuits | planned |
| 64 | `DIP_4` | Integrated circuits | planned |
| 65 | `DIP_6` | Integrated circuits | planned |
| 66 | `DIP_8` | Integrated circuits | planned |
| 67 | `DIP_14` | Integrated circuits | planned |
| 68 | `DIP_16` | Integrated circuits | planned |
| 69 | `DIP_20` | Integrated circuits | planned |
| 70 | `DIP_28` | Integrated circuits | planned |
| 71 | `Header_1x2_P2.5` | Board connectors | existing |
| 72 | `Header_1x3_P2.5` | Board connectors | existing |
| 73 | `Header_1x4_P2.5` | Board connectors | existing |
| 74 | `Header_1x1_P2.54` | Board connectors | planned |
| 75 | `Header_1x2_P2.54` | Board connectors | planned |
| 76 | `Header_1x3_P2.54` | Board connectors | planned |
| 77 | `Header_1x4_P2.54` | Board connectors | planned |
| 78 | `Header_1x6_P2.54` | Board connectors | planned |
| 79 | `Header_1x8_P2.54` | Board connectors | planned |
| 80 | `Header_1x10_P2.54` | Board connectors | planned |
| 81 | `Header_2x3_P2.54` | Board connectors | planned |
| 82 | `Header_2x5_P2.54` | Board connectors | planned |
| 83 | `JST_XH_1x2_P2.5` | Board connectors | planned |
| 84 | `JST_XH_1x4_P2.5` | Board connectors | planned |
| 85 | `Amphenol_10118192_MicroB` | Board connectors | planned |
| 86 | `LED_0603` | LEDs, switches, THT passives and mechanics | planned |
| 87 | `LED_0805` | LEDs, switches, THT passives and mechanics | planned |
| 88 | `SW_Tact_SMD_4.5x4.5` | LEDs, switches, THT passives and mechanics | planned |
| 89 | `SW_Tact_THT_6x6` | LEDs, switches, THT passives and mechanics | planned |
| 90 | `R_Axial_P7.62` | LEDs, switches, THT passives and mechanics | planned |
| 91 | `R_Axial_P10.16` | LEDs, switches, THT passives and mechanics | planned |
| 92 | `C_Radial_P2.5` | LEDs, switches, THT passives and mechanics | planned |
| 93 | `C_Radial_P5.0` | LEDs, switches, THT passives and mechanics | planned |
| 94 | `C_Electrolytic_D5_P2` | LEDs, switches, THT passives and mechanics | planned |
| 95 | `C_Electrolytic_D6.3_P2.5` | LEDs, switches, THT passives and mechanics | planned |
| 96 | `MountingHole_M2` | LEDs, switches, THT passives and mechanics | planned |
| 97 | `MountingHole_M3` | LEDs, switches, THT passives and mechanics | planned |
| 98 | `TestPoint_SMD_D1.0` | LEDs, switches, THT passives and mechanics | planned |
| 99 | `Crystal_3225_4Pad` | LEDs, switches, THT passives and mechanics | planned |
| 100 | `LED_PLCC4_5050` | LEDs, switches, THT passives and mechanics | planned |

## Completion gate

For each planned slot, record an official package and suggested-land drawing in
`docs/evidence/sources.md` and map the final ID in `docs/catalog/sources.md`. Check pin numbering,
pad shape and separation, paste/mask openings, holes and tabs, body/courtyard/silkscreen layers,
write/readback, offline discovery and a visual preview. Keep any independently authored land
`INFERRED` where the source lacks a recommendation. Replace provisional names with sourced
variant-qualified IDs before marking implementation tasks complete; never silently bind a
generic symbol to one footprint.
