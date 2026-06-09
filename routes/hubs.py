from flask import Blueprint, flash, redirect, render_template, request, url_for
import db

bp = Blueprint('hubs', __name__)


@bp.route('/hubs')
def list_hubs():
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


@bp.route('/hubs/new', methods=['POST'])
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
    return redirect(url_for('hubs.list_hubs'))


@bp.route('/hubs/<int:id>/edit', methods=['POST'])
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
    return redirect(url_for('hubs.list_hubs'))


@bp.route('/hubs/<int:id>/delete', methods=['POST'])
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
    return redirect(url_for('hubs.list_hubs'))


@bp.route('/routes/new', methods=['POST'])
def new_route():
    conn = db.get_db()
    hub_from = int(request.form['hub_from'])
    hub_to   = int(request.form['hub_to'])
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
        conn.execute('INSERT INTO hub_routes (hub_from, hub_to, distance_miles) VALUES (?,?,?)',
                     (hub_from, hub_to, distance))
        conn.commit()
        flash('Route added.', 'success')
    conn.close()
    return redirect(url_for('hubs.list_hubs'))


@bp.route('/routes/<int:id>/edit', methods=['POST'])
def edit_route(id):
    conn = db.get_db()
    conn.execute('UPDATE hub_routes SET distance_miles=? WHERE id=?',
                 (float(request.form['distance_miles']), id))
    conn.commit()
    conn.close()
    flash('Route updated.', 'success')
    return redirect(url_for('hubs.list_hubs'))


@bp.route('/routes/<int:id>/delete', methods=['POST'])
def delete_route(id):
    conn = db.get_db()
    conn.execute('DELETE FROM hub_routes WHERE id=?', (id,))
    conn.commit()
    conn.close()
    flash('Route deleted.', 'warning')
    return redirect(url_for('hubs.list_hubs'))
