"""
UNIT TESTS — routing.py (Dijkstra graph engine)

These tests exercise routing.build_graph() and routing.get_route() in
complete isolation: no Flask app, no real SQLite file.  A lightweight
fake "connection" object is used instead of a real DB connection so we
can control the graph topology exactly.

Unit tests are fast and should never touch the network or the filesystem.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import pytest
import routing


class FakeRow(dict):
    """Behave like sqlite3.Row (supports both attribute and index access)."""
    def __getattr__(self, key):
        return self[key]


class FakeConn:
    """Minimal fake DB connection that returns pre-defined hubs and routes."""

    def __init__(self, hubs, edges):
        self._hubs  = [FakeRow(h) for h in hubs]
        self._edges = [FakeRow(e) for e in edges]

    def execute(self, sql, *_):
        if 'FROM hubs' in sql:
            return self._hubs
        if 'FROM hub_routes' in sql:
            return self._edges
        return []


# ── Fixtures ──────────────────────────────────────────────────────────────────

SIMPLE_HUBS = [
    {'id': 1, 'city': 'Alpha',   'code': 'ALP', 'state': 'XX'},
    {'id': 2, 'city': 'Bravo',   'code': 'BRV', 'state': 'XX'},
    {'id': 3, 'city': 'Charlie', 'code': 'CHL', 'state': 'XX'},
    {'id': 4, 'city': 'Delta',   'code': 'DLT', 'state': 'XX'},
]

SIMPLE_EDGES = [
    {'hub_from': 1, 'hub_to': 2, 'distance_miles': 100.0},
    {'hub_from': 2, 'hub_to': 3, 'distance_miles': 150.0},
    {'hub_from': 1, 'hub_to': 3, 'distance_miles': 400.0},  # longer direct path
    {'hub_from': 3, 'hub_to': 4, 'distance_miles':  50.0},
]


@pytest.fixture
def conn():
    return FakeConn(SIMPLE_HUBS, SIMPLE_EDGES)


# ── Tests ─────────────────────────────────────────────────────────────────────

class TestBuildGraph:
    def test_all_nodes_present(self, conn):
        G = routing.build_graph(conn)
        assert set(G.nodes) == {1, 2, 3, 4}

    def test_edge_count(self, conn):
        G = routing.build_graph(conn)
        assert G.number_of_edges() == len(SIMPLE_EDGES)

    def test_edge_weight(self, conn):
        G = routing.build_graph(conn)
        assert G[1][2]['weight'] == 100.0

    def test_undirected(self, conn):
        G = routing.build_graph(conn)
        # Undirected graph: 2→1 works even though only 1→2 was added
        assert G.has_edge(2, 1)


class TestGetRoute:
    def test_shortest_path_prefers_two_hops(self, conn):
        # 1→3 directly is 400 mi; via Bravo is 250 mi — should pick the shorter
        result = routing.get_route(conn, 1, 3)
        assert result is not None
        assert result['distance'] == 250.0
        assert result['path'] == [1, 2, 3]

    def test_path_details_contain_city_names(self, conn):
        result = routing.get_route(conn, 1, 3)
        cities = [h['city'] for h in result['path_details']]
        assert cities == ['Alpha', 'Bravo', 'Charlie']

    def test_hop_count(self, conn):
        result = routing.get_route(conn, 1, 4)
        # 1→2→3→4: 3 edges = 3 hops
        assert result['hops'] == 3

    def test_direct_route(self, conn):
        result = routing.get_route(conn, 3, 4)
        assert result['distance'] == 50.0
        assert result['hops'] == 1

    def test_same_node_distance_is_zero(self, conn):
        result = routing.get_route(conn, 2, 2)
        assert result is not None
        assert result['distance'] == 0

    def test_no_path_returns_none(self, conn):
        # Node 5 doesn't exist — should return None, not raise
        result = routing.get_route(conn, 1, 99)
        assert result is None

    def test_disconnected_graph_returns_none(self):
        # Island node 5 has no edges to the rest
        hubs  = SIMPLE_HUBS + [{'id': 5, 'city': 'Island', 'code': 'ISL', 'state': 'XX'}]
        edges = SIMPLE_EDGES  # no edges to node 5
        conn  = FakeConn(hubs, edges)
        assert routing.get_route(conn, 1, 5) is None
