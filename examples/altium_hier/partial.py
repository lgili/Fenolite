# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Altium hierarchy sample with a harness entry that is not wired: the design of ``design.py`` with a fifth
entry ``HOLD`` on the net ``FLASH_HOLD_N``, which only the ``flash`` sheet uses.

Build it with ``fenolite build examples/altium_hier/partial.py --out build/altium_hier_partial --target
altium --altium-sheets modules --confirm``. Every harness block then holds five entries, and the entry
``HOLD`` gets no wire on any sheet, because its net does not leave the ``flash`` sheet (step H6 of
``docs/evidence/altium-schematic.md``).
"""

from fenolite.dsl import Design, Harness, Module, Net, Part, Power, connect

SCHLIB = "FenoliteHier.SchLib"
PCBLIB = "FenoliteHier.PcbLib"

design = Design("altium_hier_partial")

j1 = Part("J1", f"{SCHLIB}:HDR3", footprint=f"{PCBLIB}:HDR1X3")

mcu = Module("mcu")
u1 = Part("U1", f"{SCHLIB}:MCU8", footprint=f"{PCBLIB}:SOIC8", value="MCU8")
c1 = Part("C1", f"{SCHLIB}:CAP", footprint=f"{PCBLIB}:C0603", value="100nF")
mcu.add(u1, c1)

flash = Module("flash")
u2 = Part("U2", f"{SCHLIB}:FLASH8", footprint=f"{PCBLIB}:SOIC8", value="FLASH8")
c2 = Part("C2", f"{SCHLIB}:CAP", footprint=f"{PCBLIB}:C0603", value="100nF")
r1 = Part("R1", f"{SCHLIB}:RES", footprint=f"{PCBLIB}:R0603", value="10k")
flash.add(u2, c2, r1)

design.add(j1, mcu, flash)

vdd, gnd = Net("VDD"), Net("GND")
reset_n, flash_wp, flash_hold_n = Net("RESET_N"), Net("FLASH_WP"), Net("FLASH_HOLD_N")
spi_mosi, spi_miso, spi_sck, spi_cs = Net("SPI_MOSI"), Net("SPI_MISO"), Net("SPI_SCK"), Net("SPI_CS")

connect(vdd, j1[1], u1[8], c1[1], u2[8], c2[1], r1[1])
connect(gnd, j1[2], u1[4], c1[2], u2[4], c2[2])
connect(reset_n, j1[3], u1[1])
connect(flash_wp, u1[2], u2[3])
connect(spi_cs, u1[3], u2[1])
connect(spi_miso, u1[5], u2[2])
connect(spi_mosi, u1[6], u2[5])
connect(spi_sck, u1[7], u2[6])
connect(flash_hold_n, u2[7], r1[2])

design.add(Power(vdd, gnd))
design.add(
    Harness(
        "SPI",
        {"MOSI": spi_mosi, "MISO": spi_miso, "SCK": spi_sck, "CS": spi_cs, "HOLD": flash_hold_n},
    )
)
