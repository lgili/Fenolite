# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Net roles (change c0222; capability net-roles; user guide ``docs/roles.md``).

Each net of a design has one role: stated by the user (``declared`` in a script, ``confirmed`` through
``fenolite roles``) or inferred from the parts and the topology. The roles say what the analyses of
``fenolite.analysis`` measure (which loops, paths, pairs and nets), and the role checks judge their rows
against the role limits. Package layering: ``roles`` imports ``model``, ``geometry``, ``backends.base`` and
``analysis``; only ``cli`` and the root modules import ``roles``.
"""

from __future__ import annotations

from fenolite.model.rules import ROLE_KINDS, ROLE_SOURCES

__all__ = ["ROLE_KINDS", "ROLE_SOURCES"]
