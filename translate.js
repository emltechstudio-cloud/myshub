/*
 * MyShub in-page translation (Google Website Translator widget).
 *
 * Why not the translate.google.com/translate?u= proxy: it re-hosts the page on
 * Google's origin, so API requests are sent with Origin: https://translate.google.com
 * and our CORS allowlist rejects them. The widget below translates the DOM in
 * place while the page stays on myshub.site — API calls, sessions, sharing and
 * clicks keep working exactly as before.
 *
 * Usage:
 *   <script src="/translate.js" defer></script>
 *   <select data-myshub-translate> ... </select>
 *
 * Dynamic pages (API content rendered after load) should call
 *   MyShubTranslate.retranslate()
 * after their content renders; it re-runs translation once, debounced.
 */
(function (window, document) {
  'use strict';

  var SUPPORTED = 'en,fr,es,pt,ar,de,sw,ha,yo,it,zh-CN,ru,hi';
  var COOKIE = 'googtrans';

  function lang() {
    var m = document.cookie.match(/(?:^|;\s*)googtrans=\/en\/([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }

  function writeCookie(value) {
    var host = location.hostname;
    var attrs = ';path=/';
    document.cookie = COOKIE + '=' + value + attrs;
    try {
      document.cookie = COOKIE + '=' + value + attrs + ';domain=' + host;
      if (host.indexOf('.') !== -1) {
        document.cookie = COOKIE + '=' + value + attrs + ';domain=.' + host.split('.').slice(-2).join('.');
      }
    } catch (_) {}
  }

  function select(value) {
    if (!value) return;
    writeCookie('/en/' + encodeURIComponent(value));
    location.reload();
  }

  function clear() {
    document.cookie = COOKIE + '=;path=/;expires=Thu, 01 Jan 1970 00:00:01 GMT';
    location.reload();
  }

  function initWidget() {
    if (!window.google || !window.google.translate) return false;
    if (!document.getElementById('google_translate_element')) return false;
    try {
      window.google.translate.TranslateElement({
        pageLanguage: 'en',
        includedLanguages: SUPPORTED,
        autoDisplay: false
      }, 'google_translate_element');
      return true;
    } catch (_) {
      return false;
    }
  }

  var queued = false;
  function retranslate() {
    // Debounced so a burst of API re-renders only triggers one pass.
    if (queued || !lang()) return;
    queued = true;
    setTimeout(function () {
      queued = false;
      initWidget();
    }, 800);
  }

  function bindSelects() {
    var nodes = document.querySelectorAll('[data-myshub-translate]');
    var active = lang();
    for (var i = 0; i < nodes.length; i++) {
      (function (el) {
        if (el.getAttribute('data-bound')) return;
        el.setAttribute('data-bound', '1');
        if (active && el.querySelector('option[value="' + active + '"]')) el.value = active;
        el.addEventListener('change', function () {
          if (el.value) select(el.value);
          else if (lang()) clear();
        });
      })(nodes[i]);
    }
  }

  /* ---- Language chip: one visible globe control, placed beside each page's
         menu button (hamburger / nav toggle), or at the far end of the nav on
         desktop, or fixed top-right as a last resort. ---- */
  var CHIP_ID = 'myshubLangChip';
  var CHIP_POOLS = ['.hamburger', '#menuToggle', '.nav-toggle', '.nav-links', '.header-actions', '.head-actions'];
  var CHIP_CSS = '.myshub-lang-chip{display:inline-flex;align-items:center;gap:5px;border:1px solid rgba(120,130,150,.4);' +
    'background:rgba(255,255,255,.95);color:#1f2937;border-radius:999px;padding:5px 10px;cursor:pointer;font-weight:700;' +
    'font-size:12px;box-shadow:0 2px 8px rgba(15,23,42,.08);vertical-align:middle;margin:0 6px;line-height:1.2}' +
    '.myshub-lang-chip i{font-size:12px;color:#2563eb}' +
    '.myshub-lang-chip select{border:none;background:transparent;color:inherit;font:inherit;font-weight:700;font-size:12px;' +
    'cursor:pointer;outline:none;max-width:92px;padding:0}' +
    '.myshub-lang-chip.myshub-chip-fixed{position:fixed;top:10px;right:14px;z-index:95}';

  function injectChipStyles() {
    if (document.getElementById('myshub-chip-style')) return;
    var st = document.createElement('style');
    st.id = 'myshub-chip-style';
    st.textContent = CHIP_CSS;
    (document.head || document.getElementsByTagName('head')[0] || document.documentElement).appendChild(st);
  }

  function chipTarget() {
    for (var p = 0; p < CHIP_POOLS.length; p++) {
      var nodes = document.querySelectorAll(CHIP_POOLS[p]);
      for (var i = 0; i < nodes.length; i++) {
        if (nodes[i].offsetParent !== null) return { el: nodes[i], mode: CHIP_POOLS[p] };
      }
    }
    return null;
  }

  function placeChip(chip) {
    var target = chipTarget();
    if (!target) { chip.classList.add('myshub-chip-fixed'); return; }
    chip.classList.remove('myshub-chip-fixed');
    if (target.mode === '.hamburger' || target.mode === '#menuToggle' || target.mode === '.nav-toggle') {
      target.el.parentNode.insertBefore(chip, target.el.nextSibling);
    } else {
      target.el.insertBefore(chip, target.el.firstChild);
    }
  }

  function ensureChip() {
    var chip = document.getElementById(CHIP_ID);
    if (!chip) {
      injectChipStyles();
      chip = document.createElement('span');
      chip.className = 'myshub-lang-chip';
      chip.id = CHIP_ID;
      chip.title = 'Choose language';
      chip.innerHTML = '<i class="fa-solid fa-globe" aria-hidden="true"></i>' +
        '<select data-myshub-translate aria-label="Translate this page">' +
        '<option value="">English</option><option value="fr">Français</option><option value="es">Español</option>' +
        '<option value="pt">Português</option><option value="ar">العربية</option><option value="de">Deutsch</option>' +
        '<option value="sw">Kiswahili</option><option value="yo">Yoruba</option><option value="ha">Hausa</option></select>';
      placeChip(chip);
      bindSelects();
      return;
    }
    // Late-rendered navbars (API shop pages): move a fixed fallback chip into place.
    if (chip.classList.contains('myshub-chip-fixed') && chipTarget()) placeChip(chip);
  }

  function observeNewSelects() {
    if (!window.MutationObserver || !document.documentElement) return;
    var timer = null;
    new MutationObserver(function () {
      if (timer) return;
      timer = setTimeout(function () { timer = null; bindSelects(); ensureChip(); }, 300);
    }).observe(document.documentElement, { childList: true, subtree: true });
  }

  function boot() {
    if (!document.getElementById('google_translate_element')) {
      var box = document.createElement('div');
      box.id = 'google_translate_element';
      box.setAttribute('aria-hidden', 'true');
      box.style.cssText = 'position:fixed;left:-9999px;top:0;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none';
      (document.body || document.documentElement).appendChild(box);
    }
    bindSelects();
    ensureChip();
    observeNewSelects();
    initWidget();
    if (lang()) {
      // First pass runs at load; API content usually lands shortly after, so
      // translate once more after it settles.
      setTimeout(retranslate, 2600);
    }
  }

  function loadScript() {
    if (document.getElementById('gtranslate-script')) return;
    var s = document.createElement('script');
    s.id = 'gtranslate-script';
    s.src = 'https://translate.google.com/translate_a/element.js?cb=googleTranslateElementInit';
    (document.head || document.getElementsByTagName('head')[0] || document.body).appendChild(s);
  }

  window.MyShubTranslate = {
    select: select,
    clear: clear,
    lang: lang,
    retranslate: retranslate,
    bind: bindSelects
  };
  window.googleTranslateElementInit = function () {
    initWidget();
    if (lang()) setTimeout(retranslate, 2600);
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', function () { boot(); loadScript(); });
  } else {
    boot();
    loadScript();
  }
})(window, document);
