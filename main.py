from __future__ import annotations

import asyncio
import math
import os
import random
import time
from contextlib import asynccontextmanager
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

BASE_DIR = Path(__file__).resolve().parent
WEB_DIR = BASE_DIR / "web"

OPENSKY_ID = os.getenv("OPENSKY_CLIENT_ID", "").strip()
OPENSKY_SECRET = os.getenv("OPENSKY_CLIENT_SECRET", "").strip()
ANON_REFRESH = int(os.getenv("OPENSKY_ANONYMOUS_REFRESH_SECONDS", "300"))
AUTH_REFRESH = int(os.getenv("OPENSKY_AUTH_REFRESH_SECONDS", "10"))
WEATHER_REFRESH = int(os.getenv("WEATHER_REFRESH_SECONDS", "60"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    seed_domain_state()
    mutate_aircraft()
    tasks = [
        asyncio.create_task(simulator_loop()),
        asyncio.create_task(external_sync_loop()),
    ]
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="AeroCore API", version="0.1.0", lifespan=lifespan)
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

AIRPORTS: dict[str, dict[str, Any]] = {
    "DNAA": {"name": "Nnamdi Azikiwe International Airport", "city": "Abuja", "lat": 9.0068, "lon": 7.2632, "tz": "WAT"},
    "KJFK": {"name": "John F. Kennedy International Airport", "city": "New York", "lat": 40.6413, "lon": -73.7781, "tz": "ET"},
    "KLAX": {"name": "Los Angeles International Airport", "city": "Los Angeles", "lat": 33.9416, "lon": -118.4085, "tz": "PT"},
}

_opensky_token: str | None = None
_opensky_token_expiry = 0.0

state: dict[str, Any] = {
    "airport": "DNAA",
    "aircraft": {},
    "weather": None,
    "weather_meta": {"mode": "PENDING", "last_success": None, "error": None},
    "traffic_meta": {"mode": "SIMULATED", "last_success": None, "error": None, "refresh_seconds": AUTH_REFRESH if OPENSKY_ID and OPENSKY_SECRET else ANON_REFRESH},
    "events": deque(maxlen=80),
    "alerts": [],
    "incidents": [],
    "turnarounds": [],
    "baggage": {"processed": 7904, "total": 8421, "exceptions": 23, "open_exceptions": 4},
    "socket_clients": set(),
    "tick": 0,
}

SIM_AIRCRAFT = [
    {"icao24": "a3a560", "callsign": "UAL214", "country": "United States", "lat": 40.73, "lon": -73.82, "alt": 31800, "speed": 452, "track": 274, "vr": 640, "status": "AIRBORNE"},
    {"icao24": "a53eef", "callsign": "UPS846", "country": "United States", "lat": 40.82, "lon": -73.76, "alt": 27600, "speed": 411, "track": 314, "vr": -180, "status": "AIRBORNE"},
    {"icao24": "a3b88e", "callsign": "AAL2677", "country": "United States", "lat": 40.61, "lon": -73.93, "alt": 6400, "speed": 212, "track": 104, "vr": -720, "status": "APPROACHING"},
    {"icao24": "ad6966", "callsign": "N963XP", "country": "United States", "lat": 40.65, "lon": -73.77, "alt": 0, "speed": 22, "track": 172, "vr": 0, "status": "GROUND"},
    {"icao24": "a5955b", "callsign": "UPS990", "country": "United States", "lat": 40.78, "lon": -73.69, "alt": 15100, "speed": 301, "track": 86, "vr": 420, "status": "AIRBORNE"},
    {"icao24": "a3685d", "callsign": "JANET55", "country": "United States", "lat": 40.69, "lon": -73.98, "alt": 9200, "speed": 248, "track": 14, "vr": -90, "status": "AIRBORNE"},
]

BBOXES = {
    "DNAA": (7.9, 10.1, 6.0, 8.6),
    "KJFK": (39.7, 41.4, -75.0, -72.4),
    "KLAX": (33.2, 34.6, -119.0, -117.1),
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def add_event(kind: str, entity: str, detail: str, severity: str = "INFO", source: str = "SIMULATOR") -> dict[str, Any]:
    event = {
        "id": f"EVT-{int(time.time()*1000)}-{random.randint(10,99)}",
        "ts": now_iso(),
        "kind": kind,
        "entity": entity,
        "detail": detail,
        "severity": severity,
        "source": source,
    }
    state["events"].appendleft(event)
    return event


def seed_domain_state() -> None:
    state["turnarounds"] = [
        {"flight": "NG214", "aircraft": "5N-BQZ", "gate": "G17", "target_min": 55, "elapsed_min": 41, "risk": "HIGH", "status": "BOARDING", "stages": {"Arrival": 100, "Disembarkation": 100, "Baggage unload": 84, "Cleaning": 100, "Catering": 100, "Fuel": 100, "Boarding": 42, "Baggage load": 61}},
        {"flight": "BA083", "aircraft": "G-TWUK", "gate": "G21", "target_min": 62, "elapsed_min": 37, "risk": "LOW", "status": "FUELING", "stages": {"Arrival": 100, "Disembarkation": 100, "Baggage unload": 100, "Cleaning": 74, "Catering": 68, "Fuel": 58, "Boarding": 0, "Baggage load": 0}},
        {"flight": "ET901", "aircraft": "ET-AYC", "gate": "G04", "target_min": 50, "elapsed_min": 18, "risk": "MEDIUM", "status": "BAGGAGE", "stages": {"Arrival": 100, "Disembarkation": 100, "Baggage unload": 61, "Cleaning": 0, "Catering": 0, "Fuel": 0, "Boarding": 0, "Baggage load": 0}},
    ]
    state["alerts"] = [
        {"id": "ALT-001", "severity": "HIGH", "title": "NG214 departure risk", "summary": "Baggage loading is 4 min behind the turnaround target.", "age": "00:02"},
        {"id": "ALT-002", "severity": "MEDIUM", "title": "Baggage scan gap", "summary": "BAG-0837291 has no scan in expected make-up zone.", "age": "00:06"},
        {"id": "ALT-003", "severity": "LOW", "title": "Weather update received", "summary": "Latest airport METAR is available.", "age": "00:11"},
    ]
    state["incidents"] = [
        {"id": "INC-00482", "category": "Operational", "severity": "HIGH", "status": "INVESTIGATING", "title": "Approach weather condition change", "entity": "UAL1898", "opened": "11:38:42 UTC", "owner": "Duty Operations"},
        {"id": "INC-00479", "category": "Baggage", "severity": "MEDIUM", "status": "MITIGATION", "title": "Late bag transfer exception", "entity": "BAG-0837291", "opened": "11:32:10 UTC", "owner": "Baggage Control"},
    ]


def simulated_aircraft_for_airport(airport_code: str) -> list[dict[str, Any]]:
    airport = AIRPORTS[airport_code]
    # Around Abuja, use realistic synthetic traffic near the airport. For US hubs, start from the richer demo set.
    base = [dict(x) for x in SIM_AIRCRAFT]
    if airport_code == "DNAA":
        seeds = [
            ("5N-BQZ", "NG214", 9.11, 7.21, 8300, 248, 198, -480, "APPROACHING"),
            ("5N-XYZ", "Q9214", 8.96, 7.34, 0, 18, 132, 0, "GROUND"),
            ("5N-BWX", "P4712", 9.03, 7.31, 12600, 281, 92, 420, "AIRBORNE"),
            ("5N-BRM", "CW541", 9.18, 7.07, 18900, 322, 268, -120, "AIRBORNE"),
            ("5N-BOD", "LA302", 8.82, 7.15, 7200, 224, 26, -610, "APPROACHING"),
        ]
        base = []
        for i, s in enumerate(seeds):
            base.append({"icao24": f"sim{i+1:02d}", "callsign": s[1], "country": "Nigeria", "lat": s[2], "lon": s[3], "alt": s[4], "speed": s[5], "track": s[6], "vr": s[7], "status": s[8]})
    return base


def mutate_aircraft() -> None:
    airport_code = state["airport"]
    source = state["aircraft"]
    for a in simulated_aircraft_for_airport(airport_code):
        existing = source.get(a["icao24"], a)
        if existing["status"] != "GROUND":
            existing["lat"] += math.cos(math.radians(existing["track"])) * existing["speed"] * 0.00002
            existing["lon"] += math.sin(math.radians(existing["track"])) * existing["speed"] * 0.00002
            existing["alt"] = max(0, existing["alt"] + existing["vr"] * 0.45)
            existing["track"] = (existing["track"] + random.uniform(-1.2, 1.2)) % 360
            existing["speed"] = max(90, existing["speed"] + random.uniform(-3, 3))
        existing["last_contact"] = now_iso()
        source[a["icao24"]] = existing


def map_opensky_state(row: list[Any]) -> dict[str, Any] | None:
    if len(row) < 11 or row[5] is None or row[6] is None:
        return None
    return {
        "icao24": row[0],
        "callsign": (row[1] or "UNKNOWN").strip(),
        "country": row[2] or "Unknown",
        "lat": row[6],
        "lon": row[5],
        "alt": row[7] or 0,
        "speed": round((row[9] or 0) * 1.94384, 0),
        "track": row[10] or 0,
        "vr": round((row[11] or 0) * 196.85, 0),
        "status": "GROUND" if (row[7] or 0) < 100 and (row[9] or 0) < 20 else "AIRBORNE",
        "last_contact": datetime.fromtimestamp(row[4] or time.time(), tz=timezone.utc).isoformat(timespec="seconds"),
    }


async def opensky_states(airport_code: str) -> tuple[list[dict[str, Any]], str, str | None]:
    global _opensky_token, _opensky_token_expiry
    bbox = BBOXES[airport_code]
    params = {"lamin": bbox[0], "lamax": bbox[1], "lomin": bbox[2], "lomax": bbox[3]}
    headers: dict[str, str] = {}
    if OPENSKY_ID and OPENSKY_SECRET:
        if not _opensky_token or time.time() >= _opensky_token_expiry:
            async with httpx.AsyncClient(timeout=12) as client:
                token_resp = await client.post(
                    "https://auth.opensky-network.org/auth/realms/opensky-network/protocol/openid-connect/token",
                    data={"grant_type": "client_credentials", "client_id": OPENSKY_ID, "client_secret": OPENSKY_SECRET},
                    headers={"Content-Type": "application/x-www-form-urlencoded"},
                )
                token_resp.raise_for_status()
                token_data = token_resp.json()
                _opensky_token = token_data["access_token"]
                _opensky_token_expiry = time.time() + max(60, int(token_data.get("expires_in", 1800)) - 60)
        headers["Authorization"] = f"Bearer {_opensky_token}"
    async with httpx.AsyncClient(timeout=12) as client:
        resp = await client.get("https://opensky-network.org/api/states/all", params=params, headers=headers)
        resp.raise_for_status()
        payload = resp.json()
    rows = [mapped for raw in (payload.get("states") or []) if (mapped := map_opensky_state(raw))]
    return rows, "LIVE", None


async def weather_for(airport_code: str) -> tuple[dict[str, Any] | None, str | None]:
    async with httpx.AsyncClient(timeout=10) as client:
        resp = await client.get("https://aviationweather.gov/api/data/metar", params={"ids": airport_code, "format": "json"})
        resp.raise_for_status()
        data = resp.json()
    if not data:
        return None, "No METAR returned"
    m = data[0]
    return {
        "station": m.get("icaoId", airport_code),
        "flight_category": m.get("fltCat") or "UNKNOWN",
        "wind_kt": m.get("wspd", 0),
        "wind_dir": m.get("wdir"),
        "visibility": m.get("visib", "—"),
        "temp_c": m.get("temp"),
        "dewpoint_c": m.get("dewp"),
        "raw": m.get("rawOb") or m.get("raw_text") or "",
        "observed": m.get("reportTime") or now_iso(),
    }, None


async def broadcast(payload: dict[str, Any]) -> None:
    dead: list[WebSocket] = []
    for ws in list(state["socket_clients"]):
        try:
            await ws.send_json(payload)
        except Exception:
            dead.append(ws)
    for ws in dead:
        state["socket_clients"].discard(ws)


def snapshot() -> dict[str, Any]:
    aircraft = list(state["aircraft"].values())
    airborne = sum(1 for a in aircraft if a.get("status") != "GROUND")
    high = sum(1 for a in aircraft if (a.get("alt") or 0) >= 9000 * 3.28084)
    airport = AIRPORTS[state["airport"]]
    return {
        "ts": now_iso(),
        "airport": {"code": state["airport"], **airport},
        "aircraft": aircraft,
        "kpis": {
            "tracked": len(aircraft),
            "airborne": airborne,
            "high_altitude": high,
            "gates": {"occupied": 14, "total": 18, "available": 3, "maintenance": 1},
            "turnarounds": len(state["turnarounds"]),
            "alerts": len(state["alerts"]),
            "incidents": sum(1 for x in state["incidents"] if x["status"] != "CLOSED"),
            "passengers": 4218,
            "security_wait": 17,
        },
        "weather": state["weather"],
        "weather_meta": state["weather_meta"],
        "traffic_meta": state["traffic_meta"],
        "events": list(state["events"]),
        "alerts": state["alerts"][:8],
        "incidents": state["incidents"][:8],
        "turnarounds": state["turnarounds"],
        "baggage": state["baggage"],
    }


async def simulator_loop() -> None:
    if not state["events"]:
        add_event("SYSTEM_ONLINE", "AEROCORE", "Operations command center initialized", source="SYSTEM")
        add_event("DATA_SOURCE_READY", "OPEN_SKY", "Flight surveillance adapter ready", source="OPEN_SKY")
        add_event("DATA_SOURCE_READY", "AWC", "Aviation weather adapter ready", source="AWC")
        add_event("SIMULATOR_STARTED", "OPS-SIM", "Synthetic airport event engine running", source="SIMULATOR")
    while True:
        mutate_aircraft()
        state["tick"] += 1
        # Small realistic operational changes.
        if state["turnarounds"] and state["tick"] % 3 == 0:
            t = state["turnarounds"][0]
            t["elapsed_min"] += 1
            t["stages"]["Baggage load"] = min(100, t["stages"]["Baggage load"] + random.randint(1, 5))
            t["stages"]["Boarding"] = min(100, t["stages"]["Boarding"] + random.randint(1, 7))
            t["status"] = "BOARDING" if t["stages"]["Boarding"] < 100 else "READY"
            if t["elapsed_min"] > t["target_min"] and t["risk"] != "HIGH":
                t["risk"] = "HIGH"
                state["alerts"].insert(0, {"id": f"ALT-{state['tick']}", "severity": "HIGH", "title": f"{t['flight']} turnaround threshold", "summary": "Actual turnaround has exceeded target.", "age": "00:00"})
                add_event("ALERT_CREATED", t["flight"], "Turnaround target exceeded", severity="HIGH")
            else:
                add_event("TURNAROUND_STAGE_UPDATED", t["flight"], f"Boarding {t['stages']['Boarding']}% · Baggage load {t['stages']['Baggage load']}%")
        # Baggage counter simulation
        state["baggage"]["processed"] = min(state["baggage"]["total"], state["baggage"]["processed"] + random.randint(1, 6))
        if state["tick"] % 4 == 0:
            state["baggage"]["exceptions"] = max(11, state["baggage"]["exceptions"] + random.choice([-1, 0, 1]))
            add_event("BAGGAGE_SCAN_RECEIVED", f"BAG-{random.randint(100000,999999)}", "Sorter scan ingested", source="BAGGAGE-SIM")
        # Random live events.
        if state["tick"] % 5 == 0:
            a = random.choice(list(state["aircraft"].values())) if state["aircraft"] else None
            if a:
                add_event("AIRCRAFT_POSITION_UPDATED", a["callsign"], f"{a['alt']:.0f} ft · {a['speed']:.0f} kt", source=state["traffic_meta"]["mode"])
        await broadcast({"type": "snapshot", "payload": snapshot()})
        await asyncio.sleep(1)


async def external_sync_loop() -> None:
    last_traffic = 0.0
    last_weather = 0.0
    while True:
        airport_code = state["airport"]
        now = time.time()
        if now - last_traffic >= state["traffic_meta"]["refresh_seconds"]:
            try:
                rows, mode, _ = await opensky_states(airport_code)
                if rows:
                    state["aircraft"] = {x["icao24"]: x for x in rows}
                    state["traffic_meta"].update({"mode": mode, "last_success": now_iso(), "error": None})
                    add_event("TRAFFIC_SYNC", "OPEN_SKY", f"{len(rows)} state vectors received", source="OPEN_SKY")
                else:
                    mutate_aircraft()
                    state["traffic_meta"].update({"mode": "SIMULATED_FALLBACK", "error": "No live state vectors in selected box"})
            except Exception as exc:
                mutate_aircraft()
                state["traffic_meta"].update({"mode": "SIMULATED_FALLBACK", "error": str(exc)[:180]})
                add_event("DATA_SOURCE_DEGRADED", "OPEN_SKY", "Using simulator fallback", severity="MEDIUM", source="OPEN_SKY")
            last_traffic = now
        if now - last_weather >= WEATHER_REFRESH:
            try:
                weather, err = await weather_for(airport_code)
                state["weather"] = weather
                state["weather_meta"].update({"mode": "LIVE" if weather else "DEGRADED", "last_success": now_iso() if weather else state["weather_meta"].get("last_success"), "error": err})
                if weather:
                    add_event("WEATHER_UPDATE", airport_code, f"{weather['flight_category']} · {weather['wind_kt']} kt · {weather['visibility']} vis", source="AWC")
            except Exception as exc:
                state["weather_meta"].update({"mode": "DEGRADED", "error": str(exc)[:180]})
            last_weather = now
        await asyncio.sleep(1)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/health")
def health() -> dict[str, Any]:
    return {"status": "ok", "time": now_iso(), "sources": {"opensky": state["traffic_meta"], "awc": state["weather_meta"]}}


@app.get("/api/snapshot")
def get_snapshot() -> dict[str, Any]:
    return snapshot()


@app.post("/api/airport/{code}")
def set_airport(code: str) -> dict[str, Any]:
    code = code.upper()
    if code not in AIRPORTS:
        return {"ok": False, "error": "Unsupported airport"}
    state["airport"] = code
    state["aircraft"] = {}
    mutate_aircraft()
    add_event("AIRPORT_CONTEXT_CHANGED", code, f"Operations context switched to {AIRPORTS[code]['name']}", source="USER")
    return {"ok": True, "snapshot": snapshot()}


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    state["socket_clients"].add(ws)
    try:
        await ws.send_json({"type": "snapshot", "payload": snapshot()})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        state["socket_clients"].discard(ws)
    except Exception:
        state["socket_clients"].discard(ws)
