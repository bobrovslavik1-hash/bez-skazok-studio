// Тема Студии: «Студия» (тёмная, по умолчанию), «День» (светлая) или «Авто» — как в системе.
// Ставится до отрисовки страницы, чтобы не мигало. Выбор помнит этот браузер.
(function () {
  var pref = 'dark';
  try { pref = localStorage.getItem('studio-theme') || 'dark'; } catch (e) { /* хранилище недоступно — тёмная */ }
  var mq = window.matchMedia ? window.matchMedia('(prefers-color-scheme: light)') : null;
  function apply() {
    var t = pref === 'auto' ? (mq && mq.matches ? 'light' : 'dark') : (pref === 'light' ? 'light' : 'dark');
    document.documentElement.setAttribute('data-theme', t);
    var m = document.querySelector('meta[name="theme-color"]');
    if (m) m.setAttribute('content', t === 'light' ? '#e6e2dc' : '#191816');
  }
  window.studioTheme = {
    get: function () { return pref; },
    set: function (p) {
      pref = p === 'light' || p === 'auto' ? p : 'dark';
      try { localStorage.setItem('studio-theme', pref); } catch (e) { /* не запомним — не страшно */ }
      apply();
    },
  };
  if (mq && mq.addEventListener) mq.addEventListener('change', function () { if (pref === 'auto') apply(); });
  apply();
})();
