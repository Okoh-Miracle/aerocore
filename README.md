# AeroCore

## Real-Time Aviation Operations & Intelligence Platform

AeroCore is a GitHub-ready operations-control portfolio project that unifies live ADS-B surveillance, aviation weather, airport operations, aircraft turnaround, baggage intelligence, safety incidents, event streaming, and AI-ready operational analytics in one interface.

### Modules

- **Command Center** — airport-wide operating picture, KPIs, alerts, and live event feed
- **Flight Operations** — live ADS-B state vectors and aircraft details
- **Airport Operations** — gates, runway state, stands, terminal capacity
- **Turnaround** — stage-by-stage aircraft servicing and delay risk
- **Baggage Intelligence** — bag scans, flow, exceptions, and escalation workflow
- **Safety & Incident Intelligence** — event-driven anomaly flags and investigation records
- **Data Sources** — source freshness, health, mode, and last successful sync
- **Replay/Scenario Engine** — controlled real-time operational events for demos

### Data modes

AeroCore clearly distinguishes:

- **LIVE** — external data from OpenSky and the Aviation Weather Center
- **SIMULATED LIVE** — synthetic airport, baggage, turnaround, and incident telemetry
- **DEMO** — deterministic scenarios suitable for portfolio walkthroughs

The simulation layer exists because public aviation APIs do not expose all airport-internal operational events. It lets the product demonstrate real-time event processing without pretending synthetic data is real-world operational data.

### Architecture

```text
OpenSky ──────┐
AWC Weather ──┤
Airport Data ─┤
Simulator ────┘
      │
      ▼
 Ingestion / Normalization
      │
      ▼
 Operational Event Bus
      │
 ┌────┴───────────────┐
 ▼                    ▼
State Engine      Rule Engine
 ▼                    ▼
PostgreSQL        Alerts / Incidents
      \               /
       \             /
        ▼           ▼
        WebSocket API
             │
             ▼
      AeroCore Control Center
```

### Run locally

This first build intentionally uses a Python-served frontend so it can run without a Node toolchain.

```bash
cd aerocore
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

Optional OpenSky authenticated access:

```bash
export OPENSKY_CLIENT_ID="..."
export OPENSKY_CLIENT_SECRET="..."
```

Without credentials, AeroCore uses a conservative anonymous refresh cadence and clearly reports the source mode. The dashboard remains live through the simulator/WebSocket event stream.

### Aviation data disclaimer

AeroCore is a portfolio decision-support project using public and simulated data. It is **not** a certified aviation, flight-control, dispatch, air-traffic-control, navigation, or safety-critical system.

### Primary technologies

Python · FastAPI · WebSockets · OpenSky · Aviation Weather Center · Leaflet · PostgreSQL-ready domain model · Event-driven architecture · AI-ready service boundaries

## Render deployment

This version is intended for Render's native Python runtime (not Docker).

Build command:
`pip install -r requirements.txt`

Start command:
`python -m uvicorn main:app --host 0.0.0.0 --port $PORT`

Health check:
`/api/health`

The app contains a simulated-live operational stream, with optional OpenSky and Aviation Weather Center integrations.
