import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient

from main import app


def test_health():
    with TestClient(app) as client:
        response = client.get('/api/health')
        assert response.status_code == 200
        assert response.json()['status'] == 'ok'


def test_snapshot_has_operational_domains():
    with TestClient(app) as client:
        response = client.get('/api/snapshot')
        data = response.json()
        assert response.status_code == 200
        for key in ('aircraft', 'turnarounds', 'baggage', 'incidents', 'events'):
            assert key in data


def test_web_home_loads():
    with TestClient(app) as client:
        response = client.get('/')
        assert response.status_code == 200
        assert 'AEROCORE' in response.text
