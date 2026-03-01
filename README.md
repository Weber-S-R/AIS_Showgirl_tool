# AIS Showgirl tool

**Made for : Mara and 'The Showgirl'**

Python AIS tool to find ships near Mara and The Showgirl and help ensure safe transit for the cocoon of happiness. Lists vessels (name, heading, distance) within a chosen radius of a reference position. **Aggregates two data sources:** (1) **AIS Stream** — live AIS; (2) **Global Fishing Watch** — vessel presence in the area over the last 96 hours (optional free token). No hardcoded paths or machine-specific settings—works on any system with the dependencies below.

---

## Easiest way to run (no command-line needed)

1. Install the one required package:
   ```bash
   pip install -r requirements.txt
   ```
   or: `pip install websockets`

2. Run the script:
   ```bash
   python ais_vessel_proximity.py
   ```
3. When asked, paste your AIS Stream API key (get a free one at https://aisstream.io/apikeys).
4. (Optional) Set a Global Fishing Watch token to add "vessel presence in area (last 96h)": get a free token at https://globalfishingwatch.org/our-apis/tokens and set `GFW_API_TOKEN` or use `--gfw-token`.
5. For position: press **Enter** to use the default (Mara / The Showgirl), or type new latitude and longitude when prompted.

The script will then check for ships nearby (live AIS) and, if a GFW token is set, show recent vessel presence in the area. You can press **Ctrl+C** anytime to stop.

---

## Dependencies (what you need installed)

| Requirement | Purpose | How to get it |
|-------------|---------|----------------|
| **Python 3** | Run the script | Install from [python.org](https://www.python.org/downloads/) or your OS package manager. Use `python3` or `py -3` to invoke. |
| **pip** | Install Python packages | Usually included with Python. Upgrade: `python3 -m pip install --upgrade pip` |
| **websockets** | AIS Stream WebSocket client | `pip install websockets` (see below) |
| **GitHub account** (optional) | Easiest way to sign in to AIS Stream | [github.com](https://github.com) — free. Used only to log in to AIS Stream; no code or repo access. |
| **AIS Stream account** | Required to get an API key | Free sign-up at [aisstream.io](https://aisstream.io) (see steps below). |
| **AIS Stream API key** | Authenticate with the live AIS feed | Created after sign-up at [aisstream.io/apikeys](https://aisstream.io/apikeys). |
| **GFW API token** (optional) | Adds vessel presence in area over last 96h | Free token at [globalfishingwatch.org/our-apis/tokens](https://globalfishingwatch.org/our-apis/tokens) (non-commercial use). |

**No payment, no AIS hardware, no credit card.** The script uses only the above. GFW is optional but recommended for a fuller picture when AIS Stream has no coverage (e.g. open Atlantic).

---

## Step 1: Install Python dependency

From a terminal (PowerShell, cmd, or bash):

```bash
pip install websockets
```

Or with Python 3 explicitly:

```bash
python3 -m pip install websockets
```

On Windows you may use `py -3 -m pip install websockets`.

---

## Step 2: Get an AIS Stream API key

### 2a. Sign in to AIS Stream

1. Open **[https://aisstream.io/authenticate](https://aisstream.io/authenticate)** in your browser.
2. Click **Sign In With Github** (or another option if you prefer).
3. If using GitHub: on the GitHub screen, click **Authorize** so AIS Stream can see only your public profile (no repo or code access).
4. You will be redirected back to AIS Stream, now signed in.

If you see **"oauth2: Invalid OAuth2 state parameter"**: close other tabs, allow cookies for `aisstream.io` and `github.com`, and try again in a normal (non–private) window. Retry in another browser if it persists.

### 2b. Create an API key

1. While signed in, open **[https://aisstream.io/apikeys](https://aisstream.io/apikeys)** (or use the "API Keys" link from the AIS Stream site).
2. Create a new API key and copy it. You will use this when running the script.

Details are in the official docs: [aisstream.io/documentation](https://aisstream.io/documentation) (Authentication section).

---

## Step 3: Run the script

Clone this repo (or download the script), then from the repo directory:

- **Reference position** (optional): `--lat` and `--lon` in decimal degrees. If omitted, built-in example defaults are used; override these for your own vessel or waypoint.
- **Radius**: `--radius` in nautical miles (default 100).
- **GFW token** (optional): `--gfw-token` or env `GFW_API_TOKEN` to add 96h vessel presence in area.
- **Collection time**: `--collect` in seconds (default 60).
- **API key**: either set the environment variable or use `--api-key`.

### Option A: Pass the API key on the command line

```bash
python3 ais_vessel_proximity.py --api-key "YOUR_API_KEY_HERE"
```

Windows (PowerShell):

```powershell
python ais_vessel_proximity.py --api-key "YOUR_API_KEY_HERE"
```

Or with `py -3`:

```powershell
py -3 ais_vessel_proximity.py --api-key "YOUR_API_KEY_HERE"
```

### Option B: Set the API key in the environment

**Linux / macOS (bash):**

```bash
export AISSTREAM_API_KEY="YOUR_API_KEY_HERE"
python3 ais_vessel_proximity.py
```

**Windows (PowerShell):**

```powershell
$env:AISSTREAM_API_KEY = "YOUR_API_KEY_HERE"
python ais_vessel_proximity.py
```

**Windows (cmd):**

```cmd
set AISSTREAM_API_KEY=YOUR_API_KEY_HERE
python ais_vessel_proximity.py
```

### Optional arguments

| Argument | Meaning | Default |
|----------|---------|---------|
| `--lat LAT` | Reference latitude (decimal degrees) | Example value in script |
| `--lon LON` | Reference longitude (decimal degrees) | Example value in script |
| `--radius NM` | Radius in nautical miles | 100 |
| `--collect SECONDS` | How long to listen for AIS messages | 60 |
| `--api-key KEY` | AIS Stream API key (or use env `AISSTREAM_API_KEY`) | (none) |
| `--gfw-token TOKEN` | GFW API token for 96h vessel presence (or use env `GFW_API_TOKEN`) | (none) |

### Examples

- 50 NM radius, 2 minutes of collection:
  ```bash
  python3 ais_vessel_proximity.py --api-key "YOUR_KEY" --radius 50 --collect 120
  ```

- Custom reference position (e.g. 30°N, 20°W):
  ```bash
  python3 ais_vessel_proximity.py --api-key "YOUR_KEY" --lat 30 --lon -20 --radius 25
  ```

---

## Output

The script prints:

- Reference position used.
- **Live (AIS Stream):** Number of vessels within the radius (for the collection window).
- For each vessel: **name**, distance (NM), **heading** (°), speed (if available), MMSI, position, and timestamp.
- **GFW (last 96h):** If a GFW token is set, whether there was vessel presence in the area in the last 96 hours (and how many vessels), or an error/skip message.

Vessels are sorted by distance (closest first). If no vessels are in range from AIS Stream, you'll see a short message and a tip to try a larger radius or run again later. GFW gives a second, delayed view so "no live data" does not mean "no traffic recently."

---

## Portability

- No paths to your PC or username are used.
- Reference position is either the built-in example (for Mara / The Showgirl) or whatever you pass with `--lat` / `--lon`.
- API key is supplied by you via environment variable, `--api-key`, or by pasting when the script asks.
- Works on Windows, macOS, and Linux as long as Python 3 and `websockets` are installed and you have a valid AIS Stream API key.

---

## Data sources (aggregated)

- **AIS Stream** ([aisstream.io](https://aisstream.io)) — Live AIS WebSocket; service is in beta with no SLA. The script subscribes to a bounding box around your reference point, computes distances (haversine) in nautical miles, and filters to the requested radius. **Coverage can be sparse or absent in open ocean** (e.g. mid-Atlantic); "0 vessels" there often means "no terrestrial AIS feed," not "no ships."
- **Global Fishing Watch** ([globalfishingwatch.org](https://globalfishingwatch.org)) — Optional; vessel presence in the area over the **last 96 hours** (AIS-based, non-commercial). Free token at [globalfishingwatch.org/our-apis/tokens](https://globalfishingwatch.org/our-apis/tokens). Adds a second layer: "was there vessel activity in this area recently?" even when live AIS has no coverage. For **real-time** open-ocean coverage, a paid satellite-backed source (e.g. VesselAPI, MarineTraffic) would be needed; this tool focuses on free sources.

---

## Troubleshooting

- **"This script needs the 'websockets' package"** → Run `pip install websockets` (or `pip install -r requirements.txt`).
- **"No API key set"** → Sign in at [aisstream.io](https://aisstream.io/authenticate), create a key at [aisstream.io/apikeys](https://aisstream.io/apikeys), then pass it with `--api-key` or paste when prompted.
- **"Api Key Is Not Valid"** (from AIS Stream) → Create a new key at [aisstream.io/apikeys](https://aisstream.io/apikeys) and use it.
- **0 vessels (live)** → AIS Stream coverage can be sparse in open ocean; add a GFW token to see recent (96h) vessel presence in the area. Try a larger radius or longer `--collect`, or run at a different time.
- **GFW error / skipped** → Get a free token at [globalfishingwatch.org/our-apis/tokens](https://globalfishingwatch.org/our-apis/tokens) and set `GFW_API_TOKEN` or `--gfw-token`; GFW is for non-commercial use.
- **Could not connect** → Check your internet connection; if it still fails, see https://aisstream.io for service status.
- **Your API key was not accepted** → Get a new key at https://aisstream.io/apikeys and paste it when the script asks, or use `--api-key YOUR_NEW_KEY`.

---

**Author:** Scott R. Weber  
**Repo:** [github.com/Weber-S-R/AIS_Showgirl_tool](https://github.com/Weber-S-R/AIS_Showgirl_tool)  
**Last updated:** 2026-02-02
