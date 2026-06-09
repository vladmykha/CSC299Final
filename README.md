# LogiTrack — Logistics Route Optimization Dashboard

A full-stack logistics management web application built with Flask, SQLite, and NetworkX. LogiTrack lets you manage shipments across a network of 25 U.S. hub cities, calculates optimal routes using Dijkstra's algorithm, tracks driver assignments, and flags routes as "good" or "bad" based on pay-per-mile thresholds.

> Built for CSC299 — inspired by real-world logistics dispatch workflows.

---

## Features

- **Shipment management** — create, edit, delete, and track shipments through their lifecycle (pending → in-transit → delivered)
- **Graph-based routing** — Dijkstra shortest path across a 25-node, 49-edge U.S. hub network powered by NetworkX
- **Distance calculator** — hub-to-hub distance lookup and real address-to-address road distance via OpenStreetMap / OSRM
- **Good route detection** — flags any load paying ≥ 3.5× the distance in dollars as a "good route"
- **Deadline progress bars** — visual green/yellow/red progress indicator per shipment based on elapsed time
- **Driver management** — assign drivers to loads, track availability, guard against deleting drivers with active shipments
- **Hub & route editor** — add/remove hub cities and the edges between them; guards prevent deleting hubs with active shipments
- **Analytics dashboard** — bar chart of shipments by status, good/bad route breakdown, top drivers by load count
- **CSV bulk import** — upload a CSV to create multiple shipments at once; bad rows are skipped with a reported error count
- **REST API** — JSON endpoints consumed by the built-in CLI client and any future mobile or third-party app
- **CLI client** — terminal client (`cli.py`) with colored output for quick lookups without opening a browser
- **Three-layer test suite** — unit, contract, and integration tests (62 tests total)

---

## Prerequisites

- Python 3.9 or newer
- pip3

No external database server, no API keys, no Docker required.

---

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/vladmykha/CSC299Final.git
cd CSC299Final

# 2. Create and activate a virtual environment
python3 -m venv venv
source venv/bin/activate        # macOS / Linux
# venv\Scripts\activate         # Windows

# 3. Install dependencies
pip3 install -r requirements.txt

# 4. Run the app
python3 app.py
```

Open your browser at **http://127.0.0.1:5000**

The SQLite database (`logistics.db`) is created automatically on first run and seeded with 25 hub cities and 49 routes. No migration scripts needed.

---

## CLI Client

With the server running, open a second terminal:

```bash
# Summary stats
python3 cli.py stats

# List all shipments (optionally filter by status)
python3 cli.py shipments
python3 cli.py shipments --status in-transit

# Detail for a single shipment
python3 cli.py shipment 3

# List drivers
python3 cli.py drivers

# List hubs
python3 cli.py hubs

# Shortest route between two hubs
python3 cli.py route CHI LAX

# Point at a different server
python3 cli.py --url http://192.168.1.10:5000 stats
```

---

## Running Tests

```bash
pip3 install pytest
pytest tests/ -v
```

Run a specific layer:

```bash
pytest tests/unit/       -v   # pure logic, no DB, milliseconds
pytest tests/contract/   -v   # API shape & status codes
pytest tests/integration/-v   # full end-to-end workflows
```

See [`docs/testing.md`](docs/testing.md) for a full breakdown of what each layer covers.

---

## Project Structure

```
CSC299Final/
├── app.py                  # Flask app factory — registers blueprints
├── db.py                   # SQLite interface (init, seed, get_db)
├── routing.py              # NetworkX graph + Dijkstra route engine
├── schema.sql              # Table definitions
├── cli.py                  # Terminal client (requests-based)
├── requirements.txt
│
├── routes/                 # Flask blueprints (one per domain)
│   ├── shipments.py
│   ├── drivers.py
│   ├── hubs.py
│   ├── analytics.py
│   └── api.py              # /api/* JSON endpoints
│
├── templates/              # Jinja2 HTML templates
│   ├── base.html
│   ├── index.html
│   ├── shipments/
│   ├── drivers/
│   ├── hubs/
│   └── analytics/
│
├── static/                 # CSS overrides, JS helpers
│
├── tests/
│   ├── conftest.py         # Shared fixtures (isolated tmp SQLite per test)
│   ├── unit/
│   │   ├── test_routing.py
│   │   └── test_progress.py
│   ├── contract/
│   │   └── test_api.py
│   └── integration/
│       └── test_flow.py
│
└── docs/
    ├── architecture.mmd    # Mermaid system diagram
    └── testing.md          # Testing plan
```

---

## REST API Reference

All endpoints return JSON. Base URL: `http://127.0.0.1:5000`

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/stats` | Shipment counts by status + driver/hub totals |
| GET | `/api/shipments` | All shipments (array) |
| GET | `/api/shipments/<id>` | Single shipment with route info and `is_good_route` |
| GET | `/api/drivers` | All drivers |
| GET | `/api/hubs` | All hubs with lat/lng |
| GET | `/api/distance/hubs/<origin_id>/<dest_id>` | Dijkstra distance between two hubs |

### Example — single shipment

```json
{
  "id": 7,
  "cargo_type": "Steel Coils",
  "status": "in-transit",
  "origin_hub": 1,
  "destination_hub": 12,
  "deadline": "2026-07-01",
  "total_pay": 4200,
  "route_distance": 987.3,
  "route_hops": 3,
  "route_path": ["CHI", "STL", "KCI"],
  "is_good_route": true,
  "rate_per_mile": 4.25,
  "driver_name": "Bob Smith"
}
```

---

## Good Route Logic

A shipment is flagged as a **good route** when:

```
total_pay  >=  3.5  ×  route_distance_miles
```

The threshold (3.5 $/mile) reflects a break-even rate that accounts for fuel, driver pay, and overhead. Routes above this threshold are highlighted in green on the shipment detail and analytics pages.

---

## CSV Import Format

Navigate to **Analytics → Import CSV**. The file must have these columns (order matters for the header, values matched by name):

```csv
origin_code,destination_code,cargo_type,weight_lbs,deadline,total_pay,notes
CHI,LAX,Steel Coils,42000,2026-08-01,5500,Rush order
ATL,NYC,Auto Parts,18000,2026-09-15,3200,
```

**Valid hub codes:** ATL, BNA, CHI, CLT, CMH, CVG, DAL, DEN, DTW, HOU, IND, KCI, LAX, LOU, MEM, MIA, MSP, NYC, PDX, PHL, PHX, SAT, SEA, SLC, STL

Rows with unrecognized hub codes or missing required fields are skipped; the import summary reports how many rows succeeded and how many were skipped.

---

## Architecture

```
Browser / CLI
     │
     ▼
Flask App (app.py)
  ├── routes/shipments.py   (web UI)
  ├── routes/drivers.py
  ├── routes/hubs.py
  ├── routes/analytics.py
  └── routes/api.py         (JSON API)
           │
    ┌──────┴──────┐
    ▼             ▼
 db.py        routing.py
 SQLite        NetworkX
 logistics.db  Dijkstra
```

Full diagram: [`docs/architecture.mmd`](docs/architecture.mmd) (render at [mermaid.live](https://mermaid.live))

---

## Built With

- [Flask](https://flask.palletsprojects.com/) — web framework
- [SQLite3](https://docs.python.org/3/library/sqlite3.html) — embedded database (Python stdlib)
- [NetworkX](https://networkx.org/) — graph library for Dijkstra routing
- [Bootstrap 5](https://getbootstrap.com/) — UI components
- [Chart.js](https://www.chartjs.org/) — analytics bar chart
- [vis-network](https://visjs.github.io/vis-network/) — hub network visualization
- [OpenStreetMap Nominatim](https://nominatim.org/) — address geocoding (no API key)
- [OSRM](http://project-osrm.org/) — road distance calculation (no API key)
- [pytest](https://pytest.org/) — test framework
