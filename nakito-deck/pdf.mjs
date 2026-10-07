// Prints deck.html to a PDF with real, clickable links.
import { chromium } from '/opt/node-tools/node_modules/playwright/index.mjs';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1920, height: 1080 } });
await p.goto('http://127.0.0.1:8766/deck.html', { waitUntil: 'networkidle' });
await p.evaluate(async () => { await document.fonts.ready; });
if (process.argv[2]) { // preview PNGs
  const secs = await p.$$('section');
  for (let i = 0; i < secs.length; i++) await secs[i].screenshot({ path: `${process.argv[2]}_${i + 1}.png` });
}
await p.pdf({ path: 'NAKITO-Discount.pdf', width: '1920px', height: '1080px', printBackground: true, preferCSSPageSize: true });
await b.close(); console.log('pdf done');
