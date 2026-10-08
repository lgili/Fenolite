# Catalog coverage matrix

This matrix tracks reusable generic definitions, not part-number coverage. Symbol pin labels and
numbers describe conceptual roles; they are not a package pinout for a purchasable device. A part
must name its footprint explicitly and use a device-specific symbol/pin map where its datasheet
requires one.

## Symbol families

| Family | Built-in symbols | Status | Limits |
|---|---|---|---|
| Passive: resistors, ceramic/electrolytic/film capacitors, inductors and ferrite beads | `Resistor`, `Capacitor`, `Capacitor_Ceramic`, `Capacitor_Electrolytic`, `Capacitor_Film`, `Capacitor_Polarized`, `Inductor`, `Ferrite_Bead` | covered | Generic schematic roles; no electrical value, rating or MPN is implied. |
| Discrete semiconductors: diode, Zener, LED and bridge rectifier | `Diode`, `Zener_Diode`, `LED`, `Bridge_Rectifier` | covered | Bridge terminal names are conceptual; check the selected device datasheet. |
| Optoelectronic isolation | `Optocoupler` | covered | The four pins describe a generic LED/photodetector block, not an exact optocoupler pinout or isolation rating. |
| Protection: fuse, varistor and surge suppressor | `Fuse`, `Varistor`, `Surge_Suppressor` | covered | Ratings, trip curves, polarity and certification are device-specific. |
| Power/control ICs: analog amplifier, comparator, linear regulator, offline power controller, MCU and power module | `Operational_Amplifier`, `Comparator`, `Linear_Regulator`, `Offline_Power_Controller`, `Microcontroller`, `Power_Module` | covered | Block pins are role labels only; exact pin maps must come from the selected part's public datasheet or a project-authored symbol. |
| Electromechanical: connectors and single-circuit terminals | `Connector_2`, `Connector_3`, `Connector_4`, `Terminal_1Pin` | covered | Symbol count does not select a connector series, pitch or mating part. |
| Two-winding common-mode choke | `Common_Mode_Choke` | covered | Conceptual winding terminals only; coupling, current and insulation are part-specific. |
| Two-electrode gas discharge tube | `Gas_Discharge_Tube` | covered | Bidirectional non-polar symbol; sparkover ratings and package remain part-specific. |
| Common-cathode dual LED | `Dual_LED_Common_Cathode` | covered | Two anodes share a cathode in this variant only; no physical pinout or color is implied. |

| Additional semiconductors and protection | `BJT_NPN`, `BJT_PNP`, `MOSFET_N_Channel`, `MOSFET_P_Channel`, `IGBT`, `SCR`, `TRIAC`, `Schottky_Diode`, `TVS_Bidirectional` | covered | Conceptual terminal roles; see [20-symbol inventory](target-20-symbols.md) for functional sources and package-mapping limits. |

| Additional passive, contact and photodetector families | `Potentiometer`, `Thermistor_NTC`, `Thermistor_PTC`, `Crystal`, `Switch_SPST`, `Switch_SPDT`, `Pushbutton_NO`, `Relay_SPDT`, `Transformer`, `Photodiode`, `Phototransistor` | covered | Resting contacts, conceptual winding/pin roles and incident-light motifs; no implied device or footprint. |

## Reusable package styles

The c0076 change now has a [100-variant footprint target](target-100-footprints.md) selected
from a fixed public-board usage proxy and official package-family sources. The table below lists
100 currently shipped definitions; every target slot is resolved.

The [first seven new footprints](previews/c0076-first-seven.svg) are drawn from the catalog
geometry for visual review (orange copper, blue fabrication body and dashed green courtyard).
The [next seven](previews/c0076-next-seven.svg) and
[current complete gallery](previews/c0076-current-gallery.svg) use the same colors. Regenerate
the complete gallery with `uv run python tools/catalog/render_footprints.py
docs/catalog/previews/c0076-current-gallery.svg`.
The [three compact SOT variants](previews/c0076-three-compact-sot.svg) have a focused sheet.
The [five SOIC variants](previews/c0076-five-soic.svg) and
[nine fine-pitch small-outline variants](previews/c0076-nine-small-outline.svg) have focused sheets. The [five QFN variants](previews/c0076-five-qfn.svg) show gray paste windows over orange copper. The [seven additional IC variants](previews/c0076-seven-more-ic.svg) have their own sheet. The [seven DIP variants](previews/c0076-seven-dip.svg) show the through-hole group.
The [six additional discrete patterns](previews/c0076-six-discretes.svg) and
[final three discrete variants](previews/c0076-final-three-discretes.svg) have focused review sheets.

| Package style | Built-in footprint IDs | Evidence | Scope or limitation |
|---|---|---|---|
| Two-terminal chip passive, 0402 through 1206 | `Chip_0402`, `Chip_0603`, `Chip_0805`, `Chip_1206` | `INFERRED` generic use | Rectangular lands follow a Vishay reflow resistor example; other component families and assembly processes need their own review. |
| Additional Vishay chip resistor and MELF variants | `Chip_0201_Vishay_Draloric`, `Chip_1210_Vishay_Draloric`, `Chip_2010_Vishay_RCWP`, `Chip_2512_Vishay_RCWP`, `MELF_0102_Vishay_MMU` | `INFERRED` rectangular corners and implementation | Dimensions follow source-specific recommended resistor lands; the qualified IDs do not imply suitability for unrelated passives. |
| TDK 1812 MLCC | `Chip_1812_TDK_CGA8` | `INFERRED` selected range midpoint | TDK recommends ranges for gap, pad length and width; the catalog uses their midpoints for this named capacitor family. |
| Small-outline 3/5 lead and 8 lead | `SOT23_3`, `SOT23_5`, `SC70_5`, `SOT89_3`, `SOIC_8` | `INFERRED` corner/variant details | Rectangular pad size, pitch and top-view numbering follow official package examples; check the selected package variant and assembly process. |
| Six-lead TI small-outline variants | `SOT23_6_TI_DBV0006A`, `SC70_6_TI_DCK0006A` | `INFERRED` rectangular corner detail | Pads use the respective TI package land example and 1–3/6–4 top-view sequence. |
| Diodes compact transistor packages | `SOT323_3_Diodes_Standard`, `SOT523_3_Diodes`, `SOT563_6_Diodes` | `INFERRED` body and corner details | Suggested lands set pad dimensions and pitch; package-specific pin maps still need the selected device datasheet. |
| Additional discrete and power lands | `SOT143_4_Diodes`, `SOT223_3_Diodes`, `TO252_3_Diodes_Standard`, `TO263_3_Diodes_Standard`, `DO35_P10.16_Diodes`, `DO41_P10.16_Diodes` | `INFERRED` | Diodes package layouts support SMD pad sizes and spacing. The axial diode bend pitch, holes and lands are authored starting values based on lead diameter, not manufacturer recommended patterns. Tab connection and exact pinout require the chosen device. |
| Final discrete variants | `SOD128_Nexperia_CFP5`, `SOT883_3_Nexperia_DFN1006`, `TO220_3_Diodes_Vertical` | `INFERRED` | SOD128 uses Nexperia copper lands and manufacturer pin 1 at the cathode; with an anode-first generic diode symbol a build applies the pin-to-pad map `{"1": "2", "2": "1"}` by default and warns (`build.pad-map-default`), and an explicit `pad_map` wins (change c0147). SOT883 uses a rotated three-land Nexperia layout. TO220 vertical drill, pad and board projection are authored from package lead dimensions. |
| Surface-mount diode | `DO214AC` | source reference land; still `INFERRED` for Fenolite's implementation | The cited manufacturer calls its layout suggested/reference only. Verify against the selected diode and process. |
| Additional Diodes SMB/SMC and small-outline diodes | `DO214AA_Diodes_SMB`, `DO214AB_Diodes_SMC`, `SOD123_Diodes`, `SOD123F_Diodes_Standard`, `SOD323_Diodes`, `SOD523_Diodes` | `INFERRED` from suggested lands | Source drawings set nominal copper geometry; Fenolite's pad 1 is the anode and pad 2 and the right fabrication mark denote the cathode, matching its generic diode symbol. |
| SOIC 14/16/20/24/28 | `SOIC14_TI_D0014A`, `SOIC16_TI_D0016A`, `SOIC20_TI_DW0020A`, `SOIC24_Microchip_K3X`, `SOIC28_MPS_Wide` | `INFERRED` rectangular-corner implementation | Narrow and wide variants use their named manufacturers’ recommended pad size, 1.27 mm pitch and row spacing. Body dimensions match the selected package outline. |
| DIP 4/6/8/14/16/20/28 | `DIP4_Vishay_VO617A`, `DIP6_Vishay_CNY17`, `DIP8_Microchip_P`, `DIP14_Microchip_P`, `DIP16_Microchip_P`, `DIP20_Microchip_P`, `DIP28_Microchip_SP` | `INFERRED` holes and rings | Published body bounds and lead pitch; explicit authored 7.62 mm rows, 0.90 mm drill and 1.80 mm lands. |
| Additional leadless and quad ICs | `QFN48_TI_RGZ0048A`, `DFN6_Diodes_W2020_US`, `DFN8_Diodes_W3030_UXF`, `TQFP44_Microchip_PT`, `LQFP48_TI_PT0048A`, `LQFP64_TI_PM0064A`, `LQFP100_TI_PZ0100A` | `INFERRED` process/corner choices | Explicit EP mapping for leadless variants; manufacturer-specific stencil and rotated quad-side pads. |
| QFN with exposed copper | `QFN16_Diodes_W3030_A1`, `QFN20_Diodes_U4040`, `QFN24_Diodes_W4040_SWP_A1`, `QFN28_Diodes_W5050_A1`, `QFN32_Diodes_W5050` | `INFERRED` stencil and assembly choices | Official body and copper lands; explicit EP mapping, four paste windows, no automatic thermal vias. |
| Fine-pitch small-outline ICs | `TSSOP8_Diodes`, `TSSOP14_Diodes`, `TSSOP16_Diodes_A1`, `TSSOP20_Diodes`, `TSSOP24_TI_PW0024A`, `TSSOP28_Microchip_NRB`, `MSOP8_Diodes`, `MSOP10_Diodes`, `SSOP16_Diodes_CJ` | `INFERRED` rectangular-corner implementation | Official drawings distinguish pitch, overall span and pad-row centers; bodies and lands resolve to these exact manufacturer variants. |
| Leaded IC | `LQFP32_P0.8` | `INFERRED` corner/variant details | TI VF0032A example sets four-side numbering and perpendicular pad axes; not a pin-compatible symbol or approved package for every 32-pin IC. |
| Single-row through-hole header, 2.5 mm pitch | `Header_1x2_P2.5`, `Header_1x3_P2.5`, `Header_1x4_P2.5` | `INFERRED` lands | Pitch is supported by a public connector drawing. Hole and pad sizes are Fenolite starting values; check the selected terminal. |

## Project-authored or separately specified geometry

The current model can describe many custom footprints, but the generic catalog does not guess a
physical pattern when public evidence does not define a reusable package. Create a project-authored
definition or a separately sourced catalog entry for:

- power modules with vendor-specific pin grids, exposed plates, slots, mounting holes or thermal
  interfaces;
- connector families whose shrouds, stakes, locating pegs, board locks, pitch or mating geometry
  differ from the generic 2.5 mm single-row header;
- ring terminals, quick-connect tabs and fuse holders, whose formed/mechanical interfaces and
  mounting dimensions are product-specific;
- radial electrolytic and film capacitors, radial MOVs, axial parts and custom chokes when a
  specific body, lead spacing or mounting form is required;
- optocoupler surface-mount variants with a specified creepage/clearance or lead-form requirement.

These limitations are about choosing a sufficiently evidenced reusable geometry. They do not mean
that the DSL cannot author a one-off footprint. The catalog makes no safety, thermal, interchange-
ability, assembly or fabrication qualification claim.

## C0076 connector expansion

- `Header_1x1_P2.54`: generic single row.
- `Header_1x2_P2.54`: generic single row.
- `Header_1x3_P2.54`: generic single row.
- `Header_1x4_P2.54`: generic single row.
- `Header_1x6_P2.54`: generic single row.
- `Header_1x8_P2.54`: generic single row.
- `Header_1x10_P2.54`: generic single row.
- `Header_2x3_P2.54`: generic paired rows.
- `Header_2x5_P2.54`: generic paired rows.
- `JST_XH_B2B_XH_A`: exact bossless housing.
- `JST_XH_B4B_XH_A`: exact bossless housing.
- `MicroUSB_B_Wurth_629105150521`: mixed SMD contacts, four shell slots and two NPTH pegs.

## C0076 passive and crystal expansion

- `LED0603_Kingbright_APT1608SURCK`: Kingbright APT1608SURCK LED suggested land, pin 1 cathode.
- `LED0805_Kingbright_APT2012SURCK`: Kingbright APT2012SURCK LED suggested land, pin 1 cathode.
  - Both LED lands use the manufacturer's numbering, pad 1 at the cathode, while the generic LED symbol has pin 1 anode. A part without a `pad_map` gets the pin-to-pad map `{"1": "2", "2": "1"}` by default, as on `SOD128_Nexperia_CFP5`, and the build warns with `build.pad-map-default`; write `Part("D1", "Fenolite:LED", footprint=..., pad_map={"1": "2", "2": "1"})` to silence it. An explicit `pad_map` always wins (change c0147).
- `R_Axial_Vishay_MRS16_P7.62`: Vishay MRS16 with inferred 7.62 mm formed-lead pitch.
- `R_Axial_Vishay_MRS25_P10.16`: Vishay MRS25 with inferred 10.16 mm formed-lead pitch.
- `C_Film_Wima_MKS02_L4.6_W2.5_P2.5`: Wima MKS02 4.6 by 2.5 mm nominal body, 2.5 mm lead pitch.
- `C_Film_Wima_MKS2_L7.2_W2.5_P5`: Wima MKS2 7.2 by 2.5 mm nominal body, 5 mm lead pitch.
- `Crystal_3225_Abracon_ABM8`: Abracon ABM8 four-pad crystal suggested land.

## C0076 final mechanical and electromechanical expansion

- `SW_Tact_Wurth_430181038816`: Wurth 4.5 mm SMT tact switch, terminals 1-2 and 3-4 internally common.
- `SW_Tact_Wurth_430186043716`: Wurth 6 mm THT tact switch, terminals 1-3 and 2-4 internally common.
- `C_Electrolytic_Panasonic_FR_D5_P2`: Panasonic FR 5 mm nominal body and 2 mm straight-lead pitch, pad 1 positive.
- `C_Electrolytic_Panasonic_FR_D6.3_P2.5`: Panasonic FR 6.3 mm nominal body and 2.5 mm straight-lead pitch, pad 1 positive.
- `MountingHole_M2_D2.4`: Generic non-plated 2.4 mm M2 clearance hole with inferred 5 mm hardware guide.
- `MountingHole_M3_D3.4`: Generic non-plated 3.4 mm M3 clearance hole with inferred 7 mm hardware guide.
- `TestPoint_SMD_D1.0`: Generic 1 mm circular exposed test pad without solder paste.
- `LED5050_Worldsemi_WS2812B_V6`: Worldsemi WS2812B-V6 four-terminal addressable LED, manufacturer suggested lands.
