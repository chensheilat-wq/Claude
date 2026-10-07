# Reads frames from check.mjs; each word is drawn in its own test colour on black.
# Checks: (1) no two words come within GAP px of each other, (2) all text stays in the IG Reels safe zone.
import sys, json, io
import numpy as np
from PIL import Image

COLS = {'w0': (255, 0, 0), 'w1': (0, 255, 0), 'w2': (0, 0, 255), 'w3': (255, 255, 0),
        'w4': (255, 0, 255), 'w5': (0, 255, 255), 'lbl': (255, 255, 255)}
GAP = 4  # dilation radius: words must stay >= 2*GAP px apart
names = list(COLS)
ref = np.array([COLS[k] for k in names], float)
ref_n = ref / np.linalg.norm(ref, axis=1, keepdims=True)

def safe_mask(h, w):
    m = np.zeros((h, w), bool)
    m[250:h - 350, 80:w - 80] = True
    m[960:, w - 140:] = False  # IG buttons, lower half
    return m
SAFE = safe_mask(1920, 1080)

def dilate(m, r):
    out = m.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            out |= np.roll(np.roll(m, dy, 0), dx, 1)
    return out

inp = sys.stdin.buffer
bad_touch, bad_safe, slide_out, frames = [], [], [], 0
while True:
    hdr = inp.read(8)
    if len(hdr) < 8: break
    hl, bl = int.from_bytes(hdr[:4], 'little'), int.from_bytes(hdr[4:], 'little')
    meta = json.loads(inp.read(hl)); img = np.asarray(Image.open(io.BytesIO(inp.read(bl))).convert('RGB'), float)
    frames += 1
    v = img.max(axis=2)
    on = v > 90
    nrm = img / np.maximum(np.linalg.norm(img, axis=2, keepdims=True), 1)
    cls = np.argmax(nrm @ ref_n.T, axis=2)
    masks = {k: on & (cls == i) for i, k in enumerate(names)}
    # (1) touching: dilated masks of different words must not overlap
    present = [k for k in names if masks[k].sum() > 30 and k != 'lbl']
    dil = {k: dilate(masks[k], GAP) for k in present + ['lbl']}
    for i, a in enumerate(present):
        for b in present[i + 1:] + ['lbl']:
            ov = (dil[a] & dil[b]).sum()
            if ov > 20: bad_touch.append((meta['n'], a, b, int(ov)))
    # (2) safe zone
    out = on & ~SAFE
    if out.sum() > 10:
        ys, xs = np.nonzero(out)
        rec = (meta['n'], meta['entry'], round(meta['lt'], 3), int(out.sum()), int(xs.min()), int(xs.max()), int(ys.min()), int(ys.max()))
        (slide_out if meta['entry'] == 'slide' and meta['lt'] < 0.25 else bad_safe).append(rec)

print(f'frames checked: {frames}')
print(f'touching violations: {len(bad_touch)}'); [print('  ', r) for r in bad_touch[:25]]
print(f'safe-zone violations: {len(bad_safe)}'); [print('  ', r) for r in bad_safe[:25]]
print(f'slide entries starting off-frame (allowed, first 0.25s): {len(slide_out)} frames')
