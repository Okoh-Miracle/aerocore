# AeroCore Architecture

## Operational data flow

```text
External / synthetic sources
        |
        +-- OpenSky ADS-B
        +-- Aviation Weather Center METAR
        +-- Airport operational simulator
        |
        v
  Ingestion & normalization
        |
        v
  Operational event stream
        |
   +----+----------------+
   |                     |
   v                     v
State engine        Rule / alert engine
   |                     |
   v                     v
Snapshots            Alerts / incidents
   |                     |
   +----------+----------+
              v
        WebSocket API
              |
              v
       Command Center UI
```

## Domain boundaries

- **Flight operations:** aircraft state, map, flight board, source provenance.
- **Airport operations:** gates, runways, apron, terminal capacity.
- **Turnaround:** servicing stages, elapsed time, departure readiness.
- **Baggage:** scan events, flow counters, exception investigations.
- **Safety:** anomaly events, alert lifecycle, incident lifecycle and audit trail.
- **Intelligence:** grounded summaries over normalized operational records.

## Real-time contract

Every WebSocket snapshot carries a timestamp and source metadata. External data is not treated as authoritative operational control input. Synthetic internal events are explicitly labeled by source.
