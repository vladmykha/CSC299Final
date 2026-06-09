# Testing Plan — LogiTrack

## Overview

This project uses three layers of automated tests, each with a distinct purpose.
All tests are run with **pytest** from the project root:

```bash
pip3 install pytest
pytest tests/ -v
```

---

## Test Layers

### 1. Unit Tests (`tests/unit/`)

**What they test:** Individual Python functions in complete isolation — no database, no HTTP server, no network.

**Why they matter:** Fast (milliseconds each), pinpoint exactly which logic broke, and can be run anywhere without any setup.

| File | What it covers |
|---|---|
| `test_routing.py` | `routing.build_graph()` and `routing.get_route()` — Dijkstra pathfinding on a hand-crafted 4-node graph |
| `test_progress.py` | `shipment_progress()` — deadline percentage, color thresholds, edge cases (overdue, due today, bad dates) |

**Key principle:** Unit tests should never touch the filesystem or network. A `FakeConn` object substitutes for the real SQLite connection in routing tests.

---

### 2. Contract Tests (`tests/contract/`)

**What they test:** Each REST API endpoint's *contract* — the HTTP status code it promises and the JSON shape it returns.

**Why they matter:** The CLI and any future mobile app depend on the API behaving consistently. A contract test fails the moment you accidentally rename a JSON key or change a status code, catching the breakage before a client does.

| File | Endpoints covered |
|---|---|
| `test_api.py` | `/api/stats`, `/api/hubs`, `/api/shipments`, `/api/shipments/<id>`, `/api/drivers`, `/api/distance/hubs/<o>/<d>` |

**Key principle:** Contract tests use Flask's test client (no real HTTP port), but they do run against a real (temporary) SQLite database so that data flows through the full stack.

---

### 3. Integration Tests (`tests/integration/`)

**What they test:** Complete user workflows from end to end — creating a shipment, assigning a driver, changing status, importing CSV — and verifying the result is correct through the API.

**Why they matter:** A unit test can pass while the components are still broken *together*. Integration tests catch wiring problems: wrong `url_for` names, missing `JOIN` columns, template context mismatches.

| File | Flows covered |
|---|---|
| `test_flow.py` | Page rendering, full shipment lifecycle (create → transit → delivered → delete), good/bad route logic, driver assignment & guard, CSV import round-trip |

**Key principle:** Each test gets a fresh database (via the `seeded_client` fixture). Tests are independent — no test depends on the state left by another.

---

## Test Fixture Design

```
tests/
  conftest.py          ← shared pytest fixtures
  unit/
    test_routing.py
    test_progress.py
  contract/
    test_api.py
  integration/
    test_flow.py
```

The `client` fixture in `conftest.py`:
1. Creates a temporary SQLite file (`tmp_path/test.db`)
2. Patches `db.DB_PATH` to point at it
3. Calls `db.init_db()` which seeds 25 hubs and 49 routes
4. Yields a Flask test client
5. Cleans up the temp file after each test

This means every test starts from a known, identical state.

---

## What Each Test Type Catches

| Problem | Unit | Contract | Integration |
|---|:---:|:---:|:---:|
| Wrong algorithm output | ✅ | | |
| Off-by-one in date math | ✅ | | |
| API returns wrong status code | | ✅ | |
| API response missing a key | | ✅ | |
| `url_for` name wrong after refactor | | | ✅ |
| DB query missing a JOIN column | | | ✅ |
| Status transition doesn't persist | | | ✅ |
| CSV import skips bad rows correctly | | | ✅ |

---

## Running a Specific Layer

```bash
# All tests
pytest tests/ -v

# Just unit tests
pytest tests/unit/ -v

# Just contract tests
pytest tests/contract/ -v

# Just integration tests
pytest tests/integration/ -v

# A single file
pytest tests/unit/test_routing.py -v
```
