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
    print("Requires: pip install websockets", file=sys.stderr)
    sys.exit(1)

# --- Example default reference position (override with --lat / --lon for your vessel) ---
DEFAULT_REF_LAT = 19.0 + 56.770 / 60.0   # 19.94617 (19 56.770N)
DEFAULT_REF_LON = -(20.0 + 26.969 / 60.0)  # -20.44948 (20 26.969W)
DEFAULT_RADIUS_NM = 25.0
AIS_STREAM_URL = "wss://stream.aisstream.io/v0/stream"
GFW_REPORT_URL = "https://gateway.api.globalfishingwatch.org/v3/4wings/report"
GFW_PRESENCE_DATASET = "public-global-presence:latest"
GFW_HOURS_LOOKBACK = 96

# --- Default credentials (used when env vars not set) ---
# Set via env AISSTREAM_API_KEY / GFW_API_TOKEN or --api-key / --gfw-token. Leave empty in repo.
DEFAULT_AISSTREAM_API_KEY = ""
DEFAULT_GFW_API_TOKEN = ""

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


def bbox_around(lat: float, lon: float, margin_deg: float = 2.0):
    """Return AIS Stream style bbox [[lat1, lon1], [lat2, lon2]] around (lat, lon). Default 2 deg so server sends more; we filter by radius_nm locally."""
    return [
        [lat - margin_deg, lon - margin_deg],
        [lat + margin_deg, lon + margin_deg],
    ]


def _geojson_bbox_polygon(lat: float, lon: float, margin_deg: float = 1.0) -> dict:
    """Return GeoJSON Polygon for bbox around (lat, lon). Coordinates [lon, lat] per point."""
    min_lat = max(-90.0, lat - margin_deg)
    max_lat = min(90.0, lat + margin_deg)
    min_lon = max(-180.0, lon - margin_deg)
    max_lon = min(180.0, lon + margin_deg)
    ring = [
        [min_lon, min_lat],
        [max_lon, min_lat],
        [max_lon, max_lat],
        [min_lon, max_lat],
        [min_lon, min_lat],
    ]
    return {"type": "Polygon", "coordinates": [ring]}


def fetch_gfw_recent_presence(ref_lat: float, ref_lon: float, gfw_token: str) -> dict:
    """Fetch vessel presence in area from Global Fishing Watch (last 96h). Returns ok, count, vessels (list of name/mmsi/flag/hours), error."""
    if not gfw_token or not gfw_token.strip():
        return {"ok": False, "count": None, "vessels": [], "error": "no token"}
    gfw_token = gfw_token.strip()
    end_utc = datetime.now(timezone.utc)
    start_utc = end_utc - timedelta(hours=GFW_HOURS_LOOKBACK)
    # GFW v3 report API: date-range as YYYY-MM-DD,YYYY-MM-DD (date-only)
    date_range = f"{start_utc.strftime('%Y-%m-%d')},{end_utc.strftime('%Y-%m-%d')}"
    geojson = _geojson_bbox_polygon(ref_lat, ref_lon, margin_deg=1.0)
    query_params = [
        ("format", "JSON"),
        ("datasets[0]", GFW_PRESENCE_DATASET),
        ("date-range", date_range),
        ("temporal-resolution", "ENTIRE"),
        ("spatial-aggregation", "true"),
        ("group-by", "VESSEL_ID"),
    ]
    query = urllib.parse.urlencode(query_params)
    url = f"{GFW_REPORT_URL}?{query}"
    body = json.dumps({"geojson": geojson}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {gfw_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:109.0) Gecko/20100101 Firefox/115.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace").strip()
        try:
            j = json.loads(err_body) if err_body else {}
            msg = j.get("detail") or j.get("error") or (err_body if err_body else None)
        except Exception:
            msg = err_body or None
        if not msg:
            msg = "Forbidden" if e.code == 403 else str(e)
        return {"ok": False, "count": None, "vessels": [], "error": f"HTTP {e.code}: {msg}"}
    except (urllib.error.URLError, json.JSONDecodeError, OSError) as e:
        return {"ok": False, "count": None, "vessels": [], "error": str(e)}
    vessels = []  # list of {name, mmsi, flag, hours, ...} for display
    if isinstance(data, dict):
        entries = data.get("entries", data.get("data", []))
        if isinstance(entries, list):
            for entry in entries:
                if not isinstance(entry, dict):
                    continue
                for key, val in entry.items():
                    if isinstance(val, list):
                        for rec in val:
                            if isinstance(rec, dict):
                                vessels.append({
                                    "name": (rec.get("shipName") or rec.get("shipname") or "").strip() or "(no name)",
                                    "mmsi": rec.get("mmsi") or "—",
                                    "flag": rec.get("flag") or "—",
                                    "hours": rec.get("hours"),
                                    "geartype": rec.get("geartype") or "—",
                                })
                        break
    return {"ok": True, "count": len(vessels), "vessels": vessels, "error": None}


def print_gfw_summary(ref_lat: float, ref_lon: float, gfw_token: str) -> None:
    """Fetch and print GFW vessel presence (last 96h) in area."""
    result = fetch_gfw_recent_presence(ref_lat, ref_lon, gfw_token)
    print("-" * 60)
    if not gfw_token or not gfw_token.strip():
        print("GFW (last 96h): skipped (no token). Get free token: https://globalfishingwatch.org/our-apis/tokens")
        return
    if not result["ok"]:
        print(f"GFW (last 96h): skipped — {result['error']}")
        return
    vessels = result.get("vessels") or []
    count = result.get("count") or len(vessels)
    if count and vessels:
        print(f"GFW (last 96h): vessel presence in area: Yes — {len(vessels)} vessel(s) in last 96 hours")
        print("  (Name, MMSI, Flag, Hours in area — heading/course is from live AIS above only)")
        for v in vessels:
            hrs = f"  {v['hours']}h" if v.get("hours") is not None else ""
            print(f"  • {v['name']}  MMSI {v['mmsi']}  Flag {v['flag']}{hrs}")
    elif count:
        print(f"GFW (last 96h): vessel presence in area: Yes — {count} vessel(s) in last 96 hours")
    else:
        print("GFW (last 96h): vessel presence in area: No vessels in last 96 hours")


# Whole-world bbox for AIS Stream (use with --world to test key / get data in sparse areas)
AIS_WORLD_BBOX = [[-90.0, -180.0], [90.0, 180.0]]


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
    debug: bool = False,
    use_world_bbox: bool = False,
) -> None:
    # API expects list of bboxes: [[[lat1,lon1],[lat2,lon2]], ...]; each bbox is two corners
    if use_world_bbox:
        subscribe_bbox = [AIS_WORLD_BBOX]
        if debug:
            print("[debug] Using world bbox for AIS subscription (filter by radius locally)", file=sys.stderr)
    else:
        bbox = bbox_around(ref_lat, ref_lon)
        subscribe_bbox = [bbox]
    seen = {}  # MMSI -> { mmsi, name, lat, lon, dist_nm, sog, cog, time_utc }
    closest_outside = []  # list of (dist_nm, name, mmsi, lat, lon), keep up to 5
    msg_count = 0
    msg_types = set()
    first_server_error = None

    async def handle_message(raw: str) -> None:
        nonlocal msg_count, msg_types, first_server_error
        try:
            msg = json.loads(raw)
        except json.JSONDecodeError:
            return
        msg_count += 1
        if "error" in msg:
            err = msg["error"]
            if first_server_error is None:
                first_server_error = err
            print(f"AIS Stream error: {err}", file=sys.stderr)
            return
        msg_type = msg.get("MessageType")
        if msg_type:
            msg_types.add(msg_type)
        if debug and msg_count <= 3:
            print(f"[debug] msg #{msg_count} MessageType={msg_type!r}", file=sys.stderr)
        if msg_type not in ("PositionReport", "StandardClassBPositionReport", "ExtendedClassBPositionReport"):
            return
        payload = msg.get("Message", {})
        if isinstance(payload, dict):
            payload = payload.get(msg_type)
        else:
            payload = None
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
        mmsi = payload.get("UserID") or meta.get("MMSI") or "?"
        name = (meta.get("ShipName") or "").strip() or "(no name)"
        sog = payload.get("Sog")
        cog = payload.get("Cog")
        time_utc = meta.get("time_utc") or ""
        if dist > radius_nm:
            # track closest positions outside radius (for "nearest was X NM" when 0 in-range)
            entry = (dist, name, mmsi, lat, lon)
            if len(closest_outside) < 5:
                closest_outside.append(entry)
                closest_outside.sort(key=lambda x: x[0])
            elif dist < closest_outside[-1][0]:
                closest_outside.append(entry)
                closest_outside.sort(key=lambda x: x[0])
                closest_outside.pop()
            return
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
        "BoundingBoxes": subscribe_bbox,
        "FilterMessageTypes": [
            "PositionReport",
            "StandardClassBPositionReport",
            "ExtendedClassBPositionReport",
        ],
    }

    loop = asyncio.get_running_loop()
    open_timeout = 45.0  # handshake can be slow; default 10s often too short
    last_err = None
    for attempt in range(3):
        try:
            async with websockets.connect(
                AIS_STREAM_URL,
                open_timeout=open_timeout,
                close_timeout=10.0,
            ) as ws:
                await ws.send(json.dumps(subscribe))
                # Wait for first message (error or data) so we know subscription was accepted
                try:
                    first_raw = await asyncio.wait_for(ws.recv(), timeout=8.0)
                    await handle_message(first_raw)
                except asyncio.TimeoutError:
                    print(
                        "AIS Stream: no message in 8s after subscribe. Try --world to test global stream, or check API key at https://aisstream.io/apikeys",
                        file=sys.stderr,
                    )
                end = loop.time() + collect_seconds
                try:
                    while loop.time() < end:
                        try:
                            raw = await asyncio.wait_for(ws.recv(), timeout=10.0)
                            await handle_message(raw)
                        except asyncio.TimeoutError:
                            continue
                        except (ConnectionError, websockets.exceptions.ConnectionClosed) as e:
                            print(f"AIS Stream connection closed: {e}", file=sys.stderr)
                            break
                except asyncio.CancelledError:
                    pass
            break
        except (asyncio.TimeoutError, OSError) as e:
            last_err = e
            if attempt < 2:
                await asyncio.sleep(2.0 * (attempt + 1))
            else:
                print(
                    "AIS Stream: connection timed out after 3 attempts. Check network/firewall and https://aisstream.io status.",
                    file=sys.stderr,
                )
                raise

    if debug:
        print(
            f"[debug] AIS Stream: received {msg_count} messages, types={sorted(msg_types)!r}, in-range={len(seen)}",
            file=sys.stderr,
        )
        if first_server_error:
            print(f"[debug] first server error: {first_server_error!r}", file=sys.stderr)

    # Output: name, distance, heading (course), speed, position
    print(f"Reference position: {ref_lat:.5f}, {ref_lon:.5f}")
    print(f"Vessels within {radius_nm} NM (collected over ~{int(collect_seconds)}s): {len(seen)}")
    print("-" * 60)
    if seen:
        print("  Name | Distance (NM) | Heading (°) | Speed (kt) | Position")
        for v in sorted(seen.values(), key=lambda x: x["dist_nm"]):
            name = (v["name"] or "(no name)").strip() or "(no name)"
            heading = f"{v['cog']:.0f}°" if v.get("cog") is not None else "—"
            sog = f"{v['sog']} kt" if v.get("sog") is not None else "—"
            pos = f"{v['lat']:.5f}, {v['lon']:.5f}"
            print(f"  {name}")
            print(f"      {v['dist_nm']:.1f} NM  |  Heading {heading}  |  Speed {sog}  |  {pos}")
            print(f"      MMSI {v['mmsi']}  {v.get('time_utc', '')}")
    else:
        print("  No vessels in range this time.")
        if msg_count > 0:
            print("  Live AIS had no vessels within radius during this run; GFW (below) shows recent presence in the area.")
            if closest_outside:
                print("  Closest AIS positions this run (outside radius):")
                for dist_nm, name, mmsi, lat, lon in closest_outside[:3]:
                    print(f"    {dist_nm:.0f} NM — {name}  MMSI {mmsi}  ({lat:.4f}, {lon:.4f})")
        print("  You can try a larger radius (e.g. --radius 50) or run again later.")


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
        description="List AIS vessels within radius (NM) of a reference position (friend's boat)."
    )
    ap.add_argument(
        "--lat",
        type=float,
        default=None,
        help=f"Reference latitude (default from current.png: {DEFAULT_REF_LAT:.5f})",
    )
    ap.add_argument(
        "--lon",
        type=float,
        default=None,
        help=f"Reference longitude (default from current.png: {DEFAULT_REF_LON:.5f})",
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
        help="Seconds to collect AIS messages (default 60)",
    )
    ap.add_argument(
        "--api-key",
        default=os.environ.get("AISSTREAM_API_KEY", DEFAULT_AISSTREAM_API_KEY).strip(),
        help="AIS Stream API key (or set AISSTREAM_API_KEY)",
    )
    ap.add_argument(
        "--gfw-token",
        default=os.environ.get("GFW_API_TOKEN", DEFAULT_GFW_API_TOKEN).strip(),
        help="Global Fishing Watch API token (optional; adds 96h vessel presence). Set GFW_API_TOKEN",
    )
    ap.add_argument(
        "--debug",
        action="store_true",
        help="Print AIS message count, message types, and first server error to stderr",
    )
    ap.add_argument(
        "--world",
        action="store_true",
        help="Subscribe to global AIS stream (still filter by --radius). Use if you get 0 messages (sparse area or bbox issue).",
    )
    args = ap.parse_args()

    ref_lat = args.lat
    ref_lon = args.lon

    # Interactive prompts for coordinates when not given and stdin is a TTY
    if ref_lat is None or ref_lon is None:
        if sys.stdin.isatty():
            print(f"Reference position (decimal degrees). Default: {DEFAULT_REF_LAT:.5f}°N, {DEFAULT_REF_LON:.5f}°W")
            if ref_lat is None:
                raw = input(f"  Latitude [{DEFAULT_REF_LAT:.5f}]: ").strip()
                try:
                    ref_lat = float(raw) if raw else DEFAULT_REF_LAT
                except ValueError:
                    ref_lat = DEFAULT_REF_LAT
                    print(f"  Invalid input, using default {ref_lat:.5f}", file=sys.stderr)
            if ref_lon is None:
                raw = input(f"  Longitude [{DEFAULT_REF_LON:.5f}]: ").strip()
                try:
                    ref_lon = float(raw) if raw else DEFAULT_REF_LON
                except ValueError:
                    ref_lon = DEFAULT_REF_LON
                    print(f"  Invalid input, using default {ref_lon:.5f}", file=sys.stderr)
        else:
            ref_lat = ref_lat if ref_lat is not None else DEFAULT_REF_LAT
            ref_lon = ref_lon if ref_lon is not None else DEFAULT_REF_LON

    if not args.api_key:
        print(
            "No API key set. AIS Stream is free.\n"
            "  1. Go to https://aisstream.io and sign in (e.g. with GitHub).\n"
            "  2. Open https://aisstream.io/apikeys and create an API key.\n"
            "  3. Run again with env AISSTREAM_API_KEY=your_key or --api-key your_key",
            file=sys.stderr,
        )
        sys.exit(1)

    asyncio.run(
        run_proximity(
            ref_lat=ref_lat,
            ref_lon=ref_lon,
            radius_nm=args.radius,
            api_key=args.api_key,
            collect_seconds=args.collect,
            debug=args.debug,
            use_world_bbox=args.world,
        )
    )
    # Second source: GFW vessel presence in area (last 96h)
    print_gfw_summary(ref_lat, ref_lon, args.gfw_token)


if __name__ == "__main__":
    main()
