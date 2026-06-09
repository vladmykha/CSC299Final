from flask import Blueprint, flash, redirect, render_template, request, url_for
import db
import routing

bp = Blueprint('shipments', __name__)


@bp.route('/shipments')
def list_shipments():
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
    params, conditions = [], []
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
    return render_template('shipments.html', shipments=rows,
                           status_filter=status_filter, search=search)


@bp.route('/shipments/new', methods=['GET', 'POST'])
def new_shipment():
    conn = db.get_db()
    hubs    = conn.execute('SELECT * FROM hubs ORDER BY city').fetchall()
    drivers = conn.execute("SELECT * FROM drivers WHERE status != 'off-duty' ORDER BY name").fetchall()
    if request.method == 'POST':
        driver_id = request.form.get('driver_id') or None
        conn.execute(
            'INSERT INTO shipments (origin_hub, destination_hub, cargo_type, weight_lbs, '
            'deadline, total_pay, notes, driver_id) VALUES (?,?,?,?,?,?,?,?)',
            (request.form['origin_hub'], request.form['destination_hub'],
             request.form['cargo_type'], float(request.form['weight_lbs']),
             request.form['deadline'], float(request.form['total_pay']),
             request.form.get('notes', ''), driver_id)
        )
        conn.commit()
        conn.close()
        flash('Shipment added.', 'success')
        return redirect(url_for('shipments.list_shipments'))
    conn.close()
    return render_template('shipment_form.html', hubs=hubs, drivers=drivers, shipment=None)


@bp.route('/shipments/<int:id>/edit', methods=['GET', 'POST'])
def edit_shipment(id):
    conn = db.get_db()
    shipment = conn.execute('SELECT * FROM shipments WHERE id=?', (id,)).fetchone()
    hubs    = conn.execute('SELECT * FROM hubs ORDER BY city').fetchall()
    drivers = conn.execute('SELECT * FROM drivers ORDER BY name').fetchall()
    if not shipment:
        flash('Shipment not found.', 'danger')
        conn.close()
        return redirect(url_for('shipments.list_shipments'))
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
        return redirect(url_for('shipments.list_shipments'))
    conn.close()
    return render_template('shipment_form.html', hubs=hubs, drivers=drivers, shipment=shipment)


@bp.route('/shipments/<int:id>/delete', methods=['POST'])
def delete_shipment(id):
    conn = db.get_db()
    conn.execute('DELETE FROM shipments WHERE id=?', (id,))
    conn.commit()
    conn.close()
    flash('Shipment deleted.', 'warning')
    return redirect(url_for('shipments.list_shipments'))


@bp.route('/shipments/<int:id>/status', methods=['POST'])
def update_status(id):
    conn = db.get_db()
    conn.execute('UPDATE shipments SET status=? WHERE id=?', (request.form['status'], id))
    conn.commit()
    conn.close()
    return redirect(request.referrer or url_for('shipments.list_shipments'))


@bp.route('/shipments/<int:id>/route')
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
        return redirect(url_for('shipments.list_shipments'))
    result = routing.get_route(conn, shipment['origin_hub'], shipment['destination_hub'])
    conn.close()
    rate_per_mile, is_good = 0, False
    if result and result['distance'] > 0:
        rate_per_mile = round(shipment['total_pay'] / result['distance'], 2)
        is_good = shipment['total_pay'] >= 3.5 * result['distance']
    return render_template('route_detail.html', shipment=shipment, route=result,
                           is_good=is_good, rate_per_mile=rate_per_mile)
