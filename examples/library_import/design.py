# SPDX-License-Identifier: CC0-1.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite. Fictional device: https://example.invalid/exb6202
"""Place a locally imported, unverified model without a library table or hand-written pad map."""

from fenolite.dsl import Design, mm

design = Design("library_import")
design.board(mm(24), mm(18))
u1 = design.part("U1", device="Imported:EXB6202")
u1.place(mm(12), mm(9))
u1.unused_no_connect()
