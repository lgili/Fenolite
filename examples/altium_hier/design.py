# SPDX-License-Identifier: CC0-1.0
# Authored for Fenolite as an example; no file, value, name or layout comes from any other project.
"""Altium hierarchy sample: a connector on the top sheet, a controller and a flash memory in two modules,
and an SPI harness between them.

Build it with ``fenolite build examples/altium_hier/design.py --out build/altium_hier --target altium
--altium-sheets modules --confirm``: the top sheet ``altium_hier.SchDoc`` holds ``J1`` and one sheet symbol
per module, ``altium_hier_mcu.SchDoc`` and ``altium_hier_flash.SchDoc`` hold the modules, and the four SPI
nets cross in the harness ``SPI``. The lib ids name the libraries ``FenoliteHier.SchLib`` and
``FenoliteHier.PcbLib``, which Fenolite does not ship: the build reads no library. Every pin is connected
by its number.
"""

from fenolite.dsl import Design, Harness, Module, Net, Part, Power, connect

SCHLIB = "FenoliteHier.SchLib"
PCBLIB = "FenoliteHier.PcbLib"

design = Design("altium_hier")

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
design.add(Harness("SPI", {"MOSI": spi_mosi, "MISO": spi_miso, "SCK": spi_sck, "CS": spi_cs}))
