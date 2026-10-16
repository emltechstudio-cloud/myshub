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

  function boot() {
    if (!document.getElementById('google_translate_element')) {
      var box = document.createElement('div');
      box.id = 'google_translate_element';
      box.setAttribute('aria-hidden', 'true');
      box.style.cssText = 'position:fixed;left:-9999px;top:0;width:1px;height:1px;overflow:hidden;opacity:0;pointer-events:none';
      (document.body || document.documentElement).appendChild(box);
    }
    bindSelects();
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
