"""
CONTRACT TESTS — REST API endpoints (routes/api.py)

Contract tests verify that each API endpoint:
  1. Returns the correct HTTP status code
  2. Returns JSON in the expected shape (required keys present)
  3. Honours the contract that the CLI and any future client depend on

These tests use the Flask test client (no real HTTP), but they DO hit
the real SQLite logic — so they sit between unit and integration.
The seeded_client fixture provides 25 hubs + 49 routes from db._seed_data().
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import json
import pytest

# Re-use fixtures from conftest.py
from tests.conftest import client, seeded_client  # noqa: F401


# ── /api/stats ────────────────────────────────────────────────────────────────

class TestStatsEndpoint:
    def test_returns_200(self, seeded_client):
        r = seeded_client.get('/api/stats')
        assert r.status_code == 200

    def test_required_keys(self, seeded_client):
        data = r = seeded_client.get('/api/stats').get_json()
        for key in ('total', 'pending', 'in_transit', 'delivered', 'delayed', 'drivers', 'hubs'):
            assert key in data, f'Missing key: {key}'

    def test_hubs_count_is_25(self, seeded_client):
        data = seeded_client.get('/api/stats').get_json()
        assert data['hubs'] == 25

    def test_counts_are_integers(self, seeded_client):
        data = seeded_client.get('/api/stats').get_json()
        for key in ('total', 'pending', 'in_transit', 'delivered'):
            assert isinstance(data[key], int)


# ── /api/hubs ─────────────────────────────────────────────────────────────────

class TestHubsEndpoint:
    def test_returns_200(self, seeded_client):
        assert seeded_client.get('/api/hubs').status_code == 200

    def test_response_shape(self, seeded_client):
        data = seeded_client.get('/api/hubs').get_json()
        assert 'hubs'   in data
        assert 'routes' in data

    def test_hub_has_required_fields(self, seeded_client):
        hub = seeded_client.get('/api/hubs').get_json()['hubs'][0]
        for field in ('id', 'city', 'state', 'code'):
            assert field in hub

    def test_25_hubs_seeded(self, seeded_client):
        data = seeded_client.get('/api/hubs').get_json()
        assert len(data['hubs']) == 25

    def test_49_routes_seeded(self, seeded_client):
        data = seeded_client.get('/api/hubs').get_json()
        assert len(data['routes']) == 49


# ── /api/shipments ────────────────────────────────────────────────────────────

class TestShipmentsEndpoint:
    def test_returns_200_empty(self, seeded_client):
        assert seeded_client.get('/api/shipments').status_code == 200

    def test_empty_db_returns_empty_list(self, seeded_client):
        data = seeded_client.get('/api/shipments').get_json()
        assert data == []

    def test_shipment_fields_present_after_insert(self, seeded_client):
        # Get hub IDs from the seeded data
        hubs = seeded_client.get('/api/hubs').get_json()['hubs']
        origin_id = hubs[0]['id']
        dest_id   = hubs[1]['id']

        seeded_client.post('/shipments/new', data={
            'origin_hub': origin_id, 'destination_hub': dest_id,
            'cargo_type': 'Test Cargo', 'weight_lbs': '1000',
            'deadline': '2027-12-31', 'total_pay': '5000',
        })

        data = seeded_client.get('/api/shipments').get_json()
        assert len(data) == 1
        s = data[0]
        for field in ('id', 'cargo_type', 'status', 'total_pay', 'deadline',
                      'origin_city', 'dest_city', 'origin_code', 'dest_code'):
            assert field in s, f'Missing field: {field}'

    def test_default_status_is_pending(self, seeded_client):
        hubs = seeded_client.get('/api/hubs').get_json()['hubs']
        seeded_client.post('/shipments/new', data={
            'origin_hub': hubs[0]['id'], 'destination_hub': hubs[1]['id'],
            'cargo_type': 'Widgets', 'weight_lbs': '500',
            'deadline': '2027-06-01', 'total_pay': '3000',
        })
        s = seeded_client.get('/api/shipments').get_json()[0]
        assert s['status'] == 'pending'


# ── /api/shipments/<id> ───────────────────────────────────────────────────────

class TestSingleShipmentEndpoint:
    def test_404_for_missing_shipment(self, seeded_client):
        r = seeded_client.get('/api/shipments/999')
        assert r.status_code == 404

    def test_returns_route_info(self, seeded_client):
        hubs = seeded_client.get('/api/hubs').get_json()['hubs']
        seeded_client.post('/shipments/new', data={
            'origin_hub': hubs[0]['id'], 'destination_hub': hubs[5]['id'],
            'cargo_type': 'Electronics', 'weight_lbs': '2000',
            'deadline': '2027-12-31', 'total_pay': '8000',
        })
        shipment_id = seeded_client.get('/api/shipments').get_json()[0]['id']
        data = seeded_client.get(f'/api/shipments/{shipment_id}').get_json()
        assert 'route_distance' in data
        assert 'is_good_route'  in data
        assert 'rate_per_mile'  in data


# ── /api/drivers ──────────────────────────────────────────────────────────────

class TestDriversEndpoint:
    def test_returns_200(self, seeded_client):
        assert seeded_client.get('/api/drivers').status_code == 200

    def test_empty_list_initially(self, seeded_client):
        assert seeded_client.get('/api/drivers').get_json() == []

    def test_driver_appears_after_creation(self, seeded_client):
        seeded_client.post('/drivers/new', data={
            'name': 'Jane Doe', 'phone': '555-1234',
            'license_number': 'CDL-001', 'status': 'available',
        })
        drivers = seeded_client.get('/api/drivers').get_json()
        assert len(drivers) == 1
        assert drivers[0]['name'] == 'Jane Doe'
        for field in ('id', 'name', 'phone', 'license_number', 'status'):
            assert field in drivers[0]


# ── /api/distance/hubs/<o>/<d> ────────────────────────────────────────────────

class TestHubDistanceEndpoint:
    def test_valid_route_returns_200(self, seeded_client):
        hubs = seeded_client.get('/api/hubs').get_json()['hubs']
        o, d = hubs[0]['id'], hubs[5]['id']
        r = seeded_client.get(f'/api/distance/hubs/{o}/{d}')
        assert r.status_code == 200

    def test_response_shape(self, seeded_client):
        hubs = seeded_client.get('/api/hubs').get_json()['hubs']
        o, d = hubs[0]['id'], hubs[5]['id']
        data = seeded_client.get(f'/api/distance/hubs/{o}/{d}').get_json()
        for field in ('distance', 'hops', 'min_good_pay', 'path'):
            assert field in data

    def test_min_good_pay_is_3_5x_distance(self, seeded_client):
        hubs = seeded_client.get('/api/hubs').get_json()['hubs']
        o, d = hubs[0]['id'], hubs[5]['id']
        data = seeded_client.get(f'/api/distance/hubs/{o}/{d}').get_json()
        assert abs(data['min_good_pay'] - data['distance'] * 3.5) < 0.01

    def test_invalid_hub_returns_404(self, seeded_client):
        r = seeded_client.get('/api/distance/hubs/1/9999')
        assert r.status_code == 404
