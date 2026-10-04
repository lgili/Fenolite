# SPDX-License-Identifier: Apache-2.0
# Copyright (c) 2026 Fenolite contributors
"""Pluggable, model-only board routing."""

from fenolite.routing.codes import ISSUE_CODES
from fenolite.routing.merge import apply
from fenolite.routing.protocol import JobNet, JobPad, Router, RouterStatus, RoutingJob, RoutingResult
from fenolite.routing.registry import routers
from fenolite.routing.select import unrouted

__all__ = [
    "ISSUE_CODES",
    "JobNet",
    "JobPad",
    "Router",
    "RouterStatus",
    "RoutingJob",
    "RoutingResult",
    "apply",
    "routers",
    "unrouted",
]
