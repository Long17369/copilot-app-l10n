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
    <div class="untranslated">Totally unknown phrase here</div>
  </aside>
</body></html>`;

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
    check('unknown left alone', text('.untranslated'), 'Totally unknown phrase here');

    const badge = window.document.getElementById('copilot-l10n-gaps');
    check('gap badge present', !!badge, true);
    check('badge counts only real gaps', badge && badge.textContent, '译1');

    const misses = window.__COPILOT_L10N_MISSES__();
    check('no chinese in gap list', misses.some((s) => /[\u4e00-\u9fff]/.test(s)), false);
    check('gap list has the unknown string', misses.includes('Totally unknown phrase here'), true);

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
    for (const [ok, name, got, want] of results) {
      if (!ok) failed++;
      console.log(`${ok ? 'PASS' : 'FAIL'}  ${name}${ok ? '' : `  got=${JSON.stringify(got)} want=${JSON.stringify(want)}`}`);
    }
    console.log(`\n${results.length - failed}/${results.length} passed`);
    process.exit(failed ? 1 : 0);
  }, 120);
});
