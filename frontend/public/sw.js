const CACHE_NAME = "trustscope-shell-v1";
const SHELL_FILES = [
  "/",
  "/manifest.webmanifest",
  "/app-icon.svg",
];

self.addEventListener("install", (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) =>
      cache.addAll(SHELL_FILES)
    )
  );
  self.skipWaiting();
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(
        keys
          .filter((key) => key !== CACHE_NAME)
          .map((key) => caches.delete(key))
      )
    )
  );
  self.clients.claim();
});

self.addEventListener("fetch", (event) => {
  const request = event.request;
  const url = new URL(request.url);
  const cacheableDestinations = new Set([
    "document",
    "font",
    "image",
    "manifest",
    "script",
    "style",
  ]);

  if (
    request.method !== "GET" ||
    url.origin !== self.location.origin ||
    !cacheableDestinations.has(request.destination)
  ) {
    return;
  }

  event.respondWith(
    fetch(request)
      .then((response) => {
        if (response.ok) {
          const copy = response.clone();
          caches.open(CACHE_NAME).then((cache) =>
            cache.put(request, copy)
          );
        }
        return response;
      })
      .catch(() => caches.match(request))
  );
});
