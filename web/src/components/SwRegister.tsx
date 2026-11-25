// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

"use client";

import { useEffect } from "react";

export function SwRegister() {
  useEffect(() => {
    if (typeof window !== "undefined" && "serviceWorker" in navigator) {
      navigator.serviceWorker.register("/sw.js").catch(() => {
        // Falha silenciosa em ambientes sem HTTPS (exceto localhost)
      });
    }
  }, []);
  return null;
}
