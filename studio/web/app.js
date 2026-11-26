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
    play: '<svg viewBox="0 0 16 16" fill="#fff"><path d="M3 1.8v12.4c0 .6.7 1 1.2.7l10-6.2c.5-.3.5-1.1 0-1.4l-10-6.2C3.7.8 3 1.2 3 1.8z"/></svg>',
    home: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7.5" height="9" rx="1.6"/><rect x="13.5" y="3" width="7.5" height="5.5" rx="1.6"/><rect x="13.5" y="11.5" width="7.5" height="9.5" rx="1.6"/><rect x="3" y="15" width="7.5" height="6" rx="1.6"/></svg>',
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
    ['#/', 'Обзор', I.home], ['#/episodes', 'Выпуски', I.film], ['#/logs', 'Журнал', I.log],
    ['#/costs', 'Расходы', I.coin], ['#/sources', 'Источники', I.rss], ['#/settings', 'Настройки', I.gear],
  ];
  const EP_TONE = {
    preview_ready: 'ok', published: 'ok', used: 'ok', partial: 'warn', recording: 'warn live', rendering: 'warn live',
    publishing: 'warn live', redo: 'warn live', script_ready: 'info', inserts_ready: 'info', error: 'err', superseded: '', cancelled: '',
  };
  const INS_KIND = { screenshot: 'скрин', source_media: 'медиа из источника', card: 'карточка', quote: 'цитата', number: 'цифра', map: 'карта',
    stock: 'сток', wikimedia: 'Wikimedia', diagram: 'схема', ai_image: 'ИИ-картинка' };
  const RUN_TONE = { success: ['ok', 'Успешно'], error: ['err', 'Ошибка'], crashed: ['err', 'Сбой'], running: ['warn live', 'Идёт'],
    waiting: ['warn', 'Ждёт'], new: ['warn', 'В очереди'], canceled: ['', 'Отменён'] };

  const state = { user: null, version: null, errors24: 0, timer: null };

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

  // ---------- вход ----------
  function showLogin() {
    clearInterval(state.timer);
    $('#root').innerHTML = `
      <div class="login"><form class="card" id="lf" autocomplete="on">
        <div class="logo" style="padding:0"><div class="mark">${I.play}</div><div><b>Студия</b><span>Без сказок</span></div></div>
        <h1>Вход</h1><p>Пульт конвейера: выпуски, журнал, расходы.</p>
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
        boot();
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
          <nav class="nav">${nav}</nav>
          <div class="side-foot">
            <div class="who"><span>${esc(state.user.name || state.user.login)}</span><button class="linkbtn" id="logout">Выйти</button></div>
            <div class="faint">версия ${esc(v.commit || 'dev')}</div>
          </div>
        </aside>
        <div class="main">
          <header class="top"><div class="logo"><div class="mark">${I.play}</div><div><b>Студия</b></div></div>
            <a class="btn small" href="#/sources">${I.rss}</a></header>
          <div class="wrap" id="view"></div>
        </div>
      </div>
      <nav class="tabbar">${tabs}</nav>`;
    $('#logout').addEventListener('click', async () => { await api('/api/logout', { method: 'POST' }).catch(() => {}); showLogin(); });
  }

  function markNav() {
    const h = '#' + (location.hash.replace(/^#/, '').split('?')[0] || '/');
    document.querySelectorAll('[data-nav]').forEach(a => a.classList.toggle('on', a.dataset.nav === h));
    document.querySelectorAll('[data-errcount]').forEach(el => { el.textContent = state.errors24; el.classList.toggle('hidden', !state.errors24); });
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

  // ---------- Обзор ----------
  async function pageOverview(view) {
    view.innerHTML = head('Обзор', 'Что происходит с конвейером прямо сейчас', reportBtn) + loading();
    let d;
    try { d = await api('/api/overview'); } catch (e) { view.innerHTML = head('Обзор', '', reportBtn) + failBox(e.message); return; }
    state.errors24 = (d.errors_24h || []).length;
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
    const errs = d.errors_24h || [];
    const last = errs[0];
    const s = d.server || {};
    const ok = (v, yes, no, warn) => v === true ? badge(yes, 'ok') : v === false ? badge(no, 'err') : badge(warn || 'нет данных', 'warn');
    view.innerHTML = head('Обзор', 'Что происходит с конвейером прямо сейчас', reportBtn) + `
      <div class="grid kpis">
        ${balance}
        <div class="kpi card"><div class="label">Расходы за 30 дней</div><div class="value num">${money(c.d30)}</div>
          <div class="sub">сегодня ${money(c.today)} · за 7 дней ${money(c.d7)}</div></div>
        <div class="kpi card"><div class="label">Ждут записи</div><div class="value num">${d.waiting_scripts ?? '—'}</div>
          <div class="sub">${d.waiting_scripts ? 'сценарии готовы, вставки собраны' : 'готовых сценариев нет'}</div></div>
        <div class="kpi card ${errs.length ? 'bad' : 'good'}"><div class="label">Ошибки за сутки</div><div class="value num">${d.errors_note ? '—' : errs.length}</div>
          <div class="sub">${d.errors_note ? esc(d.errors_note) : last ? esc(last.workflow) + ' · ' + when(last.started_at) : 'всё спокойно'}</div></div>
      </div>
      <div class="grid two">
        <div class="card"><div class="card-h"><h2>Последние выпуски</h2><a href="#/episodes">Все</a></div>
          <div class="card-b flush">${epRows(d.episodes || [])}</div></div>
        <div class="grid">
          <div class="card"><div class="card-h"><h2>Сервер</h2></div><div class="card-b"><dl class="kv">
            <dt>Монтаж</dt><dd>${s.montage_busy ? badge('занят', 'warn live') : badge('свободен', 'ok')}</dd>
            <dt>Диск</dt><dd class="num">${s.disk_free_gb != null ? s.disk_free_gb + ' ГБ свободно из ' + s.disk_total_gb : '—'}</dd>
            <dt>n8n</dt><dd>${ok(s.n8n, 'на связи', 'нет связи', 'нет ключа API')}</dd>
            <dt>Сервер монтажа</dt><dd>${ok(s.worker, 'на связи', 'нет связи')}</dd>
            <dt>Ключ Google</dt><dd>${ok(s.google_key, 'есть', 'нет')}</dd>
            <dt>Версия Студии</dt><dd class="mono">${esc((d.version || {}).commit || 'dev')}</dd>
          </dl></div></div>
          <div class="card"><div class="card-h"><h2>Ошибки</h2><a href="#/logs?view=errors">Журнал</a></div>
            <div class="card-b flush">${errs.length ? `<ul class="rows">${errs.slice(0, 4).map(runRow).join('')}</ul>`
              : `<div class="empty"><b>Ошибок нет</b>за последние 24 часа</div>`}</div></div>
        </div>
      </div>`;
    bindRuns(view);
    bindEps(view);
  }

  // ---------- Выпуски ----------
  function epTags(e) {
    return `${badge(e.status_label || e.status, EP_TONE[e.status] || '')}${badge(e.kind === 'script' ? 'Сценарий' : 'Запись', 'plain')}${e.direction ? badge(e.direction, 'plain') : ''}`;
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

  async function pageEpisodes(view, params) {
    const kind = params.get('kind') || '';
    const seg = `<div class="seg">${[['', 'Все'], ['recording', 'Записи'], ['script', 'Сценарии']].map(([k, t]) =>
      `<button data-kind="${k}" class="${k === kind ? 'on' : ''}">${t}</button>`).join('')}</div>`;
    view.innerHTML = head('Выпуски', 'Сценарии, записи и готовые видео', seg) + loading();
    view.querySelectorAll('[data-kind]').forEach(b => b.addEventListener('click', () => { location.hash = '#/episodes' + (b.dataset.kind ? '?kind=' + b.dataset.kind : ''); }));
    let d;
    try { d = await api('/api/episodes?limit=60' + (kind ? '&kind=' + kind : '')); } catch (e) { view.lastElementChild.outerHTML = failBox(e.message); return; }
    const list = d.episodes || [];
    const cards = list.map(e => `<div class="card ep"><div class="tags">${epTags(e)}</div><h3>${esc(e.title)}</h3>
      <div class="meta">${epMeta(e)}</div>
      <div class="foot">
        ${e.preview_url ? `<a class="btn small primary" href="${esc(e.preview_url)}" target="_blank" rel="noopener">Смотреть</a>` : ''}
        ${e.youtube_url ? `<a class="btn small" href="${esc(e.youtube_url)}" target="_blank" rel="noopener">YouTube</a>` : ''}
        <button class="btn small" data-ep="${esc(e.id)}">Подробнее</button></div></div>`).join('');
    view.lastElementChild.outerHTML = list.length ? `<div class="grid eps">${cards}</div>`
      : `<div class="card"><div class="empty"><b>Пусто</b>Здесь появятся сценарии и выпуски</div></div>`;
    bindEps(view);
  }

  async function openEpisode(id) {
    const d0 = drawer('Выпуск', esc(id), loading());
    let e;
    try { e = await api('/api/episodes/' + encodeURIComponent(id)); } catch (err) { d0.querySelector('.d-b').innerHTML = failBox(err.message); return; }
    const sc = e.script;
    const fails = (e.inserts || []).filter(i => i.status !== 'ok');
    const body = `
      <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:14px">${epTags(e)}</div>
      <div class="actions" style="margin-bottom:6px">
        ${e.preview_url ? `<a class="btn primary" href="${esc(e.preview_url)}" target="_blank" rel="noopener">Смотреть превью</a>` : ''}
        ${e.youtube_url ? `<a class="btn" href="${esc(e.youtube_url)}" target="_blank" rel="noopener">YouTube</a>` : ''}
      </div>
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
      <div class="section-t">Данные монтажа</div><pre class="json">${esc(JSON.stringify(e.meta || {}, null, 2))}</pre>`;
    d0.querySelector('.d-b').innerHTML = body;
  }

  // ---------- Журнал ----------
  function runRow(r) {
    const [tone, label] = RUN_TONE[r.status] || ['', r.status];
    const err = r.error ? `${r.error.node ? r.error.node + ': ' : ''}${r.error.message || ''}` : '';
    return `<li class="click" data-run="${esc(r.id)}"><span class="dot ${tone.split(' ')[0]}" title="${esc(label)}"></span>
      <div class="grow"><div class="title">${esc(r.workflow)}</div><div class="meta"><span>${when(r.started_at)}</span><span>${dur(r.duration_s)}</span><span class="faint">№${esc(r.id)}</span></div>
      ${err ? `<div class="errtxt">${esc(err)}</div>` : ''}</div><div class="side-val">${badge(label, tone)}</div></li>`;
  }
  function bindRuns(root) { root.querySelectorAll('[data-run]').forEach(el => el.addEventListener('click', () => openRun(el.dataset.run))); }

  async function pageLogs(view, params) {
    const mode = ['important', 'all', 'errors'].includes(params.get('view')) ? params.get('view') : 'important';
    const seg = `<div class="seg">${[['important', 'Важные'], ['all', 'Все'], ['errors', 'Ошибки']].map(([k, t]) =>
      `<button data-v="${k}" class="${k === mode ? 'on' : ''}">${t}</button>`).join('')}</div>`;
    view.innerHTML = head('Журнал', 'Каждый запуск конвейера. Нажми на строку — увидишь, где и что сломалось.',
      `${seg}<button class="btn" id="rf">${I.refresh}Обновить</button>${reportBtn}`) +
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
      const html = (d.runs || []).map(runRow).join('');
      if (append) box.querySelector('ul').insertAdjacentHTML('beforeend', html);
      else box.innerHTML = html ? `<ul class="rows">${html}</ul>` : `<div class="empty"><b>${mode === 'errors' ? 'Ошибок нет' : 'Запусков нет'}</b></div>`;
      hidden += d.hidden_quiet || 0;
      $('#quiet').textContent = mode === 'important' && hidden ? `Скрыто пустых проверок по расписанию: ${hidden} (монтаж смотрит папку каждые 2 минуты). Показать их — вкладка «Все».` : '';
      bindRuns(box);
      $('#more').classList.toggle('hidden', !cursor);
    }
    $('#more').addEventListener('click', () => load(true));
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
  // Стартовый набор: строка «# Группа» задаёт группу для ссылок под ней. Сайты — главной страницей: ленту Студия найдёт сама.
  const STARTER = `# Первоисточники
https://t.me/kpszsu | Повітряні сили ЗСУ
https://t.me/GeneralStaffZSU | Генштаб ЗСУ
https://t.me/V_Zelenskiy_official | Зеленський
https://www.whitehouse.gov/ | Белый дом
http://kremlin.ru/ | Кремль

# Украинские СМИ
https://t.me/suspilnenews | Суспільне Новини
https://www.pravda.com.ua/ | Українська правда
https://t.me/uniannet | УНІАН
https://www.rbc.ua/ | РБК-Україна
https://interfax.com.ua/ | Інтерфакс-Україна
https://www.ukrinform.ua/ | Укрінформ

# Фронт
https://t.me/DeepStateUA | DeepState
https://understandingwar.org/ | ISW
https://militarnyi.com/uk/ | Мілітарний
https://defence-ua.com/ | Defense Express

# Россия изнутри
https://meduza.io/ | Медуза
https://theins.ru/ | The Insider
https://t.me/agentstvonews | Агентство
https://verstka.media/ | Вёрстка
https://zona.media/ | Медиазона
https://t.me/astrapress | ASTRA
https://www.svoboda.org/ | Радио Свобода
https://www.moscowtimes.ru/ | The Moscow Times

# Мир и США
https://kyivindependent.com/ | Kyiv Independent
https://www.axios.com/ | Axios
https://www.politico.eu/ | Politico Europe

# Мнения и разборы
https://www.youtube.com/channel/UCgpSieplNxXxLXYAzJLLpng | Майкл Наки
https://www.youtube.com/channel/UCTFygGgLg2OPIVsBZ7xeCjg | Портников. Аргументы
https://t.me/glebpiano | Глазами Пьяных. Здравый смысл

# Только сигнал
https://t.me/truexanewsua | Труха Україна
https://t.me/mod_russia | Минобороны РФ
https://t.me/rybar | Рыбарь
https://t.me/breakingmash | Mash`;

  function hostOf(s) {
    if (s.type === 'telegram') return '@' + s.url;
    if (s.type === 'youtube' && !s.site_url) return 'youtube.com';
    try { return new URL(s.site_url || s.url).host.replace(/^www\./, ''); } catch (e) { return s.url; }
  }
  const roleOptions = (roles, cur, empty = 'Без группы') => `<option value="">${esc(empty)}</option>` +
    roles.map(r => `<option value="${esc(r.key)}"${r.key === cur ? ' selected' : ''}>${esc(r.label)}</option>`).join('');
  function roleFromHeader(text, roles) {
    const t = text.toLowerCase();
    const hit = roles.find(r => t.includes(r.label.toLowerCase()) || t.includes(r.key));
    if (hit) return hit.key;
    const map = [['первоисточ', 'official'], ['официал', 'official'], ['украин', 'ua_media'], ['фронт', 'front'], ['росси', 'ru_inside'],
      ['мир', 'world'], ['сша', 'world'], ['мнени', 'opinion'], ['разбор', 'opinion'], ['сигнал', 'signal'], ['пропаганд', 'signal']];
    const m = map.find(([k]) => t.includes(k));
    return m ? m[1] : '';
  }
  function parseBulk(text, roles, defRole) {
    const out = [];
    let role = defRole || '';
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

  function srcRow(s, dirs) {
    const st = s.enabled && (s.state === 'ok' || s.state === 'warn')
      ? `<span>${s.d1} за сутки · ${s.d7} за неделю${s.last_item_at ? ' · последний ' + when(s.last_item_at) : ''}</span>` : '';
    return `<li data-id="${s.id}" class="src${s.enabled ? '' : ' off'}">
      <div class="src-ic ${esc(s.type)}">${SRC_IC[s.type] || I.rss}</div>
      <div class="grow">
        <div class="title">${esc(s.name)}</div>
        <div class="meta"><a href="${esc(s.site_url || s.url)}" target="_blank" rel="noopener">${esc(hostOf(s))}</a><span>${esc(s.type_label)}</span>
          <span>${esc(s.weight_label)}</span>${dirs.length > 1 ? `<span>${esc(s.direction_id)}</span>` : ''}</div>
        <div class="meta"><span class="st ${SRC_TONE[s.state] || ''}">${esc(s.state_text)}</span>${st}</div>
        <div class="meta"><span>Берём: ${esc(s.takes || '—')}</span>${s.total ? `<a href="#/sources?src=${s.id}">материалы (${s.total}) →</a>` : ''}</div>
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
        <select class="input" data-f="role" aria-label="Группа">${roleOptions(roles, s.role || '')}</select>
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
          h = h.replace(/^\[(\d\d):(\d\d)\]/, (m0, mm, ss) => {
            const link = ytLink(it.url, Number(mm) * 60 + Number(ss));
            return link ? `<a class="ts" href="${link}" target="_blank" rel="noopener">${mm}:${ss}</a>` : m0;
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

  async function pageSources(view, params) {
    const srcId = params && params.get ? params.get('src') : null;
    const actions = `<button class="btn" id="collect">${I.refresh}Собрать сейчас</button><button class="btn" id="bulksrc">${I.plus}Добавить списком</button>` +
      `<button class="btn primary" id="addsrc">${I.plus}Добавить источник</button>`;
    const title = 'Источники', sub = 'Сайты, Telegram- и YouTube-каналы, из которых конвейер берёт новости';
    if (!view.querySelector('.src-page')) view.innerHTML = head(title, sub, actions) + loading();
    let d;
    try { d = await api('/api/sources' + (srcId ? '?src=' + encodeURIComponent(srcId) : '')); } catch (e) { view.innerHTML = head(title, sub) + failBox(e.message); return; }
    const list = d.sources || [], dirs = d.directions || ['news'], col = d.collector || {}, items = d.items || [], roles = d.roles || [];
    const on = list.filter(s => s.enabled).length;
    const one = srcId ? list.find(s => String(s.id) === String(srcId)) : null;
    const yt = col.youtube_transcripts || {};
    const ytNote = list.some(s => s.type === 'youtube' && s.enabled)
      ? (yt.status === 'blocked' ? `<div class="note warnnote" style="margin-bottom:16px">YouTube не отдаёт расшифровки нашему серверу, поэтому из видео пока берутся название и описание. Расшифровку и суть видео подключим через Apify — это следующий шаг.</div>`
        : yt.status === 'ok' ? `<div class="note" style="margin-bottom:16px">Расшифровки YouTube работают: у новых видео будет текст того, что в них говорят.</div>` : '')
      : '';
    // группы: в порядке ролей, потом «без группы»; внутри — сначала включённые
    const groups = roles.map(r => ({ ...r, list: list.filter(s => s.role === r.key) }));
    const loose = list.filter(s => !s.role || !roles.some(r => r.key === s.role));
    if (loose.length) groups.push({ key: 'none', label: 'Без группы', hint: 'отнеси источник в группу через карандаш — так сценарист точнее понимает, чему верить', list: loose });
    const groupCard = g => {
      const n = g.list.length, gon = g.list.filter(s => s.enabled).length;
      const sorted = [...g.list].sort((a, b) => (b.enabled - a.enabled) || a.name.localeCompare(b.name, 'ru'));
      return `<div class="card src-group${g.key === 'signal' ? ' sig' : ''}" data-role="${esc(g.key)}">
        <div class="card-h"><div class="grow"><h2>${esc(g.label)} <span class="muted cnt">· включено ${gon} из ${n}</span></h2><div class="muted small">${esc(g.hint)}</div></div>
          <label class="switch" title="${gon ? 'Выключить всю группу' : 'Включить всю группу'}"><input type="checkbox" data-group="${esc(g.key)}" aria-label="Вся группа"${gon === n ? ' checked' : ''}${gon && gon < n ? ' data-mixed="1"' : ''}><i></i></label></div>
        <ul class="rows src-list">${sorted.map(s => srcRow(s, dirs)).join('')}</ul></div>`;
    };
    const summary = `<div class="card src-sum" style="margin-bottom:16px"><div class="card-b">
        <div class="sum-row">
          <div class="sum-num"><span class="big-num">${on}</span><span class="muted"> из ${list.length}</span><div class="muted small">источников читает конвейер</div></div>
          <div class="sum-text">Включённые Студия собирает каждые 30 минут, и сценарий пишется только по ним. Выключенные не собираются и в сценарий не попадают. Сбор бесплатный.
            <div class="muted small" style="margin-top:6px">${col.running ? badge('идёт сбор', 'warn live') : `последний сбор: ${col.last_run_at ? when(col.last_run_at) : 'ещё не было'}`}</div></div>
          <div class="actions sum-act">${list.length ? `<button class="btn small" data-all="on">Включить все</button><button class="btn small" data-all="off">Выключить все</button>` : ''}</div>
        </div></div></div>`;

    view.innerHTML = head(title, sub, actions) + `<div class="src-page">
      <div id="addbox"></div>${ytNote}${summary}
      ${list.length ? `<div class="src-groups">${groups.filter(g => g.list.length).map(groupCard).join('')}</div>`
        : `<div class="card" style="margin-bottom:16px"><div class="empty"><b>Источников пока нет</b>Нажми «Добавить списком» → «Вставить стартовый набор» — это 30 проверенных источников по группам. Или добавь по одной ссылке.</div></div>`}
      <div class="card" id="items" style="margin-top:16px"><div class="card-h"><h2>${one ? 'Материалы: ' + esc(one.name) : 'Последние материалы'}</h2>
          <span class="muted small">${one ? '<a href="#/sources">показать все →</a>' : 'нажми на материал, чтобы увидеть, что внутри'}</span></div>
        ${items.length ? `<ul class="rows item-list">${items.map(itemRow).join('')}</ul>` : '<div class="empty">Пока пусто — материалы появятся после первого сбора.</div>'}
      </div></div>`;
    view.querySelectorAll('input[data-mixed]').forEach(cb => { cb.indeterminate = true; });

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
    page.addEventListener('click', async ev => {
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
        li.outerHTML = srcRow(s, dirs);
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
      if (cb.dataset.toggle) {
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
        <div class="form-row" style="margin-top:10px">
          <select class="input" id="bulkrole" aria-label="Группа по умолчанию">${roleOptions(roles, '', 'Без заголовка — без группы')}</select>
          <button class="btn" id="bulkstarter">Вставить стартовый набор</button>
          <button class="btn primary" id="bulkgo">Проверить и добавить</button>
        </div>
        <div id="bulkres"></div>
      </div></div>`;
    const ta = $('#bulktext');
    if (fillStarter) ta.value = STARTER;
    ta.focus();
    $('[data-x]', box).addEventListener('click', () => { box.innerHTML = ''; });
    $('#bulkstarter').addEventListener('click', () => { ta.value = STARTER; });
    $('#bulkgo').addEventListener('click', async ev => {
      const go = ev.currentTarget;
      const todo = parseBulk(ta.value, roles, $('#bulkrole').value);
      if (!todo.length) { toast('Вставь хотя бы одну ссылку', true); return; }
      go.disabled = true; $('#bulkstarter').disabled = true; ta.readOnly = true;
      const res = $('#bulkres');
      const label = r => r ? (roles.find(x => x.key === r) || {}).label || r : 'без группы';
      res.innerHTML = `<div class="bulk-sum muted small" id="bulksum"></div><ul class="bulk-list">${todo.map((t, i) => `<li id="bk${i}"><span class="bk-st">…</span>
        <span class="bk-name">${esc(t.name || t.link)}</span><span class="faint small">${esc(label(t.role))}</span><span class="bk-msg muted small">ждёт проверки</span></li>`).join('')}</ul>`;
      const tally = { ok: 0, dup: 0, err: 0 };
      const sum = () => { $('#bulksum').textContent = `Добавлено: ${tally.ok} · уже были: ${tally.dup} · не получилось: ${tally.err} · осталось: ${todo.length - tally.ok - tally.dup - tally.err}`; };
      sum();
      let next = 0;
      const worker = async () => {
        while (next < todo.length) {
          const i = next++, t = todo[i], li = $('#bk' + i);
          li.querySelector('.bk-msg').textContent = 'проверяю…';
          try {
            const s = await api('/api/sources', { body: { link: t.link, name: t.name || undefined, role: t.role || undefined } });
            li.className = 'ok'; li.querySelector('.bk-st').textContent = '✓';
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
        ${r.warning ? `<div class="note warnnote">${esc(r.warning)}</div>` : ''}
        ${r.items.length ? `<ul class="chk-items">${r.items.map(i => `<li><a href="${esc(i.url)}" target="_blank" rel="noopener">${esc(i.title)}</a><span class="faint">${i.published_at ? when(i.published_at) : ''}</span></li>`).join('')}</ul>` : ''}
        <div class="form-row" style="margin-top:14px">
          <input class="input" id="nname" value="${esc(r.name)}" maxlength="120" style="flex:1;min-width:200px" placeholder="Название" aria-label="Название">
          <select class="input" id="nrole" aria-label="Группа">${roleOptions(roles, '')}</select>
          <select class="input" id="nweight" aria-label="Важность">${WEIGHTS.map(([v, t]) => `<option value="${v}">Важность: ${t}</option>`).join('')}</select>
          ${dirs.length > 1 ? `<select class="input" id="ndir" aria-label="Направление">${dirs.map(x => `<option>${esc(x)}</option>`).join('')}</select>` : ''}
          <button class="btn primary" id="nsave">Сохранить и включить</button>
        </div></div>`;
      $('#nsave').addEventListener('click', async ev2 => {
        const b = ev2.currentTarget;
        b.disabled = true;
        const body = { link, name: $('#nname').value, weight: Number($('#nweight').value), role: $('#nrole').value || undefined };
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
    $('#pwsave').addEventListener('click', async () => {
      try { await api('/api/password', { body: { current: $('#pw0').value, new: $('#pw1').value } }); toast('Пароль изменён'); $('#pw0').value = $('#pw1').value = ''; }
      catch (e) { toast(e.message, true); }
    });
  }

  // ---------- маршруты ----------
  const PAGES = { '/': pageOverview, '/episodes': pageEpisodes, '/logs': pageLogs, '/costs': pageCosts, '/sources': pageSources, '/settings': pageSettings };

  function route() {
    if (!state.user) return;
    closeDrawer();
    clearInterval(state.timer);
    const [path, qs] = (location.hash.replace(/^#/, '') || '/').split('?');
    const page = PAGES[path] || pageOverview;
    markNav();
    const view = $('#view');
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
