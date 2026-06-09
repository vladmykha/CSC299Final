import csv
import io
from datetime import datetime, date

from flask import (Flask, flash, jsonify, redirect, render_template,
                   request, url_for)

import db
import routing

app = Flask(__name__)
app.secret_key = 'csc299-logitrack-secret'

db.init_db()


@app.template_global()
def shipment_progress(s):
    """Return progress dict for a shipment row: pct, color, label."""
    if s['status'] == 'delivered':
        return {'pct': 100, 'color': 'success', 'label': 'Delivered', 'overdue': False}
    try:
        created  = datetime.strptime(s['created_at'][:10], '%Y-%m-%d').date()
        deadline = datetime.strptime(s['deadline'], '%Y-%m-%d').date()
        today    = date.today()
        total    = max((deadline - created).days, 1)
        elapsed  = (today - created).days
        pct      = min(100, max(0, int(elapsed / total * 100)))
        days_left = (deadline - today).days
        overdue  = days_left < 0
        if overdue:
            label = f'Overdue {abs(days_left)}d'
        elif days_left == 0:
            label = 'Due today'
        else:
            label = f'{days_left}d left'
        color = 'danger' if pct >= 85 else ('warning' if pct >= 60 else 'success')
        return {'pct': pct, 'color': color, 'label': label, 'overdue': overdue}
    except Exception:
        return {'pct': 0, 'color': 'secondary', 'label': '', 'overdue': False}


# ── Dashboard ──────────────────────────────────────────────────────────────

@app.route('/')
def index():
    conn = db.get_db()
    stats = {
        'total':      conn.execute('SELECT COUNT(*) FROM shipments').fetchone()[0],
        'pending':    conn.execute("SELECT COUNT(*) FROM shipments WHERE status='pending'").fetchone()[0],
        'in_transit': conn.execute("SELECT COUNT(*) FROM shipments WHERE status='in-transit'").fetchone()[0],
        'delivered':  conn.execute("SELECT COUNT(*) FROM shipments WHERE status='delivered'").fetchone()[0],
    }
    today = datetime.now().strftime('%Y-%m-%d')
    delayed = conn.execute(
        "SELECT s.*, h1.city AS origin_city, h2.city AS dest_city, d.name AS driver_name "
        "FROM shipments s "
        "JOIN hubs h1 ON s.origin_hub=h1.id "
        "JOIN hubs h2 ON s.destination_hub=h2.id "
        "LEFT JOIN drivers d ON s.driver_id=d.id "
        "WHERE s.status != 'delivered' AND s.deadline < ? "
        "ORDER BY s.deadline", (today,)
    ).fetchall()
    recent = conn.execute(
        "SELECT s.*, h1.city AS origin_city, h2.city AS dest_city, d.name AS driver_name "
        "FROM shipments s "
        "JOIN hubs h1 ON s.origin_hub=h1.id "
        "JOIN hubs h2 ON s.destination_hub=h2.id "
        "LEFT JOIN drivers d ON s.driver_id=d.id "
        "ORDER BY s.created_at DESC LIMIT 6"
    ).fetchall()
    conn.close()
    return render_template('index.html', stats=stats, delayed=delayed, recent=recent)


# ── Shipments ──────────────────────────────────────────────────────────────

@app.route('/shipments')
def shipments():
    status_filter = request.args.get('status', 'all')
    search = request.args.get('q', '').strip()
    conn = db.get_db()
    base = (
        "SELECT s.*, h1.city AS origin_city, h1.code AS origin_code, "
        "h2.city AS dest_city, h2.code AS dest_code, d.name AS driver_name "
        "FROM shipments s "
        "JOIN hubs h1 ON s.origin_hub=h1.id "
        "JOIN hubs h2 ON s.destination_hub=h2.id "
        "LEFT JOIN drivers d ON s.driver_id=d.id"
    )
    params = []
    conditions = []
    if status_filter != 'all':
        conditions.append("s.status=?")
        params.append(status_filter)
    if search:
        conditions.append("(h1.city LIKE ? OR h2.city LIKE ? OR s.cargo_type LIKE ?)")
        params += [f'%{search}%', f'%{search}%', f'%{search}%']
    if conditions:
        base += ' WHERE ' + ' AND '.join(conditions)
    base += ' ORDER BY s.created_at DESC'
    rows = conn.execute(base, params).fetchall()
    conn.close()
    return render_template('shipments.html', shipments=rows, status_filter=status_filter, search=search)


@app.route('/shipments/new', methods=['GET', 'POST'])
def new_shipment():
    conn = db.get_db()
    hubs    = conn.execute('SELECT * FROM hubs ORDER BY city').fetchall()
    drivers = conn.execute("SELECT * FROM drivers WHERE status != 'off-duty' ORDER BY name").fetchall()
    if request.method == 'POST':
        driver_id = request.form.get('driver_id') or None
        conn.execute(
            'INSERT INTO shipments (origin_hub, destination_hub, cargo_type, weight_lbs, deadline, total_pay, notes, driver_id) '
            'VALUES (?,?,?,?,?,?,?,?)',
            (request.form['origin_hub'], request.form['destination_hub'],
             request.form['cargo_type'], float(request.form['weight_lbs']),
             request.form['deadline'], float(request.form['total_pay']),
             request.form.get('notes', ''), driver_id)
        )
        conn.commit()
        conn.close()
        flash('Shipment added.', 'success')
        return redirect(url_for('shipments'))
    conn.close()
    return render_template('shipment_form.html', hubs=hubs, drivers=drivers, shipment=None)


@app.route('/shipments/<int:id>/edit', methods=['GET', 'POST'])
def edit_shipment(id):
    conn = db.get_db()
    shipment = conn.execute('SELECT * FROM shipments WHERE id=?', (id,)).fetchone()
    hubs    = conn.execute('SELECT * FROM hubs ORDER BY city').fetchall()
    drivers = conn.execute('SELECT * FROM drivers ORDER BY name').fetchall()
    if not shipment:
        flash('Shipment not found.', 'danger')
        conn.close()
        return redirect(url_for('shipments'))
    if request.method == 'POST':
        driver_id = request.form.get('driver_id') or None
        conn.execute(
            'UPDATE shipments SET origin_hub=?, destination_hub=?, cargo_type=?, '
            'weight_lbs=?, deadline=?, total_pay=?, notes=?, status=?, driver_id=? WHERE id=?',
            (request.form['origin_hub'], request.form['destination_hub'],
             request.form['cargo_type'], float(request.form['weight_lbs']),
             request.form['deadline'], float(request.form['total_pay']),
             request.form.get('notes', ''), request.form['status'], driver_id, id)
        )
        conn.commit()
        conn.close()
        flash('Shipment updated.', 'success')
        return redirect(url_for('shipments'))
    conn.close()
    return render_template('shipment_form.html', hubs=hubs, drivers=drivers, shipment=shipment)


@app.route('/shipments/<int:id>/delete', methods=['POST'])
def delete_shipment(id):
    conn = db.get_db()
    conn.execute('DELETE FROM shipments WHERE id=?', (id,))
    conn.commit()
    conn.close()
    flash('Shipment deleted.', 'warning')
    return redirect(url_for('shipments'))


@app.route('/shipments/<int:id>/status', methods=['POST'])
def update_status(id):
    conn = db.get_db()
    conn.execute('UPDATE shipments SET status=? WHERE id=?', (request.form['status'], id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('shipments'))


@app.route('/shipments/<int:id>/route')
def shipment_route(id):
    conn = db.get_db()
    shipment = conn.execute(
        "SELECT s.*, h1.city AS origin_city, h1.code AS origin_code, "
        "h2.city AS dest_city, h2.code AS dest_code, "
        "d.name AS driver_name, d.phone AS driver_phone, d.license_number AS driver_license "
        "FROM shipments s "
        "JOIN hubs h1 ON s.origin_hub=h1.id "
        "JOIN hubs h2 ON s.destination_hub=h2.id "
        "LEFT JOIN drivers d ON s.driver_id=d.id "
        "WHERE s.id=?", (id,)
    ).fetchone()
    if not shipment:
        flash('Shipment not found.', 'danger')
        conn.close()
        return redirect(url_for('shipments'))
    result = routing.get_route(conn, shipment['origin_hub'], shipment['destination_hub'])
    conn.close()
    rate_per_mile = 0
    is_good = False
    if result and result['distance'] > 0:
        rate_per_mile = round(shipment['total_pay'] / result['distance'], 2)
        is_good = shipment['total_pay'] >= 3.5 * result['distance']
    return render_template('route_detail.html', shipment=shipment, route=result,
                           is_good=is_good, rate_per_mile=rate_per_mile)


# ── Hubs & Routes ──────────────────────────────────────────────────────────

@app.route('/hubs')
def hubs():
    conn = db.get_db()
    all_hubs = conn.execute('SELECT * FROM hubs ORDER BY city').fetchall()
    all_routes = conn.execute(
        "SELECT r.*, h1.city AS from_city, h1.code AS from_code, "
        "h2.city AS to_city, h2.code AS to_code "
        "FROM hub_routes r "
        "JOIN hubs h1 ON r.hub_from=h1.id "
        "JOIN hubs h2 ON r.hub_to=h2.id "
        "ORDER BY h1.city, h2.city"
    ).fetchall()
    conn.close()
    return render_template('hubs.html', hubs=all_hubs, routes=all_routes)


@app.route('/hubs/new', methods=['POST'])
def new_hub():
    conn = db.get_db()
    try:
        conn.execute(
            'INSERT INTO hubs (name, city, state, code) VALUES (?,?,?,?)',
            (request.form['name'], request.form['city'],
             request.form['state'], request.form['code'].upper())
        )
        conn.commit()
        flash(f"Hub {request.form['city']} added.", 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    conn.close()
    return redirect(url_for('hubs'))


@app.route('/hubs/<int:id>/edit', methods=['POST'])
def edit_hub(id):
    conn = db.get_db()
    try:
        conn.execute(
            'UPDATE hubs SET name=?, city=?, state=?, code=? WHERE id=?',
            (request.form['name'], request.form['city'],
             request.form['state'], request.form['code'].upper(), id)
        )
        conn.commit()
        flash('Hub updated.', 'success')
    except Exception as e:
        flash(f'Error: {e}', 'danger')
    conn.close()
    return redirect(url_for('hubs'))


@app.route('/hubs/<int:id>/delete', methods=['POST'])
def delete_hub(id):
    conn = db.get_db()
    used = conn.execute(
        'SELECT COUNT(*) FROM shipments WHERE origin_hub=? OR destination_hub=?', (id, id)
    ).fetchone()[0]
    if used:
        flash('Cannot delete — hub is referenced by existing shipments.', 'danger')
    else:
        conn.execute('DELETE FROM hub_routes WHERE hub_from=? OR hub_to=?', (id, id))
        conn.execute('DELETE FROM hubs WHERE id=?', (id,))
        conn.commit()
        flash('Hub deleted.', 'warning')
    conn.close()
    return redirect(url_for('hubs'))


@app.route('/routes/new', methods=['POST'])
def new_route():
    conn = db.get_db()
    hub_from = int(request.form['hub_from'])
    hub_to = int(request.form['hub_to'])
    distance = float(request.form['distance_miles'])
    exists = conn.execute(
        'SELECT COUNT(*) FROM hub_routes WHERE (hub_from=? AND hub_to=?) OR (hub_from=? AND hub_to=?)',
        (hub_from, hub_to, hub_to, hub_from)
    ).fetchone()[0]
    if exists:
        flash('A route between those hubs already exists.', 'warning')
    elif hub_from == hub_to:
        flash('Origin and destination must be different.', 'danger')
    else:
        conn.execute(
            'INSERT INTO hub_routes (hub_from, hub_to, distance_miles) VALUES (?,?,?)',
            (hub_from, hub_to, distance)
        )
        conn.commit()
        flash('Route added.', 'success')
    conn.close()
    return redirect(url_for('hubs'))


@app.route('/routes/<int:id>/edit', methods=['POST'])
def edit_route(id):
    conn = db.get_db()
    conn.execute('UPDATE hub_routes SET distance_miles=? WHERE id=?',
                 (float(request.form['distance_miles']), id))
    conn.commit()
    conn.close()
    flash('Route updated.', 'success')
    return redirect(url_for('hubs'))


@app.route('/routes/<int:id>/delete', methods=['POST'])
def delete_route(id):
    conn = db.get_db()
    conn.execute('DELETE FROM hub_routes WHERE id=?', (id,))
    conn.commit()
    conn.close()
    flash('Route deleted.', 'warning')
    return redirect(url_for('hubs'))


# ── Analytics ──────────────────────────────────────────────────────────────

@app.route('/analytics')
def analytics():
    conn = db.get_db()
    status_counts = {r['status']: r['cnt'] for r in conn.execute(
        "SELECT status, COUNT(*) AS cnt FROM shipments GROUP BY status"
    )}
    today = datetime.now().strftime('%Y-%m-%d')
    delayed_count = conn.execute(
        "SELECT COUNT(*) FROM shipments WHERE status != 'delivered' AND deadline < ?", (today,)
    ).fetchone()[0]

    all_shipments = conn.execute('SELECT id, origin_hub, destination_hub, total_pay FROM shipments').fetchall()
    good = bad = 0
    rates = []
    for s in all_shipments:
        result = routing.get_route(conn, s['origin_hub'], s['destination_hub'])
        if result and result['distance'] > 0:
            rate = s['total_pay'] / result['distance']
            rates.append(rate)
            if s['total_pay'] >= 3.5 * result['distance']:
                good += 1
            else:
                bad += 1

    avg_rate = round(sum(rates) / len(rates), 2) if rates else 0

    top_routes = conn.execute(
        "SELECT h1.city || ' → ' || h2.city AS route, COUNT(*) AS cnt "
        "FROM shipments s "
        "JOIN hubs h1 ON s.origin_hub=h1.id "
        "JOIN hubs h2 ON s.destination_hub=h2.id "
        "GROUP BY s.origin_hub, s.destination_hub "
        "ORDER BY cnt DESC LIMIT 5"
    ).fetchall()

    conn.close()
    return render_template('analytics.html',
                           status_counts=status_counts,
                           good_count=good, bad_count=bad,
                           avg_rate=avg_rate,
                           delayed_count=delayed_count,
                           top_routes=top_routes,
                           total=len(all_shipments))


# ── CSV Import ─────────────────────────────────────────────────────────────

@app.route('/import', methods=['GET', 'POST'])
def import_csv():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename.endswith('.csv'):
            flash('Please upload a valid .csv file.', 'danger')
            return redirect(url_for('import_csv'))
        conn = db.get_db()
        hub_map = {r['code']: r['id'] for r in conn.execute('SELECT id, code FROM hubs')}
        stream = io.StringIO(file.stream.read().decode('utf-8'))
        reader = csv.DictReader(stream)
        count = 0
        errors = []
        for i, row in enumerate(reader, 1):
            try:
                origin_id = hub_map.get(row['origin_code'].strip().upper())
                dest_id = hub_map.get(row['destination_code'].strip().upper())
                if not origin_id or not dest_id:
                    errors.append(f'Row {i}: unknown hub code.')
                    continue
                conn.execute(
                    'INSERT INTO shipments (origin_hub, destination_hub, cargo_type, weight_lbs, deadline, total_pay, notes) '
                    'VALUES (?,?,?,?,?,?,?)',
                    (origin_id, dest_id, row['cargo_type'].strip(),
                     float(row['weight_lbs']), row['deadline'].strip(),
                     float(row['total_pay']), row.get('notes', '').strip())
                )
                count += 1
            except Exception as e:
                errors.append(f'Row {i}: {e}')
        conn.commit()
        conn.close()
        flash(f'Imported {count} shipment(s).', 'success')
        for err in errors[:5]:
            flash(err, 'warning')
        return redirect(url_for('shipments'))
    return render_template('import.html')


# ── Drivers ────────────────────────────────────────────────────────────────

@app.route('/drivers')
def drivers():
    conn = db.get_db()
    all_drivers = conn.execute('SELECT * FROM drivers ORDER BY name').fetchall()
    # For each driver, find their active (non-delivered) shipment if any
    active_loads = {}
    for row in conn.execute(
        "SELECT s.id, s.driver_id, s.deadline, s.cargo_type, s.status, s.created_at, "
        "h1.city AS origin_city, h2.city AS dest_city "
        "FROM shipments s "
        "JOIN hubs h1 ON s.origin_hub=h1.id "
        "JOIN hubs h2 ON s.destination_hub=h2.id "
        "WHERE s.status != 'delivered' AND s.driver_id IS NOT NULL"
    ):
        # Keep only the most recent active load per driver
        if row['driver_id'] not in active_loads:
            active_loads[row['driver_id']] = row
    conn.close()
    return render_template('drivers.html', drivers=all_drivers, active_loads=active_loads)


@app.route('/drivers/new', methods=['POST'])
def new_driver():
    conn = db.get_db()
    conn.execute(
        'INSERT INTO drivers (name, phone, license_number, status) VALUES (?,?,?,?)',
        (request.form['name'], request.form.get('phone', ''),
         request.form.get('license_number', ''), request.form.get('status', 'available'))
    )
    conn.commit()
    conn.close()
    flash(f"Driver {request.form['name']} added.", 'success')
    return redirect(url_for('drivers'))


@app.route('/drivers/<int:id>/edit', methods=['POST'])
def edit_driver(id):
    conn = db.get_db()
    conn.execute(
        'UPDATE drivers SET name=?, phone=?, license_number=?, status=? WHERE id=?',
        (request.form['name'], request.form.get('phone', ''),
         request.form.get('license_number', ''), request.form.get('status', 'available'), id)
    )
    conn.commit()
    conn.close()
    flash('Driver updated.', 'success')
    return redirect(url_for('drivers'))


@app.route('/drivers/<int:id>/delete', methods=['POST'])
def delete_driver(id):
    conn = db.get_db()
    active = conn.execute(
        "SELECT COUNT(*) FROM shipments WHERE driver_id=? AND status != 'delivered'", (id,)
    ).fetchone()[0]
    if active:
        flash('Cannot delete — driver has active shipments.', 'danger')
    else:
        conn.execute('UPDATE shipments SET driver_id=NULL WHERE driver_id=?', (id,))
        conn.execute('DELETE FROM drivers WHERE id=?', (id,))
        conn.commit()
        flash('Driver deleted.', 'warning')
    conn.close()
    return redirect(url_for('drivers'))


# ── API ────────────────────────────────────────────────────────────────────

@app.route('/api/hubs')
def api_hubs():
    conn = db.get_db()
    hubs = [dict(r) for r in conn.execute('SELECT * FROM hubs ORDER BY city')]
    routes = [dict(r) for r in conn.execute('SELECT * FROM hub_routes')]
    conn.close()
    return jsonify({'hubs': hubs, 'routes': routes})


@app.route('/api/distance/hubs/<int:origin_id>/<int:dest_id>')
def api_hub_distance(origin_id, dest_id):
    conn = db.get_db()
    result = routing.get_route(conn, origin_id, dest_id)
    conn.close()
    if not result:
        return jsonify({'error': 'No route found between these hubs.'}), 404
    GOOD_RATE = 3.5
    return jsonify({
        'distance': result['distance'],
        'hops': result['hops'],
        'min_good_pay': round(result['distance'] * GOOD_RATE, 2),
        'path': [
            {'code': h['code'], 'city': h['city'], 'state': h['state']}
            for h in result['path_details']
        ],
    })


if __name__ == '__main__':
    app.run(debug=True)
