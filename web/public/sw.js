// SPDX-License-Identifier: AGPL-3.0-only
// Copyright (C) 2026 Edmilton Cabral Martins Junior <junior.edmilton@gmail.com>

const CACHE_SHELL = "mara-shell-v4";
const CACHE_ASSETS = "mara-assets-v4";

const PRECACHE_URLS = [
  "/",
  "/manifest.webmanifest",
  "/icons/icon-192.png",
  "/icons/icon-512.png",
  "/api/emblems/d1",
  "/api/emblems/infinito",
  "/api/library",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches
      .open(CACHE_SHELL)
      .then((cache) =>
        Promise.allSettled(PRECACHE_URLS.map((url) => cache.add(url))),
      )
      .then(() => self.skipWaiting()),
  );
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k !== CACHE_SHELL && k !== CACHE_ASSETS)
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});

self.addEventListener("fetch", (event) => {
  const { request } = event;
  if (request.method !== "GET") return;

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return;

  // Nunca intercepta endpoints administrativos
  if (url.pathname.startsWith("/api/admin")) return;

  // Ativos imutáveis (_next/static, ícones, emblemas DSA): Cache-first + atualização em background
  if (
    url.pathname.startsWith("/_next/static/") ||
    url.pathname.startsWith("/icons/") ||
    url.pathname.startsWith("/api/emblems/")
  ) {
    event.respondWith(
      caches.open(CACHE_ASSETS).then(async (cache) => {
        const cached = await cache.match(request);
        const networkPromise = fetch(request)
          .then((resp) => {
            if (resp && resp.status === 200) {
              cache.put(request, resp.clone());
            }
            return resp;
          })
          .catch(() => cached);
        return cached || networkPromise;
      }),
    );
    return;
  }

  // Navegação HTML e metadados públicos (/api/library, /api/health, /api/conversations): Network-first com fallback offline
  if (
    request.mode === "navigate" ||
    url.pathname === "/api/library" ||
    url.pathname === "/api/health" ||
    url.pathname.startsWith("/api/conversations")
  ) {
    event.respondWith(
      fetch(request)
        .then(async (resp) => {
          if (resp && resp.status === 200) {
            const cache = await caches.open(CACHE_SHELL);
            cache.put(request, resp.clone());
          }
          return resp;
        })
        .catch(async () => {
          const cache = await caches.open(CACHE_SHELL);
          const hit = await cache.match(request);
          if (hit) return hit;
          if (request.mode === "navigate") {
            const rootFallback = await cache.match("/");
            if (rootFallback) return rootFallback;
          }
          return new Response(
            JSON.stringify({ detail: "Modo Acampamento Offline ativo." }),
            { status: 503, headers: { "Content-Type": "application/json" } },
          );
        }),
    );
  }
});
