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
  /* Terms that stay in English on purpose (skill, issue, agent, ...). They must not be
   * translated nor reported as missing. */
  var KEEP = __KEEP_JSON__;

  var KEEP_SET = new Set(KEEP.map(function (w) { return w.toLowerCase(); }));
  var KEEP_JOINED = new Set(
    KEEP.map(function (w) { return w.toLowerCase(); })
      .concat(KEEP.map(function (w) { return w.toLowerCase() + 's'; }))
  );

  // Dynamic messages: [regex, replacement]
  var RULES = [
    [/^(\d+)\s+files?$/i, '$1 个文件'],
    [/^(\d+)\s+folders?$/i, '$1 个文件夹'],
    [/^(\d+)\s+changes?$/i, '$1 项更改'],
    [/^(\d+)\s+comments?$/i, '$1 条评论'],
    [/^(\d+)\s+sessions?$/i, '$1 个会话'],
    [/^(\d+)\s+projects?$/i, '$1 个项目'],
    [/^(\d+)\s+agents?$/i, '$1 个 Agent'],
    [/^(\d+)\s+repositor(y|ies)$/i, '$1 个仓库'],
    [/^(\d+)\s+skills?$/i, '$1 个 Skill'],
    [/^(\d+)\s+issues?$/i, '$1 个 Issue'],
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
    [/^Thought for\s+([\d.]+)s$/i, '思考了 $1 秒'],
    [/^Thought for\s+(\d+)m\s*(\d+)s$/i, '思考了 $1 分 $2 秒'],
    [/^Thinking for\s+([\d.]+)s$/i, '思考了 $1 秒'],
    [/^AI credits quota:\s*(\d+)%\s*used$/i, 'AI 额度配额：已用 $1%'],
    [/^(in|after)\s+(\d+)\s*(s|sec|seconds?)$/i, '$2 秒后'],
    [/^(in|after)\s+(\d+)\s*(m|min|minutes?)$/i, '$2 分钟后'],
    [/^(in|after)\s+(\d+)\s*(h|hours?)$/i, '$2 小时后'],
    [/^(in|after)\s+(\d+)\s*(d|days?)$/i, '$2 天后'],
    [/^(\d+)\s*\/\s*(\d+)$/i, '$1 / $2'],
    /* Status suffixes rendered as their own span, e.g. "Session" + ", failed". */
    [/^[,，]\s*edited$/i, '，已编辑'],
    [/^[,，]\s*edit history$/i, '，编辑历史'],
    [/^[,，]\s*failed$/i, '，失败'],
    [/^[,，]\s*succeeded$/i, '，成功'],
    [/^[,，]\s*modified$/i, '，已修改'],
    [/^[,，]\s*starting$/i, '，正在启动'],
    [/^[,，]\s*no project$/i, '，无项目'],
    [/^[,，]\s*model,?\s*required$/i, '，模型（必填）'],
    [/^[,，]\s*preview$/i, '，预览']
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
  var badgeTimer = null;
  var updateBadge = null;

  /* Strings that are never worth reporting as "untranslated": paths, shortcuts,
   * identifiers and code fragments. Without this the gap list fills up with file
   * paths and key combinations copied from tool panels. */
  var MISS_NOISE = [
    /^[A-Za-z]:[\\/]/,                                  // C:\...
    /^\.{0,2}\//,                                       // /usr/..., ./src
    /^(Ctrl|Control|Alt|Shift|Cmd|Meta|⌘|Option)\b/i,   // shortcut labels
    /^[\w.-]+\.(js|mjs|ts|tsx|jsx|py|md|json|exe|cmd|bat|txt|yml|yaml|css|html)$/i,
    /^[A-Z_]{3,}$/,                                     // CONSTANTS
    /^[0-9a-f]{7,}$/i,                                  // hashes
    /^[\w-]+\/[\w-]+$/,                                 // owner/repo-ish
    /^[a-z]+[A-Z]\w+$/,                                 // camelCase identifiers
  ];

  function isNoise(text) {
    for (var i = 0; i < MISS_NOISE.length; i++) {
      if (MISS_NOISE[i].test(text)) return true;
    }
    return false;
  }

  function recordMiss(key) {
    var probe = key.trim();
    if (!probe) return;
    if (!/^[A-Z]/.test(probe) && !/\s/.test(probe)) return;
    if (isNoise(probe)) return;
    misses.add(key);
  }

  function lookup(key, quiet) {
    if (!key) return null;
    // Deliberately untranslated vocabulary: keep the English word as-is.
    if (KEEP_SET.has(key.trim().toLowerCase())) return null;
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
    if (out === null && !quiet) recordMiss(key);
    return out;
  }

  /* Accessible labels and hints are assembled from several parts, e.g.
   * "1 hour ago, Response sent, show timestamp" or
   * "New session, Ctrl + N. New chat, Ctrl + Shift + N.".
   * Translate such a string part by part, keeping separators in Chinese form. */
  function translateComposite(key) {
    if (key.length > 240) return null;
    var pieces = key.split(/(,\s+|\.\s+|;\s+)/);
    if (pieces.length < 3) return null;

    var out = '';
    var changed = false;
    for (var i = 0; i < pieces.length; i++) {
      var piece = pieces[i];
      if (i % 2 === 1) {
        var sep = piece.charAt(0);
        out += sep === ',' ? '，' : (sep === '.' ? '。' : '；');
        continue;
      }
      var core = piece.trim();
      if (!core) continue;
      var hasDot = /\.$/.test(core);
      var probe = hasDot ? core.slice(0, -1) : core;
      var t = lookup(probe, true);
      if (t === null) {
        out += core;
      } else {
        out += t;
        changed = true;
      }
    }
    return changed ? out : null;
  }

  function translate(key) {
    // Deliberately untranslated vocabulary is neither translated nor reported.
    if (KEEP_SET.has(key.trim().toLowerCase())) return null;
    var out = lookup(key, true);
    if (out !== null) return out;
    out = translateComposite(key);
    if (out !== null) {
      cache.set(key, out);
      return out;
    }
    recordMiss(key);
    return null;
  }

  var HAS_LATIN = /[A-Za-z]/;

  function localizeTextNode(node) {
    var value = node.nodeValue;
    if (!value || value.length > 400) return;
    var m = /^(\s*)([\s\S]*?)(\s*)$/.exec(value);
    if (!m) return;
    var key = m[2];
    if (!key || key.length > 160) return;
    // Text without Latin letters is already localized (or user content); translating it
    // again would both fail and pollute the untranslated list.
    if (!HAS_LATIN.test(key)) return;
    var t = translate(key);
    if (t !== null && t !== key) node.nodeValue = m[1] + t + m[3];
  }

  function setTranslatedAttribute(el, name, value) {
    var key = value.trim();
    if (!key || key.length > 160) return;
    if (!HAS_LATIN.test(key)) return;
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
      var parent = node.parentElement;
      if (!parent || isSkipped(parent)) continue;
      if (!node.nodeValue || node.nodeValue.length > 12) continue;
      // A whitespace-only node plus its neighbour is formatting, not a composed label.
      if (!node.nodeValue.trim()) continue;

      // React renders `{count} files` as two text nodes separated by a `<!-- -->`
      // comment. Skip comments (and other non-text/element nodes) to find the tail.
      var sibling = node.nextSibling;
      while (sibling && sibling.nodeType !== 3 && sibling.nodeType !== 1) {
        sibling = sibling.nextSibling;
      }
      if (!sibling) continue;

      var tail = '';
      var tailNode = null;
      if (sibling.nodeType === 3) {
        tail = sibling.nodeValue;
        tailNode = sibling;
      } else if (sibling.childNodes.length === 1 &&
                 sibling.firstChild.nodeType === 3) {
        tail = sibling.firstChild.nodeValue;
        tailNode = sibling.firstChild;
      }
      if (!tail) continue;

      var joined = (node.nodeValue + tail).trim();
      if (joined.length > 160 || !HAS_LATIN.test(joined)) continue;
      var t = translate(joined);
      if (t === null) continue;
      var lead = /^\s*/.exec(node.nodeValue)[0];
      node.nodeValue = lead + t;
      tailNode.nodeValue = '';
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
        if (!isSkipped(m.target.parentElement)) localizeTextNode(m.target);
      } else if (m.type === 'attributes') {
        if (!isSkipped(m.target)) localizeAttrs(m.target);
      }
    }
    badgeTimer = badgeTimer || setTimeout(function () {
      badgeTimer = null;
      if (typeof updateBadge === 'function') updateBadge();
    }, 500);
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
    setTimeout(function () { walk(document.body); updateBadge(); }, 300);
    setTimeout(function () { walk(document.body); updateBadge(); }, 1000);
    setTimeout(function () { walk(document.body); updateBadge(); }, 2500);
    setTimeout(function () { walk(document.body); updateBadge(); }, 6000);

    window.__COPILOT_L10N_MISSES__ = function () {
      return Array.from(misses).sort();
    };
    window.__COPILOT_L10N_COPY__ = copyMisses;

    /* Reporting gaps without DevTools.
     *
     * Ctrl+Alt+L copies every string that had no translation. The chord is matched on
     * `event.code` first because Windows turns Ctrl+Alt+<letter> into AltGr, which
     * rewrites `event.key` (sometimes to an accented character or "Unidentified").
     *
     * A small badge also appears in the corner whenever there are untranslated strings,
     * so the gaps can be copied with a click when the chord is swallowed by the host.
     */
    var BADGE_ID = 'copilot-l10n-gaps';

    function onShortcut(event) {
      if (!event.ctrlKey || !event.altKey || event.metaKey || event.shiftKey) return;
      var code = (event.code || '').toLowerCase();
      var key = (event.key || '').toLowerCase();
      var isL = code === 'keyl' || key === 'l';
      var isU = code === 'keyu' || key === 'u';
      if (!isL && !isU) return;
      event.preventDefault();
      event.stopPropagation();
      if (event.stopImmediatePropagation) event.stopImmediatePropagation();
      if (isU) {
        walk(document.body);
        if (typeof updateBadge === 'function') updateBadge();
        toast('已重新扫描当前页面');
      } else {
        copyMisses();
      }
    }

    function toast(message) {
      var notice = document.createElement('div');
      notice.textContent = message;
      notice.setAttribute('data-l10n-skip', '');
      notice.style.cssText = 'position:fixed;z-index:2147483647;bottom:16px;right:16px;' +
        'padding:8px 14px;border-radius:6px;background:#1f6feb;color:#fff;' +
        'font:13px/1.4 system-ui,sans-serif;box-shadow:0 4px 16px rgba(0,0,0,.3)';
      document.body.appendChild(notice);
      setTimeout(function () { notice.remove(); }, 3000);
    }

    function fallbackCopy(text) {
      var area = document.createElement('textarea');
      area.value = text;
      area.setAttribute('data-l10n-skip', '');
      area.style.cssText = 'position:fixed;top:-1000px;left:-1000px;';
      document.body.appendChild(area);
      area.select();
      try { document.execCommand('copy'); } catch (e) { /* ignore */ }
      area.remove();
    }

    function copyMisses() {
      var list = Array.from(misses).sort();
      var text = list.join('\n');
      var done = function () {
        toast(list.length
          ? '已复制 ' + list.length + ' 条未翻译文案'
          : '当前页面没有发现未翻译的英文');
      };
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(done, function () { fallbackCopy(text); done(); });
      } else {
        fallbackCopy(text);
        done();
      }
    }

    updateBadge = function () {
      var badge = document.getElementById(BADGE_ID);      if (!misses.size) {
        if (badge) badge.remove();
        return;
      }
      if (!badge) {
        badge = document.createElement('button');
        badge.id = BADGE_ID;
        badge.setAttribute('data-l10n-skip', '');
        badge.type = 'button';
        badge.style.cssText = 'position:fixed;right:10px;bottom:10px;z-index:2147483646;' +
          'min-width:26px;height:26px;padding:0 7px;border:0;border-radius:13px;' +
          'background:rgba(31,111,235,.82);color:#fff;font:11px/26px system-ui,sans-serif;' +
          'cursor:pointer;box-shadow:0 2px 8px rgba(0,0,0,.28);opacity:.75';
        badge.addEventListener('click', function (event) {
          event.preventDefault();
          event.stopPropagation();
          copyMisses();
        });
        document.body.appendChild(badge);
      }
      badge.textContent = '译' + misses.size;
      badge.title = '点击复制 ' + misses.size + ' 条未翻译文案';
    }

    window.addEventListener('keydown', onShortcut, true);
    document.addEventListener('keydown', onShortcut, true);
    window.addEventListener('keyup', onShortcut, true);

    updateBadge();

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
