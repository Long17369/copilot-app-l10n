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
    <div class="untranslated">Totally unknown phrase here</div>
    <div class="conversation-pane">
      <p>Copilot said: three issues fixed.</p>
      <span>Run engine tests and 14 other tool calls</span>
      <code>cd C:\work</code>
    </div>
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
    const convo = window.document.querySelector('.conversation-pane');
    check('transcript not translated', convo.querySelector('p').textContent,
          'Copilot said: three issues fixed.');
    check('tool title not reported',
          window.__COPILOT_L10N_MISSES__().some((s) => s.indexOf('tool calls') >= 0), false);
    check('transcript text not reported',
          window.__COPILOT_L10N_MISSES__().some((s) => s.indexOf('Copilot said') >= 0), false);

    const badge = window.document.getElementById('copilot-l10n-gaps');
    check('gap badge present', !!badge, true);
    check('badge counts only real gaps', badge && badge.textContent, '译1');

    const misses = window.__COPILOT_L10N_MISSES__();
    check('no chinese in gap list', misses.some((s) => /[\u4e00-\u9fff]/.test(s)), false);
    check('gap list has the unknown string', misses.includes('Totally unknown phrase here'), true);
    check('keep-english term not reported', misses.includes('Skill'), false);
    check('path not reported as gap',
          misses.some((s) => s.indexOf('C:\\') === 0 || s.indexOf('copilot-l10n') >= 0), false);

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
