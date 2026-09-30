# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Findings layer: issues attached to a design, first-class like any other data."""

from __future__ import annotations

from dataclasses import dataclass

from fenolite.core.errors import Issue


@dataclass(frozen=True, slots=True)
class Findings:
    """The findings layer of a design (``findings.json``)."""

    issues: tuple[Issue, ...] = ()


__all__ = ["Findings", "Issue"]
