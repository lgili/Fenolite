# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Altium files: the registered backend that reads them, and the experimental writers.

- **Reading** (change c0043). ``backend.AltiumBackend`` is the registered backend ``altium`` of
  ``fenolite.backends.registry``: it detects and reads ``.PrjPcb``, ``.SchDoc``, ``.SchLib``, ``.PcbDoc``
  and ``.PcbLib`` into the neutral model. The readers under ``read`` turn bytes into records and lose no
  byte; the functions under ``adapter`` map records into ``Design`` and ``Library``. The backend offers
  no ``write``.
- **Writing** (experimental). The writer modules of this package (``project``, ``schdoc``, ``schlib``,
  ``pcblib``, ``pcbdoc`` …) are not part of the backend's report: ``fenolite capabilities`` lists them
  under ``result.experimental``. ``project.write_project`` turns a model design whose components hold
  their pins into file bytes and writes nothing itself; ``fenolite.lens.altium`` checks the design and
  builds it.

Facts and sources: ``docs/formats/altium/`` and ``PROVENANCE.md`` in this package. The code is written
from those pages, never from third-party code.
"""
