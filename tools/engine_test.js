/* Engine smoke test: loads the built payload into jsdom and checks translation,
 * the Ctrl+Alt+L handler (including AltGr-style event.key) and the gap badge.
 *
 *   cd build/enginetest && npm install jsdom
 *   node ../../tools/engine_test.js
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..');
const payloadPath = path.join(ROOT, 'build', 'zh-cn.payload.js');
const payload = fs.readFileSync(payloadPath, 'utf8');

const html = `<!DOCTYPE html><html lang="en"><body>
  <aside><a title="New session">New session</a>
    <span aria-label="Settings">Settings</span>
    <button>Cancel</button>
    <span><span>3</span><span> files</span></span>
    <span id="count">3<!-- --> files</span>
    <code>New session</code>
    <span id="skill">Skill</span>
    <span id="newissue">New issue</span>
    <span id="composite" title="1 hour ago, Response sent, show timestamp">1 hour ago, Response sent, show timestamp</span>
    <span id="composite2">New session, Ctrl + N. New chat, Ctrl + Shift + N.</span>
    <span id="pathnoise">__WINPATH__</span>
    <span id="frag1">Show the GitHub Copilot icon in the</span><span id="frag2">system tray.</span>
    <span id="sessiontitle">test model</span>
    <span id="distro">Ubuntu-20.04</span>
    <span id="shortcutlabel">Edit shortcut for New tab</span>
    <span id="palette">Catppuccin Mocha</span>
    <span id="models">Models (4)</span>
    <span id="quota">49% quota used</span>
    <span id="sentence">Build, test, and deploy hosted things on your own.</span>
    <span id="spaced"><span>计算机操作</span><span> 预览</span></span>
    <div class="untranslated">Totally unknown phrase here</div>
    <div role="log" aria-live="polite">
      <div class="markdown-body"><p>Copilot said: three issues fixed.</p></div>
      <span>Run engine tests and 14 other tool calls</span>
      <code>cd C:\work</code>
    </div>
    <div class="messageComposer__toolbar">
      <button id="stopbtn" aria-label="Stop, Escape">Stop</button>
      <button id="detailsbtn" aria-label="Response details, more info">Details</button>
      <span id="background2">Background 2</span>
      <span id="statusline">test model. Status: Working.</span>
    </div>
    <div id="codeview" style="font-family: monospace">
      <span id="codestr">Hi, </span>
      <span id="codelabel">Cancel</span>
    </div>
    <span id="prose-semicolon">Research preview; experimental behavior may change.</span>
    <textarea id="instr" placeholder="Always add tests for new code.">code text here</textarea>
    <div id="lexical" contenteditable="true" data-placeholder="Always add tests for new code.">typed content</div>
    <span id="orword"><a>Enable additional usage</a> or <a>upgrade plan</a> to continue after plan credits run out.</span>
    <p id="inlinecode">Add a <code>.worktreeinclude</code> file to the repo root to auto-copy gitignored files into new worktrees.</p>
  </aside>
</body></html>`.replace('__WINPATH__', String.raw`C:\Users\long1\copilot-l10n\README.md`);

const dom = new JSDOM(html, { runScripts: 'outside-only', pretendToBeVisual: true });
const { window } = dom;

let clip = null;
window.navigator.clipboard = { writeText: (t) => { clip = t; return Promise.resolve(); } };

const results = [];
function check(name, got, want) {
  results.push([got === want, name, got, want]);
}
const text = (sel) => window.document.querySelector(sel).textContent;

function keyEvent(props) {
  // jsdom drops `code` from KeyboardEvent init, so build a plain event and assign.
  const ev = new window.Event('keydown', { bubbles: true, cancelable: true });
  for (const [k, v] of Object.entries(props)) ev[k] = v;
  return ev;
}

window.eval(payload);

window.document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    check('text node', text('a'), '新建会话');
    check('attribute', window.document.querySelector('[title]').getAttribute('title'), '新建会话');
    check('aria-label', window.document.querySelector('[aria-label]').getAttribute('aria-label'), '设置');
    check('button', text('button'), '取消');
    check('count + noun (comment-separated nodes)',
          window.document.getElementById('count').textContent, '3 个文件');
    check('code block untouched', text('code'), 'New session');
    check('keep-english term untouched', text('#skill'), 'Skill');
    check('keep-english inside sentence', text('#newissue'), '新建 Issue');
    check('composite label', text('#composite'), '1 小时前，回复已发送，显示时间戳');
    check('composite with two separators', text('#composite2'),
          '新建会话，Ctrl + N。新建对话，Ctrl + Shift + N.');
    check('unknown left alone', text('.untranslated'), 'Totally unknown phrase here');

    // Conversation content must never be translated nor reported.
    const convo = window.document.querySelector('[role="log"]');
    check('transcript not translated', convo.querySelector('p').textContent,
          'Copilot said: three issues fixed.');
    check('tool title not reported',
          window.__COPILOT_L10N_MISSES__().some((s) => s.indexOf('tool calls') >= 0), false);
    check('transcript text not reported',
          window.__COPILOT_L10N_MISSES__().some((s) => s.indexOf('Copilot said') >= 0), false);

    // The composer toolbar lives in classes that merely contain "message"; it must
    // still be translated.
    check('composer stop label', window.document.getElementById('stopbtn').getAttribute('aria-label'),
          '停止，Esc');
    check('composer details label',
          window.document.getElementById('detailsbtn').getAttribute('aria-label'),
          '回复详情，更多信息');
    check('background count', text('#background2'), '后台 2');
    check('session status line', text('#statusline'), 'test model。状态：Working');

    // Monospace content is code: never translated, even when it matches a dict key.
    check('code string not translated', text('#codestr'), 'Hi, ');
    check('code label not translated', text('#codelabel'), 'Cancel');
    check('code content not reported',
          window.__COPILOT_L10N_MISSES__().some(
            (s) => s.startsWith('Hi,') || s === 'Cancel'), false);

    // A semicolon in ordinary prose must not make the string look like code.
    check('prose with semicolon translated', text('#prose-semicolon'),
          '研究预览，实验性行为可能变化。');
    // Textarea content stays untouched, but its placeholder is UI copy.
    check('textarea content untouched',
          window.document.getElementById('instr').value, 'code text here');
    check('textarea placeholder translated',
          window.document.getElementById('instr').getAttribute('placeholder'),
          '始终为新代码添加测试。');
    // The instructions editor may be a contenteditable Lexical surface.
    check('contenteditable placeholder translated',
          window.document.getElementById('lexical').getAttribute('data-placeholder'),
          '始终为新代码添加测试。');
    check('contenteditable content untouched',
          text('#lexical'), 'typed content');
    // A bare conjunction between two link nodes is a separator and must be localized.
    check('bare conjunction translated', text('#orword'),
          '启用额外用量或升级 plan 以在 plan 额度用尽后继续。');
    // A sentence interrupted by an inline code chip is matched as a whole template, and
    // the chip element itself must survive untouched.
    (function () {
      const p = window.document.getElementById('inlinecode');
      const code = p.querySelector('code');
      check('inline-code sentence translated', p.textContent,
            '在仓库根目录添加 .worktreeinclude 文件，即可把被 gitignore 的文件自动复制到新的工作树。');
      check('inline-code chip preserved', !!(code && code.textContent === '.worktreeinclude'), true);
    })();

    const badge = window.document.getElementById('copilot-l10n-gaps');
    check('gap badge present', !!badge, true);
    check('badge counts only real gaps', badge && badge.textContent, '译2');

    const misses = window.__COPILOT_L10N_MISSES__();
    check('no chinese in gap list', misses.some((s) => /[\u4e00-\u9fff]/.test(s)), false);
    check('gap list has the unknown string', misses.includes('Totally unknown phrase here'), true);
    check('keep-english term not reported', misses.includes('Skill'), false);
    check('path not reported as gap',
          misses.some((s) => s.indexOf('C:\\') === 0 || s.indexOf('copilot-l10n') >= 0), false);

    check('generated shortcut label', text('#shortcutlabel'), '编辑「New tab」的快捷键');
    check('palette name kept English', text('#palette'), 'Catppuccin Mocha');
    check('palette not reported', misses.includes('Catppuccin Mocha'), false);
    check('count rule with parentheses', text('#models'), '模型（4）');
    check('quota rule', text('#quota'), '已用配额 49%');
    // A lowercase single word inside a sentence must not be swapped for its dictionary
    // entry ("test" -> 测试), which produced "构建，test，and deploy ...".
    check('no partial word swaps in sentences', text('#sentence'),
          'Build, test, and deploy hosted things on your own.');
    check('no stray space between CJK fragments', text('#spaced'), '计算机操作预览');
    check('fragment joined across nodes', text('#frag1'),
          '在系统托盘中显示 GitHub Copilot 图标。');
    check('fragment tail cleared', text('#frag2'), '');
    check('fragment not reported',
          misses.some((s) => s.indexOf('Show the GitHub Copilot icon') === 0), false);
    check('model id kept', (function () {
      const probe = window.document.createElement('span');
      probe.textContent = 'Edit deepseek-v4.1-flash';
      window.document.body.appendChild(probe);
      window.__COPILOT_L10N_SCAN__ && window.__COPILOT_L10N_SCAN__();
      return probe.textContent;
    })(), '编辑 deepseek-v4.1-flash');
    check('session title not reported', misses.includes('test model'), false);
    check('distro name not reported', misses.includes('Ubuntu-20.04'), false);

    clip = null;
    const ev1 = keyEvent({ ctrlKey: true, altKey: true, key: 'Unidentified', code: 'KeyL' });
    window.dispatchEvent(ev1);
    check('shortcut fired (event.code)', clip !== null, true);
    check('shortcut payload', (clip || '').includes('Totally unknown phrase here'), true);
    check('shortcut prevented default', ev1.defaultPrevented, true);

    clip = null;
    window.dispatchEvent(keyEvent({ ctrlKey: true, altKey: false, key: 'l', code: 'KeyL' }));
    check('ctrl+l ignored', clip, null);

    clip = null;
    window.dispatchEvent(keyEvent({ ctrlKey: true, altKey: true, shiftKey: true, key: 'L', code: 'KeyL' }));
    check('ctrl+alt+shift+l ignored', clip, null);

    clip = null;
    window.dispatchEvent(keyEvent({ ctrlKey: true, altKey: true, key: 'l', code: '' }));
    check('shortcut fired (event.key fallback)', clip !== null, true);

    let failed = 0;
    if (results.some((r) => !r[0])) {
      console.log('misses for debugging:', JSON.stringify(misses, null, 2));
    }
    for (const [ok, name, got, want] of results) {
      if (!ok) failed++;
      console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : `  got=${JSON.stringify(got)} want=${JSON.stringify(want)}`}`);
    }
    console.log(`\n${results.length - failed}/${results.length} passed`);
    process.exit(failed ? 1 : 0);
  }, 120);
});
