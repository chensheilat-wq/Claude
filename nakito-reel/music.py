# Procedural, royalty-free track for the NAKITO reel (16 s).
# 120 BPM = one beat per 0.5 s grid, so every cut lands on a kick.
import numpy as np, wave, sys

SR, DUR, BEAT = 48000, 16.0, 0.5
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

def hp(x, fc): return x - lowpass(x, fc)
def hz(m): return 440 * 2 ** ((m - 69) / 12)
def noise(sec): return rng.standard_normal(int(sec * SR))

def kick(g=1.0):
    n = int(0.45 * SR); x = np.arange(n) / SR
    f = 45 + 110 * np.exp(-x / 0.03)
    return np.sin(2 * np.pi * np.cumsum(f) / SR) * np.exp(-x / 0.16) * g

def clap():
    n = int(0.25 * SR); x = np.arange(n) / SR; nz = rng.standard_normal(n)
    e = sum(np.exp(-np.maximum(x - d, 0) / 0.012) * (x >= d) for d in (0, 0.011, 0.022)) * 0.5 + np.exp(-x / 0.09) * 0.6
    return hp(nz, 900) * e * 0.5

def hat(open_=False):
    n = int((0.18 if open_ else 0.05) * SR); nz = rng.standard_normal(n)
    return hp(nz, 7000) * env(n, 0.001, 0.06 if open_ else 0.012) * 0.35

def bell(m):
    n = int(1.6 * SR); x = np.arange(n) / SR; f = hz(m)
    return sum(a * np.sin(2 * np.pi * f * k * x) * np.exp(-x / d) for k, a, d in ((1, 1, .9), (2.76, .45, .35), (5.4, .25, .15), (8.9, .12, .07))) * 0.25

def saw(f, n):
    x = np.arange(n) / SR; return 2 * ((f * x) % 1) - 1

# sections: full groove, sim (half-time), end (soft)
def section(b):
    if b < 3.5: return 'A'
    if b < 7.5: return 'SIM'
    if b < 13.5: return 'A'
    return 'END'

# ---- intro riser 0 - 0.5 s
n = int(0.5 * SR); x = np.arange(n) / SR
add(hp(noise(0.5), 2000) * (x / 0.5) ** 2 * 0.35 + np.sin(2 * np.pi * np.cumsum(300 + 1500 * (x / 0.5) ** 2) / SR) * (x / 0.5) ** 3 * 0.12, 0.0)

# ---- drums
beats = np.arange(0.5, DUR - 0.49, BEAT)
for b in beats:
    sec, k = section(b), int(round(b / BEAT))
    if sec == 'A':
        add(kick(), b, 0.9)
        if k % 2 == 0: add(clap(), b, 0.55, 0.1)
        add(hat(), b + 0.25, 0.5, -0.3); add(hat(), b + 0.125, 0.18, 0.4); add(hat(), b + 0.375, 0.18, 0.4)
        if k % 4 == 3: add(hat(True), b + 0.25, 0.4, -0.2)
    elif sec == 'SIM':
        add(kick(0.8), b, 0.75 if k % 2 == 1 else 0.35)
        add(hat(), b + 0.25, 0.25, -0.3)
    else:
        add(kick(0.7), b, 0.7)

# ---- bass + pad with kick ducking (F minor, glossy)
prog = [[53, 56, 60, 63, 67], [49, 53, 56, 60, 63], [56, 60, 63, 67, 70], [51, 55, 58, 62, 65]]
bass = [29, 25, 32, 27]
duck = np.ones(N)
for b in beats:
    i = int(b * SR); m = min(N - i, int(0.3 * SR)); x = np.arange(m) / SR
    duck[i:i + m] = np.minimum(duck[i:i + m], 1 - 0.7 * np.exp(-x / 0.08))
padbus = np.zeros(N); bassbus = np.zeros(N)
for bar in range(8):
    t0 = bar * 2.0; n = int(2.0 * SR) if bar < 7 else N - int(t0 * SR)
    ch = prog[bar % 4] if bar < 7 else prog[0]
    seg = sum(saw(hz(m) * (1 + d), n) for m in ch for d in (-0.004, 0.004)) / 10
    e = np.minimum(np.arange(n) / SR / 0.05, 1) * (np.exp(-np.maximum(np.arange(n) / SR - 1.0, 0) / 1.2) if bar == 7 else 1)
    padbus[int(t0 * SR):int(t0 * SR) + n] += seg * e
    for s in np.arange(max(t0, 0.5), t0 + 2.0, 0.25):
        if section(s) not in ('A',) and not (section(s) == 'SIM' and int(s * 4) % 4 == 0): continue
        m = int(0.22 * SR); i = int(s * SR); L = max(0, min(m, N - i))
        bl = saw(hz(bass[bar % 4]), m) * 0.6 + np.sin(2 * np.pi * hz(bass[bar % 4] - 12) * np.arange(m) / SR)
        bassbus[i:i + L] += (bl * env(m, 0.003, 0.12))[:L]
open_ = np.clip((t - 1.5) / 2, 0, 1) * (1 - 0.7 * ((t > 3.5) & (t < 7.0))) + 0.7 * np.clip((t - 6.5) / 1.0, 0, 1) * ((t > 6.5) & (t < 7.5))
pad = lowpass(padbus, 900) * 0.6 + lowpass(padbus, 3500) * np.clip(open_, 0, 1) * 0.35
mix += (pad * duck * 0.5)[:, None]
mix += (lowpass(bassbus, 400) * duck * 0.45)[:, None]

# ---- hits synced to picture
for at in (0.57, 7.57, 11.07, 12.57):                     # slams: sub boom + crack
    n = int(0.7 * SR); x = np.arange(n) / SR
    boom = np.sin(2 * np.pi * np.cumsum(38 + 60 * np.exp(-x / 0.05)) / SR) * np.exp(-x / 0.35)
    add(boom + hp(noise(0.7), 3000) * np.exp(-x / 0.05) * 0.4, at - 0.02, 0.8)
for at in (2.0, 9.5, 12.0):                               # whooshes on slide-ins
    n = int(0.3 * SR); x = np.arange(n) / SR
    add(hp(noise(0.3), 1500) * np.sin(np.pi * x / 0.3) ** 2 * 0.3, at - 0.05, 0.8, 0.6)
n = int(0.12 * SR); x = np.arange(n) / SR                  # LOCKED click
add((np.sin(2 * np.pi * 2400 * x) * 0.5 + rng.standard_normal(n) * 0.3) * np.exp(-x / 0.015), 9.05, 0.7)
for at, m in ((2.8, 84), (10.3, 87), (14.0, 89), (15.0, 96)):   # sparkle bells on the dot / logo
    add(bell(m), at, 0.9, 0.2); add(bell(m + 7), at + 0.06, 0.4, -0.3)

# ---- simulation sound design (3.5 - 7.5 s)
S0 = 3.5
x = np.arange(int(0.15 * SR)) / SR                          # button blip
add(np.sin(2 * np.pi * 1320 * x) * np.exp(-x / 0.05) * 0.4 + np.sin(2 * np.pi * 1980 * x) * np.exp(-x / 0.03) * 0.2, S0 + 0.12, 0.8)
def motor(sec, f0, f1):                                     # shutter: filtered noise sweep + slat ticks
    n = int(sec * SR); x = np.arange(n) / SR; u = x / sec
    hum = np.sin(2 * np.pi * np.cumsum(f0 + (f1 - f0) * u) / SR) * 0.25
    tick = np.zeros(n); per = int(0.028 * SR)
    for j in range(0, n - 200, per): tick[j:j + 200] += np.exp(-np.arange(200) / 30) * 0.5
    return (hum + lowpass(noise(sec), 1800) * 0.6 + tick * 0.4) * np.sin(np.pi * u) ** 0.5
add(motor(0.45, 140, 90), S0 + 0.5, 0.5, -0.1)
add(motor(0.45, 90, 140), S0 + 3.0, 0.5, 0.1)
n = int(1.6 * SR); x = np.arange(n) / SR                    # water jets
spray = hp(noise(1.6), 2500) * (0.7 + 0.3 * np.sin(2 * np.pi * 9 * x)) * np.minimum(x / 0.08, 1) * np.minimum((1.6 - x) / 0.12, 1)
add(spray * 0.35, S0 + 1.0, 1.0, -0.2); add(hp(noise(1.6), 4000) * 0.15 * np.minimum(x / 0.08, 1) * np.minimum((1.6 - x) / 0.12, 1), S0 + 1.0, 1.0, 0.3)
n = int(0.55 * SR); x = np.arange(n) / SR                   # drying air
add(lowpass(noise(0.55), 900) * np.sin(np.pi * x / 0.55) * 0.9, S0 + 2.5, 0.8)
for j, at in enumerate((3.3, 3.42, 3.5, 3.58, 3.66)):       # ready sparkles
    add(bell(91 + (0, 3, 7, 10, 12)[j]), S0 + at, 0.35, (-0.5, 0.5, -0.2, 0.3, 0)[j])
n = int(0.5 * SR); x = np.arange(n) / SR                    # riser into the next slogan
add(hp(noise(0.5), 3000) * (x / 0.5) ** 2 * 0.3, 7.0, 1.0)

# ---- master: fade tail, soft clip, normalize
mix *= np.clip((DUR - t) / 0.7, 0, 1)[:, None]
mix = np.tanh(mix * 0.9)
mix /= np.abs(mix).max() / 0.89
with wave.open(sys.argv[1] if len(sys.argv) > 1 else 'music.wav', 'wb') as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes((mix * 32767).astype('<i2').tobytes())
print('ok')
