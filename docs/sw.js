'use strict';
// Service worker: guarda los juegos en el teléfono para que abran sin internet.
// - Archivos propios: primero se piden a internet (así siempre llega la última versión) y,
//   si no hay conexión, se usa la copia guardada.
// - Librerías externas (three.js y el emulador): se guardan la primera vez y luego se usan desde el teléfono.
const CACHE = 'juegos-v3';
const PROPIOS = ['./', 'index.html', 'estilo.css', 'comun.js', 'manifest.webmanifest', 'iconos/icono-192.png', 'iconos/icono-512.png',
  'bloques.html', 'pong.html', 'naves.html', 'naves3d.html', 'plataformas3d.html', 'carreras.html', 'carreras-hd.html',
  'emulador.html', 'n64.html'];
const EXTERNOS = ['https://cdn.jsdelivr.net/npm/three@0.160.0/build/three.module.js'];

self.addEventListener('install', (e) => {
  e.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    await cache.addAll(PROPIOS);
    await Promise.all(EXTERNOS.map((url) => cache.add(url).catch(() => { /* se guardará al usarla */ })));
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (e) => {
  e.waitUntil((async () => {
    for (const nombre of await caches.keys()) if (nombre !== CACHE) await caches.delete(nombre);
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (e) => {
  const pedido = e.request;
  if (pedido.method !== 'GET') return;
  const url = new URL(pedido.url);
  if (url.origin === location.origin) {
    // se guarda una sola copia por página, sin lo que va después de "?" (?s=snes, ?v=2...)
    const clave = url.origin + url.pathname;
    e.respondWith((async () => {
      try {
        const respuesta = await fetch(pedido, { cache: 'no-cache' });
        if (respuesta.ok) (await caches.open(CACHE)).put(clave, respuesta.clone());
        return respuesta;
      } catch {
        return (await caches.match(clave)) || Response.error(); // sin conexión: la copia guardada
      }
    })());
  } else if (url.hostname === 'cdn.jsdelivr.net' || url.hostname === 'cdn.emulatorjs.org') {
    e.respondWith((async () => {
      const guardada = await caches.match(pedido);
      if (guardada) return guardada;
      const respuesta = await fetch(pedido);
      if (respuesta.ok || respuesta.type === 'opaque') (await caches.open(CACHE)).put(pedido, respuesta.clone());
      return respuesta;
    })());
  }
});
