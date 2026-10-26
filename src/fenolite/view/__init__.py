# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""The board and schematic viewer (capabilities board-viewer and schematic-viewer): a scene of a board or of
an Altium sheet for a web page, the tree of a project's documents, the packaged page, a standalone export and
a local live server. Standard library only."""

from __future__ import annotations

from fenolite.view.scene import SCHEMA, build_scene, summary

__all__ = ["SCHEMA", "build_scene", "summary"]
