# 🛰️ Artemis II Mission Control Tracker

A real-time mission dashboard for NASA's **Artemis II** — the first crewed lunar mission since Apollo 17 in 1972. Built with Python and Streamlit, pulling live data from JPL Horizons, NOAA SWPC, NASA SDO, and GOES-16 satellite imagery.

> **by Rogue.tinker**

![Python](https://img.shields.io/badge/Python-3.10+-blue?style=flat-square&logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.x-red?style=flat-square&logo=streamlit)
![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)
![Data: JPL Horizons](https://img.shields.io/badge/Data-JPL%20Horizons-orange?style=flat-square)
![Data: NOAA SWPC](https://img.shields.io/badge/Data-NOAA%20SWPC-blue?style=flat-square)

---

## 📸 Preview

![ArtemisII_trqcker](https://github.com/user-attachments/assets/6f7680bc-2976-440b-a934-d29e8c223952)


```
🛰️ Artemis II: Mission Control
Mission Day 2  ·  🌌 Trans-Lunar Coast  ·  Data: JPL Horizons · NOAA SWPC · NASA

Distance from Earth    Velocity         Altitude          Light Travel Time
   45,631 km           2.341 km/s        39,260 km           0.15 sec
   28,354 mi           1.455 mi/s        24,397 mi

[ Interactive Three.js 3D WebGL scene — Earth · Moon · Orion spacecraft ]

☀️ Space Weather | 🌍 Live Views | 📡 Mission Updates
```

---

## ⬇️ Download (No GitHub Account Required)

### Option A — Download ZIP (easiest)
Click the green **Code** button on this page → **Download ZIP**
Then unzip and follow the [Quick Start](#-quick-start) steps below.

### Option B — Direct file download with wget (Linux / macOS / WSL)
```bash
BASE=https://raw.githubusercontent.com/rogue07/ArtemisII_Tracker_by_Ram/main

mkdir artemis-tracker && cd artemis-tracker
wget $BASE/app.py
wget $BASE/install.py
```

### Option C — Direct file download with curl
```bash
BASE=https://raw.githubusercontent.com/rogue07/ArtemisII_Tracker_by_Ram/main

mkdir artemis-tracker && cd artemis-tracker
curl -O $BASE/app.py
curl -O $BASE/install.py
```

### Option D — Clone with git (no login needed for public repos)
```bash
git clone https://github.com/rogue07/ArtemisII_Tracker_by_Ram.git
cd artemis-tracker
```

> **No login, no token, no account.** This repository is public. All download methods above work anonymously.

---

## 🚀 Quick Start

### 1. Install dependencies (one time only)
```bash
python3 install.py
```
This creates a virtual environment (`artemis_venv/`) and installs all required packages.

### 2. Run the dashboard
```bash
artemis_venv/bin/streamlit run app.py
```

Open your browser to **http://localhost:8501**

That's it. No API keys, no accounts, no configuration files.

---

## ✨ Features

### 🔭 Orbital Tracking (JPL Horizons)
- Live position, velocity, and range data for Artemis II (target ID `-1024`)
- Live Moon position (body `301`) queried simultaneously
- Distance in **km and miles**
- Spacecraft velocity in **km/s and mi/s**
- Altitude above Earth's surface
- Light travel time (derived from delta)
- Mission elapsed time counter
- Mission phase detection (Earth Departure → TLI → Trans-Lunar Coast → Lunar Approach → Return)
- Progress bar showing % of journey to the Moon

### 🌌 3D WebGL Scene (Three.js)
- Full WebGL render embedded in Streamlit via `components.html`
- **Earth** — multi-layer canvas texture with oceans, continents, polar ice caps, cloud layer, and city lights emissive night map
- **Moon** — canvas texture with maria, highland regions, and craters; rendered at its actual live orbital position
- **Sun** — directional lighting with glow sprites from the correct solar direction
- **Artemis II** — triple-layer pulsing orange glow with white core and yellow velocity vector
- **7,000 stars** — vertex-colored (white, blue-white, warm yellow) using golden-angle sphere distribution
- Drag to orbit · Scroll to zoom · Auto-orbits when idle
- Floating HUD panel with live metrics

### ☀️ Space Weather & Crew Safety (NOAA SWPC)
All endpoints are free, no API key required, update every 2 minutes:

| Metric | Source | Endpoint |
|---|---|---|
| Planetary Kp Index | NOAA SWPC | `planetary_k_index_1m.json` |
| Solar Wind Speed & Density | NOAA DSCOVR | `rtsw_wind_1m.json` |
| Interplanetary Bz (nT) | NOAA DSCOVR | `rtsw_wind_1m.json` |
| Solar X-Ray Flux / Flare Class | GOES Primary | `xrays-6-hour.json` |
| Proton Flux >10 MeV (S-Scale) | GOES Primary | `integral-protons-6-hour.json` |
| Active Alerts | NOAA SWPC | `alerts.json` |

### 🌍 Live Imagery
| Image | Source | Update Rate |
|---|---|---|
| Earth Full Disk (GeoColor) | GOES-16 / NOAA NESDIS | Every 10 min |
| Solar Corona (193Å EUV) | NASA Solar Dynamics Observatory | Every 15 min |

### 📡 Mission Updates
- NASA news RSS feed (latest 5 releases)
- Links to NASA TV live stream, Artemis blog, NASA Eyes, and key data portals

---

## 📦 Dependencies

| Package | Purpose |
|---|---|
| `streamlit` | Web dashboard framework |
| `plotly` | Metrics and charts |
| `requests` | HTTP calls to all live APIs |

> **No API keys required.** All data sources are open and free.

Three.js (`r128`) is loaded from Cloudflare CDN at runtime — no npm or Node.js needed.

---

## 🏗️ Project Structure

```
artemis-tracker/
├── app.py              # Main Streamlit dashboard — run this
├── install.py          # One-time installer — creates venv and installs packages
├── artemis_venv/       # Auto-created virtual environment (gitignored)
├── artemis_install.log # Install log (auto-created)
└── README.md
```

---

## 🌐 Data Sources

| Source | What We Use | URL |
|---|---|---|
| JPL Horizons API | Spacecraft ephemeris (position, velocity) | `ssd.jpl.nasa.gov/api/horizons.api` |
| NOAA SWPC | Space weather — Kp, solar wind, X-ray, protons, alerts | `services.swpc.noaa.gov/json/` |
| NASA SDO | Solar corona imagery (193Å AIA) | `sdo.gsfc.nasa.gov` |
| NOAA GOES-16 | Earth full-disk GeoColor imagery | `cdn.star.nesdis.noaa.gov` |
| NASA News | Mission updates RSS feed | `nasa.gov/news-release/feed/` |
| Three.js | WebGL 3D rendering (CDN) | `cdnjs.cloudflare.com` |

---

## 🔬 How the Horizons Query Works

The JPL Horizons REST API is queried directly (bypassing `astroquery`) to avoid column-mapping instability between library versions:

```
TARGET    : -1024      Artemis II (Orion EM-2) — official JPL spacecraft ID
CENTER    : 500@399    Earth geocenter
QUANTITIES: 1, 20     RA/DEC and delta/deldot (range + range-rate)
FORMAT    : CSV + DEG  Machine-parseable, angles in decimal degrees
```

The response is parsed by walking backwards from the `$$SOE` marker to find the first CSV header line — robust to Horizons inserting variable numbers of `***` separator lines between the header and data block.

---

## ⚠️ What's Not Available (and Why)

| Data | Status | Reason |
|---|---|---|
| Crew heart rate, O₂, temperature | ❌ Not public | Monitored by Mission Control internally, no public API |
| Cabin pressure, CO₂, power levels | ❌ Not public | NASA internal telemetry systems only |
| Orion propellant remaining | ❌ Not public | Flight dynamics team only |
| Live continuous crew video | ⚠️ Events only | Available via NASA TV at key mission events |

---

## 🛠️ Extending This Dashboard

### Add a new data source
1. Write a `@st.cache_data(ttl=N)` fetcher function
2. Parse the response into a plain dict
3. Add a new tab or column to the UI section

### Change the tracked spacecraft
Swap the Horizons target ID in `horizons_query("-1024")`. Other interesting IDs:

| ID | Body |
|---|---|
| `-1023` | Artemis I (Orion EM-1, 2022) |
| `301` | Moon |
| `-234` | STEREO-A |
| `-255` | Psyche spacecraft |

---

## 🧑‍🚀 Artemis II Crew

| Astronaut | Role | Agency |
|---|---|---|
| Reid Wiseman | Commander | NASA |
| Victor Glover | Pilot | NASA |
| Christina Koch | Mission Specialist | NASA |
| Jeremy Hansen | Mission Specialist | CSA (Canada) |

---

## 📋 Publishing This Repo (Making It Public)

When creating the repository on GitHub, make sure to select **Public** so anyone can download it without logging in:

1. Go to [github.com/new](https://github.com/new)
2. Name it `artemis-tracker`
3. Select **Public** ← important
4. Do **not** check "Add a README" (you already have one)
5. Click **Create repository**
6. Push your files:

```bash
cd artemis-tracker
git init
git add app.py install.py README.md .gitignore
git commit -m "Initial commit — Artemis II live mission tracker"
git branch -M main
git remote add origin https://github.com/rogue07/artemis-tracker.git
git push -u origin main
```

After pushing, anyone can download via ZIP or `wget`/`curl` using the commands in the [Download](#️-download-no-github-account-required) section above — no account needed.

---

## 📜 License

MIT License — free to use, modify, and redistribute.

Data from JPL, NOAA, and NASA is US Government public domain.

---

## 🙏 Acknowledgements

- **NASA Jet Propulsion Laboratory** — Horizons ephemeris system
- **NOAA Space Weather Prediction Center** — Real-time space weather data
- **NASA Goddard Space Flight Center** — Solar Dynamics Observatory
- **NOAA NESDIS** — GOES-16 Earth imagery
- **three.js** — WebGL 3D library

---

*Built with ❤️ by Rogue.tinker · Launched April 1, 2026*
