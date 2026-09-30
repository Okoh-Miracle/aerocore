-- PostgreSQL-ready domain model for AeroCore.
CREATE TABLE IF NOT EXISTS airports (
  code VARCHAR(8) PRIMARY KEY,
  name TEXT NOT NULL,
  city TEXT NOT NULL,
  latitude DOUBLE PRECISION NOT NULL,
  longitude DOUBLE PRECISION NOT NULL
);

CREATE TABLE IF NOT EXISTS aircraft (
  icao24 VARCHAR(12) PRIMARY KEY,
  callsign VARCHAR(16),
  country TEXT,
  last_latitude DOUBLE PRECISION,
  last_longitude DOUBLE PRECISION,
  altitude_ft DOUBLE PRECISION,
  speed_kt DOUBLE PRECISION,
  track_deg DOUBLE PRECISION,
  vertical_rate_fpm DOUBLE PRECISION,
  status VARCHAR(32),
  last_contact TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS flights (
  id UUID PRIMARY KEY,
  callsign VARCHAR(16) NOT NULL,
  origin VARCHAR(8),
  destination VARCHAR(8),
  scheduled_departure TIMESTAMPTZ,
  estimated_departure TIMESTAMPTZ,
  status VARCHAR(32),
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS operational_events (
  id TEXT PRIMARY KEY,
  event_time TIMESTAMPTZ NOT NULL,
  event_type VARCHAR(80) NOT NULL,
  entity_id TEXT NOT NULL,
  severity VARCHAR(16) NOT NULL,
  source VARCHAR(80) NOT NULL,
  detail TEXT,
  payload JSONB NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_operational_events_time ON operational_events(event_time DESC);
CREATE INDEX IF NOT EXISTS idx_operational_events_entity ON operational_events(entity_id, event_time DESC);

CREATE TABLE IF NOT EXISTS alerts (
  id TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  severity VARCHAR(16) NOT NULL,
  title TEXT NOT NULL,
  summary TEXT,
  status VARCHAR(32) NOT NULL DEFAULT 'OPEN',
  source_event_id TEXT REFERENCES operational_events(id)
);

CREATE TABLE IF NOT EXISTS incidents (
  id TEXT PRIMARY KEY,
  opened_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  category VARCHAR(40) NOT NULL,
  severity VARCHAR(16) NOT NULL,
  title TEXT NOT NULL,
  entity_id TEXT,
  status VARCHAR(32) NOT NULL,
  owner TEXT
);

CREATE TABLE IF NOT EXISTS audit_logs (
  id BIGSERIAL PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  entity_type TEXT NOT NULL,
  entity_id TEXT NOT NULL,
  metadata JSONB NOT NULL DEFAULT '{}'
);
