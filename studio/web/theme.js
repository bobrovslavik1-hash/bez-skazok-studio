// Оформление Студии ставится до отрисовки страницы, чтобы не мигало.
// Тема: «Студия» (тёмная, по умолчанию), «День» (светлая), «Котики» (весёлая светлая) или «Авто» — как в системе.
// Тема своя на каждом устройстве. Обои (коты, лапки, своё фото, без обоев) общие: их присылает сервер,
// а здесь берём последние известные из памяти браузера — до ответа сервера.
(function () {
  var THEMES = { dark: '#0f1117', light: '#f3f5f9', cats: '#f1efff' };
  var pref = 'dark';
  try { pref = localStorage.getItem('studio-theme') || 'dark'; } catch (e) { /* хранилище недоступно — тёмная */ }
  var mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;
  var root = document.documentElement;
  function apply() {
    var t = pref === 'auto' ? (mq && mq.matches ? 'light' : 'dark') : (THEMES[pref] ? pref : 'dark');
    root.setAttribute('data-theme', t);
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute('content', THEMES[t]);
  }
  function look(a) {
    a = a || {};
    var wall = ['cats', 'paws', 'photo', 'none'].indexOf(a.wall) >= 0 ? a.wall : 'cats';
    if (wall === 'photo' && !a.photo_v) wall = 'cats';
    root.setAttribute('data-wall', wall);
    root.setAttribute('data-mascot', a.mascot === false ? 'off' : 'on');
    if (wall === 'photo') root.style.setProperty('--wall-photo', 'url("/api/appearance/photo?v=' + encodeURIComponent(a.photo_v) + '")');
    else root.style.removeProperty('--wall-photo');
  }
  window.studioTheme = {
    get: function () { return pref; },
    set: function (p) {
      pref = (THEMES[p] || p === 'auto') ? p : 'dark';
      try { localStorage.setItem('studio-theme', pref); } catch (e) { /* не запомним — не страшно */ }
      apply();
    },
  };
  window.studioLook = {
    apply: function (a) {
      look(a);
      try { localStorage.setItem('studio-look', JSON.stringify(a || {})); } catch (e) { /* не запомним */ }
    },
  };
  if (mq && mq.addEventListener) mq.addEventListener('change', function () { if (pref === 'auto') apply(); });
  apply();
  var saved = null;
  try { saved = JSON.parse(localStorage.getItem('studio-look') || 'null'); } catch (e) { /* по умолчанию */ }
  look(saved);
})();
