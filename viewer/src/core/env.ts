// SPDX-License-Identifier: Apache-2.0
// Copyright (c) 2026 Fenolite contributors
export const PREVIEW_MODE = new URLSearchParams(location.hash.slice(1)).get("preview") === "1";
if (PREVIEW_MODE) document.body.classList.add("preview");
