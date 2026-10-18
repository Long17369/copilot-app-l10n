/*__COPILOT_L10N__*/
/* Simplified-Chinese runtime localizer for the GitHub Copilot desktop WebView.
 * Appended to an app chunk by apply_zh.py. Remove with the `restore` command.
 * Disable at runtime: localStorage.setItem('copilot-l10n','off') then reload.
 * Inspect what is still English: window.__COPILOT_L10N_MISSES__()
 */
(function () {
  'use strict';
  if (typeof window === 'undefined' || typeof document === 'undefined') return;
  if (window.__COPILOT_L10N_ZH__) return;
  try {
    if (window.localStorage && localStorage.getItem('copilot-l10n') === 'off') return;
  } catch (e) { /* ignore */ }
  window.__COPILOT_L10N_ZH__ = true;

  var DICT = __DICT_JSON__;

  // Dynamic messages: [regex, replacement]
  var RULES = [
    [/^(\d+)\s+files?$/i, '$1 个文件'],
    [/^(\d+)\s+folders?$/i, '$1 个文件夹'],
    [/^(\d+)\s+changes?$/i, '$1 项更改'],
    [/^(\d+)\s+comments?$/i, '$1 条评论'],
    [/^(\d+)\s+sessions?$/i, '$1 个会话'],
    [/^(\d+)\s+projects?$/i, '$1 个项目'],
    [/^(\d+)\s+agents?$/i, '$1 个代理'],
    [/^(\d+)\s+repositor(y|ies)$/i, '$1 个仓库'],
    [/^(\d+)\s+messages?$/i, '$1 条消息'],
    [/^(\d+)\s+results?$/i, '$1 个结果'],
    [/^(\d+)\s+matches$/i, '$1 个匹配'],
    [/^(\d+)\s+selected$/i, '已选择 $1 项'],
    [/^(\d+)\s+items?\s+selected$/i, '已选择 $1 项'],
    [/^(\d+)\s+more$/i, '还有 $1 项'],
    [/^(\d+)\s+of\s+(\d+)$/i, '$1 / $2'],
    [/^show(ing)?\s+(\d+)$/i, '显示 $2 项'],
    [/^just now$/i, '刚刚'],
    [/^(\d+)\s*s(ec(onds?)?)?\s+ago$/i, '$1 秒前'],
    [/^(\d+)\s*m(in(utes?)?)?\s+ago$/i, '$1 分钟前'],
    [/^(\d+)\s*h(ours?|rs?)?\s+ago$/i, '$1 小时前'],
    [/^(\d+)\s*d(ays?)?\s+ago$/i, '$1 天前'],
    [/^(\d+)\s*w(eeks?|ks?)?\s+ago$/i, '$1 周前'],
    [/^(\d+)\s*mo(nths?)?\s+ago$/i, '$1 个月前'],
    [/^(\d+)\s*y(ears?|rs?)?\s+ago$/i, '$1 年前'],
    [/^(in|after)\s+(\d+)\s*(s|sec|seconds?)$/i, '$2 秒后'],
    [/^(in|after)\s+(\d+)\s*(m|min|minutes?)$/i, '$2 分钟后'],
    [/^(in|after)\s+(\d+)\s*(h|hours?)$/i, '$2 小时后'],
    [/^(in|after)\s+(\d+)\s*(d|days?)$/i, '$2 天后'],
    [/^(\d+)\s*\/\s*(\d+)$/i, '$1 / $2']
  ];

  var ATTRS = [
    'placeholder',
    'title',
    'aria-label',
    'aria-description',
    'aria-placeholder',
    'aria-roledescription',
    'data-tooltip',
    'data-tooltip-content',
    'alt'
  ];
  var SKIP_SEL = 'pre,code,kbd,samp,textarea,script,style,[contenteditable="true"],.markdown-body,.monaco-editor,[data-l10n-skip]';

  var cache = new Map();
  var misses = new Set();

  function lookup(key) {
    if (!key) return null;
    if (cache.has(key)) return cache.get(key);
    var out = Object.prototype.hasOwnProperty.call(DICT, key) ? DICT[key] : null;
    if (out === null) {
      var trimmed = key.replace(/[:：]\s*$/, '');
      if (trimmed !== key && Object.prototype.hasOwnProperty.call(DICT, trimmed)) {
        out = DICT[trimmed] + '：';
      }
    }
    if (out === null) {
      for (var i = 0; i < RULES.length; i++) {
        if (RULES[i][0].test(key)) {
          out = key.replace(RULES[i][0], RULES[i][1]);
          break;
        }
      }
    }
    cache.set(key, out);
    if (out === null) misses.add(key);
    return out;
  }

  function translate(key) {
    return lookup(key);
  }

  function localizeTextNode(node) {
    var value = node.nodeValue;
    if (!value || value.length > 400) return;
    var m = /^(\s*)([\s\S]*?)(\s*)$/.exec(value);
    if (!m) return;
    var key = m[2];
    if (!key || key.length > 160) return;
    var t = translate(key);
    if (t !== null && t !== key) node.nodeValue = m[1] + t + m[3];
  }

  function setTranslatedAttribute(el, name, value) {
    var key = value.trim();
    if (!key || key.length > 160) return;
    var t = translate(key);
    if (t !== null && t !== key) el.setAttribute(name, value.replace(key, t));
  }

  function localizeAttrs(el) {
    if (!el.getAttribute) return;
    for (var i = 0; i < ATTRS.length; i++) {
      var v = el.getAttribute(ATTRS[i]);
      if (v) setTranslatedAttribute(el, ATTRS[i], v);
    }
    if (el.tagName === 'INPUT') {
      var type = (el.getAttribute('type') || '').toLowerCase();
      if (type === 'button' || type === 'submit' || type === 'reset') {
        var value = el.getAttribute('value');
        if (value) setTranslatedAttribute(el, 'value', value);
      }
    }
  }

  function isSkipped(el) {
    return !!(el.closest && el.closest(SKIP_SEL));
  }

  /* React renders `{count} files` as two text nodes ("12" + " files"). Translate the
   * joined form, then blank out the second node so the text is not duplicated. */
  function localizeJoinedText(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var node;
    while ((node = walker.nextNode())) {
      var next = node.nextSibling;
      if (!next || next.nodeType !== 3) continue;
      var parent = node.parentElement;
      if (!parent || isSkipped(parent)) continue;
      if (!node.nodeValue || node.nodeValue.length > 12) continue;
      var joined = (node.nodeValue + next.nodeValue).trim();
      if (joined.length > 160) continue;
      var t = translate(joined);
      if (t === null) continue;
      var lead = /^\s*/.exec(node.nodeValue)[0];
      node.nodeValue = lead + t;
      next.nodeValue = '';
    }
  }

  function walk(node) {
    if (!node) return;
    if (node.nodeType === 3) {
      localizeTextNode(node);
      return;
    }
    if (node.nodeType !== 1) return;
    if (isSkipped(node)) return;
    localizeAttrs(node);
    if (node.shadowRoot) walk(node.shadowRoot);

    var walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        var parent = n.parentElement;
        if (!parent || isSkipped(parent)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var text;
    while ((text = walker.nextNode())) localizeTextNode(text);

    var all = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (var i = 0; i < all.length; i++) {
      if (!isSkipped(all[i])) localizeAttrs(all[i]);
    }
    localizeJoinedText(node);
  }

  var observer = new MutationObserver(function (mutations) {
    for (var i = 0; i < mutations.length; i++) {
      var m = mutations[i];
      if (m.type === 'childList') {
        for (var j = 0; j < m.addedNodes.length; j++) walk(m.addedNodes[j]);
      } else if (m.type === 'characterData') {
        localizeTextNode(m.target);
      } else if (m.type === 'attributes') {
        localizeAttrs(m.target);
      }
    }
  });

  function start() {
    try {
      document.documentElement.lang = 'zh-CN';
    } catch (e) { /* ignore */ }
    walk(document.body || document.documentElement);
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ATTRS
    });
    // Re-apply while the first paint settles (hydration / route mount).
    setTimeout(function () { walk(document.body); }, 300);
    setTimeout(function () { walk(document.body); }, 1000);
    setTimeout(function () { walk(document.body); }, 2500);

    window.__COPILOT_L10N_MISSES__ = function () {
      return Array.from(misses).sort();
    };

    /* Ctrl+Alt+L copies every string that had no translation, so gaps can be reported
     * without opening developer tools. Ctrl+Alt+U re-scans the whole document. */
    document.addEventListener('keydown', function (event) {
      if (!event.ctrlKey || !event.altKey) return;
      var key = (event.key || '').toLowerCase();
      if (key === 'u') {
        walk(document.body);
        return;
      }
      if (key !== 'l') return;
      event.preventDefault();
      var text = Array.from(misses).sort().join('\n');
      var done = function () {
        var notice = document.createElement('div');
        notice.textContent = '已复制 ' + misses.size + ' 条未翻译文案';
        notice.setAttribute('data-l10n-skip', '');
        notice.style.cssText = 'position:fixed;z-index:2147483647;bottom:16px;right:16px;' +
          'padding:8px 14px;border-radius:6px;background:#1f6feb;color:#fff;' +
          'font:13px/1.4 system-ui,sans-serif;box-shadow:0 4px 16px rgba(0,0,0,.3)';
        document.body.appendChild(notice);
        setTimeout(function () { notice.remove(); }, 2500);
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, done);
      } else {
        var area = document.createElement('textarea');
        area.value = text;
        document.body.appendChild(area);
        area.select();
        try { document.execCommand('copy'); } catch (e) { /* ignore */ }
        area.remove();
        done();
      }
    });

    if (window.console && console.info) {
      console.info('[copilot-l10n] zh-CN active. Ctrl+Alt+L copies untranslated strings.');
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
