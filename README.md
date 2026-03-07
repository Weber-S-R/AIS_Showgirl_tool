# AIS Showgirl tool

**Made for : Mara and 'The Showgirl'**

Python AIS tool to find ships near Mara and The Showgirl and help ensure safe transit for the cocoon of happiness. Lists vessels (name, heading, distance) within a chosen radius of a reference position. **Aggregates two data sources:** (1) **AIS Stream** — live AIS WebSocket; (2) **Global Fishing Watch** — vessel presence in the area over the last 96 hours (optional free token). No hardcoded paths or machine-specific settings—works on any system with the dependencies below.

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

### Optional: Global Fishing Watch (96h vessel presence)

The script can also report whether any vessels were present in the area in the **last 96 hours** using [Global Fishing Watch](https://globalfishingwatch.org) (free, non-commercial token). This is optional; the script runs fully without it.

- **Get a token:** [globalfishingwatch.org/our-apis/tokens](https://globalfishingwatch.org/our-apis/tokens)
- **Use it:** set `GFW_API_TOKEN` in the environment or pass `--gfw-token YOUR_TOKEN`. If no token is set, the script skips the 96h check and only shows live AIS results.

---

## Step 1: Install Python dependency

From a terminal (PowerShell, cmd, or bash):

```bash
pip install -r requirements.txt
```

Or install the single required package:

```bash
pip install websockets
python3 -m pip install websockets   # or: py -3 -m pip install websockets
```

Requires **websockets** ≥ 10.0 (see `requirements.txt`).

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
- **Radius**: `--radius` in nautical miles (default 25). This controls **live AIS** filtering: which vessels must be within this radius **during the collection window** to be listed.
- **Collection time**: `--collect` in seconds (default 60). This controls how long we listen to the AIS WebSocket for live messages.
- **API key**: either set the environment variable or use `--api-key`.
- **GFW token** (optional): for 96h vessel presence in area; set `GFW_API_TOKEN` or use `--gfw-token` (GFW always looks at a fixed 1°x1° box around your reference position for the last 96 hours; it is **not** tied to `--radius`).
- **`--world`** (optional): subscribe to the **global** AIS stream instead of a regional box; the script still filters by `--radius` locally. Use in **open ocean or sparse areas** where the regional subscription returns 0 messages. Near busy coasts you can omit it to reduce data volume.
- **`--debug`** (optional): print to stderr the number of AIS messages received, message types, and any server error (useful when troubleshooting 0 vessels).

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
| `--radius NM` | Radius in nautical miles | 25 |
| `--collect SECONDS` | How long to listen for AIS messages | 60 |
| `--api-key KEY` | AIS Stream API key (or use env `AISSTREAM_API_KEY`) | (none) |
| `--gfw-token TOKEN` | Global Fishing Watch token for 96h presence (or use env `GFW_API_TOKEN`) | (none, optional) |
| `--world` | Subscribe to global AIS stream; filter by radius locally. Use in open ocean when regional subscription returns 0 messages. | off |
| `--debug` | Print AIS message count, types, and first server error to stderr | off |

### Examples

- **Open ocean (use `--world` so AIS Stream sends data)**  
  ```powershell
  py -3 ais_vessel_proximity.py --lat 14.34392 --lon -28.46047 --radius 40 --collect 120 --world
  ```
  When the regional subscription returns 0 messages (e.g. mid-Atlantic), add `--world` to subscribe globally; the script still filters by `--radius`.

- **Typical Windows (PowerShell) run for ShowGirl (last known position)**  
  ```powershell
  py -3 ais_vessel_proximity.py --lat 25.2145 --lon=-16.427 --radius 100 --collect 120
  ```
  - `--lat` / `--lon`: ShowGirl's last known position (decimal degrees, N positive, W negative).
  - `--radius 100`: list live AIS vessels within 100 NM of that point **during the 120 second window**.
  - `--collect 120`: listen to AIS for ~2 minutes.
  - Add `--world` if you get 0 live vessels in open ocean. AIS Stream API key and GFW token from env if set.

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

- **Reference position** used.
- **Live AIS vessels** within the radius (for the collection window). For each vessel: **name**, distance (NM), **heading/course** (°), speed (kt, if available), MMSI, position, and timestamp. Vessels are sorted by distance (closest first).
- If we received AIS messages but **none in range**, the script notes that and (when available) prints the **closest** positions outside the radius (e.g. "Closest AIS this run: 127 NM — SHIP NAME") so you can see how far the nearest traffic was.
- **GFW 96-hour presence** (if a token is provided): whether any vessels have been present in the surrounding 1°x1° box in the **last 96 hours**, and a list of vessel **name**, **MMSI**, **flag**, and **hours** spent in the area.

Subtle but important difference:

- **AIS Stream**: "Who is here **right now** (during this N‑second window) within `--radius` NM?" → live traffic and headings.
- **Global Fishing Watch**: "Who has spent time in this area (1°x1° box around your reference point) in the **last 96 hours**?" → recent presence, not instantaneous positions and no heading.

---

## Portability

- No paths to your PC or username are used.
- Reference position is either the built-in example (for Mara / The Showgirl) or whatever you pass with `--lat` / `--lon`.
- API key is supplied by you via environment variable or `--api-key`.
- Works on Windows, macOS, and Linux as long as Python 3 and `websockets` are installed and you have a valid AIS Stream API key.

---

## Data sources

- **AIS Stream** ([aisstream.io](https://aisstream.io)) — WebSocket API; service is in beta with no SLA. By default the script subscribes to a bounding box around your reference point; use **`--world`** to subscribe to the global stream (e.g. open ocean) and filter by radius locally. Distances are haversine in nautical miles. Connection uses a 45s open timeout and up to 3 retries; if no message arrives within 8s after subscribing, the script suggests checking the API key or trying `--world`.
- **Global Fishing Watch** (optional) — Report API for vessel presence in the area over the last 96 hours; requires a free non-commercial token. See "Optional: Global Fishing Watch" above.

---

## Troubleshooting

- **"Requires: pip install websockets"** → Run `pip install -r requirements.txt` or `pip install websockets`.
- **"No API key set"** → Sign in at [aisstream.io](https://aisstream.io/authenticate), create a key at [aisstream.io/apikeys](https://aisstream.io/apikeys), then pass it with `--api-key` or `AISSTREAM_API_KEY`.
- **"Api Key Is Not Valid"** (from AIS Stream) → Create a new key at [aisstream.io/apikeys](https://aisstream.io/apikeys) and use it.
- **"No message in 8s after subscribe"** → The server may have rejected the subscription or the regional bbox has no coverage. Try **`--world`** to subscribe to the global stream; if you still get no messages, verify your API key at [aisstream.io/apikeys](https://aisstream.io/apikeys).
- **0 vessels (live)** → In open ocean the regional subscription often returns 0 messages. Use **`--world`** so the script receives the global stream and filters by your `--radius`. You can also try a larger `--radius` or longer `--collect`. GFW (if token set) still shows 96h presence in the area.
- **GFW error / skipped** → Get a free token at [globalfishingwatch.org/our-apis/tokens](https://globalfishingwatch.org/our-apis/tokens) and set `GFW_API_TOKEN` or `--gfw-token`; GFW is for non-commercial use.
- **Could not connect** → Check your internet connection; if it still fails, see https://aisstream.io for service status.
- **Your API key was not accepted** → Get a new key at https://aisstream.io/apikeys and paste it when the script asks, or use `--api-key YOUR_NEW_KEY`.

---

**Author:** Scott R. Weber  
**Repo:** [github.com/Weber-S-R/AIS_Showgirl_tool](https://github.com/Weber-S-R/AIS_Showgirl_tool)  
**Last updated:** 2026-03-05
