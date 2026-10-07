// 4 sub-frames per output frame spread over half a frame, piped to ffmpeg (no images on disk),
// blended with tmix and decimated back to 60fps.
import { chromium } from '/opt/node-tools/node_modules/playwright/index.mjs';
import { spawn } from 'child_process';
const FPS = 60, SUB = 4;
const ff = spawn('ffmpeg', ['-y', '-loglevel', 'error', '-f', 'image2pipe', '-framerate', String(FPS * SUB), '-i', '-', '-i', 'music.wav',
  '-vf', `tmix=frames=${SUB},select=eq(mod(n\\,${SUB})\\,${SUB - 1}),setpts=N/(${FPS}*TB)`,
  '-map', '0:v', '-map', '1:a', '-r', String(FPS), '-c:v', 'libx264', '-preset', 'slow', '-crf', '16', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart',
  'nakito-reel.mp4'], { stdio: ['pipe', 'inherit', 'inherit'] });
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1080, height: 1920 } });
await p.goto('http://127.0.0.1:8765/index.html?render=1');
await p.evaluate(() => window.ready);
const DUR = await p.evaluate(() => DUR);
const stage = await p.$('#stage');
for (let n = 0; n < DUR * FPS; n++) {
  for (let k = 0; k < SUB; k++) {
    const t = n / FPS + ((k - (SUB - 1) / 2) / SUB) * (0.5 / FPS);
    await p.evaluate(t => seek(t), t);
    const buf = await stage.screenshot({ type: 'jpeg', quality: 95 });
    if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r));
  }
  if (n % 120 === 0) console.log('frame', n);
}
ff.stdin.end(); await b.close();
await new Promise(r => ff.on('close', r));
console.log('done');
