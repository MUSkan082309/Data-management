import os
import colorsys
import json
import streamlit.components.v1 as components
import base64
import datetime
import time
import html
import sqlite3
import pandas as pd
import requests
import streamlit as st
from dq_framework import Validator, DataQualityError, required, pattern, in_range, run_sql_checks

HERE = os.path.dirname(os.path.abspath(__file__))
st.set_page_config(page_title="Data Quality Guard", page_icon="🛡️", layout="wide")

st.markdown("""
<style>
.stApp{background:#1a2233;color:#f1f5f9}
header[data-testid="stHeader"]{background:transparent}
.block-container,[data-testid="stMainBlockContainer"],div.stMainBlockContainer{padding-top:3rem !important;max-width:1800px !important;width:100% !important;margin:0 auto !important;padding-left:2.2rem !important;padding-right:2.2rem !important}
[data-testid="stVerticalBlock"]{gap:.8rem}
@keyframes rise{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:none}}
.hero{position:relative;padding:1rem 1.5rem;margin-bottom:.8rem;border-radius:16px;background:linear-gradient(120deg,#243047,#2b3b5a);border:1px solid #34425e;overflow:hidden;animation:rise .5s}
.hero:before{content:"";position:absolute;left:0;top:0;right:0;height:3px;background:linear-gradient(90deg,#38bdf8,#34d399)}
.hero h1{margin:.2rem 0 0;font-size:1.9rem;line-height:1.2;font-weight:800;letter-spacing:-.5px;color:#fff}
.hero .sub{margin-top:.25rem;color:#9fb3cf;font-size:1rem}
.pill{display:inline-block;padding:.15rem .65rem;border-radius:99px;background:#38bdf822;color:#7dd3fc;border:1px solid #38bdf844;font-size:.72rem;margin-bottom:.6rem}
.verdict{display:flex;align-items:center;gap:.7rem;padding:.8rem 1.1rem;border-radius:12px;border:1px solid;animation:rise .6s}
.verdict b{font-size:1.05rem}.verdict span{color:#b6c4da;font-size:.9rem}
.verdict{margin-bottom:.8rem}.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:.8rem;margin-bottom:.8rem}
.row{display:grid;grid-template-columns:1fr 1fr;gap:.8rem;margin-bottom:.8rem}.half{min-height:230px}
.box{padding:1.1rem 1.25rem;border-radius:14px;background:#243047;border:1px solid #34425e;transition:transform .2s,border-color .2s,box-shadow .2s;animation:rise .7s}
.box:hover{transform:translateY(-3px);border-color:#38bdf866;box-shadow:0 10px 30px #00000055}
.kpi{height:128px;display:flex;align-items:center;gap:1rem}
.kpi small,.box h4{color:#8da2c0;text-transform:uppercase;letter-spacing:1px;font-size:.7rem;margin:0}
.kpi b{display:block;font-size:2.4rem;line-height:1.1}
.kpi p{margin:.2rem 0 0;color:#8da2c0;font-size:.8rem}
.panel{min-height:340px;display:flex;flex-direction:column}
.panel h4{font-size:.95rem;color:#f1f5f9;text-transform:none;letter-spacing:0}
.panel>small{color:#8da2c0;margin-bottom:.7rem}
.ring{width:84px;height:84px;border-radius:50%;display:grid;place-items:center;flex:none}
.ring div{width:64px;height:64px;border-radius:50%;background:#243047;display:grid;place-items:center;font-weight:800;font-size:1.4rem}
.tiles{display:grid;gap:10px;flex:1;align-content:start;grid-template-columns:repeat(auto-fill,var(--ts))}
.tile{width:var(--ts);height:var(--ts);border-radius:12px;display:grid;place-items:center;font-weight:700;color:#06101f;position:relative;cursor:default;transition:transform .15s,box-shadow .15s}
.tile:hover{transform:scale(1.14);z-index:9;box-shadow:0 6px 18px #00000088}
.tile:after{content:attr(data-tip);position:absolute;bottom:118%;left:50%;transform:translateX(-50%);width:max-content;max-width:230px;background:#020617;border:1px solid #334155;color:#e2e8f0;padding:.4rem .6rem;border-radius:8px;font-size:.75rem;font-weight:500;opacity:0;pointer-events:none;transition:opacity .15s}
.tile:hover:after{opacity:1}
.rib{transition:stroke-opacity .2s}.rib:hover{stroke-opacity:.9}
.bar{display:flex;height:14px;border-radius:99px;overflow:hidden;background:#ffffff12;margin:.6rem 0}
.bar div{transition:filter .2s}.bar div:hover{filter:brightness(1.3)}
.rule{margin:.7rem 0}.rl{display:flex;justify-content:space-between;font-size:.85rem;color:#c9d6ea;margin-bottom:.3rem}.track{height:8px;border-radius:99px;background:#ffffff12;overflow:hidden}.track div{height:100%;border-radius:99px}
.feed{font-family:ui-monospace,monospace;font-size:.85rem;line-height:1.8}
.legend span{margin-right:1.1rem;font-size:.82rem;color:#b6c4da}
</style>
""", unsafe_allow_html=True)

SAMPLE = pd.DataFrame([
    {"id": 1, "email": "a@x.com", "age": 25}, {"id": 2, "email": "Bad-Email", "age": 30},
    {"id": 3, "email": "", "age": 200}, {"id": 4, "email": "A@x.com ", "age": 40},
    {"id": 5, "email": "sam@corp.io", "age": 33}, {"id": 6, "email": "kim@corp.io", "age": -4},
])
WEIGHT = {"LOW": .25, "MEDIUM": .6, "HIGH": 1.0}
SEVCOL = {"LOW": "#eab308", "MEDIUM": "#f59e0b", "HIGH": "#f43f5e"}
KCOL = {"Passed": "#34d399", "Missing value": "#f43f5e", "Wrong format": "#f59e0b", "Impossible value": "#a78bfa", "Duplicate": "#38bdf8"}
KIND = {"MissingValueError": "Missing value", "FormatError": "Wrong format", "RangeError": "Impossible value", "DuplicateRecordError": "Duplicate"}
WHY = {"MissingValueError": "{f} is missing.", "FormatError": "{f} doesn't look valid (wrong format).",
       "RangeError": "{f} is outside the allowed range.", "DuplicateRecordError": "{f} already appeared in an earlier record."}
ACTION = {"MissingValueError": "Ask the source system for the value; hold the record until then.",
          "FormatError": "Trim spaces and lowercase it; if still invalid, send back to the data owner.",
          "RangeError": "Set it to empty and flag it for review. We never guess a value.",
          "DuplicateRecordError": "Keep the first record and drop this one."}

with st.sidebar:
    st.header("📏 Your data rules")
    st.caption("Switch rules on or off and watch everything update.")
    need = st.checkbox("Email is required", True, help="Records without an email are blocked.")
    fmt = st.checkbox("Email must look valid", True, help="Must look like name@domain.com.")
    uniq = st.checkbox("Email must be unique", True, help="The same email can't appear twice.")
    lo, hi = st.slider("Allowed age", 0, 150, (0, 120), help="Ages outside this range are blocked.")
    st.divider()
    autoclean = st.toggle("🪄 Auto-fix safe problems", False, help="Trims spaces, lowercases emails, removes duplicates and empties impossible ages before checking.")
    up = st.file_uploader("Use your own data (CSV)", type="csv", help="Needs columns: id, email, age.")
    st.caption("No file? A sample of customer records is used.")
    st.divider()
    client = st.text_input("Client / company name", placeholder="e.g. ACME Corp")
    logo = st.file_uploader("Client logo (optional)", type=["png", "jpg", "jpeg"])
    brand = st.color_picker("Brand colour", "#38bdf8", help="Match your client's brand. Changes the whole look.")

def _shift(h, deg):
    r, g, b = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    hh, l, sat = colorsys.rgb_to_hls(r, g, b)
    r, g, b = colorsys.hls_to_rgb((hh + deg / 360) % 1, l, sat)
    return "#%02x%02x%02x" % (int(r * 255), int(g * 255), int(b * 255))
def _light(h, k=.45):
    return "#" + "".join("%02x" % int(int(h[i:i + 2], 16) * (1 - k) + 255 * k) for i in (1, 3, 5))
acc, acc2, accl = brand, _shift(brand, -35), _light(brand)
st.markdown("""<style>
.hero:before{background:linear-gradient(90deg,ACC,ACC2) !important}
.pill{background:ACC22 !important;color:ACCL !important;border-color:ACC55 !important}
button[kind="primary"]{background:ACC !important;border-color:ACC !important;color:#05070d !important}
button[role="tab"][aria-selected="true"]{color:ACCL !important}
[data-baseweb="tab-highlight"]{background:ACC !important}
div[role="slider"]{background:ACC !important}
</style>""".replace("ACCL", accl).replace("ACC2", acc2).replace("ACC", acc), unsafe_allow_html=True)

logo_html = (f'<img src="data:{logo.type};base64,{base64.b64encode(logo.getvalue()).decode()}" style="height:46px;border-radius:8px;background:#fff;padding:4px">' if logo else "")
who = (f'<span class="pill" style="background:#34d39922;color:#6ee7b7;border-color:#34d39944;margin-left:.4rem">Prepared for {html.escape(client)}</span>' if client else "")
st.markdown(f'''<div class="hero" style="display:flex;justify-content:space-between;align-items:center;padding:.7rem 1.3rem"><div style="display:flex;align-items:center;gap:.8rem;flex-wrap:wrap">
<h1 style="margin:0;font-size:1.5rem">🛡️ Data Quality Guard</h1><span class="pill" style="margin:0">✨ AI-assisted</span>{who}</div>{logo_html}</div>''', unsafe_allow_html=True)

df = pd.read_csv(up) if up else SAMPLE
if {"id", "email", "age"} - set(df.columns):
    st.error("Your CSV needs these columns: id, email, age"); st.stop()
raw = [{k: (None if pd.isna(v) else v) for k, v in r.items()} for r in df.to_dict("records")]

def clean(recs):
    out, seen, log = [], set(), []
    for r in recs:
        r = dict(r); e = r["email"]
        if isinstance(e, str) and e != e.strip().lower():
            r["email"] = e.strip().lower(); log.append((r["id"], "Email trimmed / lowercased"))
        if r["age"] is not None and not lo <= r["age"] <= hi:
            log.append((r["id"], f"Impossible age {r['age']} emptied")); r["age"] = None
        if r["email"] and r["email"] in seen:
            log.append((r["id"], "Duplicate record removed")); continue
        if r["email"]: seen.add(r["email"])
        out.append(r)
    return out, log

rules = ([required("email")] if need else []) + ([pattern("email", r"[^@\s]+@[^@\s]+\.[a-z]+")] if fmt else []) + [in_range("age", lo, hi)]
def validate(recs): return Validator(rules, unique_fields=("email",) if uniq else ()).run(recs)
def score(rep, n):
    pen = sum(WEIGHT[max(e.severity for e in errs).name] for _, errs in rep.quarantined)
    return round(100 * (1 - pen / n)) if n else 100
def worst(errs): return max(errs, key=lambda e: e.severity)

try:
    rep_raw = validate(raw); cleaned, clog = clean(raw); rep_clean = validate(cleaned)
except DataQualityError as e:
    st.error(f"⛔ Pipeline stopped on a CRITICAL problem: {e}"); st.stop()

rep, recs = (rep_clean, cleaned) if autoclean else (rep_raw, raw)
n, ok, bad = len(recs), len(rep.valid), len(rep.quarantined)
s = score(rep, n)
col = "#34d399" if s >= 80 else "#f59e0b" if s >= 50 else "#f43f5e"
verdict = "Your data is in good shape." if s >= 80 else "Some records need attention." if s >= 50 else "Your data has serious problems."
reasons = {r["id"]: "; ".join(WHY[type(e).__name__].format(f=e.field_name.capitalize()) for e in es) for r, es in rep.quarantined}

VIEW_HTML = r'''<!doctype html><html><head><meta charset="utf-8"><style>
*{box-sizing:border-box}body{margin:0;background:transparent;font-family:Inter,Segoe UI,Arial,sans-serif;color:#f1f5f9}
#wrap{position:relative;border-radius:18px;overflow:hidden;border:1px solid #34425e;background:radial-gradient(900px 420px at 15% 0%,#1e3a8a55,transparent),radial-gradient(700px 400px at 100% 100%,#0e749040,transparent),#1a2233}
#top{display:flex;align-items:center;justify-content:space-between;padding:16px 22px;gap:18px;flex-wrap:wrap}
.chip{font-size:11px;letter-spacing:2px;color:#7dd3fc;border:1px solid #38bdf855;padding:3px 10px;border-radius:99px;background:#38bdf814}
#verdict{font-size:24px;font-weight:800;margin-top:8px}#sub{color:#8da2c0;font-size:13px;margin-top:3px}
.stat{text-align:center;min-width:90px}.stat b{display:block;font-size:32px;line-height:1.1}.stat small{color:#8da2c0;font-size:11px;letter-spacing:1px;text-transform:uppercase}
#gauge{position:relative;width:120px;height:120px}#gauge svg{transform:rotate(-90deg)}#gnum{position:absolute;inset:0;display:grid;place-items:center;font-size:34px;font-weight:800}
canvas{width:100%;height:400px;display:block}
#tip{position:absolute;pointer-events:none;background:#020617ee;border:1px solid #334155;padding:8px 11px;border-radius:10px;font-size:12px;max-width:240px;opacity:0;transition:opacity .12s}
#replay{position:absolute;left:18px;bottom:14px;background:#38bdf8;color:#04121f;border:0;border-radius:99px;padding:7px 14px;font-weight:700;cursor:pointer;font-size:12px}
#ins{position:absolute;left:18px;top:200px;width:calc(36% - 50px);padding:14px 16px;border-radius:14px;background:#243047ee;border:1px solid #38bdf844;opacity:0;transform:translateY(8px);transition:all .6s;pointer-events:none}#ins.on{opacity:1;transform:none}#ins small{color:#7dd3fc;font-size:11px;letter-spacing:2px}#ins b{display:block;font-size:17px;margin:5px 0}#ins p{margin:6px 0 0;font-size:13px;color:#c9d6ea;line-height:1.4}
</style></head><body><div id="wrap">
<div id="top"><div><span class="chip">LIVE PIPELINE</span><div id="verdict">Analysing...</div><div id="sub"></div></div>
<div style="display:flex;gap:20px;align-items:center"><div class="stat"><b id="cp" style="color:#34d399">0</b><small>passed</small></div><div class="stat"><b id="cb" style="color:#f43f5e">0</b><small>quarantined</small></div>
<div id="gauge"><svg width="120" height="120"><circle cx="60" cy="60" r="50" fill="none" stroke="#ffffff14" stroke-width="10"/><circle id="arc" cx="60" cy="60" r="50" fill="none" stroke="#34d399" stroke-width="10" stroke-linecap="round" stroke-dasharray="314" stroke-dashoffset="314"/></svg><div id="gnum">--</div></div></div></div>
<canvas id="c"></canvas><div id="tip"></div><div id="ins"><small>TOP INSIGHT</small><b id="it"></b><p id="ib"></p><p id="ip" style="color:#7dd3fc"></p><p id="il" style="color:#34d399"></p></div><button id="replay">&#8635; Replay</button></div>
<script>
const D=__DATA__, R=D.recs, N=R.length;
const cv=document.getElementById('c'),ctx=cv.getContext('2d'),tip=document.getElementById('tip');
const COL={MEDIUM:'#f59e0b',HIGH:'#f43f5e',LOW:'#eab308'},PASS='#34d399';
const d0=900,pause=240,d1=1100; let W,H,G,items=[],t0=performance.now(),done=false;
const esc=t=>String(t).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const ease=p=>p<0?0:p>1?1:1-Math.pow(1-p,3);
function layout(){
 const dpr=window.devicePixelRatio||1; W=cv.clientWidth; H=cv.clientHeight; cv.width=W*dpr; cv.height=H*dpr; ctx.setTransform(dpr,0,0,dpr,0,0);
 const r=N>80?4:N>40?6:N>16?8:N>8?12:17, gap=r*2+8, L=W*0.60, laneW=W-L-22, cols=Math.max(1,Math.floor((laneW-34)/gap));
 G={r,L,laneW,gateX:W*0.36,srcX:56,mid:H/2}; const c={p:0,b:0};
 items=R.map((rc,i)=>{const k=rc.ok?c.p++:c.b++, top=rc.ok?48:H/2+42;
  return{rc,i,r,col:rc.ok?PASS:(COL[rc.sev]||COL.HIGH),tx:L+20+r+(k%cols)*gap,ty:top+r+Math.floor(k/cols)*gap,spawn:i*Math.min(420,6500/N)};});
}
function pos(it,now){const t=now-t0-it.spawn; if(t<0)return null;
 if(t<d0){const p=ease(t/d0);return{x:G.srcX+(G.gateX-G.srcX)*p,y:G.mid+Math.sin(t/120+it.i)*3,st:0,t};}
 if(t<d0+pause)return{x:G.gateX,y:G.mid,st:1,t:t-d0};
 const p=ease((t-d0-pause)/d1);return{x:G.gateX+(it.tx-G.gateX)*p,y:G.mid+(it.ty-G.mid)*p,st:p>=1?3:2,t};}
function rr(x,y,w,h,r){ctx.beginPath();ctx.moveTo(x+r,y);ctx.arcTo(x+w,y,x+w,y+h,r);ctx.arcTo(x+w,y+h,x,y+h,r);ctx.arcTo(x,y+h,x,y,r);ctx.arcTo(x,y,x+w,y,r);ctx.closePath();}
function lane(y,h,c,label){ctx.save();rr(G.L,y,G.laneW,h,14);ctx.fillStyle=c+'14';ctx.fill();ctx.strokeStyle=c+'66';ctx.lineWidth=1;ctx.stroke();
 ctx.fillStyle=c;ctx.font='bold 12px sans-serif';ctx.textAlign='left';ctx.fillText(label,G.L+16,y+22);ctx.restore();}
function gate(now){const x=G.gateX;ctx.save();const g=ctx.createLinearGradient(0,0,0,H);g.addColorStop(0,'#38bdf800');g.addColorStop(.5,'#38bdf8');g.addColorStop(1,'#38bdf800');
 ctx.strokeStyle=g;ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(x,10);ctx.lineTo(x,H-10);ctx.stroke();
 const y=H/2+Math.sin(now/600)*(H/2-50);ctx.shadowColor='#38bdf8';ctx.shadowBlur=24;ctx.fillStyle='#7dd3fc';ctx.beginPath();ctx.arc(x,y,5,0,7);ctx.fill();
 ctx.shadowBlur=0;ctx.fillStyle='#7dd3fc';ctx.font='bold 11px sans-serif';ctx.textAlign='center';ctx.fillText('VALIDATOR · '+D.rules+' CHECKS',x,18);ctx.restore();}
function finish(){done=true;const v=document.getElementById('verdict');v.textContent=D.verdict;v.style.color=D.color;document.getElementById('sub').textContent=D.sub;
 const ins=document.getElementById('ins');document.getElementById('it').textContent=D.insight.title;document.getElementById('ib').textContent=D.insight.body;document.getElementById('ip').textContent=D.insight.tip;document.getElementById('il').textContent=D.insight.lift||'';ins.style.top=(cv.offsetTop+64)+'px';ins.classList.add('on');
 const arc=document.getElementById('arc'),gn=document.getElementById('gnum');arc.style.stroke=D.color;const s=performance.now();
 (function a(){const p=Math.min(1,(performance.now()-s)/1300),e=1-Math.pow(1-p,3);gn.textContent=Math.round(D.score*e);arc.style.strokeDashoffset=314*(1-D.score/100*e);if(p<1)requestAnimationFrame(a);})();}
function frame(now){ctx.clearRect(0,0,W,H);
 ctx.fillStyle='#ffffff0c';const off=(now/50)%38;for(let x=-38+off;x<W;x+=38)for(let y=10;y<H;y+=38){ctx.fillRect(x,y,2,2);}
 if(!done){ctx.save();ctx.setLineDash([7,11]);ctx.lineDashOffset=-now/35;ctx.strokeStyle='#38bdf855';ctx.lineWidth=2;ctx.beginPath();ctx.moveTo(G.srcX,G.mid);ctx.lineTo(G.gateX,G.mid);ctx.stroke();ctx.restore();}
 let sp=0;for(const it of items){if(now-t0-it.spawn>=0)sp++;}
 for(let k=0;k<Math.min(N-sp,24);k++){ctx.fillStyle='#64748b';ctx.beginPath();ctx.arc(26+(k%3)*(G.r*1.6+4),G.mid+34+Math.floor(k/3)*(G.r*1.6+4),Math.max(3,G.r*.6),0,7);ctx.fill();}
 lane(14,H/2-22,PASS,'CLEAN · safe to load');lane(H/2+8,H/2-22,'#f43f5e','QUARANTINE · held for review');
 ctx.fillStyle='#94a3b8';ctx.font='12px sans-serif';ctx.textAlign='left';ctx.fillText('INCOMING · '+N+' records',16,H/2-46);gate(now);
 let p=0,b=0;
 for(const it of items){const s=pos(it,now);it.cur=s;if(!s)continue;if(s.st===3)it.rc.ok?p++:b++;
  if(s.st<=2){for(let k=4;k>=1;k--){const q=pos(it,now-k*38);if(q&&q.st<3){ctx.globalAlpha=.16*(5-k)/4;ctx.fillStyle=s.st<=1?'#93c5fd':it.col;ctx.beginPath();ctx.arc(q.x,q.y,it.r*(1-k*.12),0,7);ctx.fill();}}ctx.globalAlpha=1;}
  const c=s.st<=1?'#93c5fd':it.col;ctx.save();ctx.shadowColor=c;ctx.shadowBlur=s.st===3?6:18;ctx.fillStyle=c;ctx.beginPath();ctx.arc(s.x,s.y,it.r,0,7);ctx.fill();ctx.restore();
  if(it.r>=8){ctx.save();ctx.fillStyle='#06101f';ctx.font='bold '+(it.r-1)+'px sans-serif';ctx.textAlign='center';ctx.textBaseline='middle';ctx.fillText(String(it.rc.id),s.x,s.y+.5);ctx.restore();}
  if(s.st===1){ctx.save();ctx.strokeStyle=it.col;ctx.globalAlpha=1-s.t/pause;ctx.lineWidth=2;ctx.beginPath();ctx.arc(G.gateX,G.mid,10+s.t/5,0,7);ctx.stroke();ctx.restore();}}
 document.getElementById('cp').textContent=p;document.getElementById('cb').textContent=b;
 if(!done&&p+b===N)finish();requestAnimationFrame(frame);}
cv.addEventListener('mousemove',e=>{const r=cv.getBoundingClientRect(),x=e.clientX-r.left,y=e.clientY-r.top;let hit=null;
 for(const it of items){if(it.cur&&Math.hypot(it.cur.x-x,it.cur.y-y)<it.r+5)hit=it;}
 if(!hit){tip.style.opacity=0;return;}
 tip.innerHTML=hit.rc.ok?'<b>Record #'+esc(hit.rc.id)+'</b><br>Passed all checks':'<b>Record #'+esc(hit.rc.id)+' · '+esc(hit.rc.sev)+'</b><br>'+esc(hit.rc.reason);
 tip.style.left=Math.min(x+14,W-250)+'px';tip.style.top=(y+cv.offsetTop+14)+'px';tip.style.opacity=1;});
cv.addEventListener('mouseleave',()=>tip.style.opacity=0);
document.getElementById('replay').onclick=()=>{t0=performance.now();done=false;document.getElementById('ins').classList.remove('on');document.getElementById('verdict').textContent='Analysing...';document.getElementById('verdict').style.color='#f1f5f9';
 document.getElementById('sub').textContent='Checking '+N+' records against '+D.rules+' checks';document.getElementById('gnum').textContent='--';document.getElementById('arc').style.strokeDashoffset=314;};
document.getElementById('sub').textContent='Checking '+N+' records against '+D.rules+' checks';
window.addEventListener('resize',layout);layout();requestAnimationFrame(frame);
</script></body></html>
'''

# ---- animated pipeline stage ----
sev_by_id = {r["id"]: worst(es).severity.name for r, es in rep.quarantined}
TIP = {"Wrong format": "Trim and lowercase emails. Auto-fix does this for you.", "Missing value": "Ask the source system for the missing value.",
       "Impossible value": "Empty the value and flag it for review.", "Duplicate": "Keep the first record, drop the rest. Auto-fix does this."}
tk = pd.Series([KIND[type(worst(es)).__name__] for _, es in rep.quarantined]).value_counts()
s1 = score(rep_clean, len(cleaned))
lift = f"🪄 Auto-fix could raise your score from {s} to {s1}." if (not autoclean and s1 > s) else ""
insight = ({"title": f"Top problem: {tk.index[0]}", "body": f"{tk.iloc[0]} of {n} records affected. Only {round(100 * ok / n) if n else 100}% of records are clean.", "tip": "💡 " + TIP[tk.index[0]], "lift": lift}
           if len(tk) else {"title": "All clear", "body": f"All {n} records passed every check.", "tip": "💡 Safe to load into your database."})
payload = {"insight": insight, "recs": [{"id": r["id"], "ok": r["id"] not in reasons, "sev": sev_by_id.get(r["id"], ""), "reason": reasons.get(r["id"], "")} for r in recs[:150]],
           "score": s, "color": col, "verdict": verdict, "rules": len(rules) + (1 if uniq else 0),
           "sub": f"{bad} of {n} records held back. Only {ok} clean record(s) are safe to load."}
doc = VIEW_HTML.replace("#38bdf8", acc).replace("#7dd3fc", accl).replace("#1e3a8a55", acc + "33").replace("#0e749040", acc2 + "26").replace("__DATA__", json.dumps(payload, default=str).replace("</", "<\\/"))
if hasattr(st, "iframe"): st.iframe(doc, height=590)
else: components.html(doc, height=590, scrolling=False)
if autoclean: st.caption(f"🪄 Auto-fix is ON: {len(clog)} safe fix(es) applied before checking.")

ecount = pd.Series([type(e).__name__ for _, es in rep.quarantined for e in es], dtype=object).value_counts().to_dict()
cnt = rep.summary()["errors_by_severity"]

# ---- AI ----
def ai(prompt):
    key = os.environ.get("ANTHROPIC_API_KEY")
    try: key = key or st.secrets["ANTHROPIC_API_KEY"]
    except Exception: pass
    if not key: return None
    ctx = (f"Dataset: {n} records, {ok} passed, {bad} blocked, health score {s}/100.\nBlocked records:\n" +
           "\n".join(f"- #{i}: {t}" for i, t in reasons.items()))
    try:
        r = requests.post("https://api.anthropic.com/v1/messages", timeout=45,
            headers={"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"},
            json={"model": "claude-sonnet-5-5", "max_tokens": 700,
                  "system": "You are a data quality analyst talking to a non-technical business client. Be concise, plain English, no jargon, use short bullets.",
                  "messages": [{"role": "user", "content": f"{ctx}\n\n{prompt}"}]})
        return r.json()["content"][0]["text"]
    except Exception:
        return None

def offline_report():
    if not bad: return "All records passed every check. Nothing needs attention."
    top = pd.Series([KIND[type(worst(es)).__name__] for _, es in rep.quarantined]).value_counts()
    return (f"**{bad} of {n} records** were held back. Most common problem: **{top.index[0]}** ({top.iloc[0]}).\n\n" +
            "\n".join(f"- Record #{i}: {t}" for i, t in reasons.items()) +
            "\n\n**Suggested next step:** turn on *Auto-fix safe problems*, then send the remaining records back to the data owner.")


def build_report():
    css = "body{font-family:Segoe UI,Arial,sans-serif;margin:40px;color:#0f172a}h1{margin:0}table{border-collapse:collapse;width:100%;margin:12px 0}td,th{border:1px solid #e2e8f0;padding:8px;text-align:left;font-size:14px}th{background:#f1f5f9}.k{display:inline-block;margin:0 12px 12px 0;padding:10px 16px;border:1px solid #e2e8f0;border-radius:10px}.k b{font-size:24px;display:block}.muted{color:#64748b;font-size:13px}"
    trs = "".join(f"<tr><td>#{r['id']}</td><td>{html.escape(reasons[r['id']])}</td><td>{html.escape('; '.join(ACTION[type(e).__name__] for e in es))}</td></tr>" for r, es in rep.quarantined) or "<tr><td colspan=3>No blocked records</td></tr>"
    ruls = "".join(f"<tr><td>{l}</td><td>{ecount.get(k, 0)} failed</td></tr>" for l, k, on in [("Email is required", "MissingValueError", need), ("Email looks valid", "FormatError", fmt), ("Email is unique", "DuplicateRecordError", uniq), ("Age within range", "RangeError", True)] if on)
    who_ = f" for {html.escape(client)}" if client else ""
    return (f"<!doctype html><html><head><meta charset='utf-8'><title>Data Quality Report</title><style>{css}</style></head><body>"
            f"<h1>Data Quality Report{who_}</h1><p class='muted'>Generated {datetime.date.today().strftime('%d %b %Y')}</p>"
            f"<h2>{verdict}</h2><div class='k'><b>{s}/100</b>health score</div><div class='k'><b>{n}</b>records</div>"
            f"<div class='k'><b>{ok}</b>passed</div><div class='k'><b>{bad}</b>blocked</div>"
            f"<h3>Blocked records and recommended actions</h3><table><tr><th>Record</th><th>Problem</th><th>Recommended action</th></tr>{trs}</table>"
            f"<h3>Rule results</h3><table><tr><th>Rule</th><th>Result</th></tr>{ruls}</table>"
            f"<p class='muted'>Tip: open this file in your browser and press Ctrl+P, then Save as PDF.</p></body></html>")

with st.sidebar:
    st.divider()
    st.download_button("📄 Download report", build_report(), "data_quality_report.html", "text/html", help="A shareable report. Open it and press Ctrl+P to save as PDF.")

t0, tr, t1, t2, t3, t4 = st.tabs(["🤖 AI assistant", "📊 Rules & severity", "🔎 Why was it blocked?", "🪄 Fix it for me", "🗄️ Database checks", "📄 All records"])

with t0:
    st.caption("Get a plain-English report, or ask anything about this data. Great for sharing with non-technical teammates.")
    q = st.text_input("Ask a question", placeholder="e.g. What should we fix first, and why?")
    if st.button("✨ Generate report" if not q else "✨ Ask AI", type="primary"):
        with st.spinner("Analysing your data..."):
            out = ai(q or "Write a short report: what went wrong, how serious it is, and the top 3 actions to fix it.")
        if out: st.markdown(out)
        else:
            st.info("AI is not connected (no API key), so this is the built-in summary.")
            st.markdown(offline_report())

with tr:
    st.caption("How each rule performed, and how serious the problems are. Counts problems, not records: one record can have several.")
    for label, key, on in [("Email is required", "MissingValueError", need), ("Email looks valid", "FormatError", fmt),
                           ("Email is unique", "DuplicateRecordError", uniq), ("Age within range", "RangeError", True)]:
        if on:
            f = ecount.get(key, 0); pct = round(100 * (1 - f / n)) if n else 100
            st.progress(pct / 100, text=f"{label}: {pct}% pass, {f} failed")
    st.markdown(f"🟡 Low: **{cnt.get('LOW', 0)}** (logged, record still passes) · 🟠 Medium: **{cnt.get('MEDIUM', 0)}** (held back) · 🔴 High: **{cnt.get('HIGH', 0)}** (held back, urgent) · ⛔ Critical stops the pipeline")

with t1:
    st.caption("Pick a blocked record to see the exact reason and what we recommend.")
    if not rep.quarantined: st.success("Nothing was blocked. 🎉")
    else:
        pick = st.selectbox("Blocked record", [r["id"] for r, _ in rep.quarantined], format_func=lambda i: f"Record #{i}")
        rec, errs = next(x for x in rep.quarantined if x[0]["id"] == pick)
        l, r = st.columns([1, 2])
        l.dataframe(pd.DataFrame([rec]).T.rename(columns={0: "value"}).astype(str), width="stretch")
        for e in errs:
            nm = type(e).__name__
            r.markdown(f"**{e.severity.name}**: {WHY[nm].format(f=e.field_name.capitalize())}  \n➡️ *{ACTION[nm]}*")

with t2:
    st.caption("We only fix what we're sure about, and never invent missing data.")
    s0, s1 = score(rep_raw, len(raw)), score(rep_clean, len(cleaned))
    m = st.columns(3)
    m[0].metric("Score before", s0); m[1].metric("Score after auto-fix", s1, s1 - s0)
    m[2].metric("Blocked records", len(rep_clean.quarantined), len(rep_clean.quarantined) - len(rep_raw.quarantined), delta_color="inverse")
    st.dataframe(pd.DataFrame(clog, columns=["Record", "What we fixed"]), width="stretch", hide_index=True)
    st.download_button("⬇️ Download cleaned data (CSV)", pd.DataFrame(cleaned).to_csv(index=False), "cleaned.csv", "text/csv")

with t3:
    st.caption("The same checks as SQL, so they can run directly inside your database.")
    conn = sqlite3.connect(":memory:"); pd.DataFrame(recs).to_sql("users", conn, index=False)
    LABEL = {"null_or_empty_emails": "Records with a missing email", "duplicate_emails": "Emails that appear more than once", "age_out_of_range": "Impossible ages"}
    for name, rows in run_sql_checks(conn, os.path.join(HERE, "queries.sql")).items():
        (st.success if not rows else st.warning)(f"{'✅' if not rows else '⚠️'} {LABEL.get(name, name)}: {len(rows)} found")
        if rows: st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)

with t4:
    l, r = st.columns(2)
    l.markdown("**✅ Passed**"); l.dataframe(pd.DataFrame(rep.valid), width="stretch", hide_index=True)
    qd = pd.DataFrame([{**x, "reason": reasons[x["id"]]} for x, _ in rep.quarantined])
    r.markdown("**🚫 Blocked**"); r.dataframe(qd, width="stretch", hide_index=True)
    if not qd.empty: r.download_button("⬇️ Download blocked records", qd.to_csv(index=False), "blocked.csv", "text/csv")