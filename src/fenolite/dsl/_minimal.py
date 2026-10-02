# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The packaged minimal design script: a 20 mm x 10 mm board with one net class and no parts.

``fenolite build`` uses it in its own examples, so the CLI consistency suite needs no file outside the
package.
"""

from fenolite.dsl import Design, Net, mm

design = Design("minimal")
design.board(mm(20), mm(10))
design.rules.netclass("PWR", clearance=mm(0.2), track_width=mm(0.5), nets=(Net("VIN"),))
