// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
// The entry of the vendor chunk (change c0304, design decision 6): esbuild bundles it as an IIFE that assigns the
// global `preact`; modules import `* as preact from "preact"` for the types, and the linker drops that import.
export { Component, Fragment, h, render } from "preact";
