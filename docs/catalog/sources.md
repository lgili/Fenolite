# Catalog evidence map

| Catalog entries | Evidence | Sources | Facts supported |
|---|---|---|---|
| `Fenolite:Resistor` | `INFERRED` | S-0314, S-0343 | The resistor family and zigzag schematic convention; vertices and pin coordinates are authored by Fenolite. |
| `Fenolite:Capacitor`, `Fenolite:Capacitor_Polarized`, `Fenolite:Inductor` | `INFERRED` | S-0314 | The component kinds and existence of common schematic symbol examples; vector shapes and pin coordinates are authored by Fenolite. |
| `Fenolite:Chip_0402`, `Fenolite:Chip_0603`, `Fenolite:Chip_0805`, `Fenolite:Chip_1206` | `INFERRED` | S-0315, S-0333 | Yageo RC_L body sizes and Vishay document 28950 IPC-7351 reflow resistor/fuse land examples. The generic chip family is not a claim that the same lands fit every capacitor or bead. |
| `Fenolite:Chip_0201_Vishay_Draloric`, `Fenolite:Chip_1210_Vishay_Draloric` | `INFERRED` | S-0333 | Vishay document 28950 IPC-7351 reflow resistor/fuse G/Y/X/Z dimensions for 0201 and 1210. Fenolite uses rectangular pads and nominal body guides; suitability for another manufacturer's chip is unverified. |
| `Fenolite:Chip_2010_Vishay_RCWP`, `Fenolite:Chip_2512_Vishay_RCWP` | `INFERRED` | S-0353, S-0357 | Vishay RCWP nominal body dimensions and recommended A/B/C/D pad dimensions; Fenolite authors rectangular copper from the listed numbers. |
| `Fenolite:MELF_0102_Vishay_MMU` | `INFERRED` | S-0333, S-0354 | Vishay MMU 0102 cylindrical body and IPC-7351 reflow G/Y/X/Z dimensions. Rectangular board lands and body guide remain Fenolite-authored. |
| `Fenolite:Chip_1812_TDK_CGA8` | `INFERRED` | S-0358 | TDK CGA8 body and recommended reflow A/B/C ranges; Fenolite uses the midpoints (3.40 mm gap, 1.30 mm pad length, 2.80 mm pad width). |
| `Fenolite:Ferrite_Bead` | `INFERRED` | S-0318 | Ferrite/chip bead is a common two-terminal noise-suppression component; the generic symbol is Fenolite-authored. |
| `Fenolite:Diode`, `Fenolite:LED` | `INFERRED` | S-0319 | Diode and LED categories and symbol relationships; Fenolite-authored generic vector graphics. |
| `Fenolite:Zener_Diode` | `INFERRED` | S-0319, S-0344 | The Zener family and bent-cathode convention; Fenolite-authored continuous cathode geometry. |
| `Fenolite:Bridge_Rectifier` | `INFERRED` | S-0329, S-0342 | Bridge rectifiers are a distinct four-terminal family; the four-diode topology is sourced, while all vector geometry is Fenolite-authored. |
| `Fenolite:Capacitor_Ceramic` | `INFERRED` | S-0328 | Ceramic/MLCC capacitor product family; generic symbol geometry is Fenolite-authored. |
| `Fenolite:Capacitor_Electrolytic` | `INFERRED` | S-0329 | Aluminum electrolytic capacitor product family; the generic symbol does not assert specific construction or ratings. |
| `Fenolite:Capacitor_Film` | `INFERRED` | S-0328 | Film capacitor product family; the generic symbol does not assert specific construction or ratings. |
| `Fenolite:Varistor`, `Fenolite:Surge_Suppressor` | `INFERRED` | S-0320 | MOV/varistor surge-suppression family; no rating or connection selection is implied. |
| `Fenolite:Optocoupler` | `INFERRED` | S-0325 | A public photocoupler example uses an LED and phototransistor; Fenolite's generic block is not the example's pinout. |
| `Fenolite:Fuse` | `INFERRED` | S-0326 | Fuse families provide overcurrent protection; no rating, package or trip characteristic is implied. |
| `Fenolite:Operational_Amplifier`, `Fenolite:Comparator`, `Fenolite:Linear_Regulator`, `Fenolite:Offline_Power_Controller`, `Fenolite:Microcontroller`, `Fenolite:Power_Module` | `INFERRED` | S-0316, S-0317, S-0341 | Public component categories and op-amp input signs; Fenolite's generic role-labelled symbols do not claim exact electrical pin numbers. |
| `Fenolite:Connector_2`, `Fenolite:Connector_3`, `Fenolite:Connector_4`, `Fenolite:Terminal_1Pin` | `INFERRED` | S-0324 | Generic circuit terminals and a public 2.5 mm-pitch connector family exist; the symbols do not assert the cited connector series. |
| `Fenolite:Common_Mode_Choke` | `INFERRED` | S-0345 | TDK's public example supports two separate coupled windings; Fenolite graphics and generic numbering are independent. |
| `Fenolite:Gas_Discharge_Tube` | `INFERRED` | S-0346 | Bourns' two-electrode tube is bidirectional and non-polar; Fenolite's generic symbol has no device rating. |
| `Fenolite:Dual_LED_Common_Cathode` | `INFERRED` | S-0347 | Kingbright's public example supports two anodes with one shared cathode; Fenolite's symbolic numbers are not the product's pinout. |
| `Fenolite:SOT23_3` | `INFERRED` | S-0322, S-0334 | Nexperia body outline; TI DBZ0003A top-view land example and pin sequence. Rectangular pads approximate the source's 0.05 mm corner radius. |
| `Fenolite:SOT23_5`, `Fenolite:SC70_5` | `INFERRED` | S-0323, S-0335 | TI DBV0005A and DCK0005A land examples give 1/2/3 left and 5/4 right, horizontal pad axes and non-touching pin pitch. Rectangular pads omit the 0.05 mm corner radius. |
| `Fenolite:SOT23_6_TI_DBV0006A`, `Fenolite:SC70_6_TI_DCK0006A` | `INFERRED` | S-0355, S-0356 | TI's respective six-pad package examples give horizontal pad axes, pitch and row spacing, with 1/2/3 left and 6/5/4 right. Rectangular corners omit the example's 0.05 mm radius. |
| `Fenolite:SOT323_3_Diodes_Standard`, `Fenolite:SOT523_3_Diodes`, `Fenolite:SOT563_6_Diodes` | `INFERRED` | S-0447, S-0448, S-0449 | Diodes' package documents provide pad length, width, pitch and opposing-row spacing. Fenolite rotates the three-pad layout to the same 1/2-left and 3-right convention used by its other three-lead footprints. |
| `Fenolite:SOT143_4_Diodes` | `INFERRED` | S-0369 | Diodes SOT143 suggested pad layout sets the asymmetric large lead, opposing-row centers and overall span. Fenolite approximates the three small-pad widths; the public outline supplies top-view 1–4 numbering. |
| `Fenolite:SOT223_3_Diodes` | `INFERRED` | S-0372 | Diodes SOT223-3 suggested rectangular lands supply 1.20/3.50 mm pad widths, 1.40 mm pad height, 2.30 mm lead offset and 3.10 mm row offset. |
| `Fenolite:TO252_3_Diodes_Standard`, `Fenolite:TO263_3_Diodes_Standard` | `INFERRED` | S-0373, S-0374 | Diodes standard package drawings supply the two lead lands and large tab land. Pad 2 denotes the tab; check the selected device pinout. |
| `Fenolite:DO35_P10.16_Diodes`, `Fenolite:DO41_P10.16_Diodes` | `INFERRED` | S-0370, S-0371 | Diodes package drawings supply body and lead diameters; Fenolite independently chooses 10.16 mm bending pitch, drill and annular land. Pad 1 is anode, pad 2 and the right body mark denote cathode. |
| `Fenolite:SOD128_Nexperia_CFP5` | `INFERRED` | S-0375 | Nexperia reflow drawing supplies 1.40 by 2.10 mm copper lands on 4.40 mm centers, with cathode-marked manufacturer terminal 1 at left. This differs from the generic Fenolite diode symbol’s pin 1 anode; use explicit pin-to-pad mapping. |
| `Fenolite:SOT883_3_Nexperia_DFN1006` | `INFERRED` | S-0376 | Nexperia DFN1006-3 reflow copper is 0.40 by 0.25 mm for the small pads, 0.40 by 0.70 mm for the large pad, on 0.70 mm row centers; Fenolite orients the large pad right and mirrors the bottom-view numbering for a PCB top view. |
| `Fenolite:TO220_3_Diodes_Vertical` | `INFERRED` | S-0377 | Diodes TO220-3 outline supplies the 10.70 mm maximum width, 4.85 mm maximum thickness and lead dimensions. Fenolite authors 5.08 mm outer-pad pitch, 1.50 mm drill, 2.20 mm lands and a 3.50 mm body offset for a vertical mounting option. |
| `Fenolite:SOT89_3` | `INFERRED` | S-0322, S-0338 | Diodes SOT89 reference T-shaped pad 2 is modelled as two overlapping same-number rectangles; pads 1 and 3 remain isolated. |
| `Fenolite:SOIC14_TI_D0014A`, `Fenolite:SOIC16_TI_D0016A` | `INFERRED` | S-0378, S-0379 | TI narrow SOIC land examples have 1.55 by 0.60 mm pads, 1.27 mm pitch and 5.40 mm opposing-row centers; Fenolite uses rectangular corners. |
| `Fenolite:SOIC20_TI_DW0020A` | `INFERRED` | S-0380 | TI wide SOIC-20 example has 2.00 by 0.60 mm pads, 1.27 mm pitch and 9.30 mm opposing-row centers. |
| `Fenolite:SOIC24_Microchip_K3X`, `Fenolite:SOIC28_MPS_Wide` | `INFERRED` | S-0381, S-0382 | Microchip and MPS wide SOIC recommended patterns use 9.40 mm row centers and 1.27 mm pitch; respective pads are 2.00 by 0.60 and 2.00 by 0.61 mm. |
| `Fenolite:TSSOP8_Diodes` | `INFERRED` | S-0383 | TSSOP8 copper 1.78 by 0.45 mm, 0.65 mm pitch, 7.72 mm overall span and 4.16 mm inner gap imply 5.94 mm row centers. Top-view counter-clockwise numbering follows the package pin-1 index; rectangular corners and assembly use remain inferred. |
| `Fenolite:TSSOP14_Diodes` | `INFERRED` | S-0384 | TSSOP14 copper 1.45 by 0.45 mm, 0.65 mm pitch, 5.90 mm row centers. Top-view counter-clockwise numbering follows the package pin-1 index; rectangular corners and assembly use remain inferred. |
| `Fenolite:TSSOP16_Diodes_A1` | `INFERRED` | S-0385 | TSSOP16 Type A1 copper 1.40 by 0.35 mm, 0.65 mm pitch, 6.80 mm overall span imply 5.40 mm row centers. Top-view counter-clockwise numbering follows the package pin-1 index; rectangular corners and assembly use remain inferred. |
| `Fenolite:TSSOP20_Diodes` | `INFERRED` | S-0386 | TSSOP20 copper 1.78 by 0.42 mm, 0.65 mm pitch, 7.72 mm overall span imply 5.94 mm row centers. Top-view counter-clockwise numbering follows the package pin-1 index; rectangular corners and assembly use remain inferred. |
| `Fenolite:TSSOP24_TI_PW0024A` | `INFERRED` | S-0387 | PW0024A TSSOP24 copper 1.50 by 0.45 mm, 0.65 mm pitch, 5.80 mm row centers and 7.8 by 4.4 mm body. Top-view counter-clockwise numbering follows the package pin-1 index; rectangular corners and assembly use remain inferred. |
| `Fenolite:TSSOP28_Microchip_NRB` | `INFERRED` | S-0388 | NRB TSSOP28 copper 1.50 by 0.45 mm, 0.65 mm pitch, 5.90 mm row centers and 9.7 by 4.4 mm body. Top-view counter-clockwise numbering follows the package pin-1 index; rectangular corners and assembly use remain inferred. |
| `Fenolite:MSOP8_Diodes` | `INFERRED` | S-0389 | MSOP8 copper 1.35 by 0.45 mm, 0.65 mm pitch, 5.30 mm overall span imply 3.95 mm row centers. Top-view counter-clockwise numbering follows the package pin-1 index; rectangular corners and assembly use remain inferred. |
| `Fenolite:MSOP10_Diodes` | `INFERRED` | S-0390 | MSOP10 copper 1.35 by 0.30 mm, 0.50 mm pitch, 5.30 mm overall span imply 3.95 mm row centers. Top-view counter-clockwise numbering follows the package pin-1 index; rectangular corners and assembly use remain inferred. |
| `Fenolite:SSOP16_Diodes_CJ` | `INFERRED` | S-0391 | SSOP16 Type CJ copper 1.50 by 0.410 mm, 0.635 mm pitch, 6.540 mm overall span and 2.520 mm half-row distance imply 5.040 mm row centers. Top-view counter-clockwise numbering follows the package pin-1 index; rectangular corners and assembly use remain inferred. |
| `Fenolite:QFN16_Diodes_W3030_A1` | `INFERRED` | S-0392, S-0397 | 3.00 mm body and row centers, 0.70 by 0.30 mm lands, 1.70 mm square exposed copper; 0.50 mm pitch. EP is an explicit unnumbered thermal-terminal role requiring device mapping. |
| `Fenolite:QFN20_Diodes_U4040` | `INFERRED` | S-0393, S-0397 | 4.00 mm body, 3.70 mm row centers derived from 4.30 mm outside span, 0.60 by 0.35 mm lands, 2.50 mm square exposed copper; 0.50 mm pitch. EP is an explicit unnumbered thermal-terminal role requiring device mapping. |
| `Fenolite:QFN24_Diodes_W4040_SWP_A1` | `INFERRED` | S-0394, S-0397 | 4.00 mm body, 3.85 mm row centers, 0.75 by 0.30 mm lands, 2.50 mm square exposed copper; 0.50 mm pitch. EP is an explicit unnumbered thermal-terminal role requiring device mapping. |
| `Fenolite:QFN28_Diodes_W5050_A1` | `INFERRED` | S-0395, S-0397 | 5.00 mm body, 4.70 mm row centers, 0.90 by 0.30 mm lands, 3.25 mm square exposed copper; 0.50 mm pitch. EP is an explicit unnumbered thermal-terminal role requiring device mapping. |
| `Fenolite:QFN32_Diodes_W5050` | `INFERRED` | S-0396, S-0397 | 5.00 mm body, 4.70 mm row centers derived from 5.30 mm outside span, 0.60 by 0.35 mm lands, 3.80 mm square exposed copper; 0.50 mm pitch. EP is an explicit unnumbered thermal-terminal role requiring device mapping. |
| `Fenolite:QFN48_TI_RGZ0048A` | `INFERRED` | S-0398, S-0397 | 7 mm body, 0.5 mm pitch, 6.8 mm row centers, 0.60 by 0.24 mm copper and 5.15 mm square exposed copper; sixteen 1.06 mm square stencil windows on 1.26 mm pitch. |
| `Fenolite:DFN6_Diodes_W2020_US` | `INFERRED` | S-0399, S-0397 | 2 mm body, 0.65 mm pitch, 2.35 mm overall land span, 0.545 by 0.350 mm lands and 0.85 by 1.55 mm exposed copper after 90-degree rotation. |
| `Fenolite:DFN8_Diodes_W3030_UXF` | `INFERRED` | S-0400, S-0397 | 3 mm body, 0.65 mm pitch, 3.20 mm overall land span, 0.55 by 0.40 mm lands and 1.75 by 2.35 mm exposed copper after 90-degree rotation. |
| `Fenolite:TQFP44_Microchip_PT` | `INFERRED` | S-0401 | 10 mm body, 0.80 mm pitch, 11.40 mm opposing-row centers and 1.50 by 0.55 mm recommended lands; resolves the QFP44 slot to the thin PT variant. |
| `Fenolite:LQFP48_TI_PT0048A` | `INFERRED` | S-0402 | 7 mm body, 0.50 mm pitch, 8.20 mm opposing-row centers and 1.60 by 0.30 mm lands. |
| `Fenolite:LQFP64_TI_PM0064A` | `INFERRED` | S-0403 | 10 mm body, 0.50 mm pitch, 11.40 mm opposing-row centers and 1.50 by 0.30 mm lands. |
| `Fenolite:LQFP100_TI_PZ0100A` | `INFERRED` | S-0404 | 14 mm body, 0.50 mm pitch, 15.40 mm opposing-row centers and 1.50 by 0.30 mm lands. |
| `Fenolite:DIP4_Vishay_VO617A` | `INFERRED` | S-0405 | Four-lead VO617A through-hole body, 6.5±0.5 by 4.58±0.3 mm and 2.54 mm contact pitch; 7.62 mm hole centers, 0.90 mm drill and 1.80 mm ring are authored choices. |
| `Fenolite:DIP6_Vishay_CNY17` | `INFERRED` | S-0406 | Six-lead CNY17 through-hole body, 6.5±0.5 by 7.3±0.5 mm and 2.54 mm contact pitch; 7.62 mm hole centers, 0.90 mm drill and 1.80 mm ring are authored choices. |
| `Fenolite:DIP8_Microchip_P` | `INFERRED` | S-0407 | 8-lead P/SP body maximum 7.112 by 10.16 mm, 2.54 mm pitch; 7.62 mm hole centers, 0.90 mm drill and 1.80 mm ring are authored choices. |
| `Fenolite:DIP14_Microchip_P` | `INFERRED` | S-0407 | 14-lead P/SP body maximum 7.112 by 19.685 mm, 2.54 mm pitch; 7.62 mm hole centers, 0.90 mm drill and 1.80 mm ring are authored choices. |
| `Fenolite:DIP16_Microchip_P` | `INFERRED` | S-0407 | 16-lead P/SP body maximum 7.112 by 19.685 mm, 2.54 mm pitch; 7.62 mm hole centers, 0.90 mm drill and 1.80 mm ring are authored choices. |
| `Fenolite:DIP20_Microchip_P` | `INFERRED` | S-0407 | 20-lead P/SP body maximum 7.112 by 26.924 mm, 2.54 mm pitch; 7.62 mm hole centers, 0.90 mm drill and 1.80 mm ring are authored choices. |
| `Fenolite:DIP28_Microchip_SP` | `INFERRED` | S-0407 | 28-lead P/SP body maximum 7.493 by 35.56 mm, 2.54 mm pitch; 7.62 mm hole centers, 0.90 mm drill and 1.80 mm ring are authored choices. |
| `Fenolite:SOIC_8` | `INFERRED` | S-0323, S-0336 | TI D0008A example gives horizontal 1.55 by 0.6 mm pads, 1.27 mm pitch, 5.4 mm row spacing and top-view numbering. Rectangular corners are inferred. |
| `Fenolite:DO214AC` | `INFERRED` | S-0321 | Diodes Incorporated package dimensions and a suggested reference land. The source notes land layouts may vary; the catalog still requires process-specific review. |
| `Fenolite:DO214AA_Diodes_SMB`, `Fenolite:DO214AB_Diodes_SMC` | `INFERRED` | S-0359, S-0441, S-0446 | Diodes' SMB/SMC package drawings give suggested rectangular lands; a separate manufacturer source identifies their DO-214AA/AB aliases. |
| `Fenolite:SOD123_Diodes`, `Fenolite:SOD123F_Diodes_Standard`, `Fenolite:SOD323_Diodes`, `Fenolite:SOD523_Diodes` | `INFERRED` | S-0442, S-0443, S-0444, S-0445 | Diodes' package documents give suggested land dimensions. Fenolite derives copper gap from overall span where necessary and uses pad 1 at left for anode and pad 2 at right for cathode, with a matching fabrication-layer mark. |
| `Fenolite:LQFP32_P0.8` | `INFERRED` | S-0327, S-0337 | TI VF0032A example gives 1.5 by 0.55 mm lands, 0.8 mm pitch, 8.4 mm opposing-row center spacing and top-view numbering. Top/bottom pad axes are perpendicular to left/right. Rectangular corners are inferred. |
| `Fenolite:Header_1x2_P2.5`, `Fenolite:Header_1x3_P2.5`, `Fenolite:Header_1x4_P2.5` | `INFERRED` | S-0324 | JST XH public 2.5 mm circuit pitch and board drawing support pitch only; Fenolite-authored hole/pad sizes are not a JST recommended land pattern. |
| `Fenolite:Offline_Power_Controller` | `INFERRED` | S-0316, S-0330 | Offline switcher controllers are a product family; conceptual pin-role labels are not a particular pinout. |
| `Fenolite:Power_Module` | `INFERRED` | S-0316, S-0331 | Intelligent power modules and power integrated modules are distinct families; conceptual block labels do not define a package pin map. |
| `Fenolite:Linear_Regulator` | `INFERRED` | S-0316, S-0332 | Linear/LDO regulator is a product family; conceptual pin-role labels are not a particular part pinout. |
| `Fenolite:Header_1x1_P2.54` | `INFERRED` | S-0408 | Manufacturer pitch and drill facts; independently authored copper/body geometry. |
| `Fenolite:Header_1x2_P2.54` | `INFERRED` | S-0408 | Manufacturer pitch and drill facts; independently authored copper/body geometry. |
| `Fenolite:Header_1x3_P2.54` | `INFERRED` | S-0408 | Manufacturer pitch and drill facts; independently authored copper/body geometry. |
| `Fenolite:Header_1x4_P2.54` | `INFERRED` | S-0408 | Manufacturer pitch and drill facts; independently authored copper/body geometry. |
| `Fenolite:Header_1x6_P2.54` | `INFERRED` | S-0408 | Manufacturer pitch and drill facts; independently authored copper/body geometry. |
| `Fenolite:Header_1x8_P2.54` | `INFERRED` | S-0408 | Manufacturer pitch and drill facts; independently authored copper/body geometry. |
| `Fenolite:Header_1x10_P2.54` | `INFERRED` | S-0408 | Manufacturer pitch and drill facts; independently authored copper/body geometry. |
| `Fenolite:Header_2x3_P2.54` | `INFERRED` | S-0409 | Manufacturer pitch and drill facts; independently authored copper/body geometry. |
| `Fenolite:Header_2x5_P2.54` | `INFERRED` | S-0409 | Manufacturer pitch and drill facts; independently authored copper/body geometry. |
| `Fenolite:JST_XH_B2B_XH_A` | `INFERRED` | S-0410 | Manufacturer pitch and drill facts; independently authored copper/body geometry. |
| `Fenolite:JST_XH_B4B_XH_A` | `INFERRED` | S-0410 | Manufacturer pitch and drill facts; independently authored copper/body geometry. |
| `Fenolite:MicroUSB_B_Wurth_629105150521` | `INFERRED` | S-0411 | Manufacturer pitch and drill facts; independently authored copper/body geometry. |
| `Fenolite:LED0603_Kingbright_APT1608SURCK` | `INFERRED` | S-0412 | Selected physical body and pitch; sourced LED/crystal lands, inferred leaded copper/drill. |
| `Fenolite:LED0805_Kingbright_APT2012SURCK` | `INFERRED` | S-0413 | Selected physical body and pitch; sourced LED/crystal lands, inferred leaded copper/drill. |
| `Fenolite:R_Axial_Vishay_MRS16_P7.62` | `INFERRED` | S-0414 | Selected physical body and pitch; sourced LED/crystal lands, inferred leaded copper/drill. |
| `Fenolite:R_Axial_Vishay_MRS25_P10.16` | `INFERRED` | S-0414 | Selected physical body and pitch; sourced LED/crystal lands, inferred leaded copper/drill. |
| `Fenolite:C_Film_Wima_MKS02_L4.6_W2.5_P2.5` | `INFERRED` | S-0415 | Selected physical body and pitch; sourced LED/crystal lands, inferred leaded copper/drill. |
| `Fenolite:C_Film_Wima_MKS2_L7.2_W2.5_P5` | `INFERRED` | S-0415 | Selected physical body and pitch; sourced LED/crystal lands, inferred leaded copper/drill. |
| `Fenolite:Crystal_3225_Abracon_ABM8` | `INFERRED` | S-0416 | Selected physical body and pitch; sourced LED/crystal lands, inferred leaded copper/drill. |
| `Fenolite:SW_Tact_Wurth_430181038816` | `INFERRED` | S-0417 | Selected variant dimensions and geometry; see detail notes below. |
| `Fenolite:SW_Tact_Wurth_430186043716` | `INFERRED` | S-0418 | Selected variant dimensions and geometry; see detail notes below. |
| `Fenolite:C_Electrolytic_Panasonic_FR_D5_P2` | `INFERRED` | S-0419 | Selected variant dimensions and geometry; see detail notes below. |
| `Fenolite:C_Electrolytic_Panasonic_FR_D6.3_P2.5` | `INFERRED` | S-0419 | Selected variant dimensions and geometry; see detail notes below. |
| `Fenolite:MountingHole_M2_D2.4` | `INFERRED` | S-0420 | Selected variant dimensions and geometry; see detail notes below. |
| `Fenolite:MountingHole_M3_D3.4` | `INFERRED` | S-0420 | Selected variant dimensions and geometry; see detail notes below. |
| `Fenolite:TestPoint_SMD_D1.0` | `INFERRED` | S-0421 | Selected variant dimensions and geometry; see detail notes below. |
| `Fenolite:LED5050_Worldsemi_WS2812B_V6` | `INFERRED` | S-0422 | Selected variant dimensions and geometry; see detail notes below. |
| `Fenolite:BJT_NPN` | `INFERRED` | S-0423 | Outgoing emitter arrow; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:BJT_PNP` | `INFERRED` | S-0424 | Incoming emitter arrow; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:MOSFET_N_Channel` | `INFERRED` | S-0425 | Enhancement; isolated gate, inward body arrow, S-to-D diode; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:MOSFET_P_Channel` | `INFERRED` | S-0426 | Enhancement; isolated gate, outward body arrow, D-to-S diode; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:IGBT` | `INFERRED` | S-0427 | Isolated gate and outgoing emitter arrow; no implied integrated diode; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:SCR` | `INFERRED` | S-0428 | Cathode-side gate; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:TRIAC` | `INFERRED` | S-0429 | Opposed conduction paths, MT1-side gate; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:Schottky_Diode` | `INFERRED` | S-0430 | Continuous hooked cathode; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:TVS_Bidirectional` | `INFERRED` | S-0431 | Back-to-back protection, non-polar terminals; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:Potentiometer` | `INFERRED` | S-0432 | Zigzag track, wiper touches track; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:Thermistor_NTC` | `INFERRED` | S-0433 | Zigzag and negative T coefficient mark; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:Thermistor_PTC` | `INFERRED` | S-0434 | Zigzag and positive T coefficient mark; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:Crystal` | `INFERRED` | S-0416 | Two electrodes separated from crystal body; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:Switch_SPST` | `INFERRED` | S-0435 | Unactuated open contact; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:Switch_SPDT` | `INFERRED` | S-0435 | Unactuated COM-NC contact; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:Pushbutton_NO` | `INFERRED` | S-0417, S-0418 | Normally open; internal common pairs 1-2 and 3-4; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:Relay_SPDT` | `INFERRED` | S-0436 | Unenergized COM-NC, isolated coil and mechanical coupling; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:Transformer` | `INFERRED` | S-0437 | Separate windings, core and conceptual phase markers; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:Photodiode` | `INFERRED` | S-0438, S-0440 | Diode with inward incident-light arrows; Fenolite-authored vectors and conceptual numbering, no device/package selection. |
| `Fenolite:Phototransistor` | `INFERRED` | S-0439, S-0440 | NPN detector, inward light arrows, outgoing emitter arrow; Fenolite-authored vectors and conceptual numbering, no device/package selection. |

An evidence level describes the weakest material claim attached to a catalog entry. Successful
serialization or readback checks consistency only; it does not promote the source evidence.

Soldered SMD component pad copper is rectangular. The bare probe target is intentionally circular and excludes paste. Body rectangles are fabrication-layer guides; no silkscreen line
crosses a pad. Courtyards enclose body and copper. Reflow examples and inferred corner details need
checking against the selected part and assembly process.

The c0076 symbol redraw follows public KiCad drawing and pin-direction guidance (S-0339, S-0340).
Fenolite authored every vector path and kept conceptual device pin maps. Diode anode/cathode
identities follow S-0319, and amplifier input signs follow S-0341. The positive mark on polarized
capacitors follows the generic polarity convention; the bridge's four branches follow the functional
topology in S-0342. The revised graphics, proportions, pin positions and 0.254 mm stroke do not
come from KiCad library files or a private board. Connector and terminal symbols have functional contacts;
passive and protection pin names are hidden when their numbers and body marks suffice. The
serialized KiCad symbol library now preserves that visibility setting.

Change c0134 hides the pin names of every symbol that is a drawing and keeps them on the four plain
blocks, which it enlarged. The strokes it added are Fenolite-authored and state no new fact: the plus
and the minus at the amplifier inputs repeat the signs of the pin names (S-0341), the plus, the minus
and the two waves of the bridge repeat its terminal names on the topology of S-0342, and the open
arrowhead on the optocoupler's detector marks the emitter of the phototransistor of S-0325. No
pin number, pin name or electrical type changed.

The later c0076 visual revision keeps Toshiba's public LED-to-phototransistor functional example
(S-0325) as the optocoupler's source while authoring a larger horizontal LED and two optical arrows
within its generic block. The 2/3/4-circuit connector symbols now use independently drawn square
contacts with one pin stem each; JST's S-0324 supports only circuit count and physical pitch, not
the schematic contact shape. `Capacitor_Polarized` and `Capacitor_Electrolytic` use a thicker plate
on the negative side, opposite the positive mark, as a visual choice requested by the user. Neither
the thick-plate style nor these graphics assert a manufacturer's device pinout or package.

The complete c0076 gallery was reviewed again as 26 symbols, grouped by shared drawing path:
six capacitors and the resistor, inductor and ferrite; three diode forms, bridge and optocoupler;
fuse, varistor and generic suppressor; five functional IC blocks and two amplifier triangles;
and three multi-circuit connectors plus the single terminal. The user's schematic page images
informed broad presentation preferences only. The resulting smooth coil and fuse, centered
connector rows with grouped housings and inset square contacts, square terminal socket, clean
functional IC blocks and amplifier supply contact geometry are independently authored here. No
private drawing, circuit value, net or proprietary pin map is a source. The prior zigzag resistor,
continuous Zener cathode, explicit optocoupler interior and polarized plate weight are retained.
All these symbol geometries remain `INFERRED`.

Three additional generic symbols complete functional roles seen during the gallery review:
`Common_Mode_Choke` uses TDK's public two-winding topology (S-0345),
`Gas_Discharge_Tube` uses Bourns' two-electrode and non-polar facts (S-0346), and
`Dual_LED_Common_Cathode` uses Kingbright's shared-cathode variant (S-0347). Their
schematic shapes and conceptual numbering are Fenolite-authored; the cited datasheets do not
authorize a package choice or exact pin map for another device.

QFN16–32 exposed pads exclude `F.Paste`; four filled, zero-stroke `F.Paste` rectangles cover 64% of the exposed copper, independently authored within S-0397’s guidance. Mask openings are nominal 1:1 copper; board/process mask expansion requires assembly-specific review. Peripheral paste is 1:1 copper. Thermal vias are board/application choices and are not inserted by these definitions. The pin-1 fabrication index is at the upper-left corner in the PCB top view. The standard QFN32 has one exposed pad; Type A1’s multiple internal lands are a different package and are not aliased.

DFN6 Type US and DFN8 Type UXF have separate EP lands; their underlying package views are mirrored and rotated into the left/right PCB-top numbering used here. They are not aliases for the standard DFN6 with a bonded central terminal. Their EP paste has four windows and 64% coverage. QFN48 uses sixteen 1.06 mm square windows on 1.26 mm centers, approximately 67.8% coverage before omitted corner rounding, matching the TI layout dimensions; no vias are inserted. All seven entries have a pin-1 fabrication index. Mask/paste/rounded-corner process qualifications remain inferred.

DIP through-hole dimensions are not manufacturer PCB recommendations. Their maximum body guides include the published body tolerance, omit optional flash, and retain round pads with a fabrication-layer pin-1 corner mark. No SMD lead option is substituted. Review lead forming, drills and annular rings for the selected part and fabrication process.













Connector details: generic 2.54 mm headers use 1.10 mm drills and inferred 1.80 mm copper; count-scaled rectangular housings are generic projections, not exact Würth part variants. Double-row numbering pairs odd left/even right from the top. JST B2B/B4B-XH-A are the **bossless** variants, with pin 1 at the right in PCB top view; drills differ (1.00/0.90 mm). Their housing lies from y=-2.35 to +3.40 mm relative to the pad row.

Würth micro-B uses origin at the PCB-edge center, positive y toward the board interior. Signal lands at y=5.50 mm are numbered 1–5 left to right. Rear shell centers are (±3.725,5.60) mm, copper 1.45×2.00 mm, slot 0.85×1.40 mm. Front shell centers are (±3.875,1.80) mm, copper 1.15×1.80 mm, slot 0.55×1.30 mm (the source's 0.65 mm center-to-end dimension doubled). Two empty-number NPTH pegs lie at (±2.50,4.55) mm with 0.80 mm diameter. All four plated shell pads share explicit `SH`; device mapping must assign the shell role deliberately. Their common electrical role is inferred from the drawn metal shell, not a specified continuity measurement or a copper connection on the PCB. The nominal 8.00×6.60 mm rectangular fabrication projection is centered at y=2.70 mm, inferred from the side-view front face/anchor dimensions. The y=0 fabrication guide indicates the PCB edge but does not create an Edge.Cuts segment. No extra paste is applied to the shell anchors or locating holes.

LED pin 1 is cathode on the left. Wima definitions apply only to the stated nominal box sizes (MKS0C021000B00 and MKS2C021001A00 dimension families), not all capacitances or voltages in either series. Axial resistor lead forming, leaded drills and copper annuli are authored choices. Abracon pin 1 is bottom-left in the PCB top view; a chamfer is deliberately not used as a reliable physical pin-1 identifier because the manufacturer permits multiple chamfer corners.

Würth 430181038816 SMT button has 2×1.4 mm copper on 7×3 mm centers, numbered 1/2 above 3/4. Its internal commons are 1–2 and 3–4. Würth 430186043716 THT has 6.5×4.5 mm centers, 1 mm recommended drills and inferred 1.8 mm copper, numbered 1/2 left and 3/4 right; internal commons are 1–3 and 2–4. Device pin maps must preserve these different pairings. Actuator circles and body projections are simplified fabrication guides.

Panasonic FR straight-lead cases use circular 5/6.3 mm nominal fabrication bodies, 2/2.5 mm pitch, and the manufacturer's +0.5 mm body allowance before courtyard clearance. Both use inferred 0.8 mm drill and 1.6 mm round copper for 0.5 mm leads. Pad 1 is assigned positive at the left with a plus mark; pad 2 is negative at right. Formed/taped versions can have different pitch and are not aliases.

Generic M2/M3 holes are non-plated 2.4/3.4 mm drills, with empty electrical number and excluded BOM/position flags. The inferred 5/7 mm hardware guide is not a copper keepout: board/application rules must reserve the selected head, washer and electrical clearance on all relevant layers. The single 1 mm test point has circular F.Cu/F.Mask, no F.Paste and no BOM/placement component; its diameter and 0.5 mm courtyard are inferred probe access choices, not a Tag-Connect pattern.

Worldsemi WS2812B-V6 resolves the four-terminal 5050 LED slot specifically to an addressable LED. Horizontal inner gap 3.4 mm plus 1.5 mm pad width gives 4.9 mm row centers; vertical outside span 4.3 mm minus 1 mm pad height gives 3.3 mm center spacing. Pin 1=VDD upper-left, 2=DOUT lower-left, 3=VSS lower-right, 4=DIN upper-right. Its visible corner is pin 3, not pin 1. Lens circle is an illustrative fabrication guide. It is not interchangeable with a four-terminal discrete RGB/common-cathode LED. All nominal 1:1 paste/mask apertures need part and process review.

## Additional 20 symbol drawings

See the [exact inventory](target-20-symbols.md) for role assignments and public functional sources. Transistor arrows, isolated enhancement gates, oppositely oriented body diodes, thyristor gates and non-polar TVS follow functional conventions supported by the cited datasheets. Dimensions and paths are independently authored. Background-filled outline arrowheads reproduce the current writer, rather than claiming a foreground-fill primitive. Two winding phase dots use a thick circular stroke. Mechanical coupling is a discontinuous cue, never an electrical connection.

The source transformer has multiple windings; the catalog is deliberately a generic two-winding abstraction. The source relay has duplicate physical COM terminals; the catalog exposes five functions. The crystal exposes electrode functions only, whereas ABM8 has additional case pads. Manufacturer physical numbers must be resolved explicitly in a project symbol or pad map. The build fixtures check role-to-pad mapping and serialization, not an operating circuit or an MPN qualification.
