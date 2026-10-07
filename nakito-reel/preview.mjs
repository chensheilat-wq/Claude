import { chromium } from '/opt/node-tools/node_modules/playwright/index.mjs';
const times = process.argv.slice(3).map(Number);
const out = process.argv[2];
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
await p.goto('http://127.0.0.1:8765/index.html?render=1' + (process.env.TEST ? '&test=1' : ''));
await p.evaluate(() => window.ready);
const fontsOk = await p.evaluate(() => document.fonts.check('900 100px NSH', 'אבג') && [...document.fonts].filter(f=>f.status==='loaded').length);
console.log('fonts loaded:', fontsOk);
let i = 0;
for (const t of times) { await p.evaluate(t => seek(t), t); await p.screenshot({ path: `${out}_${String(i++).padStart(2,'0')}.png` }); }
await b.close();
