# Assembles the four slides into one printable HTML page (one 1920x1080 page per slide).
import re
ORDER = ['cover', 'proof', 'offer', 'close']
BLOBS = {'/_blob/af240f03c7ffaed6b9c9c2a36c9da1bb': 'assets/unit.png',
         '/_blob/ee6d2444e0998b128d79c50ff5f42782': 'assets/pilot.png',
         '/_blob/0c5cb596b8f9d4c05e1e73aee9edc6aa': 'assets/logo.png'}
HEAD = '''<!doctype html><html lang="he"><head><meta charset="utf-8"><title>NAKITO · מצגת לדיסקונט</title><style>
@font-face{font-family:'Noto Sans Hebrew';src:url(fonts/NotoSansHebrew-hebrew-100_900.woff2) format('woff2');font-weight:100 900;font-stretch:62.5% 100%;unicode-range:U+0307-0308,U+0590-05FF,U+200C-2010,U+20AA,U+25CC,U+FB1D-FB4F}
@font-face{font-family:'Noto Sans Hebrew';src:url(fonts/NotoSansHebrew-latin-100_900.woff2) format('woff2');font-weight:100 900;font-stretch:62.5% 100%;unicode-range:U+0000-00FF,U+0131,U+0152-0153,U+02BB-02BC,U+02C6,U+02DA,U+02DC,U+0304,U+0308,U+0329,U+2000-206F,U+20AC,U+2122,U+2191,U+2193,U+2212,U+2215,U+FEFF,U+FFFD}
@font-face{font-family:'JetBrains Mono';src:url(fonts/JetBrainsMono-latin-400.woff2) format('woff2');font-weight:100 800}
@page{size:1920px 1080px;margin:0}
*{margin:0;padding:0;box-sizing:border-box}
html,body{background:#07090C}
section{position:relative;width:1920px;height:1080px;overflow:hidden;break-after:page;-webkit-print-color-adjust:exact;print-color-adjust:exact}
section>*{flex-shrink:0}
h1,h2,h3,p{margin:0}
aside{display:none}
a{text-decoration:underline;text-underline-offset:6px}
[style*="background-clip:text"]{-webkit-background-clip:text}
</style></head><body>
'''
out = HEAD
for sid in ORDER:
    s = open(f'slides/{sid}.html', encoding='utf-8').read()
    for k, v in BLOBS.items(): s = s.replace(k, v)
    out += s + '\n'
out += '</body></html>'
open('deck.html', 'w', encoding='utf-8').write(out)
print('deck.html written')
