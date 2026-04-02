import streamlit as st
import streamlit.components.v1 as components
import requests, math, json
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

st.set_page_config(page_title="Artemis II Mission Control", layout="wide",
                   page_icon="🛰️")

AU_TO_KM   = 149597870.7
KM_TO_MI   = 0.621371
SEC_PER_AU = AU_TO_KM / 299792.458
LAUNCH_DATE = datetime(2026, 4, 1, 19, 24)   # ~3:24 PM EDT = 19:24 UTC

# ── Helper functions ──────────────────────────────────────────────────────────
def horizons_query(command):
    now  = datetime.utcnow()
    stop = now + timedelta(minutes=1)
    r = requests.get("https://ssd.jpl.nasa.gov/api/horizons.api", params={
        "format":"text","COMMAND":f"'{command}'","OBJ_DATA":"'NO'",
        "MAKE_EPHEM":"'YES'","EPHEM_TYPE":"'OBSERVER'","CENTER":"'500@399'",
        "START_TIME":f"'{now.strftime('%Y-%m-%d %H:%M')}'",
        "STOP_TIME":f"'{stop.strftime('%Y-%m-%d %H:%M')}'",
        "STEP_SIZE":"'1m'","QUANTITIES":"'1,20'",
        "CSV_FORMAT":"'YES'","ANG_FORMAT":"'DEG'","RANGE_UNITS":"'AU'",
    }, timeout=20)
    r.raise_for_status()
    return r.text

def parse_horizons(raw):
    lines = raw.splitlines()
    soe   = next(i for i,l in enumerate(lines) if "$$SOE" in l)
    hdr   = next(lines[i] for i in range(soe-1,-1,-1) if lines[i].count(",")>=4)
    return dict(zip([h.strip() for h in hdr.split(",")],
                    [v.strip() for v in lines[soe+1].split(",")]))

def find(d,*keys):
    lc={k.lower():k for k in d}
    for k in keys:
        if k.lower() in lc: return lc[k.lower()]
    return None

def flt(d,col):
    if col and col in d:
        try: return float(d[col].replace("n.a.","").strip())
        except: pass
    return None

def to_xyz_km(delta_au, ra_deg, dec_deg):
    ra,dec = math.radians(ra_deg), math.radians(dec_deg)
    d = delta_au * AU_TO_KM
    return [d*math.cos(dec)*math.cos(ra), d*math.cos(dec)*math.sin(ra), d*math.sin(dec)]

# ── Data fetchers (cached) ────────────────────────────────────────────────────
@st.cache_data(ttl=60)
def fetch_positions():
    return horizons_query("-1024"), horizons_query("301")

@st.cache_data(ttl=120)
def fetch_space_weather():
    results = {}
    endpoints = {
        "kp":     "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",
        "wind":   "https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json",
        "xray":   "https://services.swpc.noaa.gov/json/goes/primary/xrays-6-hour.json",
        "proton": "https://services.swpc.noaa.gov/json/goes/primary/integral-protons-6-hour.json",
        "alerts": "https://services.swpc.noaa.gov/products/alerts.json",
    }
    for key, url in endpoints.items():
        try:
            r = requests.get(url, timeout=10)
            results[key] = r.json()
        except:
            results[key] = None
    return results

@st.cache_data(ttl=300)
def fetch_nasa_news():
    try:
        r = requests.get("https://www.nasa.gov/news-release/feed/", timeout=10)
        root = ET.fromstring(r.content)
        items = []
        for item in root.findall(".//item")[:5]:
            t = item.find("title")
            l = item.find("link")
            d = item.find("pubDate")
            desc_el = item.find("description")
            desc = desc_el.text if desc_el is not None else ""
            # Strip HTML tags from description
            import re
            desc = re.sub(r"<[^>]+>","",desc or "")[:200]
            items.append({
                "title": t.text if t is not None else "—",
                "link":  l.text if l is not None else "#",
                "date":  d.text[:16] if d is not None else "",
                "desc":  desc,
            })
        return items
    except:
        return []

# ── Parse space weather ───────────────────────────────────────────────────────
def parse_sw(sw):
    result = {}

    # Kp index
    try:
        kp_data = [x for x in sw["kp"] if x.get("kp_index") is not None]
        if kp_data:
            result["kp"] = float(kp_data[-1]["kp_index"])
    except: result["kp"] = None

    # Solar wind
    try:
        wind = [x for x in sw["wind"] if x.get("proton_speed") is not None]
        if wind:
            w = wind[-1]
            result["wind_speed"]   = float(w.get("proton_speed",   0))
            result["wind_density"] = float(w.get("proton_density", 0))
            result["bz"]           = float(w.get("bz_gsm",         0))
    except: result["wind_speed"] = result["wind_density"] = result["bz"] = None

    # X-ray flux → flare class
    try:
        long  = [x for x in sw["xray"] if "0.1-0.8" in str(x.get("energy",""))]
        if long:
            flux = float(long[-1]["flux"])
            if   flux >= 1e-4: cls, cls_val = "X", flux/1e-4
            elif flux >= 1e-5: cls, cls_val = "M", flux/1e-5
            elif flux >= 1e-6: cls, cls_val = "C", flux/1e-6
            elif flux >= 1e-7: cls, cls_val = "B", flux/1e-7
            else:               cls, cls_val = "A", flux/1e-8
            result["xray_class"] = f"{cls}{cls_val:.1f}"
            result["xray_flux"]  = flux
    except: result["xray_class"] = result["xray_flux"] = None

    # Proton flux (>10 MeV) → radiation / S-scale
    try:
        p10 = [x for x in sw["proton"] if ">10" in str(x.get("energy",""))]
        if p10:
            pf = float(p10[-1]["flux"])
            result["proton_flux"] = pf
            if   pf >= 100000: result["s_scale"] = ("S5","Extreme",  "#ff0000")
            elif pf >= 10000:  result["s_scale"] = ("S4","Severe",   "#ff4400")
            elif pf >= 1000:   result["s_scale"] = ("S3","Strong",   "#ff8800")
            elif pf >= 100:    result["s_scale"] = ("S2","Moderate", "#ffcc00")
            elif pf >= 10:     result["s_scale"] = ("S1","Minor",    "#ffff00")
            else:              result["s_scale"] = ("--","Normal",   "#00cc44")
        else:
            result["proton_flux"] = None; result["s_scale"] = ("--","Normal","#00cc44")
    except: result["proton_flux"] = None; result["s_scale"] = ("--","Normal","#00cc44")

    # Active alerts (first 3)
    try:
        result["alerts"] = [a.get("message","")[:120] for a in (sw["alerts"] or [])[:3]]
    except: result["alerts"] = []

    return result

# ── Mission phase from distance ───────────────────────────────────────────────
def mission_phase(dist_km, moon_km):
    if dist_km is None: return "Unknown"
    pct = dist_km / (moon_km or 384400) * 100
    if   pct <  5:  return "🚀 Earth Departure / TLI"
    elif pct < 40:  return "🌌 Trans-Lunar Coast"
    elif pct < 75:  return "🌌 Mid-Course Coast"
    elif pct < 92:  return "🌙 Lunar Approach"
    elif pct < 108: return "🌙 Lunar Proximity"
    else:           return "🌍 Return Coast"

# ═══════════════════════════════════════════════════════════════════════════════
# FETCH ALL DATA
# ═══════════════════════════════════════════════════════════════════════════════
fetch_err = None
try:
    raw_orion, raw_moon = fetch_positions()
    orion = parse_horizons(raw_orion)
    moon  = parse_horizons(raw_moon)

    delta_au   = flt(orion, find(orion,"delta"))
    deldot     = flt(orion, find(orion,"deldot"))
    ra_deg     = flt(orion, find(orion,"R.A._(ICRF)","RA_(ICRF)","RA"))
    dec_deg    = flt(orion, find(orion,"DEC_(ICRF)","DEC"))
    moon_delta = flt(moon,  find(moon, "delta"))
    moon_ra    = flt(moon,  find(moon, "R.A._(ICRF)","RA_(ICRF)","RA"))
    moon_dec   = flt(moon,  find(moon, "DEC_(ICRF)","DEC"))

    dist_km      = delta_au   * AU_TO_KM  if delta_au   else None
    dist_mi      = dist_km    * KM_TO_MI  if dist_km    else None
    vel_kms      = abs(deldot)            if deldot     else None
    vel_mis      = vel_kms    * KM_TO_MI  if vel_kms    else None
    lt_sec       = delta_au   * SEC_PER_AU if delta_au  else None
    moon_km      = moon_delta * AU_TO_KM  if moon_delta else 384400
    moon_mi      = moon_km    * KM_TO_MI
    pct_moon     = (dist_km/moon_km*100)  if (dist_km and moon_km) else None
    alt_km       = (dist_km - 6371)       if dist_km    else None
    alt_mi       = alt_km     * KM_TO_MI  if alt_km     else None

    orion_xyz = to_xyz_km(delta_au, ra_deg, dec_deg)  if (delta_au and ra_deg is not None) else [45000,0,0]
    moon_xyz  = to_xyz_km(moon_delta, moon_ra, moon_dec) if (moon_delta and moon_ra is not None) else [384400,0,0]

    mission_day  = max(1, (datetime.utcnow() - LAUNCH_DATE).days + 1)
    phase        = mission_phase(dist_km, moon_km)

    fetch_ok = True
except Exception as e:
    fetch_ok = False; fetch_err = str(e)
    dist_km=dist_mi=vel_kms=vel_mis=lt_sec=moon_km=moon_mi=pct_moon=alt_km=alt_mi=None
    orion_xyz=[45000,0,0]; moon_xyz=[384400,0,0]
    mission_day=1; phase="Unknown"; moon_km=384400

sw_raw  = fetch_space_weather()
sw      = parse_sw(sw_raw)
news    = fetch_nasa_news()

payload = {
    "orionDistKm": dist_km or 0,  "orionDistMi": dist_mi or 0,
    "orionKmS":    vel_kms or 0,  "orionMiS":    vel_mis or 0,
    "ltSec":       lt_sec or 0,   "pctToMoon":   pct_moon or 0,
    "moonDistKm":  moon_km,       "orionPos":    orion_xyz,
    "moonPos":     moon_xyz,
}

# ═══════════════════════════════════════════════════════════════════════════════
# UI
# ═══════════════════════════════════════════════════════════════════════════════

# ── Header ────────────────────────────────────────────────────────────────────
c1,c2,c3 = st.columns([5,2,1])
with c1:
    st.title("🛰️ Artemis II: Mission Control")
    st.caption(f"**Mission Day {mission_day}** &nbsp;·&nbsp; {phase} &nbsp;·&nbsp; "
               f"Data: JPL Horizons · NOAA SWPC · NASA")
with c2:
    elapsed = datetime.utcnow() - LAUNCH_DATE
    h,rem   = divmod(int(elapsed.total_seconds()), 3600)
    m,s     = divmod(rem,60)
    st.metric("Mission Elapsed Time", f"{h:03d}:{m:02d}:{s:02d}")
with c3:
    st.info("**by: Rogue.tinker**")

if not fetch_ok:
    st.error(f"Horizons error: {fetch_err}")

st.markdown("---")

# ── Orbital metrics ───────────────────────────────────────────────────────────
m1,m2,m3,m4 = st.columns(4)
m1.metric("Distance from Earth", f"{dist_km:,.0f} km" if dist_km else "n/a", f"{dist_mi:,.0f} mi" if dist_mi else "")
m2.metric("Velocity",            f"{vel_kms:.3f} km/s" if vel_kms else "n/a", f"{vel_mis:.3f} mi/s" if vel_mis else "")
m3.metric("Altitude above Earth",f"{alt_km:,.0f} km" if alt_km else "n/a",   f"{alt_mi:,.0f} mi"  if alt_mi  else "")
m4.metric("Light Travel Time",   f"{lt_sec:.2f} sec" if lt_sec else "n/a")

n1,n2,n3,n4 = st.columns(4)
n1.metric("Moon Distance (live)",f"{moon_km:,.0f} km", f"{moon_mi:,.0f} mi")
n2.metric("Journey to Moon",     f"{pct_moon:.1f}%" if pct_moon else "n/a")
n3.metric("RA / Dec",            f"{ra_deg:.3f}° / {dec_deg:.3f}°" if (fetch_ok and ra_deg is not None) else "n/a")
n4.metric("Mission Day",         f"Day {mission_day}")

if pct_moon:
    st.progress(min(pct_moon/100,1.0), text=f"🌙 {pct_moon:.1f}% of the way to the Moon")

st.markdown("---")

# ── Three.js scene ────────────────────────────────────────────────────────────
THREE_HTML = """<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:600px;background:#000;overflow:hidden;font-family:'Courier New',monospace}
#container{width:100%;height:600px;position:relative}
canvas{display:block}
#hud{position:absolute;top:12px;right:12px;background:rgba(2,10,25,0.85);
     border:1px solid rgba(80,160,255,0.22);border-radius:10px;padding:12px 16px;
     color:#90c8f0;font-size:11px;line-height:2;backdrop-filter:blur(6px);min-width:210px}
.hl{color:#3a7aaa;font-size:9px;text-transform:uppercase;letter-spacing:1.5px;margin-top:4px}
.hv{color:#e8f4ff;font-size:14px;font-weight:bold}.hs{color:#5a9abb;font-size:11px}
.sep{border:none;border-top:1px solid rgba(80,160,255,0.15);margin:5px 0}
#tag{position:absolute;top:12px;left:12px;color:rgba(120,180,255,0.38);
     font-size:10px;letter-spacing:1.8px;line-height:1.8;pointer-events:none}
#hint{position:absolute;bottom:8px;left:50%;transform:translateX(-50%);
      color:rgba(120,180,255,0.28);font-size:10px;letter-spacing:1px;pointer-events:none}
</style></head><body>
<div id="container"><canvas id="c"></canvas>
<div id="tag">JPL HORIZONS · ARTEMIS II · (-1024)<br>EARTH GEOCENTER 500@399 · LIVE</div>
<div id="hud">
  <div class="hl">Distance</div><div class="hv" id="hd"></div><div class="hs" id="hdmi"></div>
  <hr class="sep">
  <div class="hl">Velocity</div><div class="hv" id="hv"></div><div class="hs" id="hvmi"></div>
  <hr class="sep">
  <div class="hl">Light Travel</div><div class="hv" id="hl"></div>
  <hr class="sep">
  <div class="hl">Moon Progress</div><div class="hv" id="hm"></div>
</div>
<div id="hint">drag · scroll · auto-orbits</div></div>
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script>
__DATA__
const W=document.getElementById('container').clientWidth||900,H=600;
const ER=6.371,MR=1.737,S=1/1000;
const op=DATA.orionPos.map(v=>v*S),mp=DATA.moonPos.map(v=>v*S);
const od=DATA.orionDistKm*S,md=DATA.moonDistKm*S;
const renderer=new THREE.WebGLRenderer({canvas:document.getElementById('c'),antialias:true});
renderer.setSize(W,H);renderer.setPixelRatio(Math.min(window.devicePixelRatio,2));
const scene=new THREE.Scene(),camera=new THREE.PerspectiveCamera(50,W/H,.001,200000);
scene.add(new THREE.AmbientLight(0x0d1a3a,1.2));
const sl=new THREE.DirectionalLight(0xfff8e0,2.2);sl.position.set(1000,300,600);scene.add(sl);
// Stars
(()=>{const N=7000,p=new Float32Array(N*3),c=new Float32Array(N*3),
  sc=[[1,1,1],[.8,.9,1],[1,.95,.85],[.85,.85,1]];
  for(let i=0;i<N;i++){const r=12000+(i%300)*8,t=i*2.399963,
    phi=Math.acos(1-2*(i+.5)/N);
    p[i*3]=r*Math.sin(phi)*Math.cos(t);p[i*3+1]=r*Math.sin(phi)*Math.sin(t);p[i*3+2]=r*Math.cos(phi);
    const s=sc[i%4];c[i*3]=s[0];c[i*3+1]=s[1];c[i*3+2]=s[2];}
  const g=new THREE.BufferGeometry();
  g.setAttribute('position',new THREE.BufferAttribute(p,3));
  g.setAttribute('color',new THREE.BufferAttribute(c,3));
  scene.add(new THREE.Points(g,new THREE.PointsMaterial({size:2.5,sizeAttenuation:false,vertexColors:true,transparent:true,opacity:.85})));
})();
function glow(r,g,b,sz,op){const c=document.createElement('canvas');c.width=c.height=256;
  const cx=c.getContext('2d'),gr=cx.createRadialGradient(128,128,0,128,128,128);
  gr.addColorStop(0,`rgba(${r},${g},${b},1)`);gr.addColorStop(.2,`rgba(${r},${g},${b},.6)`);
  gr.addColorStop(.5,`rgba(${r},${g},${b},.2)`);gr.addColorStop(1,`rgba(${r},${g},${b},0)`);
  cx.fillStyle=gr;cx.fillRect(0,0,256,256);
  const sp=new THREE.Sprite(new THREE.SpriteMaterial({map:new THREE.CanvasTexture(c),
    blending:THREE.AdditiveBlending,depthWrite:false,transparent:true,opacity:op}));
  sp.scale.set(sz,sz,1);return sp;}
// Sun
const sg1=glow(255,245,180,1200,.7);sg1.position.set(1000,300,600);scene.add(sg1);
const sg2=glow(255,210,80,380,.9);sg2.position.set(1000,300,600);scene.add(sg2);
// Earth
function eTex(){const c=document.createElement('canvas');c.width=1024;c.height=512;
  const cx=c.getContext('2d'),og=cx.createLinearGradient(0,0,0,512);
  og.addColorStop(0,'#0d3d5e');og.addColorStop(.5,'#1565a0');og.addColorStop(1,'#0d3d5e');
  cx.fillStyle=og;cx.fillRect(0,0,1024,512);
  cx.fillStyle='#1e6b35';
  [[170,90,88,80,-.15],[155,160,75,65,.1],[195,230,28,42,.05],
   [228,295,50,55,.08],[215,355,55,75,.1],[487,105,52,48,0],[465,130,30,35,.1],
   [490,245,60,55,.05],[478,320,55,80,.05],[660,100,155,90,-.1],[700,175,100,65,.1],
   [580,90,70,55,.05],[633,220,28,48,.1],[755,210,38,28,.25],[788,340,62,42,.08]
  ].forEach(([x,y,rx,ry,rot])=>{cx.save();cx.translate(x,y);cx.rotate(rot);
    cx.beginPath();cx.ellipse(0,0,rx,ry,0,0,Math.PI*2);cx.fill();cx.restore();});
  cx.fillStyle='#a8d0e0';cx.beginPath();cx.ellipse(272,68,33,42,0,0,Math.PI*2);cx.fill();
  const ic=cx.createLinearGradient(0,0,0,38);ic.addColorStop(0,'#ddf0f8');ic.addColorStop(1,'rgba(200,232,244,0)');
  cx.fillStyle=ic;cx.fillRect(0,0,1024,38);
  const ia=cx.createLinearGradient(0,475,0,512);ia.addColorStop(0,'rgba(200,232,244,0)');ia.addColorStop(1,'#c8e8f4');
  cx.fillStyle=ia;cx.fillRect(0,475,1024,37);
  cx.fillStyle='rgba(255,255,255,.2)';
  [[80,175,165,22],[290,95,190,18],[445,195,155,20],[595,155,185,17],
   [710,295,210,19],[140,345,160,21],[845,175,155,17],[375,375,195,17]
  ].forEach(([x,y,rx,ry])=>{cx.beginPath();cx.ellipse(x,y,rx,ry,0,0,Math.PI*2);cx.fill();});
  return new THREE.CanvasTexture(c);}
function nTex(){const c=document.createElement('canvas');c.width=512;c.height=256;
  const cx=c.getContext('2d');cx.fillStyle='#000008';cx.fillRect(0,0,512,256);
  cx.fillStyle='rgba(255,210,80,.95)';
  [{x:88,y:77,pts:[[0,0],[5,3],[-3,5],[8,-2],[3,8],[-6,2],[10,5],[-8,8]]},
   {x:244,y:60,pts:[[0,0],[4,2],[-2,4],[6,-1],[2,6],[-4,1],[7,3]]},
   {x:378,y:72,pts:[[0,0],[5,3],[-3,5],[7,-2],[2,7],[-5,2]]},
   {x:318,y:110,pts:[[0,0],[4,2],[-2,3],[5,-1],[1,5]]},
   {x:262,y:100,pts:[[0,0],[3,2],[-2,3],[4,-1],[1,4]]}
  ].forEach(cl=>cl.pts.forEach(([dx,dy])=>{
    cx.beginPath();cx.arc(cl.x+dx,cl.y+dy,1,0,Math.PI*2);cx.fill();}));
  return new THREE.CanvasTexture(c);}
const earth=new THREE.Mesh(new THREE.SphereGeometry(ER,72,72),
  new THREE.MeshPhongMaterial({map:eTex(),emissiveMap:nTex(),
    emissive:new THREE.Color(1,1,1),emissiveIntensity:.35,
    specular:new THREE.Color(.15,.3,.5),shininess:35}));
scene.add(earth);
[{s:1.035,op:.10,c:0x5599ff},{s:1.065,op:.055,c:0x3377ee},{s:1.10,op:.025,c:0x2255cc}].forEach(({s,op,c})=>{
  const m=new THREE.MeshPhongMaterial({color:c,transparent:true,opacity:op,
    side:THREE.FrontSide,depthWrite:false,blending:THREE.AdditiveBlending});
  scene.add(new THREE.Mesh(new THREE.SphereGeometry(ER*s,32,32),m));});
const eg=glow(80,150,255,ER*9,.45);scene.add(eg);
// Moon
function mTex(){const c=document.createElement('canvas');c.width=512;c.height=256;
  const cx=c.getContext('2d');cx.fillStyle='#7a8190';cx.fillRect(0,0,512,256);
  cx.fillStyle='rgba(50,55,65,.65)';
  [[115,78,58,38],[195,115,78,48],[295,88,68,43],[374,136,52,33],[98,155,88,52],[245,165,62,38]
  ].forEach(([x,y,rx,ry])=>{cx.beginPath();cx.ellipse(x,y,rx,ry,0,0,Math.PI*2);cx.fill();});
  cx.fillStyle='rgba(170,178,195,.35)';
  [[175,58,38,23],[315,55,32,20],[410,76,28,18]
  ].forEach(([x,y,rx,ry])=>{cx.beginPath();cx.ellipse(x,y,rx,ry,0,0,Math.PI*2);cx.fill();});
  [[140,55,12],[78,178,8],[355,112,6],[422,68,9]].forEach(([x,y,r])=>{
    cx.strokeStyle='rgba(60,65,75,.5)';cx.lineWidth=1.5;
    cx.beginPath();cx.arc(x,y,r,0,Math.PI*2);cx.stroke();});
  return new THREE.CanvasTexture(c);}
const moonMesh=new THREE.Mesh(new THREE.SphereGeometry(MR,48,48),
  new THREE.MeshPhongMaterial({map:mTex(),shininess:8}));
moonMesh.position.set(...mp);scene.add(moonMesh);
const mg=glow(180,188,210,MR*8,.22);mg.position.set(...mp);scene.add(mg);
scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(
  [new THREE.Vector3(0,0,0),new THREE.Vector3(...mp)]),
  new THREE.LineBasicMaterial({color:0x1a3355,transparent:true,opacity:.35})));
// Artemis
const og3=glow(255,90,0,ER*4.5,.25);og3.position.set(...op);scene.add(og3);
const og2=glow(255,150,40,ER*2.2,.50);og2.position.set(...op);scene.add(og2);
const og1=glow(255,230,130,ER*.9,.90);og1.position.set(...op);scene.add(og1);
const oCore=new THREE.Mesh(new THREE.SphereGeometry(ER*.10,12,12),
  new THREE.MeshBasicMaterial({color:0xffffff}));
oCore.position.set(...op);scene.add(oCore);
scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(
  [new THREE.Vector3(0,0,0),new THREE.Vector3(...op)]),
  new THREE.LineBasicMaterial({color:0xff7700,transparent:true,opacity:.65})));
const mag=Math.sqrt(op.reduce((a,v)=>a+v*v,0));
if(mag>0){const u=op.map(v=>v/mag),len=od*.12,tip=op.map((v,i)=>v+u[i]*len);
  scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(
    [new THREE.Vector3(...op),new THREE.Vector3(...tip)]),
    new THREE.LineBasicMaterial({color:0xffee44,transparent:true,opacity:.8})));}
// HUD
function fmt(n,d=0){return n.toLocaleString('en-US',{maximumFractionDigits:d});}
document.getElementById('hd').textContent=fmt(DATA.orionDistKm)+' km';
document.getElementById('hdmi').textContent=fmt(DATA.orionDistMi)+' mi';
document.getElementById('hv').textContent=DATA.orionKmS.toFixed(3)+' km/s';
document.getElementById('hvmi').textContent=DATA.orionMiS.toFixed(3)+' mi/s';
document.getElementById('hl').textContent=DATA.ltSec.toFixed(2)+' sec';
document.getElementById('hm').textContent=DATA.pctToMoon.toFixed(1)+'% to Moon';
// Camera
let drag=false,auto=true,px=0,py=0;
const sr=Math.max(od*5,ER*15);
let sph={r:sr,theta:.5,phi:1.15};
function setCam(){camera.position.set(
  sph.r*Math.sin(sph.phi)*Math.cos(sph.theta),
  sph.r*Math.cos(sph.phi),
  sph.r*Math.sin(sph.phi)*Math.sin(sph.theta));camera.lookAt(0,0,0);}
const el=renderer.domElement;
el.addEventListener('mousedown',e=>{drag=true;auto=false;px=e.clientX;py=e.clientY;});
window.addEventListener('mouseup',()=>drag=false);
window.addEventListener('mousemove',e=>{if(!drag)return;
  sph.theta-=(e.clientX-px)*.007;sph.phi-=(e.clientY-py)*.007;
  sph.phi=Math.max(.04,Math.min(Math.PI-.04,sph.phi));px=e.clientX;py=e.clientY;});
el.addEventListener('wheel',e=>{e.preventDefault();sph.r*=1+e.deltaY*.0008;
  sph.r=Math.max(ER*1.3,Math.min(md*3.5,sph.r));},{passive:false});
let t=0;
function animate(){requestAnimationFrame(animate);t+=.01;
  earth.rotation.y+=.0006;moonMesh.rotation.y+=.0008;
  const p=1+.3*Math.sin(t*2.5);
  og2.scale.set(ER*2.2*p,ER*2.2*p,1);og3.scale.set(ER*4.5*p*.75,ER*4.5*p*.75,1);
  if(auto)sph.theta+=.0025;setCam();renderer.render(scene,camera);}
setCam();animate();
window.addEventListener('resize',()=>{const w=document.getElementById('container').clientWidth||900;
  renderer.setSize(w,H);camera.aspect=w/H;camera.updateProjectionMatrix();});
</script></body></html>"""

components.html(THREE_HTML.replace("__DATA__", f"const DATA={json.dumps(payload)};"),
                height=612, scrolling=False)

st.markdown("---")

# ═══════════════════════════════════════════════════════════════════════════════
# TABS: Live Views | Space Weather | Mission Updates
# ═══════════════════════════════════════════════════════════════════════════════
tab1, tab2, tab3 = st.tabs(["🌍 Live Views", "☀️ Space Weather & Crew Safety", "📡 Mission Updates"])

# ── Tab 1: Live imagery ───────────────────────────────────────────────────────
with tab1:
    iv1, iv2 = st.columns(2)
    with iv1:
        st.subheader("🌍 Earth Right Now")
        st.caption("GOES-16 GeoColor · Full Disk · NOAA/NESDIS · Updates every 10 min")
        try:
            st.image("https://cdn.star.nesdis.noaa.gov/GOES16/ABI/FD/GEOCOLOR/latest.jpg",
                     use_container_width=True)
            st.caption("_This is what astronauts left behind. GOES-16 geostationary satellite, ~35,786 km altitude._")
        except:
            st.warning("GOES-16 image unavailable")

    with iv2:
        st.subheader("☀️ The Sun Right Now")
        st.caption("NASA Solar Dynamics Observatory (SDO) · 193Å AIA · Updates every 15 min")
        try:
            st.image("https://sdo.gsfc.nasa.gov/assets/img/latest/latest_1024_0193.jpg",
                     use_container_width=True)
            st.caption("_SDO AIA 193Å — shows the corona at ~1.5 million °C. Active regions appear bright._")
        except:
            st.warning("SDO image unavailable")

    st.markdown("---")
    st.subheader("🌙 The Moon Right Now")
    st.caption("NASA SDO HMIIC · Visible Light · Destination of Artemis II")
    try:
        st.image("https://svs.gsfc.nasa.gov/vis/a000000/a005000/a005048/frames/730x730_1x1_30p/moon.0001.jpg",
                 width=400)
    except:
        pass
    st.info("📺 **NASA TV Live:** Watch the mission at [nasa.gov/nasalive](https://www.nasa.gov/nasalive) "
            "or [NASA TV on YouTube](https://www.youtube.com/@NASA/live)")

# ── Tab 2: Space Weather ──────────────────────────────────────────────────────
with tab2:
    st.subheader("🛡️ Crew Radiation Environment")
    st.caption("Source: NOAA Space Weather Prediction Center · No API key required · Updates every 2 min")

    s_label, s_color = sw.get("s_scale", ("--","Normal","#00cc44"))[1], sw.get("s_scale",("--","Normal","#00cc44"))[2]
    s_code           = sw.get("s_scale", ("--","Normal","#00cc44"))[0]

    st.markdown(
        f"""<div style="background:rgba(0,0,0,.05);border-left:4px solid {s_color};
        padding:12px 18px;border-radius:6px;margin-bottom:12px">
        <span style="font-size:22px;font-weight:bold;color:{s_color}">{s_code} — {s_label}</span>
        &nbsp;&nbsp;<span style="font-size:13px;color:#888">Solar Radiation Storm Level (NOAA S-Scale)</span>
        </div>""", unsafe_allow_html=True)

    sw1,sw2,sw3,sw4 = st.columns(4)

    kp = sw.get("kp")
    kp_labels = ["Quiet","Quiet","Quiet","Unsettled","Active","Minor Storm","Moderate Storm","Strong Storm","Severe Storm","Extreme"]
    sw1.metric("🌐 Kp Index (Geomagnetic)",
               f"{kp:.1f}" if kp is not None else "n/a",
               kp_labels[min(int(kp),9)] if kp is not None else "")

    sw2.metric("💨 Solar Wind Speed",
               f"{sw.get('wind_speed',0):,.0f} km/s" if sw.get("wind_speed") else "n/a",
               f"Density: {sw.get('wind_density',0):.1f} p/cm³" if sw.get("wind_density") else "")

    sw3.metric("⚡ X-Ray Activity",
               sw.get("xray_class","n/a") or "n/a",
               "Solar flare class")

    pf = sw.get("proton_flux")
    sw4.metric("☢️ Proton Flux (>10 MeV)",
               f"{pf:.1f} pfu" if pf else "n/a",
               "Crew radiation indicator")

    bz = sw.get("bz")
    if bz is not None:
        st.metric("🧲 Bz (Interplanetary Mag Field)", f"{bz:.1f} nT",
                  "Negative = geomagnetic storm driver" if bz < 0 else "Positive = stable")

    # Active alerts
    alerts = sw.get("alerts",[])
    if alerts:
        st.markdown("#### ⚠️ Active Space Weather Alerts")
        for a in alerts:
            st.warning(a[:200])
    else:
        st.success("✅ No active space weather alerts from NOAA SWPC")

    st.markdown("---")
    st.subheader("ℹ️ What's Not Available")
    st.info("""
**Crew biometrics (heart rate, O₂ saturation, temperature, blood pressure)** — monitored
in real-time by Mission Control in Houston but **not released publicly** during the mission.

**Internal ship telemetry (cabin pressure, CO₂ levels, power, propellant)** — same: 
NASA's internal systems only. No public API exists for Orion's onboard sensors.

**Live crew audio/video** — available via NASA TV at key events but not a continuous stream.

These data types would require a direct NASA partnership to access.
    """)

    st.markdown("---")
    st.caption(f"Space weather data from [NOAA SWPC](https://www.swpc.noaa.gov/) · "
               f"Last fetched: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}")

# ── Tab 3: Mission Updates ────────────────────────────────────────────────────
with tab3:
    st.subheader("📰 Latest from NASA")
    st.caption("Source: nasa.gov/news-release/feed")

    if news:
        for item in news:
            with st.container():
                st.markdown(f"**[{item['title']}]({item['link']})**")
                if item["date"]: st.caption(item["date"])
                if item["desc"]: st.write(item["desc"] + "…")
                st.markdown("---")
    else:
        st.warning("Could not fetch NASA news feed.")

    st.subheader("🔗 Live Mission Resources")
    col_a, col_b = st.columns(2)
    with col_a:
        st.markdown("""
- 📺 [NASA TV Live](https://www.nasa.gov/nasalive)
- 🛰️ [JPL Horizons](https://ssd.jpl.nasa.gov/horizons/)
- 🌦️ [NOAA Space Weather](https://www.swpc.noaa.gov/)
- ☀️ [NASA Solar Dynamics Observatory](https://sdo.gsfc.nasa.gov/)
        """)
    with col_b:
        st.markdown("""
- 🌍 [GOES-16 Live Imagery](https://www.star.nesdis.noaa.gov/goes/)
- 📡 [NASA Artemis Blog](https://blogs.nasa.gov/artemis/)
- 🔭 [NASA Eyes on the Solar System](https://eyes.nasa.gov/)
- 📊 [NASA API Portal](https://api.nasa.gov/)
        """)

# ── Debug ─────────────────────────────────────────────────────────────────────
with st.expander("🔧 Raw telemetry (debug)"):
    if fetch_ok:
        st.write("**Orion:**", orion)
        st.write("**Moon:**",  moon)
    st.write("**Space Weather:**", sw)
