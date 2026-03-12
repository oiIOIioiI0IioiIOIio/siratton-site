/* lang.js — Language toggle (FR ↔ EN) for siratton.site
   ─────────────────────────────────────────────────────── */
(function () {
  'use strict';

  var STORAGE_KEY = 'site-lang';

  function applyLang(lang) {
    document.querySelectorAll('[data-fr][data-en]').forEach(function (el) {
      el.textContent = el.getAttribute('data-' + lang);
    });

    document.documentElement.setAttribute('lang', lang);

    document.querySelectorAll('.btn-english').forEach(function (btn) {
      btn.textContent = lang === 'fr' ? 'EN' : 'FR';
      btn.setAttribute('aria-label',
        lang === 'fr' ? 'English version' : 'Version française');
    });

    try { localStorage.setItem(STORAGE_KEY, lang); } catch (e) { /* private browsing */ }
  }

  function currentLang() {
    try {
      var stored = localStorage.getItem(STORAGE_KEY);
      if (stored === 'en' || stored === 'fr') return stored;
    } catch (e) { /* private browsing */ }
    return 'fr';
  }

  /* Initialise on DOM ready */
  function init() {
    var lang = currentLang();
    applyLang(lang);

    document.querySelectorAll('.btn-english').forEach(function (btn) {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        var next = currentLang() === 'fr' ? 'en' : 'fr';
        applyLang(next);
      });
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
