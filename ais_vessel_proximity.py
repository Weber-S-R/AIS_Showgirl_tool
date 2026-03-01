# ais_vessel_proximity.py
# Author: Scott R. Weber
# Contact: https://www.linkedin.com/in/scottweber1985
# Created: 2026-02-02
# Repo: https://github.com/Weber-S-R/AIS_Showgirl_tool
#
# ---------------------------------------------------------------------------
# Made for : Mara and 'The Showgirl'
# ---------------------------------------------------------------------------
#
# Purpose: Tracks AIS vessel positions and lists ships within a given radius (NM)
#          of a reference position (e.g. a vessel or waypoint). Aggregates two data sources:
#          (1) AIS Stream – live AIS WebSocket (free API key); (2) Global Fishing Watch –
#          vessel presence in area over last 96 hours (free token, non-commercial).
# Reference: Pass --lat and --lon for your reference position (decimal degrees).
#            Default lat/lon in this script are example values only; override for any vessel.
#
# Dependencies (install before running):
#   - Python 3
#   - websockets:  pip install websockets
#   - AIS Stream API key (free): https://aisstream.io → https://aisstream.io/apikeys
#   - GFW API token (optional, free): https://globalfishingwatch.org/our-apis/tokens (adds 96h presence)
# See README.md in this repo for full setup and usage.

import argparse
import asyncio
import json
import math
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone, timedelta

try:
    import websockets
except ImportError:
    print("This script needs the 'websockets' package.", file=sys.stderr)
    print("Install it with:  pip install websockets", file=sys.stderr)
    sys.exit(1)

# --- Example default reference position (override with --lat / --lon for your vessel) ---
DEFAULT_REF_LAT = 25.0 + 49.435 / 60.0   # 25.82392 (example)
DEFAULT_REF_LON = -(15.0 + 44.755 / 60.0)  # -15.74592 (example)
DEFAULT_RADIUS_NM = 100.0
AIS_STREAM_URL = "wss://stream.aisstream.io/v0/stream"
GFW_REPORT_URL = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
GFW_PRESENCE_DATASET = "public-global-presence:latest"
GFW_HOURS_LOOKBACK = 96

# Earth radius in meters (for haversine)
R_M = 6_371_000
M_TO_NM = 0.000539957


def haversine_nm(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Distance between two (lat, lon) points in nautical miles."""
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlam = math.radians(lon2 - lon1)
    a = (
        math.sin(dphi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(dlam / 2) ** 2
    )
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R_M * c * M_TO_NM


def bbox_around(lat: float, lon: float, margin_deg: float = 1.0):
    """Return AIS Stream style bbox [[lat1, lon1], [lat2, lon2]] around (lat, lon)."""
    return [
        [lat - margin_deg, lon - margin_deg],
        [lat + margin_deg, lon + margin_deg],
    ]


def _clamp_coord(lat: float, lon: float):
    """Clamp lat to [-90, 90] and lon to [-180, 180]; return (lat, lon), and whether we clamped."""
    orig_lat, orig_lon = lat, lon
    lat = max(-90.0, min(90.0, lat))
    lon = max(-180.0, min(180.0, lon))
    return lat, lon, (orig_lat != lat or orig_lon != lon)


def _geojson_bbox_polygon(lat: float, lon: float, margin_deg: float = 1.0) -> dict:
    """Return GeoJSON Polygon for bbox around (lat, lon). Coordinates [lon, lat] per point."""
    min_lat = max(-90.0, lat - margin_deg)
    max_lat = min(90.0, lat + margin_deg)
    min_lon = max(-180.0, lon - margin_deg)
    max_lon = min(180.0, lon + margin_deg)
    # Exterior ring: closed polygon (first point = last point)
    ring = [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def fetch_gfw_recent_presence(ref_lat: float, ref_lon: float, gfw_token: str) -> dict:
    """
    Fetch vessel presence in area from Global Fishing Watch (last 96h). Non-commercial use.
    Returns dict: ok (bool), count (int or None), error (str or None).
    """
    if not gfw_token or not gfw_token.strip():
        return {"ok": False, "count": None, "error": "no token"}
    gfw_token = gfw_token.strip()
    end_utc = datetime.now(timezone.utc)
    start_utc = end_utc - timedelta(hours=GFW_HOURS_LOOKBACK)
    date_range = f"{start_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z')},{end_utc.strftime('%Y-%m-%dT%H:%M:%S.000Z')}"
    geojson = _geojson_bbox_polygon(ref_lat, ref_lon, margin_deg=1.0)
    query = (
        f"format=JSON"
        f"&datasets[0]={GFW_PRESENCE_DATASET}"
        f"&date-range={urllib.parse.quote(date_range)}"
        f"&temporal-resolution=ENTIRE"
        f"&spatial-aggregation=true"
        f"&group-by=VESSEL_ID"
    )
    url = f"{GFW_REPORT_URL}?{query}"
    body = json.dumps({"geojson": geojson}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {gfw_token}",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8")
            err_json = json.loads(err_body)
            msg = err_json.get("detail", err_json.get("error", str(e)))
        except Exception:
            msg = str(e)
        return {"ok": False, "count": None, "error": msg}
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        return {"ok": False, "count": None, "error": str(e)}
    # GFW report JSON: may have "entries" list or "data" / "total"
    count = 0
    if isinstance(data, list):
        count = len(data)
    elif isinstance(data, dict):
        entries = data.get("entries", data.get("data", []))
        if isinstance(entries, list):
            count = len(entries)
        else:
            count = int(data.get("total", 0)) if isinstance(data.get("total"), (int, float)) else 0
    return {"ok": True, "count": count, "error": None}


async def run_proximity(
    ref_lat: float,
    ref_lon: float,
    radius_nm: float,
    api_key: str,
    collect_seconds: float = 60.0,
) -> dict:
    """Returns dict with 'seen' (vessel list) and optionally 'api_error' (str) if API key was rejected."""
    bbox = bbox_around(ref_lat, ref_lon)
    seen = {}  # MMSI -> vessel info
    api_error = None

    async def handle_message(raw: str) -> None:
        nonlocal api_error
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        if "error" in msg:
            err = str(msg["error"])
            api_error = err
            err_lower = err.lower()
            if "api" in err_lower or "key" in err_lower or "invalid" in err_lower:
                print("\nYour API key was not accepted.", file=sys.stderr)
                print("Get a new key at: https://aisstream.io/apikeys", file=sys.stderr)
            else:
                print(f"AIS Stream reported: {err}", file=sys.stderr)
            return
        msg_type = msg.get("MessageType")
        if msg_type not in ("PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport"):
            return
        payload = msg.get("Message", {}).get(msg_type)
        meta = msg.get("MetaData") or msg.get("Metadata") or {}
        if not payload:
            return
        lat = payload.get("Latitude")
        lon = payload.get("Longitude")
        if lat is None or lon is None:
            lat = meta.get("latitude") or meta.get("Latitude")
            lon = meta.get("longitude") or meta.get("Longitude")
        if lat is None or lon is None:
            return
        dist = haversine_nm(ref_lat, ref_lon, lat, lon)
        if dist > radius_nm:
            return
        mmsi = payload.get("UserID") or meta.get("MMSI") or "?"
        name = (meta.get("ShipName") or "").strip() or "(no name)"
        sog = payload.get("Sog")
        cog = payload.get("Cog")
        time_utc = meta.get("time_utc") or ""
        seen[str(mmsi)] = {
            "mmsi": mmsi,
            "name": name,
            "lat": lat,
            "lon": lon,
            "dist_nm": round(dist, 2),
            "sog": sog,
            "cog": cog,
            "time_utc": time_utc,
        }

    subscribe = {
        "APIKey": api_key,
        "BoundingBoxes": [bbox],
        "FilterMessageTypes": [
            "PositionReport",
            "StandardClassBPositionReport",
            "ExtendedClassBPositionReport",
        ],
    }

    try:
        async with websockets.connect(AIS_STREAM_URL) as ws:
            await ws.send(json.dumps(subscribe))
            end = asyncio.get_event_loop().time() + collect_seconds
            try:
                while asyncio.get_event_loop().time() < end and api_error is None:
                    try:
                        raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                        await handle_message(raw)
                    except asyncio.TimeoutError:
                        continue
            except asyncio.CancelledError:
                pass
    except (OSError, ConnectionError, Exception) as e:
        print("\nCould not connect to the AIS service.", file=sys.stderr)
        print("Check your internet connection.", file=sys.stderr)
        print("If the problem continues, see https://aisstream.io for service status.", file=sys.stderr)
        raise SystemExit(1) from e

    # Output: name, distance, heading, then position/details
    print(f"Reference position: {ref_lat:.5f}, {ref_lon:.5f}")
    print(f"Vessels within {radius_nm} NM (collected over ~{int(collect_seconds)}s): {len(seen)}")
    print("-" * 60)
    if seen:
        for v in sorted(seen.values(), key=lambda x: x["dist_nm"]):
            name = (v["name"] or "(no name)").strip() or "(no name)"
            heading_str = f"  Heading {v['cog']:.0f}°" if v.get("cog") is not None else "  Heading —"
            sog_str = f"  Speed {v['sog']} kt" if v.get("sog") is not None else ""
            print(f"  {name}")
            print(f"      {v['dist_nm']:.1f} NM from reference{heading_str}{sog_str}")
            print(f"      MMSI {v['mmsi']}  Position: {v['lat']:.5f}, {v['lon']:.5f}  {v.get('time_utc', '')}")
    else:
        print("  No vessels in range this time.")
        print("  You can try a larger radius (e.g. --radius 50) or run again later.")

    return {"seen": seen, "api_error": api_error}


def print_gfw_summary(ref_lat: float, ref_lon: float, gfw_token: str) -> None:
    """Fetch and print GFW vessel presence (last 96h) in area; optional second data source."""
    result = fetch_gfw_recent_presence(ref_lat, ref_lon, gfw_token)
    print("-" * 60)
    if not gfw_token or not gfw_token.strip():
        print("GFW (last 96h): skipped (no token). Get free token: https://globalfishingwatch.org/our-apis/tokens")
        return
    if not result["ok"]:
        print(f"GFW (last 96h): error — {result['error']}")
        return
    count = result["count"]
    if count is not None and count > 0:
        print(f"GFW (last 96h): vessel presence in area: Yes — {count} vessel(s) in last 96 hours")
    else:
        print("GFW (last 96h): vessel presence in area: No vessels in last 96 hours")


def main() -> None:
    ap = argparse.ArgumentParser(
        description="List ships near a reference position (e.g. Mara and The Showgirl). Uses live AIS data."
    )
    ap.add_argument(
        "--lat",
        type=float,
        default=None,
        help=f"Reference latitude in decimal degrees (default: {DEFAULT_REF_LAT:.5f})",
    )
    ap.add_argument(
        "--lon",
        type=float,
        default=None,
        help=f"Reference longitude in decimal degrees (default: {DEFAULT_REF_LON:.5f})",
    )
    ap.add_argument(
        "--radius",
        type=float,
        default=DEFAULT_RADIUS_NM,
        help=f"Radius in nautical miles (default {DEFAULT_RADIUS_NM})",
    )
    ap.add_argument(
        "--collect",
        type=float,
        default=60.0,
        help="Seconds to listen for AIS data (default 60)",
    )
    ap.add_argument(
        "--api-key",
        default=os.environ.get("AISSTREAM_API_KEY", "").strip(),
        help="AIS Stream API key (or set AISSTREAM_API_KEY)",
    )
    ap.add_argument(
        "--gfw-token",
        default=os.environ.get("GFW_API_TOKEN", "").strip(),
        help="Global Fishing Watch API token (optional; adds 96h vessel presence). Set GFW_API_TOKEN",
    )
    args = ap.parse_args()

    ref_lat = args.lat
    ref_lon = args.lon

    # Interactive prompts when not given and running in a terminal
    if ref_lat is None or ref_lon is None:
        if sys.stdin.isatty():
            print("Reference position (your vessel or waypoint). Use decimal degrees, e.g. 25.82 for 25°49'N.")
            print(f"Default: {DEFAULT_REF_LAT:.5f}°N, {DEFAULT_REF_LON:.5f}°W  (press Enter to use default)")
            if ref_lat is None:
                raw = input(f"  Latitude [{DEFAULT_REF_LAT:.5f}]: ").strip()
                try:
                    ref_lat = float(raw) if raw else DEFAULT_REF_LAT
                except ValueError:
                    ref_lat = DEFAULT_REF_LAT
                    print(f"  Using default latitude {ref_lat:.5f}", file=sys.stderr)
            if ref_lon is None:
                raw = input(f"  Longitude [{DEFAULT_REF_LON:.5f}]: ").strip()
                try:
                    ref_lon = float(raw) if raw else DEFAULT_REF_LON
                except ValueError:
                    ref_lon = DEFAULT_REF_LON
                    print(f"  Using default longitude {ref_lon:.5f}", file=sys.stderr)
        else:
            ref_lat = ref_lat if ref_lat is not None else DEFAULT_REF_LAT
            ref_lon = ref_lon if ref_lon is not None else DEFAULT_REF_LON

    ref_lat, ref_lon, clamped = _clamp_coord(ref_lat, ref_lon)
    if clamped and sys.stdin.isatty():
        print("Note: Coordinates were adjusted to valid range (lat -90 to 90, lon -180 to 180).", file=sys.stderr)

    api_key = args.api_key
    if not api_key and sys.stdin.isatty():
        print("\nYou need an AIS Stream API key (free). Get one at: https://aisstream.io/apikeys")
        api_key = input("Paste your API key here (or press Enter to exit): ").strip()
        if not api_key:
            print("Exiting. Run the script again when you have a key.")
            sys.exit(0)
    elif not api_key:
        print(
            "No API key set. AIS Stream is free.\n"
            "  1. Go to https://aisstream.io and sign in (e.g. with GitHub).\n"
            "  2. Open https://aisstream.io/apikeys and create an API key.\n"
            "  3. Run again with:  --api-key YOUR_KEY   or set AISSTREAM_API_KEY",
            file=sys.stderr,
        )
        sys.exit(1)

    if sys.stdin.isatty():
        print("\nChecking for ships near your position... (this may take up to a minute)\n")

    try:
        result = asyncio.run(
            run_proximity(
                ref_lat=ref_lat,
                ref_lon=ref_lon,
                radius_nm=args.radius,
                api_key=api_key,
                collect_seconds=args.collect,
            )
        )
        if result.get("api_error"):
            sys.exit(1)
        # Second source: GFW vessel presence in area (last 96h)
        print_gfw_summary(ref_lat, ref_lon, args.gfw_token)
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)


if __name__ == "__main__":
    main()
