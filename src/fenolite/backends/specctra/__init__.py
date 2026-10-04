# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Specctra codec: writes a design file (``.dsn``) from the model and reads a session file (``.ses``).

This package is a codec, **not** a registered backend: it is absent from ``fenolite.backends.registry``,
detects no file and reads no design. A routing plugin hands ``dsn.write_dsn`` the model, the board-frame
pads and the outline rings, runs an external router on the text, and turns the router's session into
tracks and vias with ``ses.read_session`` and ``ses.to_copper``.

Facts and sources: ``docs/formats/specctra/`` and ``PROVENANCE.md`` in this package (ADR-0006). The code
is written from those pages, never from third-party code. It imports only ``core``, ``model``,
``geometry`` and ``backends.base``.
"""
