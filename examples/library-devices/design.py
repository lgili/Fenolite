# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite as an illustrative offline device example (c0266).
from fenolite.dsl import Design, mm

design = Design("library_devices")
design.board(mm(20), mm(12))
r = design.part("R1", device="FenoliteDevices:Demo900")
r.place(mm(10), mm(6))
r.unused_no_connect()
