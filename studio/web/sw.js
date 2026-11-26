// Нужен, чтобы Студию можно было поставить иконкой на телефон и компьютер. Ничего не кэширует: всегда свежая версия.
self.addEventListener('install', () => self.skipWaiting());
self.addEventListener('activate', e => e.waitUntil(self.clients.claim()));
self.addEventListener('fetch', () => {});
