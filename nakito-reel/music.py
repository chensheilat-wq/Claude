# Procedural, royalty-free track for the NAKITO reel.
# 120 BPM = one beat per 0.5 s grid, so every cut lands on a kick.
import numpy as np, wave, sys

SR, DUR, BEAT = 48000, 12.0, 0.5
N = int(SR * DUR)
t = np.arange(N) / SR
mix = np.zeros((N, 2))
rng = np.random.default_rng(7)

def add(sig, at, gain=1.0, pan=0.0):
    i = int(at * SR)
    if i >= N: return
    sig = sig[:N - i]
    l, r = np.cos((pan + 1) * np.pi / 4), np.sin((pan + 1) * np.pi / 4)
    mix[i:i + len(sig), 0] += sig * gain * l * 1.414
    mix[i:i + len(sig), 1] += sig * gain * r * 1.414

def env(n, a, d):
    x = np.arange(n) / SR
    return np.minimum(x / max(a, 1e-4), 1) * np.exp(-x / d)

def lowpass(x, fc):
    a = np.exp(-2 * np.pi * fc / SR); y = np.zeros_like(x); s = 0.0
    for i in range(len(x)): s = (1 - a) * x[i] + a * s; y[i] = s
    return y

def hz(m): return 440 * 2 ** ((m - 69) / 12)

def kick(g=1.0):
    n = int(0.45 * SR); x = np.arange(n) / SR
    f = 45 + 110 * np.exp(-x / 0.03)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x / 0.16) * g

def clap():
    n = int(0.25 * SR); x = np.arange(n) / SR
    nz = rng.standard_normal(n)
    e = sum(np.exp(-np.maximum(x - d, 0) / 0.012) * (x >= d) for d in (0, 0.011, 0.022)) * 0.5 + np.exp(-x / 0.09) * 0.6
    return (nz - lowpass(nz, 900)) * e * 0.5

def hat(open_=False):
    n = int((0.18 if open_ else 0.05) * SR); nz = rng.standard_normal(n)
    return (nz - lowpass(nz, 7000)) * env(n, 0.001, 0.06 if open_ else 0.012) * 0.35

def bell(m):
    n = int(1.6 * SR); x = np.arange(n) / SR; f = hz(m)
    return sum(a * np.sin(2 * np.pi * f * k * x) * np.exp(-x / d) for k, a, d in ((1, 1, .9), (2.76, .45, .35), (5.4, .25, .15), (8.9, .12, .07))) * 0.25

def saw(f, n):
    x = np.arange(n) / SR; ph = (f * x) % 1
    return 2 * ph - 1

# chords per 2 s bar (F minor, glossy): Fm9 - Dbmaj7 - Abmaj7 - Eb(add9) - Fm9 - Db...
prog = [[53, 56, 60, 63, 67], [49, 53, 56, 60, 63], [56, 60, 63, 67, 70], [51, 55, 58, 62, 65], [53, 56, 60, 63, 67], [49, 53, 56, 60, 65]]
bass = [29, 25, 32, 27, 29, 25]

# ---- intro riser 0 - 0.5 s
n = int(0.5 * SR); x = np.arange(n) / SR; nz = rng.standard_normal(n)
riser = (nz - lowpass(nz, 2000)) * (x / 0.5) ** 2 * 0.35 + np.sin(2 * np.pi * np.cumsum(300 + 1500 * (x / 0.5) ** 2) / SR) * (x / 0.5) ** 3 * 0.12
add(riser, 0.0, 1.0)

# ---- drums 0.5 - 11.5
beats = np.arange(0.5, 11.51, BEAT)
for b in beats:
    end = b >= 9.5
    add(kick(0.75 if end else 1.0), b, 0.9)
    k = int(round(b / BEAT))
    if k % 2 == 0 and not end: add(clap(), b, 0.55, 0.1)
    if not end:
        add(hat(), b + 0.25, 0.5, -0.3)
        add(hat(), b + 0.125, 0.18, 0.4); add(hat(), b + 0.375, 0.18, 0.4)
    if k % 4 == 3 and not end: add(hat(True), b + 0.25, 0.4, -0.2)

# ---- bass + pad with kick ducking
duck = np.ones(N)
for b in beats:
    i = int(b * SR); m = min(N - i, int(0.3 * SR)); x = np.arange(m) / SR
    duck[i:i + m] = np.minimum(duck[i:i + m], 1 - 0.75 * np.exp(-x / 0.08))
padbus = np.zeros(N); bassbus = np.zeros(N)
for bar in range(6):
    t0 = bar * 2.0; n = int(2.0 * SR) if bar < 5 else N - int(t0 * SR)
    seg = sum(saw(hz(m) * (1 + d), n) for m in prog[bar] for d in (-0.004, 0.004)) / 10
    e = np.minimum(np.arange(n) / SR / 0.05, 1) * (np.exp(-np.maximum(np.arange(n) / SR - 1.0, 0) / 1.2) if bar == 5 else 1)
    padbus[int(t0 * SR):int(t0 * SR) + n] += seg * e
    for s in np.arange(t0 + 0.5 if bar == 0 else t0, min(t0 + 2.0, 9.5), 0.25):   # 8th-note bass pulses
        m = int(0.22 * SR); bl = saw(hz(bass[bar]), m) * 0.6 + np.sin(2 * np.pi * hz(bass[bar] - 12) * np.arange(m) / SR)
        bassbus[int(s * SR):int(s * SR) + m] += bl[:max(0, N - int(s * SR))] * env(m, 0.003, 0.12)[:max(0, N - int(s * SR))]
# filter opens through the track
pad = lowpass(padbus, 900) * 0.6 + lowpass(padbus, 3500) * np.clip((t - 2) / 8, 0, 1) * 0.35
mix[:, 0] += pad * duck * 0.5; mix[:, 1] += pad * duck * 0.5
bl = lowpass(bassbus, 400) * duck
mix[:, 0] += bl * 0.45; mix[:, 1] += bl * 0.45

# ---- hits synced to picture
for at in (0.57, 3.57, 7.07, 8.57):                      # slams: sub boom + noise crack
    n = int(0.7 * SR); x = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-x / 0.05)) / SR) * np.exp(-x / 0.35)
    nz = rng.standard_normal(n); crack = (nz - lowpass(nz, 3000)) * np.exp(-x / 0.05) * 0.4
    add(boom + crack, at - 0.02, 0.8)
for at in (2.0, 5.5, 8.0):                          # whooshes on slide-ins
    n = int(0.3 * SR); x = np.arange(n) / SR; nz = rng.standard_normal(n)
    add((nz - lowpass(nz, 1500)) * np.sin(np.pi * x / 0.3) ** 2 * 0.3, at - 0.05, 0.8, 0.6)
n = int(0.12 * SR); x = np.arange(n) / SR                   # LOCKED click
add((np.sin(2 * np.pi * 2400 * x) * 0.5 + rng.standard_normal(n) * 0.3) * np.exp(-x / 0.015), 5.0, 0.7)
for at, m in ((2.8, 84), (6.3, 87), (10.0, 89), (11.5, 96)):  # sparkle bells on the dot
    add(bell(m), at, 0.9, 0.2); add(bell(m + 7), at + 0.06, 0.4, -0.3)

# ---- master: fade tail, soft clip, normalize
fade = np.clip((DUR - t) / 0.6, 0, 1)
mix *= fade[:, None]
mix = np.tanh(mix * 0.9)
mix /= np.abs(mix).max() / 0.89
pcm = (mix * 32767).astype('<i2')
with wave.open(sys.argv[1] if len(sys.argv) > 1 else 'music.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(pcm.tobytes())
print('ok')
