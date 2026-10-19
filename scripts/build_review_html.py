#!/usr/bin/env python3
"""Build ``index.html`` for the visual review from the capture indexes.

Reads ``<review>/<lang>/<theme>/index.json`` (written by capture_review.py) and
writes a self-contained navigation page (images stay as files next to it, so the
folder can be opened outside any chat). Usage: build_review_html.py <review_dir>
"""

from __future__ import annotations

import glob
import json
import os
import sys

TEMPLATE = r"""<!doctype html>
<html lang="ro"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>DisplayCAL-CG — inventar vizual</title>
<style>
:root{--bg:#f4f4f6;--fg:#1b1c20;--mut:#5d6068;--card:#fff;--line:#d3d5db;--acc:#b8541c;--warn:#c8461e;--ok:#1f7a4d}
@media(prefers-color-scheme:dark){:root{--bg:#16171a;--fg:#eceef1;--mut:#a9acb4;--card:#202226;--line:#383a41}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,system-ui,sans-serif}
header{padding:14px 18px;border-bottom:1px solid var(--line);display:flex;flex-wrap:wrap;gap:12px;align-items:center}
h1{font-size:18px;margin:0 12px 0 0}.band{background:var(--warn);color:#fff;padding:6px 10px;border-radius:6px;font-size:13px;font-weight:600}
.layout{display:grid;grid-template-columns:300px 1fr;min-height:calc(100vh - 110px)}
nav{border-right:1px solid var(--line);padding:10px 8px;overflow:auto;max-height:calc(100vh - 110px);position:sticky;top:0}
nav h2{font-size:12px;text-transform:uppercase;letter-spacing:.06em;color:var(--mut);margin:14px 8px 4px}
nav button{display:block;width:100%;text-align:left;background:none;border:0;color:var(--fg);padding:6px 8px;border-radius:6px;cursor:pointer;font:inherit}
nav button:hover{background:var(--card)}nav button.on{background:var(--card);outline:2px solid var(--acc)}
nav small{display:block;color:var(--mut)}
main{padding:16px 22px}
.ctl{display:flex;gap:6px;flex-wrap:wrap;margin:0 0 12px}.ctl button{border:1px solid var(--line);background:var(--card);color:var(--fg);padding:5px 10px;border-radius:6px;cursor:pointer}
.ctl button.on{background:var(--acc);color:#fff;border-color:var(--acc)}.ctl button:disabled{opacity:.35;cursor:default}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:0 0 14px}
.card h3{margin:0 0 4px;font-size:17px}.mut{color:var(--mut)}.sim{color:var(--warn);font-weight:600}
code{font-size:12px;word-break:break-all}.clip{color:var(--warn);font-size:13px}.ok{color:var(--ok)}
.shot{display:block;max-width:100%;height:auto;border:1px solid var(--line);border-radius:8px;cursor:zoom-in}
#zoom{position:fixed;inset:0;background:rgba(0,0,0,.88);display:none;overflow:auto;z-index:10;cursor:zoom-out}
#zoom img{display:block;margin:0 auto;max-width:none;width:var(--zw,100%)}
#zbar{position:fixed;top:8px;right:12px;z-index:11;display:none;gap:6px}#zbar button{padding:6px 12px;border-radius:6px;border:0;cursor:pointer}
@media(max-width:820px){.layout{grid-template-columns:1fr}nav{position:static;max-height:240px;border-right:0;border-bottom:1px solid var(--line)}}
</style></head><body>
<header><h1>DisplayCAL-CG — inventar vizual</h1><span class="band">Date demonstrative: monitor și instrument simulate; nimic real nu este modificat</span>
<span class="mut" id="gen"></span></header>
<div class="layout"><nav id="nav"></nav><main>
<div class="ctl" id="langs"></div><div class="ctl" id="themes"></div>
<div class="card" id="meta"></div><img id="img" class="shot" alt=""><p class="mut" style="margin-top:14px">Navigare: săgeți ←/→ sau lista din stânga; clic pe imagine pentru mărire (+/− în modul mărit, Esc pentru ieșire).</p>
</main></div>
<div id="zbar"><button id="zin">+</button><button id="zout">−</button><button id="zfit">Potrivește</button></div><div id="zoom"><img id="zimg" alt=""></div>
<script>
const DATA=__DATA__, ROOT=__ROOT__, GROUPS=__GROUPS__, EXTRAS=__EXTRAS__;
const state={lang:'ro',theme:'light',name:null};
const $=id=>document.getElementById(id);
function cur(){return (DATA[state.lang]||{})[state.theme]||[]}
function find(name,l=state.lang,t=state.theme){return EXTRAS.find(e=>e.name===name)||((DATA[l]||{})[t]||[]).find(e=>e.name===name)}
function buildNav(){const nav=$('nav');nav.innerHTML='';const base=[...EXTRAS,...((DATA.ro&&DATA.ro.light)||cur())];
 GROUPS.forEach(g=>{const items=base.filter(e=>g.match.some(m=>e.name.startsWith(m)));if(!items.length)return;
  const h=document.createElement('h2');h.textContent=g.title;nav.appendChild(h);
  items.forEach(e=>{const b=document.createElement('button');b.dataset.name=e.name;b.innerHTML=e.title.replace(/^[^—]*— /,'')+'<small>'+String(e.n).padStart(2,'0')+' · '+e.name+'</small>';b.onclick=()=>{state.name=e.name;render()};nav.appendChild(b)})})}
function render(){
 const e=find(state.name)||cur()[0]; if(!e)return; state.name=e.name;
 document.querySelectorAll('nav button').forEach(b=>b.classList.toggle('on',b.dataset.name===state.name));
 const path=e.common?e.file:`${state.lang}/${state.theme}/${e.file}`;
 $('img').src=path;$('zimg').src=path;
 const clip=(e.clipped||[]).length?`<div class="clip">Posibile tăieturi (verificare automată): ${(e.clipped||[]).map(x=>x.replace(/</g,'&lt;')).join('; ')}</div>`:'<div class="ok">Verificare automată de tăieturi: nimic suspect.</div>';
 $('meta').innerHTML=`<h3>${e.n}. ${e.title.replace(/</g,'&lt;')}</h3><div>${e.shows}</div><div class="sim">Simulat/ilustrativ: ${e.simulated||'—'}</div>${clip}<div class="mut">Fișier: <code>${ROOT}/${path}</code> · ${e.size[0]}×${e.size[1]} px</div>`;
 ['ro','en','es'].forEach(l=>{});
 location.hash=`${state.lang}/${state.theme}/${state.name}`;
}
function buildCtl(){const L=$('langs'),T=$('themes');L.innerHTML='';T.innerHTML='';
 [['ro','Română (prima)'],['en','English'],['es','Español']].forEach(([l,t])=>{const b=document.createElement('button');b.textContent=t;b.disabled=!DATA[l];b.className=state.lang===l?'on':'';b.onclick=()=>{state.lang=l;if(!((DATA[l]||{})[state.theme]))state.theme=Object.keys(DATA[l])[0];buildCtl();render()};L.appendChild(b)});
 [['light','Temă luminoasă'],['dark','Temă întunecată']].forEach(([t,x])=>{const b=document.createElement('button');b.textContent=x;b.disabled=!((DATA[state.lang]||{})[t]);b.className=state.theme===t?'on':'';b.onclick=()=>{state.theme=t;buildCtl();render()};T.appendChild(b)})}
let zw=100;function zoom(){const z=$('zoom');$('zbar').style.display=z.style.display='block';z.style.setProperty('--zw',zw+'%')}
$('img').onclick=()=>{zw=100;zoom()};$('zoom').onclick=e=>{if(e.target.id!=='zbar'){$('zoom').style.display=$('zbar').style.display='none'}};
$('zin').onclick=()=>{zw=Math.min(300,zw+25);zoom()};$('zout').onclick=()=>{zw=Math.max(50,zw-25);zoom()};$('zfit').onclick=()=>{zw=100;zoom()};
document.addEventListener('keydown',ev=>{const names=[...document.querySelectorAll('nav button')].map(b=>b.dataset.name);let i=names.indexOf(state.name);
 if(ev.key==='Escape'){$('zoom').style.display=$('zbar').style.display='none'}
 else if(ev.key==='ArrowRight'&&i<names.length-1){state.name=names[i+1];render()}else if(ev.key==='ArrowLeft'&&i>0){state.name=names[i-1];render()}
 else if($('zoom').style.display==='block'&&(ev.key==='+'||ev.key==='=')){zw=Math.min(300,zw+25);zoom()}else if($('zoom').style.display==='block'&&ev.key==='-'){zw=Math.max(50,zw-25);zoom()}});
$('gen').textContent='Generat: '+__GEN__;
const h=location.hash.replace('#','').split('/');if(h.length===3&&DATA[h[0]]){state.lang=h[0];state.theme=h[1];state.name=h[2]}
buildNav();buildCtl();render();
</script></body></html>
"""

EXTRAS = [
    {"n": 0, "name": "decision_icon_B", "common": True, "file": "icon/icon_B_large.png",
     "title": "Decizie deschisă — Iconul B (candidat, neaprobat)",
     "shows": "Iconul B (finisaj lucios controlat) la 640 px: simbolul triunghiular, sferele RGB și fasciculul păstrate. Aplicat într-un singur commit revertabil.",
     "simulated": "Candidat de design; aprobarea finală aparține lui Cristi.", "size": [1100, 700], "clipped": []},
    {"n": 0, "name": "decision_icon_B_dark", "common": True, "file": "icon/icon_B_large_dark.png",
     "title": "Decizie deschisă — Iconul B pe fundal întunecat",
     "shows": "Același icon pe fundal întunecat; triunghiul închis are contrast mic pe antet închis (punct de decis).",
     "simulated": "Candidat de design.", "size": [1100, 700], "clipped": []},
    {"n": 0, "name": "decision_icon_B_sizes_light", "common": True, "file": "icon/icon_B_context_light.png",
     "title": "Decizie deschisă — Iconul B la dimensiuni de utilizare (luminos)",
     "shows": "180 / 128 / 96 / 64 / 48 / 32 / 16 px. La 16–32 px fasciculul devine foarte fin; sferele rămân lizibile.",
     "simulated": "Candidat de design.", "size": [1100, 300], "clipped": []},
    {"n": 0, "name": "decision_icon_B_sizes_dark", "common": True, "file": "icon/icon_B_context_dark.png",
     "title": "Decizie deschisă — Iconul B la dimensiuni de utilizare (întunecat)",
     "shows": "Aceleași dimensiuni pe fundal întunecat.", "simulated": "Candidat de design.", "size": [1100, 300], "clipped": []},
]

GROUPS = [
    {"title": "Decizii deschise (icon)", "match": ["decision_"]},
    {"title": "Ghid", "match": ["guide_"]},
    {"title": "Avansat — file", "match": ["adv_"]},
    {"title": "Avansat — explicații pe decizii", "match": ["help_"]},
    {"title": "Stări care schimbă sensul controalelor", "match": ["state_"]},
    {"title": "Dialoguri și unelte", "match": ["dlg_"]},
]


def main() -> int:
    root = os.path.abspath(sys.argv[1])
    data: dict = {}
    for p in sorted(glob.glob(os.path.join(root, "*", "*", "index.json"))):
        lang, theme = p.split(os.sep)[-3:-1]
        data.setdefault(lang, {})[theme] = json.load(open(p, encoding="utf-8"))
    import time

    html = (
        TEMPLATE.replace("__DATA__", json.dumps(data, ensure_ascii=False))
        .replace("__ROOT__", json.dumps(root))
        .replace("__GROUPS__", json.dumps(GROUPS, ensure_ascii=False))
        .replace("__EXTRAS__", json.dumps(EXTRAS, ensure_ascii=False))
        .replace("__GEN__", json.dumps(time.strftime("%Y-%m-%d %H:%M")))
    )
    out = os.path.join(root, "index.html")
    with open(out, "w", encoding="utf-8") as f:
        f.write(html)
    print(out, sum(len(t) for l in data.values() for t in l.values()), "entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
