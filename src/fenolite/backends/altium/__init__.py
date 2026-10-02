# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Experimental Altium writer: an ASCII schematic (``.SchDoc``) and a project file (``.PrjPcb``).

This package is a writer only. It is **not** a registered backend: it reads no Altium file and is
absent from ``fenolite.backends.registry``; ``fenolite capabilities`` lists it under
``result.experimental``. ``project.write_project`` turns a model design whose components hold their pins
into file bytes and writes nothing itself; ``fenolite.lens.altium`` checks the design and builds it.

Facts and sources: ``docs/formats/altium/`` and ``PROVENANCE.md`` in this package. The code is written
from those pages, never from third-party code.
"""
