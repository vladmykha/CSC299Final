from datetime import datetime

from flask import Blueprint, jsonify
import db
import routing

bp = Blueprint('api', __name__, url_prefix='/api')

GOOD_RATE = 3.5


@bp.route('/stats')
def stats():
    conn = db.get_db()
    today = datetime.now().strftime('%Y-%m-%d')
    data = {
        'total':      conn.execute('SELECT COUNT(*) FROM shipments').fetchone()[0],
        'pending':    conn.execute("SELECT COUNT(*) FROM shipments WHERE status='pending'").fetchone()[0],
        'in_transit': conn.execute("SELECT COUNT(*) FROM shipments WHERE status='in-transit'").fetchone()[0],
        'delivered':  conn.execute("SELECT COUNT(*) FROM shipments WHERE status='delivered'").fetchone()[0],
        'delayed':    conn.execute(
            "SELECT COUNT(*) FROM shipments WHERE status != 'delivered' AND deadline < ?", (today,)
        ).fetchone()[0],
        'drivers':    conn.execute('SELECT COUNT(*) FROM drivers').fetchone()[0],
        'hubs':       conn.execute('SELECT COUNT(*) FROM hubs').fetchone()[0],
    }
    conn.close()
    return jsonify(data)


@bp.route('/shipments')
def list_shipments():
    conn = db.get_db()
    rows = conn.execute(
        "SELECT s.id, s.cargo_type, s.weight_lbs, s.deadline, s.status, s.total_pay, s.created_at, "
        "h1.city AS origin_city, h1.code AS origin_code, "
        "h2.city AS dest_city, h2.code AS dest_code, "
        "d.name AS driver_name "
        "FROM shipments s "
        "JOIN hubs h1 ON s.origin_hub=h1.id "
        "JOIN hubs h2 ON s.destination_hub=h2.id "
        "LEFT JOIN drivers d ON s.driver_id=d.id "
        "ORDER BY s.created_at DESC"
    ).fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route('/shipments/<int:id>')
def get_shipment(id):
    conn = db.get_db()
    row = conn.execute(
        "SELECT s.*, h1.city AS origin_city, h1.code AS origin_code, "
        "h2.city AS dest_city, h2.code AS dest_code, d.name AS driver_name "
        "FROM shipments s "
        "JOIN hubs h1 ON s.origin_hub=h1.id "
        "JOIN hubs h2 ON s.destination_hub=h2.id "
        "LEFT JOIN drivers d ON s.driver_id=d.id "
        "WHERE s.id=?", (id,)
    ).fetchone()
    if not row:
        conn.close()
        return jsonify({'error': 'Shipment not found.'}), 404
    result = routing.get_route(conn, row['origin_hub'], row['destination_hub'])
    conn.close()
    data = dict(row)
    if result:
        data['route_distance'] = result['distance']
        data['route_hops']     = result['hops']
        data['route_path']     = [h['city'] for h in result['path_details']]
        data['is_good_route']  = row['total_pay'] >= GOOD_RATE * result['distance']
        data['rate_per_mile']  = round(row['total_pay'] / result['distance'], 2) if result['distance'] else 0
    return jsonify(data)


@bp.route('/drivers')
def list_drivers():
    conn = db.get_db()
    rows = conn.execute('SELECT * FROM drivers ORDER BY name').fetchall()
    conn.close()
    return jsonify([dict(r) for r in rows])


@bp.route('/hubs')
def hubs_data():
    conn = db.get_db()
    hubs   = [dict(r) for r in conn.execute('SELECT * FROM hubs ORDER BY city')]
    routes = [dict(r) for r in conn.execute('SELECT * FROM hub_routes')]
    conn.close()
    return jsonify({'hubs': hubs, 'routes': routes})


@bp.route('/distance/hubs/<int:origin_id>/<int:dest_id>')
def hub_distance(origin_id, dest_id):
    conn = db.get_db()
    result = routing.get_route(conn, origin_id, dest_id)
    conn.close()
    if not result:
        return jsonify({'error': 'No route found between these hubs.'}), 404
    return jsonify({
        'distance':     result['distance'],
        'hops':         result['hops'],
        'min_good_pay': round(result['distance'] * GOOD_RATE, 2),
        'path': [
            {'code': h['code'], 'city': h['city'], 'state': h['state']}
            for h in result['path_details']
        ],
    })
