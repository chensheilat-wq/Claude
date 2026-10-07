// Renders every 60fps frame in test mode (unique colour per word) and streams PNGs to check.py
import { chromium } from '/opt/node-tools/node_modules/playwright/index.mjs';
import { spawn } from 'child_process';
const py = spawn('python3', ['check.py'], { stdio: ['pipe', 'inherit', 'inherit'] });
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
await p.goto('http://127.0.0.1:8765/index.html?render=1&test=1');
await p.evaluate(() => window.ready);
const N = Math.round(await p.evaluate(() => DUR) * 60);
for (let n = 30; n < N; n++) {
  const meta = await p.evaluate(t => { seek(t); const s = shots.find(s => { const g = Math.floor(t / 0.5); return g >= s.g && g < s.g + s.n; }); return { entry: s.entry || s.kind, lt: t - s.g * 0.5 }; }, n / 60);
  const buf = await p.screenshot({ type: 'png' });
  const head = Buffer.from(JSON.stringify({ n, ...meta }) + '\n');
  const len = Buffer.alloc(8); len.writeUInt32LE(head.length, 0); len.writeUInt32LE(buf.length, 4);
  if (!py.stdin.write(Buffer.concat([len, head, buf]))) await new Promise(r => py.stdin.once('drain', r));
}
py.stdin.end(); await b.close();
await new Promise(r => py.on('close', r));
