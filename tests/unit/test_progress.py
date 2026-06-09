"""
UNIT TESTS — shipment_progress() helper (app.py)

Tests the deadline progress bar calculation across date scenarios.
No DB, no Flask server, no network.  Pure date arithmetic logic.
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from datetime import date, timedelta
from unittest.mock import patch
import pytest


def _make_shipment(status, deadline_offset_days, created_offset_days=0):
    """
    Build a minimal dict that shipment_progress() can consume.
    deadline_offset_days: days from today (+future, -past).
    created_offset_days:  days from today the shipment was created (negative = in past).
    """
    today    = date.today()
    deadline = today + timedelta(days=deadline_offset_days)
    created  = today + timedelta(days=created_offset_days)
    return {
        'status':     status,
        'deadline':   deadline.strftime('%Y-%m-%d'),
        'created_at': created.strftime('%Y-%m-%d') + ' 00:00:00',
    }


# Import the function after path is set
import app as flask_app
progress = flask_app.shipment_progress


class TestDeliveredStatus:
    def test_delivered_always_100_green(self):
        s = _make_shipment('delivered', deadline_offset_days=5, created_offset_days=-10)
        p = progress(s)
        assert p['pct']   == 100
        assert p['color'] == 'success'
        assert p['overdue'] is False


class TestProgressColors:
    def test_early_is_green(self):
        # Created today, 20 days until deadline — 0% elapsed → green
        s = _make_shipment('pending', deadline_offset_days=20, created_offset_days=0)
        p = progress(s)
        assert p['color'] == 'success'
        assert p['pct']   == 0

    def test_midway_is_yellow(self):
        # Created 7 days ago, deadline in 3 days → 70% elapsed → yellow
        s = _make_shipment('in-transit', deadline_offset_days=3, created_offset_days=-7)
        p = progress(s)
        assert p['color'] == 'warning'
        assert 60 <= p['pct'] < 85

    def test_near_deadline_is_red(self):
        # Created 19 days ago, deadline tomorrow → 95% elapsed → red
        s = _make_shipment('in-transit', deadline_offset_days=1, created_offset_days=-19)
        p = progress(s)
        assert p['color'] == 'danger'
        assert p['pct']   >= 85

    def test_overdue_is_red(self):
        # Deadline was 3 days ago
        s = _make_shipment('pending', deadline_offset_days=-3, created_offset_days=-10)
        p = progress(s)
        assert p['color']   == 'danger'
        assert p['overdue'] is True
        assert p['pct']     == 100


class TestLabels:
    def test_future_label_shows_days_left(self):
        s = _make_shipment('pending', deadline_offset_days=5, created_offset_days=-5)
        p = progress(s)
        assert '5d left' in p['label']

    def test_due_today_label(self):
        s = _make_shipment('in-transit', deadline_offset_days=0, created_offset_days=-5)
        p = progress(s)
        assert p['label'] == 'Due today'

    def test_overdue_label(self):
        s = _make_shipment('pending', deadline_offset_days=-4, created_offset_days=-10)
        p = progress(s)
        assert 'Overdue 4d' in p['label']


class TestEdgeCases:
    def test_pct_never_exceeds_100(self):
        s = _make_shipment('in-transit', deadline_offset_days=-30, created_offset_days=-60)
        assert progress(s)['pct'] <= 100

    def test_pct_never_below_0(self):
        s = _make_shipment('pending', deadline_offset_days=100, created_offset_days=0)
        assert progress(s)['pct'] >= 0

    def test_bad_date_returns_safe_default(self):
        s = {'status': 'pending', 'deadline': 'not-a-date', 'created_at': 'bad'}
        p = progress(s)
        assert p['color'] == 'secondary'
        assert p['pct']   == 0
