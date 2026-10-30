# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The blocks shipped with Fenolite (``docs/blocks.md``; change c0268).

Each module of this package defines blocks with a record in the reserved namespace ``Fenolite`` and lists
them in its ``__all__``; ``fenolite blocks list`` reads them as the catalog source ``builtin``. A module
imports only ``fenolite.dsl``, ``fenolite.model`` and ``fenolite.core``, and importing it creates no
design, opens no file and imports no third-party module. ``VERSIONS.toml`` records the version and digests
of every shipped block (``tools/blocks/versions.py``). The package is empty until the starter blocks are
added.
"""

__all__: list[str] = []
