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
    if (opts.body !== undefined || opts.method === 'POST') {
      o.method = 'POST';
      o.headers['x-studio'] = '1';
      if (opts.body !== undefined) { o.headers['content-type'] = 'application/json'; o.body = JSON.stringify(opts.body); }
    }
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
  async function pageSources(view) {
    view.innerHTML = head('Источники', 'Откуда конвейер берёт новости') + loading();
    let d;
    try { d = await api('/api/sources'); } catch (e) { view.lastElementChild.outerHTML = failBox(e.message); return; }
    const sheet = d.settings_sheet ? `<a class="btn" href="${esc(d.settings_sheet)}" target="_blank" rel="noopener">${I.ext}Таблица настроек</a>` : '';
    const rows = d.sources || [];
    view.innerHTML = head('Источники', 'Откуда конвейер берёт новости', sheet) + `
      <div class="note" style="margin-bottom:16px">Добавлять и выключать источники прямо отсюда — в следующей версии Студии. Пока это делается в Google Таблице, лист <b>sources</b>.</div>
      <div class="card scroll-x">${rows.length ? `<table class="table"><tr><th>Источник</th><th>Тип</th><th>Направление</th><th class="r">За сутки</th><th class="r">За неделю</th><th class="r">Всего</th><th class="r">В выпусках</th><th>Последний раз</th></tr>
        ${rows.map(s => `<tr><td>${esc(s.source_name || '—')}</td><td>${esc(s.source_type || '—')}</td><td>${esc(s.direction_id)}</td><td class="r num">${s.d1}</td><td class="r num">${s.d7}</td><td class="r num">${s.total}</td><td class="r num">${s.used}</td><td>${when(s.last)}</td></tr>`).join('')}</table>`
        : `<div class="empty"><b>Лента пока пустая</b>Добавь сайты, Telegram- и YouTube-каналы в таблицу настроек — сбор идёт каждые 30 минут.</div>`}</div>`;
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
            <ol class="steps"><li>Адрес с токеном показал установщик на сервере. Повторить: <span class="mono">docker compose exec studio python -m app.cli mcp-url</span></li>
              <li>В Claude: Настройки → Коннекторы → Добавить свой коннектор → вставить адрес.</li>
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
