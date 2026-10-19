/* verify_strings.js - run the built payload against a list of real UI strings.
 *
 * Loads build/zh-cn.payload.js in jsdom, renders every input string as a text node,
 * and reports which ones the engine leaves in English. This validates a payload
 * without touching the installed app.
 *
 *   node tools/verify_strings.js build/ui-live.txt
 *   node tools/verify_strings.js build/ui-strings.txt --col2
 */
const fs = require('fs');
const path = require('path');
const { JSDOM } = require('jsdom');

const ROOT = path.join(__dirname, '..');
const payload = fs.readFileSync(path.join(ROOT, 'build', 'zh-cn.payload.js'), 'utf8');

const file = process.argv[2];
if (!file) {
  console.error('usage: node tools/verify_strings.js <strings-file> [--col2]');
  process.exit(2);
}
const useSecondColumn = process.argv.includes('--col2');

const strings = fs.readFileSync(file, 'utf8')
  .split('\n')
  .map((line) => {
    if (!line.trim()) return '';
    const parts = line.split('\t');
    return (useSecondColumn ? parts[1] : parts[parts.length - 1] || '').trim();
  })
  .filter(Boolean);

const unique = [...new Set(strings)];
const dom = new JSDOM('<!DOCTYPE html><html><body></body></html>',
  { runScripts: 'outside-only', pretendToBeVisual: true });
const { window } = dom;
window.navigator.clipboard = { writeText: () => Promise.resolve() };

// Render all strings as separate spans so each can be inspected individually.
const body = window.document.body;
const nodes = unique.map((text) => {
  const span = window.document.createElement('span');
  span.textContent = text;
  body.appendChild(span);
  // Separate siblings so merging logic does not join unrelated labels.
  body.appendChild(window.document.createElement('br'));
  return span;
});

window.eval(payload);

window.document.addEventListener('DOMContentLoaded', () => {
  setTimeout(() => {
    const stillEnglish = [];
    nodes.forEach((node, i) => {
      const before = unique[i];
      const after = node.textContent;
      if (after === before && /[A-Za-z]{2}/.test(before)) {
        stillEnglish.push(before);
      }
    });

    console.log(`checked ${unique.length} strings`);
    console.log(`translated: ${unique.length - stillEnglish.length}`);
    console.log(`still English: ${stillEnglish.length}\n`);
    for (const s of stillEnglish.slice(0, 80)) console.log('  ' + s);
    if (stillEnglish.length > 80) {
      console.log(`  ... ${stillEnglish.length - 80} more`);
    }
    process.exit(0);
  }, 400);
});
