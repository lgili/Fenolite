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

The names below are *target slots*. The 14 entries marked `existing` and 86 entries marked
`shipped as` are available; none remain `planned`. A provisional name is not a final lib ID:
the exact manufacturer's body, pitch, lead span, exposed pad and mounting variant must be chosen
from an official drawing first. If two slots resolve to the same lands, keep one definition and
replace the duplicate slot so the final catalog still contains 100 distinct patterns.

## Inventory

| # | Target slot | Family | State |
|---:|---|---|---|
| 1 | `Chip_0201` | Chip passives / MELF | shipped as `Chip_0201_Vishay_Draloric` |
| 2 | `Chip_0402` | Chip passives / MELF | existing |
| 3 | `Chip_0603` | Chip passives / MELF | existing |
| 4 | `Chip_0805` | Chip passives / MELF | existing |
| 5 | `Chip_1206` | Chip passives / MELF | existing |
| 6 | `Chip_1210` | Chip passives / MELF | shipped as `Chip_1210_Vishay_Draloric` |
| 7 | `Chip_1812` | Chip passives / MELF | shipped as `Chip_1812_TDK_CGA8` |
| 8 | `Chip_2010` | Chip passives / MELF | shipped as `Chip_2010_Vishay_RCWP` |
| 9 | `Chip_2512` | Chip passives / MELF | shipped as `Chip_2512_Vishay_RCWP` |
| 10 | `MELF_0102` | Chip passives / MELF | shipped as `MELF_0102_Vishay_MMU` |
| 11 | `DO214AC` | Diodes, transistors and power discretes | existing |
| 12 | `DO214AA` | Diodes, transistors and power discretes | shipped as `DO214AA_Diodes_SMB` |
| 13 | `DO214AB` | Diodes, transistors and power discretes | shipped as `DO214AB_Diodes_SMC` |
| 14 | `SOD123` | Diodes, transistors and power discretes | shipped as `SOD123_Diodes` |
| 15 | `SOD123F` | Diodes, transistors and power discretes | shipped as `SOD123F_Diodes_Standard` |
| 16 | `SOD323` | Diodes, transistors and power discretes | shipped as `SOD323_Diodes` |
| 17 | `SOD523` | Diodes, transistors and power discretes | shipped as `SOD523_Diodes` |
| 18 | `SOD128` | Diodes, transistors and power discretes | shipped as `SOD128_Nexperia_CFP5` |
| 19 | `DO35_P10.16` | Diodes, transistors and power discretes | shipped as `DO35_P10.16_Diodes` |
| 20 | `DO41_P10.16` | Diodes, transistors and power discretes | shipped as `DO41_P10.16_Diodes` |
| 21 | `SOT23_3` | Diodes, transistors and power discretes | existing |
| 22 | `SOT23_5` | Diodes, transistors and power discretes | existing |
| 23 | `SOT23_6` | Diodes, transistors and power discretes | shipped as `SOT23_6_TI_DBV0006A` |
| 24 | `SOT89_3` | Diodes, transistors and power discretes | existing |
| 25 | `SOT143_4` | Diodes, transistors and power discretes | shipped as `SOT143_4_Diodes` |
| 26 | `SOT223_3` | Diodes, transistors and power discretes | shipped as `SOT223_3_Diodes` |
| 27 | `SOT323_3` | Diodes, transistors and power discretes | shipped as `SOT323_3_Diodes_Standard` |
| 28 | `SOT523_3` | Diodes, transistors and power discretes | shipped as `SOT523_3_Diodes` |
| 29 | `SOT563_6` | Diodes, transistors and power discretes | shipped as `SOT563_6_Diodes` |
| 30 | `SOT883_3` | Diodes, transistors and power discretes | shipped as `SOT883_3_Nexperia_DFN1006` |
| 31 | `SC70_5` | Diodes, transistors and power discretes | existing |
| 32 | `SC70_6` | Diodes, transistors and power discretes | shipped as `SC70_6_TI_DCK0006A` |
| 33 | `TO252_3` | Diodes, transistors and power discretes | shipped as `TO252_3_Diodes_Standard` |
| 34 | `TO263_3` | Diodes, transistors and power discretes | shipped as `TO263_3_Diodes_Standard` |
| 35 | `TO220_3` | Diodes, transistors and power discretes | shipped as `TO220_3_Diodes_Vertical` |
| 36 | `SOIC_8` | Integrated circuits | existing |
| 37 | `SOIC_14` | Integrated circuits | shipped as `SOIC14_TI_D0014A` |
| 38 | `SOIC_16` | Integrated circuits | shipped as `SOIC16_TI_D0016A` |
| 39 | `SOIC_20` | Integrated circuits | shipped as `SOIC20_TI_DW0020A` |
| 40 | `SOIC_24` | Integrated circuits | shipped as `SOIC24_Microchip_K3X` |
| 41 | `SOIC_28` | Integrated circuits | shipped as `SOIC28_MPS_Wide` |
| 42 | `TSSOP_8` | Integrated circuits | shipped as `TSSOP8_Diodes` |
| 43 | `TSSOP_14` | Integrated circuits | shipped as `TSSOP14_Diodes` |
| 44 | `TSSOP_16` | Integrated circuits | shipped as `TSSOP16_Diodes_A1` |
| 45 | `TSSOP_20` | Integrated circuits | shipped as `TSSOP20_Diodes` |
| 46 | `TSSOP_24` | Integrated circuits | shipped as `TSSOP24_TI_PW0024A` |
| 47 | `TSSOP_28` | Integrated circuits | shipped as `TSSOP28_Microchip_NRB` |
| 48 | `MSOP_8` | Integrated circuits | shipped as `MSOP8_Diodes` |
| 49 | `MSOP_10` | Integrated circuits | shipped as `MSOP10_Diodes` |
| 50 | `SSOP_16` | Integrated circuits | shipped as `SSOP16_Diodes_CJ` |
| 51 | `QFN_16` | Integrated circuits | shipped as `QFN16_Diodes_W3030_A1` |
| 52 | `QFN_20` | Integrated circuits | shipped as `QFN20_Diodes_U4040` |
| 53 | `QFN_24` | Integrated circuits | shipped as `QFN24_Diodes_W4040_SWP_A1` |
| 54 | `QFN_28` | Integrated circuits | shipped as `QFN28_Diodes_W5050_A1` |
| 55 | `QFN_32` | Integrated circuits | shipped as `QFN32_Diodes_W5050` |
| 56 | `QFN_48` | Integrated circuits | shipped as `QFN48_TI_RGZ0048A` |
| 57 | `DFN_6` | Integrated circuits | shipped as `DFN6_Diodes_W2020_US` |
| 58 | `DFN_8` | Integrated circuits | shipped as `DFN8_Diodes_W3030_UXF` |
| 59 | `LQFP32_P0.8` | Integrated circuits | existing |
| 60 | `LQFP_44` | Integrated circuits | shipped as `TQFP44_Microchip_PT` |
| 61 | `LQFP_48` | Integrated circuits | shipped as `LQFP48_TI_PT0048A` |
| 62 | `LQFP_64` | Integrated circuits | shipped as `LQFP64_TI_PM0064A` |
| 63 | `LQFP_100` | Integrated circuits | shipped as `LQFP100_TI_PZ0100A` |
| 64 | `DIP_4` | Integrated circuits | shipped as `DIP4_Vishay_VO617A` |
| 65 | `DIP_6` | Integrated circuits | shipped as `DIP6_Vishay_CNY17` |
| 66 | `DIP_8` | Integrated circuits | shipped as `DIP8_Microchip_P` |
| 67 | `DIP_14` | Integrated circuits | shipped as `DIP14_Microchip_P` |
| 68 | `DIP_16` | Integrated circuits | shipped as `DIP16_Microchip_P` |
| 69 | `DIP_20` | Integrated circuits | shipped as `DIP20_Microchip_P` |
| 70 | `DIP_28` | Integrated circuits | shipped as `DIP28_Microchip_SP` |
| 71 | `Header_1x2_P2.5` | Board connectors | existing |
| 72 | `Header_1x3_P2.5` | Board connectors | existing |
| 73 | `Header_1x4_P2.5` | Board connectors | existing |
| 74 | `Header_1x1_P2.54` | Board connectors | shipped as `Header_1x1_P2.54` |
| 75 | `Header_1x2_P2.54` | Board connectors | shipped as `Header_1x2_P2.54` |
| 76 | `Header_1x3_P2.54` | Board connectors | shipped as `Header_1x3_P2.54` |
| 77 | `Header_1x4_P2.54` | Board connectors | shipped as `Header_1x4_P2.54` |
| 78 | `Header_1x6_P2.54` | Board connectors | shipped as `Header_1x6_P2.54` |
| 79 | `Header_1x8_P2.54` | Board connectors | shipped as `Header_1x8_P2.54` |
| 80 | `Header_1x10_P2.54` | Board connectors | shipped as `Header_1x10_P2.54` |
| 81 | `Header_2x3_P2.54` | Board connectors | shipped as `Header_2x3_P2.54` |
| 82 | `Header_2x5_P2.54` | Board connectors | shipped as `Header_2x5_P2.54` |
| 83 | `JST_XH_1x2_P2.5` | Board connectors | shipped as `JST_XH_B2B_XH_A` |
| 84 | `JST_XH_1x4_P2.5` | Board connectors | shipped as `JST_XH_B4B_XH_A` |
| 85 | `Amphenol_10118192_MicroB` | Board connectors | shipped as `MicroUSB_B_Wurth_629105150521` |
| 86 | `LED_0603` | LEDs, switches, THT passives and mechanics | shipped as `LED0603_Kingbright_APT1608SURCK` |
| 87 | `LED_0805` | LEDs, switches, THT passives and mechanics | shipped as `LED0805_Kingbright_APT2012SURCK` |
| 88 | `SW_Tact_SMD_4.5x4.5` | LEDs, switches, THT passives and mechanics | shipped as `SW_Tact_Wurth_430181038816` |
| 89 | `SW_Tact_THT_6x6` | LEDs, switches, THT passives and mechanics | shipped as `SW_Tact_Wurth_430186043716` |
| 90 | `R_Axial_P7.62` | LEDs, switches, THT passives and mechanics | shipped as `R_Axial_Vishay_MRS16_P7.62` |
| 91 | `R_Axial_P10.16` | LEDs, switches, THT passives and mechanics | shipped as `R_Axial_Vishay_MRS25_P10.16` |
| 92 | `C_Radial_P2.5` | LEDs, switches, THT passives and mechanics | shipped as `C_Film_Wima_MKS02_L4.6_W2.5_P2.5` |
| 93 | `C_Radial_P5.0` | LEDs, switches, THT passives and mechanics | shipped as `C_Film_Wima_MKS2_L7.2_W2.5_P5` |
| 94 | `C_Electrolytic_D5_P2` | LEDs, switches, THT passives and mechanics | shipped as `C_Electrolytic_Panasonic_FR_D5_P2` |
| 95 | `C_Electrolytic_D6.3_P2.5` | LEDs, switches, THT passives and mechanics | shipped as `C_Electrolytic_Panasonic_FR_D6.3_P2.5` |
| 96 | `MountingHole_M2` | LEDs, switches, THT passives and mechanics | shipped as `MountingHole_M2_D2.4` |
| 97 | `MountingHole_M3` | LEDs, switches, THT passives and mechanics | shipped as `MountingHole_M3_D3.4` |
| 98 | `TestPoint_SMD_D1.0` | LEDs, switches, THT passives and mechanics | shipped as `TestPoint_SMD_D1.0` |
| 99 | `Crystal_3225_4Pad` | LEDs, switches, THT passives and mechanics | shipped as `Crystal_3225_Abracon_ABM8` |
| 100 | `LED_PLCC4_5050` | LEDs, switches, THT passives and mechanics | shipped as `LED5050_Worldsemi_WS2812B_V6` |

## Completion gate

For each planned slot, record an official package and suggested-land drawing in
`docs/evidence/sources.md` and map the final ID in `docs/catalog/sources.md`. Check pin numbering,
pad shape and separation, paste/mask openings, holes and tabs, body/courtyard/silkscreen layers,
write/readback, offline discovery and a visual preview. Keep any independently authored land
`INFERRED` where the source lacks a recommendation. Replace provisional names with sourced
variant-qualified IDs before marking implementation tasks complete; never silently bind a
generic symbol to one footprint.

The micro-B slot resolves to Würth 629105150521 (S-0411): its official drawing could be read and visually checked, while the initial Amphenol drawing was inaccessible. This is a different physical part, not an Amphenol-compatible alias.
