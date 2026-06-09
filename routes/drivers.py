from flask import Blueprint, flash, redirect, render_template, request, url_for
import db

bp = Blueprint('drivers', __name__)


@bp.route('/drivers')
def list_drivers():
    conn = db.get_db()
    all_drivers = conn.execute('SELECT * FROM drivers ORDER BY name').fetchall()
    active_loads = {}
    for row in conn.execute(
        "SELECT s.id, s.driver_id, s.deadline, s.cargo_type, s.status, s.created_at, "
        "h1.city AS origin_city, h2.city AS dest_city "
        "FROM shipments s "
        "JOIN hubs h1 ON s.origin_hub=h1.id "
        "JOIN hubs h2 ON s.destination_hub=h2.id "
        "WHERE s.status != 'delivered' AND s.driver_id IS NOT NULL"
    ):
        if row['driver_id'] not in active_loads:
            active_loads[row['driver_id']] = row
    conn.close()
    return render_template('drivers.html', drivers=all_drivers, active_loads=active_loads)


@bp.route('/drivers/new', methods=['POST'])
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
    return redirect(url_for('drivers.list_drivers'))


@bp.route('/drivers/<int:id>/edit', methods=['POST'])
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
    return redirect(url_for('drivers.list_drivers'))


@bp.route('/drivers/<int:id>/delete', methods=['POST'])
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
    return redirect(url_for('drivers.list_drivers'))
