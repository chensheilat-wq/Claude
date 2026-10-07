// Exports deck.html to a PDF that looks the same in every viewer (iOS Quick Look, WhatsApp, Acrobat):
// each slide is baked to a 2x image (metallic text and glows included), and every <a> is re-laid
// on top as a real link area, so links stay clickable.
import { chromium } from '/opt/node-tools/node_modules/playwright/index.mjs';
import { writeFileSync, mkdirSync } from 'fs';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 2 });
await p.goto('http://127.0.0.1:8766/deck.html', { waitUntil: 'networkidle' });
await p.evaluate(async () => { await document.fonts.ready; });
mkdirSync('build', { recursive: true });
const secs = await p.$$('section');
let pages = '';
for (let i = 0; i < secs.length; i++) {
  const img = `build/slide${i + 1}.jpg`;
  await secs[i].screenshot({ path: img, type: 'jpeg', quality: 92 });
  if (process.argv[2]) await secs[i].screenshot({ path: `${process.argv[2]}_${i + 1}.png` });
  const links = await secs[i].evaluate(sec => {
    const o = sec.getBoundingClientRect();
    return [...sec.querySelectorAll('a')].map(a => { const r = a.getBoundingClientRect();
      return { href: a.href, x: r.left - o.left - 8, y: r.top - o.top - 8, w: r.width + 16, h: r.height + 16 }; });
  });
  pages += `<div class="pg"><img src="${img}">` + links.map(l =>
    `<a href="${l.href}" style="left:${l.x}px;top:${l.y}px;width:${l.w}px;height:${l.h}px"></a>`).join('') + '</div>\n';
}
writeFileSync('flat.html', `<!doctype html><html><head><meta charset="utf-8"><style>
@page{size:1920px 1080px;margin:0}*{margin:0;padding:0}
.pg{position:relative;width:1920px;height:1080px;overflow:hidden;break-after:page}
.pg img{position:absolute;inset:0;width:1920px;height:1080px}
.pg a{position:absolute;display:block}</style></head><body>${pages}</body></html>`);
const q = await b.newPage({ viewport: { width: 1920, height: 1080 } });
await q.goto('http://127.0.0.1:8766/flat.html', { waitUntil: 'networkidle' });
await q.pdf({ path: 'NAKITO-Discount.pdf', width: '1920px', height: '1080px', printBackground: true, preferCSSPageSize: true });
await b.close(); console.log('pdf done');
