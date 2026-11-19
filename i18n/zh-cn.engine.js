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

  var EXPECTED = __EXPECT__ || 1;
  var KEEP = __KEEP_JSON__;

  /* Dictionary shards are appended to several app chunks (the payload outgrew a single
   * chunk); each shard pushes its slice here, so collect them all at start time. */
  function collectDictionary() {
    var merged = {};
    var shards = window.__COPILOT_L10N_DICTS__ || [];
    for (var i = 0; i < shards.length; i++) {
      var shard = shards[i];
      if (!shard) continue;
      for (var key in shard) {
        if (Object.prototype.hasOwnProperty.call(shard, key)) merged[key] = shard[key];
      }
    }
    return merged;
  }

  var DICT = collectDictionary();

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
    [/^[,，]\s*preview$/i, '，预览'],
    /* Shortcut manager and other generated labels. */
    [/^Edit shortcut for\s+(.+)$/i, '编辑「$1」的快捷键'],
    [/^Assign shortcut for\s+(.+)$/i, '为「$1」分配快捷键'],
    /* Shortcut list rows render as "<keys>, edit shortcut for <command>". */
    [/^(.+?),\s*edit shortcut for\s+(.+)$/i, '$1，编辑「$2」的快捷键'],
    [/^edit shortcut for\s+(.+)$/i, '编辑「$1」的快捷键'],
    [/^Edit shortcut\b/i, '编辑快捷键'],
    [/^More actions for\s+(.+)$/i, '「$1」的更多操作'],
    [/^Assign…$/i, '分配…'],
    [/^without shortcut$/i, '无快捷键'],
    [/^(.+),\s*view details$/i, '「$1」，查看详情'],
    [/^(.+?),\s*edit$/i, '$1，编辑'],
    [/^(.+?),\s*delete$/i, '$1，删除'],
    [/^Background\s+(\d+)$/i, '后台 $1'],
    [/^Search\s+(\d+)\s+skills?$/i, '搜索 $1 个 Skill'],
    [/^Enable:\s*(.+)$/i, '启用：$1'],
    [/^Filter by type:\s*(.+)$/i, '按类型筛选：$1'],
    [/^Add server:\s*(.+)$/i, '添加服务器：$1'],
    [/^(\d+)\s+actions?$/i, '$1 个操作'],
    [/^(\d+)\s+shortcuts?$/i, '$1 个快捷键'],
    [/^Install:\s*(.+)$/i, '安装：$1'],
    [/^Failed to browse marketplace\s*"(.+)"$/i, '浏览市场「$1」失败'],
    [/^MCP Servers\s*·\s*(.+)$/i, 'MCP 服务器 · $1'],
    [/^(.*?)\.\s*Status:\s*(Idle|Working|Busy|Running|Paused|Queued|Failed|Done)\.?$/i,
      '$1。状态：$2'],
    [/^Status:\s*(Idle|Working|Busy|Running|Paused|Queued|Failed|Done)$/i, '状态：$1'],
    [/^Models\s*\((\d+)\)$/i, '模型（$1）'],
    [/^Not installed\s*·\s*(.+)$/i, '未安装 · $1'],
    [/^Not installed\s*·\s*(\d+\s*MB)$/i, '未安装 · $1'],
    [/^Search\s+(\d+)\s+palettes…$/i, '搜索 $1 个配色…'],
    [/^Testing connection,\s*(.+)$/i, '正在测试连接：$1'],
    [/^Model provider status checked:\s*(\d+)\s+connected\.$/i,
      '模型提供方状态已检查：$1 个已连接。'],
    [/^(\d+)%\s+quota used$/i, '已用配额 $1%'],
    [/^Last\s+(\d+)\s+days$/i, '最近 $1 天'],
    [/^(\d+)\s+days$/i, '$1 天'],
    [/^\(resets monthly\)$/i, '（每月重置）'],
    [/^Edit\s+([\w.\-]+)$/, '编辑 $1'],
    [/^Remove\s+([a-z0-9][\w.\-]*)$/i, '移除 $1'],
    [/^Download\s+([a-z0-9][\w.\-]*)$/i, '下载 $1'],
    [/^Cycle agent modes with\s*(.+)$/i, '用 $1 切换 Agent 模式'],
    [/^Cycle agent modes with$/i, '切换 Agent 模式：'],
    [/^Add model by ID$/i, '按 ID 添加模型']
  ];

  var ATTRS = [
    'placeholder',
    'data-placeholder',
    'title',
    'aria-label',
    'aria-description',
    'aria-placeholder',
    'aria-roledescription',
    'data-tooltip',
    'data-tooltip-content',
    'alt'
  ];
  var SKIP_SEL = [
    'pre', 'code', 'kbd', 'samp', 'textarea', 'script', 'style',
    '[contenteditable="true"]',
    '.markdown-body', '.monaco-editor',
    '[data-l10n-skip]',
    /* Conversation *content* only. Class names are matched on the specific content
     * containers: a broad `[class*="message"]` also matches the composer toolbar
     * (`messageComposer`), which is UI chrome that must stay translatable. */
    '[role="log"]', '[role="article"]',
    '[class*="markdown"]', '[class*="Markdown"]', '[class*="prose"]',
    '[class*="transcript"]', '[class*="Transcript"]',
    '[class*="messageBody"]', '[class*="message-body"]',
    '[class*="messageContent"]', '[class*="message-content"]',
    '[class*="userMessage"]', '[class*="assistantMessage"]',
    '[data-testid*="message-body"]', '[data-testid*="messageBody"]',
    '[data-testid*="message-content"]', '[data-testid*="transcript"]',
    '[data-testid*="tool-call"]',
    /* Code surfaces: diffs, editors and highlighted snippets are content. They are
     * usually spans/divs, not <pre>/<code>, so they need explicit selectors. */
    '[class*="diff"]', '[class*="Diff"]',
    '[class*="syntax"]', '[class*="highlight"]', '[class*="prism"]',
    '[class*="monaco"]', '[class*="editor-"]', '[class*="Editor-"]',
    '[data-language]', '[class*="blob-"]', '[class*="line-number"]'
  ].join(',');

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
    /^(cd|git|npm|node|python|pip|gh|npx|yarn|pnpm)\s/,  // shell commands
    /[\\/][\w.-]+[\\/]/,                                // anything with a path inside
    /[`{}<>]|=>|::/,                                    // code punctuation
    /^[·•]\s*[\w.-]+$/,                                 // "· github.com" style suffix
    /^(Ubuntu|Debian|Fedora|CentOS|Rocky|Alpine|Arch|openSUSE|Kali|WSL)([\s\d.\-]*)$/i,
    /^[A-Za-z][\w+.-]*-[0-9][\w.-]*$/,                  // Ubuntu-20.04, model ids
    /^@[\w.-]+$/,                                        // @handle
    /^[\w.-]+\s+@[\w.-]+$/,                              // "name @handle"
    /^GitHub v[\d.]+$/,                                  // version stamp
    /^wsl:\/\//,                                         // wsl://Ubuntu-24.04
    /^%\w+%$/,                                           // %username% placeholder
    /^(Ubuntu|docker-desktop)$/i,
    /^MCP Servers\s*·\s/,                                // third-party catalog blurb
    /^[a-z0-9][\w.-]*(\/[\w.-]+)?$/                       // bare identifiers
  ];

  function isNoise(text) {
    for (var i = 0; i < MISS_NOISE.length; i++) {
      if (MISS_NOISE[i].test(text)) return true;
    }
    return false;
  }

  function recordMiss(key) {
    var probe = key.trim();
    if (!probe || probe.length < 2) return;
    // Only sentence- or label-shaped strings matter; bare fragments are layout noise.
    // Session/chat titles are user content and usually start lowercase, so requiring an
    // initial capital keeps them out of the report.
    if (!/^[A-Z]/.test(probe) && !/^(e\.g\.|i\.e\.)/i.test(probe)) return;
    // Already localized, or user/agent content that merely contains Latin text.
    if (HAS_CJK.test(probe)) return;
    if (probe.length > 400) return;
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
    if (key.length > 140) return null;
    var pieces = key.split(/(,\s+|\.\s+|;\s+)/);
    if (pieces.length < 3) return null;

    // A real label list is short; a sentence that merely contains commas is not. If any
    // part is long, treat the whole string as prose and leave it alone.
    var parts = pieces.filter(function (_, i) { return i % 2 === 0; });
    for (var p = 0; p < parts.length; p++) {
      if (parts[p].trim().split(/\s+/).length > 5) return null;
    }

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
      // Only treat a part as translatable when it looks like a label: at least two
      // words, or a capitalised single word. Otherwise common lowercase words inside a
      // sentence ("test", "and deploy ...") get swapped for their dictionary entry.
      var wordCount = probe.split(/\s+/).length;
      if (wordCount < 2 && !/^[A-Z]/.test(probe)) {
        out += core;
        continue;
      }
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
  var HAS_CJK = /[\u4e00-\u9fff]/;

  /* Anything rendered in a monospace family is code or a code diff, never UI copy.
   * This catches code views whose markup is plain divs/spans instead of <pre>/<code>. */
  var monoCache = null;
  var MONO_FONT = /mono|consolas|cascadia|menlo|courier|lucida console|source code|fira code|jetbrains/i;

  function isMonospace(el) {
    if (!monoCache) {
      monoCache = typeof WeakMap === 'function' ? new WeakMap() : null;
    }
    var cur = el;
    var depth = 0;
    while (cur && cur.nodeType === 1 && depth < 8) {
      if (monoCache) {
        var cached = monoCache.get(cur);
        if (cached === true) return true;
      }
      var mono = false;
      try {
        var family = window.getComputedStyle(cur).fontFamily || '';
        mono = MONO_FONT.test(family);
      } catch (e) { /* ignore */ }
      if (monoCache) monoCache.set(cur, mono);
      if (mono) return true;
      if (cur === document.body) break;
      cur = cur.parentElement;
      depth++;
    }
    return false;
  }

  /* Code never gets translated, whatever container it is in. Kept deliberately narrow:
   * a stray ";" appears in ordinary prose ("Research preview; experimental behavior
   * may change."), so only real syntax markers count. Monospace detection is the
   * primary defence; this is only a safety net. */
  var CODE_LIKE = new RegExp([
    '\\$\\{',            // template interpolation
    '=>',                // arrow function
    '`',                 // template literal
    '[{}]',              // block/object braces
    '^\\s*//',           // line comment
    '^\\s*#\\s',         // shell comment
    '\\b(?:function|const|let|var|return|import|export)\\s+[\\w$]',
    '\\w+\\([^)]*\\)\\s*;\\s*$'  // statement call ending in ;
  ].join('|'));

  var MAX_TEXT = 900;
  var MAX_KEY = 480;

  function localizeTextNode(node) {
    var value = node.nodeValue;
    if (!value || value.length > MAX_TEXT) return;
    var m = /^(\s*)([\s\S]*?)(\s*)$/.exec(value);
    if (!m) return;
    var key = m[2];
    if (!key || key.length > MAX_KEY) return;
    // Text without Latin letters is already localized (or user content).
    if (!HAS_LATIN.test(key)) return;
    // Mixed CJK+Latin means this string was already localized (possibly composite).
    if (HAS_CJK.test(key)) return;
    if (CODE_LIKE.test(key)) return;
    var t = translate(key);
    if (t === null || t === key) return;
    var lead = m[1];
    var trail = m[3];
    // "计算机操作" + " 预览" leaves a stray ASCII space between two Chinese fragments;
    // Chinese typography has no such space, so drop it next to neighbouring CJK text.
    if (HAS_CJK.test(t)) {
      var prev = node.previousSibling;
      var prevText = prev ? (prev.nodeType === 3 ? prev.nodeValue : prev.textContent) : '';
      if (lead && prevText && HAS_CJK.test(prevText.replace(/\s+$/, '').slice(-1))) {
        lead = '';
      }
      var next = node.nextSibling;
      var nextText = next ? (next.nodeType === 3 ? next.nodeValue : next.textContent) : '';
      if (trail && nextText && HAS_CJK.test(nextText.replace(/^\s+/, '').charAt(0))) {
        trail = '';
      }
    }
    node.nodeValue = lead + t + trail;
  }

  function setTranslatedAttribute(el, name, value) {
    var key = value.trim();
    if (!key || key.length > MAX_KEY) return;
    if (!HAS_LATIN.test(key)) return;
    var t = translate(key);
    if (t !== null && t !== key) el.setAttribute(name, value.replace(key, t));
  }

  function localizeAttrs(el) {
    if (!el.getAttribute) return;
    if (isMonospace(el)) return;
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
  /* Find the next node that could carry the rest of a split label. React often renders
   * "Show the GitHub Copilot icon in the" and "system tray." in two sibling <span>s, so
   * the search has to leave the current element (up to two levels). */
  function nextCarrier(node) {
    var cur = node;
    for (var level = 0; level < 3 && cur; level++) {
      var sib = cur.nextSibling;
      while (sib && sib.nodeType !== 3 && sib.nodeType !== 1) sib = sib.nextSibling;
      if (sib) {
        if (sib.nodeType === 1 &&
            (sib.children.length > 1 || sib.childNodes.length > 1)) {
          return null;  // a container, not a fragment tail
        }
        return sib;
      }
      cur = cur.parentElement;
      if (!cur || cur === document.body || cur === document.documentElement) return null;
    }
    return null;
  }

  function localizeJoinedText(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var node;
    while ((node = walker.nextNode())) {
      var parent = node.parentElement;
      if (!parent || isSkipped(parent)) continue;
      if (isMonospace(parent)) continue;
      var value = node.nodeValue;
      if (!value || value.length > 200) continue;
      // A whitespace-only node plus its neighbour is formatting, not a composed label.
      if (!value.trim()) continue;
      // Only join when the first part is not a finished sentence: joining across
      // sentence boundaries would corrupt two independent labels.
      if (/[.!?。！？]\s*$/.test(value.trim())) continue;

      var sibling = nextCarrier(node);
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
      if (!tail || !tail.trim() || tail.trim().length > 80) continue;

      var rawJoin = value + tail;
      // Fragments split across elements often lose the separating space:
      // "…icon in the" + "system tray." must join with one space.
      if (!/\s$/.test(value) && !/^\s/.test(tail)) rawJoin = value + ' ' + tail;
      var joined = rawJoin.trim();
      if (joined.length > 200 || !HAS_LATIN.test(joined)) continue;

      // Dictionary keys are stored without the trailing sentence punctuation that the
      // rendered label carries, so look up the bare form and re-apply the punctuation.
      var core = joined.replace(/[.!?。！？]+\s*$/, '');
      var punct = joined.slice(core.length).trim();
      // Quiet lookup: a partial join that is not a known label is not a gap.
      var t = lookup(core, true);
      if (t === null) t = translateComposite(joined);
      if (t === null) t = translateComposite(core);
      if (t === null) continue;
      if (punct) {
        var map = { '.': '。', '!': '！', '?': '？' };
        t = t.replace(/[。！？]$/, '') + (map[punct.charAt(0)] || '');
      }
      var lead = /^\s*/.exec(value)[0];
      node.nodeValue = lead + t;
      tailNode.nodeValue = '';
    }
  }

  /* Chinese typography has no space between two CJK fragments, but the source English
   * often separates them ("Computer Use" + " preview", or a bare " or " between two
   * links). Strip ASCII spaces that end up between two Chinese runs. */
  function normalizeCjkSpacing(root) {
    var walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, null);
    var node;
    var prevChar = '';
    while ((node = walker.nextNode())) {
      var value = node.nodeValue;
      if (!value) continue;
      if (!value.trim()) { continue; }

      var first = value.trim().charAt(0);
      var last = value.trim().slice(-1);
      var changed = value;

      // Leading space after Chinese
      if (prevChar && HAS_CJK.test(prevChar) && HAS_CJK.test(first)) {
        changed = changed.replace(/^\s+/, '');
      }
      // Trailing space before Chinese
      var next = node.nextSibling;
      var nextText = '';
      while (next && !nextText) {
        if (next.nodeType === 3) nextText = next.nodeValue;
        else if (next.nodeType === 1) nextText = next.textContent;
        if (!nextText || !nextText.trim()) {
          next = next.nextSibling;
          nextText = '';
        }
      }
      if (HAS_CJK.test(last) && nextText && HAS_CJK.test(nextText.trim().charAt(0))) {
        changed = changed.replace(/\s+$/, '');
      }

      if (changed !== value) node.nodeValue = changed;
      prevChar = node.nodeValue.trim().slice(-1);
    }
  }

  /* Sentences that contain inline code chips ("Add a [.worktreeinclude] file to the repo
   * root ...") arrive as several sibling nodes, so no single text node matches a
   * dictionary key. Build a template where each inline code element becomes MARK, look
   * that up, then distribute the translated segments back into the prose nodes while
   * leaving the code chips untouched. */
  var MARK = '\u0001';
  var INLINE_CODE = /^(CODE|KBD|SAMP)$/;

  function isInlineCode(el) {
    if (!el || el.nodeType !== 1) return false;
    if (INLINE_CODE.test(el.tagName)) return true;
    var cls = (el.getAttribute && el.getAttribute('class')) || '';
    return /\bcode\b|-code\b|inline-code/i.test(cls);
  }

  /* Template keys are sensitive to spacing around the chip marker, and the app is not
   * consistent about it (sometimes the space belongs to the preceding node, sometimes
   * to the following one). Compare with spacing around the marker normalized away. */
  var NORM_TEMPLATES = null;

  function normTemplate(text) {
    return text.replace(/\s*\u0001\s*/g, MARK).replace(/\s+/g, ' ').trim();
  }

  function lookupTemplate(core) {
    if (NORM_TEMPLATES === null) {
      NORM_TEMPLATES = {};
      for (var key in DICT) {
        if (Object.prototype.hasOwnProperty.call(DICT, key) && key.indexOf(MARK) !== -1) {
          NORM_TEMPLATES[normTemplate(key)] = DICT[key];
        }
      }
    }
    var hit = NORM_TEMPLATES[normTemplate(core)];
    return hit === undefined ? null : hit;
  }

  function localizeInlineCodeSentence(el) {
    var kids = el.childNodes;
    if (!kids || kids.length < 3 || kids.length > 12) return false;

    var codes = 0;
    var template = '';
    var hasProse = false;
    for (var i = 0; i < kids.length; i++) {
      var kid = kids[i];
      if (kid.nodeType === 3) {
        template += kid.nodeValue;
        if (kid.nodeValue.trim()) hasProse = true;
      } else if (isInlineCode(kid)) {
        template += MARK;
        codes++;
      } else {
        return false;  // something more complex than prose + code chips
      }
    }
    if (!codes || !hasProse) return false;

    var lead = /^\s*/.exec(template)[0];
    var trail = /\s*$/.exec(template)[0];
    var core = template.slice(lead.length, template.length - trail.length);
    if (!core || core.length > 600) return false;

    var translated = lookup(core, true);
      if (translated === null) translated = lookupTemplate(core);
    if (translated === null) return false;

    var segments = translated.split(MARK);
    if (segments.length !== codes + 1) return false;

    // Hand the segments to the prose nodes in order; code chips stay in place.
    var next = lead;
    var seg = 0;
    var applied = false;
    for (var j = 0; j < kids.length; j++) {
      var node = kids[j];
      if (node.nodeType === 3) {
        if (node.nodeValue.trim()) {
          var before = /^\s*/.exec(node.nodeValue)[0];
          var after = /\s*$/.exec(node.nodeValue)[0];
          // Segments from the dictionary are delimited by the chip marker; the spacing
          // around the chip comes from the original node, so trim the segment itself.
          node.nodeValue = before + segments[seg].trim() + after;
          seg++;
          applied = true;
        }
      }
    }
    // Chinese text needs a space around a Latin code chip; the app relies on separate
    // whitespace nodes, which do not always survive the rewrite.
    ensureChipSpacing(el);
    return applied;
  }

  var CJK_PUNCT = /[\u3001\u3002\uff0c\uff1a\uff1b\uff01\uff1f]/;

  function ensureChipSpacing(el) {
    var kids = el.childNodes;
    for (var i = 0; i + 1 < kids.length; i++) {
      var a = kids[i];
      var b = kids[i + 1];
      if (a.nodeType === 3 && isInlineCode(b)) {
        var before = a.nodeValue.replace(/\s+$/, '');
        if (!before) continue;
        var lastChar = before.slice(-1);
        // Chinese punctuation already separates the chip ("后，/permissions").
        a.nodeValue = CJK_PUNCT.test(lastChar) ? before : before + ' ';
      } else if (isInlineCode(a) && b.nodeType === 3) {
        var after = b.nodeValue.replace(/^\s+/, '');
        if (!after) continue;
        var first = after.charAt(0);
        b.nodeValue = CJK_PUNCT.test(first) ? after : ' ' + after;
      }
    }
  }

  function hasInlineCodeChild(el) {
    var kids = el && el.childNodes;
    if (!kids) return false;
    for (var i = 0; i < kids.length; i++) {
      if (isInlineCode(kids[i])) return true;
    }
    return false;
  }

  /* Apply the template pass to every descendant that holds a code chip, before the
   * per-text-node pass can translate its fragments. */
  function localizeInlineCodeDescendants(root) {
    if (!root.querySelectorAll) return;
    var els = root.querySelectorAll('p,div,span,li,label,section,td');
    for (var i = 0; i < els.length; i++) {
      if (hasInlineCodeChild(els[i])) localizeInlineCodeSentence(els[i]);
    }
  }

  function walk(node) {
    if (!node) return;
    if (node.nodeType === 3) {
      localizeTextNode(node);
      return;
    }
    if (node.nodeType !== 1) return;
    if (isSkipped(node)) {
      // A skipped region is never translated, but form controls still deserve a
      // translated placeholder/aria-label (e.g. the instructions textarea).
      var tag = node.tagName;
      if (tag === 'TEXTAREA' || tag === 'INPUT' || tag === 'SELECT' ||
          node.isContentEditable ||
          (node.getAttribute && node.getAttribute('contenteditable') === 'true')) {
        localizeAttrs(node);
      }
      return;
    }
    // Code, diffs and editors are rendered in monospace: never touch them.
    if (isMonospace(node)) return;
    localizeAttrs(node);
    if (node.shadowRoot) walk(node.shadowRoot);
    // Inline-code sentences must be matched as a whole before the per-node pass splits
    // them further.
    localizeInlineCodeSentence(node);
    localizeInlineCodeDescendants(node);
    // Join fragments before the plain text pass, so a label split across two nodes is
    // translated as a whole and its fragments are never reported as gaps.
    localizeJoinedText(node);

    var walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        var parent = n.parentElement;
        if (!parent || isSkipped(parent)) return NodeFilter.FILTER_REJECT;
        if (isMonospace(parent)) return NodeFilter.FILTER_REJECT;
        // Text that belongs to an inline-code sentence is handled by the template pass
        // as a whole; translating fragments here would break the match.
        if (hasInlineCodeChild(parent)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      }
    });
    var text;
    while ((text = walker.nextNode())) localizeTextNode(text);

    var all = node.querySelectorAll ? node.querySelectorAll('*') : [];
    for (var i = 0; i < all.length; i++) {
      var el = all[i];
      if (isSkipped(el)) {
        // Skipped regions are never translated, but their editable controls still
        // deserve a translated placeholder/aria-label (the instructions editor is a
        // textarea or a contenteditable Lexical surface).
        var tag = el.tagName;
        if (tag === 'TEXTAREA' || tag === 'INPUT' || tag === 'SELECT' ||
            el.isContentEditable ||
            (el.getAttribute && el.getAttribute('contenteditable') === 'true')) {
          localizeAttrs(el);
        }
        continue;
      }
      localizeAttrs(el);
    }
    normalizeCjkSpacing(node);
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
    var shards = (window.__COPILOT_L10N_DICTS__ || []).length;
    if (shards < EXPECTED) {
      // Some shards live in chunks that are still loading; retry briefly, then start
      // anyway with whatever arrived so the UI is never blocked.
      var waited = 0;
      var timer = setInterval(function () {
        waited += 100;
        var now = (window.__COPILOT_L10N_DICTS__ || []).length;
        if (now >= EXPECTED || waited >= 3000) {
          clearInterval(timer);
          DICT = collectDictionary();
          start();
        }
      }, 100);
      return;
    }
    DICT = collectDictionary();
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
    window.__COPILOT_L10N_SCAN__ = function () {
      walk(document.body);
      updateBadge();
    };

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
