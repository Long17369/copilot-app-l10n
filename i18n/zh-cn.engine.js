/*__COPILOT_L10N__*/
/* Simplified-Chinese runtime localizer for the GitHub Copilot desktop WebView.
 * Appended to an app chunk by copilot_l10n.py. Remove with the `restore` command.
 * Disable at runtime: localStorage.setItem('copilot-l10n','off') then reload.
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
    [/^(\d+) files?$/, '$1 个文件'],
    [/^(\d+) folders?$/, '$1 个文件夹'],
    [/^(\d+) changes?$/, '$1 项更改'],
    [/^(\d+) comments?$/, '$1 条评论'],
    [/^(\d+) sessions?$/, '$1 个会话'],
    [/^(\d+) projects?$/, '$1 个项目'],
    [/^(\d+) agents?$/, '$1 个代理'],
    [/^(\d+) repositories$/, '$1 个仓库'],
    [/^(\d+) selected$/, '已选择 $1 项'],
    [/^(\d+) more$/, '还有 $1 项'],
    [/^(\d+) of (\d+)$/, '$1 / $2'],
    [/^just now$/i, '刚刚'],
    [/^(\d+) seconds? ago$/, '$1 秒前'],
    [/^(\d+) minutes? ago$/, '$1 分钟前'],
    [/^(\d+) hours? ago$/, '$1 小时前'],
    [/^(\d+) days? ago$/, '$1 天前'],
    [/^(\d+) weeks? ago$/, '$1 周前'],
    [/^(\d+) months? ago$/, '$1 个月前'],
    [/^(\d+) years? ago$/, '$1 年前']
  ];

  var ATTRS = ['placeholder', 'title', 'aria-label', 'aria-description', 'aria-placeholder', 'alt'];
  var SKIP_SEL = 'pre,code,kbd,samp,textarea,script,style,[contenteditable="true"],.markdown-body,.monaco-editor,[data-l10n-skip]';

  var cache = new Map();
  function translate(key) {
    if (!key) return null;
    if (cache.has(key)) return cache.get(key);
    var out = Object.prototype.hasOwnProperty.call(DICT, key) ? DICT[key] : null;
    if (out === null) {
      for (var i = 0; i < RULES.length; i++) {
        if (RULES[i][0].test(key)) {
          out = key.replace(RULES[i][0], RULES[i][1]);
          break;
        }
      }
    }
    cache.set(key, out);
    return out;
  }

  function localizeTextNode(node) {
    var value = node.nodeValue;
    if (!value || value.length > 400) return;
    var m = /^(\s*)([\s\S]*?)(\s*)$/.exec(value);
    var key = m[2];
    if (!key || key.length > 120) return;
    var t = translate(key);
    if (t !== null && t !== key) node.nodeValue = m[1] + t + m[3];
  }

  function setTranslatedAttribute(el, name, value) {
    var key = value.trim();
    if (!key || key.length > 120) return;
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
      if (type === 'button' || type === 'submit') {
        var value = el.getAttribute('value');
        if (value) setTranslatedAttribute(el, 'value', value);
      }
    }
  }

  function isSkipped(el) {
    return !!(el.closest && el.closest(SKIP_SEL));
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
      if (document.title === 'GitHub Copilot') document.title = 'GitHub Copilot';
    } catch (e) { /* ignore */ }
    walk(document.body || document.documentElement);
    observer.observe(document.documentElement, {
      childList: true,
      subtree: true,
      characterData: true,
      attributes: true,
      attributeFilter: ATTRS
    });
    // Re-apply once the first paint settles (hydration / route mount).
    setTimeout(function () { walk(document.body); }, 400);
    setTimeout(function () { walk(document.body); }, 1500);
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', start, { once: true });
  } else {
    start();
  }
})();
