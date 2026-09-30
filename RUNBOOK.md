# AeroCore Demo Runbook

## 1. Start the platform

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn apps.api.main:app --reload --host 0.0.0.0 --port 8000
```

Open `http://localhost:8000`.

## 2. Demo flow

1. Start on Command Center.
2. Show the live aircraft markers moving.
3. Open Live Traffic and Flight Board.
4. Open Turnaround and show progress changing every second.
5. Open Baggage Intelligence and demonstrate exception state.
6. Open Safety & Incidents to show traceable incident records.
7. Open Event Stream and point out normalized events, sources and timestamps.
8. Open Data Sources and explain live vs simulator fallback.

## 3. Live-source credentials

Set `OPENSKY_CLIENT_ID` and `OPENSKY_CLIENT_SECRET` for authenticated OpenSky access. Anonymous OpenSky access is deliberately polled conservatively to respect the current rate model.

METAR data is fetched from the Aviation Weather Center's Data API.
