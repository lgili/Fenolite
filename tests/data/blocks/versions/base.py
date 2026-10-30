# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite as test data (change c0268); no file, value or name comes from any other project.
"""The version rules: the committed state of a block, ``Acme:div`` 1.0.0."""

from fenolite.dsl import Net, block, param

__all__ = ["div"]


@block(id="Acme:div", version="1.0.0", summary="A divider", licence="CC0-1.0")
def div(b, *, ratio=param(2, doc="division ratio", min=1, max=10)):
    b.port("IN", Net, direction="in")
    b.port("OUT", Net, direction="out")
