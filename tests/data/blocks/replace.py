# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
# Authored for Fenolite as test data (change c0268); no file, value or name comes from any other project.
"""Two block records: ``Acme:div2`` replaces ``Acme:div``, which does not name it in ``deprecated``."""

from fenolite.dsl import Net, block

__all__ = ["div", "div2"]


@block(id="Acme:div", version="1.0.0", summary="A divider", licence="CC0-1.0")
def div(b):
    b.port("IN", Net, direction="in")
    b.part("R", "Device:R", prefix="R", value="1k")


@block(
    id="Acme:div2", version="1.0.0", summary="A divider, renamed port", licence="CC0-1.0", replaces="Acme:div"
)
def div2(b):
    b.port("VIN", Net, direction="in")
    b.part("R", "Device:R", prefix="R", value="1k")
