# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Immutable findings; the tuple retains the check evidence."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from fenolite.checks.subjects import Subject
from fenolite.core.evidence import Evidence


@dataclass(frozen=True, slots=True)
class Finding:
    code: str
    severity: str
    message: str
    where: str
    subjects: tuple[Subject, ...] = ()


class Findings(tuple[Finding, ...]):
    _evidence: Evidence

    def __new__(cls, items: Iterable[Finding], evidence: Evidence) -> Findings:
        result = super().__new__(cls, items)
        result._evidence = evidence
        return result

    @property
    def evidence(self) -> Evidence:
        return self._evidence
