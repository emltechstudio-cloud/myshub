/*
 * MyShub central analytics collector.
 *
 * Add this script to index.html, app.html, and discover.html:
 *   <script src="/analytics-collector.js" defer></script>
 *
 * Then initialize it once per page surface:
 *   MyShubAnalytics.init({ surface: 'site' });
 *   MyShubAnalytics.init({ surface: 'app' });
 *   MyShubAnalytics.init({ surface: 'discover' });
 *
 * The backend adds the timestamp, normalized referrer, device, and country.
 * This client does not send passwords, email addresses, IP addresses, or raw
 * user-agent strings. It also sends only the event fields accepted by the
 * central endpoint.
 */
(function (window, document) {
  'use strict';

  var DEFAULT_API = 'https://emltechstudio-myshub-api.hf.space';
  var ALLOWED_SURFACES = ['site', 'app', 'discover', 'shop', 'auth', 'other'];
  var ALLOWED_EVENTS = [
    'page_view',
    'discover_search',
    'discover_result_open',
    'discover_shop_click',
    'shop_view',
    'shop_click',
    'signup_started',
    'signup_completed',
    'profile_completed'
  ];

  var config = {
    apiBase: window.API || DEFAULT_API,
    surface: 'site',
    autoPageView: true,
    dedupePageViews: true,
    debug: false
  };
  var initialized = false;
  var sentPageKeys = {};
  var queue = [];
  var flushing = false;

  function clean(value, max) {
    if (value === null || value === undefined) return '';
    return String(value).trim().slice(0, max || 180);
  }

  function validSurface(surface) {
    surface = clean(surface, 30).toLowerCase();
    return ALLOWED_SURFACES.indexOf(surface) !== -1 ? surface : 'other';
  }

  function validEvent(event) {
    event = clean(event, 60).toLowerCase();
    return ALLOWED_EVENTS.indexOf(event) !== -1 ? event : '';
  }

  function currentPath() {
    return (window.location.pathname || '/') + (window.location.search || '');
  }

  function log() {
    if (config.debug && window.console && console.debug) console.debug.apply(console, arguments);
  }

  function pageKey(path, surface) {
    return 'myshub:analytics:page:' + surface + ':' + path;
  }

  function alreadySent(key) {
    if (!config.dedupePageViews) return false;
    if (sentPageKeys[key]) return true;
    try {
      if (window.sessionStorage && sessionStorage.getItem(key)) return true;
      if (window.sessionStorage) sessionStorage.setItem(key, '1');
    } catch (_) {}
    sentPageKeys[key] = true;
    return false;
  }

  function normalizedPayload(event, options) {
    options = options || {};
    var safeEvent = validEvent(event);
    if (!safeEvent) return null;
    var surface = validSurface(options.surface || config.surface);
    return {
      event: safeEvent,
      surface: surface,
      path: clean(options.path || currentPath(), 240),
      shop_slug: clean(options.shop_slug || '', 120).toLowerCase(),
      detail: clean(options.detail || '', 180),
      count: Math.max(1, Math.min(20, Number(options.count || 1) || 1))
    };
  }

  function send(payload) {
    var url = config.apiBase.replace(/\/$/, '') + '/analytics/event';
    var body = JSON.stringify(payload);

    // Beacon is reliable during page exit. It does not expose the response,
    // which is fine because analytics collection must never block navigation.
    try {
      if (navigator.sendBeacon) {
        var blob = new Blob([body], { type: 'application/json' });
        if (navigator.sendBeacon(url, blob)) return Promise.resolve(true);
      }
    } catch (_) {}

    try {
      return fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: body,
        keepalive: true,
        credentials: 'omit'
      }).then(function (response) {
        return response.ok;
      }).catch(function () { return false; });
    } catch (_) {
      return Promise.resolve(false);
    }
  }

  function flush() {
    if (flushing || !queue.length) return;
    flushing = true;
    var batch = queue.splice(0, queue.length);
    Promise.all(batch.map(send)).then(function (results) {
      results.forEach(function (ok, index) {
        if (!ok && batch[index]) {
          // Keep only a small retry queue. Analytics failure must not consume
          // memory or interfere with the user’s page.
          if (queue.length < 20) queue.push(batch[index]);
        }
      });
      flushing = false;
      if (queue.length) setTimeout(flush, 1200);
    }).catch(function () {
      flushing = false;
    });
  }

  function track(event, options) {
    var payload = normalizedPayload(event, options);
    if (!payload) return false;
    queue.push(payload);
    flush();
    return true;
  }

  function pageView(path, options) {
    options = options || {};
    var actualPath = clean(path || currentPath(), 240);
    var surface = validSurface(options.surface || config.surface);
    var key = pageKey(actualPath, surface);
    if (alreadySent(key)) return false;
    return track('page_view', {
      surface: surface,
      path: actualPath,
      detail: clean(options.detail || '', 180)
    });
  }

  function discoverSearch(context) {
    context = context || {};
    // Prefer a compact structured description over an unrestricted raw query.
    var parts = [];
    if (context.category) parts.push('category=' + clean(context.category, 60));
    if (context.country) parts.push('country=' + clean(context.country, 60));
    if (context.state) parts.push('state=' + clean(context.state, 60));
    if (context.city) parts.push('city=' + clean(context.city, 60));
    if (!parts.length && context.query) parts.push('query=' + clean(context.query, 120));
    return track('discover_search', { surface: 'discover', detail: parts.join('|') });
  }

  function discoverResultOpen(slug, position) {
    return track('discover_result_open', {
      surface: 'discover',
      shop_slug: clean(slug, 120),
      detail: position === undefined ? '' : 'position=' + Number(position || 0)
    });
  }

  function discoverShopClick(slug, target) {
    return track('discover_shop_click', {
      surface: 'discover',
      shop_slug: clean(slug, 120),
      detail: clean(target || 'shop', 120)
    });
  }

  function signupStarted(source) {
    return track('signup_started', { surface: 'auth', detail: clean(source || '', 120) });
  }

  function signupCompleted(source) {
    return track('signup_completed', { surface: 'auth', detail: clean(source || '', 120) });
  }

  function profileCompleted(slug) {
    return track('profile_completed', { surface: 'app', shop_slug: clean(slug, 120) });
  }

  function init(options) {
    options = options || {};
    config.apiBase = options.apiBase || config.apiBase;
    config.surface = validSurface(options.surface || config.surface);
    config.autoPageView = options.autoPageView !== false;
    config.dedupePageViews = options.dedupePageViews !== false;
    config.debug = options.debug === true;
    initialized = true;
    if (config.autoPageView) pageView(options.path || currentPath(), options);
    window.addEventListener('pagehide', flush, { capture: true });
    document.addEventListener('visibilitychange', function () {
      if (document.visibilityState === 'hidden') flush();
    });
    return api;
  }

  var api = {
    init: init,
    track: track,
    pageView: pageView,
    discoverSearch: discoverSearch,
    discoverResultOpen: discoverResultOpen,
    discoverShopClick: discoverShopClick,
    signupStarted: signupStarted,
    signupCompleted: signupCompleted,
    profileCompleted: profileCompleted,
    flush: flush,
    get initialized() { return initialized; }
  };

  window.MyShubAnalytics = api;
})(window, document);
