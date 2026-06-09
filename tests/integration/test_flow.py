"""
INTEGRATION TESTS — full application flows

Integration tests exercise complete user workflows end-to-end:
  - Web UI routes respond correctly (HTML pages render)
  - Creating data via UI is readable via API
  - Status transitions work
  - CSV import round-trips correctly
  - Driver assignment propagates to shipment details

Unlike unit tests, these tests use the full Flask app with a real
(temporary) SQLite database, so they catch problems that only appear
when all layers work together.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import io
import pytest
from tests.conftest import client, seeded_client  # noqa: F401


# ── Helper ────────────────────────────────────────────────────────────────────

def _create_shipment(c, origin_id, dest_id, pay=5000, days_ahead=30):
    from datetime import date, timedelta
    deadline = (date.today() + timedelta(days=days_ahead)).strftime('%Y-%m-%d')
    return c.post('/shipments/new', data={
        'origin_hub': origin_id, 'destination_hub': dest_id,
        'cargo_type': 'Integration Test Cargo', 'weight_lbs': '2500',
        'deadline': deadline, 'total_pay': str(pay),
    }, follow_redirects=True)


def _hub_ids(c):
    hubs = c.get('/api/hubs').get_json()['hubs']
    return hubs[0]['id'], hubs[4]['id']


# ── Page Rendering ────────────────────────────────────────────────────────────

class TestPageRendering:
    def test_dashboard_renders(self, seeded_client):
        r = seeded_client.get('/')
        assert r.status_code == 200
        assert b'LogiTrack' in r.data

    def test_shipments_page_renders(self, seeded_client):
        r = seeded_client.get('/shipments')
        assert r.status_code == 200

    def test_new_shipment_form_renders(self, seeded_client):
        r = seeded_client.get('/shipments/new')
        assert r.status_code == 200
        assert b'origin_hub' in r.data

    def test_drivers_page_renders(self, seeded_client):
        assert seeded_client.get('/drivers').status_code == 200

    def test_hubs_page_renders(self, seeded_client):
        assert seeded_client.get('/hubs').status_code == 200

    def test_analytics_page_renders(self, seeded_client):
        assert seeded_client.get('/analytics').status_code == 200

    def test_import_page_renders(self, seeded_client):
        assert seeded_client.get('/import').status_code == 200


# ── Shipment Lifecycle ────────────────────────────────────────────────────────

class TestShipmentLifecycle:
    def test_create_shipment_appears_in_api(self, seeded_client):
        o, d = _hub_ids(seeded_client)
        _create_shipment(seeded_client, o, d)
        data = seeded_client.get('/api/shipments').get_json()
        assert len(data) == 1
        assert data[0]['cargo_type'] == 'Integration Test Cargo'

    def test_status_update_pending_to_intransit(self, seeded_client):
        o, d = _hub_ids(seeded_client)
        _create_shipment(seeded_client, o, d)
        shipment_id = seeded_client.get('/api/shipments').get_json()[0]['id']

        seeded_client.post(f'/shipments/{shipment_id}/status',
                           data={'status': 'in-transit'}, follow_redirects=True)
        s = seeded_client.get(f'/api/shipments/{shipment_id}').get_json()
        assert s['status'] == 'in-transit'

    def test_status_update_to_delivered(self, seeded_client):
        o, d = _hub_ids(seeded_client)
        _create_shipment(seeded_client, o, d)
        sid = seeded_client.get('/api/shipments').get_json()[0]['id']
        seeded_client.post(f'/shipments/{sid}/status',
                           data={'status': 'delivered'}, follow_redirects=True)
        s = seeded_client.get(f'/api/shipments/{sid}').get_json()
        assert s['status'] == 'delivered'

    def test_delete_shipment_removes_from_api(self, seeded_client):
        o, d = _hub_ids(seeded_client)
        _create_shipment(seeded_client, o, d)
        sid = seeded_client.get('/api/shipments').get_json()[0]['id']
        seeded_client.post(f'/shipments/{sid}/delete', follow_redirects=True)
        assert seeded_client.get('/api/shipments').get_json() == []

    def test_route_detail_page_shows_path(self, seeded_client):
        o, d = _hub_ids(seeded_client)
        _create_shipment(seeded_client, o, d)
        sid = seeded_client.get('/api/shipments').get_json()[0]['id']
        r = seeded_client.get(f'/shipments/{sid}/route')
        assert r.status_code == 200
        assert b'Route Path' in r.data


# ── Good Route Logic ──────────────────────────────────────────────────────────

class TestGoodRouteLogic:
    def test_high_pay_is_good_route(self, seeded_client):
        o, d = _hub_ids(seeded_client)
        # Get distance first
        dist = seeded_client.get(f'/api/distance/hubs/{o}/{d}').get_json()['distance']
        # Pay well above 3.5x
        _create_shipment(seeded_client, o, d, pay=dist * 5)
        sid = seeded_client.get('/api/shipments').get_json()[0]['id']
        data = seeded_client.get(f'/api/shipments/{sid}').get_json()
        assert data['is_good_route'] is True

    def test_low_pay_is_not_good_route(self, seeded_client):
        o, d = _hub_ids(seeded_client)
        dist = seeded_client.get(f'/api/distance/hubs/{o}/{d}').get_json()['distance']
        _create_shipment(seeded_client, o, d, pay=dist * 1.0)
        sid = seeded_client.get('/api/shipments').get_json()[0]['id']
        data = seeded_client.get(f'/api/shipments/{sid}').get_json()
        assert data['is_good_route'] is False


# ── Driver Assignment ─────────────────────────────────────────────────────────

class TestDriverAssignment:
    def test_driver_shows_on_shipment(self, seeded_client):
        seeded_client.post('/drivers/new', data={
            'name': 'Bob Smith', 'phone': '555-9999',
            'license_number': 'CDL-X', 'status': 'available',
        })
        driver_id = seeded_client.get('/api/drivers').get_json()[0]['id']
        o, d = _hub_ids(seeded_client)
        from datetime import date, timedelta
        deadline = (date.today() + timedelta(days=14)).strftime('%Y-%m-%d')
        seeded_client.post('/shipments/new', data={
            'origin_hub': o, 'destination_hub': d,
            'cargo_type': 'Fragile Goods', 'weight_lbs': '800',
            'deadline': deadline, 'total_pay': '4000',
            'driver_id': driver_id,
        }, follow_redirects=True)
        sid = seeded_client.get('/api/shipments').get_json()[0]['id']
        s = seeded_client.get(f'/api/shipments/{sid}').get_json()
        assert s['driver_name'] == 'Bob Smith'

    def test_cannot_delete_driver_with_active_load(self, seeded_client):
        seeded_client.post('/drivers/new', data={
            'name': 'Alice Jones', 'phone': '', 'license_number': '', 'status': 'available',
        })
        driver_id = seeded_client.get('/api/drivers').get_json()[0]['id']
        o, d = _hub_ids(seeded_client)
        _create_shipment(seeded_client, o, d)
        # Assign driver via edit
        sid = seeded_client.get('/api/shipments').get_json()[0]['id']
        s = seeded_client.get(f'/api/shipments/{sid}').get_json()
        from datetime import date, timedelta
        seeded_client.post(f'/shipments/{sid}/edit', data={
            'origin_hub': s['origin_hub'] if 'origin_hub' in s else o,
            'destination_hub': s['destination_hub'] if 'destination_hub' in s else d,
            'cargo_type': s['cargo_type'], 'weight_lbs': s['weight_lbs'],
            'deadline': s['deadline'], 'total_pay': s['total_pay'],
            'status': 'in-transit', 'driver_id': driver_id,
        }, follow_redirects=True)
        # Now try to delete driver — should fail
        seeded_client.post(f'/drivers/{driver_id}/delete', follow_redirects=True)
        drivers = seeded_client.get('/api/drivers').get_json()
        assert len(drivers) == 1  # still there


# ── CSV Import ────────────────────────────────────────────────────────────────

class TestCSVImport:
    def test_valid_csv_creates_shipments(self, seeded_client):
        hubs = seeded_client.get('/api/hubs').get_json()['hubs']
        # Pick two hubs whose codes we know
        code_a = hubs[0]['code']
        code_b = hubs[1]['code']
        from datetime import date, timedelta
        deadline = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
        csv_content = (
            'origin_code,destination_code,cargo_type,weight_lbs,deadline,total_pay,notes\n'
            f'{code_a},{code_b},CSV Cargo,3000,{deadline},6000,test row\n'
        )
        data = {'file': (io.BytesIO(csv_content.encode()), 'test.csv')}
        r = seeded_client.post('/import', data=data,
                               content_type='multipart/form-data', follow_redirects=True)
        assert r.status_code == 200
        shipments = seeded_client.get('/api/shipments').get_json()
        assert len(shipments) == 1
        assert shipments[0]['cargo_type'] == 'CSV Cargo'

    def test_csv_with_bad_hub_code_skips_row(self, seeded_client):
        from datetime import date, timedelta
        deadline = (date.today() + timedelta(days=30)).strftime('%Y-%m-%d')
        csv_content = (
            'origin_code,destination_code,cargo_type,weight_lbs,deadline,total_pay,notes\n'
            f'XXXXX,YYYYY,Bad Cargo,1000,{deadline},2000,\n'
        )
        data = {'file': (io.BytesIO(csv_content.encode()), 'bad.csv')}
        seeded_client.post('/import', data=data,
                           content_type='multipart/form-data', follow_redirects=True)
        assert seeded_client.get('/api/shipments').get_json() == []
