#!/usr/bin/env python3
"""Build the public DisplayCAL-CG pages (landing + technical guide, RO/EN/ES).

Static HTML, no external requests (system fonts, inline CSS/JS), images as WebP.
Usage:  build_site.py [--out DIR] [--assets-only]

The technical guide is generated from docs/guides/ (the very sources of the PDFs),
so the web and PDF guides cannot disagree. Page set and paths are in strings.PATHS.
Nothing here is published: the output is staged, then copied by the owner's decision.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(REPO, "docs", "guides"))
import strings as S  # noqa: E402

EXT = "/Volumes/CristiGordas/TESTE/GDC_PROJECTS/DisplayCAL-CG"
ASSETS = "assets/site"

# --------------------------------------------------------------------------- images


def prep_images(out_root: str) -> dict[str, tuple[int, int]]:
    """Convert the source captures to optimized WebP; returns name -> (w, h)."""
    from PIL import Image

    out = os.path.join(out_root, ASSETS)
    os.makedirs(out, exist_ok=True)
    sizes: dict[str, tuple[int, int]] = {}

    def save(src: str, name: str, width: int, quality: int = 80) -> None:
        if not os.path.isfile(src):
            return
        im = Image.open(src).convert("RGB")
        if im.width > width:
            im = im.resize((width, round(im.height * width / im.width)), Image.LANCZOS)
        im.save(os.path.join(out, name + ".webp"), "WEBP", quality=quality, method=6)
        sizes[name] = im.size

    ic = Image.open(f"{EXT}/icon/icon_B_1024.png").convert("RGBA")
    ic.resize((512, 512), Image.LANCZOS).save(os.path.join(out, "icon-b-512.webp"), "WEBP", quality=90, method=6)
    ic.resize((180, 180), Image.LANCZOS).save(os.path.join(out, "icon-b-180.png"), optimize=True)
    ic.resize((32, 32), Image.LANCZOS).save(os.path.join(out, "favicon-32.png"), optimize=True)
    sizes["icon-b-512"] = (512, 512)

    cap = f"{EXT}/site/captures"
    for lang in ("ro", "en", "es"):
        for theme in ("light", "dark"):
            base = f"{cap}/{lang}/{theme}"
            if not os.path.isdir(base):
                continue
            files = sorted(os.listdir(base))
            pick = {
                "flow1": "guide_1_monitor", "flow2": "guide_2_goal", "flow3": "guide_3_prepare",
                "flow4": "guide_4_measure", "flow5": "guide_5_finish", "adv": "adv_profiling_more",
                "rec": "dlg_recovery", "fin": "dlg_profile_finish", "diag": "dlg_diagnostic",
            }
            for key, frag in pick.items():
                hit = next((f for f in files if f.endswith(".png") and frag in f), None)
                if hit:
                    save(f"{base}/{hit}", f"{key}-{lang}-{theme}", 1100 if key.startswith(("flow", "adv")) else 760)
    save(f"{EXT}/design/render/hero_A_remaster.png", "hero-render", 1500, 82)
    for lang in ("ro", "en", "es"):
        for n in range(1, 6):
            save(f"{REPO}/docs/guides/img/{lang}/step{n}.png", f"gstep{n}-{lang}", 1100)
    fdir = os.path.join(out, "fonts"); os.makedirs(fdir, exist_ok=True)
    import shutil
    for fn in ("Archivo-VF.ttf", "B612Mono-Regular.ttf", "B612Mono-Bold.ttf"):
        shutil.copy(f"{EXT}/design/src/fonts/{fn}", os.path.join(fdir, fn))
    shutil.copy(f"{EXT}/design/FONTS_NOTICE.txt", os.path.join(fdir, "NOTICE.txt"))
    real = f"{EXT}/site/real"
    if os.path.isdir(real):
        for f in sorted(os.listdir(real)):
            if f.endswith(".png"):
                save(f"{real}/{f}", "real-" + f[:-4], 1300)
    return sizes


def prep_readme(out_root: str) -> None:
    """JPEG images for the READMEs (GitHub renders them anywhere)."""
    from PIL import Image

    out = os.path.join(out_root, "assets", "readme")
    os.makedirs(out, exist_ok=True)
    cap, real = f"{EXT}/site/captures", f"{EXT}/site/real"

    def first(*cands: str) -> str | None:
        return next((c for c in cands if c and os.path.isfile(c)), None)

    def demo(lang: str, frag: str) -> str | None:
        base = f"{cap}/{lang}/dark"
        if not os.path.isdir(base):
            return None
        hit = next((f for f in sorted(os.listdir(base)) if frag in f and f.endswith(".png")), None)
        return f"{base}/{hit}" if hit else None

    for lang in ("ro", "en", "es"):
        for name, srcs in (
            ("plan", (f"{real}/mac-plan-{lang}.png", f"{real}/mac-plan-ro.png" if lang == "ro" else None, demo(lang, "guide_4_measure"))),
            ("adv", (f"{real}/mac-adv-{lang}.png", demo(lang, "adv_profiling_more"))),
        ):
            src = first(*srcs)
            if not src:
                continue
            im = Image.open(src).convert("RGB")
            if im.width > 1100:
                im = im.resize((1100, round(im.height * 1100 / im.width)), Image.LANCZOS)
            im.save(os.path.join(out, f"{name}-{lang}.jpg"), "JPEG", quality=86, optimize=True, progressive=True)


# --------------------------------------------------------------------------- shared css / js

CSS = r"""
:root{color-scheme:dark light;--bg:#0d0e11;--bg2:#14161b;--surface:#191c22;--surface2:#20242b;--line:rgba(255,255,255,.10);--text:#eef0f4;--mut:#aab0bc;--ac:#ffb347;--ac2:#ff8a3d;--acink:#1b1205;--ok:#4cc38a;--warn:#ffb347;--markink:#06180f;--shadow:0 30px 70px -24px rgba(0,0,0,.75);--glow:radial-gradient(60% 50% at 78% 0%,rgba(255,150,40,.16),transparent 70%),radial-gradient(50% 40% at 0% 30%,rgba(90,140,255,.10),transparent 70%)}
@media (prefers-color-scheme:light){:root{--bg:#f6f3ee;--bg2:#efebe4;--surface:#ffffff;--surface2:#f4f0e9;--line:rgba(20,20,30,.12);--text:#17181c;--mut:#555a66;--ac:#8c4f00;--ac2:#a8420a;--acink:#ffffff;--ok:#18794e;--warn:#8c4f00;--markink:#ffffff;--shadow:0 26px 60px -26px rgba(40,30,10,.35);--glow:radial-gradient(60% 50% at 78% 0%,rgba(255,170,60,.22),transparent 70%),radial-gradient(50% 40% at 0% 30%,rgba(90,140,255,.10),transparent 70%)}}
*{box-sizing:border-box}html{scroll-behavior:smooth;-webkit-text-size-adjust:100%}
@media (prefers-reduced-motion:reduce){html{scroll-behavior:auto}*{animation-duration:.001ms!important;animation-iteration-count:1!important;transition-duration:.001ms!important}}
body{margin:0;background:var(--bg) var(--glow) no-repeat;color:var(--text);font:400 clamp(16px,1.05vw + 12px,18px)/1.6 -apple-system,BlinkMacSystemFont,"SF Pro Text","Segoe UI Variable Text","Segoe UI",system-ui,Roboto,"Helvetica Neue",Arial,sans-serif;-webkit-font-smoothing:antialiased}
a{color:var(--ac)}a:hover{text-decoration-thickness:2px}
:focus-visible{outline:3px solid var(--ac);outline-offset:3px;border-radius:6px}
.skip{position:absolute;left:12px;top:-60px;background:var(--ac);color:var(--acink);padding:10px 14px;border-radius:8px;font-weight:600;z-index:100}.skip:focus{top:12px}
.wrap{width:min(1180px,100% - 32px);margin-inline:auto}
header.top{position:sticky;top:0;z-index:50;background:color-mix(in srgb,var(--bg) 78%,transparent);backdrop-filter:saturate(1.4) blur(14px);-webkit-backdrop-filter:saturate(1.4) blur(14px)}
header.top:after{content:none}
.bar{display:flex;align-items:center;gap:14px;padding:10px 0}
.brand{display:flex;align-items:center;gap:10px;color:var(--text);text-decoration:none;font-weight:700;letter-spacing:-.01em}
.brand img{width:32px;height:32px;border-radius:8px}.brand b{color:var(--ac)}
nav.main{display:flex;gap:4px;margin-left:auto;align-items:center;flex-wrap:wrap}
nav.main a{color:var(--mut);text-decoration:none;padding:8px 10px;border-radius:8px;font-size:.92rem}
nav.main a:hover{color:var(--text);background:var(--surface)}
.langs{display:flex;gap:2px;margin-left:6px}.langs a{padding:6px 8px;border:1px solid var(--line);color:var(--mut);font-size:.82rem;text-decoration:none}
.langs a:first-child{border-radius:8px 0 0 8px}.langs a:last-child{border-radius:0 8px 8px 0}.langs a[aria-current=page]{background:var(--ac);color:var(--acink);border-color:var(--ac);font-weight:700}
@media(max-width:820px){nav.main a.hide-s{display:none}.bar{flex-wrap:wrap}}
.btn{display:inline-flex;align-items:center;gap:10px;padding:13px 20px;border-radius:12px;font-weight:700;text-decoration:none;color:var(--acink);background:linear-gradient(180deg,color-mix(in srgb,var(--ac) 92%,#fff),var(--ac) 46%,var(--ac2));box-shadow:inset 0 1px 0 rgba(255,255,255,.55),inset 0 -2px 0 rgba(0,0,0,.18),0 12px 28px -10px color-mix(in srgb,var(--ac2) 70%,transparent);border:0;cursor:pointer;font-size:1rem;letter-spacing:-.005em}
.btn:hover{filter:brightness(1.05);transform:translateY(-1px)}.btn:active{transform:none}
.btn.ghost{background:linear-gradient(180deg,var(--surface2),var(--surface));color:var(--text);box-shadow:inset 0 1px 0 rgba(255,255,255,.10),0 0 0 1px var(--line)}
.btn.small{padding:9px 14px;font-size:.92rem;border-radius:10px}
.hero{padding:clamp(34px,7vw,84px) 0 clamp(30px,5vw,60px)}
.hero .grid{display:grid;grid-template-columns:minmax(0,1.02fr) minmax(0,1fr);gap:clamp(24px,4vw,64px);align-items:center}
@media(max-width:940px){.hero .grid{grid-template-columns:1fr}}
.kicker{color:var(--ac);font-weight:700;font-size:.82rem;letter-spacing:.14em;text-transform:uppercase;margin:0 0 10px}
h1{font-size:clamp(2.2rem,5.2vw,4rem);line-height:1.04;letter-spacing:-.035em;margin:0 0 18px;font-weight:800;text-wrap:balance}
h1 .ac{background:linear-gradient(100deg,var(--ac),var(--ac2));-webkit-background-clip:text;background-clip:text;color:transparent}
h2{font-size:clamp(1.55rem,3vw,2.3rem);line-height:1.12;letter-spacing:-.025em;margin:0 0 12px;font-weight:750;text-wrap:balance}
h3{font-size:1.12rem;margin:0 0 6px;letter-spacing:-.01em}
.lead{font-size:clamp(1.05rem,1.4vw + .6rem,1.28rem);color:var(--mut);max-width:62ch;margin:0 0 24px}
.cta{display:flex;flex-wrap:wrap;gap:12px;margin:0 0 20px}
.facts{display:flex;flex-wrap:wrap;gap:6px 0;list-style:none;padding:0;margin:0 0 14px;color:var(--mut);font-size:.92rem}
.facts li+li:before{content:"·";margin:0 10px;color:var(--ac)}
.ver{color:var(--mut);font-size:.86rem;margin:0}
.stage{position:relative;border-radius:20px;padding:10px;background:linear-gradient(160deg,color-mix(in srgb,var(--surface2) 85%,#fff 6%),var(--surface));box-shadow:var(--shadow),inset 0 1px 0 rgba(255,255,255,.16),0 0 0 1px var(--line)}
.stage:before{content:"";position:absolute;inset:0;border-radius:20px;background:linear-gradient(115deg,rgba(255,255,255,.14),transparent 34%);pointer-events:none}
.stage img{display:block;width:100%;height:auto;border-radius:12px}
.stage figcaption,.cap{color:var(--mut);font-size:.86rem;margin:10px 4px 2px}
.stage .reflect{position:absolute;left:8%;right:8%;bottom:-26px;height:24px;background:radial-gradient(closest-side,rgba(255,150,40,.35),transparent);filter:blur(10px);opacity:.7;pointer-events:none}
.stage img.badge-icon{position:absolute;left:-18px;top:-22px;width:84px;height:84px;border-radius:22px;box-shadow:0 18px 36px -10px rgba(0,0,0,.6),0 0 0 1px var(--line);z-index:2}
@media(max-width:940px){.stage img.badge-icon{left:-6px;top:-18px;width:64px;height:64px}}
section.band{padding:clamp(36px,6vw,76px) 0}
section.alt{background:linear-gradient(180deg,transparent,color-mix(in srgb,var(--bg2) 80%,transparent) 14%,color-mix(in srgb,var(--bg2) 80%,transparent) 86%,transparent)}
.split{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1.15fr);gap:clamp(22px,4vw,56px);align-items:start}
.split.rev{grid-template-columns:minmax(0,1.15fr) minmax(0,1fr)}.split.rev>:first-child{order:2}
@media(max-width:900px){.split,.split.rev{grid-template-columns:1fr}.split.rev>:first-child{order:0}}
.three{display:grid;grid-template-columns:1.2fr 1fr;gap:clamp(20px,4vw,56px)}@media(max-width:820px){.three{grid-template-columns:1fr}}
.cols{columns:2 330px;column-gap:44px;max-width:none!important}.cols li{break-inside:avoid}.prose p{margin:0 0 14px;max-width:68ch}.prose ul{padding-left:1.15em;margin:0 0 14px;max-width:66ch}.prose li{margin:0 0 8px}
.note{border-left:3px solid var(--ac);padding:4px 0 4px 16px;margin:18px 0;color:var(--text);max-width:68ch}
.note strong{display:block;margin-bottom:2px}
.defs{display:grid;gap:14px;margin:0}.defs div{padding:12px 0 0;border-top:1px solid var(--line)}.defs dt{font-weight:700;margin:0 0 2px}.defs dd{margin:0;color:var(--mut);max-width:62ch}
/* flow demo */
.flow{display:grid;grid-template-columns:minmax(230px,300px) minmax(0,1fr);gap:clamp(16px,3vw,36px);align-items:start}
@media(max-width:900px){.flow{grid-template-columns:1fr}}
.rail{list-style:none;margin:0;padding:0;position:relative}
.rail:before{content:"";position:absolute;left:17px;top:14px;bottom:14px;width:2px;background:#16171a;opacity:.5}
.rail li{position:relative}
.rail button{all:unset;box-sizing:border-box;display:flex;gap:12px;align-items:flex-start;width:100%;padding:9px 8px 9px 0;cursor:pointer;color:var(--mut);border-radius:10px}
.rail .n{flex:none;width:36px;height:36px;border-radius:50%;display:grid;place-items:center;font-weight:800;background:var(--surface2);box-shadow:0 0 0 1px var(--line);color:var(--text);position:relative;z-index:1}
.rail button[aria-current=true] .n{background:linear-gradient(180deg,color-mix(in srgb,var(--ac) 92%,#fff),var(--ac2));color:var(--acink);box-shadow:0 8px 20px -8px var(--ac2)}
.rail button[aria-current=true]{color:var(--text)}.rail strong{display:block;color:var(--text);line-height:1.25;padding-top:7px}
.rail span.t{display:block;font-size:.9rem;line-height:1.45;margin-top:2px}
.js .rail span.t{display:none}.js .rail button[aria-current=true] span.t{display:block}
.ctrl{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0 0;align-items:center}
.ctrl .btn{padding:9px 14px;font-size:.9rem}
.progress{height:3px;background:var(--line);border-radius:3px;overflow:hidden;margin-top:12px}.progress i{display:block;height:100%;width:0;background:linear-gradient(90deg,var(--ac),var(--ac2))}
.shots{position:relative}.shot{display:none}.shot.on{display:block}
.nojs-list{display:grid;gap:22px;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr))}.js .nojs-list{display:none}.js .showall .nojs-list{display:grid}.js .showall .shots,.js .showall .rail,.js .showall .ctrl .only-one{display:none}
.js .showall .flow{display:block}
.static-step figcaption{font-weight:600;color:var(--text);margin:8px 0 2px}.static-step p{margin:0;color:var(--mut);font-size:.9rem}
.demo-tag{display:inline-block;font-size:.76rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:#fff;background:#c8461e;border-radius:6px;padding:2px 8px;margin-right:8px}
.real-tag{display:inline-block;font-size:.76rem;font-weight:800;letter-spacing:.06em;text-transform:uppercase;color:#fff;background:#18794e;border-radius:6px;padding:2px 8px;margin-right:8px}
/* placement */
.place{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(0,1fr);gap:clamp(20px,4vw,48px);align-items:center}@media(max-width:900px){.place{grid-template-columns:1fr}}
.place svg{width:100%;height:auto;border-radius:18px;background:linear-gradient(170deg,var(--surface2),var(--surface));box-shadow:0 0 0 1px var(--line),var(--shadow)}
.place ol{margin:0 0 6px;padding:0;list-style:none;counter-reset:s}.place li{counter-increment:s;display:flex;gap:12px;padding:10px 0;border-top:1px solid var(--line);color:var(--mut)}
.place li:before{content:counter(s);flex:none;width:28px;height:28px;border-radius:50%;display:grid;place-items:center;font-weight:800;font-size:.9rem;background:var(--surface2);color:var(--text);box-shadow:0 0 0 1px var(--line)}
.place li[aria-current=true]{color:var(--text)}.place li[aria-current=true]:before{background:var(--ac);color:var(--acink)}
.place li strong{display:block;color:var(--text)}
.sensor{transition:transform 1.1s cubic-bezier(.3,.8,.3,1)}
.s1 .sensor{transform:translate(70px,235px) rotate(-14deg)}.s2 .sensor{transform:translate(285px,150px) rotate(-3deg)}.s3 .sensor{transform:translate(318px,172px) rotate(0)}
.s1 .lens{animation:pulse 1.6s ease-in-out infinite}.s3 .target{animation:pulse 1.4s ease-in-out infinite}
@keyframes pulse{50%{opacity:.35}}
/* concepts pipeline */
.pipe{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:0;margin:26px 0 0;position:relative;list-style:none;padding:0}
.pipe:before{content:"";position:absolute;left:5%;right:5%;top:19px;height:2px;background:#16171a;opacity:.5}
.pipe li{position:relative;padding:0 14px 0 0}
.pipe .dot{width:40px;height:40px;border-radius:50%;display:grid;place-items:center;font-weight:800;background:var(--surface);box-shadow:0 0 0 2px var(--ac),0 8px 18px -8px var(--ac2);position:relative;z-index:1;margin-bottom:12px}
.pipe p{margin:0;color:var(--mut);font-size:.93rem}
@media(max-width:860px){.pipe{grid-template-columns:1fr;gap:18px}.pipe:before{left:19px;right:auto;top:10px;bottom:10px;width:2px;height:auto}.pipe li{padding:0 0 0 56px}.pipe .dot{position:absolute;left:0;top:0;margin:0}}
/* limits */
.lim{display:grid;grid-template-columns:1fr 1fr;gap:clamp(18px,4vw,48px)}@media(max-width:820px){.lim{grid-template-columns:1fr}}
.lim h3{display:flex;align-items:center;gap:8px}.lim ul{list-style:none;margin:10px 0 0;padding:0}.lim li{display:flex;gap:10px;padding:9px 0;border-top:1px solid var(--line);color:var(--mut)}
.lim .mk{flex:none;width:22px;height:22px;border-radius:50%;display:grid;place-items:center;font-weight:900;font-size:.8rem;margin-top:3px}
.lim .y .mk{background:var(--ok);color:var(--markink)}.lim .n .mk{background:var(--warn);color:var(--markink)}
.links{list-style:none;padding:0;margin:0}.links li{padding:7px 0;border-top:1px solid var(--line)}
.star{display:inline-flex;align-items:center;gap:10px;margin-top:6px}.star img{width:22px;height:22px;filter:none}
details.more{margin-top:10px}details.more summary{cursor:pointer;font-weight:700;color:var(--ac)}
footer{border-top:1px solid var(--line);margin-top:30px;padding:26px 0 40px;color:var(--mut);font-size:.9rem}
footer a{color:var(--mut)}footer .row{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:10px}
.cards2{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,420px),1fr));gap:22px;align-items:start}
/* guide */
.guide{display:grid;grid-template-columns:260px minmax(0,1fr);gap:clamp(20px,4vw,52px);padding:30px 0 40px}
@media(max-width:900px){.guide{grid-template-columns:1fr}}
.toc{position:sticky;top:78px;align-self:start;max-height:calc(100vh - 100px);overflow:auto;font-size:.92rem;padding-right:6px}
.toc h2{font-size:.8rem;letter-spacing:.14em;text-transform:uppercase;color:var(--ac);margin:0 0 8px}
.toc ol{list-style:none;margin:0;padding:0}.toc a{display:block;padding:6px 10px;border-left:2px solid var(--line);color:var(--mut);text-decoration:none}.toc a:hover{color:var(--text);border-color:var(--ac)}
@media(max-width:900px){.toc{position:static;max-height:none}.toc ol{columns:2}}
.guide>*{min-width:0}.toc a{overflow-wrap:anywhere}.guide article{overflow-wrap:anywhere}.guide article code{white-space:normal;overflow-wrap:anywhere}
@media(max-width:520px){.toc ol{columns:1}}
[id$="-h"],#top,#get{scroll-margin-top:92px}article section{padding:8px 0 22px;border-top:1px solid var(--line);margin-top:22px;scroll-margin-top:84px}article section:first-of-type{border-top:0;margin-top:0}
article h2{margin-top:14px}article h3{margin:22px 0 8px;font-size:1.15rem}
article p,article li{max-width:72ch}article ol.steps{padding-left:1.3em}article ol.steps li{margin:0 0 8px}
table.opt{border-collapse:collapse;width:100%;margin:14px 0;font-size:.95rem}table.opt th,table.opt td{border-top:1px solid var(--line);padding:9px 10px;text-align:left;vertical-align:top}table.opt th{color:var(--mut);font-weight:600}
.callout{border-radius:14px;padding:14px 16px;margin:16px 0;background:var(--surface);box-shadow:0 0 0 1px var(--line);max-width:74ch}
.callout.warn{box-shadow:0 0 0 1px color-mix(in srgb,var(--warn) 55%,transparent)}.callout.ok{box-shadow:0 0 0 1px color-mix(in srgb,var(--ok) 55%,transparent)}
.callout strong{display:block;margin-bottom:4px}.callout p{margin:0}
pre{overflow:auto;background:var(--surface);padding:12px 14px;border-radius:10px;box-shadow:0 0 0 1px var(--line)}

/* ===== Direcția A «Foaia de probă» ===== */
:root,:root{color-scheme:light;--bg:#f7f6f3;--bg2:#f1f0ec;--surface:#fbfbf9;--surface2:#f1f0ec;--line:rgba(29,31,36,.14);--text:#1d1f24;--mut:#5b5f68;--ac:#2c2f36;--ac2:#2c2f36;--acink:#f7f6f3;--ok:#0b7a45;--warn:#8a5b00;--markink:#fff;--shadow:0 18px 40px -22px rgba(29,31,36,.35);--glow:none;--sheet:#f7f6f3;--mono:"Archivo",system-ui,sans-serif}
html,body{background:var(--bg)}
body{background:var(--bg);font-family:"Archivo",system-ui,sans-serif}
header.top,main,footer{width:100%;background:transparent}
header.top{margin:0;position:sticky;top:0;background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(10px);-webkit-backdrop-filter:blur(10px);box-shadow:none}
header.top:after{content:"";display:block;height:2px;width:min(1180px,100% - 32px);margin:0 auto;background:linear-gradient(90deg,rgba(247,246,243,0),#2e3192 10%,#d4147a 28%,#e8312f 46%,#ffd400 62%,#00a651 80%,#00a3e0 92%,rgba(247,246,243,0))}
.bar{padding-block:12px}
.brand{font-family:"Archivo";font-weight:700;letter-spacing:-.01em}.brand b{color:var(--text)}.brand img{border-radius:8px}
nav.main a{font:600 14px/1 "Archivo";letter-spacing:0;text-transform:none;color:var(--mut);border-radius:999px;padding:10px 14px}
nav.main a:hover{background:rgba(29,31,36,.07);color:var(--text)}
.langs a{font:600 12px "Archivo";border-radius:999px!important;border:1px solid var(--line);color:var(--mut);padding:6px 10px}.langs a[aria-current=page]{background:var(--ac);color:var(--acink);border-color:var(--ac)}
.btn{border-radius:11px;font:600 15px/1 "Archivo";letter-spacing:0;text-transform:none;background:linear-gradient(#3b3e47,#2c2f36 55%,#24262c);color:#f7f6f3;box-shadow:0 1px 0 rgba(255,255,255,.14) inset,0 8px 16px -10px rgba(29,31,36,.7);padding:15px 24px;border:1px solid #1c1e23}
.btn:hover{filter:brightness(1.12);transform:none}
.btn.ghost{background:linear-gradient(#fff,#f1f0ec);color:var(--text);border:1px solid var(--line);box-shadow:0 1px 2px rgba(29,31,36,.08)}
.btn.ghost:hover{filter:none;border-color:rgba(29,31,36,.34)}
.kicker{display:none}
h1{font-family:"Archivo";font-weight:800;letter-spacing:-.03em;font-size:clamp(2.2rem,5vw,4.2rem);line-height:1}
h1 .ac{background:none;-webkit-text-fill-color:currentColor;color:var(--text)}
h2{font-family:"Archivo";font-weight:800;letter-spacing:-.02em}
.lead{color:var(--mut)}
.stage{border-radius:22px;padding:0;background:transparent;box-shadow:none}
.stage:before{display:none}
.stage img{border-radius:18px}
.stage .reflect{display:none}.stage img.badge-icon{display:none}
.stage figcaption,.cap{color:var(--mut)}
.ill-tag,.real-tag,.demo-tag{display:inline-block;font:600 12px/1 "Archivo";color:#fff;border-radius:999px;padding:5px 10px;margin-right:8px;vertical-align:1px}
.ill-tag{background:#2c2f36}.real-tag{background:#0b7a45}.demo-tag{background:#8a5b00}
.wcv{margin:26px 0;padding-top:14px;border-top:1px solid var(--line)}.wcv-fig{margin:14px 0}.wcv-fig img{width:100%;height:auto;display:block;border-radius:16px;box-shadow:var(--shadow)}.wcv-fig figcaption{font:400 .85rem/1.4 "Archivo";color:var(--mut);margin-top:8px}.wcv-cols{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:18px}.wcv-col h4{font:700 .95rem "Archivo";margin:0 0 6px;border-top:1px solid var(--line);padding-top:8px}.wcv-limit{border:1px solid var(--line);border-radius:14px;padding:10px 14px;background:var(--surface)}
section.alt{background:var(--bg2);border-block:0}
.note,.callout{border:1px solid var(--line);border-radius:16px;padding:14px 18px;background:var(--surface);box-shadow:none}
.rail:before,.pipe:before{background:var(--line);opacity:1}
.rail .n,.place li:before,.pipe .dot{border-radius:50%;background:var(--surface);color:var(--text);box-shadow:0 0 0 1px rgba(29,31,36,.3);font-family:"Archivo"}
.rail button[aria-current=true] .n,.place li[aria-current=true]:before{background:var(--ac);color:var(--acink);box-shadow:none}
.progress{background:var(--line);border-radius:999px}.progress i{background:var(--ac)}
.place svg{border-radius:18px;background:var(--surface);box-shadow:0 0 0 1px var(--line)}
.toc h2{color:var(--text);font-family:"Archivo"}.toc a{border-left-color:var(--line);color:var(--text)}
.toc a:hover{background:rgba(29,31,36,.06);border-color:var(--text)}
table.opt th{color:var(--text);font-family:"Archivo";font-size:.85rem}
table.opt th,table.opt td{border-color:var(--line)}
article section{border-color:var(--line)}
pre{border-radius:14px;box-shadow:0 0 0 1px var(--line);background:var(--surface)}
a{color:var(--text);text-decoration-thickness:1px;text-underline-offset:3px}
:focus-visible{outline:3px solid #2d5bd8;outline-offset:3px;border-radius:8px}
.lim .y .mk{background:var(--ok)}.lim .n .mk{background:var(--warn)}
.star .btn{box-shadow:none}
details.more summary{color:var(--text)}
"""

JS = r"""
(function(){
var d=document,h=d.documentElement;h.classList.add('js');
var reduce=window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches;
/* guided-flow demo */
var f=d.getElementById('flow');
if(f){var btns=[].slice.call(f.querySelectorAll('.rail button')),shots=[].slice.call(f.querySelectorAll('.shot')),pb=f.querySelector('.progress i'),
 play=d.getElementById('flow-play'),prev=d.getElementById('flow-prev'),next=d.getElementById('flow-next'),all=d.getElementById('flow-all'),live=d.getElementById('flow-live'),
 i=0,timer=null,playing=!reduce,T=5200;
 function show(n,say){i=(n+btns.length)%btns.length;btns.forEach(function(b,k){b.setAttribute('aria-current',k===i?'true':'false')});shots.forEach(function(s,k){s.classList.toggle('on',k===i)});
  if(say&&live){live.textContent=btns[i].querySelector('strong').textContent}
  if(pb){pb.style.transition='none';pb.style.width='0';if(playing&&!reduce){void pb.offsetWidth;pb.style.transition='width '+T+'ms linear';pb.style.width='100%'}}}
 function tick(){show(i+1,false)}
 function set(p){playing=p;clearInterval(timer);if(p){timer=setInterval(tick,T)}play.setAttribute('aria-pressed',p?'true':'false');play.textContent=p?play.dataset.pause:play.dataset.play;show(i,false)}
 btns.forEach(function(b,k){b.addEventListener('click',function(){set(false);show(k,true)})});
 prev.addEventListener('click',function(){set(false);show(i-1,true)});next.addEventListener('click',function(){set(false);show(i+1,true)});
 play.addEventListener('click',function(){set(!playing)});
 all.addEventListener('click',function(){var on=f.parentNode.classList.toggle('showall');all.setAttribute('aria-expanded',on?'true':'false');all.textContent=on?all.dataset.one:all.dataset.all;if(on)set(false)});
 f.addEventListener('mouseenter',function(){if(playing){clearInterval(timer)}});f.addEventListener('mouseleave',function(){if(playing){timer=setInterval(tick,T)}});
 f.addEventListener('focusin',function(){if(playing){clearInterval(timer)}});
 var seen=false;if('IntersectionObserver' in window){new IntersectionObserver(function(e){if(e[0].isIntersecting&&!seen){seen=true;set(!reduce)}else if(!e[0].isIntersecting){clearInterval(timer)}else if(playing){timer=setInterval(tick,T)}},{threshold:.35}).observe(f)}else{set(false)}
 show(0,false);play.textContent=reduce?play.dataset.play:play.dataset.pause;play.setAttribute('aria-pressed',reduce?'false':'true');
}
/* placement animation */
var p=d.getElementById('place');
if(p){var svg=p.querySelector('svg'),lis=[].slice.call(p.querySelectorAll('ol li')),pp=d.getElementById('place-play'),k=0,pt=null,pl=!reduce;
 function ps(n){k=(n+3)%3;svg.setAttribute('class','s'+(k+1));lis.forEach(function(l,j){l.setAttribute('aria-current',j===k?'true':'false')})}
 function pset(v){pl=v;clearInterval(pt);if(v){pt=setInterval(function(){ps(k+1)},3400)}pp.setAttribute('aria-pressed',v?'true':'false');pp.textContent=v?pp.dataset.pause:pp.dataset.play}
 lis.forEach(function(l,j){l.addEventListener('click',function(){pset(false);ps(j)})});
 pp.addEventListener('click',function(){pset(!pl)});ps(0);pset(pl);
 if('IntersectionObserver' in window){new IntersectionObserver(function(e){if(!e[0].isIntersecting){clearInterval(pt)}else if(pl){clearInterval(pt);pt=setInterval(function(){ps(k+1)},3400)}},{threshold:.2}).observe(p)}
}
})();
"""

PLACEMENT_SVG = """<svg id="place-svg" class="s1" viewBox="0 0 520 360" role="img" aria-labelledby="place-t"><title id="place-t">{label}</title>
<defs><linearGradient id="scr" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#2a2e38"/><stop offset="1" stop-color="#12141a"/></linearGradient><linearGradient id="gl" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#fff" stop-opacity=".55"/><stop offset="1" stop-color="#fff" stop-opacity="0"/></linearGradient><linearGradient id="sn" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#4a505c"/><stop offset="1" stop-color="#1b1e25"/></linearGradient></defs>
<g transform="translate(60,26)"><rect x="0" y="0" width="400" height="248" rx="16" fill="#0b0c10" stroke="#555b68" stroke-width="2"/><rect x="10" y="10" width="380" height="228" rx="8" fill="url(#scr)"/>
<rect x="10" y="10" width="380" height="80" rx="8" fill="url(#gl)" opacity=".12"/>
<g class="target" transform="translate(150,76)"><rect width="96" height="96" rx="6" fill="#fff" opacity=".92"/><rect x="2" y="2" width="92" height="92" rx="5" fill="none" stroke="#d4147a" stroke-width="3" stroke-dasharray="9 7"/></g>
<path d="M170 248 h60 l14 38 h-88 z" fill="#2a2e38" stroke="#555b68" stroke-width="2"/><rect x="120" y="286" width="160" height="10" rx="5" fill="#2a2e38" stroke="#555b68" stroke-width="2"/></g>
<g class="sensor"><g transform="translate(-52,-52)"><rect width="104" height="104" rx="18" fill="url(#sn)" stroke="#8a919f" stroke-width="2"/><circle class="lens" cx="52" cy="52" r="26" fill="#0b0c10" stroke="#d4147a" stroke-width="3"/><circle cx="52" cy="52" r="12" fill="#2a3b6b"/><circle cx="46" cy="46" r="4" fill="#fff" opacity=".7"/><rect x="20" y="4" width="64" height="9" rx="4.5" fill="#fff" opacity=".12"/></g></g></svg>"""

# --------------------------------------------------------------------------- helpers

E = html.escape


def rel(depth: int) -> str:
    return "../" * depth


def lang_links(lang: str, kind: str, depth: int) -> str:
    out = []
    for code in ("ro", "en", "es"):
        target = S.PATHS[code][kind]
        cur = ' aria-current="page"' if code == lang else ""
        out.append(f'<a href="{rel(depth)}{target}" hreflang="{code}" lang="{code}"{cur}>{code.upper()}</a>')
    return '<div class="langs" role="group" aria-label="Language">' + "".join(out) + "</div>"


def head(lang: str, kind: str, depth: int, title: str, desc: str, og_img: str) -> str:
    alts = "".join(
        f'<link rel="alternate" hreflang="{c}" href="{S.SITE}{S.PATHS[c][kind]}">' for c in ("ro", "en", "es")
    )
    canon = S.SITE + S.PATHS[lang][kind]
    r = rel(depth)
    ld = (
        '{"@context":"https://schema.org","@type":"SoftwareApplication","name":"DisplayCAL-CG",'
        '"applicationCategory":"MultimediaApplication","operatingSystem":"macOS, Windows",'
        f'"softwareVersion":"{S.VERSION}","license":"https://www.gnu.org/licenses/gpl-3.0.html",'
        '"offers":{"@type":"Offer","price":"0","priceCurrency":"EUR"},'
        f'"url":"{S.SITE}","codeRepository":"{S.REPO}","author":{{"@type":"Person","name":"Cristi Gordaș"}}}}'
    )
    return (
        f'<!doctype html><html lang="{S.L[lang]["html_lang"]}"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<title>{E(title)}</title><meta name=\"description\" content=\"{E(desc)}\">"
        f'<link rel="canonical" href="{canon}">{alts}<link rel="alternate" hreflang="x-default" href="{S.SITE}">'
        '<meta name="theme-color" content="#b3b5b8">'
        f'<link rel="icon" type="image/png" href="{r}{ASSETS}/favicon-32.png"><link rel="apple-touch-icon" href="{r}{ASSETS}/icon-b-180.png">'
        f'<meta property="og:type" content="website"><meta property="og:title" content="{E(title)}">'
        f'<meta property="og:description" content="{E(desc)}"><meta property="og:url" content="{canon}">'
        f'<meta property="og:image" content="{S.SITE}{ASSETS}/{og_img}.webp">'
        f"<style>@font-face{{font-family:Archivo;src:url({r}{ASSETS}/fonts/Archivo-VF.ttf);font-weight:100 900;font-stretch:62% 125%;font-display:swap}}"
        f"@font-face{{font-family:'B612 Mono';src:url({r}{ASSETS}/fonts/B612Mono-Regular.ttf);font-weight:400;font-display:swap}}"
        f"@font-face{{font-family:'B612 Mono';src:url({r}{ASSETS}/fonts/B612Mono-Bold.ttf);font-weight:700;font-display:swap}}</style>"
        f"<style>{CSS}</style><script type=\"application/ld+json\">{ld}</script></head>"
    )


def header(lang: str, kind: str, depth: int) -> str:
    t = S.L[lang]
    r = rel(depth)
    home = f"{r}{S.PATHS[lang]['home']}"
    guide = f"{r}{S.PATHS[lang]['guide']}"
    anchors = "" if kind == "guide" else (
        f'<a class="hide-s" href="#flow-h">{E(t["nav_flow"])}</a><a class="hide-s" href="#prep-h">{E(t["nav_prepare"])}</a>'
        f'<a class="hide-s" href="#plan-h">{E(t["nav_plan"])}</a><a class="hide-s" href="#limits-h">{E(t["nav_limits"])}</a>'
    )
    return (
        f'<a class="skip" href="#main">{E(t["skip"])}</a><header class="top"><div class="wrap bar">'
        f'<a class="brand" href="{home}"><img src="{r}{ASSETS}/icon-b-180.png" width="32" height="32" alt=""><span>Display<b>CAL-CG</b></span></a>'
        f'<nav class="main" aria-label="{E(t["nav_guide"])}">{anchors}<a href="{guide}">{E(t["nav_guide"])}</a>'
        f'<a href="{home}#get">{E(t["nav_get"])}</a>{lang_links(lang, kind if kind=="guide" else "home", depth)}</nav></div></header>'
    )


def footer(lang: str, depth: int) -> str:
    t = S.L[lang]
    return (
        f'<footer><div class="wrap"><div>© DisplayCAL-CG · GPLv3 · {S.VERSION} ({S.BUILD}) · Cristi Gordaș</div>'
        f'<div style="margin-top:6px">{E(t["foot_legal"])}</div><div class="row">'
        f'<a href="https://gordas.dev/termeni">{E(t["foot_terms"])}</a><a href="https://gordas.dev/confidentialitate">{E(t["foot_priv"])}</a>'
        f'<a href="https://gordas.dev/cookie">{E(t["foot_cookie"])}</a><a href="{S.REPO}">GitHub</a><a href="#top">{E(t["foot_up"])}</a></div></div></footer>'
    )


def pic(name: str, lang: str, depth: int, alt: str, sizes: dict, lazy: bool = True, light_dark: bool = True) -> str:
    """<picture> with a light and a dark variant; falls back to whichever exists."""
    r = rel(depth)
    d, l = f"{name}-{lang}-dark", f"{name}-{lang}-light"
    have_d, have_l = d in sizes, l in sizes
    if not (have_d or have_l):
        return ""
    base = d if have_d else l
    w, h = sizes[base]
    src = ""
    if have_d and have_l and light_dark:
        wl, hl = sizes[l]
        src = f'<source media="(prefers-color-scheme: light)" srcset="{r}{ASSETS}/{l}.webp" width="{wl}" height="{hl}">'
    ld = ' loading="lazy" decoding="async"' if lazy else ' fetchpriority="high"'
    return f'<picture>{src}<img src="{r}{ASSETS}/{base}.webp" width="{w}" height="{h}" alt="{E(alt)}"{ld}></picture>'


def single(name: str, depth: int, alt: str, sizes: dict, lazy: bool = True) -> str:
    if name not in sizes:
        return ""
    w, h = sizes[name]
    ld = ' loading="lazy" decoding="async"' if lazy else ' fetchpriority="high"'
    return f'<img src="{rel(depth)}{ASSETS}/{name}.webp" width="{w}" height="{h}" alt="{E(alt)}"{ld}>'


# --------------------------------------------------------------------------- landing


def landing(lang: str, sizes: dict) -> str:
    t = S.L[lang]
    depth = S.PATHS[lang]["home"].count("/")
    r = rel(depth)
    real_hero = f"real-mac-step1-{lang}"
    ill = {"ro": ("ILUSTRAȚIE", "Randare originală: sonda pe pătratul alb de măsurare, în timp ce aplicația rulează planul. Nu este o fotografie de produs și nu este un model anume de instrument; imaginea de pe ecran este captura reală a aplicației.", "Monitor cu sonda generică așezată pe pătratul alb de măsurare"),
           "en": ("ILLUSTRATION", "Original render: the probe on the white measurement square while the application runs the plan. It is not a product photo and not a specific instrument model; the picture on the screen is a real capture of the application.", "A monitor with a generic probe resting on the white measurement square"),
           "es": ("ILUSTRACIÓN", "Render original: la sonda sobre el cuadrado blanco de medición mientras la aplicación ejecuta el plan. No es una foto de producto ni un modelo concreto de instrumento; la imagen de la pantalla es una captura real de la aplicación.", "Un monitor con una sonda genérica sobre el cuadrado blanco de medición")}[lang]
    hero_img = single("hero-render", depth, ill[2], sizes, lazy=False) or pic("flow1", lang, depth, t["hero_alt"], sizes, lazy=False)
    tag_html = f'<span class="ill-tag">{ill[0]}</span>{E(ill[1])}'
    steps = t["flow_steps"]
    rail = "".join(
        f'<li><button type="button" aria-current="{"true" if k == 0 else "false"}"><span class="n">{k+1}</span>'
        f'<span><strong>{E(a)}</strong><span class="t">{E(b)}</span></span></button></li>'
        for k, (a, b) in enumerate(steps)
    )
    shots = "".join(
        f'<div class="shot{" on" if k == 0 else ""}">{pic(f"flow{k+1}", lang, depth, steps[k][0] + ": " + steps[k][1], sizes)}</div>'
        for k in range(5)
    )
    static = "".join(
        f'<figure class="static-step">{pic(f"flow{k+1}", lang, depth, steps[k][0], sizes)}'
        f'<figcaption>{k+1}. {E(steps[k][0])}</figcaption><p>{E(steps[k][1])}</p></figure>'
        for k in range(5)
    )
    prep = "".join(f"<li>{E(x)}</li>" for x in t["prep_list"])
    place_li = "".join(
        f'<li aria-current="{"true" if k == 0 else "false"}"><div><strong>{E(t["place_steps"][k])}</strong>{E(t["place_steps_text"][k])}</div></li>'
        for k in range(3)
    )
    pipe = "".join(
        f'<li><div class="dot">{k+1}</div><h3>{E(a)}</h3><p>{E(b)}</p></li>' for k, (a, b) in enumerate(t["concepts"])
    )
    plan_defs = "".join(f"<div><dt>{E(a)}</dt><dd>{E(b)}</dd></div>" for a, b in t["plan_points"])
    plan_img = single("real-mac-plan-ro", depth, t["plan_cap_real"], sizes) if lang == "ro" else ""
    plan_tag = "real"
    if not plan_img:
        plan_img = pic("flow4", lang, depth, t["plan_cap_est"], sizes)
        plan_tag = "demo"
    plan_cap = (f'<span class="real-tag">REAL</span>{E(t["plan_cap_real"])}' if plan_tag == "real"
                else f'<span class="demo-tag">DEMO</span>{E(t["plan_cap_est"])}')
    adv_real = f"real-mac-adv-{lang}"
    adv_img = single(adv_real, depth, t["adv_cap"], sizes) or pic("adv", lang, depth, t["adv_cap"], sizes)
    adv_tag = f'<span class="real-tag">REAL</span>' if adv_real in sizes else '<span class="demo-tag">DEMO</span>'
    mac_img = single(f"real-mac-step1-{lang}", depth, t["plat_mac"], sizes) or pic("flow1", lang, depth, t["plat_mac"], sizes)
    win_img = single("real-win-plan-en", depth, t["plat_win"], sizes) or single("real-win-step1-en", depth, t["plat_win"], sizes)
    rec_img = pic("rec", lang, depth, t["report_h"], sizes)
    fin_img = pic("fin", lang, depth, t["report_h"], sizes)
    ok = "".join(f'<li><span class="mk" aria-hidden="true">✓</span><span>{E(x)}</span></li>' for x in t["limits_ok"])
    no = "".join(f'<li><span class="mk" aria-hidden="true">–</span><span>{E(x)}</span></li>' for x in t["limits_no"])
    credits = "".join(f"<li>{E(x)}</li>" for x in t["credits"])
    links = "".join(f'<li><a href="{u}">{E(a)}</a></li>' for a, u in t["links"])
    pdf = f"{r}{S.PDF[lang]}"
    guide = f"{r}{S.PATHS[lang]['guide']}"
    body = f"""
<main id="main">
<section class="hero" id="top"><div class="wrap grid">
<div><p class="kicker">{E(t["kicker"])}</p><h1>{t["h1"]}</h1><p class="lead">{E(t["lead"])}</p>
<div class="cta" id="get"><a class="btn" href="{S.DMG}">{E(t["cta_mac"])}</a><a class="btn" href="{S.EXE}">{E(t["cta_win"])}</a><a class="btn ghost" href="{guide}">{E(t["cta_guide"])}</a></div>
<ul class="facts">{"".join(f"<li>{E(c)}</li>" for c in t["chips"])}</ul><p class="ver">{E(t["ver_line"].format(v=S.VERSION, b=S.BUILD))}</p></div>
<figure class="stage" style="margin:0"><img class="badge-icon" src="{r}{ASSETS}/icon-b-512.webp" width="84" height="84" alt="DisplayCAL-CG">{hero_img}<span class="reflect"></span><figcaption>{tag_html}</figcaption></figure>
</div></section>

<section class="band"><div class="wrap three prose"><div><h2>{E(t["what_h"])}</h2><p>{E(t["what_p"])}</p></div>
<div><h2 style="font-size:1.3rem">{E(t["need_h"])}</h2><p>{E(t["need_p"])}</p><p class="note">{E(t["need_note"])}</p></div></div></section>

<section class="band alt" aria-labelledby="flow-h"><div class="wrap"><h2 id="flow-h">{E(t["flow_h"])}</h2><p class="lead" style="margin-bottom:22px">{E(t["flow_lead"])}</p>
<div class="flowwrap"><div class="flow" id="flow" role="group" aria-label="{E(t["flow_label"])}">
<div><ol class="rail">{rail}</ol>
<div class="ctrl"><button class="btn small ghost" id="flow-prev" type="button">{E(t["flow_prev"])}</button><button class="btn small ghost" id="flow-next" type="button">{E(t["flow_next"])}</button>
<button class="btn small" id="flow-play" type="button" aria-pressed="false" data-play="{E(t["flow_play"])}" data-pause="{E(t["flow_pause"])}">{E(t["flow_pause"])}</button>
<button class="btn small ghost" id="flow-all" type="button" aria-expanded="false" data-all="{E(t["flow_all"])}" data-one="{E(t["flow_one"])}">{E(t["flow_all"])}</button></div><div class="progress" aria-hidden="true"><i></i></div></div>
<div class="shots stage" style="padding:8px">{shots}<p id="flow-live" class="sr" style="position:absolute;width:1px;height:1px;overflow:hidden" aria-live="polite"></p></div></div>
<div class="nojs-list">{static}</div></div>
<p class="cap"><span class="demo-tag">DEMO</span>{E(t["flow_demo"])}</p></div></section>

<section class="band" aria-labelledby="prep-h"><div class="wrap"><h2 id="prep-h">{E(t["prep_h"])}</h2><p class="lead" style="margin-bottom:22px">{E(t["prep_lead"])}</p>
<div class="prose" style="margin-bottom:34px"><ul class="cols">{prep}</ul></div>
<div id="place" class="place"><div>{PLACEMENT_SVG.replace("{label}", E(t["place_label"]))}
<div class="ctrl"><button class="btn small" id="place-play" type="button" aria-pressed="false" data-play="{E(t["place_play"])}" data-pause="{E(t["place_pause"])}">{E(t["place_pause"])}</button></div></div>
<div><h3>{E(t["place_h"])}</h3><ol>{place_li}</ol><p class="cap">{E(t["place_note"])}</p></div></div></div></section>

<section class="band alt" aria-labelledby="concepts-h"><div class="wrap"><h2 id="concepts-h">{E(t["concepts_h"])}</h2><p class="lead">{E(t["concepts_lead"])}</p><ol class="pipe">{pipe}</ol>
<div class="note" style="margin-top:28px"><strong>{E(t["macos_h"])}</strong>{E(t["macos_p"])}</div></div></section>

<section class="band" aria-labelledby="plan-h"><div class="wrap"><h2 id="plan-h">{E(t["plan_h"])}</h2><p class="lead" style="margin-bottom:22px">{E(t["plan_lead"])}</p>
<div class="split rev"><div class="stage" style="padding:8px"><figure style="margin:0">{plan_img}<figcaption>{plan_cap}</figcaption></figure></div>
<div><dl class="defs">{plan_defs}</dl></div></div>
<div class="split" style="margin-top:34px"><div class="prose"><h3>{E(t["recover_h"])}</h3><p>{E(t["recover_p"])}</p></div>
<div class="cards2"><figure class="stage" style="margin:0;padding:8px">{rec_img}<figcaption><span class="demo-tag">DEMO</span>{E(t["report_p"])}</figcaption></figure></div></div></div></section>

<section class="band alt" aria-labelledby="adv-h"><div class="wrap split rev"><figure class="stage" style="margin:0;padding:8px">{adv_img}<figcaption>{adv_tag}{E(t["adv_cap"])}</figcaption></figure>
<div class="prose"><h2 id="adv-h">{E(t["adv_h"])}</h2><p>{E(t["adv_p"])}</p><h3>{E(t["text_h"])}</h3><p>{E(t["text_p"])}</p></div></div></section>

<section class="band" aria-labelledby="plat-h"><div class="wrap"><h2 id="plat-h">{E(t["plat_h"])}</h2><div class="cards2" style="margin-top:20px">
<figure class="stage" style="margin:0;padding:8px">{mac_img}<figcaption><span class="real-tag">REAL</span>{E(t["plat_mac"])}</figcaption></figure>
<figure class="stage" style="margin:0;padding:8px">{win_img}<figcaption><span class="real-tag">REAL</span>{E(t["plat_win"])}</figcaption></figure></div>
<p class="cap" style="max-width:70ch">{E(t["plat_note"])}</p>
<figure class="stage" style="margin:26px 0 0;padding:8px;max-width:760px">{fin_img}<figcaption><span class="demo-tag">DEMO</span>{E(t["report_p"])}</figcaption></figure></div></section>

<section class="band alt" aria-labelledby="limits-h"><div class="wrap"><h2 id="limits-h">{E(t["limits_h"])}</h2><p class="lead">{E(t["limits_lead"].format(v=S.VERSION, b=S.BUILD))}</p>
<div class="lim"><div class="y"><h3>{E(t["ok_label"])}</h3><ul>{ok}</ul></div><div class="n"><h3>{E(t["no_label"])}</h3><ul>{no}</ul></div></div></div></section>

<section class="band" aria-labelledby="free-h"><div class="wrap split"><div class="prose"><h2 id="free-h">{E(t["free_h"])}</h2><p>{E(t["free_p"])}</p><h3>{E(t["credits_h"])}</h3><ul>{credits}</ul></div>
<div class="prose"><h3>{E(t["links_h"])}</h3><ul class="links">{links}<li><a href="{pdf}">{E(t["pdf_h"])}</a></li></ul>
<p>{E(t["star"])}</p><a class="btn small ghost star" href="{S.REPO}"><picture><source media="(prefers-color-scheme: dark)" srcset="{r}{ASSETS}/github-invertocat-white.svg"><img src="{r}{ASSETS}/github-invertocat-black.svg" width="22" height="22" alt=""></picture>{E(t["star_btn"])}</a></div></div></section>

<section class="band alt" aria-labelledby="inst-h"><div class="wrap split"><div class="prose"><h2 id="inst-h">{E(t["install_h"])}</h2><p>{E(t["install_mac"])}</p><p>{E(t["install_win"])}</p><p>{E(t["install_incl"])}</p></div>
<div class="prose"><p>{E(t["install_upd"])}</p><p>{E(t["install_rm"])}</p><h3>{E(t["support_h"])}</h3><p>{E(t["support_p"])}</p></div></div></section>
</main>"""
    return head(lang, "home", depth, t["title"], t["desc"], real_hero if real_hero in sizes else "icon-b-512") + "<body>" + header(lang, "home", depth) + body + footer(lang, depth) + f"<script>{JS}</script></body></html>"


# --------------------------------------------------------------------------- guide


def slug(text: str) -> str:
    s = re.sub(r"<[^>]+>", "", text).lower()
    s = re.sub(r"[^a-z0-9ăâîșşțţáéíóúñü]+", "-", s).strip("-")
    return s or "sec"


def _web(text: str) -> str:
    """The guide sources are written for the PDF engine; map its font tags to HTML."""
    return re.sub(r"<font face=['\"]Courier['\"]>(.*?)</font>", r"<code>\1</code>", text, flags=re.S)


def blocks_html(blocks: list, lang: str = "", sizes: dict | None = None, r: str = "") -> str:
    out = []
    for b in blocks:
        kind, val = b[0], b[1]
        if kind == "p":
            out.append(f"<p>{val}</p>")
        elif kind == "h2":
            out.append(f"<h3>{val}</h3>")
        elif kind == "ul":
            out.append("<ul>" + "".join(f"<li>{x}</li>" for x in val) + "</ul>")
        elif kind == "steps":
            out.append('<ol class="steps">' + "".join(f"<li>{x}</li>" for x in val) + "</ol>")
        elif kind == "code":
            out.append(f"<pre><code>{E(val)}</code></pre>")
        elif kind == "opt":
            (h1, h2), rows = val
            out.append(
                f'<table class="opt"><thead><tr><th>{h1}</th><th>{h2}</th></tr></thead><tbody>'
                + "".join(f"<tr><td>{a}</td><td>{c}</td></tr>" for a, c in rows)
                + "</tbody></table>"
            )
        elif kind in ("info", "warn", "ok"):
            title, text = val
            cls = {"info": "", "warn": " warn", "ok": " ok"}[kind]
            out.append(f'<aside class="callout{cls}" role="note"><strong>{title}</strong><p>{text}</p></aside>')
        elif kind == "wcv":
            lab_do, lab_why, lab_chk, lab_lim, lab_step = val["labels"]
            name = f"gstep{val['n']}-{lang}"
            fig = ""
            if sizes and name in sizes:
                w, h = sizes[name]
                fig = (f'<figure class="wcv-fig"><img src="{r}{ASSETS}/{name}.webp" width="{w}" height="{h}" loading="lazy" alt="{E(val["fig"])}">'
                       f'<figcaption>{E(val["fig"])}</figcaption></figure>')
            cols = "".join(
                f'<div class="wcv-col"><h4>{lab}</h4>' + "".join(f"<p>{x}</p>" for x in items) + "</div>"
                for lab, items in ((lab_do, val["do"]), (lab_why, val["why"]), (lab_chk, val["check"]))
            )
            limit = f'<p class="wcv-limit"><strong>{lab_lim}.</strong> {val["limit"]}</p>' if val.get("limit") else ""
            out.append(f'<div class="wcv"><h3>{val["n"]}. {val["title"]}</h3><p>{val["purpose"]}</p>{fig}<div class="wcv-cols">{cols}</div>{limit}</div>')
        # "img" blocks point to earlier screenshots of the old layout: left to the PDF
    return _web("".join(out))


def guide(lang: str, sizes: dict) -> str:
    mod = __import__(f"ghid_{lang}")
    content = mod.CONTENT
    t = S.L[lang]
    depth = S.PATHS[lang]["guide"].count("/")
    r = rel(depth)
    secs = list(content["sections"])
    secs.append({
        "h": t["limits_h"],
        "blocks": [("p", E(t["limits_lead"].format(v=S.VERSION, b=S.BUILD))),
                   ("h2", t["ok_label"]), ("ul", [E(x) for x in t["limits_ok"]]),
                   ("h2", t["no_label"]), ("ul", [E(x) for x in t["limits_no"]])],
    })
    ids = [slug(s["h"]) for s in secs]
    toc = "".join(f'<li><a href="#{i}">{s["h"]}</a></li>' for i, s in zip(ids, secs))
    art = "".join(f'<section id="{i}"><h2>{s["h"]}</h2>{blocks_html(s["blocks"], lang, sizes, r)}</section>' for i, s in zip(ids, secs))
    home = f"{r}{S.PATHS[lang]['home']}"
    pdf = f"{r}{S.PDF[lang]}"
    body = (
        f'<main id="main"><div class="wrap"><p style="margin:20px 0 0"><a href="{home}">← {E(t["back_home"])}</a></p>'
        f'<div style="padding-top:14px"><p class="kicker">{E(t["guide_h"])}</p><h1 style="font-size:clamp(1.9rem,4vw,3rem)">{E(content["title"])}</h1>'
        f'<p class="lead">{E(t["guide_intro"].format(v=S.VERSION, b=S.BUILD))} <a href="{pdf}">{E(t["pdf_h"])}</a></p></div>'
        f'<div class="guide"><nav class="toc" aria-label="{E(t["toc"])}"><h2>{E(t["toc"])}</h2><ol>{toc}</ol></nav><article>{art}</article></div></div></main>'
    )
    return head(lang, "guide", depth, f'{content["title"]} — DisplayCAL-CG', t["guide_intro"].format(v=S.VERSION, b=S.BUILD), "icon-b-512") + "<body>" + header(lang, "guide", depth) + body + footer(lang, depth) + "</body></html>"


# --------------------------------------------------------------------------- main


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=os.path.join(REPO, "docs"))
    ap.add_argument("--assets-only", action="store_true")
    a = ap.parse_args()
    sizes = prep_images(a.out)
    prep_readme(a.out)
    # official GitHub Invertocat (unaltered), see docs/BRAND_ASSETS.md
    brand = os.path.join(REPO, "DisplayCAL", "theme", "brands")
    os.makedirs(os.path.join(a.out, ASSETS), exist_ok=True)
    for src, dst in (("github-invertocat-white.svg", "github-invertocat-white.svg"), ("github-invertocat-black.svg", "github-invertocat-black.svg")):
        if os.path.isfile(os.path.join(brand, src)):
            with open(os.path.join(brand, src), "rb") as f, open(os.path.join(a.out, ASSETS, dst), "wb") as g:
                g.write(f.read())
    # the star button sits on a neutral button: the theme picks black or white
    if os.path.isfile(os.path.join(a.out, ASSETS, "github-invertocat-black.svg")):
        with open(os.path.join(a.out, ASSETS, "github-invertocat-black.svg"), "rb") as f, open(os.path.join(a.out, ASSETS, "github-invertocat.svg"), "wb") as g:
            g.write(f.read())
    if a.assets_only:
        return 0
    for lang in ("ro", "en", "es"):
        for kind, fn in (("home", landing), ("guide", guide)):
            path = os.path.join(a.out, S.PATHS[lang][kind], "index.html")
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(fn(lang, sizes))
            print(path, os.path.getsize(path) // 1024, "KB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
