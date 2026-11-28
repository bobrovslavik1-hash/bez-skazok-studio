/* Студия «Без сказок» — веб-интерфейс без сборки: одна страница, разделы по адресу #/… */
(() => {
  'use strict';

  // ---------- мелочи ----------
  const $ = (s, el = document) => el.querySelector(s);
  const esc = v => String(v ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const TZ = 'Europe/Sofia';
  const fDT = new Intl.DateTimeFormat('ru-RU', { timeZone: TZ, day: '2-digit', month: '2-digit', hour: '2-digit', minute: '2-digit' });
  const fDay = new Intl.DateTimeFormat('ru-RU', { timeZone: TZ, day: 'numeric', month: 'short' });
  const fYMD = new Intl.DateTimeFormat('en-CA', { timeZone: TZ, year: 'numeric', month: '2-digit', day: '2-digit' });
  const dt = iso => (iso ? fDT.format(new Date(iso)) : '—');
  function when(iso) {
    if (!iso) return '—';
    const s = (Date.now() - new Date(iso)) / 1000;
    if (s < 50) return 'только что';
    if (s < 3600) return Math.round(s / 60) + ' мин назад';
    if (s < 86400) return Math.round(s / 3600) + ' ч назад';
    return dt(iso);
  }
  function dur(sec) {
    if (sec == null) return '—';
    if (sec < 60) return (Math.round(sec * 10) / 10) + ' с';
    const m = Math.floor(sec / 60), s = Math.round(sec % 60);
    return m + ' мин' + (s ? ' ' + s + ' с' : '');
  }
  function money(v, digits = 2) {
    if (v == null || isNaN(v)) return '—';
    v = Number(v);
    if (v > 0 && v < 0.01) return '<$0.01';
    return '$' + v.toFixed(digits);
  }
  const plural = (n, a, b, c) => { const m10 = n % 10, m100 = n % 100; return m10 === 1 && m100 !== 11 ? a : m10 >= 2 && m10 <= 4 && (m100 < 10 || m100 >= 20) ? b : c; };

  const I = {
    copy: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><rect x="9" y="9" width="11" height="11" rx="2"/><path d="M5 15V5a1 1 0 0 1 1-1h10"/></svg>',
    plug: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M9 7V3M15 7V3"/><path d="M6 7h12v4a6 6 0 0 1-12 0V7z"/><path d="M12 17v4"/></svg>',
    fb: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M14 8h3V4h-3c-2.8 0-4.5 1.8-4.5 4.6V11H7v4h2.5v8h4v-8h3l.5-4h-3.5V8.8c0-.5.3-.8.5-.8z"/></svg>',
    tg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M21.4 4.3 2.9 11.4c-1.3.5-1.2 1.2-.2 1.5l4.7 1.5 1.8 5.6c.2.6.4.8.9.8.4 0 .6-.2.9-.4l2.3-2.2 4.7 3.5c.9.5 1.5.2 1.7-.8l3.1-14.6c.3-1.3-.5-1.9-1.4-1.5zM9.9 14.2l-.4 4.2-1.4-4.6 10-6.3-8.2 6.7z"/></svg>',
    threads: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round"><path d="M16.5 11.2c-.3-2.6-1.9-3.9-4.3-3.9-2.6 0-4.2 1.9-4.2 4.7s1.6 4.8 4.4 4.8c2 0 3.6-1.1 3.6-3 0-2.4-2.6-3-4.6-2.6"/><path d="M19.5 8.5C18.3 5.2 15.6 3.5 12 3.5c-5 0-8 3.4-8 8.5s3 8.5 8 8.5c3.9 0 6.6-2 7.4-5.2"/></svg>',
    dirs: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3 3 7.5l9 4.5 9-4.5L12 3z"/><path d="m3 12 9 4.5 9-4.5"/><path d="m3 16.5 9 4.5 9-4.5"/></svg>',
    play: '<svg viewBox="0 0 16 16" fill="#fff"><path d="M3 1.8v12.4c0 .6.7 1 1.2.7l10-6.2c.5-.3.5-1.1 0-1.4l-10-6.2C3.7.8 3 1.2 3 1.8z"/></svg>',
    home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7.5" height="9" rx="1.6"/><rect x="13.5" y="3" width="7.5" height="5.5" rx="1.6"/><rect x="13.5" y="11.5" width="7.5" height="9.5" rx="1.6"/><rect x="3" y="15" width="7.5" height="6" rx="1.6"/></svg>',
    prompter: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3.5" width="18" height="17" rx="2.5"/><path d="M7 8.5h10M7 12h10M7 15.5h6"/><path d="M3 12h1.6" stroke-width="2.4"/></svg>',
    film: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="16" rx="2.5"/><path d="M7.5 4v16M16.5 4v16M3 9h4.5M3 15h4.5M16.5 9H21M16.5 15H21"/></svg>',
    log: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M4 6h3M4 12h3M4 18h3M10 6h10M10 12h10M10 18h7"/></svg>',
    coin: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.5"/><path d="M14.8 9.2c-.5-.9-1.5-1.4-2.8-1.4-1.7 0-2.8.8-2.8 2.1 0 2.9 5.8 1.4 5.8 4.3 0 1.3-1.2 2.1-3 2.1-1.4 0-2.5-.6-3-1.6M12 6.2v1.6M12 16.3v1.5"/></svg>',
    rss: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M5 11a8 8 0 0 1 8 8M5 5a14 14 0 0 1 14 14"/><circle cx="6" cy="18" r="1.4" fill="currentColor"/></svg>',
    gear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .3 1.8l.1.1a2 2 0 1 1-2.8 2.8l-.1-.1a1.7 1.7 0 0 0-1.8-.3 1.7 1.7 0 0 0-1 1.5V21a2 2 0 1 1-4 0v-.1a1.7 1.7 0 0 0-1.1-1.5 1.7 1.7 0 0 0-1.8.3l-.1.1a2 2 0 1 1-2.8-2.8l.1-.1a1.7 1.7 0 0 0 .3-1.8 1.7 1.7 0 0 0-1.5-1H3a2 2 0 1 1 0-4h.1a1.7 1.7 0 0 0 1.5-1.1 1.7 1.7 0 0 0-.3-1.8l-.1-.1a2 2 0 1 1 2.8-2.8l.1.1a1.7 1.7 0 0 0 1.8.3H9a1.7 1.7 0 0 0 1-1.5V3a2 2 0 1 1 4 0v.1a1.7 1.7 0 0 0 1 1.5 1.7 1.7 0 0 0 1.8-.3l.1-.1a2 2 0 1 1 2.8 2.8l-.1.1a1.7 1.7 0 0 0-.3 1.8V9a1.7 1.7 0 0 0 1.5 1H21a2 2 0 1 1 0 4h-.1a1.7 1.7 0 0 0-1.5 1z"/></svg>',
    download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11M7 10.5l5 5 5-5M5 20h14"/></svg>',
    refresh: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M20 11a8 8 0 0 0-14.3-4.9L4 8M4 4v4h4M4 13a8 8 0 0 0 14.3 4.9L20 16M20 20v-4h-4"/></svg>',
    ext: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M14 4h6v6M20 4l-9 9M18 14v5a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V7a1 1 0 0 1 1-1h5"/></svg>',
    plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
    pencil: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4L19 9a2.8 2.8 0 0 0-4-4L4 16v4zM13.5 6.5l4 4"/></svg>',
    trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.9" stroke-linecap="round" stroke-linejoin="round"><path d="M4 7h16M10 11v6M14 11v6M6 7l1 12a2 2 0 0 0 2 2h6a2 2 0 0 0 2-2l1-12M9 7V4h6v3"/></svg>',
    globe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="9"/><path d="M3 12h18M12 3c2.5 2.6 3.8 5.6 3.8 9s-1.3 6.4-3.8 9c-2.5-2.6-3.8-5.6-3.8-9S9.5 5.6 12 3z"/></svg>',
    tg: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M20.7 4.3 2.9 11.2c-1.2.5-1.2 1.2-.2 1.5l4.6 1.4 1.7 5.4c.2.6.4.8.9.8.4 0 .6-.2.9-.4l2.2-2.1 4.6 3.4c.8.5 1.4.2 1.6-.8l3-14.2c.3-1.3-.5-1.9-1.5-1.5zM8.3 13.8l9.4-5.9c.5-.3.9-.1.5.2l-8 7.2-.3 3.3-1.6-4.8z"/></svg>',
    yt: '<svg viewBox="0 0 24 24" fill="currentColor"><path d="M21.6 7.2a2.6 2.6 0 0 0-1.8-1.8C18.2 5 12 5 12 5s-6.2 0-7.8.4a2.6 2.6 0 0 0-1.8 1.8C2 8.8 2 12 2 12s0 3.2.4 4.8a2.6 2.6 0 0 0 1.8 1.8C5.8 19 12 19 12 19s6.2 0 7.8-.4a2.6 2.6 0 0 0 1.8-1.8c.4-1.6.4-4.8.4-4.8s0-3.2-.4-4.8zM10 15.1V8.9l5.2 3.1L10 15.1z"/></svg>',
  };

  const NAV = [
    ['#/', 'Обзор', I.home], ['#/episodes', 'Выпуски', I.film], ['#/prompter', 'Суфлёр', I.prompter], ['#/logs', 'Журнал', I.log],
    ['#/costs', 'Расходы', I.coin], ['#/directions', 'Направления', I.dirs], ['#/connections', 'Подключения', I.plug], ['#/sources', 'Источники', I.rss],
    ['#/settings', 'Настройки', I.gear],
  ];
  const EP_TONE = {
    preview_ready: 'ok', published: 'ok', used: 'ok', partial: 'warn', recording: 'warn live', rendering: 'warn live',
    publishing: 'warn live', redo: 'warn live', script_ready: 'info', inserts_ready: 'info', error: 'err', superseded: '', cancelled: '',
    publish_requested: 'warn live',
  };
  // действия с выпуском из Студии — те же, что кнопки бота под превью
  const EP_ACT = {
    publish: { label: 'Опубликовать', tone: 'primary', ask: 'Опубликовать выпуск и шортсы на YouTube? Доступ к видео — как указано в настройках направления.', done: 'Отправил на публикацию — начнётся в течение минуты' },
    redo: { label: 'Пересобрать', tone: '', ask: 'Пересобрать выпуск? Запись заново пройдёт монтаж под новым номером (старт в течение 2 минут).', done: 'Пересборка поставлена' },
    cancel: { label: 'Отменить', tone: '', ask: 'Отменить выпуск? Он не будет опубликован; файлы на сервере удалятся сами через 7 дней.', askScript: 'Отменить сценарий? Запись к нему больше не привяжется.', done: 'Отменено' },
  };
  const tc = ms => { const s = Math.max(0, Math.round((ms || 0) / 1000)); return Math.floor(s / 60) + ':' + String(s % 60).padStart(2, '0'); };
  // длительность этапа: 45 с · 14 мин · 1 ч 05 мин · 2 дн 3 ч
  const took = sec => {
    if (sec == null) return '—';
    if (sec < 60) return sec + ' с';
    const m = Math.round(sec / 60);
    if (m < 60) return m + ' мин';
    const h = Math.floor(m / 60);
    if (h < 48) return h + ' ч' + (m % 60 ? ' ' + String(m % 60).padStart(2, '0') + ' мин' : '');
    return Math.floor(h / 24) + ' дн' + (h % 24 ? ' ' + (h % 24) + ' ч' : '');
  };
  const DELIVERY_T = { opinion: 'С моим мнением', facts: 'Только новости' };
  // «Как прошёл выпуск»: этапы со временем и сколько что длилось (учёт ведёт база с 28.11)
  const reportSection = rp => {
    if (!rp || !(rp.steps || []).length) return '';
    const kv = [];
    if (rp.delivery) kv.push(['Подача', esc(DELIVERY_T[rp.delivery] || rp.delivery)]);
    rp.steps.forEach(s => kv.push([esc(s.label), dt(s.at)]));
    if (rp.montage_s != null) kv.push(['Монтаж занял', took(rp.montage_s)]);
    if (rp.review_s != null) kv.push(['Проверка заняла', took(rp.review_s)]);
    if (rp.publish_s != null) kv.push(['Публикация заняла', took(rp.publish_s)]);
    if (rp.total_s != null) kv.push(['От сценария до эфира', took(rp.total_s)]);
    if (rp.shorts_ready != null && rp.shorts_planned) kv.push(['Шортсы', rp.shorts_ready + ' из ' + rp.shorts_planned]);
    return `<div class="section-t">Как прошёл выпуск</div><dl class="kv">${kv.map(([k, v]) => `<dt>${k}</dt><dd>${v}</dd>`).join('')}</dl>`;
  };
  // удалить выпуск или сценарий целиком (база, вставки, файлы на сервере); пока идёт монтаж или публикация — нельзя
  const EP_BUSY = ['recording', 'rendering', 'publishing', 'publish_requested', 'redo'];
  const mbText = mb => mb >= 1024 ? (mb / 1024).toFixed(1).replace('.', ',') + ' ГБ' : mb + ' МБ';
  async function deleteEpisode(id, title, isScript) {
    if (!confirm(`Удалить ${isScript ? 'сценарий' : 'выпуск'} «${title}»?\n\nУдалятся вставки и файлы на сервере — вернуть будет нельзя. ` +
      'Расходы останутся в истории, исходник на Google Диске не трогаем.')) return false;
    try {
      const r = await api('/api/episodes/' + encodeURIComponent(id), { method: 'DELETE' });
      toast(r.files_left_mb ? `Удалено. Остаток файлов (${mbText(r.files_left_mb)}) сервер уберёт сам в течение недели`
        : 'Удалено' + (r.freed_mb ? ' · освобождено ' + mbText(r.freed_mb) : ''));
      return true;
    } catch (e) { toast(e.message, true); return false; }
  }
  const INS_KIND = { screenshot: 'скрин', source_media: 'медиа из источника', card: 'карточка', quote: 'цитата', number: 'цифра', map: 'карта',
    stock: 'сток', wikimedia: 'Wikimedia', diagram: 'схема', ai_image: 'ИИ-картинка' };
  const RUN_TONE = { success: ['ok', 'Успешно'], error: ['err', 'Ошибка'], crashed: ['err', 'Сбой'], running: ['warn live', 'Идёт'],
    waiting: ['warn', 'Ждёт'], new: ['warn', 'В очереди'], canceled: ['', 'Отменён'] };

  const state = { user: null, version: null, errors24: 0, timer: null, now: { state: 'idle', ep: null }, tallyTimer: null, clockT: null, clockI: null };

  // ---------- связь с сервером ----------
  async function api(path, opts = {}) {
    const o = { credentials: 'same-origin', headers: { accept: 'application/json' } };
    const method = opts.method || (opts.body !== undefined ? 'POST' : 'GET');
    if (method !== 'GET') {
      o.method = method;
      o.headers['x-studio'] = '1';
    }
    if (opts.body !== undefined) { o.headers['content-type'] = 'application/json'; o.body = JSON.stringify(opts.body); }
    const r = await fetch(path, o);
    if (r.status === 401 && !opts.noAuthRedirect) { showLogin(); throw new Error('Нужно войти'); }
    let data = null;
    try { data = await r.json(); } catch (e) { /* пустой ответ */ }
    if (!r.ok) throw new Error((data && data.detail) || 'Ошибка ' + r.status);
    return data;
  }

  function toast(msg, isErr) {
    const t = document.createElement('div');
    t.className = 'toast' + (isErr ? ' err' : '');
    t.textContent = msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), isErr ? 5000 : 2600);
  }

  // ---------- студия: табло «ЭФИР», часы, тема ----------
  // какое состояние у конвейера сейчас — по самому важному выпуску: публикуется → монтаж → ждёт решения → ждёт записи
  const NOW_RULES = [['live', ['publish_requested', 'publishing']], ['busy', ['recording', 'rendering', 'redo']],
    ['ready', ['preview_ready', 'partial']], ['cue', ['inserts_ready', 'script_ready']]];
  const TALLY = {
    live: { plate: 'В ЭФИРЕ', label: 'Публикуется' }, busy: { plate: 'МОНТАЖ', label: 'Идёт монтаж' },
    ready: { plate: 'ПРОВЕРКА', label: 'Готов, ждёт решения' }, cue: { plate: 'ЗАПИСЬ', label: 'Ждёт записи' },
    done: { plate: 'ЭФИР', label: 'Опубликован' }, idle: { plate: 'ЭФИР', label: 'Тихо' },
  };
  function pickNow(list) {
    const eps = (list || []).filter(e => !['superseded', 'cancelled'].includes(e.status));
    for (const [st, codes] of NOW_RULES) {
      const e = eps.find(x => codes.includes(x.status));
      if (e) return { state: st, ep: e };
    }
    const pub = eps.find(x => x.status === 'published');
    return pub ? { state: 'done', ep: pub } : { state: 'idle', ep: null };
  }
  const lampState = st => (st === 'done' ? 'idle' : st);
  function tallyInner(now) {
    const t = TALLY[now.state] || TALLY.idle;
    return `<span class="tally-plate">${t.plate}</span><span class="tally-txt"><b>${esc(t.label)}</b>
      <small>${esc(now.ep ? now.ep.title || now.ep.id : 'новых выпусков нет')}</small></span>`;
  }
  async function refreshTally(list) {
    let eps = list;
    if (!eps) {
      try { eps = (await api('/api/episodes?limit=12', { noAuthRedirect: true })).episodes; } catch (e) { return; }
    }
    state.now = pickNow(eps);
    const b = $('#tally');
    if (b) { b.dataset.state = lampState(state.now.state); b.innerHTML = tallyInner(state.now); }
    const m = $('#mlamp');
    if (m) m.dataset.state = lampState(state.now.state);
  }
  const openNow = () => { if (state.now.ep) openEpisode(state.now.ep.id); else location.hash = '#/episodes'; };

  // часы: 60 огней секунд по кругу и цифры как на табло; «Хронометр» — секундомер для записи (помнит себя после обновления страницы)
  const pad2 = n => String(n).padStart(2, '0');
  const sclk = { mode: 'time', start: 0, acc: 0, run: false };
  try { Object.assign(sclk, JSON.parse(localStorage.getItem('studio-chrono') || '{}')); } catch (e) { /* без памяти — с нуля */ }
  const saveClock = () => { try { localStorage.setItem('studio-chrono', JSON.stringify(sclk)); } catch (e) { /* не запомним */ } };
  function clockSVG() {
    const pt = (i, n, r) => { const a = i / n * 2 * Math.PI - Math.PI / 2; return `cx="${(100 + r * Math.cos(a)).toFixed(2)}" cy="${(100 + r * Math.sin(a)).toFixed(2)}"`; };
    let dots = '', hours = '';
    for (let i = 0; i < 60; i++) dots += `<circle ${pt(i, 60, 92)} r="${i % 5 ? 2.3 : 3.2}"/>`;
    for (let i = 0; i < 12; i++) hours += `<circle class="h" ${pt(i, 12, 79)} r="2.4"/>`;
    return `<svg viewBox="0 0 200 200" aria-hidden="true"><g class="ring">${dots}</g><g>${hours}</g></svg>`;
  }
  const elapsed = ms => { const t = Math.max(0, Math.floor(ms / 1000)), h = Math.floor(t / 3600);
    return (h ? h + ':' : '') + pad2(Math.floor(t / 60) % 60) + ':' + pad2(t % 60); };
  const ghost = txt => txt.replace(/\d/g, '8');
  let litUpTo = -1;
  function tick() {
    const now = new Date();
    const chrono = sclk.mode === 'chrono';
    const ms = sclk.acc + (sclk.run ? Date.now() - sclk.start : 0);
    const sec = chrono ? Math.floor(ms / 1000) % 60 : now.getSeconds();
    const box = $('#sclock');
    if (box) {
      if (box.dataset.mode !== sclk.mode) box.dataset.mode = sclk.mode;
      const dots = box.querySelectorAll('.ring circle');
      if (sec < litUpTo || litUpTo < 0) { dots.forEach(c => c.classList.remove('on')); litUpTo = -1; }
      for (let i = litUpTo + 1; i <= sec && i < dots.length; i++) dots[i].classList.add('on');
      litUpTo = sec;
      const main = chrono ? elapsed(ms) : pad2(now.getHours()) + ':' + pad2(now.getMinutes());
      const hm = $('#shm'), ss = $('#ss');
      if (hm.textContent !== main) { hm.textContent = main; hm.dataset.ghost = ghost(main); hm.style.fontSize = main.length > 5 ? '23px' : ''; }
      ss.textContent = chrono ? '' : pad2(sec);
      ss.classList.toggle('hidden', chrono);
      $('#sdate').textContent = chrono ? (sclk.run ? 'хронометр идёт — нажми на часы, чтобы остановить' : ms ? 'хронометр на паузе' : 'нажми на часы, чтобы пустить')
        : now.toLocaleDateString('ru-RU', { weekday: 'long', day: 'numeric', month: 'long' });
      box.querySelectorAll('[data-cm]').forEach(b => b.classList.toggle('on', b.dataset.cm === sclk.mode));
      const go = box.querySelector('[data-cc="go"]');
      if (go) go.textContent = sclk.run ? 'Стоп' : ms ? 'Дальше' : 'Старт';
    }
    const mh = $('#mhm');
    if (mh) { const t = pad2(now.getHours()) + ':' + pad2(now.getMinutes()) + ':' + pad2(now.getSeconds()); mh.textContent = t; }
    document.querySelectorAll('[data-since]').forEach(el => {
      const t = elapsed(Date.now() - Date.parse(el.dataset.since));
      el.textContent = t; el.dataset.ghost = ghost(t);
    });
  }
  function startClock() {
    clearTimeout(state.clockT); clearInterval(state.clockI);
    litUpTo = -1; tick();
    state.clockT = setTimeout(() => { tick(); state.clockI = setInterval(tick, 1000); }, 1005 - (Date.now() % 1000));
  }
  function chronoToggle() {
    if (sclk.run) { sclk.acc += Date.now() - sclk.start; sclk.run = false; }
    else { sclk.start = Date.now(); sclk.run = true; }
    saveClock(); tick();
  }
  function bindStudio() {
    const box = $('#sclock');
    if (box) {
      box.querySelectorAll('[data-cm]').forEach(b => b.addEventListener('click', () => { sclk.mode = b.dataset.cm; saveClock(); litUpTo = -1; tick(); }));
      box.querySelector('[data-cc="go"]').addEventListener('click', chronoToggle);
      box.querySelector('[data-cc="reset"]').addEventListener('click', () => { sclk.acc = 0; sclk.start = 0; sclk.run = false; saveClock(); litUpTo = -1; tick(); });
      $('#sdial').addEventListener('click', () => { if (sclk.mode === 'chrono') chronoToggle(); });
    }
    const tb = $('#tally');
    if (tb) tb.addEventListener('click', openNow);
    const mc = $('#mclock');
    if (mc) mc.addEventListener('click', openNow);
    document.querySelectorAll('[data-theme-set]').forEach(b => b.addEventListener('click', () => {
      if (window.studioTheme) window.studioTheme.set(b.dataset.themeSet);
      document.querySelectorAll('[data-theme-set]').forEach(x => x.classList.toggle('on', x === b));
    }));
    clearInterval(state.tallyTimer);
    state.tallyTimer = setInterval(() => { if (!document.hidden) refreshTally(); }, 60000);
    refreshTally();
    startClock();
  }

  // ---------- вход ----------
  function showLogin() {
    clearInterval(state.timer); clearInterval(state.tallyTimer); clearTimeout(state.clockT); clearInterval(state.clockI);
    $('#root').innerHTML = `
      <div class="login"><form class="card" id="lf" autocomplete="on">
        <div class="tally-plate" aria-hidden="true">ЭФИР</div>
        <div class="logo" style="padding:0"><div class="mark">${I.play}</div><div><b>Студия</b><span>Без сказок</span></div></div>
        <h1>Вход в студию</h1><p>Пульт конвейера: выпуски, запись, публикация.</p>
        <input class="input" name="login" placeholder="Логин" autocomplete="username" required>
        <input class="input" name="password" type="password" placeholder="Пароль" autocomplete="current-password" required>
        <button class="btn primary" type="submit">Войти</button>
        <div class="error" id="lerr"></div>
      </form></div>`;
    $('#lf').addEventListener('submit', async ev => {
      ev.preventDefault();
      const f = new FormData(ev.target);
      $('#lerr').textContent = '';
      try {
        await api('/api/login', { body: { login: f.get('login'), password: f.get('password') }, noAuthRedirect: true });
        const plate = $('#lf .tally-plate');  // табло загорается — и мы в студии
        if (plate) { plate.textContent = 'В ЭФИРЕ'; plate.dataset.state = 'live'; }
        setTimeout(boot, plate && !matchMedia('(prefers-reduced-motion: reduce)').matches ? 650 : 0);
      } catch (e) { $('#lerr').textContent = e.message; }
    });
  }

  // ---------- каркас ----------
  function shell() {
    const nav = NAV.map(([h, t, ic]) => `<a href="${h}" data-nav="${h}">${ic}<span>${t}</span>${h === '#/logs' ? '<i class="count hidden" data-errcount></i>' : ''}</a>`).join('');
    const tabs = NAV.filter(n => n[0] !== '#/sources').map(([h, t, ic]) => `<a href="${h}" data-nav="${h}">${ic}<span>${t}</span>${h === '#/logs' ? '<i class="count hidden" data-errcount></i>' : ''}</a>`).join('');
    const v = state.version || {};
    $('#root').innerHTML = `
      <div class="app">
        <aside class="side">
          <div class="logo"><div class="mark">${I.play}</div><div><b>Студия</b><span>Без сказок</span></div></div>
          <button class="tally" id="tally" type="button" data-state="idle" title="Открыть выпуск, который сейчас в работе">${tallyInner(state.now)}</button>
          <div class="sclock" id="sclock" data-mode="${sclk.mode}">
            <div class="sclock-dial" id="sdial">${clockSVG()}<div class="sclock-read">
              <span class="led" id="shm" data-ghost="88:88">--:--</span><span class="led s" id="ss" data-ghost="88">--</span></div></div>
            <div class="sclock-date" id="sdate"></div>
            <div class="sclock-tabs"><button type="button" data-cm="time">Время</button><button type="button" data-cm="chrono">Хронометр</button></div>
            <div class="sclock-ctl"><button type="button" class="go" data-cc="go">Старт</button><button type="button" data-cc="reset">Сброс</button></div>
          </div>
          <nav class="nav">${nav}</nav>
          <div class="side-foot">
            <div class="who"><span>${esc(state.user.name || state.user.login)}</span><button class="linkbtn" id="logout">Выйти</button></div>
            <div class="theme-sw" role="group" aria-label="Тема">${[['dark', 'Студия'], ['light', 'День'], ['auto', 'Авто']].map(([k, t]) =>
              `<button type="button" data-theme-set="${k}" class="${(window.studioTheme ? window.studioTheme.get() : 'dark') === k ? 'on' : ''}">${t}</button>`).join('')}</div>
            <div class="faint">версия ${esc(v.commit || 'dev')}</div>
          </div>
        </aside>
        <div class="main">
          <header class="top"><div class="logo"><div class="mark">${I.play}</div><div><b>Студия</b></div></div>
            <button class="mclock" id="mclock" type="button" title="Открыть выпуск, который сейчас в работе"><span class="mlamp" id="mlamp"></span><span class="led" id="mhm" data-ghost="88:88:88">--:--:--</span></button>
            <a class="btn small" href="#/sources" aria-label="Источники">${I.rss}</a></header>
          <div class="wrap" id="view"></div>
        </div>
      </div>
      <nav class="tabbar">${tabs}</nav>`;
    $('#logout').addEventListener('click', async () => { await api('/api/logout', { method: 'POST' }).catch(() => {}); showLogin(); });
    bindStudio();
  }

  function markNav() {
    const h = '#' + (location.hash.replace(/^#/, '').split('?')[0] || '/');
    document.querySelectorAll('[data-nav]').forEach(a => a.classList.toggle('on', a.dataset.nav === h || (a.dataset.nav !== '#/' && h.startsWith(a.dataset.nav + '/'))));
    document.querySelectorAll('[data-errcount]').forEach(el => { el.textContent = state.errors24; el.classList.toggle('hidden', !state.errors24); });
    const cur = document.querySelector('.tabbar a.on');  // на телефоне панель листается — держим открытый раздел на виду
    if (cur && cur.scrollIntoView) cur.scrollIntoView({ inline: 'nearest', block: 'nearest' });
  }

  const head = (title, sub, actions = '') => `<div class="head"><div><h1>${title}</h1>${sub ? `<p>${sub}</p>` : ''}</div><div class="actions">${actions}</div></div>`;
  const badge = (text, tone = '') => `<span class="badge ${tone}">${esc(text)}</span>`;
  const loading = () => `<div class="card"><div class="card-b"><div class="skel" style="width:40%"></div><br><div class="skel"></div><br><div class="skel" style="width:70%"></div></div></div>`;
  const failBox = msg => `<div class="card"><div class="empty"><b>Не получилось загрузить</b>${esc(msg)}</div></div>`;
  const reportBtn = `<a class="btn" href="/api/report/download?hours=24" download>${I.download}Скачать отчёт JSON</a>`;

  // ---------- боковая панель ----------
  function drawer(title, sub, body) {
    closeDrawer();
    const shade = document.createElement('div');
    shade.className = 'shade';
    const d = document.createElement('aside');
    d.className = 'drawer';
    d.innerHTML = `<div class="d-h"><div><h2>${title}</h2>${sub ? `<div class="muted" style="margin-top:4px">${sub}</div>` : ''}</div><button class="close" aria-label="Закрыть">×</button></div><div class="d-b">${body}</div>`;
    document.body.append(shade, d);
    shade.addEventListener('click', closeDrawer);
    d.querySelector('.close').addEventListener('click', closeDrawer);
    return d;
  }
  function closeDrawer() { document.querySelectorAll('.drawer,.shade').forEach(e => e.remove()); }
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });

  // ---------- «Сейчас в студии»: монитор и следующий шаг для самого важного выпуска ----------
  function onairHTML(list) {
    const now = pickNow(list);
    const e = now.ep;
    if (!e) {
      return `<div class="card onair"><div class="onair-mon" data-state="idle"><div class="onair-slate"><span class="led" data-ghost="88:88">00:00</span>
        <span>новых выпусков нет</span></div><span class="onair-tag"><i></i>Тихо</span></div>
        <div class="onair-info"><div class="onair-when">Сейчас в студии</div><h2>Тихо</h2>
        <p class="onair-next">Новый сценарий появится, когда бот получит /news или /topic. Новости из источников собираются сами каждые 30 минут.</p></div></div>`;
    }
    const thumb = e.preview_url && /\/final\.mp4(\?|$)/.test(e.preview_url) ? e.preview_url.replace(/final\.mp4(\?.*)?$/, 'thumb.jpg') : '';
    const plan = (e.minutes ? pad2(e.minutes) : '00') + ':00';
    const slate = (led, cap) => `<div class="onair-slate">${led}<span>${esc(cap)}</span></div>`;
    const planLed = `<span class="led" data-ghost="${ghost(plan)}">${plan}</span>`;
    const picture = cap => thumb ? `<img src="${esc(thumb)}" alt="" loading="lazy"><span class="onair-play">${I.play}</span>` : slate(planLed, cap);
    const more = `<button class="btn" type="button" data-onair="${esc(e.id)}">Подробнее</button>`;
    let screen, next, acts;
    if (now.state === 'cue') {
      screen = slate(planLed, `${e.kind === 'script' ? 'сценарий' : 'выпуск'} на ${e.minutes || '—'} мин` + (e.inserts_total ? `, вставки ${e.inserts_ok} из ${e.inserts_total}` : ''));
      next = 'Сценарий готов, вставки собраны. Открой суфлёр, запиши выпуск и положи файл в папку направления на Google Диске — монтаж начнётся сам.';
      acts = `<a class="btn primary" href="#/prompter/view?s=${encodeURIComponent(e.id)}">Открыть суфлёр</a>${more}`;
    } else if (now.state === 'busy') {
      screen = slate(`<span class="led" data-since="${esc(e.updated_at || e.created_at)}" data-ghost="88:88">00:00</span>`, 'идёт монтаж');
      next = 'Запись собирается: паузы, вставки, субтитры и шортсы. Превью придёт сюда и в Telegram.';
      acts = more;
    } else if (now.state === 'ready') {
      screen = picture('готов к проверке');
      next = 'Посмотри выпуск, проверь отмеченные места и опубликуй — у каждой площадки своя кнопка.';
      acts = `<button class="btn primary" type="button" data-onair="${esc(e.id)}">Проверить и опубликовать</button>`;
    } else if (now.state === 'live') {
      screen = picture('публикуется');
      next = 'Загружаем на площадки. Итог придёт в Telegram и появится в карточке выпуска.';
      acts = more;
    } else {
      screen = picture('опубликован');
      next = e.youtube_id ? 'Выпуск на площадках. Если на YouTube он с ограниченным доступом — открой его в YouTube Studio.' : 'Выпуск опубликован.';
      acts = (e.youtube_id ? `<a class="btn" href="https://youtu.be/${esc(e.youtube_id)}" target="_blank" rel="noopener">${I.yt}YouTube</a>` : '') + more;
    }
    return `<div class="card onair"><div class="onair-mon" data-state="${now.state}" data-onair="${esc(e.id)}">${screen}
        <span class="onair-tag"><i></i>${esc(TALLY[now.state].label)}</span></div>
      <div class="onair-info"><div class="onair-when">Сейчас в студии</div><h2>${esc(e.title || e.id)}</h2>
        <p class="onair-next">${next}</p><div class="actions">${acts}</div></div></div>`;
  }

  // ---------- Обзор ----------
  // «Что сделать сейчас»: короткий список дел из того, что видно на «Обзоре» — как входящие у больших сервисов
  function todoHTML(eps, errs, bal) {
    const items = [];
    const seen = new Set();
    for (const e of eps) {
      if (seen.has(e.id)) continue;
      seen.add(e.id);
      if (['inserts_ready', 'script_ready'].includes(e.status)) items.push([I.prompter, 'Записать выпуск', e.title,
        `<a class="btn small primary" href="#/prompter/view?s=${encodeURIComponent(e.id)}">Суфлёр</a>`]);
      else if (['preview_ready', 'partial'].includes(e.status)) items.push([I.film, 'Проверить и опубликовать', e.title,
        `<button class="btn small primary" data-todo-ep="${esc(e.id)}">Открыть</button>`]);
      else if (e.status === 'error') items.push([I.log, 'Выпуск с ошибкой', e.title, `<button class="btn small" data-todo-ep="${esc(e.id)}">Открыть</button>`]);
    }
    if (errs.length) items.push([I.log, 'Разобрать ошибки конвейера', `${errs.length} за сутки — в журнале видно, где и что сломалось`,
      `<a class="btn small" href="#/logs?view=errors">Журнал</a>`]);
    if (bal && bal.known && bal.low) items.push([I.coin, 'Пополнить баланс Claude', `осталось около ${money(bal.estimate)}`, `<a class="btn small" href="#/costs">Расходы</a>`]);
    return `<div class="card todo"><div class="card-h"><h2>Что сделать сейчас</h2>${items.length ? `<span class="faint">${items.length}</span>` : ''}</div>
      <div class="card-b flush">${items.length ? `<ul class="rows">${items.slice(0, 6).map(([ic, what, title, btn]) =>
        `<li><span class="todo-ic">${ic}</span><div class="grow"><div class="title">${esc(what)}</div><div class="meta">${esc(title || '')}</div></div>${btn}</li>`).join('')}</ul>`
        : `<div class="empty"><b>Дел нет</b>Новых выпусков на проверку нет, ошибок нет. Конвейер ждёт новостей.</div>`}</div></div>`;
  }

  async function pageOverview(view) {
    view.innerHTML = head('Обзор', 'Что происходит с конвейером прямо сейчас', reportBtn) + loading();
    let d;
    try { d = await api('/api/overview'); } catch (e) { view.innerHTML = head('Обзор', '', reportBtn) + failBox(e.message); return; }
    state.errors24 = (d.errors_24h || []).filter(e => !e.ack).length;
    markNav();
    const b = d.balance || {};
    const pct = b.known && b.baseline_usd > 0 ? Math.max(0, Math.min(100, b.estimate / b.baseline_usd * 100)) : 0;
    const balance = b.known
      ? `<div class="kpi card ${b.low ? 'bad' : ''}"><div class="label">Баланс Claude · оценка</div><div class="value num">${money(b.estimate)}</div>
          <div class="sub">предупрежу при ${money(b.threshold, 0)} · записано ${money(b.baseline_usd)} ${when(b.baseline_at)}</div>
          <div class="bar ${b.low ? 'low' : ''}"><i style="width:${pct}%"></i></div></div>`
      : `<div class="kpi card"><div class="label">Баланс Claude</div><div class="value" style="font-size:20px">не указан</div>
          <div class="sub"><a href="#/costs">Указать остаток</a> — и я предупрежу при $5</div></div>`;
    const c = d.costs || {};
    const allErrs = d.errors_24h || [];
    const errs = allErrs.filter(e => !e.ack);
    const acked = allErrs.length - errs.length;
    const last = errs[0];
    const s = d.server || {};
    const ok = (v, yes, no, warn) => v === true ? badge(yes, 'ok') : v === false ? badge(no, 'err') : badge(warn || 'нет данных', 'warn');
    // сторож сервера: запас памяти, процессора и диска (пики — за неделю замеров)
    const h = s.host || {}, wk = h.week || {}, vd = h.verdict || {};
    const nf = (x) => x == null ? '—' : String(x).replace('.', ',');
    const pc = (x) => x == null ? '—' : Math.round(x) + '%';
    const hostRows = h.ram_total_gb || h.cpu_cores ? `
            <dt>Запас</dt><dd>${badge({ tight: 'тесно', watch: 'следим' }[vd.level] || 'есть', { tight: 'err', watch: 'warn' }[vd.level] || 'ok')}
              ${vd.text && vd.text !== 'запас есть' ? `<span class="muted"> ${esc(vd.text)}</span>` : ''}</dd>
            <dt>Память</dt><dd class="num">${h.ram_total_gb ? `занято ${pc(h.ram_used_pct)} из ${nf(h.ram_total_gb)} ГБ${wk.ram_max != null ? ` · пик ${pc(wk.ram_max)}` : ''}${h.swap_used_gb ? ` · своп ${nf(h.swap_used_gb)} ГБ` : ''}` : '—'}</dd>
            <dt>Процессор</dt><dd class="num">${h.cpu_cores ? `${h.cpu_cores} ${plural(h.cpu_cores, 'ядро', 'ядра', 'ядер')} · сейчас ${pc(h.cpu_pct)}${wk.cpu_max != null ? ` · пик ${pc(wk.cpu_max)}` : ''}` : '—'}</dd>` : '';
    const diskLeft = h.disk_days_left != null ? ` · хватит на ~${h.disk_days_left} ${plural(h.disk_days_left, 'день', 'дня', 'дней')}` : '';
    refreshTally(d.episodes || []);
    view.innerHTML = head('Обзор', 'Что происходит с конвейером прямо сейчас', reportBtn) + onairHTML(d.episodes || []) + todoHTML(d.episodes || [], errs, b) + `
      <div class="grid kpis">
        ${balance}
        <div class="kpi card"><div class="label">Расходы за 30 дней</div><div class="value num">${money(c.d30)}</div>
          <div class="sub">сегодня ${money(c.today)} · за 7 дней ${money(c.d7)}</div></div>
        <div class="kpi card"><div class="label">Ждут записи</div><div class="value num">${d.waiting_scripts ?? '—'}</div>
          <div class="sub">${d.waiting_scripts ? 'сценарии готовы, вставки собраны' : 'готовых сценариев нет'}</div></div>
        <div class="kpi card ${errs.length ? 'bad' : 'good'}"><div class="label">Ошибки за сутки</div><div class="value num">${d.errors_note ? '—' : errs.length}</div>
          <div class="sub">${d.errors_note ? esc(d.errors_note) : last ? esc(last.workflow) + ' · ' + when(last.started_at) : 'всё спокойно'}${acked ? ` · ещё ${acked} разобрано` : ''}</div></div>
      </div>
      <div class="grid two">
        <div class="card"><div class="card-h"><h2>Последние выпуски</h2><a href="#/episodes">Все</a></div>
          <div class="card-b flush">${epRows(d.episodes || [])}</div></div>
        <div class="grid">
          <div class="card"><div class="card-h"><h2>Сервер</h2></div><div class="card-b"><dl class="kv">
            <dt>Монтаж</dt><dd>${s.montage_busy ? badge('занят', 'warn live') : badge('свободен', 'ok')}</dd>${hostRows}
            <dt>Диск</dt><dd class="num">${s.disk_free_gb != null ? nf(s.disk_free_gb) + ' ГБ свободно из ' + nf(s.disk_total_gb) + diskLeft : '—'}</dd>
            <dt>n8n</dt><dd>${ok(s.n8n, 'на связи', 'нет связи', 'нет ключа API')}</dd>
            <dt>Сервер монтажа</dt><dd>${ok(s.worker, 'на связи', 'нет связи')}</dd>
            <dt>Ключ Google</dt><dd>${ok(s.google_key, 'есть', 'нет')}</dd>
            <dt>Версия Студии</dt><dd class="mono">${esc((d.version || {}).commit || 'dev')}</dd>
          </dl></div></div>
          <div class="card"><div class="card-h"><h2>Ошибки</h2><a href="#/logs?view=errors">Журнал</a></div>
            <div class="card-b flush">${errs.length ? `<ul class="rows">${errs.slice(0, 4).map(r => runRow(r)).join('')}</ul>`
              : `<div class="empty"><b>Ошибок нет</b>за последние 24 часа</div>`}</div></div>
        </div>
      </div>`;
    bindRuns(view);
    bindEps(view);
    view.querySelectorAll('[data-onair]').forEach(el => el.addEventListener('click', () => openEpisode(el.dataset.onair)));
    view.querySelectorAll('[data-todo-ep]').forEach(el => el.addEventListener('click', () => openEpisode(el.dataset.todoEp)));
    tick();
  }

  // ---------- Выпуски ----------
  function epTags(e) {
    return `${badge(e.status_label || e.status, EP_TONE[e.status] || '')}${badge(e.kind === 'script' ? 'Сценарий' : 'Запись', 'plain')}${e.direction ? badge(e.direction_name || e.direction, 'plain') : ''}`;
  }
  function epMeta(e) {
    const parts = [e.kind === 'script' ? 'сценарий' : 'запись', when(e.created_at)];
    if (e.inserts_total) parts.push(`вставки ${e.inserts_ok}/${e.inserts_total}`);
    if (e.cost_usd) parts.push(money(e.cost_usd));
    return parts.map(p => `<span>${esc(p)}</span>`).join('');
  }
  function epRows(list) {
    if (!list.length) return `<div class="empty"><b>Выпусков пока нет</b>Отправь боту /topic или /news — сценарий появится здесь</div>`;
    return `<ul class="rows">${list.map(e => `<li class="click" data-ep="${esc(e.id)}"><div class="grow"><div class="title">${esc(e.title)}</div>
      <div class="meta">${epMeta(e)}</div></div><div>${badge(e.status_label || e.status, EP_TONE[e.status] || '')}</div></li>`).join('')}</ul>`;
  }
  function bindEps(root) {
    root.querySelectorAll('[data-ep]').forEach(el => el.addEventListener('click', ev => {
      if (ev.target.closest('a')) return;
      openEpisode(el.dataset.ep);
    }));
  }

  // доска по этапам — как у досок задач: где сейчас каждый выпуск и что с ним сделать
  const BOARD = [
    { t: 'Сценарии', st: ['script_ready', 'inserts_ready'], hint: 'ждут записи' },
    { t: 'Монтаж', st: ['recording', 'rendering', 'redo'], hint: 'сервер собирает' },
    { t: 'Проверка', st: ['preview_ready', 'partial'], hint: 'посмотри и реши' },
    { t: 'Публикация', st: ['publish_requested', 'publishing'], hint: 'уходит на площадки' },
    { t: 'Вышли', st: ['published'], hint: 'последние', max: 8 },
    { t: 'Ошибки', st: ['error'], hint: 'нужна помощь', hideEmpty: true },
  ];
  const EVIEW = 'studio.episodes.view';
  function boardCard(e, many) {
    const next = ['script_ready', 'inserts_ready'].includes(e.status) ? `<a class="btn small primary" href="#/prompter/view?s=${encodeURIComponent(e.id)}">Суфлёр</a>`
      : ['preview_ready', 'partial'].includes(e.status) ? `<button class="btn small primary">Проверить</button>`  // клик дойдёт до карточки
      : e.youtube_url ? `<a class="btn small" href="${esc(e.youtube_url)}" target="_blank" rel="noopener">YouTube</a>` : '';
    return `<div class="bd-card${EP_BUSY.includes(e.status) ? ' busy' : ''}" data-ep="${esc(e.id)}">
      <div class="bd-t">${esc(e.title || e.id)}</div>
      <div class="bd-m">${many && e.direction_name ? `<span>${esc(e.direction_name)}</span>` : ''}<span>${when(e.updated_at || e.created_at)}</span>
        ${EP_BUSY.includes(e.status) ? `<span class="bd-live">${esc(e.status_label)}</span>` : ''}</div>
      ${next ? `<div class="bd-f">${next}</div>` : ''}</div>`;
  }

  async function pageEpisodes(view, params) {
    const kind = params.get('kind') || '';
    const dir = params.get('dir') || '';
    let vmode = params.get('view');
    if (!['list', 'board'].includes(vmode)) { try { vmode = localStorage.getItem(EVIEW) || 'list'; } catch (e) { vmode = 'list'; } }
    try { localStorage.setItem(EVIEW, vmode); } catch (e) { /* без памяти — по умолчанию списком */ }
    const url = o => '#/episodes?' + new URLSearchParams(Object.entries(Object.assign({ kind, dir, view: vmode }, o)).filter(([, v]) => v)).toString();
    const seg = `<div class="seg">${[['', 'Все'], ['recording', 'Записи'], ['script', 'Сценарии']].map(([k, t]) =>
      `<button data-go="${esc(url({ kind: k }))}" class="${k === kind ? 'on' : ''}">${t}</button>`).join('')}</div>
      <div class="seg">${[['list', 'Списком'], ['board', 'По этапам']].map(([k, t]) => `<button data-go="${esc(url({ view: k }))}" class="${k === vmode ? 'on' : ''}">${t}</button>`).join('')}</div>`;
    view.innerHTML = head('Выпуски', 'Сценарии, записи и готовые видео — по всем направлениям', seg) + loading();
    view.querySelectorAll('[data-go]').forEach(b => b.addEventListener('click', () => { location.hash = b.dataset.go; }));
    let d;
    try { d = await api('/api/episodes?limit=100' + (kind ? '&kind=' + kind : '') + (dir ? '&direction=' + encodeURIComponent(dir) : '')); }
    catch (e) { view.lastElementChild.outerHTML = failBox(e.message); return; }
    const list = d.episodes || [];
    const dirs = d.directions || [];
    const many = dirs.length > 1 && !dir;
    const chips = dirs.length > 1 ? `<div class="dir-chips">${[{ id: '', name: 'Все направления', n: dirs.reduce((a, x) => a + x.n, 0) }, ...dirs].map(x =>
      `<a class="chip${x.id === dir ? ' on' : ''}" href="${esc(url({ dir: x.id }))}">${esc(x.name)}<span>${x.n}</span></a>`).join('')}</div>` : '';
    let body;
    if (!list.length) body = `<div class="card"><div class="empty"><b>Пусто</b>Здесь появятся сценарии и выпуски${dir ? ' этого направления' : ''}</div></div>`;
    else if (vmode === 'board') {
      const cols = BOARD.map(c => {
        const items = list.filter(e => c.st.includes(e.status));
        if (!items.length && c.hideEmpty) return '';
        return `<section class="bd-col"><div class="bd-h"><b>${c.t}</b><span class="faint">${items.length}</span></div><div class="bd-hint faint">${c.hint}</div>
          ${items.slice(0, c.max || 50).map(e => boardCard(e, many)).join('') || '<div class="bd-empty faint">пусто</div>'}</section>`;
      }).join('');
      const rest = list.filter(e => !BOARD.some(c => c.st.includes(e.status))).length;
      body = `<div class="board">${cols}</div>${rest ? `<div class="faint" style="margin-top:10px;font-size:12.5px">Не на доске: ${rest} — заменённые, отменённые и записанные сценарии. Они есть в виде «Списком».</div>` : ''}`;
    } else {
      body = `<div class="grid eps">${list.map(e => `<div class="card ep"><div class="tags">${epTags(e)}</div><h3>${esc(e.title)}</h3>
        <div class="meta">${epMeta(e)}</div>
        <div class="foot">
          ${e.preview_url ? `<a class="btn small primary" href="${esc(e.preview_url)}" target="_blank" rel="noopener">Смотреть</a>` : ''}
          ${e.youtube_url ? `<a class="btn small" href="${esc(e.youtube_url)}" target="_blank" rel="noopener">YouTube</a>` : ''}
          ${e.kind === 'script' ? `<a class="btn small" href="#/prompter/view?s=${encodeURIComponent(e.id)}">Суфлёр</a>` : ''}
          <button class="btn small" data-ep="${esc(e.id)}">Подробнее</button>
          ${EP_BUSY.includes(e.status) ? '' : `<button class="btn small icon ep-del" data-del="${esc(e.id)}" title="Удалить" aria-label="Удалить">${I.trash}</button>`}</div></div>`).join('')}</div>`;
    }
    view.lastElementChild.outerHTML = chips + body;
    bindEps(view);
    view.querySelectorAll('[data-del]').forEach(b => b.addEventListener('click', async () => {
      const e = list.find(x => x.id === b.dataset.del);
      if (e && await deleteEpisode(e.id, e.title, e.kind === 'script')) route();
    }));
  }

  // ---------- публикация: тексты для площадок и кнопки «Опубликовать» (тексты пишет Claude, правишь здесь) ----------
  const pubCnt = (n, lim) => lim ? `<span class="pub-cnt${n > lim ? ' over' : ''}">${n} / ${lim}</span>` : '';
  const pubFld = (path, label, val, o = {}) => `<label class="pub-f"><span><span class="pub-lbl">${label}</span>${pubCnt((val || '').length, o.lim)}</span>${o.area
    ? `<textarea class="input" rows="${o.rows || 3}" data-f="${esc(path)}"${o.lim ? ` data-lim="${o.lim}"` : ''}>${esc(val || '')}</textarea>`
    : `<input class="input" data-f="${esc(path)}"${o.lim ? ` data-lim="${o.lim}"` : ''} value="${esc(val || '')}">`}</label>`;
  const pubPost = (i, val, lim) => `<div class="pub-post">${pubFld('threads.' + i, 'Пост ' + (i + 1), val, { area: true, rows: 3, lim })}
    <button class="btn small icon" data-thdel title="Убрать пост" aria-label="Убрать пост">×</button></div>`;
  function pubSection(e) {
    const p = e.pub;
    if (!p || (!p.texts && !p.can_write)) return '';
    const head = `<div class="section-t">Публикация</div>`;
    if (!p.texts) return head + `<div class="note">${p.video_ready ? 'Тексты для площадок Claude пишет сам сразу после монтажа. Если их долго нет — нажми кнопку.'
      : 'Тексты для площадок появятся сами после монтажа. Можно написать уже сейчас — по сценарию.'}
      <div style="margin-top:10px"><button class="btn primary" data-pubgen>Написать тексты</button></div></div>`;
    const t = p.texts, L = p.limits || {}, pd = p.published || {}, soc = (e.video && e.video.social) || {};
    const ctags = (p.channel_tags || []).join(' ');
    const tagStr = a => (a || []).join(' ');
    const card = (part, title, body, foot) => `<div class="pub-card" data-part="${part}"><div class="pub-h"><b>${title}</b>
      <button class="btn small" data-regen="${part}" title="Claude перепишет только эту часть">${I.refresh}Переписать</button></div>${body}${foot ? `<div class="pub-foot">${foot}</div>` : ''}</div>`;
    const yt = t.youtube || {};
    let ytFoot;
    if (pd.youtube && pd.youtube.url) ytFoot = `<span class="dot ok"></span><a href="${esc(pd.youtube.url)}" target="_blank" rel="noopener">Выпуск на YouTube</a>
      <span class="faint">если доступ ограниченный — открой его в YouTube Studio</span>`;
    else if (e.status === 'publish_requested' || e.status === 'publishing') ytFoot = `<span class="faint">Загружается на YouTube — итог придёт в Telegram…</span>`;
    else if ((e.actions || []).includes('publish')) ytFoot = `<button class="btn primary" data-pubto="youtube">Опубликовать на YouTube</button><span class="faint">выпуск и шортсы, доступ — как в направлении</span>`;
    else ytFoot = `<span class="faint">${p.video_ready ? 'Опубликовать можно, когда выпуск ждёт проверки' : 'Кнопка появится после монтажа'}</span>`;
    const ytCard = card('youtube', 'YouTube · выпуск',
      pubFld('youtube.title', 'Заголовок', yt.title, { lim: L.yt_title }) +
      pubFld('youtube.description', 'Описание', yt.description, { area: true, rows: 5, lim: L.yt_desc }) +
      pubFld('youtube.hashtags', 'Хэштеги по темам', tagStr(yt.hashtags)) +
      `<div class="faint pub-hint">Всегда добавятся: ${esc(ctags || '— задай в «Направлениях»')}. Главы, источники и авторы вставок допишутся сами.</div>`, ytFoot);
    const shs = p.shorts || [];
    const shBody = shs.length ? shs.map(s => {
      const x = (t.shorts || {})[s.name] || {};
      const link = pd.youtube && pd.youtube.shorts && pd.youtube.shorts[s.name];
      const tgLink = ((pd.telegram || {}).shorts || {})[s.name];
      const tgOn = (p.telegram || {}).connected && s.file && p.video_ready;
      return `<div class="pub-short"><div class="pub-h"><b>${esc(x.title || s.title || s.name)}</b><span class="pub-btns">
        ${s.file ? `<a class="btn small" href="/api/episodes/${encodeURIComponent(e.id)}/file/${encodeURIComponent(s.name)}" download>${I.download}Скачать</a>` : ''}
        ${tgLink ? `<a class="btn small" href="${esc(tgLink)}" target="_blank" rel="noopener">${I.tg}В Telegram ✓</a>`
          : tgOn ? `<button class="btn small" data-tgshort="${esc(s.name)}" data-tgtitle="${esc(x.title || s.title || s.name)}">${I.tg}В Telegram</button>` : ''}
        <button class="btn small" data-copytt="${esc(s.name)}">${I.copy}Подпись для TikTok</button></span></div>
        ${pubFld(`shorts.${s.name}.title`, 'Заголовок на YouTube', x.title, { lim: L.short_title })}
        ${pubFld(`shorts.${s.name}.description`, 'Описание на YouTube', x.description, { area: true, rows: 2 })}
        ${pubFld(`shorts.${s.name}.tiktok`, 'Подпись для TikTok', x.tiktok, { area: true, rows: 2 })}
        ${pubFld(`shorts.${s.name}.hashtags`, 'Хэштеги', tagStr(x.hashtags))}
        ${link ? `<div class="pub-foot"><span class="dot ok"></span><a href="${esc(link)}" target="_blank" rel="noopener">Шортс на YouTube</a></div>` : ''}</div>`;
    }).join('') : `<div class="faint">Шортсов в этом выпуске нет.</div>`;
    const shCard = card('shorts', 'Шортсы — YouTube и TikTok', `<div class="faint pub-hint">На YouTube шортсы уходят вместе с выпуском, в описание добавится ссылка на полный выпуск.
      В TikTok выкладываешь сам: «Скачать» и «Подпись для TikTok» (текст с хэштегами — в буфер обмена).</div>` + shBody);
    const fb = pd.facebook || {};
    const fbErr = soc.facebook && !soc.facebook.ok ? soc.facebook.error : '';
    let fbFoot;
    if (fb.url) fbFoot = `<span class="dot ok"></span><a href="${esc(fb.url)}" target="_blank" rel="noopener">Опубликовано в Facebook</a>`;
    else if (soc.pending) fbFoot = `<span class="faint">Публикуется в фоне — длинное видео грузится несколько минут…</span>`;
    else if (p.video_ready) fbFoot = `<button class="btn primary" data-pubto="facebook">${fbErr ? 'Повторить' : 'Опубликовать в Facebook'}</button>`
      + (fbErr ? `<span class="pub-err">${esc(fbErr)}</span>` : `<span class="faint">выйдет сразу, для всех</span>`);
    else fbFoot = `<span class="faint">Кнопка появится после монтажа</span>`;
    const fbCard = card('facebook', 'Facebook · видео на страницу',
      pubFld('facebook.text', 'Текст над видео', (t.facebook || {}).text, { area: true, rows: 3 }) +
      `<div class="faint pub-hint">Заголовок — как у YouTube. Допишутся главы, источники и хэштеги: ${esc([ctags, tagStr(yt.hashtags)].filter(Boolean).join(' '))}.</div>`, fbFoot);
    const th = pd.threads || {};
    const posts = t.threads || [];
    const thErr = soc.threads && !soc.threads.ok ? soc.threads.error : '';
    let thFoot;
    if (th.id && th.posted >= posts.length) thFoot = `<span class="dot ok"></span>${th.url ? `<a href="${esc(th.url)}" target="_blank" rel="noopener">Опубликовано в Threads</a>` : 'Опубликовано в Threads'}`;
    else if (soc.pending) thFoot = `<span class="faint">Публикуется…</span>`;
    else if (!p.video_ready) thFoot = `<span class="faint">Кнопка появится после монтажа</span>`;
    else thFoot = `<button class="btn primary" data-pubto="threads">${th.posted ? 'Продолжить цепочку' : thErr ? 'Повторить' : 'Опубликовать в Threads'}</button>`
      + (thErr ? `<span class="pub-err">${esc(thErr)}</span>`
        : `<span class="faint">${th.posted ? `вышло ${th.posted} из ${posts.length} — продолжу с места`
          : fb.url ? 'к первому посту прикрепится ссылка на видео в Facebook' : 'ссылка на видео прикрепится, если выпуск уже в Facebook — опубликуй его первым'}</span>`);
    const thCard = card('threads', 'Threads · цепочка постов', `<div class="pub-posts">${posts.map((x, i) => pubPost(i, x, L.th_post)).join('')}</div>
      <div><button class="btn small" data-thadd>+ пост</button></div>`, thFoot);
    const tgS = p.telegram || {}, tgPd = pd.telegram || {};
    const tgT = t.telegram || { text: (t.facebook || {}).text || '', link: 'auto', fallback: true };
    const tgErr = soc.telegram && !soc.telegram.ok ? soc.telegram.error : '';
    const LNK = { youtube: 'YouTube', facebook: 'Facebook', none: 'без ссылки' };
    const lk = tgS.links || {};
    let tgFoot;
    if (tgPd.url) tgFoot = `<span class="dot ok"></span><a href="${esc(tgPd.url)}" target="_blank" rel="noopener">Опубликовано в Telegram</a>`;
    else if (!tgS.connected) tgFoot = `<span class="faint">Сначала подключи канал: <a href="#/connections">«Подключения»</a> → Telegram</span>`;
    else if (!p.video_ready) tgFoot = `<span class="faint">Кнопка появится после монтажа</span>`;
    else tgFoot = `<button class="btn primary" data-pubto="telegram">${tgErr ? 'Повторить' : 'Опубликовать в Telegram'}</button>`
      + (tgErr ? `<span class="pub-err">${esc(tgErr)}</span>` : `<span class="faint">выйдет сразу в канал${tgS.chat ? ' «' + esc(tgS.chat) + '»' : ''}</span>`);
    const tgCard = card('telegram', 'Telegram · пост в канал',
      pubFld('telegram.text', 'Текст поста', tgT.text, { area: true, rows: 4, lim: L.tg }) +
      `<label class="pub-f"><span><span class="pub-lbl">Ссылка в посте</span></span><select class="input" data-f="telegram.link">${[
        ['auto', 'сама: ' + LNK[tgS.auto || 'none']], ['youtube', 'YouTube' + (lk.youtube ? (lk.youtube_open ? '' : ' (сейчас доступ ограниченный)') : ' — выпуска там ещё нет')],
        ['facebook', 'Facebook' + (lk.facebook ? '' : ' — выпуска там ещё нет')], ['none', 'без ссылки']].map(([k, v]) =>
        `<option value="${k}"${(tgT.link || 'auto') === k ? ' selected' : ''}>${esc(v)}</option>`).join('')}</select></label>` +
      `<div class="faint pub-hint">В посте: обложка выпуска, заголовок как у YouTube, этот текст, ссылка и хэштеги: ${esc([ctags, tagStr(yt.hashtags)].filter(Boolean).join(' '))}.
        ${tgT.fallback ? 'Текст пока взят из Facebook — поправь под Telegram и сохрани.' : ''}</div>`, tgFoot);
    const who = [t.generated_at ? `написал Claude ${dt(t.generated_at)}` : '', t.edited_at ? `правил ${esc(t.edited_by || '')} ${dt(t.edited_at)}` : ''].filter(Boolean).join(' · ');
    return head + `<div class="pub" data-pub>${ytCard}${shCard}${fbCard}${thCard}${tgCard}
      <div class="pub-save"><button class="btn primary" data-pubsave disabled>Сохранить правки</button>
        <button class="btn" data-pubgen>Переписать всё</button><span class="faint">${who}</span></div></div>`;
  }
  function bindPub(box, e, id) {
    const base = '/api/episodes/' + encodeURIComponent(id);
    const root = box.querySelector('[data-pub]');
    box.querySelectorAll('[data-pubgen]').forEach(b => b.addEventListener('click', async () => {
      if (root && !confirm(root.dataset.dirty ? 'Несохранённые правки пропадут. Переписать все тексты?' : 'Claude перепишет все тексты заново — твои правки пропадут. Переписать?')) return;
      const was = b.innerHTML;
      b.disabled = true; b.textContent = 'Claude пишет… до минуты';
      try { await api(base + '/pub/generate', { body: {} }); toast('Тексты готовы'); openEpisode(id); }
      catch (err) { toast(err.message, true); b.disabled = false; b.innerHTML = was; }
    }));
    if (!root) return;
    const saveBtn = root.querySelector('[data-pubsave]');
    const mark = () => { root.dataset.dirty = '1'; saveBtn.disabled = false; };
    const count = el => {
      const c = el.closest('.pub-f').querySelector('.pub-cnt'), lim = +el.dataset.lim;
      if (c && lim) { c.textContent = el.value.length + ' / ' + lim; c.classList.toggle('over', el.value.length > lim); }
    };
    const renum = () => root.querySelectorAll('.pub-post').forEach((el, i) => { el.querySelector('.pub-lbl').textContent = 'Пост ' + (i + 1); });
    root.addEventListener('input', ev => { if (ev.target.matches('[data-f]')) { mark(); count(ev.target); } });
    root.addEventListener('click', ev => {
      const del = ev.target.closest('[data-thdel]');
      if (del) { del.closest('.pub-post').remove(); renum(); mark(); }
    });
    root.querySelector('[data-thadd]').addEventListener('click', () => {
      const wrap = root.querySelector('.pub-posts');
      wrap.insertAdjacentHTML('beforeend', pubPost(wrap.children.length, '', (e.pub.limits || {}).th_post));
      wrap.lastElementChild.querySelector('textarea').focus();
      mark();
    });
    const collect = () => {
      const out = { youtube: {}, shorts: {}, facebook: {}, threads: [], telegram: {} };
      root.querySelectorAll('[data-f]').forEach(el => {
        const [a, b, c] = el.dataset.f.split('.');
        if (a === 'threads') { if (el.value.trim()) out.threads.push(el.value); }
        else if (a === 'shorts') (out.shorts[b] = out.shorts[b] || {})[c] = el.value;
        else out[a][b] = el.value;
      });
      return out;
    };
    const save = async () => { await api(base + '/pub', { method: 'PUT', body: collect() }); delete root.dataset.dirty; saveBtn.disabled = true; };
    saveBtn.addEventListener('click', async () => {
      saveBtn.disabled = true;
      try { await save(); toast('Сохранено'); } catch (err) { toast(err.message, true); saveBtn.disabled = false; }
    });
    root.querySelectorAll('[data-regen]').forEach(b => b.addEventListener('click', async () => {
      if (root.dataset.dirty && !confirm('Несохранённые правки пропадут. Переписать эту часть?')) return;
      b.disabled = true; b.textContent = 'пишет…';
      try { await api(base + '/pub/generate', { body: { part: b.dataset.regen } }); toast('Переписано'); openEpisode(id); }
      catch (err) { toast(err.message, true); b.disabled = false; b.innerHTML = I.refresh + 'Переписать'; }
    }));
    root.querySelectorAll('[data-copytt]').forEach(b => b.addEventListener('click', () => {
      const n = b.dataset.copytt;
      const v = f => ((root.querySelector(`[data-f="shorts.${n}.${f}"]`) || {}).value || '').trim();
      const own = v('hashtags').split(/[\s,;]+/).filter(Boolean).map(x => x.startsWith('#') ? x : '#' + x);
      const tags = [...new Set([...(e.pub.channel_tags || []), ...own])];
      copyText([v('tiktok'), tags.join(' ')].filter(Boolean).join('\n\n'));
    }));
    const ASK = {
      youtube: 'Загрузить выпуск и шортсы на YouTube? Доступ — как в направлении (сейчас «ограниченный»: откроешь сам в YouTube Studio).',
      facebook: 'Опубликовать выпуск в Facebook? Видео выйдет сразу, для всех.',
      threads: 'Опубликовать цепочку в Threads? Посты выйдут сразу, для всех.',
      telegram: 'Опубликовать пост о выпуске в Telegram-канал? Он выйдет сразу — его увидят подписчики.',
    };
    root.querySelectorAll('[data-pubto]').forEach(b => b.addEventListener('click', async () => {
      const pl = b.dataset.pubto;
      if (!confirm(ASK[pl])) return;
      b.disabled = true;
      try {
        if (root.dataset.dirty) await save();
        const r = await api(base + '/publish/' + pl, { body: {} });
        toast(pl === 'youtube' ? 'Отправил на YouTube — начнётся в течение минуты'
          : pl === 'telegram' ? (r && r.again ? 'Этот пост уже в канале' : 'Опубликовано в Telegram') : 'Публикую — итог придёт в Telegram и появится здесь');
        openEpisode(id);
      } catch (err) { toast(err.message, true); b.disabled = false; if (pl === 'telegram') openEpisode(id); }
    }));
    root.querySelectorAll('[data-tgshort]').forEach(b => b.addEventListener('click', async () => {
      if (!confirm(`Отправить шортс «${b.dataset.tgtitle}» в Telegram-канал? Он выйдет сразу — его увидят подписчики.`)) return;
      b.disabled = true;
      const was = b.innerHTML;
      b.textContent = 'отправляю…';
      try {
        if (root.dataset.dirty) await save();
        const r = await api(base + '/publish/telegram', { body: { short: b.dataset.tgshort } });
        toast(r && r.again ? 'Этот шортс уже в канале' : 'Шортс в Telegram'); openEpisode(id);
      } catch (err) { toast(err.message, true); b.disabled = false; b.innerHTML = was; }
    }));
  }

  // ---------- монтажный стол: поправить вставки и пересобрать без пересъёмки ----------
  const MT_KIND = { screenshot: 'Скриншот', source_media: 'Медиа из источника', card: 'Карточка', quote: 'Цитата', number: 'Цифра',
    map: 'Карта', diagram: 'Схема', stock: 'Сток', wikimedia: 'Архивное фото', ai_image: 'Картинка ИИ' };
  function bindMontage(box, id, vid) {
    const det = box.querySelector('details.mt');
    if (!det) return null;
    const b = det.querySelector('.mt-b');
    let ready = null, d = null;
    const load = () => ready || (ready = api('/api/episodes/' + encodeURIComponent(id) + '/montage')
      .then(x => { d = x; renderMontage(det, b, d, id, vid); return d; })
      .catch(err => { ready = null; b.innerHTML = failBox(err.message); throw err; }));
    det.addEventListener('toggle', () => { if (det.open) load().catch(() => {}); });
    if (det.open) load().catch(() => {});
    const onScreen = ms => (d.inserts || []).find(it => ms >= it.at_ms && ms < it.at_ms + it.dur_ms);
    const show = async pick => {  // открыть стол и подсветить нужную строку
      det.open = true;
      try { await load(); } catch (x) { return; }
      const it = pick();
      const li = it && b.querySelector(`.mt-row[data-i="${it.i}"]`);
      if (!li) { toast('Этой вставки в монтаже нет — возможно, она не встала', true); return; }
      li.scrollIntoView({ behavior: 'smooth', block: 'center' });
      li.classList.remove('flash');
      void li.offsetWidth;
      li.classList.add('flash');
    };
    if (vid) {  // пауза на вставке — под плеером кнопка «Поправить»
      const hint = document.createElement('div');
      hint.className = 'mt-now';
      hint.hidden = true;
      vid.after(hint);
      const onPause = async () => {
        if (!vid.paused) return;
        try { await load(); } catch (x) { return; }
        const it = vid.paused && onScreen(vid.currentTime * 1000);
        if (!it) { hint.hidden = true; return; }
        hint.innerHTML = `<span>На экране вставка ${it.marker ? '№' + esc(it.marker) + ' · ' : ''}${esc(it.badge || MT_KIND[it.kind] || 'вставка')}</span>
          <button class="btn small" data-mt-fix="${it.i}">Поправить</button>`;
        hint.hidden = false;
      };
      vid.addEventListener('pause', onPause);
      vid.addEventListener('seeked', onPause);
      vid.addEventListener('play', () => { hint.hidden = true; });
      hint.addEventListener('click', ev => {
        const btn = ev.target.closest('[data-mt-fix]');
        if (btn) show(() => d.inserts.find(it => it.i === Number(btn.dataset.mtFix)));
      });
    }
    return { focus: (marker, ms) => show(() => d.inserts.find(it => String(it.marker) === String(marker)) || onScreen(ms)) };
  }

  function renderMontage(det, b, d, id, vid) {
    const ed = {};  // правки: номер вставки → что поменяли
    const byI = {};
    (d.inserts || []).forEach(it => { byI[it.i] = it; });
    const cur = it => Object.assign({}, it, ed[it.i] || {});
    const maxAt = c => (d.total_ms ? Math.max(0, d.total_ms - c.dur_ms) : Infinity);
    const host = u => { try { return new URL(u).hostname.replace(/^www\./, ''); } catch (x) { return u; } };
    const sec = ms => (Math.round(ms / 100) / 10).toString().replace('.', ',') + ' с';
    const job = d.job || {};
    const running = d.status === 'rendering' && job.status === 'running';
    const can = d.can_edit;
    const row = it => {
      const c = cur(it);
      const thumb = it.asset ? (it.video ? `<video src="${esc(it.asset)}#t=0.5" muted preload="metadata" playsinline></video>`
        : `<img src="${esc(it.asset)}" alt="" loading="lazy">`) : '<span class="mt-nofile">файла нет</span>';
      const rep = c.replace ? (c.replace.url ? 'скрин ' + host(c.replace.url) : 'файл ' + c.replace.fname) : '';
      const unsure = it.conf != null && it.conf < 0.8 && !ed[it.i];
      const own = ed[it.i] && ed[it.i].badge !== undefined;  // подпись поменяли руками
      const badge = own ? ed[it.i].badge : c.replace ? '' : it.badge || '';
      const label = badge ? esc(badge) : own ? '<i>без подписи</i>'
        : c.replace ? (c.replace.url ? '<i>подпись со скрина</i>' : '<i>без подписи</i>') : esc(MT_KIND[it.kind] || it.kind || 'вставка');
      return `<li class="mt-row${c.remove ? ' rm' : ''}${ed[it.i] ? ' chg' : ''}" data-i="${it.i}">
        <button class="mt-thumb" data-mt-seek="${c.at_ms}" title="Перемотать к вставке">${thumb}</button>
        <div class="mt-info">
          <div class="title">${it.marker ? '№' + esc(it.marker) + ' · ' : ''}<button class="mt-tc" data-mt-seek="${c.at_ms}">${tc(c.at_ms)}</button> · ${sec(c.dur_ms)}${c.layout === 'full' ? ' · без ведущего' : ''}</div>
          <div class="meta">${can ? `<button class="mt-badge" data-mt="badge" title="Поправить подпись на кадре">${label}</button>` : label}${rep ? ' → <b>' + esc(rep) + '</b>' : it.replaced && !ed[it.i] ? ' · заменена' : it.edited && !ed[it.i] ? ' · правлена' : ''}${c.remove ? ' · <b>уберу</b>' : ''}${unsure ? ' · <span class="warntxt">проверь место</span>' : ''}</div>
        </div>
        ${can ? `<div class="mt-act">
          <button class="btn small" data-mt="earlier" title="На секунду раньше">−1 с</button><button class="btn small" data-mt="later" title="На секунду позже">+1 с</button>
          <button class="btn small" data-mt="shorter" title="На секунду короче">короче</button><button class="btn small" data-mt="longer" title="На секунду длиннее">длиннее</button>
          <button class="btn small" data-mt="pip" title="Ведущий в углу поверх вставки">${c.layout === 'full' ? 'ведущий: нет' : 'ведущий: в углу'}</button>
          <button class="btn small" data-mt="replace">Заменить</button>
          <button class="btn small${c.remove ? '' : ' danger'}" data-mt="remove">${c.remove ? 'Вернуть' : 'Убрать'}</button></div>
        <div class="mt-rep" hidden>
          <label class="mt-field">Подпись на кадре<input class="input" data-mt-badge maxlength="90" value="${esc(badge)}"
            placeholder="${c.replace && c.replace.url ? 'подпись со скрина: ' + esc(host(c.replace.url)) : 'без подписи'}"></label>
          <div class="mt-rep-row">
            <input class="input" data-mt-url placeholder="Ссылка на страницу — сделаю её скрин" value="${esc(c.replace && c.replace.url || '')}">
            <button class="btn small" data-mt="rep-url">Скрин страницы</button>
            <label class="btn small">Свой файл<input type="file" data-mt-file hidden accept="image/png,image/jpeg,image/webp,video/mp4,video/quicktime,video/webm"></label>
            ${c.replace ? '<button class="btn small" data-mt="rep-undo">Не заменять</button>' : ''}</div></div>` : ''}
      </li>`;
    };
    const changes = () => Object.entries(ed).map(([i, x]) => (x.remove ? { i: Number(i), remove: true } : { i: Number(i), ...x }));
    const head = running ? `<div class="note">Пересобираю${job.revert ? ' как было' : job.only_shorts ? ` шортсы с исправленными субтитрами (${job.changes || 0})` : ` с правками (${job.changes || 0})`} — начато ${dt(job.at)}. ${job.only_shorts ? 'Шортсы заменятся сами' : 'Видео заменится само'}, итог придёт в Telegram.</div>`
      : !can ? `<div class="note">${esc(d.reason)}</div>`
      : job.status === 'error' ? `<div class="note warnnote">${job.partial ? 'Видео пересобрано, но шортсы или обложка могли остаться старыми' : 'Последняя пересборка не удалась'}: ${esc(job.error || '')}.${job.partial ? '' : ' Прежний вариант на месте.'}</div>`
      : `<div class="faint mt-help">Нажми на картинку или время — видео перемотается к вставке. Поставь видео на паузу на неудачной вставке — под плеером появится «Поправить». Правки копятся, пересборка одна на все.${job.status === 'done' ? ` Последняя пересборка: ${dt(job.done_at)}.` : ''}</div>`;
    const subsOn = can && d.subs && (d.subs.shorts || d.subs.srt);
    b.innerHTML = `${head}
      ${subsOn ? `<div class="mt-subs">
        <div class="mt-subs-h">Исправить слово в субтитрах <span class="faint">${d.subs.shorts ? 'шортсов (они вшиты в видео) и выпуска' : 'выпуска'}</span></div>
        <div class="mt-subs-f"><input class="input" data-mt-sf maxlength="60" placeholder="Как сейчас: Ефримов">
          <span class="mt-arrow" aria-hidden="true">→</span>
          <input class="input" data-mt-st maxlength="60" placeholder="Как надо: Ефремов">
          <button class="btn small" data-mt-sfind>Найти</button></div>
        <div class="mt-subs-res" hidden></div><ul class="mt-subs-list"></ul></div>` : ''}
      ${(d.inserts || []).length ? `<ul class="mt-list">${d.inserts.map(row).join('')}</ul>` : '<div class="faint">Вставок в этом монтаже нет.</div>'}
      ${can ? `<div class="mt-foot"><span class="mt-count faint">Правок нет</span>
        <button class="btn" data-mt-reset hidden>Сбросить</button>
        ${d.edited ? '<button class="btn" data-mt-revert>Вернуть как было</button>' : ''}
        <button class="btn primary" data-mt-go disabled>Пересобрать с правками</button></div>` : ''}`;
    const list = b.querySelector('.mt-list');
    const subsEd = [];  // исправления субтитров: {from, to}
    const foot = () => {
      const n = Object.keys(ed).length + subsEd.length;
      const cnt = b.querySelector('.mt-count');
      if (!cnt) return;
      cnt.textContent = n ? `Правок: ${n}` : 'Правок нет';
      b.querySelector('[data-mt-go]').disabled = !n;
      b.querySelector('[data-mt-reset]').hidden = !n;
    };
    const redraw = i => {
      const li = list.querySelector(`.mt-row[data-i="${i}"]`);
      const rep = li && li.querySelector('.mt-rep');
      const open = !!rep && !rep.hidden;
      li.outerHTML = row(byI[i]);
      if (open) list.querySelector(`.mt-row[data-i="${i}"] .mt-rep`).hidden = false;
      foot();
    };
    const setEd = (i, x) => {  // правка, совпадающая с исходным, — не правка
      const it = byI[i];
      if (x.at_ms === it.at_ms) delete x.at_ms;
      if (x.dur_ms === it.dur_ms) delete x.dur_ms;
      if (x.layout === it.layout) delete x.layout;
      if (x.badge !== undefined && x.badge === (it.badge || '') && !x.replace) delete x.badge;
      if (!x.remove) delete x.remove;
      if (Object.keys(x).length) ed[i] = x; else delete ed[i];
    };
    const seek = ms => {
      if (!vid) return;
      vid.currentTime = Math.max(0, Number(ms) / 1000 - 1);
      vid.play().catch(() => {});
      vid.scrollIntoView({ behavior: 'smooth', block: 'center' });
    };
    if (list) {
      list.addEventListener('click', ev => {
        const sk = ev.target.closest('[data-mt-seek]');
        if (sk) { seek(sk.dataset.mtSeek); return; }
        const btn = ev.target.closest('[data-mt]');
        if (!btn) return;
        const i = Number(btn.closest('.mt-row').dataset.i);
        const it = byI[i], c = cur(it), x = Object.assign({}, ed[i] || {});
        switch (btn.dataset.mt) {
          case 'earlier': x.at_ms = Math.max(0, c.at_ms - 1000); break;
          case 'later': x.at_ms = Math.min(maxAt(c), c.at_ms + 1000); break;
          case 'shorter': x.dur_ms = Math.max(d.limits.dur_min, c.dur_ms - 1000); break;
          case 'longer': x.dur_ms = Math.min(d.limits.dur_max, c.dur_ms + 1000); break;
          case 'pip': x.layout = c.layout === 'full' ? 'full_pip' : 'full'; break;
          case 'remove': x.remove = !c.remove; break;
          case 'replace': case 'badge': {
            const r = btn.closest('.mt-row').querySelector('.mt-rep');
            r.hidden = btn.dataset.mt === 'replace' ? !r.hidden : false;
            if (!r.hidden) r.querySelector(btn.dataset.mt === 'badge' ? '[data-mt-badge]' : '[data-mt-url]').focus();
            return;
          }
          case 'rep-url': {
            const u = btn.closest('.mt-row').querySelector('[data-mt-url]').value.trim();
            if (!/^https?:\/\//i.test(u)) { toast('Нужна ссылка на страницу — начинается с https://', true); return; }
            x.replace = { url: u };
            break;
          }
          case 'rep-undo': delete x.replace; break;
          default: return;
        }
        setEd(i, x);
        redraw(i);
      });
      list.addEventListener('change', ev => {
        const bd = ev.target.closest('[data-mt-badge]');
        if (bd) {
          const i = Number(bd.closest('.mt-row').dataset.i), x = Object.assign({}, ed[i] || {});
          x.badge = bd.value.replace(/\s+/g, ' ').trim();
          setEd(i, x);
          redraw(i);
          return;
        }
        const inp = ev.target.closest('[data-mt-file]');
        if (!inp || !inp.files || !inp.files[0]) return;
        const f = inp.files[0], i = Number(inp.closest('.mt-row').dataset.i);
        if (f.size > d.limits.upload_mb * 1048576) { toast(`Файл больше ${d.limits.upload_mb} МБ — возьми поменьше`, true); return; }
        const ext = (f.name.split('.').pop() || '').toLowerCase();
        const rd = new FileReader();
        rd.onload = () => { const x = Object.assign({}, ed[i] || {}); x.replace = { b64: String(rd.result), ext, fname: f.name }; setEd(i, x); redraw(i); };
        rd.onerror = () => toast('Файл не прочитался', true);
        rd.readAsDataURL(f);
      });
    }
    const sb = b.querySelector('.mt-subs');
    if (sb) {
      const sf = sb.querySelector('[data-mt-sf]'), st = sb.querySelector('[data-mt-st]'), res = sb.querySelector('.mt-subs-res');
      const ul = sb.querySelector('.mt-subs-list');
      const chips = () => {
        ul.innerHTML = subsEd.map((x, k) => `<li><b>${esc(x.from)}</b> → ${x.to ? `<b>${esc(x.to)}</b>` : 'убрать'}
          <button class="btn small" data-mt-sdel="${k}">Не исправлять</button></li>`).join('');
        foot();
      };
      let found = null;
      const find = async () => {
        const q = sf.value.replace(/\s+/g, ' ').trim();
        if (!q) { sf.focus(); return; }
        res.hidden = false;
        res.innerHTML = '<span class="faint">Ищу…</span>';
        try { found = await api('/api/episodes/' + encodeURIComponent(id) + '/montage/subs?q=' + encodeURIComponent(q)); }
        catch (err) { res.innerHTML = `<span class="warntxt">${esc(err.message)}</span>`; return; }
        const to = st.value.replace(/\s+/g, ' ').trim();
        if (!found.total) { res.innerHTML = `Не нашёл «${esc(found.q)}». Проверь, как слово написано в субтитрах.`; return; }
        res.innerHTML = `<div>Нашёл: ${found.total}</div><ul>
          ${(found.shorts || []).map(x => `<li>шортс «${esc(x.title)}» — ${x.n}: <span class="faint">${esc(x.example)}</span></li>`).join('')}
          ${found.srt ? `<li>субтитры выпуска — ${found.srt}${found.srt_examples.length ? `: <span class="faint">${esc(found.srt_examples[0])}</span>` : ''}</li>` : ''}</ul>
          <button class="btn small primary" data-mt-sadd>${to ? `Заменить на «${esc(to)}»` : 'Убрать это слово'}</button>`;
      };
      sb.addEventListener('keydown', ev => { if (ev.key === 'Enter' && ev.target.matches('input')) { ev.preventDefault(); find(); } });
      sb.addEventListener('input', ev => { if (ev.target === sf) { found = null; res.hidden = true; } });
      sb.addEventListener('click', ev => {
        if (ev.target.closest('[data-mt-sfind]')) { find(); return; }
        if (ev.target.closest('[data-mt-sadd]') && found) {
          const x = { from: found.q, to: st.value.replace(/\s+/g, ' ').trim() };
          const k = subsEd.findIndex(y => y.from.toLowerCase() === x.from.toLowerCase());
          if (k >= 0) subsEd[k] = x; else subsEd.push(x);
          sf.value = ''; st.value = ''; res.hidden = true; found = null;
          chips();
          return;
        }
        const del = ev.target.closest('[data-mt-sdel]');
        if (del) { subsEd.splice(Number(del.dataset.mtSdel), 1); chips(); }
      });
      sb.chips = chips;
    }
    const go = b.querySelector('[data-mt-go]');
    if (go) go.addEventListener('click', async () => {
      const ch = changes();
      if (!ch.length && !subsEd.length) return;
      const shots = ch.filter(x => x.replace && x.replace.url).length;
      const ask = !ch.length ? `Пересобрать шортсы с исправленными субтитрами (${subsEd.length})?\nВидео выпуска останется как есть, итог придёт в Telegram.`
        : `Пересобрать выпуск с правками (${ch.length + subsEd.length})?${shots ? `\nСначала сделаю скрины страниц (${shots}) — это до минуты.` : ''}\nВидео заменится, когда сервер закончит, — итог придёт в Telegram.`;
      if (!confirm(ask)) return;
      go.disabled = true;
      go.textContent = shots ? 'Делаю скрины…' : 'Отправляю…';
      try {
        await api('/api/episodes/' + encodeURIComponent(id) + '/montage', { body: { subs: subsEd,
          changes: ch.map(x => (x.replace ? { ...x, replace: { url: x.replace.url, b64: x.replace.b64, ext: x.replace.ext } } : x)) } });
        toast('Пересобираю — итог придёт в Telegram');
        openEpisode(id);
      } catch (err) { toast(err.message, true); go.disabled = false; go.textContent = 'Пересобрать с правками'; }
    });
    const reset = b.querySelector('[data-mt-reset]');
    if (reset) reset.addEventListener('click', () => {
      Object.keys(ed).forEach(k => delete ed[k]);
      subsEd.length = 0;
      if (list) list.innerHTML = d.inserts.map(row).join('');
      if (sb) sb.chips(); else foot();
    });
    const back = b.querySelector('[data-mt-revert]');
    if (back) back.addEventListener('click', async () => {
      if (!confirm('Вернуть выпуск как был собран автоматически? Все правки монтажного стола пропадут, выпуск пересоберётся.')) return;
      back.disabled = true;
      try { await api('/api/episodes/' + encodeURIComponent(id) + '/montage/revert', { body: {} }); toast('Возвращаю как было — итог придёт в Telegram'); openEpisode(id); }
      catch (err) { toast(err.message, true); back.disabled = false; }
    });
    if (running) {  // пока сервер собирает — раз в 15 секунд проверяем, не готово ли
      const t = setInterval(async () => {
        if (!document.body.contains(det)) { clearInterval(t); return; }
        try {
          const n = await api('/api/episodes/' + encodeURIComponent(id) + '/montage');
          if (!(n.status === 'rendering' && n.job && n.job.status === 'running')) { clearInterval(t); openEpisode(id); }
        } catch (x) { /* сеть моргнула — спросим ещё раз */ }
      }, 15000);
    }
  }

  async function openEpisode(id) {
    const d0 = drawer('Выпуск', esc(id), loading());
    let e;
    try { e = await api('/api/episodes/' + encodeURIComponent(id)); } catch (err) { d0.querySelector('.d-b').innerHTML = failBox(err.message); return; }
    const sc = e.script;
    const fails = (e.inserts || []).filter(i => i.status !== 'ok');
    const v = e.video;
    const soc = (v && v.social) || {};
    const socLink = (k, t) => soc[k] && soc[k].ok && soc[k].url ? `<a class="btn" href="${esc(soc[k].url)}" target="_blank" rel="noopener">${t}</a>` : '';
    const socErr = [['facebook', 'Facebook'], ['threads', 'Threads']].filter(([k]) => soc[k] && !soc[k].ok).map(([k, t]) => `${t}: ${esc(soc[k].error)}`);
    const newPub = !!(e.pub && e.pub.texts);  // есть тексты публикации — публикуем кнопками у площадок
    const acts = (e.actions || []).filter(a => EP_ACT[a] && !(newPub && a === 'publish'));
    const rev = v && v.rev ? '?v=' + v.rev : '';  // метка пересборки с монтажного стола
    const mj = (e.meta && e.meta.montage_job) || {};
    const review = v ? [
      ...(v.review || []).map(x => `<li><button class="btn small" data-seek="${x.at_ms || 0}">${tc(x.at_ms)}</button><div class="grow">
        <div class="title">Вставка ${esc(x.marker)} — проверь место</div><div class="meta">уверенность ${Math.round((x.conf || 0) * 100)}%</div></div>
        <button class="btn small" data-mt-fixm="${esc(x.marker)}" data-ms="${x.at_ms || 0}">Поправить</button></li>`),
      ...(v.missed || []).map(x => `<li><span class="dot err"></span><div class="grow"><div class="title">Вставка ${esc(x.marker)} не встала</div>
        <div class="meta">${esc(x.why)}</div></div></li>`)] : [];
    const body = `
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px">${epTags(e)}</div>
      ${v ? `<video class="ep-video" controls preload="metadata" playsinline poster="${esc(v.thumb_url + rev)}" src="${esc(v.final_url + rev)}"></video>` : ''}
      <div class="actions" style="margin:12px 0 6px">
        ${acts.map(a => `<button class="btn ${EP_ACT[a].tone}" data-act="${a}">${EP_ACT[a].label}</button>`).join('')}
        ${v ? `<a class="btn" href="${esc(v.final_url)}" target="_blank" rel="noopener">Открыть видео</a>`
          : e.preview_url ? `<a class="btn primary" href="${esc(e.preview_url)}" target="_blank" rel="noopener">Смотреть превью</a>` : ''}
        ${e.youtube_url ? `<a class="btn" href="${esc(e.youtube_url)}" target="_blank" rel="noopener">YouTube</a>` : ''}
        ${socLink('facebook', 'Facebook')}${socLink('threads', 'Threads')}
        ${!newPub && (e.social_todo || []).length && !socErr.length ? `<button class="btn" data-social>В ${e.social_todo.map(k =>
          ({ facebook: 'Facebook', threads: 'Threads', telegram: 'Telegram' })[k] || k).join(' и ')}</button>` : ''}
        ${e.kind === 'script' ? `<a class="btn" href="#/prompter/view?s=${encodeURIComponent(e.id)}">Открыть в суфлёре</a>` : ''}
        ${EP_BUSY.includes(e.status) ? '' : `<button class="btn danger" data-delep>${I.trash}Удалить</button>`}
      </div>
      ${e.status === 'publish_requested' ? `<div class="note">Публикация начнётся в течение минуты — итог придёт в Telegram и появится здесь.</div>` : ''}
      ${soc.pending ? `<div class="note">Соцсети публикуются в фоне — длинное видео в Facebook грузится несколько минут, итог придёт в Telegram.</div>` : ''}
      ${!newPub && socErr.length && !soc.pending ? `<div class="note warnnote">Не опубликовано — ${socErr.join(' · ')}.
        <div style="margin-top:8px"><button class="btn small" data-social>Повторить Facebook и Threads</button> <span class="faint">уже выложенное второй раз не пойдёт</span></div></div>` : ''}
      ${v ? `
        ${review.length ? `<div class="section-t">Проверь перед публикацией</div><div class="card"><ul class="rows">${review.join('')}</ul></div>` : ''}
        ${(v.shorts || []).length ? `<div class="section-t">Шортсы · ${v.shorts.length}</div><div class="ep-shorts">${v.shorts.map(s => `<figure>
          <video controls preload="none" playsinline src="${esc(s.url + rev)}"></video><figcaption>${esc(s.title)}</figcaption></figure>`).join('')}</div>` : ''}
        <details class="mt"${mj.status === 'running' && e.status === 'rendering' ? ' open' : ''}><summary class="section-t">Монтажный стол
          ${mj.status === 'running' && e.status === 'rendering' ? '<span class="mt-sum">пересобираю…</span>'
            : mj.status === 'error' ? `<span class="mt-sum warntxt">${mj.partial ? 'пересобрано не до конца' : 'последняя пересборка не удалась'}</span>`
            : '<span class="mt-sum">поправить вставки без пересъёмки</span>'}</summary>
          <div class="mt-b"><div class="faint">Загружаю вставки…</div></div></details>
        ${pubSection(e)}
        <div class="section-t">Монтаж</div><dl class="kv">
          <dt>Вставки</dt><dd>${v.inserts_placed ?? '—'}${(v.missed || []).length ? ` · не встали: ${v.missed.length}` : ''}</dd>
          <dt>Вырезано пауз и дублей</dt><dd>${v.cuts ?? 0}${v.cut_ms ? ` · ${tc(v.cut_ms)}` : ''}</dd>
          <dt>Субтитры</dt><dd><a href="${esc(v.subs_url)}" target="_blank" rel="noopener">subs.srt</a></dd></dl>
        ${v.chapters_text ? `<div class="section-t">Главы для описания</div><pre class="json">${esc(v.chapters_text)}</pre>` : ''}` : ''}
      ${v ? '' : pubSection(e)}
      ${reportSection(e.report)}
      <div class="section-t">Главное</div>
      <dl class="kv"><dt>Создан</dt><dd>${dt(e.created_at)}</dd><dt>Обновлён</dt><dd>${dt(e.updated_at)}</dd>
        ${e.script_id ? `<dt>Сценарий</dt><dd class="mono">${esc(e.script_id)}</dd>` : ''}
        <dt>Вставки</dt><dd>${e.inserts_total ? `${e.inserts_ok} из ${e.inserts_total}` : '—'}</dd>
        <dt>Стоимость (Claude)</dt><dd class="num">${money(e.cost_usd, 3)}</dd></dl>
      ${sc ? `<div class="section-t">Сценарий</div><dl class="kv"><dt>Заголовок</dt><dd>${esc(sc.yt_title || sc.title || '—')}</dd>
        <dt>Части / главы</dt><dd>${sc.segments} / ${sc.chapters}</dd><dt>Факты</dt><dd>${sc.claims}</dd><dt>Источники</dt><dd>${sc.sources}</dd><dt>Шортсы</dt><dd>${sc.shorts}</dd></dl>` : ''}
      ${(e.inserts || []).length ? `<div class="section-t">Вставки${fails.length ? ` · не получилось: ${fails.length}` : ''}</div>
        <div class="card"><ul class="rows">${e.inserts.map(i => `<li><span class="dot ${i.status === 'ok' ? 'ok' : 'err'}"></span><div class="grow">
          <div class="title">${esc(i.marker)} · ${esc(INS_KIND[i.kind] || i.kind)}</div><div class="meta">${esc(i.query || i.source || '')}</div>
          ${i.note ? `<div class="${i.status === 'ok' ? 'meta' : 'errtxt'}">${esc(i.note)}</div>` : ''}</div></li>`).join('')}</ul></div>` : ''}
      ${(e.costs || []).length ? `<div class="section-t">Вызовы Claude</div><div class="card scroll-x"><table class="table"><tr><th>Шаг</th><th>Модель</th><th class="r">Токены</th><th class="r">$</th></tr>
        ${e.costs.map(c => `<tr><td>${esc(c.node)}<div class="faint">${esc(c.workflow_name || '')}</div></td><td class="mono">${esc(c.model)}</td>
          <td class="r num">${(c.input_tokens || 0).toLocaleString('ru-RU')} / ${(c.output_tokens || 0).toLocaleString('ru-RU')}</td><td class="r num">${money(c.usd, 3)}</td></tr>`).join('')}</table></div>` : ''}
      <details class="ep-raw"><summary class="section-t">Данные монтажа (для разбора)</summary><pre class="json">${esc(JSON.stringify(e.meta || {}, null, 2))}</pre></details>`;
    const box = d0.querySelector('.d-b');
    box.innerHTML = body;
    const vid = box.querySelector('.ep-video');
    box.querySelectorAll('[data-seek]').forEach(b => b.addEventListener('click', () => {
      if (!vid) return;
      vid.currentTime = Math.max(0, Number(b.dataset.seek) / 1000 - 2);
      vid.play().catch(() => {});
      vid.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }));
    bindPub(box, e, id);
    const mt = bindMontage(box, id, vid);
    box.querySelectorAll('[data-mt-fixm]').forEach(b => b.addEventListener('click', () => mt && mt.focus(b.dataset.mtFixm, Number(b.dataset.ms))));
    const socBtn = box.querySelector('[data-social]');
    if (socBtn) socBtn.addEventListener('click', async () => {
      socBtn.disabled = true;
      try {
        await api('/api/episodes/' + encodeURIComponent(id) + '/social', { body: {} });
        toast('Поставил в очередь — итог придёт в Telegram'); openEpisode(id);
      } catch (err) { toast(err.message, true); socBtn.disabled = false; }
    });
    const delBtn = box.querySelector('[data-delep]');
    if (delBtn) delBtn.addEventListener('click', async () => {
      if (!await deleteEpisode(e.id, e.title, e.kind === 'script')) return;
      if (location.hash.startsWith('#/episodes') || location.hash === '#/' || location.hash === '' || location.hash.startsWith('#/prompter')) route(); else closeDrawer();
    });
    box.querySelectorAll('[data-act]').forEach(b => b.addEventListener('click', async () => {
      const a = EP_ACT[b.dataset.act];
      if (!confirm(e.kind === 'script' && a.askScript ? a.askScript : a.ask)) return;
      box.querySelectorAll('[data-act]').forEach(x => { x.disabled = true; });
      try {
        await api('/api/episodes/' + encodeURIComponent(id) + '/action', { body: { action: b.dataset.act } });
        toast(a.done);
        // перерисовать список (route сам закрывает выдвижную панель), затем открыть выпуск с новым статусом
        if (location.hash.startsWith('#/episodes') || location.hash === '#/' || location.hash === '') route(); else closeDrawer();
        openEpisode(id);
      } catch (err) {
        toast(err.message, true);
        box.querySelectorAll('[data-act]').forEach(x => { x.disabled = false; });
      }
    }));
  }

  // ---------- Подключения ----------
  // Каналы и аккаунты, куда публикует конвейер. YouTube входит через n8n (Credentials) — Студия секретов не видит.
  // Facebook и Threads подключаются здесь же кнопкой (вход Meta): ключи доступа Студия хранит зашифрованными и не показывает.
  const PLAT_ICON = { youtube: () => I.yt, facebook: () => I.fb, threads: () => I.threads, telegram: () => I.tg };
  // Telegram-канал: бот — администратор канала; токен вписывается только сюда
  const HOWTO_TG = ['В Telegram открой @BotFather → /mybots → бот конвейера (или новый: /newbot) → «API Token» → скопируй токен.',
    'Открой свой канал → «Управление каналом» → «Администраторы» → «Добавить администратора» → найди бота → оставь право «Публикация сообщений» → «Сохранить».',
    'Здесь нажми «Подключить», вставь токен и адрес канала — Студия проверит, что бот может публиковать.',
    'Токен — как пароль: вписывай только сюда, не в чат. Он хранится зашифрованным и назад не показывается.'];
  const HOWTO_YT = ['В n8n открой Credentials → Add credential → «YouTube OAuth2 API».', 'Нажми «Sign in with Google» и войди той почтой, на которой канал.',
    'Назови вход «YouTube — канал …» и сохрани — он сам появится здесь.'];
  // запись входа в n8n есть, но вход в Google не выполнен (или устарел) — что сделать
  const HOWTO_YT_LOGIN = ['Открой n8n → слева «Credentials» (учётные данные) → запись этого входа.',
    'Нажми «Sign in with Google» и войди почтой, на которой канал «Без сказок».',
    'Если Google спросит, какой аккаунт или канал, — выбери канал «Без сказок», затем «Разрешить» (Allow).',
    'Если n8n просит Client ID и Client Secret — остановись и напиши мне.',
    'Вернись сюда и нажми «Проверить вход» — появится имя канала.'];
  const YT_STATE = { ok: ['ok', 'вход выполнен'], no_login: ['warn', 'вход в Google не выполнен — публиковать на YouTube нельзя'],
    expired: ['err', 'вход устарел — войди в Google ещё раз'], no_channel: ['warn', 'у этой почты нет канала YouTube — войди почтой, где канал'],
    error: ['err', 'проверка не прошла'], unknown: ['', 'вход не проверен'] };
  // один раз на developers.facebook.com: одно приложение, в нём два сценария — страница и Threads
  const META_HOWTO = {
    facebook: ['Открой developers.facebook.com → «Мои приложения» → «Создать приложение». Выбери только два сценария: «Управлять всем на своей Странице» и «Доступ к Threads API». С лишними сценариями Meta не даст опубликовать приложение без подтверждения компании.',
      '«Настройки приложения» → «Основное»: домен Студии в «Домены приложений», адрес политики и «URL инструкций для удаления данных» (ниже), категория «Бизнес и Страницы» → «Сохранить изменения». Потом слева «Опубликовать» → «Опубликовать» — иначе публикации видишь только ты.',
      'Сценарии → «Управлять всем на своей Странице» → «Настроить»: добавь pages_manage_posts и pages_read_engagement.',
      '«Вход через Facebook для бизнеса» → «Настройки»: адрес возврата (ниже) вставь в «Действительные URI перенаправления для OAuth» и нажми Enter; адрес деавторизации и удаления данных — в поля ниже; «Сохранить изменения».',
      '«Вход через Facebook для бизнеса» → «Конфигурации» → «Создать конфигурацию»: «Общий», «Маркер доступа пользователя», разрешения pages_show_list, pages_read_engagement, pages_manage_posts, business_management.',
      'Кнопкой ниже впиши номер приложения, секрет («Основное» → «Показать») и номер конфигурации — не в чат. Потом «Подключить».'],
    threads: ['В том же приложении сценарий «Доступ к Threads API» → «Настроить»: добавь threads_content_publish и threads_manage_replies (ответы — для цепочки постов).',
      'Там же «Настройки»: адрес возврата (ниже) — в поле перенаправления, Enter; адреса Uninstall и Delete — в свои поля; «Сохранить». «Идентификатор приложения Threads» и «Секрет приложения Threads» — свои, не как у Facebook.',
      '«Роли в приложении» → «Роли» → «Добавить людей» → «Тестировщик Threads» → твой аккаунт Threads. Приглашение прими на threads.com: Настройки → «Ещё настройки» → «Разрешения для сайтов» → «Приглашения».',
      'Впиши номер и секрет Threads сюда кнопкой ниже и нажми «Подключить».'],
  };
  async function copyText(t) {
    try { await navigator.clipboard.writeText(t); toast('Скопировано'); } catch (e) { window.prompt('Скопируй адрес:', t); }
  }
  async function pageConnections(view, params) {
    view.innerHTML = head('Подключения', 'Каналы и аккаунты, куда конвейер публикует: всё видно и настраивается здесь') + loading();
    if (params && (params.get('ok') || params.get('err'))) {  // вернулись со входа Meta
      toast(params.get('ok') || params.get('err'), !params.get('ok'));
      history.replaceState(null, '', '#/connections');
    }
    let d;
    try { d = await api('/api/connections'); } catch (e) { view.lastElementChild.outerHTML = failBox(e.message); return; }
    const P = d.platforms || {};
    const M = d.meta || {};
    const PRIV = { private: 'ограниченный доступ', unlisted: 'по ссылке', public: 'открытый доступ' };
    const metaState = (pid) => {
      const m = M[pid] || {};
      if (m.connected) return ['подключено', 'ok'];
      if (pid === 'facebook' && (m.pages || []).length) return ['выбери страницу', 'warn'];
      return [m.app && m.app.app_id && m.app.secret ? 'осталось войти' : 'не подключено', ''];
    };
    const metaBlock = (pid) => {
      const m = M[pid] || {};
      const ap = m.app || {};
      const redirect = m.redirect_uri || (location.origin + '/oauth/' + pid + '/callback');
      const privacy = m.privacy_url || (location.origin + '/privacy');
      const urlBox = (t, u) => `<div class="conn-redir"><div class="faint">${t}</div><code>${esc(u)}</code>
          <button class="btn small" data-copy="${esc(u)}">${I.copy}Скопировать</button></div>`;
      const steps = `<ol class="conn-steps">${META_HOWTO[pid].map(x => `<li>${esc(x)}</li>`).join('')}</ol>
        ${urlBox('Адрес возврата (URI перенаправления)', redirect)}
        ${pid === 'facebook' ? urlBox('Политика конфиденциальности', privacy) +
            urlBox('Инструкции по удалению данных («Основное»)', privacy + '#delete') +
            urlBox('Деавторизация URL обратного вызова', m.uninstall_url || location.origin + '/oauth/facebook/uninstall') +
            urlBox('URL запроса на удаление данных', m.delete_url || location.origin + '/oauth/facebook/delete')
          : urlBox('Uninstall Callback URL', m.uninstall_url || location.origin + '/oauth/threads/uninstall') +
            urlBox('Delete Callback URL', m.delete_url || location.origin + '/oauth/threads/delete')}`;
      const appBtn = (t, tone = '') => `<button class="btn ${tone || 'small'}" data-mapp="${pid}">${t}</button>`;
      if (m.connected) {
        const name = pid === 'facebook' ? m.page.name : '@' + m.username;
        const link = pid === 'facebook' ? m.page.link : 'https://www.threads.net/@' + encodeURIComponent(m.username);
        const pages = pid === 'facebook' && m.pages.length > 1 ? `<label class="conn-page">Страница <select class="input" data-mpage>${m.pages.map(x =>
          `<option value="${esc(x.id)}"${x.id === m.page.id ? ' selected' : ''}>${esc(x.name)}${x.can_post ? '' : ' (нет права публиковать)'}</option>`).join('')}</select></label>` : '';
        return `<div class="conn-acc"><div class="conn-acc-t"><span class="dot ok"></span><b>${esc(name)}</b>
            <a href="${esc(link)}" target="_blank" rel="noopener">открыть</a></div>
          ${pid === 'facebook' ? `<div class="faint">вошёл: ${esc(m.user || '—')} · подключено ${when(m.connected_at)}</div>
            <div class="faint">все увидят публикации, когда приложение Meta в режиме «Опубликовано» (Live)</div>`
            : `<div class="faint">подключено ${when(m.connected_at)} · доступ продлевается сам${m.expires_at ? ', сейчас до ' + dt(m.expires_at) : ''}</div>`}
          ${pages}
          <div class="actions"><a class="btn small" href="/oauth/${pid}/start">Переподключить</a>${appBtn('Приложение')}
            <button class="btn small danger" data-mdisc="${pid}">Отключить</button></div></div>`;
      }
      if (pid === 'facebook' && (m.pages || []).length) {
        return `<div class="note"><b>Выбери страницу, куда публиковать</b><div class="conn-pages">${m.pages.map(x =>
          `<button class="btn" data-mpick="${esc(x.id)}">${I.fb}${esc(x.name)}${x.can_post ? '' : ' · нет права публиковать'}</button>`).join('')}</div></div>`;
      }
      if (ap.app_id && ap.secret) {
        return `<div class="faint">Приложение Meta № ${esc(ap.app_id)} · секрет сохранён</div>
          <div class="actions"><a class="btn primary" href="/oauth/${pid}/start">Подключить</a>${appBtn('Изменить приложение')}</div>
          <details class="conn-more"><summary>Шаги и адрес возврата</summary>${steps}</details>`;
      }
      return `<div class="note"><b>Один раз — приложение Meta</b>${steps}</div>
        <div class="actions">${appBtn('Вписать номер и секрет приложения', 'primary')}</div>`;
    };
    const T = d.telegram || {};
    const tgBlock = () => {
      if (!T.connected) return `<div class="note"><b>Как подключить канал</b><ol class="conn-steps">${HOWTO_TG.map(x => `<li>${esc(x)}</li>`).join('')}</ol></div>
        <div class="actions"><button class="btn primary" data-tgset>Подключить</button></div>`;
      const ch = T.chat || {};
      return `<div class="conn-acc"><div class="conn-acc-t"><span class="dot ${T.can_post ? 'ok' : 'err'}"></span><b>${esc(ch.title || '@' + ch.username)}</b>
          ${ch.link ? `<a href="${esc(ch.link)}" target="_blank" rel="noopener">открыть</a>` : ''}</div>
        <div class="${T.can_post ? 'faint' : 'conn-warn'}">${T.can_post ? `бот @${esc((T.bot || {}).username)} — администратор, может публиковать` : esc(T.error || 'бот не может публиковать')}</div>
        <div class="faint">подключено ${when(T.connected_at)}${T.checked_at && T.checked_at !== T.connected_at ? ' · проверено ' + when(T.checked_at) : ''}</div>
        <div class="actions"><button class="btn small" data-tgcheck>Проверить</button><button class="btn small" data-tgset>Изменить</button>
          <button class="btn small danger" data-tgoff>Отключить</button></div></div>`;
    };
    const card = (pid) => {
      const p = P[pid] || { accounts: [], directions: [], publications: [] };
      const isTg = pid === 'telegram';
      const isMeta = pid === 'facebook' || pid === 'threads';
      const ytOk = p.accounts.some(a => a.check && a.check.state === 'ok');
      const [st, tone] = isTg ? (T.connected ? (T.can_post ? ['подключено', 'ok'] : ['не может публиковать', 'err']) : ['не подключено', ''])
        : isMeta ? metaState(pid) : ytOk ? ['подключено', 'ok'] : p.accounts.length ? ['нужно войти', 'warn'] : ['не подключено', ''];
      const accs = p.accounts.map(a => {
        const ck = a.check || { state: 'unknown', channels: [] };
        const [dot, label] = YT_STATE[ck.state] || YT_STATE.unknown;
        const n8nLink = d.n8n_credentials_url ? ` <a href="${esc(d.n8n_credentials_url)}" target="_blank" rel="noopener">открыть n8n</a>` : '';
        return `<div class="conn-acc"><div class="conn-acc-t"><span class="dot ${dot}"></span><b>${esc(a.title)}</b>
          ${a.url ? `<a href="${esc(a.url)}" target="_blank" rel="noopener">открыть</a>` : ''}</div>
          <div class="${ck.state === 'ok' ? 'faint' : 'conn-warn'}">${esc(label)}${ck.state === 'error' && ck.error ? ': ' + esc(ck.error) : ''}</div>
          ${(ck.channels || []).map(ch => `<div class="faint">канал: <a href="${esc(ch.url)}" target="_blank" rel="noopener">${esc(ch.title)}</a></div>`).join('')}
          <div class="faint">вход в n8n: ${esc(a.credential_name)}</div>
          <div class="faint">${a.used_by.length ? 'пользуется: ' + esc(a.used_by.join(', ')) : 'пока ни один процесс не публикует'}</div>
          ${a.notes ? `<div class="faint">${esc(a.notes)}</div>` : ''}
          ${ck.state !== 'ok' && ck.state !== 'unknown' ? `<div class="note"><b>Как войти</b>${n8nLink}<ol class="conn-steps">${HOWTO_YT_LOGIN.map(x => `<li>${esc(x)}</li>`).join('')}</ol></div>` : ''}
          <div class="actions"><button class="btn small" data-edit="${esc(a.credential_id)}">${I.pencil}Изменить</button>
            <button class="btn small" data-recheck>Проверить вход</button></div></div>`;
      }).join('');
      const dirs = p.directions.length ? p.directions.map(x => badge(x.name + (x.privacy ? ' · ' + (PRIV[x.privacy] || x.privacy) : ''), x.enabled ? 'info' : '')).join(' ')
        : `<span class="muted">${isTg ? 'кнопкой на странице выпуска — любое направление; само после YouTube — пока ни одно (включается в «Направлениях» → Публикация)'
          : 'ни одно направление сюда не публикует' + (isMeta ? ' — включается в «Направлениях» → Публикация' : '')}</span>`;
      const pubs = p.publications.length ? `<ul class="rows">${p.publications.map(x => `<li><div class="grow"><div class="title">${x.url
          ? `<a href="${esc(x.url)}" target="_blank" rel="noopener">${esc(x.title)}</a>` : esc(x.title)}</div>
          <div class="meta"><span>${when(x.at)}</span>${x.shorts ? `<span>шортсов: ${x.shorts}</span>` : ''}</div></div></li>`).join('')}</ul>`
        : '<div class="muted">Пока ничего не публиковали</div>';
      return `<div class="card conn"><div class="card-h"><h2><span class="conn-ic ${pid}">${PLAT_ICON[pid]()}</span>${esc(p.title || pid)}</h2>${badge(st, tone)}</div>
        <div class="card-b">
          <div class="faint conn-what">${esc(p.what || '')}</div>
          ${isTg ? tgBlock() : isMeta ? metaBlock(pid) : (p.accounts.length ? accs : `<div class="note"><b>Как подключить</b><ol class="conn-steps">${HOWTO_YT.map(x => `<li>${esc(x)}</li>`).join('')}</ol></div>`)}
          <div class="section-t">Кто сюда публикует</div><div class="conn-dirs">${dirs}</div>
          <div class="section-t">Последние публикации</div>${pubs}
        </div></div>`;
    };
    view.lastElementChild.outerHTML = (d.error ? failBox('Не получилось спросить n8n: ' + d.error) : '') +
      `<div class="grid conns">${['youtube', 'facebook', 'threads', 'telegram'].map(card).join('')}</div>
       <div class="note" style="margin-top:16px">Пароли сюда не вводятся. YouTube входит через n8n — статус здесь проверяется по-настоящему: «подключено» только когда вход в Google выполнен. Facebook и Threads — кнопкой «Подключить»: входишь на сайте Meta, а Студия получает доступ и хранит его зашифрованным, никому не показывая. Telegram — бот-администратор канала: токен бота вписываешь сам, Студия хранит его зашифрованным. Куда публикует каждое направление — в «Направлениях».</div>`;
    view.querySelectorAll('[data-copy]').forEach(b => b.addEventListener('click', () => copyText(b.dataset.copy)));
    view.querySelectorAll('[data-recheck]').forEach(b => b.addEventListener('click', async () => {
      b.disabled = true;
      try { await api('/api/connections?recheck=1'); toast('Проверил'); route(); } catch (e) { toast(e.message, true); b.disabled = false; }
    }));
    view.querySelectorAll('[data-edit]').forEach(b => b.addEventListener('click', () => {
      const a = Object.values(P).flatMap(p => p.accounts).find(x => x.credential_id === b.dataset.edit);
      if (!a) return;
      const dlg = drawer('Подключение', esc(a.credential_name), `<div class="conn-form">
          <label>Подпись<input class="input" id="ctitle" maxlength="120" value="${esc(a.title)}"></label>
          <label>Ссылка на канал или страницу<input class="input" id="curl" maxlength="300" value="${esc(a.url)}" placeholder="https://www.youtube.com/@…"></label>
          <label>Заметка<input class="input" id="cnotes" maxlength="500" value="${esc(a.notes)}" placeholder="например: на какой почте канал"></label>
          <div class="actions"><button class="btn primary" id="csave">Сохранить</button></div></div>`);
      dlg.querySelector('#csave').addEventListener('click', async () => {
        try {
          await api('/api/connections/' + encodeURIComponent(a.credential_id), { method: 'PUT',
            body: { title: dlg.querySelector('#ctitle').value, url: dlg.querySelector('#curl').value, notes: dlg.querySelector('#cnotes').value } });
          toast('Сохранено'); route();
        } catch (e) { toast(e.message, true); }
      });
    }));
    // приложение Meta: номер не секрет, секрет вписывается только сюда и назад не показывается
    view.querySelectorAll('[data-mapp]').forEach(b => b.addEventListener('click', () => {
      const pid = b.dataset.mapp, fb = pid === 'facebook';
      const ap = (M[pid] || {}).app || {};
      const dlg = drawer(fb ? 'Приложение Meta для Facebook' : 'Приложение Meta для Threads', '', `<div class="conn-form">
          <label>${fb ? 'Идентификатор приложения (App ID)' : 'Идентификатор приложения Threads (Threads app ID)'}
            <input class="input" id="mid" inputmode="numeric" autocomplete="off" maxlength="25" value="${esc(ap.app_id || '')}" placeholder="только цифры"></label>
          <label>${fb ? 'Секрет приложения (App Secret)' : 'Секрет приложения Threads (Threads app secret)'}
            <input class="input" id="msec" type="password" autocomplete="new-password" spellcheck="false" maxlength="64"
              placeholder="${ap.secret ? 'сохранён — впиши, только если меняешь' : 'нажми «Показать» в Meta, скопируй и вставь сюда'}"></label>
          ${fb ? `<label>Номер конфигурации («Вход через Facebook для бизнеса» → «Конфигурации»)
            <input class="input" id="mcfg" inputmode="numeric" autocomplete="off" maxlength="25" value="${esc(ap.config_id || '')}" placeholder="только цифры"></label>` : ''}
          ${ap.app_id ? `<div class="faint">Меняешь приложение — впиши новый номер, новый секрет${fb ? ' и номер новой конфигурации' : ''}. Старый вход сбросится, потом нажмёшь «Подключить».</div>` : ''}
          <div class="faint">Секрет сразу шифруется на сервере. Назад его не покажу — ни здесь, ни в чате.</div>
          <div class="actions"><button class="btn primary" id="msave">Сохранить</button></div></div>`);
      dlg.querySelector('#msave').addEventListener('click', async (ev) => {
        ev.target.disabled = true;
        try {
          const cfg = dlg.querySelector('#mcfg');
          await api('/api/meta/' + pid + '/app', { method: 'PUT', body: { app_id: dlg.querySelector('#mid').value, secret: dlg.querySelector('#msec').value,
            config_id: cfg ? cfg.value : '' } });
          dlg.querySelector('#msec').value = '';
          toast('Сохранено — теперь нажми «Подключить»'); closeDrawer(); route();
        } catch (e) { toast(e.message, true); ev.target.disabled = false; }
      });
    }));
    view.querySelectorAll('[data-tgset]').forEach(b => b.addEventListener('click', () => {
      const ch = T.chat || {};
      const dlg = drawer('Telegram-канал', T.connected ? esc(ch.title || '') : 'подключение', `<div class="conn-form">
          ${T.connected ? '' : `<ol class="conn-steps">${HOWTO_TG.slice(0, 2).map(x => `<li>${esc(x)}</li>`).join('')}</ol>`}
          <label>Токен бота
            <input class="input" id="tgtok" type="password" autocomplete="new-password" spellcheck="false" maxlength="80"
              placeholder="${T.connected ? 'сохранён — впиши, только если меняешь бота' : '123456789:AA… — у @BotFather'}"></label>
          <label>Канал<input class="input" id="tgch" autocomplete="off" maxlength="80" value="${esc(ch.username ? '@' + ch.username : '')}"
              placeholder="@имя_канала или ссылка t.me/имя_канала"></label>
          <div class="faint">Студия проверит, что бот — администратор канала и может публиковать. Ничего в канал при этом не отправит.</div>
          <div class="faint">Токен сразу шифруется на сервере. Назад его не покажу — ни здесь, ни в чате.</div>
          <div class="actions"><button class="btn primary" id="tgsave">Проверить и подключить</button></div></div>`);
      dlg.querySelector('#tgsave').addEventListener('click', async (ev) => {
        ev.target.disabled = true;
        try {
          await api('/api/telegram', { method: 'PUT', body: { token: dlg.querySelector('#tgtok').value, channel: dlg.querySelector('#tgch').value } });
          dlg.querySelector('#tgtok').value = '';
          toast('Telegram подключён — бот может публиковать в канал'); closeDrawer(); route();
        } catch (e) { toast(e.message, true); ev.target.disabled = false; }
      });
    }));
    view.querySelectorAll('[data-tgcheck]').forEach(b => b.addEventListener('click', async () => {
      b.disabled = true;
      try { const r = await api('/api/telegram/check', { body: {} }); toast(r.can_post ? 'Проверил: бот может публиковать' : r.error, !r.can_post); route(); }
      catch (e) { toast(e.message, true); b.disabled = false; }
    }));
    view.querySelectorAll('[data-tgoff]').forEach(b => b.addEventListener('click', async () => {
      if (!confirm('Отключить Telegram-канал? Студия забудет токен бота, публикации в канал остановятся. Сам бот и канал не изменятся.')) return;
      try { await api('/api/telegram', { method: 'DELETE' }); toast('Отключено'); route(); } catch (e) { toast(e.message, true); }
    }));
    const setPage = async (id) => {
      try { await api('/api/meta/facebook/page', { method: 'PUT', body: { page_id: id } }); toast('Страница выбрана'); route(); }
      catch (e) { toast(e.message, true); }
    };
    view.querySelectorAll('[data-mpick]').forEach(b => b.addEventListener('click', () => setPage(b.dataset.mpick)));
    view.querySelectorAll('[data-mpage]').forEach(s => s.addEventListener('change', () => setPage(s.value)));
    view.querySelectorAll('[data-mdisc]').forEach(b => b.addEventListener('click', async () => {
      const pid = b.dataset.mdisc;
      if (!confirm(`Отключить ${pid === 'facebook' ? 'Facebook' : 'Threads'}? Студия забудет доступ, публикации туда остановятся. Подключить снова — одной кнопкой.`)) return;
      try { await api('/api/meta/' + pid, { method: 'DELETE' }); toast('Отключено'); route(); } catch (e) { toast(e.message, true); }
    }));
  }

  // ---------- Направления ----------
  // Рубрики и каналы: настройки, по которым конвейер пишет сценарий, собирает вставки, монтирует и публикует.
  // Раньше лежали в Google-таблице; процессы n8n читают их отсюда (studio/app/directions.py).
  const STOCK_T = { coverr: 'Coverr — видео', wikimedia: 'Wikimedia', openverse: 'Openverse — фото', nasa: 'NASA' };
  async function pageDirections(view) {
    view.innerHTML = head('Направления', 'Рубрики и каналы: длительность, стиль, вставки, монтаж, папка на Диске и публикация',
      `<a class="btn primary" href="#/directions/edit?new=1">${I.plus}Новое направление</a>`) + loading();
    let d;
    try { d = await api('/api/directions'); } catch (e) { view.lastElementChild.outerHTML = failBox(e.message); return; }
    const list = d.directions || [];
    const cards = list.map(x => `<div class="card ep dir${x.enabled ? '' : ' off'}">
      <div class="tags">${badge(x.enabled ? 'включено' : 'выключено', x.enabled ? 'ok' : '')}${badge(d.modes[x.mode] || x.mode, 'plain')}${badge(x.id, 'plain')}</div>
      <h3>${esc(x.name)}</h3>
      <div class="meta"><span>${x.minutes} мин</span><span>${x.words_per_min} сл/мин</span><span>шортсов: ${x.shorts}</span>
        ${x.episodes_30d ? `<span>выпусков за 30 дней: ${x.episodes_30d}</span>` : ''}</div>
      <dl class="kv dir-kv">
        <dt>Вставки</dt><dd>${esc(x.inserts.map(k => (d.kinds[k] || k).toLowerCase()).join(', ')) || '—'}</dd>
        <dt>Монтаж</dt><dd>${x.cut_pauses ? 'паузы длиннее ' + x.pause_cut_ms + ' мс — вырезать' : 'паузы не трогать'}${x.cut_retakes ? ', дубли — убирать' : ''}</dd>
        <dt>YouTube</dt><dd>${x.publish_youtube ? esc((d.privacy[x.youtube_privacy] || x.youtube_privacy).toLowerCase()) : 'не публиковать'}</dd>
        ${x.publish_facebook || x.publish_threads || x.publish_telegram ? `<dt>Ещё</dt><dd>${[x.publish_facebook && 'Facebook', x.publish_threads && 'Threads', x.publish_telegram && 'Telegram'].filter(Boolean).join(', ')}</dd>` : ''}
        <dt>Папка на Диске</dt><dd>${x.folder_url ? `<a href="${esc(x.folder_url)}" target="_blank" rel="noopener">открыть</a>` : 'не задана'}</dd>
      </dl>
      <div class="foot"><a class="btn small" href="#/directions/edit?id=${encodeURIComponent(x.id)}">${I.pencil}Изменить</a></div></div>`).join('');
    view.lastElementChild.outerHTML = (list.length ? `<div class="grid eps">${cards}</div>`
      : `<div class="card"><div class="empty"><b>Направлений пока нет</b>Нажми «Новое направление»</div></div>`) +
      `<div class="note" style="margin-top:16px">Раньше эти настройки жили в Google-таблице. Теперь конвейер берёт их отсюда: изменил и сохранил — следующий выпуск пойдёт уже по-новому.</div>`;
  }

  async function pageDirectionEdit(view, params) {
    const isNew = params.get('new') === '1';
    view.innerHTML = head(isNew ? 'Новое направление' : 'Направление', '', `<a class="btn" href="#/directions">Назад</a>`) + loading();
    let d;
    try { d = await api('/api/directions'); } catch (e) { view.lastElementChild.outerHTML = failBox(e.message); return; }
    const all = d.directions || [];
    let x = isNew ? null : all.find(r => r.id === params.get('id'));
    if (!isNew && !x) { view.lastElementChild.outerHTML = failBox('Нет такого направления'); return; }
    const blank = { id: '', name: '', enabled: true, mode: 'free', language: 'ru', minutes: 15, words_per_min: 130, shorts: 3, sources_on: false,
      style_prompt: '', delivery: 'opinion', inserts: ['card', 'quote', 'number', 'map', 'stock', 'wikimedia'], stock_sources: [], cut_pauses: true, pause_cut_ms: 700,
      pause_keep_ms: 150, cut_retakes: true, publish_youtube: false, youtube_privacy: 'private', publish_facebook: false, publish_threads: false, publish_telegram: false,
      brand_color: '#111111', accent_color: '#E53935',
      logo_url: '', drive_folder_id: '', folder_url: '' };
    const sw = (k, on, off) => `<label class="switch${off ? ' off' : ''}"><input type="checkbox" data-k="${k}" ${on ? 'checked' : ''}${off ? ' disabled' : ''}><i></i></label>`;
    const cn = d.connected || {};
    const row = (label, inner, hint) => `<div class="df"><div class="df-l">${label}${hint ? `<div class="faint">${hint}</div>` : ''}</div><div class="df-i">${inner}</div></div>`;
    const sel = (k, opts, v) => `<select class="input" data-k="${k}">${Object.entries(opts).map(([o, t]) => `<option value="${o}"${o === v ? ' selected' : ''}>${esc(t)}</option>`).join('')}</select>`;
    const num = (k, v, min, max, step = 1) => `<input class="input df-num" type="number" data-k="${k}" value="${v}" min="${min}" max="${max}" step="${step}">`;
    const txt = (k, v, ph = '') => `<input class="input" data-k="${k}" value="${esc(v || '')}" placeholder="${esc(ph)}">`;
    const checks = (k, opts, vals) => `<div class="df-checks">${Object.entries(opts).map(([o, t]) =>
      `<label class="chk"><input type="checkbox" data-list="${k}" value="${o}"${vals.includes(o) ? ' checked' : ''}><span>${esc(t)}</span></label>`).join('')}</div>`;
    const form = (v) => `
      <div class="card"><div class="card-h"><h2>Основное</h2></div><div class="card-b">
        ${isNew ? row('Код', `<input class="input" id="dnid" placeholder="например blog" maxlength="31">`, 'латиницей, без пробелов — по нему конвейер узнаёт направление') +
          row('Взять настройки из', `<select class="input" id="dcopy"><option value="">— с нуля —</option>${all.map(r => `<option value="${esc(r.id)}"${r.id === v._copy ? ' selected' : ''}>${esc(r.name)}</option>`).join('')}</select>`) : ''}
        ${row('Название', txt('name', v.name, 'как назвать рубрику или канал'))}
        ${row('Включено', sw('enabled', v.enabled), 'выключенное направление конвейер не трогает: папку не смотрит, выпуски не делает')}
        ${row('Режим', sel('mode', d.modes, v.mode), 'новости — из источников; тема — по запросу боту; своё видео — кидаешь запись без сценария, вставки подберутся по речи')}
        ${row('Язык', sel('language', d.langs, v.language))}
      </div></div>
      <div class="card"><div class="card-h"><h2>Сценарий</h2></div><div class="card-b">
        ${row('Длительность, мин', num('minutes', v.minutes, 1, 90))}
        ${row('Темп чтения, слов в минуту', num('words_per_min', v.words_per_min, 60, 250, 5), 'по нему считается длина текста и скорость суфлёра')}
        ${row('Шортсов', num('shorts', v.shorts, 0, 5))}
        ${row('Собирать новости из источников', sw('sources_on', v.sources_on), 'для режима «Новости из источников»')}
        ${row('Подача', sel('delivery', d.delivery || { opinion: 'Новости с моим мнением', facts: 'Только новости, без мнения' }, v.delivery || 'opinion'),
          'для новостей. С мнением — после фактов разбор и вывод ведущего, как у Наки. Только новости — факты и почему это важно, без оценок. Действует на новые сценарии')}
        ${row('Стиль', `<textarea class="input df-area" data-k="style_prompt" rows="5" placeholder="Как писать: тон, структура, чего избегать">${esc(v.style_prompt || '')}</textarea>`, 'это читает сценарист (Claude) перед каждым текстом')}
      </div></div>
      <div class="card"><div class="card-h"><h2>Вставки</h2></div><div class="card-b">
        ${row('Какие можно', checks('inserts', d.kinds, v.inserts), 'скриншоты и медиа из источника бывают только в новостях')}
        ${row('Откуда брать сток', checks('stock_sources', STOCK_T, v.stock_sources), 'ничего не выбрано — набор по умолчанию')}
      </div></div>
      <div class="card"><div class="card-h"><h2>Монтаж</h2></div><div class="card-b">
        ${row('Вырезать паузы', sw('cut_pauses', v.cut_pauses))}
        ${row('Паузы длиннее, мс', num('pause_cut_ms', v.pause_cut_ms, 200, 3000, 50), '700 — обычный темп; меньше — динамичнее')}
        ${row('Оставлять от паузы, мс', num('pause_keep_ms', v.pause_keep_ms, 0, 1000, 50), 'чтобы речь не слипалась')}
        ${row('Убирать дубли', sw('cut_retakes', v.cut_retakes), 'если фразу прочитал два раза — останется последняя')}
      </div></div>
      <div class="card"><div class="card-h"><h2>Публикация</h2></div><div class="card-b">
        ${row('YouTube', sw('publish_youtube', v.publish_youtube), 'выпуск и шортсы')}
        ${row('Доступ к видео', sel('youtube_privacy', d.privacy, v.youtube_privacy))}
        ${row('Хэштеги канала', txt('hashtags', v.hashtags || '', '#БезСказок #новости'), 'добавляются ко всем публикациям; ещё 2–3 по темам выпуска пишет Claude')}
        ${row('Facebook вместе с YouTube', sw('publish_facebook', v.publish_facebook, !cn.facebook && !v.publish_facebook),
          cn.facebook ? 'включено — после YouTube выпуск сам уйдёт и сюда, сразу для всех; выключено — только кнопкой на странице выпуска' : 'сначала подключи страницу в <a href="#/connections">«Подключениях»</a>')}
        ${row('Threads вместе с YouTube', sw('publish_threads', v.publish_threads, !cn.threads && !v.publish_threads),
          cn.threads ? 'включено — после YouTube цепочка выйдет сама, сразу для всех; выключено — только кнопкой на странице выпуска' : 'сначала подключи в <a href="#/connections">«Подключениях»</a>')}
        ${row('Telegram вместе с YouTube', sw('publish_telegram', v.publish_telegram, !cn.telegram && !v.publish_telegram),
          cn.telegram ? 'включено — после YouTube пост с обложкой и ссылкой сам уйдёт в канал; выключено — только кнопкой на странице выпуска' : 'сначала подключи канал в <a href="#/connections">«Подключениях»</a>')}
        <div class="note">На странице выпуска у каждой площадки своя кнопка «Опубликовать»: Facebook, Threads и Telegram выходят сразу, YouTube — с доступом, как выше. Включённые здесь Facebook, Threads и Telegram выйдут ещё и сами, следом за YouTube.</div>
      </div></div>
      <div class="card"><div class="card-h"><h2>Оформление и папка</h2></div><div class="card-b">
        ${row('Цвет фона карточек', `<input class="input df-color" type="color" data-k="brand_color" value="${esc(v.brand_color)}">`)}
        ${row('Акцентный цвет', `<input class="input df-color" type="color" data-k="accent_color" value="${esc(v.accent_color)}">`)}
        ${row('Логотип', txt('logo_url', v.logo_url, 'ссылка на картинку, можно пусто'))}
        ${row('Папка на Google Диске', txt('drive_folder_id', v.folder_url || v.drive_folder_id, 'ссылка на папку, куда кидаешь записи') +
          (v.folder_url ? ` <a class="btn small" href="${esc(v.folder_url)}" target="_blank" rel="noopener">${I.ext}Открыть</a>` : ''),
          'монтаж проверяет её каждые 2 минуты')}
      </div></div>`;
    const draw = (v) => {
      view.lastElementChild.outerHTML = `<div class="dir-form">${form(v)}
        <div class="actions"><button class="btn primary" id="dsave">Сохранить</button><a class="btn" href="#/directions">Отмена</a></div></div>`;
      const copySel = $('#dcopy');
      if (copySel) copySel.addEventListener('change', () => {
        const src = all.find(r => r.id === copySel.value);
        const nid = $('#dnid').value;
        draw(Object.assign({}, src || blank, { id: '', drive_folder_id: '', folder_url: '', name: $('[data-k="name"]').value, _copy: copySel.value }));
        $('#dnid').value = nid;
      });
      $('#dsave').addEventListener('click', save);
    };
    const collect = () => {
      const out = {};
      view.querySelectorAll('[data-k]').forEach(el => { out[el.dataset.k] = el.type === 'checkbox' ? el.checked : el.value; });
      ['inserts', 'stock_sources'].forEach(k => { out[k] = [...view.querySelectorAll(`[data-list="${k}"]:checked`)].map(c => c.value); });
      return out;
    };
    async function save() {
      const btn = $('#dsave'); btn.disabled = true;
      try {
        const body = collect();
        if (isNew) {
          body.id = ($('#dnid').value || '').trim().toLowerCase();
          body.copy_from = ($('#dcopy') || {}).value || null;
          await api('/api/directions', { body });
        } else {
          await api('/api/directions/' + encodeURIComponent(x.id), { method: 'PUT', body });
        }
        toast(isNew ? 'Направление добавлено' : 'Сохранено — следующий выпуск пойдёт по новым настройкам');
        location.hash = '#/directions';
      } catch (e) { toast(e.message, true); btn.disabled = false; }
    }
    draw(x || blank);
  }

  // ---------- Суфлёр ----------
  // Сценарии конвейера и свои тексты. Плеер получает текст блоками (см. studio/app/prompter.py):
  // section — раздел, para — абзац; в абзаце строки — слова, объекты — метки (вставка, пауза, шортс).
  const PKEY = 'studio.prompter.v1';
  const P_DEFAULTS = { wpm: 130, size: 46, width: 820, mirror: false, secHold: true, hints: true };
  const CLAIM = { confirmed: ['ok', 'подтверждено'], single: ['warn', 'один источник'], unconfirmed: ['err', 'не подтверждено'] };
  const pNorm = w => String(w).toLowerCase().replace(/ё/g, 'е').replace(/[^0-9a-zа-яіїєґ]+/g, '');
  const mins = (words, wpm) => { const m = words / Math.max(40, wpm); return m < 1 ? '<1 мин' : '~' + Math.round(m) + ' мин'; };
  const clock = sec => { sec = Math.max(0, Math.round(sec)); return Math.floor(sec / 60) + ':' + String(sec % 60).padStart(2, '0'); };
  function pPrefs() {
    const phone = window.matchMedia('(max-width: 820px)').matches;
    const d = Object.assign({}, P_DEFAULTS, phone ? { size: 32 } : {});
    try { return Object.assign(d, JSON.parse(localStorage.getItem(PKEY) || '{}')); } catch (e) { return d; }
  }
  function pSave(p) { try { localStorage.setItem(PKEY, JSON.stringify(p)); } catch (e) { /* хранилище недоступно — настройки живут до закрытия */ } }
  const textWords = body => String(body || '').replace(/^\s*#.*$/gm, ' ').replace(/\/{2,}/g, ' ').split(/\s+/).filter(w => pNorm(w)).length;

  async function pagePrompter(view) {
    const wpm = pPrefs().wpm;
    view.innerHTML = head('Суфлёр', 'Текст бежит по экрану в твоём темпе: сценарии конвейера и любые свои тексты',
      `<a class="btn" href="#/remote" title="Открой на телефоне — он станет пультом для суфлёра у камеры">📱 Пульт</a><a class="btn primary" href="#/prompter/edit">${I.plus}Свой текст</a>`) + loading();
    let d;
    try { d = await api('/api/prompter'); } catch (e) { view.lastElementChild.outerHTML = failBox(e.message); return; }
    const row = (href, title, meta, right) => `<li class="click" data-href="${esc(href)}"><div class="grow"><div class="title">${esc(title)}</div>
      <div class="meta">${meta.map(m => `<span>${esc(m)}</span>`).join('')}</div></div>${right}</li>`;
    const scripts = (d.scripts || []).map(s => row('#/prompter/view?s=' + encodeURIComponent(s.id), s.title,
      [when(s.created_at), s.words.toLocaleString('ru-RU') + ' ' + plural(s.words, 'слово', 'слова', 'слов'), mins(s.words, wpm)],
      `<div class="pp-row-act">${badge(s.status_label || s.status, EP_TONE[s.status] || '')}<a class="btn small primary" data-read="s:${esc(s.id)}">Читать</a>
        ${EP_BUSY.includes(s.status) ? '' : `<button class="btn small icon" data-pdel="s:${esc(s.id)}" title="Удалить" aria-label="Удалить">${I.trash}</button>`}</div>`)).join('');
    const texts = (d.texts || []).map(t => row('#/prompter/view?t=' + t.id, t.title,
      [when(t.updated_at), t.words.toLocaleString('ru-RU') + ' ' + plural(t.words, 'слово', 'слова', 'слов'), mins(t.words, wpm)],
      `<div class="pp-row-act"><a class="btn small primary" data-read="t:${t.id}">Читать</a>
        <button class="btn small icon" data-pdel="t:${t.id}" title="Удалить" aria-label="Удалить">${I.trash}</button></div>`)).join('');
    view.lastElementChild.outerHTML = `
      <div class="grid two">
        <div class="card"><div class="card-h"><h2>Сценарии конвейера</h2><span class="faint">новые сверху</span></div>
          <div class="card-b flush">${scripts ? `<ul class="rows">${scripts}</ul>` : `<div class="empty"><b>Сценариев пока нет</b>Отправь боту /news или /topic — сценарий появится здесь</div>`}</div></div>
        <div class="card"><div class="card-h"><h2>Свои тексты</h2><a href="#/prompter/edit">Добавить</a></div>
          <div class="card-b flush">${texts ? `<ul class="rows">${texts}</ul>` : `<div class="empty"><b>Своих текстов нет</b>Вставь любой текст — суфлёр прокрутит его с той скоростью, с какой ты читаешь</div>`}</div></div>
      </div>
      <div class="note" style="margin-top:16px">В суфлёре: <b>пробел</b> или касание — пауза и пуск, <b>↑ ↓</b> — скорость, <b>← →</b> — предыдущий и следующий раздел, <b>1–9</b> — к сюжету, колёсико или палец — подвинуть текст.
        <b>Кликер или педаль</b>: PageDown — пуск и пауза, PageUp — абзац назад. <b>Пульт с телефона</b>: суфлёр открыт у камеры, а на телефоне — Студия → Суфлёр → «📱 Пульт». Скорость и размер шрифта запоминаются на этом устройстве.</div>`;
    view.querySelectorAll('[data-href]').forEach(li => li.addEventListener('click', ev => {
      if (ev.target.closest('a,button')) return;
      location.hash = li.dataset.href;
    }));
    view.querySelectorAll('[data-read]').forEach(b => b.addEventListener('click', ev => { ev.preventDefault(); ev.stopPropagation(); readNow(b.dataset.read); }));
    view.querySelectorAll('[data-pdel]').forEach(b => b.addEventListener('click', async ev => {
      ev.preventDefault(); ev.stopPropagation();
      const [k, id] = [b.dataset.pdel.slice(0, 1), b.dataset.pdel.slice(2)];
      if (k === 's') {
        const s = (d.scripts || []).find(x => x.id === id);
        if (s && await deleteEpisode(s.id, s.title, true)) route();
        return;
      }
      const t = (d.texts || []).find(x => String(x.id) === id);
      if (!t || !confirm('Удалить текст «' + t.title + '»?')) return;
      try { await api('/api/prompter/texts/' + t.id, { method: 'DELETE' }); toast('Текст удалён'); route(); }
      catch (e) { toast(e.message, true); }
    }));
  }

  async function loadDoc(key) {
    const [k, id] = String(key).split(/:(.*)/s);
    return api(k === 's' ? '/api/prompter/script/' + encodeURIComponent(id) : '/api/prompter/texts/' + encodeURIComponent(id));
  }
  async function readNow(key) {
    try { openPlayer(await loadDoc(key)); } catch (e) { toast(e.message, true); }
  }

  // текст блоками → HTML (и для просмотра на странице, и для плеера)
  function blocksHtml(blocks, { counter, hints = true } = {}) {
    let html = '', wi = 0, inShort = 0;
    for (const b of blocks || []) {
      if (b.type === 'section') {
        html += `<div class="pp-sec" data-sec-at="${wi}">${esc(b.text)}</div>`;
        continue;
      }
      html += '<p>';
      for (const it of b.items || []) {
        if (typeof it === 'string') {
          html += `<span class="w${inShort ? ' sh' : ''}" data-i="${wi}">${esc(it)} </span>`;
          if (counter) counter.push(it);
          wi++;
        } else if (it.ins) {
          if (hints) html += `<span class="pp-ins" title="Здесь на экране появится вставка">${esc(INS_KIND[it.kind] || 'вставка')}</span> `;
        } else if (it.pause) {
          html += `<span class="pp-pz" title="Пауза">⏸</span> `;
        } else if (it.short) {
          inShort = it.short;
          html += `<span class="pp-shs" title="${esc(it.title || '')}">▶ шортс ${it.short}</span> `;
        } else if (it.short_end) {
          inShort = 0;
          html += `<span class="pp-she" title="Конец шортса">■</span> `;
        }
      }
      html += '</p>';
    }
    return html;
  }

  // сюжеты текста с хронометражем (как сюжеты в выпуске новостей): слова, длительность при твоём темпе, с какой минуты
  function rundown(blocks, wpm, secHold) {
    const out = [];
    let wi = 0, cur = { title: 'Начало', at: 0, words: 0, pause: 0 };
    for (const b of blocks || []) {
      if (b.type === 'section') { out.push(cur); cur = { title: b.text, at: wi, words: 0, pause: secHold && wi > 0 ? 1.5 : 0 }; continue; }
      for (const it of b.items || []) {
        if (typeof it === 'string') { cur.words++; wi++; } else if (it.pause) cur.pause += it.pause;
      }
    }
    out.push(cur);
    let start = 0;
    return out.filter(x => x.words).map(x => { const dur = x.words / Math.max(40, wpm) * 60 + x.pause; const r = Object.assign(x, { start, dur }); start += dur; return r; });
  }

  async function pagePrompterView(view, params) {
    const key = params.get('s') ? 's:' + params.get('s') : params.get('t') ? 't:' + params.get('t') : '';
    view.innerHTML = head('Суфлёр', '') + loading();
    if (!key) { location.hash = '#/prompter'; return; }
    let d;
    try { d = await loadDoc(key); } catch (e) { view.innerHTML = head('Суфлёр', '', `<a class="btn" href="#/prompter">Назад</a>`) + failBox(e.message); return; }
    const wpm = pPrefs().wpm;
    const isScript = d.kind === 'script';
    const meta = [isScript ? 'сценарий' : 'свой текст', when(d.updated_at || d.created_at),
      d.words.toLocaleString('ru-RU') + ' ' + plural(d.words, 'слово', 'слова', 'слов'), mins(d.words, wpm) + ' при ' + wpm + ' сл/мин'];
    const actions = `<a class="btn" href="#/prompter">Назад</a>
      ${isScript ? `<button class="btn" id="pcopy">${I.pencil}Копия для правки</button>${EP_BUSY.includes(d.status) ? '' : `<button class="btn" id="psdel">${I.trash}Удалить</button>`}`
        : `<a class="btn" href="#/prompter/edit?t=${d.id}">${I.pencil}Править</a><button class="btn" id="pdel">${I.trash}Удалить</button>`}
      <button class="btn primary" id="pread">${I.play.replace('fill="#fff"', 'fill="currentColor"')}Читать</button>`;
    const claims = d.claims || [];
    const pS = pPrefs();
    const rd = rundown(d.blocks, wpm, pS.secHold);
    const rdTotal = rd.reduce((a, x) => a + x.dur, 0);
    const rdCard = rd.length > 1 ? `<div class="card"><div class="card-h"><h2>Сюжеты</h2><span class="faint">${clock(rdTotal)} при ${wpm} сл/мин</span></div><div class="card-b flush">
        <ul class="rows pp-rd">${rd.map(x => `<li><span class="pp-rd-at num">${clock(x.start)}</span><div class="grow"><div class="title">${esc(x.title)}</div>
          <div class="meta"><span>${x.words.toLocaleString('ru-RU')} ${plural(x.words, 'слово', 'слова', 'слов')}</span><span>${clock(x.dur)}</span></div></div>
          <button class="btn small" data-from="${x.at}" title="Открыть суфлёр с этого сюжета">▶ Читать отсюда</button></li>`).join('')}</ul></div></div>` : '';
    const side = (rdCard || '') + (isScript ? `
      <div class="card"><div class="card-h"><h2>Шортсы</h2><span class="faint">${(d.shorts || []).length}</span></div><div class="card-b flush">
        ${(d.shorts || []).length ? `<ul class="rows">${d.shorts.map(s => `<li><span class="dot ${s.found === true ? 'ok' : 'warn'}"></span><div class="grow">
          <div class="title">${s.n}. ${esc(s.title)}</div><div class="meta">${s.found === true ? 'отмечен в тексте красным ▶ … ■ — это место читай живее'
            : s.found ? 'начало отмечено ▶, конец примерный — в сценарии он записан неточно' : 'не нашёлся в тексте'}</div></div></li>`).join('')}</ul>`
          : `<div class="empty">Шортсов нет</div>`}</div></div>
      <div class="card"><div class="card-h"><h2>Факты</h2><span class="faint">${claims.length}</span></div><div class="card-b flush">
        ${claims.length ? `<ul class="rows pp-claims">${claims.map(c => { const [tone, label] = CLAIM[c.status] || CLAIM.single; return `<li><div class="grow">
          <div>${badge(label, tone)}</div><div class="pp-claim">${esc(c.text)}</div>
          ${c.sources.length ? `<div class="meta">${c.sources.map(s => `<a href="${esc(s.url)}" target="_blank" rel="noopener" title="${esc(s.title)}">${esc(s.name || 'источник')}</a>`).join('')}</div>` : ''}
          ${c.note ? `<div class="faint" style="font-size:12.5px">${esc(c.note)}</div>` : ''}</div></li>`; }).join('')}</ul>` : `<div class="empty">Фактов нет</div>`}</div></div>`
      : `<div class="card"><div class="card-h"><h2>Как размечать свой текст</h2></div><div class="card-b pp-help">
          <p><code># Заголовок</code> — новый раздел: по разделам можно прыгать стрелками ← →, перед разделом суфлёр делает паузу.</p>
          <p><code>//</code> — пауза в этом месте (<code>///</code> — длинная).</p>
          <p>Пустая строка — новый абзац.</p></div></div>`);
    view.innerHTML = head(esc(d.title), meta.map(esc).join(' · '), actions) + `
      <div class="pp-view">
        <div class="card"><div class="card-h"><h2>Текст</h2>${isScript ? `<span class="faint">◆ вставка · ⏸ пауза · <span class="pp-shs">▶ шортс</span></span>` : ''}</div>
          <div class="card-b"><div class="pp-preview">${blocksHtml(d.blocks)}</div></div></div>
        <div class="grid">${side}</div>
      </div>`;
    $('#pread').addEventListener('click', () => openPlayer(d));
    view.querySelectorAll('[data-from]').forEach(b => b.addEventListener('click', () => openPlayer(d, { from: +b.dataset.from })));
    view.querySelectorAll('.pp-preview .pp-sec').forEach(sec => {  // заголовок сюжета в тексте — тоже «читать отсюда»
      sec.classList.add('click');
      sec.title = 'Читать отсюда';
      sec.addEventListener('click', () => openPlayer(d, { from: +sec.dataset.secAt }));
    });
    const copy = $('#pcopy');
    if (copy) copy.addEventListener('click', () => {
      try { sessionStorage.setItem('prompter.draft', JSON.stringify({ title: d.title + ' (копия)', body: d.plain || '' })); } catch (e) { /* без черновика откроется пустой редактор */ }
      location.hash = '#/prompter/edit?draft=1';
    });
    const sdel = $('#psdel');
    if (sdel) sdel.addEventListener('click', async () => {
      if (await deleteEpisode(d.id, d.title, true)) location.hash = '#/prompter';
    });
    const del = $('#pdel');
    if (del) del.addEventListener('click', async () => {
      if (!confirm('Удалить текст «' + d.title + '»?')) return;
      try { await api('/api/prompter/texts/' + d.id, { method: 'DELETE' }); toast('Текст удалён'); location.hash = '#/prompter'; }
      catch (e) { toast(e.message, true); }
    });
  }

  async function pagePrompterEdit(view, params) {
    const tid = params.get('t');
    let d = { title: '', body: '' };
    view.innerHTML = head(tid ? 'Правка текста' : 'Свой текст', '') + loading();
    if (tid) {
      try { d = await api('/api/prompter/texts/' + encodeURIComponent(tid)); }
      catch (e) { view.innerHTML = head('Правка текста', '', `<a class="btn" href="#/prompter">Назад</a>`) + failBox(e.message); return; }
    } else if (params.get('draft')) {
      try { d = Object.assign(d, JSON.parse(sessionStorage.getItem('prompter.draft') || '{}')); } catch (e) { /* нет черновика */ }
    }
    const wpm = pPrefs().wpm;
    view.innerHTML = head(tid ? 'Правка текста' : 'Свой текст', 'Вставь или напиши текст — суфлёр прокрутит его в твоём темпе',
      `<a class="btn" href="${tid ? '#/prompter/view?t=' + esc(tid) : '#/prompter'}">Отмена</a><button class="btn" id="psave">Сохранить</button><button class="btn primary" id="pgo">${I.play.replace('fill="#fff"', 'fill="currentColor"')}Сохранить и читать</button>`) + `
      <div class="card"><div class="card-b pp-edit">
        <input class="input" id="ptitle" maxlength="200" placeholder="Название (можно не писать — возьму первую строку)" value="${esc(d.title || '')}">
        <textarea class="input" id="pbody" placeholder="Текст для суфлёра…&#10;&#10;# Заголовок — новый раздел&#10;// — пауза&#10;пустая строка — новый абзац">${esc(d.body || '')}</textarea>
        <div class="pp-edit-foot"><span id="pcount" class="muted"></span><span class="faint"><code># Заголовок</code> — раздел · <code>//</code> — пауза · пустая строка — абзац</span></div>
      </div></div>`;
    const body = $('#pbody'), count = $('#pcount');
    const upd = () => { const n = textWords(body.value); count.textContent = `${n.toLocaleString('ru-RU')} ${plural(n, 'слово', 'слова', 'слов')} · ${mins(n, wpm)} при ${wpm} сл/мин`; };
    body.addEventListener('input', upd); upd();
    if (!tid && !d.body) body.focus();
    async function save(andRead) {
      const payload = { title: $('#ptitle').value, body: body.value };
      $('#psave').disabled = $('#pgo').disabled = true;
      try {
        const r = tid ? await api('/api/prompter/texts/' + encodeURIComponent(tid), { method: 'PUT', body: payload })
          : await api('/api/prompter/texts', { body: payload });
        try { sessionStorage.removeItem('prompter.draft'); } catch (e) { /* нечего чистить */ }
        toast('Сохранено');
        location.hash = '#/prompter/view?t=' + r.id;
        if (andRead) openPlayer(r);
      } catch (e) { toast(e.message, true); $('#psave').disabled = $('#pgo').disabled = false; }
    }
    $('#psave').addEventListener('click', () => save(false));
    $('#pgo').addEventListener('click', () => save(true));
  }

  // ---------- плеер суфлёра ----------
  function openPlayer(doc, opts = {}) {
    document.querySelectorAll('.pp').forEach(e => { if (e.prompter) e.prompter.close(); else e.remove(); });
    const S = pPrefs();
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
    const el = document.createElement('div');
    el.className = 'pp';
    el.innerHTML = `
      <div class="pp-stage"><div class="pp-track"></div></div>
      <div class="pp-read" aria-hidden="true"><i></i><i></i></div>
      <div class="pp-fade pp-fade-top"></div><div class="pp-fade pp-fade-bot"></div>
      <div class="pp-hud"><div class="pp-prog"><i></i></div><div class="pp-hud-row"><span class="pp-secname"></span><span class="pp-remote" title="Пульт с телефона на связи">📱 пульт</span><span class="pp-left"></span></div></div>
      <div class="pp-count hidden"></div>
      <div class="pp-done hidden"><b>Конец текста</b><span>Нажми «В начало», чтобы прочитать ещё раз</span></div>
      <div class="pp-panel hidden"></div>
      <div class="pp-bar">
        <button data-a="close" title="Закрыть (Esc)">✕</button>
        <button data-a="start" class="pp-opt" title="В начало">⏮</button>
        <button data-a="prev" title="Предыдущий раздел (←)">◀</button>
        <button data-a="play" class="pp-play" title="Пуск / пауза (пробел)">▶</button>
        <button data-a="next" title="Следующий раздел (→)">▶▏</button>
        <span class="pp-speed" title="Слов в минуту"><button data-a="slower" title="Медленнее (↓)">−</button><b><span data-v="wpm"></span><small>сл/мин</small></b><button data-a="faster" title="Быстрее (↑)">+</button></span>
        ${SR ? `<button data-a="voice" class="pp-opt" title="Следить за голосом (проба)">🎙</button>` : ''}
        <button data-a="panel" title="Настройки">⚙</button>
      </div>`;
    document.body.appendChild(el);
    document.body.classList.add('pp-open');
    const stage = $('.pp-stage', el), track = $('.pp-track', el), bar = $('.pp-bar', el), panel = $('.pp-panel', el);
    const hudProg = $('.pp-prog i', el), hudLeft = $('.pp-left', el), hudSec = $('.pp-secname', el), doneBox = $('.pp-done', el);

    // ---- разметка и измерения ----
    const words = [];
    let W = [], N = 0, lines = [], lineOf = [], holds = new Float32Array(1), holdLeft = new Float32Array(1), secs = [], paras = [];
    function build() {
      words.length = 0;
      track.innerHTML = blocksHtml(doc.blocks, { counter: words, hints: S.hints });
      N = words.length;
      W = words.map(pNorm);
      // паузы: «//» — всегда, перед разделом — если включено
      holds = new Float32Array(N + 1);
      paras = [];
      let wi = 0;
      for (const b of doc.blocks || []) {
        if (b.type === 'section') { if (S.secHold && wi > 0) holds[wi - 1] += 1.5; continue; }
        paras.push(wi);
        for (const it of b.items || []) {
          if (typeof it === 'string') wi++;
          else if (it.pause && wi > 0) holds[wi - 1] += it.pause;
        }
      }
      holdLeft = new Float32Array(N + 1);  // сумма пауз от слова i до конца — для «осталось»
      for (let i = N - 1; i >= 0; i--) holdLeft[i] = holdLeft[i + 1] + holds[i];
      secs = [...track.querySelectorAll('.pp-sec')].map(s => ({ at: +s.dataset.secAt, title: s.textContent }));
      style();
    }
    function style() {
      track.style.fontSize = S.size + 'px';
      track.style.width = `min(${S.width}px, 94vw)`;
      stage.classList.toggle('mirror', !!S.mirror);
      $('[data-v="wpm"]', el).textContent = S.wpm;
      measure();
    }
    let lineH = 60;
    function measure() {
      const spans = track.querySelectorAll('.w');
      lines = []; lineOf = new Int32Array(N);
      let lastTop = -1;
      spans.forEach((s, i) => {
        const top = s.offsetTop;
        if (Math.abs(top - lastTop) > 2) { lines.push({ top, start: i, n: 0 }); lastTop = top; }
        const L = lines.length - 1; lines[L].n++; lineOf[i] = L;
      });
      lineH = S.size * 1.45;
      seen = -1;
      paint(true);
    }
    // позиция (в пикселях дорожки) для «прочитано t слов»: плавно внутри строки
    function yAt(t) {
      if (!lines.length) return 0;
      const i = Math.max(0, Math.min(N - 1, Math.floor(t)));
      const L = lineOf[i], ln = lines[L];
      const next = L + 1 < lines.length ? lines[L + 1].top : ln.top + lineH;
      const f = Math.max(0, Math.min(1, (t - ln.start) / ln.n));
      return ln.top + f * (next - ln.top);
    }
    function tAtY(y) {
      if (!lines.length) return 0;
      let lo = 0, hi = lines.length - 1;
      while (lo < hi) { const mid = (lo + hi + 1) >> 1; if (lines[mid].top <= y) lo = mid; else hi = mid - 1; }
      const ln = lines[lo], next = lo + 1 < lines.length ? lines[lo + 1].top : ln.top + lineH;
      return Math.max(0, Math.min(N, ln.start + ln.n * Math.max(0, Math.min(1, (y - ln.top) / Math.max(1, next - ln.top)))));
    }

    // ---- состояние ----
    let t = 0, target = 0, playing = false, hold = 0, last = 0, raf = 0, seen = -1, voiceOn = false, rec = null, hideT = 0, lock = null, closed = false, fresh = true;
    const readY = () => stage.clientHeight * 0.36;
    function paint(force) {
      const y = yAt(t);
      track.style.transform = `translate(-50%, ${Math.round((readY() - y - lineH * 0.55) * 10) / 10}px)`;
      const idx = Math.floor(t);
      if (idx !== seen || force) {
        const spans = track.querySelectorAll('.w');
        const from = Math.max(0, Math.min(seen, idx)), to = Math.min(N, Math.max(seen, idx) + 1);
        for (let i = force ? 0 : from; i < (force ? N : to); i++) spans[i] && spans[i].classList.toggle('past', i < idx);
        seen = idx;
        const s = [...secs].reverse().find(x => x.at <= idx);
        hudSec.textContent = s ? s.title : (doc.title || '');
      }
      hudProg.style.width = (N ? (t / N) * 100 : 0) + '%';
      const left = (N - t) / S.wpm * 60 + (holdLeft[Math.min(N, Math.ceil(t))] || 0);
      hudLeft.textContent = clock(Math.floor(t) < N ? left : 0) + ' осталось';
    }
    function frame(ts) {
      if (closed) return;
      const dt = last ? Math.min(0.1, (ts - last) / 1000) : 0;
      last = ts;
      if (voiceOn) {
        if (Math.abs(target - t) > 0.01) t += (target - t) * Math.min(1, dt * 5);
      } else if (playing) {
        if (hold > 0) hold -= dt;
        else {
          const prev = Math.floor(t);
          t += dt * S.wpm / 60;
          for (let k = prev; k < Math.floor(t) && k < N; k++) if (holds[k] > 0) { hold = holds[k]; t = k + 1; break; }
          if (t >= N) { t = N; setPlay(false); doneBox.classList.remove('hidden'); }
        }
      }
      paint(false);
      raf = requestAnimationFrame(frame);
    }
    function setPlay(on) {
      if (on && voiceOn) voiceStop();
      playing = on;
      $('.pp-play', el).textContent = on ? '⏸' : '▶';
      el.classList.toggle('playing', on);
      if (on) { doneBox.classList.add('hidden'); hideSoon(); } else showBar();
    }
    let counting = 0;
    function toggle() {
      if (counting) return;
      if (playing) { setPlay(false); return; }
      if (t >= N) { t = 0; hold = 0; fresh = true; }
      if (fresh) {  // первый пуск (с начала или с выбранного места) — отсчёт, чтобы успеть сесть и посмотреть в камеру
        fresh = false;
        const c = $('.pp-count', el); let n = 3;
        c.classList.remove('hidden'); c.textContent = n;
        counting = setInterval(() => {
          n--;
          if (n > 0) { c.textContent = n; return; }
          clearInterval(counting); counting = 0; c.classList.add('hidden');
          if (!closed) setPlay(true);
        }, 800);
        return;
      }
      setPlay(true);
    }
    const jump = dir => {
      const idx = Math.floor(t) + (dir < 0 ? -2 : 0);
      const s = dir > 0 ? secs.find(x => x.at > idx) : [...secs].reverse().find(x => x.at <= idx);
      t = target = s ? s.at : (dir < 0 ? 0 : t); hold = 0;
      doneBox.classList.add('hidden');
    };
    const speed = d => { S.wpm = Math.max(60, Math.min(260, S.wpm + d)); pSave(S); $('[data-v="wpm"]', el).textContent = S.wpm; };
    const restart = () => { t = target = 0; hold = 0; fresh = true; setPlay(false); doneBox.classList.add('hidden'); };
    // абзац назад: сбился — к началу абзаца (если только начал его — к предыдущему); пуск не прерывается
    const backPara = () => {
      const cur = Math.floor(t);
      const p = [...paras].reverse().find(x => x <= cur - 3);
      t = target = p != null ? p : 0; hold = 0;
      doneBox.classList.add('hidden');
    };
    const bump = d => { S.size = Math.max(20, Math.min(110, S.size + d)); pSave(S); style(); };
    function showBar() { el.classList.remove('calm'); clearTimeout(hideT); if (playing) hideSoon(); }
    function hideSoon() { clearTimeout(hideT); hideT = setTimeout(() => { if (playing && panel.classList.contains('hidden')) el.classList.add('calm'); }, 2500); }

    // ---- голос: суфлёр сам двигается за тем, что ты читаешь (Chrome, нужен микрофон) ----
    const close5 = (a, b) => a === b || (a.length > 3 && b.length > 3 && a.slice(0, 4) === b.slice(0, 4));
    function follow(text) {
      const heard = String(text).split(/\s+/).map(pNorm).filter(Boolean).slice(-6);
      if (heard.length < 2) return;
      const base = Math.floor(target);
      let best = -1, score = 0;
      for (let p = Math.max(0, base - 2); p < Math.min(N, base + 45); p++) {
        let s = 0, m = 0;
        for (let k = 0; k < heard.length; k++) {
          const w = W[p - (heard.length - 1 - k)];
          if (w && close5(w, heard[k])) { s += 1 + k * 0.25; m++; }
        }
        if (m >= 2 && s > score) { score = s; best = p; }  // одно частое слово («что», «это») — не повод прыгать
      }
      if (best >= 0) target = Math.max(target, best + 1);
    }
    function voiceStart() {
      if (!SR) return;
      try {
        rec = new SR();
        rec.lang = 'ru-RU'; rec.continuous = true; rec.interimResults = true;
        rec.onresult = ev => { let s = ''; for (let i = ev.resultIndex; i < ev.results.length; i++) s += ' ' + ev.results[i][0].transcript; follow(s); };
        rec.onerror = ev => { if (['not-allowed', 'service-not-allowed', 'audio-capture'].includes(ev.error)) { voiceStop(); toast('Нет доступа к микрофону — разреши его браузеру', true); } };
        rec.onend = () => { if (voiceOn && !closed) { try { rec.start(); } catch (e) { /* уже слушает */ } } };
        setPlay(false);
        voiceOn = true; target = t;
        rec.start();
        $('[data-a="voice"]', el).classList.add('on');
        toast('Слушаю: читай вслух — текст пойдёт за голосом');
      } catch (e) { voiceOn = false; toast('Голос не включился: ' + e.message, true); }
    }
    function voiceStop() {
      voiceOn = false;
      if (rec) { try { rec.onend = null; rec.stop(); } catch (e) { /* уже остановлен */ } rec = null; }
      const b = $('[data-a="voice"]', el); if (b) b.classList.remove('on');
    }

    // ---- настройки ----
    function drawPanel() {
      const on = v => v ? ' on' : '';
      panel.innerHTML = `
        <div class="pp-p-row"><span>Читать с начала</span><button class="pp-btn" data-p="restart">⏮ В начало</button></div>
        ${SR ? `<div class="pp-p-row"><span>Следить за голосом <small class="pp-dim">проба: текст идёт за тем, что ты читаешь вслух</small></span><button class="pp-sw${on(voiceOn)}" data-p="voice"></button></div>` : ''}
        <div class="pp-p-row"><span>Размер текста</span><span class="pp-step"><button data-p="size:-4">A−</button><b>${S.size}</b><button data-p="size:4">A+</button></span></div>
        <div class="pp-p-row"><span>Ширина строки</span><span class="pp-step"><button data-p="width:-80">−</button><b>${S.width}</b><button data-p="width:80">+</button></span></div>
        <div class="pp-p-row"><span>Зеркало (для стекла суфлёра)</span><button class="pp-sw${on(S.mirror)}" data-p="mirror"></button></div>
        <div class="pp-p-row"><span>Пауза перед разделом</span><button class="pp-sw${on(S.secHold)}" data-p="secHold"></button></div>
        <div class="pp-p-row"><span>Показывать вставки</span><button class="pp-sw${on(S.hints)}" data-p="hints"></button></div>
        ${document.fullscreenEnabled ? `<div class="pp-p-row"><span>Во весь экран</span><button class="pp-sw${on(!!document.fullscreenElement)}" data-p="fs"></button></div>` : ''}
        <div class="pp-p-row pp-p-note"><span>Пульт с телефона: Студия на телефоне → Суфлёр → «Пульт»${remoteOn ? ' — <b>на связи</b>' : ''}.
          Кликер или педаль: PageDown — пуск и пауза, PageUp — абзац назад, цифры — к сюжету.</span></div>
        ${secs.length ? `<div class="pp-p-t">Разделы</div><div class="pp-secs">${secs.map((s, i) => `<button data-sec="${i}">${esc(s.title)}</button>`).join('')}</div>` : ''}`;
    }
    panel.addEventListener('click', ev => {
      ev.stopPropagation();
      const b = ev.target.closest('button'); if (!b) return;
      if (b.dataset.sec != null) { t = target = secs[+b.dataset.sec].at; hold = 0; panel.classList.add('hidden'); return; }
      const [k, v] = String(b.dataset.p || '').split(':');
      if (k === 'restart') { restart(); panel.classList.add('hidden'); return; }
      if (k === 'voice') { if (voiceOn) voiceStop(); else voiceStart(); drawPanel(); return; }
      if (k === 'size') S.size = Math.max(20, Math.min(110, S.size + +v));
      else if (k === 'width') S.width = Math.max(400, Math.min(1600, S.width + +v));
      else if (k === 'fs') { if (document.fullscreenElement) document.exitFullscreen().catch(() => {}); else el.requestFullscreen().catch(() => {}); setTimeout(drawPanel, 300); return; }
      else if (k in S) S[k] = !S[k];
      pSave(S);
      if (k === 'hints' || k === 'secHold') { const keep = t; build(); t = target = keep; } else style();
      drawPanel();
    });

    // ---- управление ----
    bar.addEventListener('click', ev => {
      ev.stopPropagation();
      const b = ev.target.closest('button'); if (!b) return;
      const a = b.dataset.a;
      showBar();
      if (a === 'close') close();
      else if (a === 'play') toggle();
      else if (a === 'start') restart();
      else if (a === 'prev') jump(-1);
      else if (a === 'next') jump(1);
      else if (a === 'slower') speed(-10);
      else if (a === 'faster') speed(10);
      else if (a === 'voice') { if (voiceOn) voiceStop(); else voiceStart(); }
      else if (a === 'panel') { drawPanel(); panel.classList.toggle('hidden'); }
    });
    // касание по тексту — пауза/пуск; тянуть пальцем — двигать текст
    let drag = null;
    stage.addEventListener('pointerdown', ev => { drag = { y: ev.clientY, t0: t, moved: false }; stage.setPointerCapture(ev.pointerId); });
    stage.addEventListener('pointermove', ev => {
      if (!drag) return;
      const dy = ev.clientY - drag.y;
      if (Math.abs(dy) > 8) drag.moved = true;
      if (drag.moved) { t = target = tAtY(yAt(drag.t0) - dy); hold = 0; showBar(); }
    });
    stage.addEventListener('pointerup', () => {
      const d = drag; drag = null;
      if (!d) return;
      if (!panel.classList.contains('hidden')) { panel.classList.add('hidden'); return; }
      if (!d.moved) toggle();
    });
    stage.addEventListener('wheel', ev => { ev.preventDefault(); t = target = tAtY(yAt(t) + ev.deltaY); hold = 0; showBar(); }, { passive: false });
    el.addEventListener('pointermove', () => showBar());
    function onKey(ev) {
      if (ev.target.closest && ev.target.closest('input,textarea')) return;
      const k = ev.key;
      if (k === ' ' || k === 'Enter') { ev.preventDefault(); toggle(); }
      else if (k === 'PageDown' || k === 'F5' || k === 'b' || k === 'B' || k === 'и' || k === 'И' || k === '.' || k === 'ю') { ev.preventDefault(); toggle(); }
      else if (k === 'PageUp') { ev.preventDefault(); backPara(); }
      else if (k === 'Home') { ev.preventDefault(); restart(); }
      else if (/^[1-9]$/.test(k) && secs[+k - 1]) { ev.preventDefault(); t = target = secs[+k - 1].at; hold = 0; doneBox.classList.add('hidden'); }
      else if (k === 'Escape' && playing) { ev.preventDefault(); setPlay(false); }
      else if (k === 'ArrowUp') { ev.preventDefault(); speed(10); }
      else if (k === 'ArrowDown') { ev.preventDefault(); speed(-10); }
      else if (k === 'ArrowLeft') { ev.preventDefault(); jump(-1); }
      else if (k === 'ArrowRight') { ev.preventDefault(); jump(1); }
      else if (k === '+' || k === '=') bump(4);
      else if (k === '-' || k === '_') bump(-4);
      else if (k === 'm' || k === 'ь') { S.mirror = !S.mirror; pSave(S); style(); }
      else if (k === 'Escape' && !document.fullscreenElement) close();
      else return;
      showBar();
    }
    document.addEventListener('keydown', onKey, true);
    const onResize = () => measure();
    window.addEventListener('resize', onResize);
    // экран не гаснет, пока открыт суфлёр
    async function wake() { try { if ('wakeLock' in navigator && !document.hidden) lock = await navigator.wakeLock.request('screen'); } catch (e) { lock = null; } }
    const onVis = () => { if (!document.hidden && !closed) wake(); };
    document.addEventListener('visibilitychange', onVis);
    let remoteT = 0, remoteOn = false;
    const doCmd = c => {
      if (c === 'toggle') toggle();
      else if (c === 'faster') speed(10);
      else if (c === 'slower') speed(-10);
      else if (c === 'next') jump(1);
      else if (c === 'prev') jump(-1);
      else if (c === 'back') backPara();
      else if (c === 'start') restart();
      else if (c === 'bigger') bump(4);
      else if (c === 'smaller') bump(-4);
      else if (c === 'mirror') { S.mirror = !S.mirror; pSave(S); style(); }
      showBar();
    };
    const lineNow = () => {
      if (!lines.length || !N) return '';
      const ln = lines[lineOf[Math.max(0, Math.min(N - 1, Math.floor(t)))]];
      return words.slice(ln.start, ln.start + ln.n).join(' ');
    };
    async function remoteSync() {
      if (closed) return;
      try {
        const r = await api('/api/prompter/remote/state', { noAuthRedirect: true, body: { open: true, title: doc.title || '', sec: hudSec.textContent,
          line: lineNow(), left: hudLeft.textContent.replace(' осталось', ''), pct: N ? t / N * 100 : 0, wpm: S.wpm, size: S.size,
          playing, mirror: !!S.mirror, voice: voiceOn, done: N > 0 && t >= N, counting: !!counting } });
        (r.cmds || []).forEach(doCmd);
        if (!!r.remote !== remoteOn) { remoteOn = !!r.remote; el.classList.toggle('remote', remoteOn); }
      } catch (e) { /* сеть моргнула — спросим ещё раз */ }
      if (!closed) remoteT = setTimeout(remoteSync, 400);
    }
    function close() {
      if (closed) return;
      closed = true;
      clearTimeout(remoteT);
      api('/api/prompter/remote/state', { noAuthRedirect: true, body: { open: false } }).catch(() => {});
      cancelAnimationFrame(raf); clearInterval(counting); clearTimeout(hideT);
      voiceStop();
      if (lock) lock.release().catch(() => {});
      document.removeEventListener('keydown', onKey, true);
      document.removeEventListener('visibilitychange', onVis);
      window.removeEventListener('resize', onResize);
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
      document.body.classList.remove('pp-open');
      el.remove();
    }
    build();
    if (opts.from > 0) { t = target = Math.min(N, opts.from); }  // «Читать отсюда» — с выбранного сюжета
    wake();
    if (!N) doneBox.classList.remove('hidden');
    raf = requestAnimationFrame(frame);
    remoteSync();
    // для проверки и будущих кнопок (Студия, расширения): управление суфлёром снаружи
    el.prompter = { toggle, jump, speed, close, back: backPara, cmd: doCmd, state: () => ({ t, N, playing, wpm: S.wpm, voice: voiceOn, target, remote: remoteOn, size: S.size, mirror: !!S.mirror }),
      seek: v => { t = target = Math.max(0, Math.min(N, v)); },
      hear: text => { if (!voiceOn) { setPlay(false); voiceOn = true; target = t; } follow(text); } };  // то же, что делает микрофон: для проверки без голоса
  }

  // ---------- пульт суфлёра: телефон управляет суфлёром у камеры ----------
  async function pageRemote(view) {
    view.innerHTML = `<div class="rm">
      <div class="rm-top"><div><h1>Пульт</h1><p class="faint">управляет суфлёром, открытым на другом устройстве</p></div><span class="rm-on badge">ищу суфлёр…</span></div>
      <div class="rm-now card"><div class="card-b"><div class="rm-title"></div><div class="rm-sec faint"></div>
        <div class="pp-prog rm-prog"><i></i></div><div class="rm-meta faint"></div><div class="rm-line"></div></div></div>
      <div class="rm-off note hidden"><b>Суфлёр не открыт</b>На устройстве у камеры открой Студию → Суфлёр → текст → «Читать». Пульт подхватит его сам — нужен тот же вход в Студию.</div>
      <div class="rm-pad">
        <button class="rm-b" data-c="prev" aria-label="Предыдущий сюжет">◀<small>сюжет</small></button>
        <button class="rm-b rm-play" data-c="toggle" aria-label="Пуск или пауза">▶</button>
        <button class="rm-b" data-c="next" aria-label="Следующий сюжет">▶<small>сюжет</small></button>
        <button class="rm-b" data-c="back">↺<small>абзац назад</small></button>
        <button class="rm-b" data-c="slower">−<small>медленнее</small></button>
        <button class="rm-b" data-c="faster">+<small>быстрее</small></button>
        <button class="rm-b" data-c="smaller">A−<small>шрифт</small></button>
        <button class="rm-b" data-c="bigger">A+<small>шрифт</small></button>
        <button class="rm-b" data-c="mirror">⇋<small>зеркало</small></button>
        <button class="rm-b rm-wide" data-c="start">⏮<small>в начало</small></button>
      </div></div>`;
    const $$ = q => view.querySelector(q);
    let st = null, busy = false, stop = false;
    const draw = r => {
      st = r.online ? r.state : null;
      const on = $$('.rm-on');
      on.textContent = st ? 'на связи' : 'суфлёр не открыт';
      on.className = 'rm-on badge ' + (st ? 'ok' : '');
      $$('.rm-off').classList.toggle('hidden', !!st);
      $$('.rm-now').classList.toggle('hidden', !st);
      view.querySelectorAll('.rm-b').forEach(b => { b.disabled = !st; });
      if (!st) return;
      $$('.rm-title').textContent = st.title || 'Текст';
      $$('.rm-sec').textContent = st.sec && st.sec !== st.title ? st.sec : '';
      $$('.rm-prog i').style.width = (st.pct || 0) + '%';
      $$('.rm-meta').textContent = [st.counting ? 'отсчёт…' : st.done ? 'конец текста' : st.playing ? 'идёт' : 'пауза', st.left ? 'осталось ' + st.left : '',
        st.wpm + ' сл/мин', st.mirror ? 'зеркало' : ''].filter(Boolean).join(' · ');
      $$('.rm-line').textContent = st.line || '';
      const play = $$('.rm-play');
      play.textContent = st.playing || st.counting ? '⏸' : '▶';
      play.classList.toggle('on', !!(st.playing || st.counting));
    };
    view.querySelectorAll('.rm-b').forEach(b => b.addEventListener('click', async () => {
      if (navigator.vibrate) navigator.vibrate(12);
      busy = true;
      try { draw(await api('/api/prompter/remote/cmd', { body: { cmd: b.dataset.c } })); } catch (e) { toast(e.message, true); }
      busy = false;
    }));
    const here = () => location.hash.split('?')[0] === '#/remote';
    const gen = pageRemote.gen = (pageRemote.gen || 0) + 1;  // ушёл и вернулся — старый опрос сам закончится
    while (!stop && here() && gen === pageRemote.gen) {  // пока открыт пульт — раз в 0,7 с спрашиваем, что в суфлёре
      if (!busy) { try { draw(await api('/api/prompter/remote')); } catch (e) { if (!here()) break; } }
      await new Promise(r => setTimeout(r, 700));
      if (!document.body.contains(view.querySelector('.rm'))) stop = true;
    }
  }

  // ---------- Журнал ----------
  const isErr = r => ['error', 'crashed'].includes(r.status);
  function runRow(r, o = {}) {
    const [tone, label] = RUN_TONE[r.status] || ['', r.status];
    const err = r.error ? `${r.error.node ? r.error.node + ': ' : ''}${r.error.message || ''}` : '';
    const acked = isErr(r) && r.ack;
    return `<li class="click${acked ? ' acked' : ''}" data-run="${esc(r.id)}"><span class="dot ${acked ? '' : tone.split(' ')[0]}" title="${esc(label)}"></span>
      <div class="grow"><div class="title">${esc(r.workflow)}</div><div class="meta"><span>${when(r.started_at)}</span><span>${dur(r.duration_s)}</span><span class="faint">№${esc(r.id)}</span></div>
      ${err ? `<div class="errtxt">${esc(err)}</div>` : ''}</div><div class="side-val">${acked ? badge('разобрано', '') : badge(label, tone)}
      ${o.ack && isErr(r) && !r.ack ? `<button class="btn small" data-ack="${esc(r.id)}" title="Ошибка больше не будет гореть красным в меню">Разобрано</button>` : ''}</div></li>`;
  }
  function bindRuns(root) {
    root.querySelectorAll('[data-run]').forEach(el => el.addEventListener('click', ev => { if (!ev.target.closest('[data-ack]')) openRun(el.dataset.run); }));
    root.querySelectorAll('[data-ack]').forEach(b => b.addEventListener('click', async ev => {
      ev.stopPropagation();
      b.disabled = true;
      try {
        await api('/api/runs/ack', { body: { ids: [b.dataset.ack] } });
        const li = b.closest('li');
        li.classList.add('acked');
        li.querySelector('.dot').className = 'dot';
        b.closest('.side-val').innerHTML = badge('разобрано', '');
        state.errors24 = Math.max(0, state.errors24 - 1); markNav();
      } catch (e) { toast(e.message, true); b.disabled = false; }
    }));
  }

  async function pageLogs(view, params) {
    const mode = ['important', 'all', 'errors'].includes(params.get('view')) ? params.get('view') : 'important';
    const seg = `<div class="seg">${[['important', 'Важные'], ['all', 'Все'], ['errors', 'Ошибки']].map(([k, t]) =>
      `<button data-v="${k}" class="${k === mode ? 'on' : ''}">${t}</button>`).join('')}</div>`;
    view.innerHTML = head('Журнал', 'Каждый запуск конвейера. Нажми на строку — увидишь, где и что сломалось.',
      `${seg}<button class="btn" id="rf">${I.refresh}Обновить</button><button class="btn hidden" id="ackall" title="Все ошибки за неделю — разобраны: красный счётчик в меню погаснет">Всё разобрано</button>${reportBtn}`) +
      `<div class="note" style="margin-bottom:16px">Если что-то пошло не так — нажми «Скачать отчёт JSON» и пришли файл Claude. Ключи и токены в файле скрыты.</div>
       <div class="card"><div class="card-b flush" id="runs">${loading()}</div></div>
       <div class="faint" id="quiet" style="margin-top:10px;font-size:12.5px"></div>
       <div style="text-align:center;margin-top:14px"><button class="btn hidden" id="more">Показать ещё</button></div>`;
    view.querySelectorAll('[data-v]').forEach(b => b.addEventListener('click', () => { location.hash = '#/logs' + (b.dataset.v === 'important' ? '' : '?view=' + b.dataset.v); }));
    $('#rf').addEventListener('click', () => route());
    let cursor = null, hidden = 0;
    const box = $('#runs');
    async function load(append) {
      let d;
      try { d = await api(`/api/runs?limit=40&view=${mode}` + (cursor ? '&cursor=' + encodeURIComponent(cursor) : '')); }
      catch (e) { box.innerHTML = `<div class="empty"><b>Журнал недоступен</b>${esc(e.message)}</div>`; return; }
      cursor = d.next_cursor;
      const html = (d.runs || []).map(r => runRow(r, { ack: true })).join('');
      if ((d.runs || []).some(r => isErr(r) && !r.ack)) $('#ackall').classList.remove('hidden');
      if (append) box.querySelector('ul').insertAdjacentHTML('beforeend', html);
      else box.innerHTML = html ? `<ul class="rows">${html}</ul>` : `<div class="empty"><b>${mode === 'errors' ? 'Ошибок нет' : 'Запусков нет'}</b></div>`;
      hidden += d.hidden_quiet || 0;
      $('#quiet').textContent = mode === 'important' && hidden ? `Скрыто пустых проверок по расписанию: ${hidden} (монтаж смотрит папку каждые 2 минуты). Показать их — вкладка «Все».` : '';
      bindRuns(box);
      $('#more').classList.toggle('hidden', !cursor);
    }
    $('#more').addEventListener('click', () => load(true));
    $('#ackall').addEventListener('click', async ev => {
      if (!confirm('Отметить все ошибки за неделю как разобранные? Они останутся в журнале, но перестанут гореть красным в меню и на «Обзоре».')) return;
      ev.target.disabled = true;
      try { const r = await api('/api/runs/ack', { body: { all: true } }); toast(r.acked ? `Отмечено: ${r.acked}` : 'Новых ошибок нет'); state.errors24 = 0; markNav(); route(); }
      catch (e) { toast(e.message, true); ev.target.disabled = false; }
    });
    load(false);
  }

  async function openRun(id) {
    const d0 = drawer('Запуск №' + esc(id), '', loading());
    let r;
    try { r = await api('/api/runs/' + encodeURIComponent(id)); } catch (e) { d0.querySelector('.d-b').innerHTML = failBox(e.message); return; }
    const [tone, label] = RUN_TONE[r.status] || ['', r.status];
    d0.querySelector('.d-h h2').textContent = r.workflow || 'Запуск';
    d0.querySelector('.d-h h2').insertAdjacentHTML('afterend', `<div class="muted" style="margin-top:4px">№${esc(r.id)} · ${dt(r.started_at)}</div>`);
    const nodes = r.nodes || [];
    const slow = Math.max(1, ...nodes.map(n => n.ms || 0));
    d0.querySelector('.d-b').innerHTML = `
      <div class="actions" style="margin-bottom:16px">${badge(label, tone)}
        <a class="btn small" href="/api/runs/${encodeURIComponent(r.id)}/download" download>${I.download}Скачать JSON</a>
        ${r.n8n_link ? `<a class="btn small" href="${esc(r.n8n_link)}" target="_blank" rel="noopener">${I.ext}Открыть в n8n</a>` : ''}</div>
      ${r.error ? `<div class="errbox"><b>${esc(r.error.node || 'Ошибка')}</b><div style="margin-top:4px">${esc(r.error.message || '')}</div>
        ${r.error.description ? `<div class="muted" style="margin-top:6px">${esc(r.error.description)}</div>` : ''}</div>` : ''}
      <div class="section-t">Как прошло</div>
      <dl class="kv"><dt>Начало</dt><dd>${dt(r.started_at)}</dd><dt>Длительность</dt><dd>${dur(r.duration_s)}</dd>
        <dt>Шагов выполнено</dt><dd>${r.nodes_total}</dd><dt>Последний шаг</dt><dd>${esc(r.last_node || '—')}</dd></dl>
      <div class="section-t">Шаги по порядку</div>
      <div class="card scroll-x"><table class="table"><tr><th>Шаг</th><th class="r">Время</th><th class="r">Элементов</th></tr>
        ${nodes.map(n => `<tr><td><span class="dot ${n.error ? 'err' : n.status === 'success' ? 'ok' : 'warn'}" style="display:inline-block;margin-right:8px"></span>${esc(n.node)}
          ${n.error ? `<div class="errtxt" style="white-space:normal">${esc(n.error.message || '')}</div>` : ''}
          <div class="bar" style="height:3px;margin-top:6px"><i style="width:${Math.round((n.ms || 0) / slow * 100)}%"></i></div></td>
          <td class="r num">${n.ms != null ? (n.ms >= 1000 ? (n.ms / 1000).toFixed(1) + ' с' : n.ms + ' мс') : '—'}</td><td class="r num">${n.items ?? '—'}</td></tr>`).join('')}
      </table></div>`;
  }

  // ---------- Расходы ----------
  function chart(byDay) {
    const map = Object.fromEntries((byDay || []).map(d => [d.day, d.usd]));
    const days = [];
    for (let i = 29; i >= 0; i--) {
      const d = new Date(Date.now() - i * 86400000);
      const key = fYMD.format(d);
      days.push({ key, label: fDay.format(d), usd: map[key] || 0 });
    }
    const max = Math.max(0.01, ...days.map(d => d.usd));
    return `<div class="chart">${days.map(d => `<div class="col ${d.usd ? '' : 'zero'}" title="${esc(d.label)}: ${money(d.usd)}"><i style="height:${Math.max(1.5, d.usd / max * 100)}%"></i></div>`).join('')}</div>
      <div class="chart-axis"><span>${esc(days[0].label)}</span><span>${esc(days[15].label)}</span><span>сегодня</span></div>`;
  }

  async function pageCosts(view) {
    view.innerHTML = head('Расходы', 'Сколько стоит Claude: по дням, моделям и процессам', `<button class="btn" id="scan">${I.refresh}Пересчитать</button>`) + loading();
    let d;
    try { d = await api('/api/costs?days=30'); } catch (e) { view.lastElementChild.outerHTML = failBox(e.message); return; }
    const b = d.balance || {};
    view.innerHTML = head('Расходы', 'Сколько стоит Claude: по дням, моделям и процессам', `<button class="btn" id="scan">${I.refresh}Пересчитать</button>`) + `
      <div class="card" style="margin-bottom:16px"><div class="card-h"><h2>Баланс Claude</h2>${b.known ? (b.low ? badge('пора пополнить', 'err') : badge('в порядке', 'ok')) : ''}</div>
        <div class="card-b"><div class="grid two">
          <div>${b.known ? `<div class="big-num num" style="${b.low ? 'color:var(--err)' : ''}">${money(b.estimate)}</div>
            <div class="muted" style="margin-top:6px">оценка: записано ${money(b.baseline_usd)} ${dt(b.baseline_at)}, потрачено с тех пор ${money(b.spent_since)}</div>`
            : `<div class="big-num" style="font-size:24px">Остаток не указан</div><div class="muted" style="margin-top:6px">Впиши, сколько сейчас на счету в Claude Console — дальше Студия будет вычитать расходы сама.</div>`}
            <div class="note" style="margin-top:14px">Студия считает траты конвейера и Mario по данным запусков n8n. Точный остаток — в Claude Console → Billing; после пополнения впиши новую сумму сюда.</div></div>
          <div>
            <div class="form-row"><label for="bal">Сейчас на счету, $</label></div>
            <div class="form-row" style="margin:6px 0 16px"><input class="input num" id="bal" inputmode="decimal" placeholder="например 19.75" style="width:160px"><button class="btn primary" id="balsave">Сохранить</button></div>
            <div class="form-row"><label for="thr">Предупредить в Telegram, когда останется, $</label></div>
            <div class="form-row" style="margin-top:6px"><input class="input num" id="thr" inputmode="decimal" value="${esc(b.threshold ?? 5)}" style="width:100px"><button class="btn" id="thrsave">Сохранить порог</button></div>
          </div></div></div></div>
      <div class="grid kpis">
        <div class="kpi card"><div class="label">Сегодня</div><div class="value num">${money(d.today)}</div></div>
        <div class="kpi card"><div class="label">7 дней</div><div class="value num">${money(d.d7)}</div></div>
        <div class="kpi card"><div class="label">30 дней</div><div class="value num">${money(d.d30)}</div></div>
        <div class="kpi card"><div class="label">Всего учтено</div><div class="value num">${money(d.total)}</div><div class="sub">${d.runs} ${plural(d.runs, 'запуск', 'запуска', 'запусков')}</div></div>
      </div>
      <div class="card" style="margin-bottom:16px"><div class="card-h"><h2>По дням, 30 дней</h2></div><div class="card-b">${chart(d.by_day)}</div></div>
      <div class="grid two">
        <div class="card"><div class="card-h"><h2>По процессам</h2></div><div class="card-b flush scroll-x">${d.by_workflow.length ? `<table class="table"><tr><th>Процесс</th><th class="r">Запусков</th><th class="r">$</th></tr>
          ${d.by_workflow.map(w => `<tr><td>${esc(w.workflow)}</td><td class="r num">${w.runs}</td><td class="r num">${money(w.usd)}</td></tr>`).join('')}</table>` : '<div class="empty">Пока нет данных</div>'}</div></div>
        <div class="card"><div class="card-h"><h2>По моделям</h2></div><div class="card-b flush scroll-x">${d.by_model.length ? `<table class="table"><tr><th>Модель</th><th class="r">Вход / выход</th><th class="r">$</th></tr>
          ${d.by_model.map(m => `<tr><td class="mono">${esc(m.model)}</td><td class="r num">${Number(m.input_tokens || 0).toLocaleString('ru-RU')} / ${Number(m.output_tokens || 0).toLocaleString('ru-RU')}</td><td class="r num">${money(m.usd)}</td></tr>`).join('')}</table>` : '<div class="empty">Пока нет данных</div>'}</div></div>
      </div>`;
    $('#balsave').addEventListener('click', async () => {
      try { await api('/api/balance', { body: { amount: $('#bal').value } }); toast('Остаток сохранён'); route(); } catch (e) { toast(e.message, true); }
    });
    $('#thrsave').addEventListener('click', async () => {
      try { await api('/api/balance/threshold', { body: { value: $('#thr').value } }); toast('Порог сохранён'); route(); } catch (e) { toast(e.message, true); }
    });
    $('#scan').addEventListener('click', async ev => {
      ev.target.disabled = true;
      try { const r = await api('/api/costs/scan', { method: 'POST' }); toast('Готово: новых запусков ' + r.scanned); route(); } catch (e) { toast(e.message, true); ev.target.disabled = false; }
    });
  }

  // ---------- Источники ----------
  const SRC_IC = { rss: I.globe, telegram: I.tg, youtube: I.yt };
  const SRC_TONE = { ok: 'ok', err: 'err', warn: 'warn', off: '', new: 'info' };
  const WEIGHTS = [[1, 'обычный'], [2, 'важный'], [3, 'главный']];
  let SRC_FILTER = 'all';  // какие источники показывать: все, только включённые, только выключенные
  let SRC_DIR = null;      // открытое направление («папка»), например «Новости»
  let SRC_GROUP = 'all';   // открытая вкладка группы
  const DIR_LABEL = { news: 'Новости' };
  const dirLabel = x => DIR_LABEL[x] || x;

  function hostOf(s) {
    if (s.type === 'telegram') return '@' + s.url;
    if (s.type === 'youtube' && !s.site_url) return 'youtube.com';
    try { return new URL(s.site_url || s.url).host.replace(/^www\./, ''); } catch (e) { return s.url; }
  }
  // группы для выпадающего списка; «none» — без группы
  const roleOptions = (roles, cur) => roles.map(r => `<option value="${esc(r.key)}"${r.key === cur ? ' selected' : ''}>${esc(r.label)}</option>`).join('') +
    `<option value="none"${!cur || cur === 'none' ? ' selected' : ''}>Без группы</option>`;
  const roleLabel = (roles, key) => key === 'auto' ? 'группу определит Студия' : (!key || key === 'none') ? 'без группы' : ((roles.find(r => r.key === key) || {}).label || key);
  function roleFromHeader(text, roles) {
    const t = text.toLowerCase();
    if (/без групп/.test(t)) return 'none';
    const hit = roles.find(r => t.includes(r.label.toLowerCase()) || t.includes(r.key));
    if (hit) return hit.key;
    const map = [['первоисточ', 'official'], ['официал', 'official'], ['украин', 'ua_media'], ['фронт', 'front'], ['росси', 'ru_inside'],
      ['мир', 'world'], ['сша', 'world'], ['мнени', 'opinion'], ['разбор', 'opinion'], ['сигнал', 'signal'], ['пропаганд', 'signal']];
    const m = map.find(([k]) => t.includes(k));
    return m ? m[1] : 'auto';
  }
  function parseBulk(text, roles, defRole) {
    const out = [];
    let role = defRole || 'auto';
    for (const raw of String(text || '').split(/\r?\n/)) {
      const line = raw.trim();
      if (!line) continue;
      if (line.startsWith('#')) { role = roleFromHeader(line.slice(1), roles); continue; }
      const parts = line.split('|').map(x => x.trim());
      let link = parts[0], name = parts[1] || '';
      if (!/[./@]/.test(link) && parts[1] && /[./@]/.test(parts[1])) { link = parts[1]; name = parts[0]; }
      out.push({ link, name, role });
    }
    return out;
  }

  function srcRow(s, dirs, roles) {
    const st = s.enabled && (s.state === 'ok' || s.state === 'warn')
      ? `<span>${s.d1} за сутки · ${s.d7} за неделю${s.last_item_at ? ' · последний ' + when(s.last_item_at) : ''}</span>` : '';
    const sel = `<select class="inline-sel" data-move="${s.id}" aria-label="Группа источника «${esc(s.name)}»" title="Перенести в другую группу">${roleOptions(roles, s.role || 'none')}</select>`;
    const tip = !s.role && s.role_guess
      ? `<div class="guess"><span>Подходит группа <b>«${esc(s.role_guess_label)}»</b>${s.role_guess_why ? ' — ' + esc(s.role_guess_why) : ''}</span>
          <button class="btn small" data-accept="${esc(s.role_guess)}">Перенести</button></div>` : '';
    return `<li data-id="${s.id}" class="src${s.enabled ? '' : ' off'}">
      <div class="src-ic ${esc(s.type)}">${SRC_IC[s.type] || I.rss}</div>
      <div class="grow">
        <div class="title">${esc(s.name)}</div>
        <div class="meta"><a href="${esc(s.site_url || s.url)}" target="_blank" rel="noopener">${esc(hostOf(s))}</a><span>${esc(s.type_label)}</span>
          <span>${esc(s.weight_label)}</span>${dirs.length > 1 ? `<span>${esc(s.direction_id)}</span>` : ''}<span class="grp">группа: ${sel}</span></div>
        <div class="meta"><span class="st ${SRC_TONE[s.state] || ''}">${esc(s.state_text)}</span>${st}</div>
        <div class="meta"><span>Берём: ${esc(s.takes || '—')}</span>${s.total ? `<a href="#/sources?src=${s.id}">материалы (${s.total}) →</a>` : ''}</div>
        ${tip}
      </div>
      <div class="src-act">
        <label class="switch" title="${s.enabled ? 'Выключить' : 'Включить'}"><input type="checkbox" data-toggle="${s.id}" aria-label="Включён"${s.enabled ? ' checked' : ''}><i></i></label>
        <button class="btn small icon" data-act="edit" title="Изменить" aria-label="Изменить">${I.pencil}</button>
        <button class="btn small icon" data-act="del" title="Удалить" aria-label="Удалить">${I.trash}</button>
      </div></li>`;
  }
  function srcEditForm(s, dirs, roles) {
    return `<div class="src-ic ${esc(s.type)}">${SRC_IC[s.type] || I.rss}</div>
      <div class="grow src-form">
        <input class="input" data-f="name" value="${esc(s.name)}" maxlength="120" placeholder="Название">
        <select class="input" data-f="role" aria-label="Группа">${roleOptions(roles, s.role || 'none')}</select>
        <select class="input" data-f="weight">${WEIGHTS.map(([v, t]) => `<option value="${v}"${v === s.weight ? ' selected' : ''}>Важность: ${t}</option>`).join('')}</select>
        ${dirs.length > 1 ? `<select class="input" data-f="direction_id">${dirs.map(x => `<option${x === s.direction_id ? ' selected' : ''}>${esc(x)}</option>`).join('')}</select>` : ''}
      </div>
      <div class="src-act"><button class="btn small primary" data-act="save">Сохранить</button><button class="btn small" data-act="cancel">Отмена</button></div>`;
  }
  function itemBadge(it) {
    if (it.content_kind === 'transcript') return badge('расшифровка', 'ok');
    if (it.content_kind === 'article' || it.content_kind === 'post') return badge('полный текст', 'ok');
    if (it.content_kind === 'description') return badge('только описание', 'warn');
    if (it.content_error) return badge('текст не достали', 'warn');
    return badge('текст скоро', 'plain');
  }
  const itemRow = it => `<li class="click${it.in_script === false ? ' off' : ''}" data-item="${it.id}"><div class="grow"><div class="title">${esc(it.title || it.url)}</div>
    <div class="meta"><span>${esc(it.source_name || '—')}</span><span>${when(it.published_at || it.collected_at)}</span>${itemBadge(it)}${it.source_role === 'signal' ? badge('только сигнал', 'warn') : ''}${it.in_script === false ? badge('источник выключен — не в сценарии', 'plain') : ''}${it.used_in ? badge('в выпуске', 'ok') : ''}</div></div></li>`;

  function ytLink(url, sec) {
    const m = String(url || '').match(/[?&]v=([A-Za-z0-9_-]{11})/);
    return m ? `https://www.youtube.com/watch?v=${m[1]}&t=${sec}s` : null;
  }
  async function openItem(id) {
    const d = drawer('Материал', '', loading());
    let it;
    try { it = await api('/api/items/' + id); } catch (e) { d.querySelector('.d-b').innerHTML = failBox(e.message); return; }
    d.querySelector('.d-h h2').textContent = it.title || 'Материал';
    d.querySelector('.d-h h2').insertAdjacentHTML('afterend', `<div class="muted" style="margin-top:4px">${esc(it.src_name || it.source_name || '')} · ${dt(it.published_at || it.collected_at)}</div>`);
    const isImg = it.media_url && /\.(jpe?g|png|webp|gif)(\?|$)/i.test(it.media_url);
    let text = '';
    if (it.content) {
      text = it.content.split(/\n+/).filter(Boolean).map(line => {
        let h = esc(line);
        if (it.content_kind === 'transcript') {
          h = h.replace(/^\[(?:(\d+):)?(\d\d):(\d\d)\]/, (m0, hh, mm, ss) => {
            const link = ytLink(it.url, Number(hh || 0) * 3600 + Number(mm) * 60 + Number(ss));
            return link ? `<a class="ts" href="${link}" target="_blank" rel="noopener">${hh ? hh + ':' : ''}${mm}:${ss}</a>` : m0;
          });
        }
        return `<p>${h}</p>`;
      }).join('');
    }
    const why = it.content_error ? `Не получилось достать текст: ${esc(it.content_error)}.` : 'Текст ещё не достали — он появится после следующего сбора.';
    d.querySelector('.d-b').innerHTML = `
      <div class="actions" style="margin-bottom:14px"><a class="btn small" href="${esc(it.url)}" target="_blank" rel="noopener">${I.ext}Открыть оригинал</a>
        ${it.media_url && !isImg ? `<a class="btn small" href="${esc(it.media_url)}" target="_blank" rel="noopener">${I.ext}Фото или видео</a>` : ''}
        ${it.used_in ? badge('использован в выпуске', 'ok') : ''}</div>
      ${isImg ? `<img class="item-media" src="${esc(it.media_url)}" alt="" loading="lazy" referrerpolicy="no-referrer">` : ''}
      ${it.content_kind === 'description' ? `<div class="note warnnote" style="margin-bottom:12px">Это только описание видео. ${esc(it.content_error ? 'Расшифровку взять не получилось: ' + it.content_error + '.' : 'Расшифровку попробуем взять при следующем сборе.')}</div>` : ''}
      <div class="section-t">${esc(it.content_label || 'Текст')}${it.content_chars ? ` · ${Number(it.content_chars).toLocaleString('ru-RU')} знаков` : ''}</div>
      ${text ? `<div class="item-text">${text}</div>` : `<p class="muted">${why}</p>${it.summary ? `<div class="item-text"><p>${esc(it.summary)}</p></div>` : ''}`}`;
  }

  const hashParams = () => new URLSearchParams(location.hash.split('?')[1] || '');
  function refreshSources(view, delays = [6000, 20000]) {
    delays.forEach(ms => setTimeout(() => {
      if (location.hash.split('?')[0] === '#/sources' && !document.querySelector('.add-src, li.src.editing, .drawer')) pageSources(view, hashParams());
    }, ms));
  }

  function applySrcFilter(root) {
    const rows = root.querySelectorAll('li.src');
    rows.forEach(li => {
      const off = li.classList.contains('off');
      li.classList.toggle('hidden', SRC_FILTER === 'on' ? off : SRC_FILTER === 'off' ? !off : false);
    });
    let shown = 0;
    root.querySelectorAll('.src-group').forEach(g => {
      const n = g.querySelectorAll('li.src:not(.hidden)').length;
      const mine = SRC_GROUP === 'all' || g.dataset.role === SRC_GROUP;
      if (mine) shown += n;
      g.classList.toggle('hidden', !n || !mine);
    });
    root.querySelectorAll('[data-filter]').forEach(b => { const on = b.dataset.filter === SRC_FILTER; b.classList.toggle('on', on); b.setAttribute('aria-pressed', String(on)); });
    root.querySelectorAll('[data-gtab]').forEach(b => { const on = b.dataset.gtab === SRC_GROUP; b.classList.toggle('on', on); b.setAttribute('aria-selected', String(on)); });
    const note = root.querySelector('#filtnote');
    if (note) note.textContent = rows.length && !shown ? (SRC_FILTER === 'off' ? 'выключенных здесь нет' : SRC_FILTER === 'on' ? 'включённых здесь нет' : '') : '';
  }

  async function pageSources(view, params) {
    const srcId = params && params.get ? params.get('src') : null;
    const actions = `<button class="btn" id="collect">${I.refresh}Собрать сейчас</button><button class="btn" id="bulksrc">${I.plus}Добавить списком</button>` +
      `<button class="btn primary" id="addsrc">${I.plus}Добавить источник</button>`;
    const title = 'Источники', sub = 'Сайты, Telegram- и YouTube-каналы, из которых конвейер берёт новости';
    if (!view.querySelector('.src-page')) view.innerHTML = head(title, sub, actions) + loading();
    let d;
    try { d = await api('/api/sources' + (srcId ? '?src=' + encodeURIComponent(srcId) : '')); } catch (e) { view.innerHTML = head(title, sub) + failBox(e.message); return; }
    const all = d.sources || [], dirs = d.directions || ['news'], col = d.collector || {}, roles = d.roles || [];
    if (!SRC_DIR || !dirs.includes(SRC_DIR)) SRC_DIR = dirs.includes('news') ? 'news' : dirs[0];
    // направление — «папка»: свои источники и свои выпуски (сейчас одно — «Новости»)
    const list = all.filter(s => s.direction_id === SRC_DIR), items = (d.items || []).filter(it => !it.direction_id || it.direction_id === SRC_DIR);
    const on = list.filter(s => s.enabled).length;
    const one = srcId ? list.find(s => String(s.id) === String(srcId)) : null;
    const yt = col.youtube_transcripts || {}, ap = col.apify || {};
    const ytNote = !list.some(s => s.type === 'youtube' && s.enabled) ? ''
      : yt.status === 'ok' ? `<div class="note" style="margin-bottom:16px">Расшифровки YouTube работают: у новых видео будет текст того, что в них говорят.</div>`
      : yt.status !== 'blocked' ? ''
      : !ap.connected ? `<div class="note warnnote" style="margin-bottom:16px">YouTube не отдаёт расшифровки нашему серверу, поэтому из видео пока берутся только название и описание.
          Подключи Apify — и у видео будет полный текст: <a href="#/settings">Настройки → Ключи сервисов</a>.</div>`
      : ap.budget_hit ? `<div class="note warnnote" style="margin-bottom:16px">Расшифровки через Apify на паузе: в этом месяце потрачено $${Number(ap.used_usd || 0).toFixed(2)} — это твой лимит. Поднять его можно в <a href="#/settings">Настройках</a>.</div>`
      : ap.last_status === 'error' ? `<div class="note warnnote" style="margin-bottom:16px">Apify не сработал: ${esc(ap.last_error || 'ошибка')}. Проверь ключ в <a href="#/settings">Настройках</a>.</div>`
      : `<div class="note" style="margin-bottom:16px">Расшифровки YouTube идут через Apify: сегодня ${ap.today_got || 0} ${plural(ap.today_got || 0, 'видео', 'видео', 'видео')} из ${ap.per_day} в сутки, шортсы не берём.${ap.used_usd != null ? ` В этом месяце на Apify потрачено $${Number(ap.used_usd).toFixed(2)} из $${Number(ap.monthly_limit_usd).toFixed(2)}.` : ''}</div>`;
    // группы: в порядке ролей, потом «без группы»; внутри — сначала включённые
    const groups = roles.map(r => ({ ...r, list: list.filter(s => s.role === r.key) }));
    const loose = list.filter(s => !s.role || !roles.some(r => r.key === s.role));
    const known = loose.filter(s => s.role_guess).length;
    if (loose.length) groups.push({ key: 'none', label: 'Без группы', list: loose, known,
      hint: known ? `Студия узнаёт ${known} из ${loose.length}: нажми «Разложить по группам» или выбери группу в строке источника`
        : 'выбери группу в строке источника — так сценарист точнее понимает, чему верить' });
    const groupCard = g => {
      const n = g.list.length, gon = g.list.filter(s => s.enabled).length;
      const sorted = [...g.list].sort((a, b) => (b.enabled - a.enabled) || a.name.localeCompare(b.name, 'ru'));
      return `<div class="card src-group${g.key === 'signal' ? ' sig' : ''}${g.key === 'none' ? ' loose' : ''}" data-role="${esc(g.key)}">
        <div class="card-h"><div class="grow"><h2>${esc(g.label)} <span class="muted cnt">· включено ${gon} из ${n}</span></h2><div class="muted small">${esc(g.hint)}</div></div>
          ${g.key === 'none' && g.known ? `<button class="btn small primary" data-autogroup>Разложить по группам</button>` : ''}
          <label class="switch" title="${gon ? 'Выключить всю группу' : 'Включить всю группу'}"><input type="checkbox" data-group="${esc(g.key)}" aria-label="Вся группа «${esc(g.label)}»"${gon === n ? ' checked' : ''}${gon && gon < n ? ' data-mixed="1"' : ''}><i></i></label></div>
        <ul class="rows src-list">${sorted.map(s => srcRow(s, dirs, roles)).join('')}</ul></div>`;
    };
    const summary = `<div class="card src-sum" style="margin-bottom:12px"><div class="card-b">
        <div class="sum-row">
          <div class="sum-num"><span class="big-num">${on}</span><span class="muted"> из ${list.length}</span><div class="muted small">источников читает конвейер</div></div>
          <div class="sum-text">Включённые Студия собирает каждые 30 минут, и сценарий пишется только по ним. Выключенные не собираются и в сценарий не попадают. Сбор бесплатный.
            <div class="muted small" style="margin-top:6px">${col.running ? badge('идёт сбор', 'warn live') : `последний сбор: ${col.last_run_at ? when(col.last_run_at) : 'ещё не было'}`}</div></div>
          <div class="actions sum-act">${list.length ? `<button class="btn small" data-all="on">Включить все</button><button class="btn small" data-all="off">Выключить все</button>` : ''}</div>
        </div></div></div>`;
    const shownGroups = groups.filter(g => g.list.length);
    if (SRC_GROUP !== 'all' && !shownGroups.some(g => g.key === SRC_GROUP)) SRC_GROUP = 'all';
    const dirTabs = `<div class="dir-tabs" role="tablist" aria-label="Направления">${dirs.map(x => {
      const n = all.filter(s => s.direction_id === x).length;
      return `<button role="tab" class="dir-tab${x === SRC_DIR ? ' on' : ''}" data-dir="${esc(x)}" aria-selected="${x === SRC_DIR}">${I.rss}<span>${esc(dirLabel(x))}</span><span class="num">${n}</span></button>`;
    }).join('')}</div>`;
    const tools = list.length ? `<div class="src-tabs" role="tablist" aria-label="Группы источников">
        <button role="tab" data-gtab="all">Все группы <span class="num">${on}/${list.length}</span></button>${shownGroups.map(g =>
          `<button role="tab" data-gtab="${esc(g.key)}"${g.key === 'signal' ? ' class="sig"' : ''}>${esc(g.label)} <span class="num">${g.list.filter(s => s.enabled).length}/${g.list.length}</span></button>`).join('')}
      </div>
      <div class="src-tools"><span class="muted small">Показать:</span><div class="seg" role="group" aria-label="Какие источники показать">${
      [['all', 'Все'], ['on', 'Включённые'], ['off', 'Выключенные']]
        .map(([k, t]) => `<button data-filter="${k}">${t}</button>`).join('')}</div><span class="muted small" id="filtnote"></span>
        <span class="muted small src-tip">Цифры — включено / всего. Включённые конвейер читает, выключенные нет.</span></div>` : '';

    view.innerHTML = head(title, sub, actions) + `<div class="src-page">
      ${dirTabs}<div id="addbox"></div>${ytNote}${summary}${tools}
      ${list.length ? `<div class="src-groups">${shownGroups.map(groupCard).join('')}</div>`
        : `<div class="card" style="margin-bottom:16px"><div class="empty"><b>Источников пока нет</b>Нажми «Добавить списком» → «Вставить стартовый набор»: это проверенные источники, уже разложенные по группам. Или добавь по одной ссылке.</div></div>`}
      <div class="card" id="items" style="margin-top:16px"><div class="card-h"><h2>${one ? 'Материалы: ' + esc(one.name) : 'Последние материалы'}</h2>
          <span class="muted small">${one ? '<a href="#/sources">показать все →</a>' : 'нажми на материал, чтобы увидеть, что внутри'}</span></div>
        ${items.length ? `<ul class="rows item-list">${items.map(itemRow).join('')}</ul>` : '<div class="empty">Пока пусто — материалы появятся после первого сбора.</div>'}
      </div></div>`;
    view.querySelectorAll('input[data-mixed]').forEach(cb => { cb.indeterminate = true; });
    applySrcFilter(view);

    $('#collect').addEventListener('click', async ev => {
      const b = ev.currentTarget;
      b.disabled = true;
      try {
        const r = await api('/api/sources/collect', { body: {} });
        toast(r.started ? 'Сбор запущен — обновлю страницу через несколько секунд' : 'Сбор уже идёт');
        refreshSources(view);
      } catch (e) { toast(e.message, true); }
      setTimeout(() => { b.disabled = false; }, 4000);
    });
    $('#addsrc').addEventListener('click', () => openAddSource(view, dirs, roles));
    $('#bulksrc').addEventListener('click', () => openBulk(view, roles, !list.length));
    const itemsEl = $('.item-list', view);
    if (itemsEl) itemsEl.addEventListener('click', ev => { const li = ev.target.closest('li[data-item]'); if (li) openItem(li.dataset.item); });
    if (one) $('#items').scrollIntoView({ block: 'start' });

    const page = $('.src-page', view);
    const moveTo = async (id, role, el) => {
      if (el) el.disabled = true;
      try {
        await api('/api/sources/' + id, { method: 'PATCH', body: { role } });
        toast(role === 'none' ? 'Источник теперь без группы' : `Перенесён в группу «${roleLabel(roles, role)}»`);
        pageSources(view, hashParams());
      } catch (e) { toast(e.message, true); if (el) el.disabled = false; }
    };
    page.addEventListener('click', async ev => {
      const f = ev.target.closest('button[data-filter]');
      if (f) { SRC_FILTER = f.dataset.filter; applySrcFilter(view); return; }
      const gt = ev.target.closest('button[data-gtab]');
      if (gt) { SRC_GROUP = gt.dataset.gtab; applySrcFilter(view); return; }
      const dt = ev.target.closest('button[data-dir]');
      if (dt) { if (dt.dataset.dir !== SRC_DIR) { SRC_DIR = dt.dataset.dir; SRC_GROUP = 'all'; pageSources(view, hashParams()); } return; }
      const ag = ev.target.closest('button[data-autogroup]');
      if (ag) {
        ag.disabled = true;
        try {
          const r = await api('/api/sources/autogroup', { body: {} });
          toast(`Разложено по группам: ${r.moved.length}` + (r.left.length ? `. Без группы осталось ${r.left.length} — для них выбери группу сам` : ''));
          pageSources(view, hashParams());
        } catch (e) { toast(e.message, true); ag.disabled = false; }
        return;
      }
      const acc = ev.target.closest('button[data-accept]');
      if (acc) { const li = acc.closest('li[data-id]'); if (li) moveTo(Number(li.dataset.id), acc.dataset.accept, acc); return; }
      const all = ev.target.closest('button[data-all]');
      if (all) {
        const enable = all.dataset.all === 'on';
        if (!enable && !confirm('Выключить все источники? Конвейер перестанет собирать новости, пока не включишь хотя бы один.')) return;
        all.disabled = true;
        try { const r = await api('/api/sources/enable', { body: { enabled: enable, role: 'all' } }); toast(enable ? `Включено: ${r.changed}` : `Выключено: ${r.changed}`); pageSources(view, hashParams()); if (enable) refreshSources(view); }
        catch (e) { toast(e.message, true); all.disabled = false; }
        return;
      }
      const btn = ev.target.closest('button[data-act]');
      if (!btn) return;
      const li = btn.closest('li[data-id]');
      if (!li) return;
      const id = Number(li.dataset.id), s = list.find(x => x.id === id);
      const act = btn.dataset.act;
      if (act === 'edit') {
        li.classList.add('editing');
        li.innerHTML = srcEditForm(s, dirs, roles);
        $('[data-f=name]', li).focus();
      } else if (act === 'cancel') {
        li.outerHTML = srcRow(s, dirs, roles);
      } else if (act === 'save') {
        const body = { name: $('[data-f=name]', li).value, weight: Number($('[data-f=weight]', li).value), role: $('[data-f=role]', li).value };
        const dsel = $('[data-f=direction_id]', li);
        if (dsel) body.direction_id = dsel.value;
        btn.disabled = true;
        try { await api('/api/sources/' + id, { method: 'PATCH', body }); toast('Сохранено'); pageSources(view, hashParams()); }
        catch (e) { toast(e.message, true); btn.disabled = false; }
      } else if (act === 'del') {
        if (!confirm(`Удалить источник «${s.name}»?\nУже собранные материалы останутся, но в сценарий больше не попадут.`)) return;
        btn.disabled = true;
        try { await api('/api/sources/' + id, { method: 'DELETE' }); toast('Источник удалён'); pageSources(view, hashParams()); }
        catch (e) { toast(e.message, true); btn.disabled = false; }
      }
    });
    page.addEventListener('change', async ev => {
      const cb = ev.target;
      if (cb.dataset.move) {
        moveTo(Number(cb.dataset.move), cb.value, cb);
      } else if (cb.dataset.toggle) {
        cb.disabled = true;
        try {
          await api('/api/sources/' + cb.dataset.toggle, { method: 'PATCH', body: { enabled: cb.checked } });
          toast(cb.checked ? 'Включён — собираю свежее' : 'Выключен: не собирается и в сценарий не попадает');
          pageSources(view, hashParams());
          if (cb.checked) refreshSources(view);
        } catch (e) { cb.checked = !cb.checked; cb.disabled = false; toast(e.message, true); }
      } else if (cb.dataset.group) {
        const enable = cb.dataset.mixed ? true : cb.checked;
        cb.disabled = true;
        try {
          const r = await api('/api/sources/enable', { body: { enabled: enable, role: cb.dataset.group } });
          toast(enable ? `Группа включена (${r.changed})` : `Группа выключена (${r.changed})`);
          pageSources(view, hashParams());
          if (enable) refreshSources(view);
        } catch (e) { cb.checked = !cb.checked; cb.disabled = false; toast(e.message, true); }
      }
    });
  }

  function openBulk(view, roles, fillStarter) {
    const box = $('#addbox');
    box.innerHTML = `<div class="card add-src" style="margin-bottom:16px">
      <div class="card-h"><h2>Добавить списком</h2><button class="close" data-x aria-label="Закрыть">×</button></div>
      <div class="card-b">
        <div class="muted small" style="margin-bottom:8px">По одной ссылке в строке, можно с названием: <span class="mono">ссылка | название</span>.
          Строка <span class="mono"># Фронт</span> задаёт группу для ссылок под ней. Студия проверит каждую ссылку и добавит те, что работают.</div>
        <textarea class="input area" id="bulktext" rows="12" spellcheck="false" placeholder="# Фронт&#10;https://t.me/DeepStateUA | DeepState&#10;https://militarnyi.com/uk/"></textarea>
        <div class="muted small" id="starterinfo" style="margin-top:6px"></div>
        <div class="form-row" style="margin-top:10px">
          <select class="input" id="bulkrole" aria-label="Группа для строк без заголовка">
            <option value="auto" selected>Без заголовка — группу определит Студия</option>
            ${roles.map(r => `<option value="${esc(r.key)}">Без заголовка — ${esc(r.label)}</option>`).join('')}
            <option value="none">Без заголовка — без группы</option></select>
          <button class="btn" id="bulkstarter">Вставить стартовый набор</button>
          <button class="btn primary" id="bulkgo">Проверить и добавить</button>
        </div>
        <div id="bulkres"></div>
      </div></div>`;
    const ta = $('#bulktext');
    ta.focus();
    $('[data-x]', box).addEventListener('click', () => { box.innerHTML = ''; });
    let starter = null;
    const insertStarter = async () => {
      const b = $('#bulkstarter');
      b.disabled = true;
      try {
        starter = starter || await api('/api/sources/starter');
        ta.value = starter.text;
        const c = starter.check || {};
        let t = `Стартовый набор: ${starter.count} источников в ${starter.groups} группах.`;
        if (c.running) t += ' Сервер как раз проверяет их — это пара минут.';
        else if (c.checked_at && c.fresh) t += ` Сервер проверил их ${when(c.checked_at)}: открываются ${c.ok} из ${c.total}.` +
          (c.failed && c.failed.length ? ` Сейчас не открываются: ${c.failed.map(f => f.name).join(', ')}.` : '');
        $('#starterinfo').textContent = t;
      } catch (e) { toast(e.message, true); }
      b.disabled = false;
    };
    if (fillStarter) insertStarter();
    $('#bulkstarter').addEventListener('click', insertStarter);
    $('#bulkgo').addEventListener('click', async ev => {
      const go = ev.currentTarget;
      const todo = parseBulk(ta.value, roles, $('#bulkrole').value);
      if (!todo.length) { toast('Вставь хотя бы одну ссылку', true); return; }
      go.disabled = true; $('#bulkstarter').disabled = true; ta.readOnly = true;
      const res = $('#bulkres');
      res.innerHTML = `<div class="bulk-sum muted small" id="bulksum"></div><ul class="bulk-list">${todo.map((t, i) => `<li id="bk${i}"><span class="bk-st">…</span>
        <span class="bk-name">${esc(t.name || t.link)}</span><span class="faint small bk-grp">${esc(roleLabel(roles, t.role))}</span><span class="bk-msg muted small">ждёт проверки</span></li>`).join('')}</ul>`;
      const tally = { ok: 0, dup: 0, err: 0 };
      const sum = () => { $('#bulksum').textContent = `Добавлено: ${tally.ok} · уже были: ${tally.dup} · не получилось: ${tally.err} · осталось: ${todo.length - tally.ok - tally.dup - tally.err}`; };
      sum();
      let next = 0;
      const worker = async () => {
        while (next < todo.length) {
          const i = next++, t = todo[i], li = $('#bk' + i);
          li.querySelector('.bk-msg').textContent = 'проверяю…';
          try {
            const s = await api('/api/sources', { body: { link: t.link, name: t.name || undefined, role: t.role || 'auto' } });
            li.className = 'ok'; li.querySelector('.bk-st').textContent = '✓';
            li.querySelector('.bk-grp').textContent = s.role_label || 'без группы';
            li.querySelector('.bk-msg').textContent = `добавлен: ${s.type_label}`;
            tally.ok++;
          } catch (e) {
            const dup = /уже есть/.test(e.message);
            li.className = dup ? 'dup' : 'err'; li.querySelector('.bk-st').textContent = dup ? '=' : '✗';
            li.querySelector('.bk-msg').textContent = e.message;
            dup ? tally.dup++ : tally.err++;
          }
          sum();
        }
      };
      await Promise.all([worker(), worker(), worker()]);
      go.disabled = false; $('#bulkstarter').disabled = false; ta.readOnly = false;
      toast(`Готово: добавлено ${tally.ok}, уже были ${tally.dup}, не получилось ${tally.err}`, tally.err > 0 && !tally.ok);
      res.insertAdjacentHTML('beforeend', `<div class="form-row" style="margin-top:12px"><button class="btn primary" id="bulkdone">Показать список источников</button></div>`);
      $('#bulkdone').addEventListener('click', () => { box.innerHTML = ''; pageSources(view, hashParams()); refreshSources(view); });
    });
  }

  function openAddSource(view, dirs, roles) {
    const box = $('#addbox');
    box.innerHTML = `<div class="card add-src" style="margin-bottom:16px">
      <div class="card-h"><h2>Новый источник</h2><button class="close" data-x aria-label="Закрыть">×</button></div>
      <div class="card-b">
        <form class="form-row" id="chkform"><input class="input" id="srclink" style="flex:1;min-width:220px" autocomplete="off" inputmode="url"
          placeholder="Ссылка на сайт, t.me/канал или youtube.com/@канал"><button class="btn primary" type="submit">Проверить</button></form>
        <div class="muted small" style="margin-top:8px">Например: <span class="mono">meduza.io</span> · <span class="mono">t.me/durov</span> · <span class="mono">youtube.com/@varlamov</span>.
          Студия сама найдёт ленту и покажет, что в ней последнее. X (Twitter) пока не подключаем — он платный.</div>
        <div id="chkres"></div>
      </div></div>`;
    $('#srclink').focus();
    $('[data-x]', box).addEventListener('click', () => { box.innerHTML = ''; });
    $('#chkform').addEventListener('submit', async ev => {
      ev.preventDefault();
      const link = $('#srclink').value.trim();
      if (!link) return;
      const res = $('#chkres'), sb = ev.target.querySelector('button');
      sb.disabled = true;
      res.innerHTML = '<div class="muted" style="margin-top:14px">Проверяю ссылку… (до 20 секунд)</div>';
      let r;
      try { r = await api('/api/sources/check', { body: { link } }); }
      catch (e) { res.innerHTML = `<div class="errbox" style="margin-top:14px"><b>Не получилось.</b> ${esc(e.message)}</div>`; sb.disabled = false; return; }
      sb.disabled = false;
      res.innerHTML = `<div class="chk">
        <div class="chk-h"><div class="src-ic ${esc(r.type)}">${SRC_IC[r.type] || I.rss}</div>
          <div class="grow"><b>${esc(r.feed_title || r.name)}</b><div class="muted small">${esc(r.type_label)} · ${r.count} ${plural(r.count, 'материал', 'материала', 'материалов')} в ленте${r.newest_at ? ' · последний ' + when(r.newest_at) : ''}</div></div>
          ${badge('лента найдена', 'ok')}</div>
        <div class="muted small" style="margin-top:10px">Что будем брать: <b>${esc(r.takes || '—')}</b></div>
        <div class="muted small" style="margin-top:4px">${r.role_guess ? `Группа: <b>«${esc(r.role_guess_label)}»</b> — ${esc(r.role_guess_why || '')}. Можно поменять ниже.`
          : 'Студия не знает этот источник: выбери ему группу ниже — так сценарист поймёт, чему верить.'}</div>
        ${r.warning ? `<div class="note warnnote">${esc(r.warning)}</div>` : ''}
        ${r.items.length ? `<ul class="chk-items">${r.items.map(i => `<li><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a><span class="faint">${i.published_at ? when(i.published_at) : ''}</span></li>`).join('')}</ul>` : ''}
        <div class="form-row" style="margin-top:14px">
          <input class="input" id="nname" value="${esc(r.name)}" maxlength="120" style="flex:1;min-width:200px" placeholder="Название" aria-label="Название">
          <select class="input" id="nrole" aria-label="Группа">${roleOptions(roles, r.role_guess || 'none')}</select>
          <select class="input" id="nweight" aria-label="Важность">${WEIGHTS.map(([v, t]) => `<option value="${v}">Важность: ${t}</option>`).join('')}</select>
          ${dirs.length > 1 ? `<select class="input" id="ndir" aria-label="Направление">${dirs.map(x => `<option>${esc(x)}</option>`).join('')}</select>` : ''}
          <button class="btn primary" id="nsave">Сохранить и включить</button>
        </div></div>`;
      $('#nsave').addEventListener('click', async ev2 => {
        const b = ev2.currentTarget;
        b.disabled = true;
        const body = { link, name: $('#nname').value, weight: Number($('#nweight').value), role: $('#nrole').value || 'none' };
        if ($('#ndir')) body.direction_id = $('#ndir').value;
        try {
          const s = await api('/api/sources', { body });
          toast('Добавлен «' + s.name + '» — собираю первые материалы');
          box.innerHTML = '';
          pageSources(view, hashParams());
          refreshSources(view);
        } catch (e) { toast(e.message, true); b.disabled = false; }
      });
    });
  }

  // ---------- Настройки ----------
  async function pageSettings(view) {
    view.innerHTML = head('Настройки', 'Доступы, версия и безопасность') + loading();
    let d;
    try { d = await api('/api/settings'); } catch (e) { view.lastElementChild.outerHTML = failBox(e.message); return; }
    const v = d.version || {};
    view.innerHTML = head('Настройки', 'Доступы, версия и безопасность') + `
      <div class="grid two">
        <div class="grid">
          <div class="card"><div class="card-h"><h2>Доступ Claude (MCP)</h2>${d.mcp_enabled ? badge('включён', 'ok') : badge('выключен', 'warn')}</div><div class="card-b">
            <p style="margin-top:0">Через этот вход Claude сам смотрит журнал, ошибки, выпуски и расходы. Секреты в ответах скрыты, каждое действие пишется в журнал действий.</p>
            <ol class="steps"><li>Адрес с токеном показал установщик на сервере. Показать ещё раз (в окне сервера): <span class="mono">cd /opt/n8n &amp;&amp; docker compose exec -T studio python -m app.cli mcp-url</span></li>
              <li>В Claude: Плагины → Добавить → Добавить пользовательский коннектор. Название — «Студия», URL — этот адрес, аутентификация — «Без входа».</li>
              <li>Токен никому не пересылай и в чат не вставляй.</li></ol></div></div>
          <div class="card" id="svc-apify"></div>
          <div class="card"><div class="card-h"><h2>Сменить пароль</h2></div><div class="card-b">
            <div class="form-row" style="margin-bottom:8px"><input class="input" type="password" id="pw0" placeholder="Текущий пароль" autocomplete="current-password" style="flex:1"></div>
            <div class="form-row"><input class="input" type="password" id="pw1" placeholder="Новый, от 10 символов" autocomplete="new-password" style="flex:1"><button class="btn primary" id="pwsave">Сменить</button></div>
          </div></div>
        </div>
        <div class="grid">
          <div class="card"><div class="card-h"><h2>Версия</h2></div><div class="card-b"><dl class="kv">
            <dt>Код</dt><dd class="mono">${esc(v.commit || 'dev')}</dd><dt>Обновлено</dt><dd>${esc(v.at || '—')}</dd>
            <dt>Ключ n8n API</dt><dd>${d.n8n_key ? badge('есть', 'ok') : badge('нет — журнал недоступен', 'err')}</dd></dl>
            <p class="muted" style="margin-bottom:0">Студия обновляется сама: сервер раз в 2 минуты забирает новую версию из GitHub.</p>
            <div class="actions" style="margin-top:12px">${d.links.n8n ? `<a class="btn small" href="${esc(d.links.n8n)}" target="_blank" rel="noopener">${I.ext}n8n</a>` : ''}
              ${d.links.settings_sheet ? `<a class="btn small" href="${esc(d.links.settings_sheet)}" target="_blank" rel="noopener">${I.ext}Таблица настроек</a>` : ''}</div></div></div>
          <div class="card"><div class="card-h"><h2>Пользователи</h2></div><div class="card-b flush"><ul class="rows">${(d.users || []).map(u => `<li><div class="grow"><div class="title">${esc(u.name || u.login)}</div>
            <div class="meta"><span>${esc(u.login)}</span><span>${esc(u.role)}</span><span>вход ${when(u.last_login)}</span></div></div></li>`).join('')}</ul></div></div>
          <div class="card"><div class="card-h"><h2>Последние действия</h2></div><div class="card-b flush"><ul class="rows">${(d.audit || []).map(a => `<li><div class="grow"><div class="title">${esc(a.action)}</div>
            <div class="meta"><span>${esc(a.actor || '—')}</span><span>${when(a.at)}</span></div></div></li>`).join('') || '<li class="muted">пусто</li>'}</ul></div></div>
        </div>
      </div>`;
    drawApify($('#svc-apify'), (d.services || {}).apify || {}, d.role === 'owner');
    $('#pwsave').addEventListener('click', async () => {
      try { await api('/api/password', { body: { current: $('#pw0').value, new: $('#pw1').value } }); toast('Пароль изменён'); $('#pw0').value = $('#pw1').value = ''; }
      catch (e) { toast(e.message, true); }
    });
  }

  // Apify — посредник для расшифровок YouTube. Ключ вводит сам человек; Студия показывает только последние 4 знака.
  function drawApify(box, a, owner, acct) {
    const st = a.state || {};
    const usd = v => v == null ? '—' : '$' + Number(v).toFixed(2);
    const used = acct ? acct.used_usd : st.used_usd;
    box.innerHTML = `<div class="card-h"><h2>Ключи сервисов: Apify</h2>${a.set ? badge('подключён', 'ok') : badge('не подключён', 'warn')}</div><div class="card-b">
      <p style="margin-top:0">Apify достаёт расшифровки YouTube-видео: наш сервер YouTube не пускает. Это примерно $5 за 1000 видео.
        Бесплатно Apify даёт $5 в месяц, Студия берёт до ${st.per_day ?? 20} видео в сутки, без шортсов.</p>
      ${a.set ? `<dl class="kv">
          <dt>Ключ</dt><dd class="mono">…${esc(a.last4 || '')}</dd>
          ${acct ? `<dt>Аккаунт</dt><dd>${esc(acct.username || '—')}${acct.plan ? ' · тариф ' + esc(acct.plan) : ''}</dd>` : ''}
          <dt>Потрачено в этом месяце</dt><dd>${usd(used)}${acct && acct.max_usd != null ? ` <span class="muted">(лимит аккаунта Apify ${usd(acct.max_usd)})</span>` : ''}</dd>
          <dt>Сегодня</dt><dd>${st.today_got || 0} ${plural(st.today_got || 0, 'расшифровка', 'расшифровки', 'расшифровок')}${st.last_run_at ? ` · последний запуск ${when(st.last_run_at)}` : ' · ещё не запускался'}</dd>
          ${st.last_error ? `<dt>Ошибка</dt><dd class="errtxt">${esc(st.last_error)}</dd>` : ''}</dl>
        <div class="form-row" style="margin-top:12px"><label for="aplim">Тратить не больше, $ в месяц</label>
          <input class="input" id="aplim" type="number" min="0" max="500" step="0.5" value="${esc(st.monthly_limit_usd ?? 4)}" style="width:90px"${owner ? '' : ' disabled'}>
          <label for="apday">видео в сутки</label><input class="input" id="apday" type="number" min="0" max="300" step="1" value="${esc(st.per_day ?? 20)}" style="width:80px"${owner ? '' : ' disabled'}>
          ${owner ? '<button class="btn small" id="apsave">Сохранить</button>' : ''}</div>
        <div class="actions" style="margin-top:12px"><button class="btn small" id="apcheck">Проверить</button>${owner ? '<button class="btn small" id="apoff">Отключить</button>' : ''}</div>`
      : owner ? `<ol class="steps">
          <li>Зарегистрируйся на <a href="https://apify.com" target="_blank" rel="noopener">apify.com</a> — это бесплатно.</li>
          <li>В Apify: Settings → API &amp; Integrations → скопируй Personal API token.</li>
          <li>Вставь его сюда и нажми «Подключить». Ключ хранится на нашем сервере в зашифрованном виде. Никому его не пересылай и в чат не вставляй.</li></ol>
        <form class="form-row" id="apform" autocomplete="off"><input class="input" type="password" id="aptoken" placeholder="Ключ Apify (apify_api_…)" autocomplete="off" spellcheck="false" style="flex:1;min-width:220px">
          <button class="btn primary" type="submit">Подключить</button></form>`
      : '<p class="muted" style="margin-bottom:0">Подключить ключ может только владелец кабинета.</p>'}</div>`;
    const form = $('#apform', box);
    if (form) form.addEventListener('submit', async ev => {
      ev.preventDefault();
      const inp = $('#aptoken', box), btn = form.querySelector('button');
      const token = inp.value.trim();
      if (!token) { toast('Вставь ключ', true); return; }
      btn.disabled = true; btn.textContent = 'Проверяю…';
      try {
        const r = await api('/api/services/apify', { body: { token } });
        inp.value = '';
        toast('Apify подключён' + (r.account && r.account.username ? ': ' + r.account.username : '') + '. Расшифровки начнутся при ближайшем сборе');
        drawApify(box, r, owner, r.account);
      } catch (e) { toast(e.message, true); btn.disabled = false; btn.textContent = 'Подключить'; }
    });
    const chk = $('#apcheck', box);
    if (chk) chk.addEventListener('click', async () => {
      chk.disabled = true;
      try { const r = await api('/api/services/apify/check', { body: {} }); drawApify(box, r, owner, r.account); toast('Ключ работает'); }
      catch (e) { toast(e.message, true); chk.disabled = false; }
    });
    const save = $('#apsave', box);
    if (save) save.addEventListener('click', async () => {
      save.disabled = true;
      try {
        const r = await api('/api/services/apify/settings', { method: 'PATCH', body: { monthly_limit_usd: Number($('#aplim', box).value), per_day: Number($('#apday', box).value) } });
        drawApify(box, r, owner, acct); toast('Сохранено');
      } catch (e) { toast(e.message, true); save.disabled = false; }
    });
    const off = $('#apoff', box);
    if (off) off.addEventListener('click', async () => {
      if (!confirm('Отключить Apify? Расшифровки YouTube перестанут приходить. Ключ удалится с нашего сервера.')) return;
      off.disabled = true;
      try { const r = await api('/api/services/apify', { method: 'DELETE' }); drawApify(box, r, owner); toast('Apify отключён'); }
      catch (e) { toast(e.message, true); off.disabled = false; }
    });
  }

  // ---------- маршруты ----------
  const PAGES = { '/': pageOverview, '/episodes': pageEpisodes, '/prompter': pagePrompter, '/prompter/view': pagePrompterView, '/prompter/edit': pagePrompterEdit, '/remote': pageRemote, '/logs': pageLogs, '/costs': pageCosts, '/sources': pageSources, '/directions': pageDirections, '/directions/edit': pageDirectionEdit, '/connections': pageConnections, '/settings': pageSettings };

  function route() {
    if (!state.user) return;
    closeDrawer();
    clearInterval(state.timer);
    const [path, qs] = (location.hash.replace(/^#/, '') || '/').split('?');
    const page = PAGES[path] || pageOverview;
    markNav();
    // новый контейнер на каждый переход: страница, которая ещё грузится, допишет в старый, а не поверх новой
    const old = $('#view');
    const view = old.cloneNode(false);
    old.replaceWith(view);
    window.scrollTo(0, 0);
    page(view, new URLSearchParams(qs || ''));
    if (page === pageOverview) {
      state.timer = setInterval(() => { if (!document.hidden && !document.querySelector('.drawer')) pageOverview(view); }, 60000);
    }
  }

  async function boot() {
    try {
      const me = await api('/api/me', { noAuthRedirect: true });
      state.user = me.user;
      state.version = me.version;
    } catch (e) { showLogin(); return; }
    shell();
    route();
  }

  window.addEventListener('hashchange', route);
  if ('serviceWorker' in navigator) navigator.serviceWorker.register('/sw.js').catch(() => {});
  boot();
})();
